# rag-hnsw

-- カテゴリ別のINSERT操作
INSERT INTO embeddings_table (file_name, business_category, document_page, chunk_no, chunk_text, model, prompt_tokens, total_tokens, created_date_time, chunk_vector)
VALUES ('example.pdf', 'finance', 1, 1, 'This is a financial document.', 'text-embedding-3-large', 10, 20, CURRENT_TIMESTAMP, '[0.1, 0.2, ..., 0.3]'::vector(3072));

-- カテゴリ別のDELETE操作
DELETE FROM embeddings_table
WHERE business_category = 'finance';

-- インデックスの再構築
DROP INDEX IF EXISTS hnsw_embeddings_table_chunk_vector_idx;
CREATE INDEX hnsw_embeddings_table_chunk_vector_idx ON embeddings_table
USING hnsw ((chunk_vector::halfvec(3072)) halfvec_ip_ops)
WITH (m = 16, ef_construction = 256);

-- オプション: VACUUM ANALYZE を実行してテーブル統計を更新
VACUUM ANALYZE embeddings_table;


コンテナ内でファイルを作成するユーザーのUIDを確認:
docker exec -it <コンテナ名> id

ホストマシン上でのあなたのUIDとGIDを確認:
id #確認コマンド

UIDが一致しない場合、以下のいずれかの対策を検討:
 - DockerfileでUSER命令を使用して、ホストマシンと同じUIDを持つユーザーでコンテナを実行する。
```
USER 0
```
 - ホストマシン上で、./backendディレクトリの所有者を変更する。 (セキュリティリスクを考慮)
```

```
 - ボリュームマウント時に:uid=1000,gid=1000のようにUIDとGIDを指定する。 (コンテナ内でのユーザーとグループの整合性に注意が必要)
 ```
volumes:
  - ./backend:/app:uid=0,gid=0
 ```

\d+

# .env

# Base directories
DATA_DIR='/app/data'

# POSTGRES (オーバーライドが必要な場合のみ設定)
POSTGRES_DB=aurora
POSTGRES_USER=user
POSTGRES_PASSWORD=pass
POSTGRES_HOST=aurora
POSTGRES_PORT=5432

# Index settings
INDEX_TYPE="hnsw"
HNSW_SETTINGS='{"m": 16, "ef_construction": 256, "ef_search": 500}'

# PostgreSQL table settings
MANUAL_TABLE_NAME="manual_embeddings"
FAQ_TABLE_NAME="faq_embeddings"
TOC_TABLE_NAME="toc_table"

# Other settings
BATCH_SIZE=1000
PIPELINE_EXECUTION_MODE="csv_to_aurora"
