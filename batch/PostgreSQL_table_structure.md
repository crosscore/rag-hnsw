# PostgreSQLテーブル構造

## 注意事項:

1. すべてのテーブル名は config.py から読み込まれる大文字の変数です。
2. すべてのカラム名は小文字で設定されます。
3. すべての日時はAsia/Tokyo（日本時間）のタイムゾーンで保存されます。
4. SMALLINT は PostgreSQL では int2 と同等です。
5. INTEGER は PostgreSQL では int4 と同等です。
6. vector(3072)データ型はpgvector拡張機能を使用しています。Dockerfileの設定により、事前にauroraコンテナのPostgreSQLにpgvector拡張機能がインストールされています。
7. MANUAL_TABLEとFAQ_TABLEのembeddingカラムにはHNSWインデックスが作成されます。これはpgvector拡張機能によって提供される近似最近傍探索インデックスです。
8. すべての外部キー（pdf_table_id）はPDF_TABLEのidカラムを参照しています。
9. CHUNK_SIZEとCHUNK_OVERLAPの設定：
   - CHUNK_SIZE: 1000文字
   - CHUNK_OVERLAP: 0文字
   - これらの値はconfig.pyで設定されています。
10. HNSWインデックスの設定：
    - m: 16
    - ef_construction: 256
    - ef_search: 500
    - これらの値はconfig.pyで設定されています。
11. MANUAL_TABLEとFAQ_TABLEのpdf_table_idカラムにUNIQUE制約は指定されていません。
12. PDF_CATEGORY_TABLEのpdf_table_idはUNIQUEであるべきではありません。
13. TOC_TABLEはベクトル化しないため、HNSWインデックスは不要です。
14. テーブル名はconfig.pyから読み込むことを想定しています。

## PDF_TABLE (PDF情報テーブル):

- id (Primary Key): uuid, NOT NULL, UUID v4によるランダム値
- file_path: varchar(1024), NOT NULL, PDFのフルパス
- file_name: varchar(1024), NOT NULL, PDFのファイル名
- document_type: SMALLINT, NOT NULL, ドキュメントの種類 (1: manual, 2: faq)
- checksum: varchar(64), NOT NULL, PDFのSHA256ハッシュ値
- created_date_time: timestamp with time zone, NOT NULL, レコード作成日時

## PDF_CATEGORY_TABLE (PDFとカテゴリの関係テーブル):

- id (Primary Key): uuid, NOT NULL, UUID v4によるランダム値
- pdf_table_id (Foreign Key): uuid, NOT NULL, PDF_TABLEのidカラムを参照
- business_category: SMALLINT, NOT NULL, 業務カテゴリ (1: 新契約, 2: 収納, 3: 保全, 4: 保険金, 5: 商品, 6: MSA ケア, 7: 手数料, 8: 代理店制度, 9: 職域推進, 10: 人事, 11: 会計)
- created_date_time: timestamp with time zone, NOT NULL, レコード作成日時

## TOC_TABLE (XLSX目次情報テーブル)

- id (Primary Key): uuid, NOT NULL, UUID v4によるランダム値
- pdf_table_id (Foreign Key): uuid, NOT NULL, PDF_TABLEのidカラムを参照
- toc_data: text, NOT NULL, XLSXファイルの1シート分を「","区切りのCSV形式」でテキスト化し、行単位で改行された内容
- checksum: varchar(64), NOT NULL, XLSXファイルのSHA256ハッシュ値
- created_date_time: timestamp with time zone, NOT NULL, レコード作成日時

## MANUAL_TABLE (PDFマニュアル情報テーブル)

- id (Primary Key): uuid, NOT NULL, UUID v4によるランダム値
- pdf_table_id (Foreign Key): uuid, NOT NULL, PDF_TABLEのidカラムを参照
- chunk_no: INTEGER, NOT NULL, PDFのテキストをページ毎かつCHUNK_SIZE毎に分割したチャンクの連番 (開始番号: 1)
- document_page: SMALLINT, NOT NULL, チャンクの存在するPDFのページ番号 (開始番号: 1)
- chunk_text: text, NOT NULL, チャンク毎のテキスト
- embedding: vector(3072), NOT NULL, chunk_textのベクトルデータ
- created_date_time: timestamp with time zone, NOT NULL, レコード作成日時

## FAQ_TABLE (PDFマニュアル情報テーブル)

- id (Primary Key): uuid, NOT NULL, UUID v4によるランダム値
- pdf_table_id (Foreign Key): uuid, NOT NULL, PDF_TABLEのidカラムを参照
- document_page: INTEGER, NOT NULL, PDFのページ番号 (開始番号: 1)
- faq_no: SMALLINT, NOT NULL, ページ毎のFAQ番号 (preprocess_faq_text関数が返却するfaq_noの数値)
- page_text: text, NOT NULL, ページ毎のテキスト (preprocess_faq_text関数が返却するprocessed_textの文字列)
- embedding: vector(3072), NOT NULL, page_textのベクトルデータ
- created_date_time: timestamp with time zone, NOT NULL, レコード作成日時

## テーブル作成クエリ
### pgvector拡張機能のインストール
CREATE EXTENSION IF NOT EXISTS vector;

### PDF_TABLE
CREATE TABLE IF NOT EXISTS {PDF_TABLE} (
    id UUID PRIMARY KEY,
    file_path VARCHAR(1024) NOT NULL,
    file_name VARCHAR(1024) NOT NULL,
    document_type SMALLINT NOT NULL,
    checksum VARCHAR(64) NOT NULL,
    created_date_time TIMESTAMP WITH TIME ZONE NOT NULL
);

### PDF_CATEGORY_TABLE
CREATE TABLE IF NOT EXISTS {PDF_CATEGORY_TABLE} (
    id UUID PRIMARY KEY,
    pdf_table_id UUID NOT NULL REFERENCES {PDF_TABLE}(id),
    business_category SMALLINT NOT NULL,
    created_date_time TIMESTAMP WITH TIME ZONE NOT NULL
);

### TOC_TABLE
CREATE TABLE IF NOT EXISTS {TOC_TABLE} (
    id UUID PRIMARY KEY,
    pdf_table_id UUID NOT NULL REFERENCES {PDF_TABLE}(id),
    toc_data TEXT NOT NULL,
    checksum VARCHAR(64) NOT NULL,
    created_date_time TIMESTAMP WITH TIME ZONE NOT NULL
);

### MANUAL_TABLE
CREATE TABLE IF NOT EXISTS {MANUAL_TABLE} (
    id UUID PRIMARY KEY,
    pdf_table_id UUID NOT NULL REFERENCES {PDF_TABLE}(id),
    chunk_no INTEGER NOT NULL,
    document_page SMALLINT NOT NULL,
    chunk_text TEXT NOT NULL,
    embedding VECTOR(3072) NOT NULL,
    created_date_time TIMESTAMP WITH TIME ZONE NOT NULL
);

### FAQ_TABLE
CREATE TABLE IF NOT EXISTS {FAQ_TABLE} (
    id UUID PRIMARY KEY,
    pdf_table_id UUID NOT NULL REFERENCES {PDF_TABLE}(id),
    document_page INTEGER NOT NULL,
    faq_no SMALLINT NOT NULL,
    page_text TEXT NOT NULL,
    embedding VECTOR(3072) NOT NULL,
    created_date_time TIMESTAMP WITH TIME ZONE NOT NULL
);

### HNSWインデックスの作成
CREATE INDEX IF NOT EXISTS {MANUAL_TABLE}_embedding_idx ON {MANUAL_TABLE}
USING hnsw((embedding::halfvec(3072)) halfvec_ip_ops)
WITH (m = {HNSW_M}, ef_construction = {HNSW_EF_CONSTRUCTION});

CREATE INDEX IF NOT EXISTS {FAQ_TABLE}_embedding_idx ON {FAQ_TABLE}
USING hnsw((embedding::halfvec(3072)) halfvec_ip_ops)
WITH (m = {HNSW_M}, ef_construction = {HNSW_EF_CONSTRUCTION});
