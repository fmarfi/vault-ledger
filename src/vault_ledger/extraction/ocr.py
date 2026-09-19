"""OCR extraction wrapper (Report 1, item 2).

Cheapest viable OCR -- Tesseract locally. Accuracy is not the bottleneck to
optimize yet; the loop working end-to-end is. See Report 4 SS3 for benchmark
context: template/layout-based approaches get 95%+ on structured documents,
which is the bar these 3 target formats should be able to hit.
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path

from PIL import Image, ImageOps

# Tesseract needs roughly 300-DPI-equivalent text height to read reliably.
# A phone screenshot or a small web-saved image can come in well below that
# -- upscale anything with a short side under this before OCR. This recovers
# real text from small-but-legible images; it can't invent detail that
# genuinely isn't in the source pixels (e.g. a ~150px thumbnail).
MIN_SHORT_SIDE = 900


_WINDOWS_TESSERACT_DEFAULTS = (
    r"C:\Program Files\Tesseract-OCR\tesseract.exe",
    r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
)


def find_tesseract() -> str | None:
    """Locate the tesseract binary on macOS/Linux/Windows.

    Order: TESSERACT_CMD env var, PATH, then the default Windows installer
    locations (the Windows installer does not add itself to PATH).
    """
    override = os.environ.get("TESSERACT_CMD")
    if override and Path(override).exists():
        return override
    on_path = shutil.which("tesseract")
    if on_path:
        return on_path
    for candidate in _WINDOWS_TESSERACT_DEFAULTS:
        if Path(candidate).exists():
            return candidate
    return None


def _prepare_for_ocr(image: Image.Image) -> Image.Image:
    image = ImageOps.exif_transpose(image).convert("L")
    short_side = min(image.size)
    if short_side < MIN_SHORT_SIDE:
        scale = MIN_SHORT_SIDE / short_side
        image = image.resize(
            (round(image.width * scale), round(image.height * scale)), Image.LANCZOS
        )
    return ImageOps.autocontrast(image)


def ocr_image(image: Image.Image) -> str:
    """Run OCR on an already-loaded PIL image. Shared with the PDF
    scanned-page fallback (`extraction/pdf.py`) so both paths get the same
    upscale/contrast preprocessing.
    """
    # Lazy: pytesseract eagerly imports pandas, which native-text PDFs
    # (no OCR) shouldn't have to pay for.
    try:
        import pytesseract
    except ImportError:  # pragma: no cover
        raise RuntimeError("pytesseract is not installed") from None

    binary = find_tesseract()
    if binary is None:
        raise RuntimeError(
            "tesseract binary not found. Install it (macOS: `brew install tesseract`; "
            "Windows: the UB Mannheim installer) or set TESSERACT_CMD to its path."
        )
    pytesseract.pytesseract.tesseract_cmd = binary
    return pytesseract.image_to_string(_prepare_for_ocr(image))


def extract_raw_text(document_path: str | Path) -> str:
    """Run OCR on a single document (image or PDF) and return raw text.

    PDFs are routed to `extraction.pdf.extract_pdf_text`, which prefers a
    native text layer and only falls back to rasterize + OCR for scanned
    PDFs -- see that module for details. Requires the `tesseract` binary to
    be installed and on PATH (`brew install tesseract` on macOS).
    """
    document_path = Path(document_path)
    if document_path.suffix.lower() == ".pdf":
        from vault_ledger.extraction.pdf import extract_pdf_text

        return extract_pdf_text(document_path)

    return ocr_image(Image.open(document_path))
