# PostgreSQL テーブル構造

## 注意事項:

1. すべてのテーブル名は config.py から読み込まれる大文字の変数です。
2. すべてのカラム名は小文字で設定されます。
3. すべての日時は Asia/Tokyo（日本時間）のタイムゾーンで保存されます。
4. SMALLINT は PostgreSQL では int2 と同等です。
5. INTEGER は PostgreSQL では int4 と同等です。
6. vector(3072)データ型は pgvector 拡張機能を使用しています。Dockerfile の設定により、事前に aurora コンテナの PostgreSQL に pgvector 拡張機能がインストールされています。
7. PDF_MANUAL_TABLE と PDF_FAQ_TABLE の embedding カラムには HNSW インデックスが作成されます。これは pgvector 拡張機能によって提供される近似最近傍探索インデックスです。
8. すべての外部キー（document_table_id）は DOCUMENT_TABLE の id カラムを参照しています。
9. CHUNK_SIZE と CHUNK_OVERLAP の設定：
    - CHUNK_SIZE: 1000 文字
    - CHUNK_OVERLAP: 0 文字
    - これらの値は config.py で設定されています。
10. HNSW インデックスの設定：
    - m: 16
    - ef_construction: 256
    - ef_search: 500
    - これらの値は config.py で設定されています。
11. DOCUMENT_CATEGORY_TABLE の document_table_id は UNIQUE であるべきではありません。
12. XLSX_TOC_TABLE はベクトル化しないため、HNSW インデックスは不要です。
13. テーブル名は config.py から読み込みます。
14. この構造では、1 つの PDF ファイルを複数のカテゴリに関連付けることができます。例えば、"/app/data/pdf/manual/category1/test.pdf"と"/app/data/pdf/manual/category2/test.pdf"のように、同じファイル名の PDF が複数のカテゴリに属する場合があります。
15. XLSX_TOC_TABLE は、DOCUMENT_TABLE に保存される PDF 毎に存在する目次データを格納します。
16. PDF と XLSX ファイルの関連付けは、business_category でフィルタリングした後、file_name（拡張子を除く）で行います。
17. file_name カラムには、拡張子を含めたファイル名を保存します。
18. DOCUMENT_TABLE から folder_name カラムは削除されました。
19. csv_to_aurora.py と toc_to_aurora.py の両方で、PDF と XLSX ファイルの関連付けのロジックを実装する必要があります。
20. HNSW インデックスの作成は PDF_MANUAL_TABLE と PDF_FAQ_TABLE の両方に必要です。toc_to_aurora.py ではベクトル化を行わないため、HNSW インデックスの作成は不要です。

## PDF と XLSX の関連付けクエリ例

```sql
SELECT p.*, x.*
FROM DOCUMENT_TABLE p
JOIN DOCUMENT_CATEGORY_TABLE c ON p.id = c.document_table_id
JOIN XLSX_TOC_TABLE x ON p.id = x.document_table_id
WHERE c.business_category = [指定のカテゴリ]
  AND SUBSTRING(p.file_name, 1, LENGTH(p.file_name) - 4) = SUBSTRING(x.file_name, 1, LENGTH(x.file_name) - 5);
```

## DOCUMENT_TABLE (PDF 情報テーブル):

-   id (Primary Key): uuid, NOT NULL, UUID v4 によるランダム値
-   file_path: varchar(1024) NOT NULL, PDF のフルパス
-   file_name: varchar(1024) NOT NULL, PDF のファイル名（拡張子を含む）
-   document_type: SMALLINT NOT NULL, ドキュメントの種類 (1: manual(PDF), 2: faq(PDF), 3: toc(XLSX))
-   checksum: varchar(64) NOT NULL, PDF の SHA256 ハッシュ値
-   created_date_time: timestamp with time zone NOT NULL, レコード作成日時
-   UNIQUE(file_path)

## DOCUMENT_CATEGORY_TABLE (PDF とカテゴリの関係テーブル):

-   id (Primary Key): uuid NOT NULL, UUID v4 によるランダム値
-   document_table_id (Foreign Key): uuid NOT NULL, DOCUMENT_TABLE の id カラムを参照
-   business_category: SMALLINT NOT NULL, 業務カテゴリ (1: 新契約, 2: 収納, 3: 保全, 4: 保険金, 5: 商品, 6: MSA ケア, 7: 手数料, 8: 代理店制度, 9: 職域推進, 10: 人事, 11: 会計)
-   created_date_time: timestamp with time zone NOT NULL, レコード作成日時
-   UNIQUE(document_table_id, business_category)

## XLSX_TOC_TABLE (XLSX 目次情報テーブル)

-   id (Primary Key): uuid NOT NULL, UUID v4 によるランダム値
-   document_table_id (Foreign Key): uuid NOT NULL, DOCUMENT_TABLE の id カラムを参照
-   file_name: varchar(1024) NOT NULL, XLSX のファイル名（拡張子を含む）
-   toc_data: text NOT NULL, XLSX ファイルの 1 シート分を「","区切りの CSV 形式」でテキスト化し、行単位で改行された内容
-   checksum: varchar(64) NOT NULL, XLSX ファイルの SHA256 ハッシュ値
-   created_date_time: timestamp with time zone NOT NULL, レコード作成日時
-   UNIQUE(document_table_id, file_name)

## PDF_MANUAL_TABLE (PDF マニュアル情報テーブル)

-   id (Primary Key): uuid NOT NULL, UUID v4 によるランダム値
-   document_table_id (Foreign Key): uuid NOT NULL, DOCUMENT_TABLE の id カラムを参照
-   chunk_no: INTEGER NOT NULL, PDF のテキストをページ毎かつ CHUNK_SIZE 毎に分割したチャンクの連番 (開始番号: 1)
-   document_page: SMALLINT NOT NULL, チャンクの存在する PDF のページ番号 (開始番号: 1)
-   chunk_text: text NOT NULL, チャンク毎のテキスト
-   embedding: vector(3072) NOT NULL, chunk_text のベクトルデータ
-   created_date_time: timestamp with time zone NOT NULL, レコード作成日時

## PDF_FAQ_TABLE (PDF マニュアル情報テーブル)

-   id (Primary Key): uuid NOT NULL, UUID v4 によるランダム値
-   document_table_id (Foreign Key): uuid NOT NULL, DOCUMENT_TABLE の id カラムを参照
-   document_page: INTEGER NOT NULL, PDF のページ番号 (開始番号: 1)
-   faq_no: SMALLINT NOT NULL, ページ毎の FAQ 番号 (preprocess_faq_text 関数が返却する faq_no の数値)
-   page_text: text NOT NULL, ページ毎のテキスト (preprocess_faq_text 関数が返却する processed_text の文字列)
-   embedding: vector(3072) NOT NULL, page_text のベクトルデータ
-   created_date_time: timestamp with time zone NOT NULL, レコード作成日時

## テーブル作成クエリ

### pgvector 拡張機能のインストール

CREATE EXTENSION IF NOT EXISTS vector;

### DOCUMENT_TABLE

CREATE TABLE IF NOT EXISTS {DOCUMENT_TABLE} (
id UUID PRIMARY KEY,
file_path VARCHAR(1024) NOT NULL,
file_name VARCHAR(1024) NOT NULL,
document_type SMALLINT NOT NULL,
checksum VARCHAR(64) NOT NULL,
created_date_time TIMESTAMP WITH TIME ZONE NOT NULL,
UNIQUE(file_path)
);

### DOCUMENT_CATEGORY_TABLE

CREATE TABLE IF NOT EXISTS {DOCUMENT_CATEGORY_TABLE} (
id UUID PRIMARY KEY,
document_table_id UUID NOT NULL REFERENCES {DOCUMENT_TABLE}(id),
business_category SMALLINT NOT NULL,
created_date_time TIMESTAMP WITH TIME ZONE NOT NULL,
UNIQUE(document_table_id, business_category)
);

### XLSX_TOC_TABLE

CREATE TABLE IF NOT EXISTS {XLSX_TOC_TABLE} (
id UUID PRIMARY KEY,
document_table_id UUID NOT NULL REFERENCES {DOCUMENT_TABLE}(id),
file_name VARCHAR(1024) NOT NULL,
toc_data TEXT NOT NULL,
checksum VARCHAR(64) NOT NULL,
created_date_time TIMESTAMP WITH TIME ZONE NOT NULL,
UNIQUE(document_table_id, file_name)
);

### PDF_MANUAL_TABLE

CREATE TABLE IF NOT EXISTS {PDF_MANUAL_TABLE} (
id UUID PRIMARY KEY,
document_table_id UUID NOT NULL REFERENCES {DOCUMENT_TABLE}(id),
chunk_no INTEGER NOT NULL,
document_page SMALLINT NOT NULL,
chunk_text TEXT NOT NULL,
embedding VECTOR(3072) NOT NULL,
created_date_time TIMESTAMP WITH TIME ZONE NOT NULL
);

### PDF_FAQ_TABLE

CREATE TABLE IF NOT EXISTS {PDF_FAQ_TABLE} (
id UUID PRIMARY KEY,
document_table_id UUID NOT NULL REFERENCES {DOCUMENT_TABLE}(id),
document_page INTEGER NOT NULL,
faq_no SMALLINT NOT NULL,
page_text TEXT NOT NULL,
embedding VECTOR(3072) NOT NULL,
created_date_time TIMESTAMP WITH TIME ZONE NOT NULL
);

### HNSW インデックスの作成

CREATE INDEX IF NOT EXISTS {PDF_MANUAL_TABLE}\_embedding_idx ON {PDF_MANUAL_TABLE}
USING hnsw((embedding::halfvec(3072)) halfvec_ip_ops)
WITH (m = {HNSW_M}, ef_construction = {HNSW_EF_CONSTRUCTION});

CREATE INDEX IF NOT EXISTS {PDF_FAQ_TABLE}\_embedding_idx ON {PDF_FAQ_TABLE}
USING hnsw((embedding::halfvec(3072)) halfvec_ip_ops)
WITH (m = {HNSW_M}, ef_construction = {HNSW_EF_CONSTRUCTION});
