# /batch/src/utils.py
import os
import logging
from contextlib import contextmanager
import psycopg
from psycopg import sql
import uuid
import pytz
from datetime import datetime
import hashlib
from config import *

def setup_logging(module_name):
    log_dir = os.path.join(DATA_DIR, "log")
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, "unified_log.log")

    # ルートロガーの設定
    root_logger = logging.getLogger()
    if not root_logger.handlers:  # ハンドラーが既に設定されていない場合のみ設定
        root_logger.setLevel(logging.DEBUG)
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(logging.DEBUG)
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)

    # モジュール固有のロガーを返す
    return logging.getLogger(module_name)

# utils.py 自体のロガーを設定
logger = setup_logging("utils")

@contextmanager
def get_db_connection():
    conn = None
    try:
        conn = psycopg.connect(
            dbname=POSTGRES_DB,
            user=POSTGRES_USER,
            password=POSTGRES_PASSWORD,
            host=POSTGRES_HOST,
            port=POSTGRES_PORT
        )
        logger.info(f"Connected to database: {POSTGRES_HOST}:{POSTGRES_PORT}")
        yield conn
    except Exception as e:
        logger.error(f"Database connection error: {e}")
        raise
    finally:
        if conn:
            conn.close()
            logger.info("Database connection closed")

def create_table(cursor, table_name, create_query):
    try:
        cursor.execute(create_query)
        logger.info(f"Table {table_name} creation query executed")
    except psycopg.Error as e:
        logger.error(f"Error creating table {table_name}: {e}")
        raise

def create_tables(cursor):
    # Install pgvector extension if not exists
    try:
        cursor.execute("CREATE EXTENSION IF NOT EXISTS vector;")
        logger.info("pgvector extension installed or already exists")
    except psycopg.Error as e:
        logger.error(f"Error installing pgvector extension: {e}")
        raise

    tables = [
        (DOCUMENT_TABLE, """
        CREATE TABLE IF NOT EXISTS {} (
            id UUID PRIMARY KEY,
            file_path VARCHAR(1024) NOT NULL,
            file_name VARCHAR(1024) NOT NULL,
            document_type SMALLINT NOT NULL,
            checksum VARCHAR(64) NOT NULL,
            created_date_time TIMESTAMP WITH TIME ZONE NOT NULL,
            UNIQUE(file_path)
        )
        """),
        (DOCUMENT_CATEGORY_TABLE, """
        CREATE TABLE IF NOT EXISTS {} (
            id UUID PRIMARY KEY,
            document_table_id UUID NOT NULL REFERENCES {}(id),
            business_category SMALLINT NOT NULL,
            created_date_time TIMESTAMP WITH TIME ZONE NOT NULL,
            UNIQUE(document_table_id, business_category)
        )
        """),
        (PDF_MANUAL_TABLE, """
        CREATE TABLE IF NOT EXISTS {} (
            id UUID PRIMARY KEY,
            document_table_id UUID NOT NULL REFERENCES {}(id),
            chunk_no INTEGER NOT NULL,
            document_page SMALLINT NOT NULL,
            chunk_text TEXT NOT NULL,
            embedding VECTOR(3072) NOT NULL,
            created_date_time TIMESTAMP WITH TIME ZONE NOT NULL,
            UNIQUE(document_table_id, chunk_no, document_page)
        )
        """),
        (PDF_FAQ_TABLE, """
        CREATE TABLE IF NOT EXISTS {} (
            id UUID PRIMARY KEY,
            document_table_id UUID NOT NULL REFERENCES {}(id),
            document_page INTEGER NOT NULL,
            faq_no SMALLINT NOT NULL,
            chunk_text TEXT NOT NULL,
            embedding VECTOR(3072) NOT NULL,
            created_date_time TIMESTAMP WITH TIME ZONE NOT NULL,
            UNIQUE(document_table_id, document_page, faq_no)
        )
        """),
        (XLSX_TOC_TABLE, """
        CREATE TABLE IF NOT EXISTS {} (
            id UUID PRIMARY KEY,
            document_table_id UUID NOT NULL REFERENCES {}(id),
            file_name VARCHAR(1024) NOT NULL,
            toc_data TEXT NOT NULL,
            checksum VARCHAR(64) NOT NULL,
            created_date_time TIMESTAMP WITH TIME ZONE NOT NULL,
            UNIQUE(document_table_id, file_name)
        )
        """)
    ]

    for table_name, create_query in tables:
        formatted_query = sql.SQL(create_query).format(
            sql.Identifier(table_name),
            sql.Identifier(DOCUMENT_TABLE)
        )
        create_table(cursor, table_name, formatted_query)

def create_index(cursor, table_name):
    index_name = f"hnsw_{table_name}_embedding_idx"
    index_query = sql.SQL("""
    CREATE INDEX IF NOT EXISTS {} ON {}
    USING hnsw((embedding::halfvec(3072)) halfvec_ip_ops)
    WITH (m = {}, ef_construction = {});
    """).format(
        sql.Identifier(index_name),
        sql.Identifier(table_name),
        sql.Literal(HNSW_M),
        sql.Literal(HNSW_EF_CONSTRUCTION)
    )
    try:
        cursor.execute(index_query)
        logger.info(f"HNSW index creation query executed for {table_name}")
    except psycopg.Error as e:
        logger.error(f"Error creating HNSW index for {table_name}: {e}")
        raise

def get_table_count(cursor, table_name):
    cursor.execute(sql.SQL("SELECT COUNT(*) FROM {}").format(sql.Identifier(table_name)))
    count = cursor.fetchone()[0]
    logger.info(f"Total records in {table_name}: {count}")
    return count

def process_file_common(cursor, file_path, file_name, document_type, checksum, created_date_time, business_category):
    # Insert into DOCUMENT_TABLE first
    insert_pdf_query = sql.SQL("""
    INSERT INTO {}
    (id, file_path, file_name, document_type, checksum, created_date_time)
    VALUES (%s, %s, %s, %s, %s, %s)
    ON CONFLICT (file_path) DO UPDATE SET
    file_name = EXCLUDED.file_name,
    document_type = EXCLUDED.document_type,
    checksum = EXCLUDED.checksum,
    created_date_time = EXCLUDED.created_date_time
    RETURNING id;
    """).format(sql.Identifier(DOCUMENT_TABLE))

    pdf_data = (
        uuid.uuid4(),
        file_path,
        file_name,
        document_type,
        checksum,
        created_date_time
    )

    try:
        cursor.execute(insert_pdf_query, pdf_data)
        document_table_id = cursor.fetchone()[0]
        logger.info(f"Inserted/Updated DOCUMENT data in {DOCUMENT_TABLE}")
    except Exception as e:
        logger.error(f"Error inserting/updating DOCUMENT data in {DOCUMENT_TABLE}: {e}")
        raise

    # Insert into DOCUMENT_CATEGORY_TABLE
    insert_category_query = sql.SQL("""
    INSERT INTO {}
    (id, document_table_id, business_category, created_date_time)
    VALUES (%s, %s, %s, %s)
    ON CONFLICT (document_table_id, business_category) DO NOTHING;
    """).format(sql.Identifier(DOCUMENT_CATEGORY_TABLE))

    category_data = (
        uuid.uuid4(),
        document_table_id,
        business_category,
        created_date_time
    )

    try:
        cursor.execute(insert_category_query, category_data)
        logger.info(f"Inserted category data into {DOCUMENT_CATEGORY_TABLE}")
    except Exception as e:
        logger.error(f"Error inserting category data into {DOCUMENT_CATEGORY_TABLE}: {e}")
        raise

    return document_table_id

def calculate_checksum(file_path):
    return hashlib.sha256(open(file_path, 'rb').read()).hexdigest()

def get_current_datetime():
    tokyo_tz = pytz.timezone('Asia/Tokyo')
    return datetime.now(tokyo_tz)

def get_file_name(file_path):
    return os.path.basename(file_path)

def get_business_category(file_path, base_dir):
    relative_path = os.path.relpath(os.path.dirname(file_path), base_dir)
    category_name = relative_path.split(os.path.sep)[0]
    
    if category_name in BUSINESS_CATEGORY_MAPPING:
        return BUSINESS_CATEGORY_MAPPING[category_name]
    else:
        raise ValueError(f"Unknown business category: {category_name}. Valid categories are: {', '.join(BUSINESS_CATEGORY_MAPPING.keys())}")

