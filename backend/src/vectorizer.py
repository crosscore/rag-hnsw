# rag-hnsw/backend/src/vectorizer.py
import os
import pandas as pd
from pypdf import PdfReader
from openai import AzureOpenAI, OpenAI
import logging
from config import *
from datetime import datetime, timezone
import hashlib
import traceback
import re

log_dir = os.path.join(DATA_DIR, "log")
os.makedirs(log_dir, exist_ok=True)
logging.basicConfig(filename=os.path.join(log_dir, "vectorizer.log"), level=logging.DEBUG,
                    format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)
logger.info("Initializing vectorizer to read from manual and FAQ PDF folders")

if ENABLE_OPENAI:
    client = OpenAI(api_key=OPENAI_API_KEY)
    logger.info("Using OpenAI API for embeddings")
else:
    client = AzureOpenAI(
        azure_endpoint=AZURE_OPENAI_ENDPOINT,
        api_key=AZURE_OPENAI_API_KEY,
        api_version=AZURE_OPENAI_API_VERSION
    )
    logger.info("Using Azure OpenAI API for embeddings")

def get_pdf_files(directory):
    pdf_files = []
    logger.debug(f"Searching for PDF files in: {directory}")

    for root, _, files in os.walk(directory):
        for file in files:
            if file.lower().endswith('.pdf'):
                file_path = os.path.join(root, file)
                relative_path = os.path.relpath(root, directory)
                pdf_files.append((file_path, relative_path))
                logger.debug(f"Found PDF: {file} in path: {relative_path}")

    logger.info(f"Found {len(pdf_files)} PDF files in {directory}")
    return pdf_files

def extract_text_from_pdf(file_path):
    try:
        with open(file_path, 'rb') as file:
            pdf = PdfReader(file)
            pages = [{"page_content": page.extract_text(), "metadata": {"page": i + 1}} for i, page in enumerate(pdf.pages)]
        logger.debug(f"Extracted {len(pages)} pages from {file_path}")
        return pages
    except Exception as e:
        logger.error(f"Error extracting text from PDF {file_path}: {str(e)}")
        logger.error(traceback.format_exc())
        return []

def create_embedding(text):
    try:
        if ENABLE_OPENAI:
            response = client.embeddings.create(
                input=text,
                model="text-embedding-3-large"
            )
        else:
            response = client.embeddings.create(
                input=text,
                model=AZURE_OPENAI_EMBEDDINGS_DEPLOYMENT
            )
        logger.debug(f"Created embedding for text of length {len(text)}")
        return response
    except Exception as e:
        logger.error(f"Error creating embedding: {str(e)}")
        logger.error(traceback.format_exc())
        return None

def calculate_sha256(file_path):
    hash_sha256 = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_sha256.update(chunk)
    return hash_sha256.hexdigest()

def preprocess_faq_text(text):
    faq_id_match = re.search(r'#ID\n(\d+)', text)
    faq_id = int(faq_id_match.group(1)) if faq_id_match else None

    processed_text_match = re.search(r'#質問・疑問\n(.*)', text, re.DOTALL)
    processed_text = processed_text_match.group(0) if processed_text_match else text

    return faq_id, processed_text.strip()

def process_pdf(file_path, category, document_type):
    logger.info(f"Processing {document_type} PDF: {file_path}")
    pages = extract_text_from_pdf(file_path)
    if not pages:
        logger.warning(f"No text extracted from PDF file: {file_path}")
        return None

    processed_data = []
    sha256_hash = calculate_sha256(file_path)

    for page in pages:
        page_text = page["page_content"]
        page_num = page["metadata"]["page"]

        if page_text.strip():  # Only process non-empty pages
            if document_type == "faq":
                faq_id, processed_text = preprocess_faq_text(page_text)
            else:
                faq_id, processed_text = None, page_text

            response = create_embedding(processed_text)
            if response is None:
                logger.warning(f"Failed to create embedding for page {page_num}")
                continue

            current_time = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S %Z')
            data = {
                'file_name': os.path.basename(file_path),
                'file_path': file_path,
                'sha256_hash': sha256_hash,
                'business_category': category,
                'document_type': document_type,
                'document_page': str(page_num),
                'page_text': processed_text,
                'created_date_time': current_time,
                'embedding': response.data[0].embedding
            }
            if faq_id is not None:
                data['faq_id'] = faq_id
            processed_data.append(data)

    logger.info(f"Processed {file_path}: {len(pages)} pages")
    return pd.DataFrame(processed_data)

def process_pdf_files(input_dir, output_dir, document_type):
    pdf_files = get_pdf_files(input_dir)
    logger.info(f"Starting to process {len(pdf_files)} {document_type} PDF files")
    for file_path, relative_path in pdf_files:
        try:
            processed_data = process_pdf(file_path, relative_path, document_type)
            if processed_data is not None and not processed_data.empty:
                output_subdir = os.path.join(output_dir, relative_path)
                os.makedirs(output_subdir, exist_ok=True)

                csv_file_name = f'{os.path.splitext(os.path.basename(file_path))[0]}.csv'
                output_file = os.path.join(output_subdir, csv_file_name)

                processed_data.to_csv(output_file, index=False)
                logger.info(f"CSV output completed for {csv_file_name} in path {output_file}")
            else:
                logger.warning(f"No data processed for {file_path}")
        except Exception as e:
            logger.error(f"Error processing {file_path}: {str(e)}")
            logger.error(traceback.format_exc())

if __name__ == "__main__":
    try:
        logger.info(f"PDF_MANUAL_DIR: {PDF_MANUAL_DIR}")
        logger.info(f"PDF_FAQ_DIR: {PDF_FAQ_DIR}")
        logger.info(f"CSV_MANUAL_DIR: {CSV_MANUAL_DIR}")
        logger.info(f"CSV_FAQ_DIR: {CSV_FAQ_DIR}")

        process_pdf_files(PDF_MANUAL_DIR, CSV_MANUAL_DIR, "manual")
        process_pdf_files(PDF_FAQ_DIR, CSV_FAQ_DIR, "faq")

        logger.info("PDF processing completed successfully")
    except Exception as e:
        logger.error(f"An error occurred during PDF processing: {str(e)}")
        logger.error(traceback.format_exc())
