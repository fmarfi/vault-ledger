"""PDF extraction: native text layer first, rasterize + OCR as fallback.

First page only -- matches the 3 target formats (invoice/utility bill/
receipt), which are virtually always single-page. Multi-page PDFs are out
of scope for now; only the first page is read.

Deliberately local-only: no hosted Document AI API (AWS Textract / Google
Document AI / Azure Document Intelligence). Researched and rejected for
privacy reasons -- by default those services use customer content to
improve/train their models unless you explicitly opt out, and even opted
out, the document still leaves the machine and is processed by a third
party. Do not add a hosted OCR call here without revisiting that decision
with the user; see the vault-ledger-ocr-extraction skill.

Uses pypdfium2 (Apache-2.0/BSD, Google's PDFium/Chromium bindings) for both
native text extraction and rasterization -- one dependency for both paths.
Deliberately NOT PyMuPDF/fitz (AGPL-3.0 -- would require a paid commercial
license for a closed-source SaaS product) and NOT pdfplumber (pulls in
pdfminer.six -> cryptography, which has no prebuilt wheel for this
environment and fails to build from source; not worth fighting for a
feature -- encrypted-PDF support -- this product doesn't need).
"""

from __future__ import annotations

from pathlib import Path

import pypdfium2 as pdfium

from vault_ledger.extraction.ocr import ocr_image

# A scanned PDF's page typically extracts to "" or a handful of stray
# characters from embedded metadata/artifacts. This threshold just needs to
# separate "no real text layer" from "there's an actual line of text" --
# it doesn't need to be precise.
MIN_NATIVE_TEXT_CHARS = 20

RASTERIZE_SCALE = 200 / 72  # ~200 DPI: enough for Tesseract, ~55% fewer pixels than 300


def _native_text_sufficient(text: str) -> bool:
    return len(text.strip()) >= MIN_NATIVE_TEXT_CHARS


def extract_pdf_text(pdf_path: str | Path) -> str:
    document = pdfium.PdfDocument(pdf_path)
    try:
        page = document[0]

        text_page = page.get_textpage()
        try:
            native_text = text_page.get_text_range()
        finally:
            text_page.close()

        if _native_text_sufficient(native_text):
            return native_text

        image = page.render(scale=RASTERIZE_SCALE).to_pil()
    finally:
        document.close()

    return ocr_image(image)
