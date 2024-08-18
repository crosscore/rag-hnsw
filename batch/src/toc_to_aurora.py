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

    # Extract file name without extension
    file_name = os.path.splitext(os.path.basename(file_path))[0]

    # Get the relative path for business_category
    relative_path = os.path.relpath(os.path.dirname(file_path), TOC_XLSX_DIR)
    business_category = int(relative_path.split(os.path.sep)[0])

    # Check if a corresponding PDF exists in PDF_TABLE
    check_pdf_query = sql.SQL("""
    SELECT id FROM {}
    WHERE file_name = %s AND id IN (
        SELECT pdf_table_id FROM {} WHERE business_category = %s
    )
    """).format(sql.Identifier(PDF_TABLE), sql.Identifier(PDF_CATEGORY_TABLE))

    cursor.execute(check_pdf_query, (file_name, business_category))
    existing_pdf = cursor.fetchone()

    if existing_pdf:
        pdf_table_id = existing_pdf[0]
        logger.info(f"Found corresponding PDF in {PDF_TABLE}")
    else:
        logger.warning(f"No corresponding PDF found for XLSX file: {file_name}")
        return

    # Insert into XLSX_TOC_TABLE
    insert_toc_query = sql.SQL("""
    INSERT INTO {}
    (id, pdf_table_id, file_name, toc_data, checksum, created_date_time)
    VALUES (%s, %s, %s, %s, %s, %s)
    ON CONFLICT (pdf_table_id, file_name) DO UPDATE SET
    toc_data = EXCLUDED.toc_data,
    checksum = EXCLUDED.checksum,
    created_date_time = EXCLUDED.created_date_time;
    """).format(sql.Identifier(XLSX_TOC_TABLE))

    toc_data = (
        uuid.uuid4(),
        pdf_table_id,
        file_name,
        toc_data,
        checksum,
        created_date_time
    )

    try:
        cursor.execute(insert_toc_query, toc_data)
        logger.info(f"Inserted/Updated TOC data in {XLSX_TOC_TABLE}")
    except Exception as e:
        logger.error(f"Error inserting/updating TOC data in {XLSX_TOC_TABLE}: {e}")
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

                for table_name in [PDF_TABLE, XLSX_TOC_TABLE]:
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
