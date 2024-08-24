# batch/src/toc_to_aurora.py
import os
import pandas as pd
from psycopg import sql
import uuid
from utils import get_db_connection, create_tables, get_table_count, process_file_common, calculate_checksum, get_current_datetime, get_file_name, get_business_category, setup_logging
from config import *

logger = setup_logging("toc_to_aurora")

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

    file_name = get_file_name(file_path)  # This now includes the extension
    checksum = calculate_checksum(file_path)
    created_date_time = get_current_datetime()
    business_category = get_business_category(file_path, TOC_XLSX_DIR)

    # Use the common function to process DOCUMENT_TABLE and DOCUMENT_CATEGORY_TABLE
    document_table_id = process_file_common(cursor, file_path, file_name, DOCUMENT_TYPE_XLSX_TOC, checksum, created_date_time, business_category)

    # Insert into XLSX_TOC_TABLE
    insert_toc_query = sql.SQL("""
    INSERT INTO {}
    (id, document_table_id, file_name, toc_data, checksum, created_date_time)
    VALUES (%s, %s, %s, %s, %s, %s)
    ON CONFLICT (document_table_id, file_name) DO UPDATE SET
    toc_data = EXCLUDED.toc_data,
    checksum = EXCLUDED.checksum,
    created_date_time = EXCLUDED.created_date_time;
    """).format(sql.Identifier(XLSX_TOC_TABLE))

    toc_data = (
        uuid.uuid4(),
        document_table_id,
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

                for table_name in [DOCUMENT_TABLE, XLSX_TOC_TABLE]:
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
