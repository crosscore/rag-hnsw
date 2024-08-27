from pypdf import PdfReader, PdfWriter

input_pdf = "../../data/pdf/input.pdf"
output_pdf = "../../data/pdf/faq/3/output.pdf"

reader = PdfReader(input_pdf)
writer = PdfWriter()

n = 0
for i in range(21, 27):
    page = reader.pages[i]
    writer.add_page(page)
    n += 1

with open(output_pdf, "wb") as output_file:
    writer.write(output_file)

print(f"{output_pdf}に{n}ページ分のPDFを出力しました。")
