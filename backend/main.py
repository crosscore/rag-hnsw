# rag-hnsw/backend/main.py
from fastapi import FastAPI, WebSocket, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from openai import OpenAI, AzureOpenAI
from starlette.websockets import WebSocketDisconnect
from psycopg import sql
import logging
import os
import json
from utils.pdf_utils import get_pdf
from utils.db_utils import get_db_connection, get_search_query, get_available_categories, execute_search_query, execute_query
from config import *

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8000", "http://frontend:8000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

if ENABLE_OPENAI:
    client = OpenAI(api_key=OPENAI_API_KEY)
else:
    client = AzureOpenAI(
        azure_endpoint=AZURE_OPENAI_ENDPOINT,
        api_key=AZURE_OPENAI_API_KEY,
        api_version=AZURE_OPENAI_API_VERSION
    )

@app.get("/categories")
async def get_categories():
    try:
        categories = get_available_categories()
        return {"categories": categories}
    except Exception as e:
        logger.error(f"Error fetching categories: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.get("/pdf/{document_type}/{category}/{path:path}")
async def serve_pdf(document_type: str, category: str, path: str, page: int = None):
    return get_pdf(document_type, category, path, page)

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    logger.info("WebSocket connection established")

    db_pool = get_db_connection()

    try:
        with db_pool.connection() as conn:
            while True:
                try:
                    data = await websocket.receive_json()
                    logger.debug(f"Received data: {data}")
                    question = data["question"]
                    category = data.get("category")
                    top_n = int(data.get("top_n", 3))

                    if not category:
                        await websocket.send_json({"error": "Category is required"})
                        continue

                    logger.debug(f"Processing question: {question[:50]}... in category: {category}")

                    if ENABLE_OPENAI:
                        question_vector = client.embeddings.create(
                            input=question,
                            model="text-embedding-3-large"
                        ).data[0].embedding
                    else:
                        question_vector = client.embeddings.create(
                            input=question,
                            model=AZURE_OPENAI_EMBEDDINGS_DEPLOYMENT
                        ).data[0].embedding

                    manual_results = execute_search_query(conn, question_vector, category, top_n, PDF_MANUAL_TABLE)
                    faq_results = execute_search_query(conn, question_vector, category, top_n, PDF_FAQ_TABLE)

                    formatted_manual_results = []
                    formatted_faq_results = []
                    manual_texts = []
                    faq_texts = []

                    for result in manual_results:
                        document_table_id, chunk_no, document_page, chunk_text, distance = result
                        doc_info = execute_query(conn, sql.SQL("""
                            SELECT file_path, file_name FROM {} WHERE id = %s
                        """).format(sql.Identifier(DOCUMENT_TABLE)), (document_table_id,))
                        file_path, file_name = doc_info[0] if doc_info else (None, None)

                        formatted_result = {
                            "file_name": str(file_name),
                            "page": int(document_page),
                            "chunk_text": str(chunk_text),
                            "distance": float(distance),
                            "category": category,
                            "document_type": "manual",
                            "link_text": f"/manual/{category}/{file_name}, p.{document_page}",
                            "link": f"pdf/manual/{category}/{file_name}?page={document_page}",
                        }
                        formatted_manual_results.append(formatted_result)
                        manual_texts.append(chunk_text)

                    for result in faq_results:
                        document_table_id, document_page, faq_no, page_text, distance = result
                        doc_info = execute_query(conn, sql.SQL("""
                            SELECT file_path, file_name FROM {} WHERE id = %s
                        """).format(sql.Identifier(DOCUMENT_TABLE)), (document_table_id,))
                        file_path, file_name = doc_info[0] if doc_info else (None, None)

                        formatted_result = {
                            "file_name": str(file_name),
                            "page": int(document_page),
                            "page_text": str(page_text),
                            "distance": float(distance),
                            "category": category,
                            "document_type": "faq",
                            "link_text": f"/faq/{category}/{file_name}, p.{document_page}",
                            "link": f"pdf/faq/{category}/{file_name}?page={document_page}",
                        }
                        formatted_faq_results.append(formatted_result)
                        faq_texts.append(page_text)

                    formatted_manual_results.sort(key=lambda x: x['distance'])
                    formatted_faq_results.sort(key=lambda x: x['distance'])

                    await websocket.send_json({"manual_results": formatted_manual_results[:top_n]})
                    await websocket.send_json({"faq_results": formatted_faq_results[:top_n]})
                    logger.debug(f"Sent search results for question: {question[:50]}... in category: {category}")

                    if manual_texts or faq_texts:
                        formatted_prompt = f"""
                        ユーザーの質問に対して、参考文書を元に回答して下さい。

                        ユーザーの質問：
                        {question}

                        参考文書(マニュアル)：
                        {' '.join(manual_texts)}

                        参考文書(Q&A):
                        {' '.join(faq_texts)}
                        """

                        if ENABLE_OPENAI:
                            response = client.chat.completions.create(
                                model="gpt-4o-mini",
                                temperature=1.00,
                                max_tokens=250,
                                messages=[
                                    {"role": "system", "content": "You are a helpful assistant."},
                                    {"role": "user", "content": formatted_prompt}
                                ],
                                stream=True
                            )
                        else:
                            response = client.chat.completions.create(
                                model=AZURE_OPENAI_DEPLOYMENT,
                                messages=[
                                    {"role": "system", "content": "You are a helpful assistant."},
                                    {"role": "user", "content": formatted_prompt}
                                ],
                                stream=True
                            )

                        try:
                            for chunk in response:
                                if chunk.choices and len(chunk.choices) > 0:
                                    if hasattr(chunk.choices[0], 'delta') and hasattr(chunk.choices[0].delta, 'content'):
                                        content = chunk.choices[0].delta.content
                                        if content:
                                            await websocket.send_json({"ai_response_chunk": content})
                                else:
                                    logger.warning("Received an empty chunk from OpenAI API")
                        except Exception as e:
                            logger.error(f"Error processing AI response: {str(e)}")
                            await websocket.send_json({"error": "Error generating AI response"})
                        finally:
                            await websocket.send_json({"ai_response_end": True})
                            logger.debug(f"Sent streaming AI response for question: {question[:50]}...")
                    else:
                        await websocket.send_json({"ai_response_chunk": "申し訳ありませんが、該当する情報が見つかりませんでした。"})
                        await websocket.send_json({"ai_response_end": True})
                        logger.info("No relevant information found for the query")

                except json.JSONDecodeError:
                    logger.error("Received invalid JSON data")
                    await websocket.send_json({"error": "Invalid JSON data received"})
                except KeyError as e:
                    logger.error(f"Missing required key in received data: {str(e)}")
                    await websocket.send_json({"error": f"Missing required data: {str(e)}"})
                except Exception as e:
                    logger.error(f"Error processing query: {str(e)}")
                    logger.exception("Full traceback:")
                    await websocket.send_json({"error": f"Error processing query: {str(e)}"})

    except WebSocketDisconnect:
        logger.info("WebSocket disconnected")
    except Exception as e:
        logger.error(f"Unexpected error in WebSocket connection: {str(e)}")
        logger.exception("Full traceback:")
    finally:
        pass

if __name__ == "__main__":
    import uvicorn
    logger.info("Starting the application")
    uvicorn.run(app, host="0.0.0.0", port=8001, log_level="debug")
