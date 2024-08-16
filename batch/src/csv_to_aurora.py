# rag-hnsw/batch/src/csv_to_aurora.py
import os
import pandas as pd
import psycopg
from psycopg import sql
from config import *
import logging
from contextlib import contextmanager

log_dir = os.path.join(DATA_DIR, "log")
os.makedirs(log_dir, exist_ok=True)
logging.basicConfig(filename=os.path.join(log_dir, "csv_to_aurora.log"), level=logging.DEBUG,
                    format='%(asctime)s - %(levelname)s - %(message)s')
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
    except Exception as e:
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
        business_category SMALLINT,
        document_type TEXT,
        document_page SMALLINT,
        chunk_no INTEGER,
        chunk_text TEXT,
        created_date_time TIMESTAMPTZ,
        embedding vector(3072)
        {});
    """).format(
        sql.Identifier(table_name),
        sql.SQL(", faq_id INTEGER" if table_name == FAQ_TABLE_NAME else "")
    )

    try:
        cursor.execute(create_table_query)
        logger.info(f"Table {table_name} creation query executed")

        cursor.execute(sql.SQL("SELECT to_regclass({})").format(sql.Literal(table_name)))
        if cursor.fetchone()[0]:
            logger.info(f"Confirmed: Table {table_name} exists")
        else:
            raise Exception(f"Failed to create table {table_name}")

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
            logger.info(f"HNSW index creation query executed for {table_name}")
        else:
            logger.info(f"No index created for {table_name} as per configuration")
    except psycopg.Error as e:
        logger.error(f"Error creating table or index for {table_name}: {e}")
        raise

def process_csv_file(file_path, cursor, table_name, document_type):
    logger.info(f"Processing CSV file: {file_path}")
    try:
        df = pd.read_csv(file_path)
        logger.debug(f"Successfully read CSV file: {file_path}")
    except Exception as e:
        logger.error(f"Error reading CSV file {file_path}: {e}")
        return

    insert_query = sql.SQL("""
    INSERT INTO {}
    (file_name, file_path, sha256_hash, business_category, document_type, document_page, chunk_no, chunk_text, created_date_time, embedding{})
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s::vector(3072){});
    """).format(
        sql.Identifier(table_name),
        sql.SQL(", faq_id" if table_name == FAQ_TABLE_NAME else ""),
        sql.SQL(", %s" if table_name == FAQ_TABLE_NAME else "")
    )

    data = []
    for _, row in df.iterrows():
        embedding = row['embedding']
        if isinstance(embedding, str):
            embedding = eval(embedding)
        if len(embedding) != 3072:
            logger.warning(f"Incorrect vector dimension for row in {file_path}. Expected 3072, got {len(embedding)}. Skipping.")
            continue

        business_category = os.path.basename(os.path.dirname(file_path))
        row_data = [
            row['file_name'],
            row['file_path'],
            row['sha256_hash'],
            business_category,
            document_type,
            row['document_page'],
            row['chunk_no'],
            row['chunk_text'],
            row['created_date_time'],
            embedding
        ]

        if table_name == FAQ_TABLE_NAME:
            row_data.append(row['faq_id'])

        data.append(tuple(row_data))

    try:
        cursor.executemany(insert_query, data)
        logger.info(f"Inserted {len(data)} rows into the {table_name} table from {file_path}")
    except Exception as e:
        logger.error(f"Error inserting batch into {table_name} from {file_path}: {e}")
        raise

def process_directory(cursor, directory, table_name, document_type):
    csv_files = [os.path.join(root, file) for root, _, files in os.walk(directory) for file in files if file.endswith('.csv')]
    logger.info(f"Found {len(csv_files)} CSV files in {directory} and its subdirectories")
    if not csv_files:
        logger.warning(f"No CSV files found in {directory}")
    for csv_file_path in csv_files:
        try:
            process_csv_file(csv_file_path, cursor, table_name, document_type)
            logger.info(f"Successfully processed {csv_file_path}")
        except Exception as e:
            logger.error(f"Error processing {csv_file_path}: {e}")

def process_csv_files():
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                conn.autocommit = False
                try:
                    create_table_and_index(cursor, MANUAL_TABLE_NAME)
                    create_table_and_index(cursor, FAQ_TABLE_NAME)
                    conn.commit()
                    logger.info("Tables created successfully")

                    logger.info(f"Processing manual CSVs from: {CSV_MANUAL_DIR}")
                    process_directory(cursor, CSV_MANUAL_DIR, MANUAL_TABLE_NAME, "manual")

                    logger.info(f"Processing FAQ CSVs from: {CSV_FAQ_DIR}")
                    process_directory(cursor, CSV_FAQ_DIR, FAQ_TABLE_NAME, "faq")

                    conn.commit()
                    logger.info("All CSV files have been processed and inserted into the database.")
                except Exception as e:
                    conn.rollback()
                    logger.error(f"Transaction rolled back due to error: {e}")
                    raise

                for table_name in [MANUAL_TABLE_NAME, FAQ_TABLE_NAME]:
                    cursor.execute(sql.SQL("SELECT COUNT(*) FROM {}").format(sql.Identifier(table_name)))
                    count = cursor.fetchone()[0]
                    logger.info(f"Total records in {table_name}: {count}")

    except Exception as e:
        logger.error(f"An error occurred during processing: {e}", exc_info=True)
        raise

if __name__ == "__main__":
    try:
        process_csv_files()
    except Exception as e:
        logger.error(f"Script execution failed: {e}", exc_info=True)
        exit(1)
