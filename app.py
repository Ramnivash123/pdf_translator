# pdf_translate_deep.py
import time
import math
from concurrent.futures import ThreadPoolExecutor, as_completed

import fitz  # PyMuPDF
from deep_translator import GoogleTranslator

# -----------------------------
# Step 1: Extract text blocks
# -----------------------------
def extract_blocks_from_pdf(pdf_path):
    """Extract text blocks per page with coordinates."""
    doc = fitz.open(pdf_path)
    pages_blocks = []

    for page in doc:
        blocks = page.get_text("blocks")
        page_blocks = []
        for block in blocks:
            # block format: (x0, y0, x1, y1, "text", block_no, block_type, ...)
            if len(block) < 5:
                continue
            x0, y0, x1, y1, text = block[:5]
            if text and str(text).strip():
                page_blocks.append({
                    "x0": x0, "y0": y0, "x1": x1, "y1": y1,
                    "text": str(text).strip()
                })
        pages_blocks.append(page_blocks)

    doc.close()
    return pages_blocks


# -----------------------------
# Helper: translate single block with retry/backoff
# -----------------------------
def translate_with_retry(text, src="fr", dest="en", retries=3, sleep_between=0.5):
    if not text:
        return ""
    if not isinstance(text, str):
        text = str(text)

    for attempt in range(1, retries + 1):
        try:
            translator = GoogleTranslator(source=src, target=dest)
            translated = translator.translate(text)
            if not translated:  # sometimes returns None
                return text
            return translated
        except Exception as e:
            if attempt == retries:
                print(f"   ⚠️ translate error (give up): {e}")
                return text
            else:
                backoff = sleep_between * (2 ** (attempt - 1))
                print(f"   ⚠️ translate error (attempt {attempt}) - retrying in {backoff:.1f}s: {e}")
                time.sleep(backoff)
    return text


# -----------------------------
# Step 2: Translate all blocks (concurrent)
# -----------------------------
def translate_blocks_deep(pages_blocks, src="fr", dest="en", workers=4, pause_between_calls=0.02):
    """Translate all text blocks using deep-translator concurrently."""
    tasks = []
    for p_idx, page_blocks in enumerate(pages_blocks):
        for b_idx, block in enumerate(page_blocks):
            tasks.append((p_idx, b_idx, block["text"]))

    translated_map = {}

    def worker(task):
        p_idx, b_idx, text = task
        if pause_between_calls:
            time.sleep(pause_between_calls)
        translated = translate_with_retry(text, src=src, dest=dest)
        return (p_idx, b_idx, translated)

    print(f"🔁 Submitting {len(tasks)} blocks for translation with {workers} workers...")
    with ThreadPoolExecutor(max_workers=workers) as exc:
        futures = {exc.submit(worker, t): t for t in tasks}
        completed = 0
        for fut in as_completed(futures):
            p_idx, b_idx, translated_text = fut.result()
            translated_map[(p_idx, b_idx)] = translated_text
            completed += 1
            if completed % 50 == 0 or completed == len(tasks):
                print(f"   ✅ Translated {completed}/{len(tasks)} blocks")

    translated_pages = []
    for p_idx, page_blocks in enumerate(pages_blocks):
        translated_page_blocks = []
        for b_idx, block in enumerate(page_blocks):
            new_text = translated_map.get((p_idx, b_idx), block["text"])
            translated_page_blocks.append({
                "x0": block["x0"],
                "y0": block["y0"],
                "x1": block["x1"],
                "y1": block["y1"],
                "text": new_text if new_text else ""
            })
        translated_pages.append(translated_page_blocks)

    return translated_pages


# -----------------------------
# Helper: insert textbox with font-fit
# -----------------------------
def insert_textbox_fitted(page, rect, text, fontname="helv",
                          initial_fontsize=10, min_fontsize=6,
                          line_spacing_mult=1.15):
    """Insert text, shrinking font if necessary to fit inside rect."""
    if not text:
        return
    if not isinstance(text, str):
        text = str(text)

    text = text.strip()
    if not text:
        return

    rect_w = rect.width
    rect_h = rect.height
    fontsize = initial_fontsize

    while fontsize >= min_fontsize:
        est_chars_per_line = max(20, int(rect_w / (fontsize * 0.5)))
        total_chars = len(text)
        estimated_lines = math.ceil(total_chars / est_chars_per_line)
        needed_height = estimated_lines * fontsize * line_spacing_mult

        if needed_height <= rect_h or fontsize == min_fontsize:
            try:
                page.insert_textbox(rect, text, fontsize=fontsize, fontname=fontname, align=0)
            except Exception:
                page.insert_textbox(rect, text, fontsize=min_fontsize, fontname=fontname, align=0)
            return
        else:
            fontsize -= 1

    page.insert_textbox(rect, text, fontsize=min_fontsize, fontname=fontname, align=0)


# -----------------------------
# Step 3: Replace translated blocks in the PDF
# -----------------------------
def replace_blocks_in_pdf(input_pdf, translated_pages, output_pdf):
    """Replace block texts in same positions while keeping layout/images."""
    doc = fitz.open(input_pdf)

    for page_num, page in enumerate(doc):
        if page_num >= len(translated_pages):
            continue
        for block in translated_pages[page_num]:
            rect = fitz.Rect(block["x0"], block["y0"], block["x1"], block["y1"])
            new_text = block["text"]

            inset = 0.5
            fill_rect = fitz.Rect(block["x0"] - inset, block["y0"] - inset,
                                  block["x1"] + inset, block["y1"] + inset)
            page.draw_rect(fill_rect, color=(1, 1, 1), fill=(1, 1, 1))

            insert_textbox_fitted(page, rect, new_text, initial_fontsize=10, min_fontsize=6)

    doc.save(output_pdf)
    doc.close()


# -----------------------------
# Step 4: Run Workflow
# -----------------------------
if __name__ == "__main__":
    input_pdf = "1_LATEST STRUCT UPTO (DIR S-03).pdf"
    output_pdf = "replaced_deep_translated.pdf"

    print("📄 Extracting text blocks...")
    pages_blocks = extract_blocks_from_pdf(input_pdf)
    total_blocks = sum(len(p) for p in pages_blocks)
    print(f"   → Found {len(pages_blocks)} pages and {total_blocks} text blocks")

    print("🌍 Translating blocks with deep-translator (Google)...")
    translated_pages = translate_blocks_deep(pages_blocks, src="fr", dest="en",
                                             workers=4, pause_between_calls=0.02)

    print("📝 Replacing text while preserving layout...")
    replace_blocks_in_pdf(input_pdf, translated_pages, output_pdf)

    print("✅ Done! File created:", output_pdf)
