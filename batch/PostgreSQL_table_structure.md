# PostgreSQLテーブル構造

注意:
- すべてのテーブル名とカラム名は小文字で設定されます。
- すべての日時はAsia/Tokyo（日本時間）のタイムゾーンで保存されます。

## pdf_table (PDF情報テーブル):

- id (Primary Key): uuid, NOT NULL, UUID v4によるランダム値
- file_path: varchar(1024), NOT NULL, PDFのフルパス
- file_name: varchar(1024), NOT NULL, PDFのファイル名
- document_type: int2, NOT NULL, ドキュメントの種類 (1: manual, 2: faq)
- checksum: varchar(64), NOT NULL, PDFのSHA256ハッシュ値
- created_date_time: timestamp with time zone, レコード作成日時

## pdf_category_table (PDFとカテゴリの関係テーブル):

- id (Primary Key): uuid, NOT NULL, UUID v4によるランダム値
- pdf_table_id (Foreign Key): uuid, NOT NULL, pdf_tableのidカラムを参照
- business_category: int2, NOT NULL, 業務カテゴリ (1: 新契約, 2: 収納, 3: 保全, 4: 保険金, 5: 商品, 6: MSA ケア, 7: 手数料, 8: 代理店制度, 9: 職域推進, 10: 人事, 11: 会計)
- created_date_time: timestamp with time zone, NOT NULL, レコード作成日時

## toc_table (XLSX目次情報テーブル)

- id (Primary Key): uuid, NOT NULL, UUID v4によるランダム値
- pdf_table_id (Foreign Key): uuid, NOT NULL, pdf_tableのidカラムを参照
- toc_data: text, NOT NULL, XLSXファイルの1シート分を「","区切りのCSV形式」でテキスト化し、行単位で改行された内容
- checksum: varchar(64), NOT NULL, XLSXファイルのSHA256ハッシュ値
- created_date_time: timestamp with time zone, レコード作成日時

## manual_table (PDFマニュアル情報テーブル)

- id (Primary Key): uuid, NOT NULL, UUID v4によるランダム値
- pdf_table_id (Foreign Key): uuid, NOT NULL, pdf_tableのidカラムを参照
- chunk_no: int4, NOT NULL, PDFのテキストをページ毎かつCHUNK_SIZE毎に分割したチャンクの連番 (開始番号: 1)
- document_page: int2, NOT NULL, チャンクの存在するPDFのページ番号 (開始番号: 1)
- chunk_text: text, NOT NULL, チャンク毎のテキスト
- embedding: vector(3072), NOT NULL, chunk_textのベクトルデータ
- created_date_time: timestamp with time zone, NOT NULL, レコード作成日時

## faq_table (PDFマニュアル情報テーブル)

- id (Primary Key): uuid, NOT NULL, UUID v4によるランダム値
- pdf_table_id (Foreign Key): uuid, NOT NULL, pdf_tableのidカラムを参照
- document_page: int4, NOT NULL, PDFのページ番号 (開始番号: 1)
- faq_no: int2, NOT NULL, ページ毎のFAQ番号 (preprocess_faq_text関数が返却するfaq_noの数値)
- page_text: text, NOT NULL, ページ毎のテキスト (preprocess_faq_text関数が返却するprocessed_textの文字列)
- embedding: vector(3072), NOT NULL, page_textのベクトルデータ
- created_date_time: timestamp with time zone, NOT NULL, レコード作成日時

注意事項:
1. vector(3072)データ型はpgvector拡張機能を使用しています。事前にPostgreSQLにpgvector拡張機能をインストールする必要があります。
2. manual_tableとfaq_tableのembeddingカラムにはHNSWインデックスが作成されます。これはpgvector拡張機能によって提供される高性能な近似最近傍探索インデックスです。
3. すべての外部キー（pdf_table_id）はpdf_tableのidカラムを参照しています。
4. CHUNK_SIZEとCHUNK_OVERLAPの設定：
   - CHUNK_SIZE: 1000文字
   - CHUNK_OVERLAP: 0文字
   - これらの値はconfig.pyで設定されています。
5. HNSWインデックスの設定：
   - m: 16
   - ef_construction: 256
   - ef_search: 500
   - これらの値はconfig.pyで設定されています。

## テーブル作成クエリ

```sql
-- pgvector拡張機能のインストール
CREATE EXTENSION IF NOT EXISTS vector;

-- pdf_table
CREATE TABLE IF NOT EXISTS pdf_table (
    id UUID PRIMARY KEY,
    file_path VARCHAR(1024) NOT NULL,
    file_name VARCHAR(1024) NOT NULL,
    document_type INT2 NOT NULL,
    checksum VARCHAR(64) NOT NULL,
    created_date_time TIMESTAMP WITH TIME ZONE
);

-- pdf_category_table
CREATE TABLE IF NOT EXISTS pdf_category_table (
    id UUID PRIMARY KEY,
    pdf_table_id UUID NOT NULL REFERENCES pdf_table(id),
    business_category INT2 NOT NULL,
    created_date_time TIMESTAMP WITH TIME ZONE NOT NULL
);

-- toc_table
CREATE TABLE IF NOT EXISTS toc_table (
    id UUID PRIMARY KEY,
    pdf_table_id UUID NOT NULL REFERENCES pdf_table(id),
    toc_data TEXT NOT NULL,
    checksum VARCHAR(64) NOT NULL,
    created_date_time TIMESTAMP WITH TIME ZONE
);

-- manual_table
CREATE TABLE IF NOT EXISTS manual_table (
    id UUID PRIMARY KEY,
    pdf_table_id UUID NOT NULL REFERENCES pdf_table(id),
    chunk_no INT4 NOT NULL,
    document_page INT2 NOT NULL,
    chunk_text TEXT NOT NULL,
    embedding VECTOR(3072) NOT NULL,
    created_date_time TIMESTAMP WITH TIME ZONE NOT NULL
);

-- faq_table
CREATE TABLE IF NOT EXISTS faq_table (
    id UUID PRIMARY KEY,
    pdf_table_id UUID NOT NULL REFERENCES pdf_table(id),
    document_page INT4 NOT NULL,
    faq_no INT2 NOT NULL,
    page_text TEXT NOT NULL,
    embedding VECTOR(3072) NOT NULL,
    created_date_time TIMESTAMP WITH TIME ZONE NOT NULL
);

-- HNSWインデックスの作成
CREATE INDEX IF NOT EXISTS manual_table_embedding_idx ON manual_table USING hnsw(embedding vector_ip_ops) WITH (m = 16, ef_construction = 256);
CREATE INDEX IF NOT EXISTS faq_table_embedding_idx ON faq_table USING hnsw(embedding vector_ip_ops) WITH (m = 16, ef_construction = 256);
