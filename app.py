import pdfplumber
from googletrans import Translator
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
import textwrap
import fitz  # PyMuPDF

# -----------------------------
# Step 1: Extract text from PDF
# -----------------------------
def extract_text_from_pdf(pdf_path):
    text = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                text.append(page_text)
    return text

# -----------------------------
# Step 2: Split text into smaller chunks
# -----------------------------
def chunk_text(text, max_chars=4000):
    chunks = []
    while len(text) > max_chars:
        split_at = text.rfind(".", 0, max_chars)
        if split_at == -1:
            split_at = max_chars
        chunks.append(text[:split_at+1])
        text = text[split_at+1:]
    chunks.append(text)
    return chunks

# -----------------------------
# Step 3: Translate text
# -----------------------------
def translate_text(text_list, src='fr', dest='en'):
    translator = Translator()
    translated_pages = []

    for page_text in text_list:
        chunks = chunk_text(page_text)
        translated_chunks = []
        for chunk in chunks:
            translation = translator.translate(chunk, src=src, dest=dest)
            translated_chunks.append(translation.text)
        translated_pages.append(" ".join(translated_chunks))
    return translated_pages

# -----------------------------
# Step 4: Save translated text to NEW PDF
# -----------------------------
def save_text_to_pdf(translated_pages, output_pdf):
    c = canvas.Canvas(output_pdf, pagesize=letter)
    width, height = letter
    margin = 40
    for page_text in translated_pages:
        wrapped_text = textwrap.wrap(page_text, width=100)
        y = height - margin
        for line in wrapped_text:
            c.drawString(margin, y, line)
            y -= 14
            if y < margin:
                c.showPage()
                y = height - margin
        c.showPage()
    c.save()

# -----------------------------
# Step 5: Replace text in original layout
# -----------------------------
def replace_text_in_pdf(input_pdf, translated_pages, output_pdf):
    doc = fitz.open(input_pdf)
    for page_num, page in enumerate(doc):
        if page_num < len(translated_pages):
            page_text = translated_pages[page_num]
            # Remove old text visually
            page.clean_contents()
            # Write translated text over original
            rect = page.rect
            page.insert_textbox(rect, page_text, fontsize=10, fontname="helv")
    doc.save(output_pdf)

# -----------------------------
# Step 6: Run workflow
# -----------------------------
input_pdf = "1_LATEST STRUCT UPTO (DIR S-03).pdf"
output_pdf = "english_document.pdf"
replaced_pdf = "replaced.pdf"

print("Extracting text...")
pages_text = extract_text_from_pdf(input_pdf)

print("Translating (this may take a while)...")
translated_pages = translate_text(pages_text)

print("Saving translated-only PDF...")
save_text_to_pdf(translated_pages, output_pdf)

print("Replacing text in original layout...")
replace_text_in_pdf(input_pdf, translated_pages, replaced_pdf)

print("Done! Files created:")
print(" - English translation PDF:", output_pdf)
print(" - Layout-preserved replaced PDF:", replaced_pdf)
