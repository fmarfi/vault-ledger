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

from PIL import Image, ImageFilter, ImageOps

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


# Language data: the app's own folder first (Program Files needs admin to add
# Dutch), else Tesseract's default. VAULT_TESSDATA_DIR overrides.
APP_TESSDATA = Path(__file__).resolve().parents[3] / "data" / "tessdata"
_lang_cache: dict[str, str] = {}


def _tessdata_dir() -> Path | None:
    override = os.environ.get("VAULT_TESSDATA_DIR")
    if override and Path(override).is_dir():
        return Path(override)
    return APP_TESSDATA if (APP_TESSDATA / "eng.traineddata").exists() else None


def _tesseract_config() -> str:
    """Point Tesseract at our language folder via TESSDATA_PREFIX (a quoted
    --tessdata-dir is mangled on Windows). Returns the cache key."""
    tessdata = _tessdata_dir()
    if tessdata:
        os.environ["TESSDATA_PREFIX"] = str(tessdata)
    return str(tessdata or "")


def _ocr_lang(pytesseract, config: str) -> str:
    """Dutch + English when Dutch data is installed; VAULT_OCR_LANG overrides."""
    if os.environ.get("VAULT_OCR_LANG"):
        return os.environ["VAULT_OCR_LANG"]
    if config not in _lang_cache:
        try:
            available = set(pytesseract.get_languages())
        except Exception:  # an old tesseract without --list-langs: play safe
            available = {"eng"}
        _lang_cache[config] = "nld+eng" if "nld" in available else "eng"
    return _lang_cache[config]


def _remove_shadows(image: Image.Image) -> Image.Image:
    """Divide by a heavily blurred copy: evens out shadows and uneven light
    (phone photos) while leaving the text strokes dark."""
    import numpy as np

    radius = max(image.size) / 40
    background = np.asarray(image.filter(ImageFilter.GaussianBlur(radius)), dtype=np.float32)
    pixels = np.asarray(image, dtype=np.float32)
    even = np.clip(pixels / np.maximum(background, 1.0) * 255.0, 0, 255).astype(np.uint8)
    return Image.fromarray(even, mode="L")


def _skew_angle(image: Image.Image, max_angle: float = 5.0, step: float = 0.25) -> float:
    """Small rotation (degrees) that makes text lines horizontal: the angle whose
    row-sum profile of dark pixels is sharpest. Measured on a small copy."""
    import numpy as np

    small = image.copy()
    small.thumbnail((800, 800))
    dark = np.asarray(small, dtype=np.uint8) < 128
    if dark.mean() < 0.002:  # (nearly) blank page
        return 0.0
    mask = Image.fromarray((dark * 255).astype(np.uint8), mode="L")
    best_angle, best_score = 0.0, -1.0
    for i in range(int(2 * max_angle / step) + 1):
        angle = -max_angle + i * step
        rows = np.asarray(mask.rotate(angle, resample=Image.NEAREST, expand=True), dtype=np.float32).sum(axis=1)
        score = float(np.sum(np.diff(rows) ** 2))
        if score > best_score:
            best_angle, best_score = angle, score
    return best_angle


def _prepare_for_ocr(image: Image.Image) -> Image.Image:
    image = ImageOps.exif_transpose(image).convert("L")
    short_side = min(image.size)
    if short_side < MIN_SHORT_SIDE:
        scale = MIN_SHORT_SIDE / short_side
        image = image.resize(
            (round(image.width * scale), round(image.height * scale)), Image.LANCZOS
        )
    image = _remove_shadows(image)
    angle = _skew_angle(image)
    if abs(angle) >= 0.5:
        image = image.rotate(angle, resample=Image.BICUBIC, expand=True, fillcolor=255)
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
    config = _tesseract_config()
    return pytesseract.image_to_string(
        _prepare_for_ocr(image), lang=_ocr_lang(pytesseract, config)
    )


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
