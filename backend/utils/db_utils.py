# rag-hnsw/backend/utils/db_utils.py
import psycopg
from psycopg import sql
from contextlib import contextmanager
import logging
from config import *

logger = logging.getLogger(__name__)

@contextmanager
def get_db_connection():
    conn = None
    cursor = None
    try:
        conn = psycopg.connect(
            dbname=POSTGRES_DB,
            user=POSTGRES_USER,
            password=POSTGRES_PASSWORD,
            host=POSTGRES_HOST,
            port=POSTGRES_PORT
        )
        conn.autocommit = True
        cursor = conn.cursor()
        if INDEX_TYPE == "hnsw":
            cursor.execute(f"SET hnsw.ef_search = {HNSW_EF_SEARCH};")
            logger.info(f"Set hnsw.ef_search to {HNSW_EF_SEARCH}")
        conn.autocommit = False
        yield conn, cursor
    except psycopg.Error as e:
        logger.error(f"Database connection error: {e}")
        raise
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

def get_available_categories():
    try:
        with get_db_connection() as (conn, cursor):
            cursor.execute(sql.SQL("""
                SELECT DISTINCT business_category
                FROM {}
                ORDER BY business_category
            """).format(sql.Identifier(MANUAL_TABLE_NAME)))
            categories = [row[0] for row in cursor.fetchall()]
        return categories
    except psycopg.Error as e:
        logger.error(f"Error fetching available categories: {e}")
        raise

def get_search_query(index_type):
    vector_type = "halfvec(3072)" if index_type == "hnsw" else "vector(3072)"
    operator = "<#>"
    query = sql.SQL("""
    SELECT file_name, document_page, chunk_no, chunk_text,
            (chunk_vector::{vector_type} {operator} %s::{vector_type}) AS distance
    FROM {table}
    WHERE business_category = %s
    ORDER BY distance ASC
    LIMIT %s;
    """).format(
        vector_type=sql.SQL(vector_type),
        operator=sql.SQL(operator),
        table=sql.Identifier(MANUAL_TABLE_NAME)
    )
    return query

def execute_search_query(conn, cursor, question_vector, category, top_n):
    query = get_search_query(INDEX_TYPE)
    cursor.execute(query, (question_vector, category, top_n))
    return cursor.fetchall()
