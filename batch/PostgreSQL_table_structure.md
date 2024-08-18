# PostgreSQLテーブル構造

## 注意事項:

1. すべてのテーブル名は config.py から読み込まれる大文字の変数です。
2. すべてのカラム名は小文字で設定されます。
3. すべての日時はAsia/Tokyo（日本時間）のタイムゾーンで保存されます。
4. SMALLINT は PostgreSQL では int2 と同等です。
5. INTEGER は PostgreSQL では int4 と同等です。
6. vector(3072)データ型はpgvector拡張機能を使用しています。Dockerfileの設定により、事前にauroraコンテナのPostgreSQLにpgvector拡張機能がインストールされています。
7. PDF_MANUAL_TABLEとPDF_FAQ_TABLEのembeddingカラムにはHNSWインデックスが作成されます。これはpgvector拡張機能によって提供される近似最近傍探索インデックスです。
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
11. PDF_CATEGORY_TABLEのpdf_table_idはUNIQUEであるべきではありません。
12. XLSX_TOC_TABLEはベクトル化しないため、HNSWインデックスは不要です。
13. テーブル名はconfig.pyから読み込みます。
14. この構造では、1つのPDFファイルを複数のカテゴリに関連付けることができます。例えば、"/app/data/pdf/manual/category1/test.pdf"と"/app/data/pdf/manual/category2/test.pdf"のように、同じファイル名のPDFが複数のカテゴリに属する場合があります。
15. XLSX_TOC_TABLEは、PDF_TABLEに保存されるPDF毎に存在する目次データを格納します。
16. PDFとXLSXファイルの関連付けは、business_categoryでフィルタリングした後、file_name（拡張子を除く）で行います。
17. file_nameカラムには、PDFファイル名から拡張子を除いた形式で保存します。この情報は、PDFとXLSXファイルのペアを見つけるために重要です。
18. file_nameには拡張子を含めません。拡張子を含むファイル名が必要な場合は、file_pathから取得できます。
19. PDF_TABLEからfolder_nameカラムは削除されました。
20. csv_to_aurora.pyとtoc_to_aurora.pyの両方で、PDFとXLSXファイルの関連付けのロジックを実装する必要があります。
21. HNSWインデックスの作成はPDF_MANUAL_TABLEとPDF_FAQ_TABLEの両方に必要です。toc_to_aurora.pyではベクトル化を行わないため、HNSWインデックスの作成は不要です。

## PDFとXLSXの関連付けクエリ例
```sql
SELECT p.*, x.*
FROM PDF_TABLE p
JOIN PDF_CATEGORY_TABLE c ON p.id = c.pdf_table_id
JOIN XLSX_TOC_TABLE x ON p.id = x.pdf_table_id
WHERE c.business_category = [指定のカテゴリ]
  AND p.file_name = x.file_name;
```

## PDF_TABLE (PDF情報テーブル):

- id (Primary Key): uuid, NOT NULL, UUID v4によるランダム値
- file_path: varchar(1024) NOT NULL, PDFのフルパス
- file_name: varchar(1024) NOT NULL, PDFのファイル名（拡張子を除く）
- document_type: SMALLINT NOT NULL, ドキュメントの種類 (1: manual, 2: faq)
- checksum: varchar(64) NOT NULL, PDFのSHA256ハッシュ値
- created_date_time: timestamp with time zone NOT NULL, レコード作成日時
- UNIQUE(file_path)

## PDF_CATEGORY_TABLE (PDFとカテゴリの関係テーブル):

- id (Primary Key): uuid NOT NULL, UUID v4によるランダム値
- pdf_table_id (Foreign Key): uuid NOT NULL, PDF_TABLEのidカラムを参照
- business_category: SMALLINT NOT NULL, 業務カテゴリ (1: 新契約, 2: 収納, 3: 保全, 4: 保険金, 5: 商品, 6: MSA ケア, 7: 手数料, 8: 代理店制度, 9: 職域推進, 10: 人事, 11: 会計)
- created_date_time: timestamp with time zone NOT NULL, レコード作成日時
- UNIQUE(pdf_table_id, business_category)

## XLSX_TOC_TABLE (XLSX目次情報テーブル)

- id (Primary Key): uuid NOT NULL, UUID v4によるランダム値
- pdf_table_id (Foreign Key): uuid NOT NULL, PDF_TABLEのidカラムを参照
- file_name: varchar(1024) NOT NULL, XLSXのファイル名（拡張子を除く）
- toc_data: text NOT NULL, XLSXファイルの1シート分を「","区切りのCSV形式」でテキスト化し、行単位で改行された内容
- checksum: varchar(64) NOT NULL, XLSXファイルのSHA256ハッシュ値
- created_date_time: timestamp with time zone NOT NULL, レコード作成日時
- UNIQUE(pdf_table_id, file_name)

## PDF_MANUAL_TABLE (PDFマニュアル情報テーブル)

- id (Primary Key): uuid NOT NULL, UUID v4によるランダム値
- pdf_table_id (Foreign Key): uuid NOT NULL, PDF_TABLEのidカラムを参照
- chunk_no: INTEGER NOT NULL, PDFのテキストをページ毎かつCHUNK_SIZE毎に分割したチャンクの連番 (開始番号: 1)
- document_page: SMALLINT NOT NULL, チャンクの存在するPDFのページ番号 (開始番号: 1)
- chunk_text: text NOT NULL, チャンク毎のテキスト
- embedding: vector(3072) NOT NULL, chunk_textのベクトルデータ
- created_date_time: timestamp with time zone NOT NULL, レコード作成日時

## PDF_FAQ_TABLE (PDFマニュアル情報テーブル)

- id (Primary Key): uuid NOT NULL, UUID v4によるランダム値
- pdf_table_id (Foreign Key): uuid NOT NULL, PDF_TABLEのidカラムを参照
- document_page: INTEGER NOT NULL, PDFのページ番号 (開始番号: 1)
- faq_no: SMALLINT NOT NULL, ページ毎のFAQ番号 (preprocess_faq_text関数が返却するfaq_noの数値)
- page_text: text NOT NULL, ページ毎のテキスト (preprocess_faq_text関数が返却するprocessed_textの文字列)
- embedding: vector(3072) NOT NULL, page_textのベクトルデータ
- created_date_time: timestamp with time zone NOT NULL, レコード作成日時

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
    created_date_time TIMESTAMP WITH TIME ZONE NOT NULL,
    UNIQUE(file_path)
);

### PDF_CATEGORY_TABLE
CREATE TABLE IF NOT EXISTS {PDF_CATEGORY_TABLE} (
    id UUID PRIMARY KEY,
    pdf_table_id UUID NOT NULL REFERENCES {PDF_TABLE}(id),
    business_category SMALLINT NOT NULL,
    created_date_time TIMESTAMP WITH TIME ZONE NOT NULL,
    UNIQUE(pdf_table_id, business_category)
);

### XLSX_TOC_TABLE
CREATE TABLE IF NOT EXISTS {XLSX_TOC_TABLE} (
    id UUID PRIMARY KEY,
    pdf_table_id UUID NOT NULL REFERENCES {PDF_TABLE}(id),
    file_name VARCHAR(1024) NOT NULL,
    toc_data TEXT NOT NULL,
    checksum VARCHAR(64) NOT NULL,
    created_date_time TIMESTAMP WITH TIME ZONE NOT NULL,
    UNIQUE(pdf_table_id, file_name)
);

### PDF_MANUAL_TABLE
CREATE TABLE IF NOT EXISTS {PDF_MANUAL_TABLE} (
    id UUID PRIMARY KEY,
    pdf_table_id UUID NOT NULL REFERENCES {PDF_TABLE}(id),
    chunk_no INTEGER NOT NULL,
    document_page SMALLINT NOT NULL,
    chunk_text TEXT NOT NULL,
    embedding VECTOR(3072) NOT NULL,
    created_date_time TIMESTAMP WITH TIME ZONE NOT NULL
);

### PDF_FAQ_TABLE
CREATE TABLE IF NOT EXISTS {PDF_FAQ_TABLE} (
    id UUID PRIMARY KEY,
    pdf_table_id UUID NOT NULL REFERENCES {PDF_TABLE}(id),
    document_page INTEGER NOT NULL,
    faq_no SMALLINT NOT NULL,
    page_text TEXT NOT NULL,
    embedding VECTOR(3072) NOT NULL,
    created_date_time TIMESTAMP WITH TIME ZONE NOT NULL
);

### HNSWインデックスの作成
CREATE INDEX IF NOT EXISTS {PDF_MANUAL_TABLE}_embedding_idx ON {PDF_MANUAL_TABLE}
USING hnsw((embedding::halfvec(3072)) halfvec_ip_ops)
WITH (m = {HNSW_M}, ef_construction = {HNSW_EF_CONSTRUCTION});

CREATE INDEX IF NOT EXISTS {PDF_FAQ_TABLE}_embedding_idx ON {PDF_FAQ_TABLE}
USING hnsw((embedding::halfvec(3072)) halfvec_ip_ops)
WITH (m = {HNSW_M}, ef_construction = {HNSW_EF_CONSTRUCTION});
