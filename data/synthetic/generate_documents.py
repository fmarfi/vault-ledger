"""Generate synthetic document images and PDFs for the 3 target formats.

These stand in for real scanned/digital invoices/bills/receipts (Report 1,
item 2) until real sample documents are available. Run this before
exercising the OCR step or the end-to-end pipeline demo:

    python data/synthetic/generate_documents.py

For each sample this writes:
  - {name}.png            -- image, for the existing image OCR path
  - {name}_native.pdf      -- born-digital PDF with a real text layer
                               (tests the fast native-text-extraction path)
  - {name}_scanned.pdf     -- the .png wrapped in a PDF with no text layer
                               (tests the rasterize + OCR fallback path)

PDF generation needs the `fpdf2` dev dependency (`pip install -e ".[dev]"").
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from vault_ledger.synthetic_samples import SAMPLES

OUTPUT_DIR = Path(__file__).parent / "documents"


def _render_image(text: str, out_path: Path) -> None:
    lines = text.splitlines()
    width, line_height, padding = 700, 34, 30
    height = padding * 2 + line_height * len(lines)

    image = Image.new("RGB", (width, height), color="white")
    draw = ImageDraw.Draw(image)
    try:
        font = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial.ttf", 22)
    except OSError:
        font = ImageFont.load_default()

    for i, line in enumerate(lines):
        draw.text((padding, padding + i * line_height), line, fill="black", font=font)

    image.save(out_path)


def _render_native_pdf(text: str, out_path: Path) -> None:
    from fpdf import FPDF  # dev-only dependency, imported lazily

    pdf = FPDF(format=(194, 194 + 8 * len(text.splitlines())))
    pdf.add_page()
    pdf.set_font("Helvetica", size=14)
    for line in text.splitlines():
        pdf.cell(0, 8, line, new_x="LMARGIN", new_y="NEXT")
    pdf.output(str(out_path))


def _render_scanned_pdf(image_path: Path, out_path: Path) -> None:
    Image.open(image_path).convert("RGB").save(out_path, "PDF")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for sample in SAMPLES:
        image_path = OUTPUT_DIR / f"{sample.name}.png"
        _render_image(sample.text, image_path)
        print(f"wrote {image_path}")

        native_pdf_path = OUTPUT_DIR / f"{sample.name}_native.pdf"
        _render_native_pdf(sample.text, native_pdf_path)
        print(f"wrote {native_pdf_path}")

        scanned_pdf_path = OUTPUT_DIR / f"{sample.name}_scanned.pdf"
        _render_scanned_pdf(image_path, scanned_pdf_path)
        print(f"wrote {scanned_pdf_path}")


if __name__ == "__main__":
    main()
