import pdfplumber
from googletrans import Translator
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
import textwrap
import fitz  # PyMuPDF

# -----------------------------
# Step 1: Extract text per page
# -----------------------------
def extract_text_from_pdf(pdf_path):
    text = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                text.append(page_text)
    return text   # list of page strings

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
# Step 3a: Page-level translation
# -----------------------------
def translate_pages(text_list, src='fr', dest='en'):
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
# Step 3b: Block-level translation
# -----------------------------
def translate_blocks(blocks, src='fr', dest='en'):
    translator = Translator()
    translated_blocks = []
    for b in blocks:
        text = b[4].strip()
        if text:
            try:
                translated = translator.translate(text, src=src, dest=dest).text
            except Exception:
                translated = text  # fallback
        else:
            translated = ""
        translated_blocks.append((b[:4], translated))
    return translated_blocks

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
def replace_text_in_pdf(input_pdf, output_pdf, src='fr', dest='en'):
    doc = fitz.open(input_pdf)

    for page in doc:
        blocks = page.get_text("blocks")  # [(x0,y0,x1,y1,text,...)]
        translated_blocks = translate_blocks(blocks, src, dest)

        for rect_coords, translated_text in translated_blocks:
            rect = fitz.Rect(rect_coords)
            # Cover old text with white rectangle
            page.draw_rect(rect, color=(1,1,1), fill=(1,1,1))
            # Insert translated text
            page.insert_textbox(rect, translated_text,
                                fontsize=9, fontname="helv", align=0)

    doc.save(output_pdf)
    doc.close()

# -----------------------------
# Step 6: Run workflow
# -----------------------------
input_pdf = "1_LATEST STRUCT UPTO (DIR S-03).pdf"
output_pdf = "english_document.pdf"  # plain translated text
replaced_pdf = "replaced.pdf"        # layout-preserved translation

print("Extracting text...")
pages_text = extract_text_from_pdf(input_pdf)

print("Translating full pages...")
translated_pages = translate_pages(pages_text)

print("Saving translated-only PDF...")
save_text_to_pdf(translated_pages, output_pdf)

print("Replacing text in original layout...")
replace_text_in_pdf(input_pdf, replaced_pdf)

print("Done! Files created:")
print(" - English translation PDF:", output_pdf)
print(" - Layout-preserved replaced PDF:", replaced_pdf)
