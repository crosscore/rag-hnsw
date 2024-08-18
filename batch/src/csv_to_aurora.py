# rag-hnsw/batch/src/csv_to_aurora.py
import os
import pandas as pd
from psycopg import sql
import logging
import uuid
from utils import get_db_connection, create_tables, create_index, get_table_count
from config import *

log_dir = os.path.join(DATA_DIR, "log")
os.makedirs(log_dir, exist_ok=True)
logging.basicConfig(filename=os.path.join(log_dir, "csv_to_aurora.log"), level=logging.DEBUG,
                    format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def process_csv_file(file_path, cursor, table_name, document_type):
    logger.info(f"Processing CSV file: {file_path}")
    try:
        df = pd.read_csv(file_path)
        logger.debug(f"Successfully read CSV file: {file_path}")
    except Exception as e:
        logger.error(f"Error reading CSV file {file_path}: {e}")
        return

    # Insert into PDF_TABLE first
    insert_pdf_query = sql.SQL("""
    INSERT INTO {}
    (id, file_path, file_name, document_type, checksum, created_date_time)
    VALUES (%s, %s, %s, %s, %s, %s)
    ON CONFLICT (file_path) DO NOTHING
    RETURNING id;
    """).format(sql.Identifier(PDF_TABLE))

    pdf_data = (
        uuid.uuid4(),
        df['file_path'].iloc[0],
        df['file_name'].iloc[0],
        1 if document_type == 'manual' else 2,
        df['checksum'].iloc[0],
        df['created_date_time'].iloc[0]
    )

    try:
        cursor.execute(insert_pdf_query, pdf_data)
        pdf_table_id = cursor.fetchone()
        if pdf_table_id:
            pdf_table_id = pdf_table_id[0]
            logger.info(f"Inserted PDF data into {PDF_TABLE}")
        else:
            cursor.execute(sql.SQL("SELECT id FROM {} WHERE file_path = %s").format(sql.Identifier(PDF_TABLE)), (df['file_path'].iloc[0],))
            pdf_table_id = cursor.fetchone()[0]
            logger.info(f"PDF data already exists in {PDF_TABLE}")
    except Exception as e:
        logger.error(f"Error inserting PDF data into {PDF_TABLE}: {e}")
        raise

    # Insert into PDF_CATEGORY_TABLE
    insert_category_query = sql.SQL("""
    INSERT INTO {}
    (id, pdf_table_id, business_category, created_date_time)
    VALUES (%s, %s, %s, %s)
    ON CONFLICT (pdf_table_id, business_category) DO NOTHING;
    """).format(sql.Identifier(PDF_CATEGORY_TABLE))

    category_data = (
        uuid.uuid4(),
        pdf_table_id,
        int(df['business_category'].iloc[0]),
        df['created_date_time'].iloc[0]
    )

    try:
        cursor.execute(insert_category_query, category_data)
        logger.info(f"Inserted category data into {PDF_CATEGORY_TABLE}")
    except Exception as e:
        logger.error(f"Error inserting category data into {PDF_CATEGORY_TABLE}: {e}")
        raise

    # Insert into PDF_MANUAL_TABLE or PDF_FAQ_TABLE
    if table_name == PDF_MANUAL_TABLE:
        insert_query = sql.SQL("""
        INSERT INTO {}
        (id, pdf_table_id, chunk_no, document_page, chunk_text, embedding, created_date_time)
        VALUES (%s, %s, %s, %s, %s, %s::vector(3072), %s);
        """).format(sql.Identifier(table_name))
    else:  # PDF_FAQ_TABLE
        insert_query = sql.SQL("""
        INSERT INTO {}
        (id, pdf_table_id, document_page, faq_no, page_text, embedding, created_date_time)
        VALUES (%s, %s, %s, %s, %s, %s::vector(3072), %s);
        """).format(sql.Identifier(table_name))

    data = []
    for _, row in df.iterrows():
        embedding = row['embedding']
        if isinstance(embedding, str):
            embedding = eval(embedding)
        if len(embedding) != 3072:
            logger.warning(f"Incorrect vector dimension for row in {file_path}. Expected 3072, got {len(embedding)}. Skipping.")
            continue

        if table_name == PDF_MANUAL_TABLE:
            row_data = (
                uuid.uuid4(),
                pdf_table_id,
                row['chunk_no'],
                row['document_page'],
                row['chunk_text'],
                embedding,
                row['created_date_time']
            )
        else:  # PDF_FAQ_TABLE
            row_data = (
                uuid.uuid4(),
                pdf_table_id,
                row['document_page'],
                row['faq_no'],
                row['page_text'],
                embedding,
                row['created_date_time']
            )

        data.append(row_data)

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
                    create_tables(cursor)
                    create_index(cursor, PDF_MANUAL_TABLE)
                    create_index(cursor, PDF_FAQ_TABLE)
                    conn.commit()
                    logger.info("Tables created successfully")

                    logger.info(f"Processing manual CSVs from: {CSV_MANUAL_DIR}")
                    process_directory(cursor, CSV_MANUAL_DIR, PDF_MANUAL_TABLE, "manual")

                    logger.info(f"Processing FAQ CSVs from: {CSV_FAQ_DIR}")
                    process_directory(cursor, CSV_FAQ_DIR, PDF_FAQ_TABLE, "faq")

                    conn.commit()
                    logger.info("All CSV files have been processed and inserted into the database.")
                except Exception as e:
                    conn.rollback()
                    logger.error(f"Transaction rolled back due to error: {e}")
                    raise

                for table_name in [PDF_TABLE, PDF_CATEGORY_TABLE, PDF_MANUAL_TABLE, PDF_FAQ_TABLE]:
                    get_table_count(cursor, table_name)

    except Exception as e:
        logger.error(f"An error occurred during processing: {e}", exc_info=True)
        raise

if __name__ == "__main__":
    try:
        process_csv_files()
    except Exception as e:
        logger.error(f"Script execution failed: {e}", exc_info=True)
        exit(1)
