# rag-hnsw/backend/main.py
from fastapi import FastAPI, WebSocket, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from starlette.websockets import WebSocketDisconnect, WebSocketState
import logging
from utils.pdf_utils import get_pdf
from utils.db_utils import get_db_connection, get_available_categories, get_toc_data
from utils.websocket_utils import get_openai_client, process_search_results, generate_ai_response, generate_first_ai_response
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

client = get_openai_client()

@app.get("/categories")
async def get_categories():
    try:
        categories = get_available_categories()
        return {"categories": categories}
    except Exception as e:
        logger.error(f"Error fetching categories: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.get("/pdf/{document_type}/{category}/{path:path}")
async def serve_pdf(document_type: str, category: str, path: str, start_page: int = None, end_page: int = None):
    return get_pdf(document_type, category, path, start_page, end_page)

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    logger.info("WebSocket connection established")

    db_pool = get_db_connection()

    try:
        with db_pool.connection() as conn:
            while websocket.client_state == WebSocketState.CONNECTED:
                await process_websocket_message(websocket, conn)
    except WebSocketDisconnect:
        logger.info("WebSocket disconnected")
    except Exception as e:
        logger.error(f"Unexpected error in WebSocket connection: {str(e)}")
        logger.exception("Full traceback:")
    finally:
        logger.info("WebSocket connection closed")
        if websocket.client_state == WebSocketState.CONNECTED:
            await websocket.close()

async def process_websocket_message(websocket: WebSocket, conn):
    try:
        data = await websocket.receive_json()
        question = data["question"]
        category = data.get("category")
        top_n = int(data.get("top_n", 3))

        if not category:
            await websocket.send_json({"error": "Category is required"})
            return

        logger.debug(f"Processing question: {question[:50]}... in category: {category}")

        # 類似検索の処理
        question_vector = client.embeddings.create(
            input=question,
            model="text-embedding-3-large" if ENABLE_OPENAI else AZURE_OPENAI_EMBEDDINGS_DEPLOYMENT
        ).data[0].embedding

        manual_results, faq_results, manual_texts, faq_texts = await process_search_results(conn, question_vector, category, top_n)

        logger.debug(f"Manual results: {manual_results}")
        logger.debug(f"FAQ results: {faq_results}")

        await websocket.send_json({"manual_results": manual_results})
        await websocket.send_json({"faq_results": faq_results})

        logger.debug(f"Sent search results for question: {question[:50]}... in category: {category}")

        # 1回目のAI応答の生成
        toc_data = get_toc_data(conn, category)
        first_ai_response = await generate_first_ai_response(client, question, toc_data, websocket, category)

        # 2回目（最終）のAI応答の生成
        if manual_texts or faq_texts:
            await generate_ai_response(client, question, manual_texts, faq_texts, first_ai_response, websocket)
        else:
            await websocket.send_json({"ai_response_chunk": "申し訳ありませんが、該当する情報が見つかりませんでした。"})
            await websocket.send_json({"ai_response_end": True})
            logger.info("No relevant information found for the query")

    except WebSocketDisconnect:
        logger.info("WebSocket disconnected during message processing")
        raise
    except Exception as e:
        logger.error(f"Error processing message: {str(e)}")
        if websocket.client_state == WebSocketState.CONNECTED:
            await websocket.send_json({"error": "An error occurred while processing your request"})

if __name__ == "__main__":
    import uvicorn
    logger.info("Starting the application")
    uvicorn.run(app, host="0.0.0.0", port=8001, log_level="debug")
