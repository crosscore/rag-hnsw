# rag-hnsw/backend/src/vectorizer.py
import os
import pandas as pd
from pypdf import PdfReader
from openai import AzureOpenAI, OpenAI
import logging
from config import *
from langchain_text_splitters import CharacterTextSplitter
from datetime import datetime, timezone
import hashlib
import traceback

log_filedir = "/app/data/log/"
os.makedirs(log_filedir, exist_ok=True)
logging.basicConfig(filename=os.path.join(log_filedir, "vectorizer.log"), level=logging.DEBUG, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)
logger.info("Initializing vectorizer to read from local PDF folder")

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

def get_pdf_files_from_local():
    pdf_files = []
    logger.debug(f"Searching for PDF files in: {PDF_INPUT_DIR}")

    for root, dirs, files in os.walk(PDF_INPUT_DIR):
        for file in files:
            if file.endswith('.pdf'):
                file_path = os.path.join(root, file)
                relative_path = os.path.relpath(root, PDF_INPUT_DIR)
                pdf_files.append((file_path, relative_path))
                logger.debug(f"Found PDF: {file} in path: {relative_path}")

    logger.info(f"Found {len(pdf_files)} PDF files in {PDF_INPUT_DIR}")
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

def split_text_into_chunks(text):
    text_splitter = CharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        separator=SEPARATOR
    )
    chunks = text_splitter.split_text(text)
    if not chunks:
        logger.warning(f"Text splitting resulted in no chunks. Using full text as a single chunk.")
        chunks = [text]
    logger.debug(f"Split text into {len(chunks)} chunks")
    return chunks

def process_pdf(file_path, category):
    logger.info(f"Processing PDF: {file_path}")
    pages = extract_text_from_pdf(file_path)
    if not pages:
        logger.warning(f"No text extracted from PDF file: {file_path}")
        return None

    processed_data = []
    total_chunks = 0
    sha256_hash = calculate_sha256(file_path)

    for page in pages:
        page_text = page["page_content"]
        page_num = page["metadata"]["page"]
        chunks = split_text_into_chunks(page_text)

        for chunk in chunks:
            if chunk.strip():  # Only process non-empty chunks
                response = create_embedding(chunk)
                if response is None:
                    logger.warning(f"Failed to create embedding for chunk in page {page_num}")
                    continue
                current_time = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S %Z')
                total_chunks += 1
                processed_data.append({
                    'file_name': os.path.basename(file_path),
                    'file_path': file_path,
                    'sha256_hash': sha256_hash,
                    'business_category': category,
                    'document_page': str(page_num),
                    'chunk_no': total_chunks,
                    'chunk_text': chunk,
                    'created_date_time': current_time,
                    'embedding': response.data[0].embedding
                })

    logger.info(f"Processed {file_path}: {len(pages)} pages, {total_chunks} chunks")
    return pd.DataFrame(processed_data)

def process_pdf_files():
    pdf_files = get_pdf_files_from_local()
    logger.info(f"Starting to process {len(pdf_files)} PDF files")
    for file_path, relative_path in pdf_files:
        try:
            processed_data = process_pdf(file_path, relative_path)
            if processed_data is not None and not processed_data.empty:
                output_dir = os.path.join(CSV_OUTPUT_DIR, relative_path)
                os.makedirs(output_dir, exist_ok=True)

                csv_file_name = f'{os.path.splitext(os.path.basename(file_path))[0]}.csv'
                output_file = os.path.join(output_dir, csv_file_name)

                processed_data.to_csv(output_file, index=False)
                logger.info(f"CSV output completed for {csv_file_name} in path {output_file}")
            else:
                logger.warning(f"No data processed for {file_path}")
        except Exception as e:
            logger.error(f"Error processing {file_path}: {str(e)}")
            logger.error(traceback.format_exc())

if __name__ == "__main__":
    try:
        logger.info(f"PDF_INPUT_DIR: {PDF_INPUT_DIR}")
        logger.info(f"CSV_OUTPUT_DIR: {CSV_OUTPUT_DIR}")
        process_pdf_files()
        logger.info("PDF processing completed successfully")
    except Exception as e:
        logger.error(f"An error occurred during PDF processing: {str(e)}")
        logger.error(traceback.format_exc())
