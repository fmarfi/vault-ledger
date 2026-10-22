"""Generate a sample Dutch purchase invoice, in English and in Dutch, for
testing by hand in the app.

    python data/synthetic/generate_nl_invoice.py

Writes into data/synthetic/documents/, each as a born-digital PDF (native text
path) and as a PNG of the same page (OCR path):
  - nl_invoice_office_supplies      English wording, point as decimal mark
  - nl_factuur_kantoorartikelen     Dutch wording, comma as decimal mark

The invoice carries every item the Belastingdienst lists for a full invoice
("Factuureisen", read 2026-10-14): full name and address of supplier and
customer, the supplier's VAT identification number and KVK number, issue date,
a sequential invoice number, what was delivered and how many, the delivery
date, the amount excluding VAT, the VAT rate, the VAT amount, the unit price,
and amounts split per VAT rate. Total, due date and IBAN are extras. The rules
prescribe the contents, not the language.

Every company, address and number on it is invented.

PDF generation needs the `fpdf2` dev dependency (`pip install -e ".[dev]"`).
"""

from __future__ import annotations

from pathlib import Path

OUTPUT_DIR = Path(__file__).parent / "documents"

SUPPLIER = "Noordkade Kantoorartikelen B.V."
VAT_RATE = 21
PRICES = (24.50, 89.00, 13.00)
QUANTITIES = (4, 2, 1)

ENGLISH = {
    "name": "nl_invoice_office_supplies",
    "dutch_numbers": False,
    "supplier_lines": (
        "Havenstraat 112, 3024 SK Rotterdam, The Netherlands",
        "KVK number: 71234567",
        "VAT identification number: NL861234567B01",
        "IBAN: NL12 RABO 0123 4567 89",
    ),
    "title": "INVOICE",
    "invoice_lines": (
        "Invoice number: 2026-0417",
        "Invoice date: 2026-10-01",
        "Delivery date: 2026-09-29",
        "Due date: 2026-10-31",
    ),
    # Name and address on one line: the legal form must not end a second line,
    # or the locator sees two company names and escalates.
    "customer": "Bill to: Atelier Zuidwijk B.V., Oudegracht 245, 3511 NL Utrecht, The Netherlands",
    "description": "Description: Printer paper, toner cartridges and ring binders",
    "columns": ("Item", "Qty", "Unit price", "VAT", "Net"),
    "items": (
        "A4 printer paper 80 g, box of 5 reams",
        "Toner cartridge black HP 59A",
        "Ring binders A4, pack of 10",
    ),
    "subtotal": "Subtotal excluding VAT",
    "vat": "VAT {rate}% on {net}",
    "due": "Amount Due",
    "footer": "Please pay within 30 days to the IBAN above, quoting the invoice number.",
}

DUTCH = {
    "name": "nl_factuur_kantoorartikelen",
    "dutch_numbers": True,
    "supplier_lines": (
        "Havenstraat 112, 3024 SK Rotterdam",
        "KVK-nummer: 71234567",
        "Btw-identificatienummer: NL861234567B01",
        "IBAN: NL12 RABO 0123 4567 89",
    ),
    "title": "FACTUUR",
    "invoice_lines": (
        "Factuurnummer: 2026-0417",
        "Factuurdatum: 01-10-2026",
        "Leverdatum: 29-09-2026",
        "Vervaldatum: 31-10-2026",
    ),
    "customer": "Factuuradres: Atelier Zuidwijk B.V., Oudegracht 245, 3511 NL Utrecht",
    "description": "Omschrijving: Printerpapier, tonercartridges en ordners",
    "columns": ("Artikel", "Aantal", "Stukprijs", "Btw", "Netto"),
    "items": (
        "A4 printerpapier 80 g, doos van 5 pakken",
        "Tonercartridge zwart HP 59A",
        "Ordners A4, pak van 10",
    ),
    "subtotal": "Subtotaal exclusief btw",
    "vat": "Btw {rate}% over {net}",
    "due": "Totaal te betalen",
    "footer": "Gelieve binnen 30 dagen te betalen op bovenstaand IBAN onder vermelding van het factuurnummer.",
}


def totals() -> tuple[float, float, float]:
    net = round(sum(quantity * price for quantity, price in zip(QUANTITIES, PRICES)), 2)
    vat = round(net * VAT_RATE / 100, 2)
    return net, vat, round(net + vat, 2)


def _money(value: float, dutch: bool) -> str:
    text = f"{value:,.2f}"
    if dutch:
        text = text.replace(",", " ").replace(".", ",").replace(" ", ".")
    return f"EUR {text}"


def render_pdf(wording: dict, out_path: Path) -> None:
    from fpdf import FPDF  # dev-only dependency, imported lazily

    dutch = wording["dutch_numbers"]
    net, vat, total = totals()
    pdf = FPDF(format="A4")
    pdf.set_margins(20, 20, 20)
    pdf.add_page()

    def line(text: str, size: int = 11, style: str = "", height: float = 6) -> None:
        pdf.set_font("Helvetica", style=style, size=size)
        pdf.cell(0, height, text, new_x="LMARGIN", new_y="NEXT")

    line(SUPPLIER, size=16, style="B", height=9)
    for text in wording["supplier_lines"]:
        line(text)
    pdf.ln(8)
    line(wording["title"], size=20, style="B", height=11)
    pdf.ln(2)
    for text in wording["invoice_lines"]:
        line(text)
    pdf.ln(6)
    line(wording["customer"])
    pdf.ln(8)
    line(wording["description"])
    pdf.ln(4)

    widths = (84, 16, 30, 14, 26)
    aligns = ("L", "R", "R", "R", "R")

    def row(cells: tuple[str, ...], style: str = "") -> None:
        pdf.set_font("Helvetica", style=style, size=10)
        for text, width, align in zip(cells, widths, aligns):
            pdf.cell(width, 8, text, border="B", align=align)
        pdf.ln(8)

    row(wording["columns"], style="B")
    for item, quantity, price in zip(wording["items"], QUANTITIES, PRICES):
        row((item, str(quantity), _money(price, dutch), f"{VAT_RATE}%", _money(quantity * price, dutch)))
    pdf.ln(6)
    line(f"{wording['subtotal']}: {_money(net, dutch)}")
    line(f"{wording['vat'].format(rate=VAT_RATE, net=_money(net, dutch))}: {_money(vat, dutch)}")
    line(f"{wording['due']}: {_money(total, dutch)}", size=13, style="B", height=9)
    pdf.ln(6)
    line(wording["footer"], size=10)
    pdf.output(str(out_path))


def render_png(pdf_path: Path, out_path: Path) -> None:
    import pypdfium2

    document = pypdfium2.PdfDocument(str(pdf_path))
    try:
        document[0].render(scale=200 / 72).to_pil().convert("RGB").save(out_path)
    finally:
        document.close()


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for wording in (ENGLISH, DUTCH):
        pdf_path = OUTPUT_DIR / f"{wording['name']}.pdf"
        render_pdf(wording, pdf_path)
        print(f"wrote {pdf_path}")
        png_path = OUTPUT_DIR / f"{wording['name']}.png"
        render_png(pdf_path, png_path)
        print(f"wrote {png_path}")


if __name__ == "__main__":
    main()
