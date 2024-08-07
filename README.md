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

