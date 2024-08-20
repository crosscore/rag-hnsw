from pypdf import PdfReader, PdfWriter

input_pdf = "../../data/pdf/FAQ_収納.pdf"
output_pdf = "../../data/pdf/faq/3/FAQ_3.pdf"

reader = PdfReader(input_pdf)
writer = PdfWriter()

# nページ分の抽出
n = 0
for i in range(21, 27): # 開始ページ1, 終了ページ10
    page = reader.pages[i]  # iページ目を取得
    writer.add_page(page)
    n += 1

with open(output_pdf, "wb") as output_file:
    writer.write(output_file)

print(f"{output_pdf}に{n}ページ分のPDFを出力しました。")
