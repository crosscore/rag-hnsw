## PDF_TABLE (PDF情報テーブル):
- id (Primary Key): uuid, NOT NULL, UUIDバージョン4によるランダム値
- folder_name: varchar(1024), NOT NULL, PDFのフルパスからファイル名を除いたパス
- file_name: varchar(1024), NOT NULL, PDFのファイル名
- document_type: int2, NOT NULL, ドキュメントの種類 (1: manual, 2: faq)
- checksum: varchar(64), NOT NULL, PDFファイルのSHA256ハッシュ値
- created_date_time: timestamptz, レコード作成日時 (タイムゾーン付き)

## PDF_CATEGORY_TABLE (PDFとカテゴリの関係テーブル):
- id (Primary Key): uuid, NOT NULL, UUIDバージョン4によるランダム値
- pdf_table_id (Foreign Key): uuid, NOT NULL, PDF_TABLEのidカラムを参照
- business_category: int2, NOT NULL, 業務カテゴリ (例: 1: 新契約, 2: 収納, 3: 保全, 4: 保険金, 5: 商品, 6: MSAケア, 7: 手数料, 8: 代理店制度, 9: 職域推進, 10: 人事, 11: 会計)
- created_date_time: timestamptz, NOT NULL, レコード作成日時 (タイムゾーン付き)

## TOC_TABLE　（EXCEL目次情報テーブル）
- id (Primary Key): uuid, NOT NULL, UUIDバージョン4によるランダム値
- pdf_table_id (Foreign Key): uuid, NOT NULL, PDF_TABLEのidカラムを参照
- toc_data: varchar(1024), NOT NULL, XLSXファイルの1シート分をテキスト化した内容
- checksum: varchar(64), NOT NULL, XLSXファイルのSHA256ハッシュ値
- created_date_time: timestamptz, レコード作成日時 (タイムゾーン付き)

## MANUAL_TABLE (PDFマニュアル情報テーブル)
- id (Primary Key): uuid, NOT NULL, UUIDバージョン4によるランダム値
- pdf_table_id (Foreign Key, Unique): uuid, NOT NULL, PDF_TABLEのidカラムを参照
- chunk_no: int4, NOT NULL, PDFのテキストをページ毎かつチャンクサイズ毎に分割したチャンクの連番 (開始番号: 1)
- document_page: int2, NOT NULL, チャンクの存在するPDFのページ番号 (開始番号: 1)
- chunk_text: text, NOT NULL, チャンク毎のテキスト
- embedding: vector(3072), NOT NULL, chunk_textのベクトルデータ
- created_date_time: timestamptz, NOT NULL, レコード作成日時 (タイムゾーン付き)

## FAQ_TABLE (PDFマニュアル情報テーブル)
- id (Primary Key): uuid, NOT NULL, UUIDバージョン4によるランダム値
- pdf_table_id (Foreign Key, Unique): uuid, NOT NULL, PDF_TABLEのidカラムを参照
- document_page: int4, NOT NULL, PDFのページ番号 (開始番号: 1)
- page_text: text, NOT NULL, ページ毎のテキスト (テキスト内容はpreprocess_faq_text関数によって前処理)
- embedding: vector(3072), NOT NULL, page_textのベクトルデータ
- created_date_time: timestamptz, NOT NULL, レコード作成日時 (タイムゾーン付き)



# 全テーブル作成クエリまとめ
```
CREATE TABLE PDF_TABLE (
    id uuid PRIMARY KEY NOT NULL,
    folder_name varchar(1024) NOT NULL,
    file_name varchar(1024) NOT NULL,
    document_type int2 NOT NULL,
    checksum varchar(64) NOT NULL,
    created_date_time timestamptz
);

CREATE TABLE PDF_CATEGORY_TABLE (
    id uuid PRIMARY KEY NOT NULL,
    pdf_table_id uuid NOT NULL REFERENCES PDF_TABLE(id),
    business_category int2 NOT NULL,
    created_date_time timestamptz NOT NULL
);

CREATE TABLE TOC_TABLE (
    id uuid PRIMARY KEY NOT NULL,
    pdf_table_id uuid NOT NULL REFERENCES PDF_TABLE(id),
    toc_data varchar(1024) NOT NULL,
    checksum varchar(64) NOT NULL,
    created_date_time timestamptz
);

CREATE TABLE MANUAL_TABLE (
    id uuid PRIMARY KEY NOT NULL,
    pdf_table_id uuid NOT NULL REFERENCES PDF_TABLE(id),
    chunk_no int4 NOT NULL,
    document_page int2 NOT NULL,
    chunk_text text NOT NULL,
    embedding vector(3072) NOT NULL,
    created_date_time timestamptz NOT NULL
);

CREATE TABLE FAQ_TABLE (
    id uuid PRIMARY KEY NOT NULL,
    pdf_table_id uuid NOT NULL REFERENCES PDF_TABLE(id),
    document_page int4 NOT NULL,
    page_text text NOT NULL,
    embedding vector(3072) NOT NULL,
    created_date_time timestamptz NOT NULL
);
```
