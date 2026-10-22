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


def test_total_amount_and_amount_due_with_different_values_escalate():
    """Was: returned "100.00" (the first label in the list), while tier 3
    accepts 40.00 for the same document. Two total labels that disagree are
    two candidates -- which one is owed is not decided by label order."""
    assert _find_amount_raw(["Total Amount: 100.00", "Amount Due: 40.00"]) is None


def test_total_amount_and_amount_due_with_the_same_value_agree():
    assert _find_amount_raw(["Total Amount: 100.00", "Amount Due: 100.00"]) == "100.00"


def test_total_and_total_incl_vat_escalate_instead_of_taking_the_first():
    lines = ["Total: $100.00", "VAT: $21.00", "Total incl. VAT: $121.00"]
    assert _find_amount_raw(lines) is None


# --- Faults found by an independent measurement of the Dutch change ---------
# English documents first: three things the committed code got right and the
# first Dutch draft broke.

def test_us_state_nv_on_an_address_line_is_not_a_dutch_legal_form():
    text = "Desert Coffee Roasters\n410 Sierra St\nReno, NV\nDescription: Espresso beans\nTotal: $84.00"
    assert parse_fields(text).vendor == "Desert Coffee Roasters"
    # Without the comma as well: no Dutch label on the document, so no Dutch-only form.
    assert _find_vendor(["Desert Coffee Roasters", "Reno NV", "Total: $84.00"]) == "Desert Coffee Roasters"


def test_prose_line_ending_in_cv_is_not_a_dutch_legal_form():
    text = (
        "Brightside Staffing\nCandidate placement fee, see attached C.V.\n"
        "Description: Recruitment\nTotal: $900.00"
    )
    assert parse_fields(text).vendor == "Brightside Staffing"


def test_dutch_bv_is_still_a_vendor_on_an_english_language_invoice():
    lines = ["INVOICE", "Noordkade Kantoorartikelen B.V.", "Description: Toner", "Total: $84.00"]
    assert _find_vendor(lines) == "Noordkade Kantoorartikelen B.V."


@pytest.mark.parametrize(
    "line",
    [
        "Policy No: 12-45-9087",   # month 45, year 9087
        "Ref 31/02/2026",          # 31 February
        "Ref 2026-13-01",          # month 13
        "Ref February 30, 2026",
        "Ref 12-11-9087",          # a real day and month, not a year
        "Tel 010-12-03-2026",      # inside a longer number
    ],
)
def test_date_shaped_text_that_is_not_in_the_calendar_is_not_a_date(line):
    assert _find_date(line) is None


def test_reference_number_shaped_like_a_date_does_not_become_the_date():
    text = "Acme Office Supplies Inc\nPolicy No: 12-45-9087\nDescription: Toner\nTotal: $84.00"
    assert parse_fields(text).date is None


def test_us_dashed_date_is_read():
    assert _find_date("Date: 03-14-2026") == "03-14-2026"


def test_indian_digit_grouping_raises_instead_of_being_read(monkeypatch):
    """Decision: 1,23,456.78 raises. The committed code read 123456.78, but
    only because its pattern ignored where the commas stood -- the same
    pattern read $45.129 as 45.12. Grouping that is not in threes is how a
    misread shows itself; lakh grouping belongs in a locale profile of its
    own if that market is ever supported."""
    monkeypatch.setattr(
        "vault_ledger.extraction.field_parser.extract_fields_via_llm", lambda text: None
    )
    for total in ("1,23,456.78", "$45.129", "$1,234"):
        with pytest.raises(FieldParseError, match="amount"):
            parse_fields(f"Acme Office Supplies Inc\nDescription: Consulting\nTotal: {total}")


# Vendor: the company under a customer label is the customer.

@pytest.mark.parametrize(
    "customer_line", ["Bill to: Atelier Zuidwijk Ltd", "Sold To: Atelier Zuidwijk Ltd", "Customer: Atelier Zuidwijk Ltd"]
)
def test_company_under_a_customer_label_is_not_the_vendor(customer_line):
    assert _find_vendor(["Brightside Staffing", customer_line, "Total: $84.00"]) == "Brightside Staffing"
    # With a real vendor line next to it, that one is taken -- not an ambiguity.
    assert _find_vendor(["Invoice", customer_line, "Brightside Staffing Inc"]) == "Brightside Staffing Inc"


def test_company_under_a_label_that_names_no_party_escalates():
    assert _find_vendor(["Some heading", "Remit payments to: XYZ Inc"]) is None
    assert _find_vendor(["Lovable Labs Incorporated", "Remit payments to: XYZ Inc"]) is None


@pytest.mark.parametrize(
    "first_line", ["INVOICE #1042", "Invoice no. 2026-0417", "Receipt 88123", "Date: 03/14/2026", "Total: $84.00"]
)
def test_document_number_or_labelled_field_on_line_one_is_not_the_vendor(first_line):
    assert _find_vendor([first_line, "Brightside Staffing", "more content"]) is None


# Date: the labelled invoice date wins; several unlabelled dates are not guessed.

def test_labelled_invoice_date_beats_other_dates_whatever_their_notation():
    text = "Due date: 2026-10-31\nDelivery date: 09/29/2026\nInvoice date: October 1, 2026"
    assert _find_date(text) == "October 1, 2026"


def test_date_labelled_as_another_kind_of_date_is_not_the_document_date():
    assert _find_date("Due date: 2026-10-31") is None
    assert _find_date("Due date 2026-10-31") is None


def test_several_unlabelled_dates_give_none_not_the_first():
    assert _find_date("Printed 2026-10-01\nShipped 2026-10-03") is None
    assert _find_date("Printed 2026-10-01\nReprinted 2026-10-01") == "2026-10-01"


def test_two_different_labelled_invoice_dates_give_none():
    assert _find_date("Date: 03/14/2026\nInvoice date: 03/15/2026") is None


# Labels damaged by OCR.

def test_status_without_its_colon_is_read_when_the_value_is_a_status_word():
    text = "CityPower & Gas Utility Co\nService: Electricity\nTotal Amount $212.10\nStatus PAID"
    assert parse_fields(text).paid is True
    text = "CityPower & Gas Utility Co\nService: Electricity\nTotal Amount $212.10\nStatus UNPAID"
    assert parse_fields(text).paid is False


def test_description_label_without_its_colon_escalates_instead_of_taking_the_total_line(monkeypatch):
    """OCR of our own receipt sample dropped the colon: "Items Coffee, ..."
    was read as a table header and "Total: $27.85" became the description."""
    monkeypatch.setattr(
        "vault_ledger.extraction.field_parser.extract_fields_via_llm", lambda text: None
    )
    text = "QuickMart Retail Store\nReceipt\nItems Coffee, notebooks pens\nTotal: $27.85\nStatus PAID"
    with pytest.raises(FieldParseError, match="description"):
        parse_fields(text)


@pytest.mark.parametrize("stray", ["‘", "|", ". ", "'"])
def test_stray_mark_before_a_label_does_not_hide_the_label(stray):
    text = (
        "Acme Office Supplies Inc\n"
        f"{stray}Description: Printer paper\n"
        "Item Qty Net\nA4 paper 4 98.00\n"
        f"{stray}Total: $98.00"
    )
    fields = parse_fields(text)
    assert fields.description == "Printer paper"
    assert fields.amount == 98.00


def test_stray_letter_before_a_label_is_not_guessed_away(monkeypatch):
    monkeypatch.setattr(
        "vault_ledger.extraction.field_parser.extract_fields_via_llm", lambda text: None
    )
    with pytest.raises(FieldParseError, match="description"):
        parse_fields("Acme Office Supplies Inc\nlDescription: Printer paper\nTotal: $98.00")


def test_table_header_on_line_one_is_not_the_vendor():
    assert _find_vendor(["Item, Qty Unit price Net", "A4 paper 4 98.00"]) is None


# Tier 3 answers that tiers 1-2 know better.

def test_llm_date_is_replaced_by_the_labelled_invoice_date(monkeypatch):
    monkeypatch.setattr(
        "vault_ledger.extraction.field_parser.extract_fields_via_llm",
        lambda text: {
            "vendor": "Some Vendor",
            "description": "Some description",
            "date": "2026-10-31",  # the due date
            "amount": 42.0,
            "paid": False,
        },
    )
    text = "Invoice date: 2026-10-01\nDue date: 2026-10-31\nno other structure"
    assert parse_fields(text).date == "2026-10-01"


def test_paid_and_unpaid_statements_together_raise_even_after_the_llm_tier(monkeypatch):
    monkeypatch.setattr(
        "vault_ledger.extraction.field_parser.extract_fields_via_llm",
        lambda text: {
            "vendor": "Some Vendor",
            "description": "Some description",
            "date": None,
            "amount": 42.0,
            "paid": True,
        },
    )
    with pytest.raises(FieldParseError, match="paid"):
        parse_fields("Payment received, thank you\nPlease pay the remainder\nno other structure")


def test_paid_statement_outweighs_an_amount_due_label():
    text = "Acme Office Supplies Inc\nDescription: Toner\nAmount Due: $84.00\nPayment received 2026-10-02"
    assert parse_fields(text).paid is True


def test_card_line_covering_the_total_means_paid():
    text = "QuickMart Retail Store\nItems: Coffee\nAmount Due: $27.85\nVisa $27.85"
    assert parse_fields(text).paid is True
    text = "QuickMart Retail Store\nItems: Coffee\nAmount Due: $27.85\nVisa $7.85"
    assert parse_fields(text).paid is False
