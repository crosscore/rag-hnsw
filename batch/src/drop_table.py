# rag-hnsw/batch/src/drop_table.py
import psycopg
from psycopg import sql
import logging
import time
from config import POSTGRES_DB, POSTGRES_USER, POSTGRES_PASSWORD, POSTGRES_HOST, POSTGRES_PORT

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)

def get_db_connection():
    return psycopg.connect(
        dbname=POSTGRES_DB,
        user=POSTGRES_USER,
        password=POSTGRES_PASSWORD,
        host=POSTGRES_HOST,
        port=POSTGRES_PORT
    )

def get_all_public_tables(cursor):
    cursor.execute("""
    SELECT table_name
    FROM information_schema.tables
    WHERE table_schema = 'public'
    """)
    return [row[0] for row in cursor.fetchall()]

def terminate_active_connections(cursor, database_name):
    cursor.execute("""
    SELECT pg_terminate_backend(pid)
    FROM pg_stat_activity
    WHERE datname = %s AND pid <> pg_backend_pid()
    """, (database_name,))
    logger.info("Terminated all active connections.")

def drop_table_with_retry(cursor, table, max_retries=3, retry_delay=5):
    for attempt in range(max_retries):
        try:
            drop_table_query = sql.SQL("DROP TABLE IF EXISTS {} CASCADE").format(sql.Identifier(table))
            cursor.execute(drop_table_query)
            logger.info(f"Deleted table {table}.")
            return True
        except psycopg.Error as e:
            logger.warning(f"Failed to drop table {table} on attempt {attempt + 1}: {e}")
            if attempt < max_retries - 1:
                time.sleep(retry_delay)
    logger.error(f"Failed to drop table {table} after {max_retries} attempts.")
    return False

def drop_all_tables(cursor, tables):
    for table in tables:
        drop_table_with_retry(cursor, table)

def main():
    logger.info("Starting the process of deleting all public tables.")

    try:
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                # Increase statement timeout
                cursor.execute("SET statement_timeout = '300s'")
                
                # Terminate active connections
                terminate_active_connections(cursor, POSTGRES_DB)
                
                tables = get_all_public_tables(cursor)
                if not tables:
                    logger.info("No public tables to delete.")
                else:
                    logger.info(f"Tables to be deleted: {', '.join(tables)}")
                    drop_all_tables(cursor, tables)
                    conn.commit()
                    logger.info(f"Deleted a total of {len(tables)} tables.")
    except psycopg.Error as e:
        logger.error(f"An error occurred during database operation: {e}")
    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}")

    logger.info("Table deletion process completed.")

if __name__ == "__main__":
    main()
