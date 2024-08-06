# rag-hnsw/backend/main.py
from fastapi import FastAPI, WebSocket, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from openai import OpenAI, AzureOpenAI
from starlette.websockets import WebSocketDisconnect
import logging
import os
from utils.pdf_utils import get_pdf
from utils.db_utils import get_db_connection, get_search_query, get_available_categories
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

@app.get("/pdf/{category}/{path:path}")
async def serve_pdf(category: str, path: str, page: int = None):
    return get_pdf(category, path, page)

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
                    cursor.execute(get_search_query(INDEX_TYPE, category), (question_vector, top_n))
                    results = cursor.fetchall()
                    conn.commit()

                formatted_results = []
                chunk_texts = []
                for file_name, document_page, chunk_no, chunk_text, distance in results:
                    result = {
                        "file_name": str(file_name),
                        "page": int(document_page),
                        "chunk_no": int(chunk_no),
                        "chunk_text": str(chunk_text),
                        "distance": float(distance),
                        "category": category,
                        "link_text": f"/{category}/{os.path.basename(file_name)}, p.{document_page}",
                        "link": f"pdf/{category}/{os.path.basename(file_name)}?page={document_page}",
                    }
                    formatted_results.append(result)
                    chunk_texts.append(chunk_text)

                await websocket.send_json({"results": formatted_results, "chunk_texts": chunk_texts})
                logger.info(f"Sent search results for question: {question[:50]}... in category: {category}")

                # Generate AI response
                if chunk_texts:
                    formatted_prompt = f"""
                    以下のユーザーの質問に対して、参考文書を元に回答して下さい。
                    参考文書が1つも存在しない場合はそのことをユーザーに伝えて下さい。

                    ユーザーの質問：
                    {question}

                    参考文書：
                    """
                    for i, chunk in enumerate(chunk_texts, 1):
                        formatted_prompt += f"{i}. {chunk}\n"

                if ENABLE_OPENAI:
                    response = client.chat.completions.create(
                        model="gpt-4o-mini",
                        temperature=1.00,
                        max_tokens=150,
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

                for chunk in response:
                    if chunk.choices[0].delta.content:
                        await websocket.send_json({"ai_response_chunk": chunk.choices[0].delta.content})

                await websocket.send_json({"ai_response_end": True})
                logger.info(f"Sent streaming AI response for question: {question[:50]}...")

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
