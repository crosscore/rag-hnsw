# rag-hnsw/backend/src/drop_table.py
import psycopg
from psycopg import sql
import logging
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

def drop_all_tables(cursor, tables):
    for table in tables:
        drop_table_query = sql.SQL("DROP TABLE IF EXISTS {} CASCADE").format(sql.Identifier(table))
        cursor.execute(drop_table_query)
        logger.info(f"Deleted table {table}.")

def main():
    logger.info("Starting the process of deleting all public tables.")

    try:
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
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
