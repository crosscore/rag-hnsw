# rag-hnsw/backend/src/csv_to_pgvector.py
import os
import pandas as pd
import psycopg
from psycopg import sql
from config import *
import logging
from contextlib import contextmanager

log_dir = "/app/data/log"
os.makedirs(log_dir, exist_ok=True)
logging.basicConfig(filename="/app/data/log/csv_to_pgvector.log", level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)

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
    except (KeyError, psycopg.Error) as e:
        logger.error(f"Database connection error: {e}")
        raise
    finally:
        if conn:
            conn.close()
            logger.info("Database connection closed")

def create_table_and_index(cursor):
    create_table_query = sql.SQL("""
    CREATE TABLE IF NOT EXISTS {} (
        id SERIAL PRIMARY KEY,
        file_name TEXT,
        file_path TEXT,
        sha256_hash TEXT,
        business_category TEXT,
        document_page SMALLINT,
        chunk_no INTEGER,
        chunk_text TEXT,
        created_date_time TIMESTAMPTZ,
        embedding vector(3072)
    );
    """).format(sql.Identifier(MANUAL_TABLE_NAME))

    try:
        cursor.execute(create_table_query)
        logger.info(f"Table {MANUAL_TABLE_NAME} created successfully")

        if INDEX_TYPE == "hnsw":
            create_index_query = sql.SQL("""
            CREATE INDEX IF NOT EXISTS {} ON {}
            USING hnsw ((embedding::halfvec(3072)) halfvec_ip_ops)
            WITH (m = {}, ef_construction = {});
            """).format(
                sql.Identifier(f"hnsw_{MANUAL_TABLE_NAME}_embedding_idx"),
                sql.Identifier(MANUAL_TABLE_NAME),
                sql.Literal(HNSW_M),
                sql.Literal(HNSW_EF_CONSTRUCTION)
            )
            cursor.execute(create_index_query)
            logger.info(f"HNSW index created successfully for {MANUAL_TABLE_NAME} with parameters: m = {HNSW_M}, ef_construction = {HNSW_EF_CONSTRUCTION}")
        else:
            logger.info(f"No index created for {MANUAL_TABLE_NAME} as per configuration")
    except psycopg.Error as e:
        logger.error(f"Error creating table or index for {MANUAL_TABLE_NAME}: {e}")
        raise

def process_csv_file(file_path, cursor, category):
    logger.info(f"Processing CSV file: {file_path}")
    df = pd.read_csv(file_path)

    insert_query = sql.SQL("""
    INSERT INTO {}
    (file_name, file_path, sha256_hash, business_category, document_page, chunk_no, chunk_text, created_date_time, embedding)
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s::vector(3072));
    """).format(sql.Identifier(MANUAL_TABLE_NAME))

    data = []
    for _, row in df.iterrows():
        embedding = row['embedding']
        if isinstance(embedding, str):
            embedding = eval(embedding)
        if len(embedding) != 3072:
            logger.warning(f"Incorrect vector dimension for row. Expected 3072, got {len(embedding)}. Skipping.")
            continue

        data.append((
            row['file_name'],
            row['file_path'],
            row['sha256_hash'],
            category,
            row['document_page'],
            row['chunk_no'],
            row['chunk_text'],
            row['created_date_time'],
            embedding
        ))

    try:
        cursor.executemany(insert_query, data)
        logger.info(f"Inserted {len(data)} rows into the {MANUAL_TABLE_NAME} table")
    except Exception as e:
        logger.error(f"Error inserting batch into {MANUAL_TABLE_NAME}: {e}")
        raise

def process_csv_files():
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                # Manual処理
                if os.path.exists(CSV_MANUAL_DIR):
                    logger.info(f"CSV_MANUAL_DIR exists: {CSV_MANUAL_DIR}")
                    create_table_and_index(cursor)
                    csv_files = []
                    for root, dirs, files in os.walk(CSV_MANUAL_DIR):
                        csv_files.extend([os.path.join(root, file) for file in files if file.endswith('.csv')])
                    logger.info(f"Found {len(csv_files)} CSV files in {CSV_MANUAL_DIR} and its subdirectories")
                    for csv_file_path in csv_files:
                        try:
                            category = os.path.relpath(os.path.dirname(csv_file_path), CSV_MANUAL_DIR)
                            process_csv_file(csv_file_path, cursor, category)
                            conn.commit()
                            logger.info(f"Successfully processed and committed {csv_file_path}")
                        except Exception as e:
                            conn.rollback()
                            logger.error(f"Error processing {csv_file_path}: {e}")
                else:
                    logger.warning(f"CSV_MANUAL_DIR does not exist: {CSV_MANUAL_DIR}")

                # テーブル内のレコード数を確認
                cursor.execute(f"SELECT COUNT(*) FROM {MANUAL_TABLE_NAME}")
                count = cursor.fetchone()[0]
                logger.info(f"Total records in {MANUAL_TABLE_NAME}: {count}")

                logger.info(f"CSV files have been processed and inserted into the database with {INDEX_TYPE.upper()} index.")
                if INDEX_TYPE == "hnsw":
                    logger.info(f"HNSW index parameters: m = {HNSW_M}, ef_construction = {HNSW_EF_CONSTRUCTION}")

    except Exception as e:
        logger.error(f"An error occurred during processing: {e}")
        raise

if __name__ == "__main__":
    try:
        process_csv_files()
    except Exception as e:
        logger.error(f"Script execution failed: {e}")
        exit(1)
