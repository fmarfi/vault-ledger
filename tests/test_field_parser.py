import pytest

from vault_ledger.extraction.field_parser import FieldParseError, parse_fields
from vault_ledger.synthetic_samples import SAMPLES


@pytest.mark.parametrize("sample", SAMPLES, ids=[s.name for s in SAMPLES])
def test_vendor_and_description_are_separate_fields(sample):
    """M3 checkpoint: vendor and description must never blend into one string.

    This is Report 1's explicitly flagged risk -- test it directly rather
    than trusting it as a side effect of the other field assertions below.
    """
    fields = parse_fields(sample.text)
    assert fields.vendor != fields.description
    assert fields.description not in fields.vendor
    assert fields.vendor not in fields.description


@pytest.mark.parametrize("sample", SAMPLES, ids=[s.name for s in SAMPLES])
def test_all_fields_parsed_correctly(sample):
    fields = parse_fields(sample.text)
    assert fields.vendor == sample.expected_vendor
    assert fields.description == sample.expected_description
    assert fields.amount == pytest.approx(sample.expected_amount)
    assert fields.paid == sample.expected_paid
    assert fields.date is not None


# --- Real-world fallback heuristics ---------------------------------------
# These mirror the tricky characteristics of an actual real-world receipt
# encountered during development (a SaaS billing receipt: greeting line
# before the vendor name, no-colon "Total" line, table-style description
# header, ISO date, no explicit Status line) without committing that real
# document -- see git history for the original finding.

_REALWORLD_RECEIPT_TEXT = (
    "We received payment for your Example Corp subscription. Thanks!\n"
    "Date 2026-07-11\n"
    "Description Amount\n"
    "Widget Pro Plan - month\n"
    "$10.00 USD\n"
    "Tax $0.00 USD\n"
    "Total $10.00 USD*\n"
    "Example Corp, Inc.\n"
    "1 Market Street\n"
    "San Francisco, CA"
)


def test_vendor_falls_back_to_company_suffix_when_first_line_is_not_the_vendor():
    fields = parse_fields(_REALWORLD_RECEIPT_TEXT)
    assert fields.vendor == "Example Corp, Inc."


def test_description_falls_back_to_table_header_next_line():
    fields = parse_fields(_REALWORLD_RECEIPT_TEXT)
    assert fields.description == "Widget Pro Plan - month"


def test_amount_falls_back_to_total_word_without_colon():
    fields = parse_fields(_REALWORLD_RECEIPT_TEXT)
    assert fields.amount == pytest.approx(10.00)


def test_amount_fallback_prefers_total_over_tax():
    """Tax appears before Total in the fixture -- must not be picked up
    instead just because it also has a currency amount on the line."""
    fields = parse_fields(_REALWORLD_RECEIPT_TEXT)
    assert fields.amount != pytest.approx(0.00)


def test_date_parses_iso_format():
    fields = parse_fields(_REALWORLD_RECEIPT_TEXT)
    assert fields.date == "2026-07-11"


def test_paid_inferred_true_from_received_payment_language_with_no_status_line():
    fields = parse_fields(_REALWORLD_RECEIPT_TEXT)
    assert fields.paid is True


def test_paid_inferred_false_from_amount_due_language_with_no_status_line():
    text = (
        "Reminder: your account has a balance due.\n"
        "Date 2026-08-01\n"
        "Description Amount\n"
        "Consulting Retainer\n"
        "$500.00 USD\n"
        "Total $500.00 USD\n"
        "Example Corp, Inc."
    )
    fields = parse_fields(text)
    assert fields.paid is False


def test_still_raises_clearly_when_nothing_matches():
    with pytest.raises(FieldParseError, match="description"):
        parse_fields("Just some unrelated text\nwith no structure at all")
