# rag-hnsw/backend/config.py
import os
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

# PDF処理設定
CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", 1000))
CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", 0))
SEPARATOR = os.getenv("SEPARATOR", "\n\n")
PDF_INPUT_DIR = os.getenv("PDF_INPUT_DIR", '/app/data/pdf')
CSV_OUTPUT_DIR = os.getenv("CSV_OUTPUT_DIR", '/app/data/csv')

# POSTGRES
POSTGRES_DB = os.getenv("POSTGRES_DB", "aurora")
POSTGRES_USER = os.getenv("POSTGRES_USER", "user")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "pass")
POSTGRES_HOST = os.getenv("POSTGRES_HOST", "api1_aurora")
POSTGRES_PORT = int(os.getenv("POSTGRES_PORT", 5432))

# インデックス設定
INDEX_TYPE = os.getenv("INDEX_TYPE", "hnsw").lower()
HNSW_M = int(os.getenv("HNSW_M", "16"))
HNSW_EF_CONSTRUCTION = int(os.getenv("HNSW_EF_CONSTRUCTION", "256"))
HNSW_EF_SEARCH = int(os.getenv("HNSW_EF_SEARCH", "500"))

# PostgreSQLテーブル設定
MANUAL_TABLE_NAME = os.getenv("MANUAL_TABLE_NAME", "manual_embeddings")
FAQ_TABLE_NAME = os.getenv("FAQ_TABLE_NAME", "faq_embeddings")

# CSV directory PATH
CSV_MANUAL_DIR = os.path.join(CSV_OUTPUT_DIR, "manual")
CSV_FAQ_DIR = os.path.join(CSV_OUTPUT_DIR, "faq")

# その他の設定
BATCH_SIZE = int(os.getenv("BATCH_SIZE", "1000"))
POSTGRES_CONTAINER_NAME = os.getenv("POSTGRES_CONTAINER_NAME", "api1_aurora")
PIPELINE_EXECUTION_MODE = os.getenv("PIPELINE_EXECUTION_MODE", "csv_to_pgvector")
