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
            dbname=PGVECTOR_DB_NAME,
            user=PGVECTOR_DB_USER,
            password=PGVECTOR_DB_PASSWORD,
            host=PGVECTOR_DB_HOST,
            port=PGVECTOR_DB_PORT
        )
        conn.autocommit = True
        cursor = conn.cursor()
        if INDEX_TYPE == "ivfflat":
            cursor.execute(f"SET ivfflat.probes = {IVFFLAT_PROBES};")
            logger.info(f"Set ivfflat.probes to {IVFFLAT_PROBES}")
        elif INDEX_TYPE == "hnsw":
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
            cursor.execute("""
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = 'public' AND table_name != 'document_vectors'
            """)
            categories = [row[0] for row in cursor.fetchall()]
        return categories
    except psycopg.Error as e:
        logger.error(f"Error fetching available categories: {e}")
        raise

def get_search_query(index_type, category):
    vector_type = "halfvec(3072)" if index_type in ["hnsw", "ivfflat"] else "vector(3072)"
    query = sql.SQL("""
    SELECT file_name, document_page, chunk_no, chunk_text,
            (chunk_vector::{vector_type} <#> %s::{vector_type}) AS distance
    FROM {table}
    ORDER BY distance ASC
    LIMIT %s;
    """).format(
        vector_type=sql.SQL(vector_type),
        table=sql.Identifier(category)
    )
    return query

def execute_search_query(conn, cursor, question_vector, top_n, category):
    query = get_search_query(INDEX_TYPE, category)
    cursor.execute(query, (question_vector, top_n))
    return cursor.fetchall()
