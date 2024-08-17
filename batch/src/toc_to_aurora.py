# rag-hnsw/batch/src/toc_to_aurora.py
import os
import pandas as pd
from psycopg import sql
import logging
import uuid
import hashlib
from datetime import datetime
import pytz
from utils import get_db_connection, create_tables, get_table_count
from config import *

log_dir = os.path.join(DATA_DIR, "log")
os.makedirs(log_dir, exist_ok=True)
logging.basicConfig(filename=os.path.join(log_dir, "toc_to_aurora.log"), level=logging.DEBUG,
                    format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

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

    # Extract file name and folder name
    file_name = os.path.basename(file_path)
    folder_name = os.path.dirname(file_path)

    # Insert into PDF_TABLE first
    pdf_table_id = uuid.uuid4()
    insert_pdf_query = sql.SQL("""
    INSERT INTO {}
    (id, file_path, folder_name, file_name, document_type, checksum, created_date_time)
    VALUES (%s, %s, %s, %s, %s, %s, %s)
    RETURNING id;
    """).format(sql.Identifier(PDF_TABLE))

    pdf_data = (
        pdf_table_id,
        file_path,
        folder_name,
        file_name,
        1,  # Assuming 1 is the document_type for manual
        checksum,
        created_date_time
    )

    try:
        cursor.execute(insert_pdf_query, pdf_data)
        logger.info(f"Inserted PDF data into {PDF_TABLE}")
    except Exception as e:
        logger.error(f"Error inserting PDF data into {PDF_TABLE}: {e}")
        raise

    # Insert into TOC_TABLE
    insert_toc_query = sql.SQL("""
    INSERT INTO {}
    (id, pdf_table_id, toc_data, checksum, created_date_time)
    VALUES (%s, %s, %s, %s, %s);
    """).format(sql.Identifier(TOC_TABLE))

    toc_data = (
        uuid.uuid4(),
        pdf_table_id,
        toc_data,
        checksum,
        created_date_time
    )

    try:
        cursor.execute(insert_toc_query, toc_data)
        logger.info(f"Inserted TOC data into {TOC_TABLE}")
    except Exception as e:
        logger.error(f"Error inserting TOC data into {TOC_TABLE}: {e}")
        raise

def process_toc_files():
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                conn.autocommit = False
                try:
                    create_tables(cursor)
                    conn.commit()
                    logger.info("Tables created successfully")

                    xlsx_files = []
                    for root, _, files in os.walk(TOC_XLSX_DIR):
                        for file in files:
                            if file.endswith('.xlsx'):
                                xlsx_files.append(os.path.join(root, file))

                    logger.info(f"Found {len(xlsx_files)} XLSX files in {TOC_XLSX_DIR} and its subdirectories")

                    for xlsx_file in xlsx_files:
                        try:
                            process_xlsx_file(xlsx_file, cursor)
                            conn.commit()
                            logger.info(f"Successfully processed {xlsx_file}")
                        except Exception as e:
                            conn.rollback()
                            logger.error(f"Error processing {xlsx_file}: {e}")
                            continue

                    logger.info("All XLSX files have been processed and inserted into the database.")

                except Exception as e:
                    conn.rollback()
                    logger.error(f"Transaction rolled back due to error: {e}")
                    raise

                for table_name in [PDF_TABLE, TOC_TABLE]:
                    get_table_count(cursor, table_name)

    except Exception as e:
        logger.error(f"An error occurred during processing: {e}", exc_info=True)
        raise

if __name__ == "__main__":
    try:
        process_toc_files()
    except Exception as e:
        logger.error(f"Script execution failed: {e}", exc_info=True)
        exit(1)
