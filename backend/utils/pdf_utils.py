# rag-hnsw/backend/utils/pdf_utils.py
import os
from fastapi import HTTPException
from fastapi.responses import StreamingResponse, FileResponse
from io import BytesIO
from pypdf import PdfReader, PdfWriter
import logging
from config import PDF_INPUT_DIR

logger = logging.getLogger(__name__)

def get_pdf(category: str, path: str, page: int = None):
    file_path = os.path.join(PDF_INPUT_DIR, category, path)
    logger.info(f"Attempting to access PDF file: {file_path}")
    
    if not os.path.exists(file_path):
        logger.error(f"PDF file not found: {file_path}")
        raise HTTPException(status_code=404, detail=f"PDF file not found: {file_path}")

    try:
        if page is not None and page > 0:
            logger.info(f"Extracting page {page} from PDF file: {file_path}")
            pdf_reader = PdfReader(file_path)
            
            if page > len(pdf_reader.pages):
                logger.error(f"Invalid page number: {page}. PDF has {len(pdf_reader.pages)} pages.")
                raise HTTPException(status_code=400, detail=f"Invalid page number: {page}. PDF has {len(pdf_reader.pages)} pages.")
            
            pdf_writer = PdfWriter()
            pdf_writer.add_page(pdf_reader.pages[page - 1])
            pdf_bytes = BytesIO()
            pdf_writer.write(pdf_bytes)
            pdf_bytes.seek(0)
            return StreamingResponse(pdf_bytes, media_type="application/pdf", headers={"Content-Disposition": f'inline; filename="{os.path.basename(file_path)}_page_{page}.pdf"'})
        else:
            logger.info(f"Serving full PDF file: {file_path}")
            return FileResponse(file_path, media_type="application/pdf", filename=os.path.basename(file_path))
    except Exception as e:
        logger.error(f"Error serving PDF file: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error serving PDF file: {str(e)}")
