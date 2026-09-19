import pytest

from vault_ledger.extraction.field_parser import (
    FieldParseError,
    _find_amount_raw,
    _find_date,
    _find_description_raw,
    _find_vendor,
    parse_fields,
)
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


def test_still_raises_clearly_when_nothing_matches(monkeypatch):
    """LLM fallback (tier 3) is mocked off here -- this tests tiers 1-2
    only. Real LLM-tier behavior is covered in test_llm_fallback.py,
    isolated from the rest of the suite so it doesn't make every
    heuristic-failure test slow/dependent on Ollama being installed."""
    monkeypatch.setattr(
        "vault_ledger.extraction.field_parser.extract_fields_via_llm", lambda text: None
    )
    with pytest.raises(FieldParseError, match="description"):
        parse_fields("Just some unrelated text\nwith no structure at all")


def test_llm_fallback_used_when_heuristics_fail(monkeypatch):
    monkeypatch.setattr(
        "vault_ledger.extraction.field_parser.extract_fields_via_llm",
        lambda text: {
            "vendor": "Some Vendor",
            "description": "Some description",
            "date": "2026-01-01",
            "amount": 42.0,
            "paid": True,
        },
    )
    fields = parse_fields("Just some unrelated text\nwith no structure at all")
    assert fields.vendor == "Some Vendor"
    assert fields.amount == 42.0


# --- Ambiguity-detection tier-2 fixes --------------------------------------
# Found via a real invoice (Lovable Labs): "Page 1 of 1" as line one (no
# company-suffix line at all) picked as vendor, and "Total excluding tax
# €20.66" picked over the real "Total €25.00" since it matched first. Fixed
# by treating multiple plausible candidates as ambiguous (escalate, don't
# guess) rather than hardcoding an ever-growing exclude-phrase list -- see
# the module docstring. These test the private helpers directly since
# they're the load-bearing logic the module docstring's design rule
# describes; parse_fields-level coverage is above and in test_pdf_extraction.

def test_vendor_ambiguous_suffix_matches_returns_none_not_first_match():
    """A code-review finding: picking the first suffix-matching line among
    several is the same silent-guess mistake this design rule forbids for
    amount. A 'Bill To' line and the real vendor's footer can both carry a
    legal suffix -- must not just take whichever appears first."""
    lines = ["Bill To: ABC Corp", "some other line", "Remit payments to: XYZ Inc"]
    assert _find_vendor(lines) is None


def test_vendor_with_digit_is_not_rejected_when_unambiguous():
    """A code-review finding: an earlier version of this fix rejected any
    first line containing a digit at all, which would have broken every
    legitimate vendor name with a digit in it (7-Eleven, Store 24, 3M)."""
    assert _find_vendor(["7-Eleven", "Date: 03/14/2026"]) == "7-Eleven"
    assert _find_vendor(["Store 24", "Date: 03/14/2026"]) == "Store 24"


def test_vendor_rejects_page_number_boilerplate_as_first_line():
    lines = ["Page 1 of 1", "Invoice", "Lovable Labs Incorporated"]
    # No ambiguity here -- exactly one suffix match ("Incorporated").
    assert _find_vendor(lines) == "Lovable Labs Incorporated"
    # With no suffix anywhere, boilerplate must still not be trusted as vendor.
    assert _find_vendor(["Page 1 of 1", "some content", "more content"]) is None


def test_amount_ambiguous_total_candidates_returns_none_not_first_match():
    lines = ["Subtotal €25.00", "Total excluding tax €20.66", "Total €25.00"]
    assert _find_amount_raw(lines) is None


def test_amount_single_total_candidate_still_works():
    lines = ["Subtotal €25.00", "Total €25.00"]
    assert _find_amount_raw(lines) == "Total €25.00"


def test_date_parses_written_month_name_format():
    assert _find_date("Date of issue June 18, 2026") == "June 18, 2026"


def test_llm_escalation_does_not_override_confident_paid_heuristic(monkeypatch):
    """A real invoice caught the LLM guessing paid=True for a document
    explicitly reading '...due June 18, 2026 ... Pay online' -- our own
    keyword heuristic has no ambiguity failure mode for this field and
    should win over the LLM's guess when it has a real signal."""
    monkeypatch.setattr(
        "vault_ledger.extraction.field_parser.extract_fields_via_llm",
        lambda text: {
            "vendor": "Some Vendor",
            "description": "Some description",
            "date": "2026-01-01",
            "amount": 42.0,
            "paid": True,  # the LLM's (wrong) guess
        },
    )
    text = "amount due\nJust some unrelated text\nwith no other structure"
    fields = parse_fields(text)
    assert fields.paid is False


def test_conflicting_labeled_totals_raise_instead_of_taking_the_first():
    with pytest.raises(FieldParseError):
        _find_amount_raw(["Total: $10.00", "Total: $12.00"])


def test_duplicate_labeled_total_with_same_value_is_not_ambiguous():
    assert _find_amount_raw(["Total: $10.00", "Total: $10.00"]) == "$10.00"


def test_conflicting_labeled_descriptions_raise_instead_of_taking_the_first():
    with pytest.raises(FieldParseError):
        _find_description_raw(["Description: Widgets", "Description: Gadgets"])


def test_same_total_in_different_formats_is_not_a_conflict():
    assert _find_amount_raw(["Total: $1,000.00", "Total: 1000.00"]) == "$1,000.00"


def test_total_amount_and_amount_due_are_different_fields_not_a_conflict():
    assert _find_amount_raw(["Total Amount: 100.00", "Amount Due: 40.00"]) == "100.00"
