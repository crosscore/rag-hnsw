# backend/utils/pdf_utils.py
import os
from fastapi import HTTPException
from fastapi.responses import StreamingResponse, FileResponse
from io import BytesIO
from pypdf import PdfReader, PdfWriter
import logging
from urllib.parse import quote
from config import PDF_MANUAL_DIR, PDF_FAQ_DIR

logger = logging.getLogger(__name__)

def create_pdf_range(file_path: str, start_page: int, end_page: int):
    try:
        pdf_reader = PdfReader(file_path)
        pdf_writer = PdfWriter()

        for page_num in range(start_page - 1, min(end_page, len(pdf_reader.pages))):
            pdf_writer.add_page(pdf_reader.pages[page_num])

        pdf_bytes = BytesIO()
        pdf_writer.write(pdf_bytes)
        pdf_bytes.seek(0)

        return pdf_bytes
    except Exception as e:
        logger.error(f"Error creating PDF range: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error creating PDF range: {str(e)}")

def get_pdf(document_type: str, category: str, path: str, start_page: int = None, end_page: int = None):
    if document_type == "manual":
        file_path = os.path.join(PDF_MANUAL_DIR, category, path)
    elif document_type == "faq":
        file_path = os.path.join(PDF_FAQ_DIR, category, path)
    else:
        raise HTTPException(status_code=400, detail=f"Invalid document type: {document_type}")

    logger.info(f"Attempting to access PDF file: {file_path}")

    if not os.path.exists(file_path):
        logger.error(f"PDF file not found: {file_path}")
        raise HTTPException(status_code=404, detail=f"PDF file not found: {file_path}")

    try:
        if start_page is not None and end_page is not None:
            logger.info(f"Extracting pages {start_page} to {end_page} from PDF file: {file_path}")
            pdf_bytes = create_pdf_range(file_path, start_page, end_page)

            headers = {
                "Content-Disposition": f'inline; filename*=UTF-8\'\'{quote(os.path.basename(path))}_pages_{start_page}-{end_page}.pdf'
            }
            return StreamingResponse(pdf_bytes, media_type="application/pdf", headers=headers)
        else:
            logger.info(f"Serving full PDF file: {file_path}")
            headers = {
                "Content-Disposition": f'inline; filename*=UTF-8\'\'{quote(os.path.basename(path))}'
            }
            return FileResponse(file_path, media_type="application/pdf", headers=headers)
    except Exception as e:
        logger.error(f"Error serving PDF file: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error serving PDF file: {str(e)}")
