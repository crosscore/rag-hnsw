# rag-hnsw/backend/main.py
from fastapi import FastAPI, WebSocket, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from openai import OpenAI, AzureOpenAI
from starlette.websockets import WebSocketDisconnect
import logging
import os
from utils.pdf_utils import get_pdf
from utils.db_utils import get_db_connection, get_search_query, get_available_categories, execute_search_query
from config import *

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
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
    try:
        while True:
            data = await websocket.receive_json()
            question = data["question"]
            category = data.get("category")
            top_n = int(data.get("top_n", 3))

            if not category:
                await websocket.send_json({"error": "Category is required"})
                continue

            try:
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

                with get_db_connection() as (conn, cursor):
                    manual_results = execute_search_query(conn, cursor, question_vector, category, top_n, MANUAL_TABLE_NAME)
                    faq_results = execute_search_query(conn, cursor, question_vector, category, top_n, FAQ_TABLE_NAME)
                    
                    conn.commit()

                formatted_manual_results = []
                formatted_faq_results = []
                manual_texts = []
                faq_texts = []

                for result in manual_results:
                    file_name, document_page, page_text, document_type, distance = result
                    formatted_result = {
                        "file_name": str(file_name),
                        "page": int(document_page),
                        "page_text": str(page_text),
                        "distance": float(distance),
                        "category": category,
                        "document_type": str(document_type),
                        "link_text": f"/{document_type}/{category}/{os.path.basename(file_name)}, p.{document_page}",
                        "link": f"pdf/{document_type}/{category}/{os.path.basename(file_name)}?page={document_page}",
                    }
                    formatted_manual_results.append(formatted_result)
                    manual_texts.append(page_text)

                for result in faq_results:
                    file_name, document_page, page_text, document_type, distance = result
                    formatted_result = {
                        "file_name": str(file_name),
                        "page": int(document_page),
                        "page_text": str(page_text),
                        "distance": float(distance),
                        "category": category,
                        "document_type": str(document_type),
                        "link_text": f"/{document_type}/{category}/{os.path.basename(file_name)}, p.{document_page}",
                        "link": f"pdf/{document_type}/{category}/{os.path.basename(file_name)}?page={document_page}",
                    }
                    formatted_faq_results.append(formatted_result)
                    faq_texts.append(page_text)

                # Sort results by distance
                formatted_manual_results.sort(key=lambda x: x['distance'])
                formatted_faq_results.sort(key=lambda x: x['distance'])

                # Send manual and FAQ results separately
                await websocket.send_json({"manual_results": formatted_manual_results[:top_n]})
                await websocket.send_json({"faq_results": formatted_faq_results[:top_n]})
                logger.info(f"Sent search results for question: {question[:50]}... in category: {category}")

                # Generate AI response
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
                            max_tokens=100,
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
                        logger.info(f"Sent streaming AI response for question: {question[:50]}...")
                else:
                    await websocket.send_json({"ai_response_chunk": "申し訳ありませんが、該当する情報が見つかりませんでした。"})
                    await websocket.send_json({"ai_response_end": True})
                    logger.info("No relevant information found for the query")

            except Exception as e:
                logger.error(f"Error processing query: {str(e)}")
                logger.exception("Full traceback:")
                await websocket.send_json({"error": f"Error processing query: {str(e)}"})

    except WebSocketDisconnect:
        logger.info("WebSocket disconnected")
    except Exception as e:
        logger.error(f"Unexpected error in WebSocket connection: {str(e)}")
        logger.exception("Full traceback:")

if __name__ == "__main__":
    import uvicorn
    logger.info("Starting the application")
    uvicorn.run(app, host="0.0.0.0", port=8001, log_level="info")
