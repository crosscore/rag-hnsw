# rag-hnsw/batch/src/toc_to_aurora.py
import os
import pandas as pd
import psycopg
from psycopg import sql
from config import *
import logging
from contextlib import contextmanager
from datetime import datetime
import pytz
import hashlib

log_dir = os.path.join(DATA_DIR, "log")
os.makedirs(log_dir, exist_ok=True)
logging.basicConfig(filename=os.path.join(log_dir, "toc_to_aurora.log"), level=logging.DEBUG,
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

def create_toc_table(cursor):
    create_table_query = sql.SQL("""
    CREATE TABLE IF NOT EXISTS {} (
        id SERIAL PRIMARY KEY,
        file_path TEXT,
        toc_data TEXT,
        checksum TEXT,
        created_date_time TIMESTAMPTZ
    );
    """).format(sql.Identifier(TOC_TABLE_NAME))

    try:
        cursor.execute(create_table_query)
        logger.info(f"Table {TOC_TABLE_NAME} creation query executed")

        cursor.execute(sql.SQL("SELECT to_regclass({})").format(sql.Literal(TOC_TABLE_NAME)))
        if cursor.fetchone()[0]:
            logger.info(f"Confirmed: Table {TOC_TABLE_NAME} exists")
        else:
            raise Exception(f"Failed to create table {TOC_TABLE_NAME}")
    except psycopg.Error as e:
        logger.error(f"Error creating table {TOC_TABLE_NAME}: {e}")
        raise

def process_xlsx_file(file_path, cursor):
    logger.info(f"Processing XLSX file: {file_path}")
    try:
        df = pd.read_excel(file_path, engine='openpyxl')
        logger.debug(f"Successfully read XLSX file: {file_path}")
    except Exception as e:
        logger.error(f"Error reading XLSX file {file_path}: {e}")
        return

    # Convert DataFrame to CSV string
    toc_data = df.to_csv(index=False)

    # Calculate SHA256 hash of the file
    checksum = hashlib.sha256(open(file_path, 'rb').read()).hexdigest()

    # Get current datetime in Tokyo timezone
    tokyo_tz = pytz.timezone('Asia/Tokyo')
    created_date_time = datetime.now(tokyo_tz)

    insert_query = sql.SQL("""
    INSERT INTO {} (file_path, toc_data, checksum, created_date_time)
    VALUES (%s, %s, %s, %s);
    """).format(sql.Identifier(TOC_TABLE_NAME))

    try:
        cursor.execute(insert_query, (file_path, toc_data, checksum, created_date_time))
        logger.info(f"Inserted data from {file_path} into the {TOC_TABLE_NAME} table")
    except Exception as e:
        logger.error(f"Error inserting data into {TOC_TABLE_NAME} from {file_path}: {e}")
        raise

def process_toc_files():
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                conn.autocommit = False
                try:
                    create_toc_table(cursor)
                    conn.commit()
                    logger.info("TOC table created successfully")

                    xlsx_files = []
                    for root, _, files in os.walk(TOC_XLSX_DIR):
                        for file in files:
                            if file.endswith('.xlsx'):
                                xlsx_files.append(os.path.join(root, file))

                    logger.info(f"Found {len(xlsx_files)} XLSX files in {TOC_XLSX_DIR} and its subdirectories")

                    for xlsx_file in xlsx_files:
                        try:
                            process_xlsx_file(xlsx_file, cursor)
                            logger.info(f"Successfully processed {xlsx_file}")
                        except Exception as e:
                            logger.error(f"Error processing {xlsx_file}: {e}")
                            conn.rollback()
                            continue

                    conn.commit()
                    logger.info("All XLSX files have been processed and inserted into the database.")

                except Exception as e:
                    conn.rollback()
                    logger.error(f"Transaction rolled back due to error: {e}")
                    raise

                cursor.execute(sql.SQL("SELECT COUNT(*) FROM {}").format(sql.Identifier(TOC_TABLE_NAME)))
                count = cursor.fetchone()[0]
                logger.info(f"Total records in {TOC_TABLE_NAME}: {count}")

    except Exception as e:
        logger.error(f"An error occurred during processing: {e}", exc_info=True)
        raise

if __name__ == "__main__":
    try:
        process_toc_files()
    except Exception as e:
        logger.error(f"Script execution failed: {e}", exc_info=True)
        exit(1)
