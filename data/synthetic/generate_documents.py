"""Generate synthetic document images for the 3 target formats.

These stand in for real scanned invoices/bills/receipts (Report 1, item 2)
until real sample documents are available. Run this before exercising the
OCR step or the end-to-end pipeline demo:

    python data/synthetic/generate_documents.py
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from vault_ledger.synthetic_samples import SAMPLES

OUTPUT_DIR = Path(__file__).parent / "documents"


def _render(text: str, out_path: Path) -> None:
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


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for sample in SAMPLES:
        out_path = OUTPUT_DIR / f"{sample.name}.png"
        _render(sample.text, out_path)
        print(f"wrote {out_path}")


if __name__ == "__main__":
    main()
