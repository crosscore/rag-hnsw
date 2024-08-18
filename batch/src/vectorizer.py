# rag-hnsw/batch/vectorizer.py
import os
import pandas as pd
from pypdf import PdfReader
from openai import AzureOpenAI, OpenAI
import traceback
import re
from langchain_text_splitters import CharacterTextSplitter
from utils import calculate_checksum, get_current_datetime, get_file_name, get_business_category, setup_logging
from config import *

logger = setup_logging("vectorizer")

def initialize_openai_client():
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
    return client

client = initialize_openai_client()

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

def preprocess_faq_text(text):
    faq_no_match = re.search(r'#(ID|No)\n(\d+)', text)
    faq_no = int(faq_no_match.group(2)) if faq_no_match else None

    processed_text_match = re.search(r'#質問・疑問\n(.*)', text, re.DOTALL)
    processed_text = processed_text_match.group(1) if processed_text_match else text

    return faq_no, processed_text.strip()

def split_text_into_chunks(text):
    text_splitter = CharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        separator=SEPARATOR
    )
    chunks = text_splitter.split_text(text)
    return chunks if chunks else [text]

def process_manual_page(page_text, page_num, file_info):
    chunks = split_text_into_chunks(page_text)
    processed_data = []
    for chunk_no, chunk in enumerate(chunks, start=1):
        response = create_embedding(chunk)
        if response is None:
            logger.warning(f"Failed to create embedding for chunk {chunk_no} on page {page_num}")
            continue

        data = {
            'file_name': file_info['file_name'],
            'file_path': file_info['file_path'],
            'checksum': file_info['checksum'],
            'business_category': file_info['business_category'],
            'document_type': file_info['document_type'],
            'document_page': int(page_num),
            'chunk_no': chunk_no,
            'chunk_text': chunk,
            'created_date_time': file_info['created_date_time'],
            'embedding': response.data[0].embedding
        }
        processed_data.append(data)
    return processed_data

def process_faq_page(page_text, page_num, file_info):
    faq_no, processed_text = preprocess_faq_text(page_text)
    response = create_embedding(processed_text)
    if response is None:
        logger.warning(f"Failed to create embedding for FAQ page {page_num}")
        return None

    data = {
        'file_name': file_info['file_name'],
        'file_path': file_info['file_path'],
        'checksum': file_info['checksum'],
        'business_category': file_info['business_category'],
        'document_type': file_info['document_type'],
        'document_page': int(page_num),
        'faq_no': faq_no,
        'page_text': processed_text,
        'created_date_time': file_info['created_date_time'],
        'embedding': response.data[0].embedding
    }
    return [data]

def process_pdf(file_path, category, document_type):
    logger.info(f"Processing {document_type} PDF: {file_path}")
    pages = extract_text_from_pdf(file_path)
    if not pages:
        logger.warning(f"No text extracted from PDF file: {file_path}")
        return None

    file_info = {
        'file_name': get_file_name(file_path),
        'file_path': file_path,
        'checksum': calculate_checksum(file_path),
        'business_category': category,
        'document_type': document_type,
        'created_date_time': get_current_datetime()
    }

    processed_data = []
    for page in pages:
        page_text = page["page_content"]
        page_num = page["metadata"]["page"]

        if page_text.strip():  # Only process non-empty pages
            if document_type == "faq":
                page_data = process_faq_page(page_text, page_num, file_info)
            else:  # manual
                page_data = process_manual_page(page_text, page_num, file_info)

            if page_data:
                processed_data.extend(page_data)

    logger.info(f"Processed {file_path}: {len(pages)} pages, {len(processed_data)} total entries")
    return pd.DataFrame(processed_data)

def process_pdf_files(input_dir, output_dir, document_type):
    pdf_files = get_pdf_files(input_dir)
    logger.info(f"Starting to process {len(pdf_files)} {document_type} PDF files")
    for file_path, relative_path in pdf_files:
        try:
            business_category = get_business_category(file_path, input_dir)
            processed_data = process_pdf(file_path, business_category, document_type)
            if processed_data is not None and not processed_data.empty:
                output_subdir = os.path.join(output_dir, relative_path)
                os.makedirs(output_subdir, exist_ok=True)

                csv_file_name = f'{get_file_name(file_path)}.csv'
                output_file = os.path.join(output_subdir, csv_file_name)

                processed_data.to_csv(output_file, index=False)
                logger.info(f"CSV output completed for {csv_file_name} in path {output_file}")
            else:
                logger.warning(f"No data processed for {file_path}")
        except Exception as e:
            logger.error(f"Error processing {file_path}: {str(e)}")
            logger.error(traceback.format_exc())

def main():
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

if __name__ == "__main__":
    main()
