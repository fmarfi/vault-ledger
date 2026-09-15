"""OCR extraction wrapper (Report 1, item 2).

Cheapest viable OCR -- Tesseract locally. Accuracy is not the bottleneck to
optimize yet; the loop working end-to-end is. See Report 4 SS3 for benchmark
context: template/layout-based approaches get 95%+ on structured documents,
which is the bar these 3 target formats should be able to hit.
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageOps

try:
    import pytesseract
except ImportError:  # pragma: no cover
    pytesseract = None

# Tesseract needs roughly 300-DPI-equivalent text height to read reliably.
# A phone screenshot or a small web-saved image can come in well below that
# -- upscale anything with a short side under this before OCR. This recovers
# real text from small-but-legible images; it can't invent detail that
# genuinely isn't in the source pixels (e.g. a ~150px thumbnail).
MIN_SHORT_SIDE = 900


def _prepare_for_ocr(image: Image.Image) -> Image.Image:
    image = ImageOps.exif_transpose(image).convert("L")
    short_side = min(image.size)
    if short_side < MIN_SHORT_SIDE:
        scale = MIN_SHORT_SIDE / short_side
        image = image.resize(
            (round(image.width * scale), round(image.height * scale)), Image.LANCZOS
        )
    return ImageOps.autocontrast(image)


def extract_raw_text(image_path: str | Path) -> str:
    """Run OCR on a single document image and return raw text.

    Requires the `tesseract` binary to be installed and on PATH
    (`brew install tesseract` on macOS).
    """
    if pytesseract is None:
        raise RuntimeError("pytesseract is not installed")

    image = _prepare_for_ocr(Image.open(image_path))
    return pytesseract.image_to_string(image)
