# batch/config.py
import os
import json
from dotenv import load_dotenv
load_dotenv()

# Azure OpenAI
AZURE_OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT")
AZURE_OPENAI_API_KEY = os.getenv("AZURE_OPENAI_API_KEY")
AZURE_OPENAI_DEPLOYMENT = os.getenv("AZURE_OPENAI_DEPLOYMENT")
AZURE_OPENAI_EMBEDDINGS_DEPLOYMENT = os.getenv("AZURE_OPENAI_EMBEDDINGS_DEPLOYMENT")
AZURE_OPENAI_API_VERSION = os.getenv("AZURE_OPENAI_API_VERSION")
MODEL_GPT4o_DEPLOY_NAME = os.getenv("MODEL_GPT4o_DEPLOY_NAME")

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

# CharacterTextSplitter settings
CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", 1000))
CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", 0))
SEPARATOR = os.getenv("SEPARATOR", "\n\n")

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
POSTGRES_HOST = os.getenv("POSTGRES_HOST", "aurora")
POSTGRES_PORT = int(os.getenv("POSTGRES_PORT", 5432))

# pgvector settings
OPERATOR = os.getenv("OPERATOR", "<#>")

# Index settings
INDEX_TYPE = os.getenv("INDEX_TYPE", "hnsw").lower()
HNSW_SETTINGS = json.loads(os.getenv("HNSW_SETTINGS", '{"m": 16, "ef_construction": 256, "ef_search": 500}'))
HNSW_M = HNSW_SETTINGS.get("m", 16)
HNSW_EF_CONSTRUCTION = HNSW_SETTINGS.get("ef_construction", 256)
HNSW_EF_SEARCH = HNSW_SETTINGS.get("ef_search", 500)

# PostgreSQL table settings
DOCUMENT_TABLE = os.getenv("DOCUMENT_TABLE", "document_table")
DOCUMENT_CATEGORY_TABLE = os.getenv("DOCUMENT_CATEGORY_TABLE","document_category_table")
XLSX_TOC_TABLE = os.getenv("XLSX_TOC_TABLE", "xlsx_toc_table")
PDF_MANUAL_TABLE = os.getenv("PDF_MANUAL_TABLE", "pdf_manual_table")
PDF_FAQ_TABLE = os.getenv("PDF_FAQ_TABLE", "pdf_faq_table")

# Document types
DOCUMENT_TYPE_PDF_MANUAL = 1
DOCUMENT_TYPE_PDF_FAQ = 2
DOCUMENT_TYPE_XLSX_TOC = 3

# Business Category Mapping
DEFAULT_BUSINESS_CATEGORY_MAPPING = {
    "新契約": 1,
    "収納": 2,
    "保全": 3,
    "保険金": 4,
    "商品": 5,
    "MSAケア": 6,
    "手数料": 7,
    "代理店制度": 8,
    "職域推進": 9,
    "人事": 10,
    "会計": 11
}

# Load business category mapping from environment variable if available
BUSINESS_CATEGORY_MAPPING = json.loads(os.getenv('BUSINESS_CATEGORY_MAPPING', json.dumps(DEFAULT_BUSINESS_CATEGORY_MAPPING)))

# Other settings
BATCH_SIZE = int(os.getenv("BATCH_SIZE", "1000"))
PIPELINE_EXECUTION_MODE = os.getenv("PIPELINE_EXECUTION_MODE", "csv_to_aurora")
