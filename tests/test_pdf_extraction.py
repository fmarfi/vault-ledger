from pathlib import Path

import pytest

from vault_ledger.extraction.ocr import find_tesseract
from vault_ledger.extraction.pdf import _native_text_sufficient, extract_pdf_text
from vault_ledger.synthetic_samples import SAMPLES

DOCUMENTS_DIR = Path(__file__).resolve().parents[1] / "data" / "synthetic" / "documents"

TESSERACT_AVAILABLE = find_tesseract() is not None


@pytest.mark.parametrize("text,expected", [
    ("", False),
    ("   \n  ", False),
    ("a few stray chars", False),  # 17 chars, under MIN_NATIVE_TEXT_CHARS
    ("Acme Office Supplies Inc\nInvoice total: $184.32", True),
])
def test_native_text_sufficient(text, expected):
    assert _native_text_sufficient(text) is expected


@pytest.mark.parametrize("sample", SAMPLES, ids=[s.name for s in SAMPLES])
def test_native_pdf_extracts_exact_text_without_ocr(sample):
    """Born-digital PDFs should return their real text layer -- this path
    must work even without tesseract installed, since no OCR is involved."""
    pdf_path = DOCUMENTS_DIR / f"{sample.name}_native.pdf"
    assert pdf_path.exists(), "run data/synthetic/generate_documents.py first"

    text = extract_pdf_text(pdf_path)

    assert sample.expected_vendor in text
    assert sample.expected_description in text


@pytest.mark.skipif(not TESSERACT_AVAILABLE, reason="tesseract binary not installed")
@pytest.mark.parametrize("sample", SAMPLES, ids=[s.name for s in SAMPLES])
def test_scanned_pdf_falls_back_to_ocr(sample):
    """A PDF with no text layer (image-only) should still yield readable
    text via the rasterize + OCR fallback path."""
    pdf_path = DOCUMENTS_DIR / f"{sample.name}_scanned.pdf"
    assert pdf_path.exists(), "run data/synthetic/generate_documents.py first"

    text = extract_pdf_text(pdf_path)

    assert sample.expected_vendor.split()[0] in text


def test_find_tesseract_honors_env_override(tmp_path, monkeypatch):
    fake = tmp_path / "tesseract-fake"
    fake.write_text("")
    monkeypatch.setenv("TESSERACT_CMD", str(fake))
    assert find_tesseract() == str(fake)


def test_find_tesseract_ignores_missing_env_override(monkeypatch, tmp_path):
    monkeypatch.setenv("TESSERACT_CMD", str(tmp_path / "does-not-exist"))
    result = find_tesseract()
    assert result != str(tmp_path / "does-not-exist")
