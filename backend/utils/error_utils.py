# rag-hnsw/backend/utils/error_utils.py
from fastapi import WebSocket
import logging
from functools import wraps

logger = logging.getLogger(__name__)

async def send_error_message(websocket: WebSocket, message: str):
    await websocket.send_json({"error": message})

def websocket_error_handler(func):
    @wraps(func)
    async def wrapper(websocket: WebSocket, *args, **kwargs):
        try:
            return await func(websocket, *args, **kwargs)
        except json.JSONDecodeError:
            logger.error("Received invalid JSON data")
            await send_error_message(websocket, "Invalid JSON data received")
        except KeyError as e:
            logger.error(f"Missing required key in received data: {str(e)}")
            await send_error_message(websocket, f"Missing required data: {str(e)}")
        except Exception as e:
            logger.error(f"Error processing query: {str(e)}")
            logger.exception("Full traceback:")
            await send_error_message(websocket, f"Error processing query: {str(e)}")
    return wrapper
