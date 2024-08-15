# rag-hnsw/backend/config.py
import os
import json
from dotenv import load_dotenv
load_dotenv()

# OpenAI
ENABLE_OPENAI = os.getenv("ENABLE_OPENAI").lower() == "true"
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Azure OpenAI
AZURE_OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT")
AZURE_OPENAI_API_KEY = os.getenv("AZURE_OPENAI_API_KEY")
AZURE_OPENAI_DEPLOYMENT = os.getenv("AZURE_OPENAI_DEPLOYMENT")
AZURE_OPENAI_EMBEDDINGS_DEPLOYMENT = os.getenv("AZURE_OPENAI_EMBEDDINGS_DEPLOYMENT")
AZURE_OPENAI_API_VERSION = os.getenv("AZURE_OPENAI_API_VERSION")
MODEL_GPT4o_DEPLOY_NAME = os.getenv("MODEL_GPT4o_DEPLOY_NAME", "gpt40o_20240705")

# AWS credentials and region
AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")
AWS_REGION = os.getenv("AWS_REGION")

# S3 and SQS settings
S3_BUCKET_NAME = os.getenv("S3_BUCKET_NAME")
SQS_QUEUE_URL = os.getenv("SQS_QUEUE_URL")
DEAD_LETTER_QUEUE_URL=os.getenv("DEAD_LETTER_QUEUE_URL")
LOCAL_UPLOAD_PATH = os.getenv("LOCAL_UPLOAD_PATH")
LOCAL_DOWNLOAD_PATH = os.getenv("LOCAL_DOWNLOAD_PATH")

# Base directories
DATA_DIR = os.getenv("DATA_DIR", "/app/data")
PDF_INPUT_DIR = os.path.join(DATA_DIR, "pdf")
CSV_OUTPUT_DIR = os.path.join(DATA_DIR, "csv")
XLSX_INPUT_DIR = os.path.join(DATA_DIR, "xlsx")

# Derived directories
PDF_MANUAL_DIR = os.path.join(PDF_INPUT_DIR, "manual")
PDF_FAQ_DIR = os.path.join(PDF_INPUT_DIR, "faq")
CSV_MANUAL_DIR = os.path.join(CSV_OUTPUT_DIR, "manual")
CSV_FAQ_DIR = os.path.join(CSV_OUTPUT_DIR, "faq")
TOC_XLSX_DIR = os.path.join(XLSX_INPUT_DIR, "toc")

# POSTGRES
POSTGRES_DB = os.getenv("POSTGRES_DB", "aurora")
POSTGRES_USER = os.getenv("POSTGRES_USER", "user")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "pass")
POSTGRES_HOST = os.getenv("POSTGRES_HOST", "api1_aurora")
POSTGRES_PORT = int(os.getenv("POSTGRES_PORT", 5432))

# Index settings
INDEX_TYPE = os.getenv("INDEX_TYPE", "hnsw").lower()
HNSW_SETTINGS = json.loads(os.getenv("HNSW_SETTINGS", '{"m": 16, "ef_construction": 256, "ef_search": 500}'))
HNSW_M = HNSW_SETTINGS.get("m", 16)
HNSW_EF_CONSTRUCTION = HNSW_SETTINGS.get("ef_construction", 256)
HNSW_EF_SEARCH = HNSW_SETTINGS.get("ef_search", 500)

# PostgreSQL table settings
MANUAL_TABLE_NAME = os.getenv("MANUAL_TABLE_NAME", "manual_embeddings")
FAQ_TABLE_NAME = os.getenv("FAQ_TABLE_NAME", "faq_embeddings")
TOC_TABLE_NAME = "toc_table"

# Other settings
BATCH_SIZE = int(os.getenv("BATCH_SIZE", "1000"))
PIPELINE_EXECUTION_MODE = os.getenv("PIPELINE_EXECUTION_MODE", "csv_to_aurora")
