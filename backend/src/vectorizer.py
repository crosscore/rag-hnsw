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

log_filedir = "/app/data/log/"
os.makedirs(log_filedir, exist_ok=True)
logging.basicConfig(filename=os.path.join(log_filedir, "vectorizer.log"), level=logging.INFO, format='%(asctime)s - %(message)s')
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
    for root, _, files in os.walk(PDF_INPUT_DIR):
        for file in files:
            if file.endswith('.pdf'):
                category = os.path.relpath(root, PDF_INPUT_DIR)
                pdf_files.append((os.path.join(root, file), category))
    logger.info(f"Found {len(pdf_files)} PDF files in {PDF_INPUT_DIR}")
    return pdf_files

def extract_text_from_pdf(file_path):
    try:
        with open(file_path, 'rb') as file:
            pdf = PdfReader(file)
            return [{"page_content": page.extract_text(), "metadata": {"page": i + 1}} for i, page in enumerate(pdf.pages)]
    except Exception as e:
        logger.error(f"Error extracting text from PDF {file_path}: {str(e)}")
        return []

def create_embedding(text):
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
    return response

def split_text_into_chunks(text):
    text_splitter = CharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        separator=SEPARATOR
    )
    chunks = text_splitter.split_text(text)
    return chunks if chunks else [text]

def calculate_md5(file_path):
    hash_md5 = hashlib.md5()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_md5.update(chunk)
    return hash_md5.hexdigest()

def process_pdf(file_path, category):
    pages = extract_text_from_pdf(file_path)
    if not pages:
        logger.warning(f"No text extracted from PDF file: {file_path}")
        return None

    processed_data = []
    total_chunks = 0
    md5_hash = calculate_md5(file_path)

    for page in pages:
        page_text = page["page_content"]
        page_num = page["metadata"]["page"]
        chunks = split_text_into_chunks(page_text)

        if not chunks and page_text:
            chunks = [page_text]

        for chunk in chunks:
            if chunk.strip():  # Only process non-empty chunks
                response = create_embedding(chunk)
                current_time = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S %Z')
                total_chunks += 1
                processed_data.append({
                    'file_name': os.path.basename(file_path),
                    'file_path': file_path,
                    'md5_hash': md5_hash,
                    'business_category': category,
                    'document_page': str(page_num),
                    'chunk_no': total_chunks,
                    'chunk_text': chunk,
                    'created_date_time': current_time,
                    'chunk_vector': response.data[0].embedding
                })

    logger.info(f"Processed {file_path}: {len(pages)} pages, {total_chunks} chunks")
    return pd.DataFrame(processed_data)

def process_pdf_files():
    for file_path, category in get_pdf_files_from_local():
        processed_data = process_pdf(file_path, category)
        if processed_data is not None and not processed_data.empty:
            output_dir = os.path.join(CSV_OUTPUT_DIR, category)
            os.makedirs(output_dir, exist_ok=True)

            csv_file_name = f'{os.path.splitext(os.path.basename(file_path))[0]}.csv'
            output_file = os.path.join(output_dir, csv_file_name)

            processed_data.to_csv(output_file, index=False)
            logger.info(f"CSV output completed for {csv_file_name} in category {category}")
        else:
            logger.warning(f"No data processed for {file_path}")

if __name__ == "__main__":
    process_pdf_files()
