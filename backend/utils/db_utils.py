# backend/utils/db_utils.py
import psycopg_pool
from psycopg import sql
import logging
from config import *

logger = logging.getLogger(__name__)

# Create a connection pool
pool = psycopg_pool.ConnectionPool(
    f"dbname={POSTGRES_DB} user={POSTGRES_USER} password={POSTGRES_PASSWORD} host={POSTGRES_HOST} port={POSTGRES_PORT}",
    min_size=1,
    max_size=10
)

def get_db_connection():
    return pool

def execute_query(conn, query, params=None):
    with conn.cursor() as cur:
        if INDEX_TYPE == "hnsw":
            cur.execute(f"SET hnsw.ef_search = {HNSW_EF_SEARCH};")
        cur.execute(query, params)
        return cur.fetchall()

def get_available_categories():
    try:
        with pool.connection() as conn:
            query = sql.SQL("""
                SELECT DISTINCT business_category
                FROM {}
                ORDER BY business_category
            """).format(sql.Identifier(DOCUMENT_CATEGORY_TABLE))
            categories = [row[0] for row in execute_query(conn, query)]
            return {name: value for name, value in BUSINESS_CATEGORY_MAPPING.items() if value in categories}
    except psycopg_pool.PoolError as e:
        logger.error(f"Error fetching available categories: {e}")
        raise

def get_search_query(index_type, table_name):
    vector_type = "halfvec(3072)" if index_type == "hnsw" else "vector(3072)"
    operator = OPERATOR

    if table_name == PDF_MANUAL_TABLE:
        query = sql.SQL("""
        SELECT t.document_table_id, t.chunk_no, t.document_page, t.chunk_text,
                (t.embedding::{vector_type} {operator} %s::{vector_type}) AS distance
        FROM {table} t
        JOIN {document_category_table} c ON t.document_table_id = c.document_table_id
        WHERE c.business_category = %s
        ORDER BY distance ASC
        LIMIT %s;
        """)
    elif table_name == PDF_FAQ_TABLE:
        query = sql.SQL("""
        SELECT t.document_table_id, t.document_page, t.faq_no, t.chunk_text,
                (t.embedding::{vector_type} {operator} %s::{vector_type}) AS distance
        FROM {table} t
        JOIN {document_category_table} c ON t.document_table_id = c.document_table_id
        WHERE c.business_category = %s
        ORDER BY distance ASC
        LIMIT %s;
        """)
    else:
        raise ValueError(f"Unsupported table name: {table_name}")

    return query.format(
        vector_type=sql.SQL(vector_type),
        operator=sql.SQL(operator),
        table=sql.Identifier(table_name),
        document_category_table=sql.Identifier(DOCUMENT_CATEGORY_TABLE)
    )

def execute_search_query(conn, question_vector, category, top_n, table_name):
    query = get_search_query(INDEX_TYPE, table_name)
    results = execute_query(conn, query, (question_vector, int(category), top_n))

    if len(results) < top_n:
        additional_query = get_search_query(INDEX_TYPE, table_name)
        additional_results = execute_query(conn, additional_query, (question_vector, int(category), top_n - len(results)))
        results.extend(additional_results)

    return results[:top_n]

def get_toc_data(conn, category):
    try:
        query = sql.SQL("""
            SELECT xt.toc_data
            FROM {xlsx_toc_table} xt
            JOIN {document_table} dt ON xt.document_table_id = dt.id
            JOIN {document_category_table} dct ON dt.id = dct.document_table_id
            WHERE dct.business_category = %s
        """).format(
            xlsx_toc_table=sql.Identifier(XLSX_TOC_TABLE),
            document_table=sql.Identifier(DOCUMENT_TABLE),
            document_category_table=sql.Identifier(DOCUMENT_CATEGORY_TABLE)
        )
        
        results = execute_query(conn, query, (category,))
        
        if not results:
            logger.warning(f"No TOC data found for category: {category}")
            return ""
        
        # 複数のTOC dataを結合
        all_toc_data = "\n\n".join([result[0] for result in results])
        
        return all_toc_data
    except Exception as e:
        logger.error(f"Error fetching TOC data for category {category}: {e}")
        return ""
