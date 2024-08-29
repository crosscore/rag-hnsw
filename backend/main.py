# backend/main.py
from fastapi import FastAPI, WebSocket, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from starlette.websockets import WebSocketDisconnect, WebSocketState
import logging
from utils.pdf_utils import get_pdf
from utils.db_utils import get_db_connection, get_available_categories
from utils.langchain_utils import get_langchain_client, process_websocket_message_langchain
from config import *

logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8000", "http://frontend:8000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

embeddings, llm = get_langchain_client()

@app.get("/categories")
async def get_categories():
    try:
        categories = get_available_categories()
        return {"categories": categories}
    except Exception as e:
        logger.error(f"Error fetching categories: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.get("/pdf/{document_type}/{category}/{path:path}")
async def serve_pdf(document_type: str, category: str, path: str, page: int = None, start_page: int = None, end_page: int = None):
    return get_pdf(document_type, category, path, page, start_page, end_page)

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    logger.info("WebSocket connection established")

    db_pool = get_db_connection()

    try:
        with db_pool.connection() as conn:
            while websocket.client_state == WebSocketState.CONNECTED:
                data = await websocket.receive_json()
                await process_websocket_message_langchain(websocket, conn, data, embeddings, llm)
    except WebSocketDisconnect:
        logger.info("WebSocket disconnected")
    except Exception as e:
        logger.error(f"Unexpected error in WebSocket connection: {str(e)}")
        logger.exception("Full traceback:")
    finally:
        logger.info("WebSocket connection closed")
        if websocket.client_state == WebSocketState.CONNECTED:
            await websocket.close()

if __name__ == "__main__":
    import uvicorn
    logger.info("Starting the application")
    uvicorn.run(app, host="0.0.0.0", port=8001, log_level="debug")
