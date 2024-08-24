# batch/src/reading_aurora.py
import os
import logging
import psycopg
from psycopg.rows import dict_row
from config import *

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

def get_db_connection():
    db_params = {
        'dbname': POSTGRES_DB,
        'user': POSTGRES_USER,
        'password': POSTGRES_PASSWORD,
        'host': POSTGRES_HOST,
        'port': POSTGRES_PORT
    }
    logger.info(f"Attempting to connect to database with params: {db_params}")
    return psycopg.connect(**db_params, options="-c timezone=Asia/Tokyo", row_factory=dict_row)

def get_table_info(cursor, table_name):
    # Get table structure
    cursor.execute("""
    SELECT column_name, data_type
    FROM information_schema.columns
    WHERE table_name = %s;
    """, (table_name,))
    structure = cursor.fetchall()

    # Get index information
    cursor.execute("""
    SELECT
        i.relname AS index_name,
        a.attname AS column_name,
        am.amname AS index_type,
        pg_get_indexdef(i.oid) AS index_definition
    FROM
        pg_index ix
        JOIN pg_class i ON i.oid = ix.indexrelid
        JOIN pg_class t ON t.oid = ix.indrelid
        JOIN pg_am am ON i.relam = am.oid
        LEFT JOIN pg_attribute a ON a.attrelid = t.oid AND a.attnum = ANY(ix.indkey)
    WHERE
        t.relname = %s
    ORDER BY
        i.relname, a.attnum;
    """, (table_name,))
    indexes = cursor.fetchall()

    # Get sample data
    cursor.execute(f"SELECT * FROM {table_name} LIMIT 1;")
    sample = cursor.fetchone()

    # Get record count
    cursor.execute(f"SELECT COUNT(*) FROM {table_name};")
    count = cursor.fetchone()['count']

    return {
        'structure': structure,
        'indexes': indexes,
        'sample': sample,
        'count': count
    }

def get_all_tables(cursor):
    cursor.execute("""
    SELECT table_name
    FROM information_schema.tables
    WHERE table_schema = 'public';
    """)
    return [row['table_name'] for row in cursor.fetchall()]

def get_unique_business_categories_with_counts(cursor, table_name):
    cursor.execute(f"""
    SELECT business_category, COUNT(*) as record_count
    FROM {table_name}
    GROUP BY business_category
    ORDER BY business_category;
    """)
    return cursor.fetchall()

def print_table_info(table_name, info):
    logger.info(f"\n######### Table: {table_name} #########")

    logger.info("------ Table Structure ------")
    for column in info['structure']:
        logger.info(f"  - {column['column_name']}: {column['data_type']}")

    logger.info("\n------ Index Information ------")
    for index in info['indexes']:
        logger.info(f"Index Name: {index['index_name']}")
        logger.info(f"  Column: {index['column_name']}")
        logger.info(f"  Type: {index['index_type']}")
        logger.info(f"  Definition: {index['index_definition']}")
        logger.info("  ---")

    logger.info("------ Sample Data ------")
    if info['sample']:
        formatted_sample = {k: (v[:27] + " ...]" if k == 'embedding' and len(str(v)) > 30 else v) for k, v in info['sample'].items()}
        logger.info(formatted_sample)
    else:
        logger.warning("No sample data found.")

def main():
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                tables = get_all_tables(cursor)

                if not tables:
                    logger.warning("No tables found in the database.")
                else:
                    logger.info(f"Found {len(tables)} tables in the database.")

                table_summary = []
                for table_name in tables:
                    info = get_table_info(cursor, table_name)
                    print_table_info(table_name, info)
                    table_summary.append((table_name, info['count']))

                    # Get business categories for each table
                    if 'business_category' in [col['column_name'] for col in info['structure']]:
                        categories_with_counts = get_unique_business_categories_with_counts(cursor, table_name)
                        if categories_with_counts:
                            logger.info(f"\n------ Unique Business Categories with Record Counts for {table_name} ------")
                            total_records = sum(category['record_count'] for category in categories_with_counts)
                            for category in categories_with_counts:
                                percentage = (category['record_count'] / total_records) * 100
                                logger.info(f"  - {category['business_category']}: {category['record_count']} records ({percentage:.2f}%)")
                            logger.info(f"\nTotal records across all categories in {table_name}: {total_records}")

                logger.info("\n------ Table Summary ------")
                for table_name, record_count in table_summary:
                    logger.info(f"Table: {table_name}, Records: {record_count}")

        logger.info("\nDatabase reading completed.")
    except psycopg.Error as e:
        logger.error(f"Database error occurred: {e}")
    except Exception as e:
        logger.error(f"Unexpected error occurred: {e}", exc_info=True)

if __name__ == "__main__":
    main()
