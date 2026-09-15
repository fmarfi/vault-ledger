"""Canonical synthetic document samples, one per target format.

Single source of truth used by both `data/synthetic/generate_documents.py`
(renders these to images for the OCR step) and the test suite (field parser
and pipeline tests) -- keeps the "3 target formats" concept consistent
end-to-end instead of duplicated in two places.

These are placeholders sized only to prove the pipeline runs end-to-end, not
representative of real invoice variety -- see README "Known limitations".
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SyntheticDocument:
    name: str
    format_type: str  # "invoice" | "utility_bill" | "receipt"
    text: str
    expected_vendor: str
    expected_description: str
    expected_amount: float
    expected_paid: bool


SAMPLES: list[SyntheticDocument] = [
    SyntheticDocument(
        name="invoice_office_supplies",
        format_type="invoice",
        text=(
            "Acme Office Supplies Inc\n"
            "INVOICE #1042\n"
            "Date: 03/14/2026\n"
            "Description: Printer paper and toner cartridges\n"
            "Amount Due: $184.32\n"
            "Status: UNPAID"
        ),
        expected_vendor="Acme Office Supplies Inc",
        expected_description="Printer paper and toner cartridges",
        expected_amount=184.32,
        expected_paid=False,
    ),
    SyntheticDocument(
        name="utility_bill_citypower",
        format_type="utility_bill",
        text=(
            "CityPower & Gas Utility Co\n"
            "Account Statement\n"
            "Date: 03/01/2026\n"
            "Service: Electricity and gas usage for March\n"
            "Total Amount: $212.10\n"
            "Status: PAID"
        ),
        expected_vendor="CityPower & Gas Utility Co",
        expected_description="Electricity and gas usage for March",
        expected_amount=212.10,
        expected_paid=True,
    ),
    SyntheticDocument(
        name="receipt_quickmart",
        format_type="receipt",
        text=(
            "QuickMart Retail Store\n"
            "Receipt\n"
            "Date: 03/10/2026\n"
            "Items: Coffee, notebooks, pens\n"
            "Total: $27.85\n"
            "Status: PAID"
        ),
        expected_vendor="QuickMart Retail Store",
        expected_description="Coffee, notebooks, pens",
        expected_amount=27.85,
        expected_paid=True,
    ),
]
