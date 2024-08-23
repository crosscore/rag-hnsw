# rag-hnsw/frontend/main.py
# rag-hnsw/frontend/main.py
from fastapi import FastAPI, WebSocket, Request, WebSocketDisconnect, HTTPException
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, StreamingResponse
import os
import websockets
import asyncio
import logging
import httpx
import json
from urllib.parse import unquote, quote

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

BACKEND_URL = os.getenv("BACKEND_URL", "ws://backend:8001")
BACKEND_HTTP_URL = os.getenv("BACKEND_HTTP_URL", "http://backend:8001")

@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    return FileResponse("/app/static/fastapi-1.svg", media_type="image/svg+xml")

@app.get("/")
async def read_root(request: Request):
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{BACKEND_HTTP_URL}/categories")
            categories = response.json()["categories"]
            categories = [{"name": name, "value": value} for name, value in categories.items()]
    except Exception as e:
        logger.error(f"Error fetching categories: {str(e)}")
        categories = []

    return templates.TemplateResponse("index.html", {"request": request, "categories": categories})

@app.get("/pdf/{document_type}/{category}/{path:path}")
async def stream_pdf(document_type: str, category: str, path: str, page: int = None, start_page: int = None, end_page: int = None):
    decoded_path = unquote(path)
    url = f"{BACKEND_HTTP_URL}/pdf/{document_type}/{category}/{quote(decoded_path)}"
    params = {}
    if page is not None:
        params['page'] = page
    if start_page is not None:
        params['start_page'] = start_page
    if end_page is not None:
        params['end_page'] = end_page

    logger.info(f"Proxying PDF from backend: {url}")

    async def stream_response():
        async with httpx.AsyncClient() as client:
            async with client.stream('GET', url, params=params) as response:
                if response.status_code == 200:
                    async for chunk in response.aiter_bytes():
                        yield chunk
                else:
                    error_content = await response.aread()
                    error_message = error_content.decode('utf-8', errors='replace')
                    logger.error(f"Error from backend: {error_message}")
                    raise HTTPException(status_code=response.status_code, detail=error_message)

    try:
        headers = {
            "Content-Disposition": f'inline; filename*=UTF-8\'\'{quote(os.path.basename(decoded_path))}'
        }
        return StreamingResponse(
            stream_response(),
            media_type="application/pdf",
            headers=headers
        )
    except httpx.HTTPStatusError as e:
        logger.error(f"HTTP error occurred while fetching PDF: {str(e)}")
        raise HTTPException(status_code=e.response.status_code, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error occurred while fetching PDF: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    backend_ws_url = f"{BACKEND_URL}/ws"

    try:
        async with websockets.connect(backend_ws_url) as backend_ws:
            await asyncio.gather(
                forward_to_backend(websocket, backend_ws),
                forward_to_client(websocket, backend_ws)
            )
    except WebSocketDisconnect:
        logger.info("WebSocket disconnected")
    except Exception as e:
        logger.error(f"Error: {str(e)}")

async def forward_to_backend(client_ws: WebSocket, backend_ws: websockets.WebSocketClientProtocol):
    try:
        while True:
            data = await client_ws.receive_text()
            await backend_ws.send(data)
    except WebSocketDisconnect:
        await backend_ws.close()

async def forward_to_client(client_ws: WebSocket, backend_ws: websockets.WebSocketClientProtocol):
    try:
        while True:
            response = await backend_ws.recv()
            response_data = json.loads(response)
            logger.debug(f"Received from backend: {response_data}")

            if "manual_results" in response_data:
                logger.debug(f"Sending manual results to client: {response_data['manual_results']}")
                await client_ws.send_json({"manual_results": response_data["manual_results"]})
            elif "faq_results" in response_data:
                logger.debug(f"Sending FAQ results to client: {response_data['faq_results']}")
                await client_ws.send_json({"faq_results": response_data["faq_results"]})
            elif "ai_response_chunk" in response_data:
                await client_ws.send_json({"ai_response_chunk": response_data["ai_response_chunk"]})
            elif "ai_response_end" in response_data:
                await client_ws.send_json({"ai_response_end": True})
            else:
                await client_ws.send_text(response)
    except WebSocketDisconnect:
        await client_ws.close()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
