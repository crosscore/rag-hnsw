# rag-hnsw/backend/src/csv_to_aurora.py
import os
import pandas as pd
import psycopg
from psycopg import sql
from config import *
import logging
from contextlib import contextmanager

log_dir = "/app/data/log"
os.makedirs(log_dir, exist_ok=True)
logging.basicConfig(filename="/app/data/log/csv_to_aurora.log", level=logging.INFO, format='%(asctime)s - %(message)s')
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

def create_table_and_index(cursor, table_name):
    create_table_query = sql.SQL("""
    CREATE TABLE IF NOT EXISTS {} (
        id SERIAL PRIMARY KEY,
        file_name TEXT,
        file_path TEXT,
        sha256_hash TEXT,
        business_category TEXT,
        document_type TEXT,
        document_page SMALLINT,
        page_text TEXT,
        created_date_time TIMESTAMPTZ,
        embedding vector(3072)
        {});
    """).format(
        sql.Identifier(table_name),
        sql.SQL(", faq_id INTEGER" if table_name == FAQ_TABLE_NAME else "")
    )

    try:
        cursor.execute(create_table_query)
        logger.info(f"Table {table_name} created successfully")

        if INDEX_TYPE == "hnsw":
            create_index_query = sql.SQL("""
            CREATE INDEX IF NOT EXISTS {} ON {}
            USING hnsw ((embedding::halfvec(3072)) halfvec_ip_ops)
            WITH (m = {}, ef_construction = {});
            """).format(
                sql.Identifier(f"hnsw_{table_name}_embedding_idx"),
                sql.Identifier(table_name),
                sql.Literal(HNSW_M),
                sql.Literal(HNSW_EF_CONSTRUCTION)
            )
            cursor.execute(create_index_query)
            logger.info(f"HNSW index created successfully for {table_name} with parameters: m = {HNSW_M}, ef_construction = {HNSW_EF_CONSTRUCTION}")
        else:
            logger.info(f"No index created for {table_name} as per configuration")
    except psycopg.Error as e:
        logger.error(f"Error creating table or index for {table_name}: {e}")
        raise

def process_csv_file(file_path, cursor, table_name, document_type):
    logger.info(f"Processing CSV file: {file_path}")
    df = pd.read_csv(file_path)

    if table_name == FAQ_TABLE_NAME:
        insert_query = sql.SQL("""
        INSERT INTO {}
        (file_name, file_path, sha256_hash, business_category, document_type, document_page, page_text, created_date_time, embedding, faq_id)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s::vector(3072), %s);
        """).format(sql.Identifier(table_name))
    else:
        insert_query = sql.SQL("""
        INSERT INTO {}
        (file_name, file_path, sha256_hash, business_category, document_type, document_page, page_text, created_date_time, embedding)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s::vector(3072));
        """).format(sql.Identifier(table_name))

    data = []
    for _, row in df.iterrows():
        embedding = row['embedding']
        if isinstance(embedding, str):
            embedding = eval(embedding)
        if len(embedding) != 3072:
            logger.warning(f"Incorrect vector dimension for row. Expected 3072, got {len(embedding)}. Skipping.")
            continue

        row_data = (
            row['file_name'],
            row['file_path'],
            row['sha256_hash'],
            row['business_category'],
            document_type,
            row['document_page'],
            row['page_text'],
            row['created_date_time'],
            embedding
        )

        if table_name == FAQ_TABLE_NAME:
            row_data += (row['faq_id'],)

        data.append(row_data)

    try:
        cursor.executemany(insert_query, data)
        logger.info(f"Inserted {len(data)} rows into the {table_name} table")
    except Exception as e:
        logger.error(f"Error inserting batch into {table_name}: {e}")
        raise

def process_csv_files():
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                # Process manual CSVs
                if os.path.exists(CSV_MANUAL_DIR):
                    logger.info(f"CSV_MANUAL_DIR exists: {CSV_MANUAL_DIR}")
                    create_table_and_index(cursor, MANUAL_TABLE_NAME)
                    process_directory(cursor, CSV_MANUAL_DIR, MANUAL_TABLE_NAME, "manual")

                # Process FAQ CSVs
                if os.path.exists(CSV_FAQ_DIR):
                    logger.info(f"CSV_FAQ_DIR exists: {CSV_FAQ_DIR}")
                    create_table_and_index(cursor, FAQ_TABLE_NAME)
                    process_directory(cursor, CSV_FAQ_DIR, FAQ_TABLE_NAME, "faq")

                conn.commit()
                logger.info("All CSV files have been processed and inserted into the database.")

                # Log record counts
                for table_name in [MANUAL_TABLE_NAME, FAQ_TABLE_NAME]:
                    cursor.execute(sql.SQL("SELECT COUNT(*) FROM {}").format(sql.Identifier(table_name)))
                    count = cursor.fetchone()[0]
                    logger.info(f"Total records in {table_name}: {count}")

    except Exception as e:
        logger.error(f"An error occurred during processing: {e}")
        raise

def process_directory(cursor, directory, table_name, document_type):
    csv_files = []
    for root, dirs, files in os.walk(directory):
        csv_files.extend([os.path.join(root, file) for file in files if file.endswith('.csv')])
    logger.info(f"Found {len(csv_files)} CSV files in {directory} and its subdirectories")
    for csv_file_path in csv_files:
        try:
            process_csv_file(csv_file_path, cursor, table_name, document_type)
            logger.info(f"Successfully processed {csv_file_path}")
        except Exception as e:
            logger.error(f"Error processing {csv_file_path}: {e}")

if __name__ == "__main__":
    try:
        process_csv_files()
    except Exception as e:
        logger.error(f"Script execution failed: {e}")
        exit(1)
