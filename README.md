# rag-hnsw

-- カテゴリ別の INSERT 操作
INSERT INTO embeddings_table (file_name, business_category, document_page, chunk_no, chunk_text, model, prompt_tokens, total_tokens, created_date_time, chunk_vector)
VALUES ('example.pdf', 'finance', 1, 1, 'This is a financial document.', 'text-embedding-3-large', 10, 20, CURRENT_TIMESTAMP, '[0.1, 0.2, ..., 0.3]'::vector(3072));

-- カテゴリ別の DELETE 操作
DELETE FROM embeddings_table
WHERE business_category = 'finance';

-- インデックスの再構築
DROP INDEX IF EXISTS hnsw_embeddings_table_chunk_vector_idx;
CREATE INDEX hnsw_embeddings_table_chunk_vector_idx ON embeddings_table
USING hnsw ((chunk_vector::halfvec(3072)) halfvec_ip_ops)
WITH (m = 16, ef_construction = 256);

-- オプション: VACUUM ANALYZE を実行してテーブル統計を更新
VACUUM ANALYZE embeddings_table;

コンテナ内でファイルを作成するユーザーの UID を確認:
docker exec -it <コンテナ名> id

# .env

# Base directories
DATA_DIR='/app/data'

# POSTGRES
POSTGRES_DB=aurora
POSTGRES_USER=user
POSTGRES_PASSWORD=pass
POSTGRES_HOST=aurora
POSTGRES_PORT=5432

# Index settings
INDEX_TYPE="hnsw"
HNSW_SETTINGS='{"m": 16, "ef_construction": 256, "ef_search": 500}'

# Other settings
BATCH_SIZE=1000
PIPELINE_EXECUTION_MODE="csv_to_aurora"
