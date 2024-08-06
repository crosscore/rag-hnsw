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
            dbname=PGVECTOR_DB_NAME,
            user=PGVECTOR_DB_USER,
            password=PGVECTOR_DB_PASSWORD,
            host=PGVECTOR_DB_HOST,
            port=PGVECTOR_DB_PORT
        )
        logger.info(f"Connected to database: {PGVECTOR_DB_HOST}:{PGVECTOR_DB_PORT}")
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
        md5_hash TEXT,
        business_category TEXT,
        document_page SMALLINT,
        chunk_no INTEGER,
        chunk_text TEXT,
        created_date_time TIMESTAMPTZ,
        chunk_vector vector(3072)
    );
    """).format(sql.Identifier(EMBEDDINGS_TABLE_NAME))

    try:
        cursor.execute(create_table_query)
        logger.info(f"Table {EMBEDDINGS_TABLE_NAME} created successfully")

        if INDEX_TYPE == "hnsw":
            create_index_query = sql.SQL("""
            CREATE INDEX IF NOT EXISTS {} ON {}
            USING hnsw ((chunk_vector::halfvec(3072)) halfvec_ip_ops)
            WITH (m = {}, ef_construction = {});
            """).format(
                sql.Identifier(f"hnsw_{EMBEDDINGS_TABLE_NAME}_chunk_vector_idx"),
                sql.Identifier(EMBEDDINGS_TABLE_NAME),
                sql.Literal(HNSW_M),
                sql.Literal(HNSW_EF_CONSTRUCTION)
            )
            cursor.execute(create_index_query)
            logger.info(f"HNSW index created successfully for {EMBEDDINGS_TABLE_NAME} with parameters: m = {HNSW_M}, ef_construction = {HNSW_EF_CONSTRUCTION}")
        elif INDEX_TYPE == "none":
            logger.info(f"No index created for {EMBEDDINGS_TABLE_NAME} as per configuration")
        else:
            raise ValueError(f"Unsupported index type: {INDEX_TYPE}")
    except psycopg.Error as e:
        logger.error(f"Error creating table or index for {EMBEDDINGS_TABLE_NAME}: {e}")
        raise

def process_csv_file(file_path, cursor, category):
    logger.info(f"Processing CSV file: {file_path}")
    df = pd.read_csv(file_path)

    insert_query = sql.SQL("""
    INSERT INTO {}
    (file_name, file_path, md5_hash, business_category, document_page, chunk_no, chunk_text, created_date_time, chunk_vector)
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s::vector(3072));
    """).format(sql.Identifier(EMBEDDINGS_TABLE_NAME))

    data = []
    for _, row in df.iterrows():
        embedding = row['chunk_vector']
        if isinstance(embedding, str):
            embedding = eval(embedding)
        if len(embedding) != 3072:
            logger.warning(f"Incorrect vector dimension for row. Expected 3072, got {len(embedding)}. Skipping.")
            continue

        data.append((
            row['file_name'],
            row['file_path'],
            row['md5_hash'],
            category,
            row['document_page'],
            row['chunk_no'],
            row['chunk_text'],
            row['created_date_time'],
            embedding
        ))

    try:
        cursor.executemany(insert_query, data)
        logger.info(f"Inserted {len(data)} rows into the {EMBEDDINGS_TABLE_NAME} table")
    except Exception as e:
        logger.error(f"Error inserting batch into {EMBEDDINGS_TABLE_NAME}: {e}")
        raise

def process_csv_files():
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                create_table_and_index(cursor)
                for category in os.listdir(CSV_OUTPUT_DIR):
                    category_dir = os.path.join(CSV_OUTPUT_DIR, category)
                    if os.path.isdir(category_dir):
                        logger.info(f"Processing category: {category}")
                        for file in os.listdir(category_dir):
                            if file.endswith('.csv'):
                                csv_file_path = os.path.join(category_dir, file)
                                try:
                                    process_csv_file(csv_file_path, cursor, category)
                                    conn.commit()
                                except Exception as e:
                                    conn.rollback()
                                    logger.error(f"Error processing {csv_file_path}: {e}")

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
