"""OCR extraction wrapper (Report 1, item 2).

Cheapest viable OCR -- Tesseract locally. Accuracy is not the bottleneck to
optimize yet; the loop working end-to-end is. See Report 4 SS3 for benchmark
context: template/layout-based approaches get 95%+ on structured documents,
which is the bar these 3 target formats should be able to hit.
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image

try:
    import pytesseract
except ImportError:  # pragma: no cover
    pytesseract = None


def extract_raw_text(image_path: str | Path) -> str:
    """Run OCR on a single document image and return raw text.

    Requires the `tesseract` binary to be installed and on PATH
    (`brew install tesseract` on macOS).
    """
    if pytesseract is None:
        raise RuntimeError("pytesseract is not installed")

    image = Image.open(image_path)
    return pytesseract.image_to_string(image)
