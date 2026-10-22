"""Dutch words, dates and amount notation in the field locator (tiers 1-2 only)."""

import pytest

from vault_ledger.extraction import field_parser
from vault_ledger.extraction.amounts import AmountError, find_amounts, first_amount, single_amount
from vault_ledger.extraction.field_parser import FieldParseError, parse_fields


@pytest.fixture(autouse=True)
def no_llm(monkeypatch):
    """Tier 3 off: these tests are about what the locator itself reads."""
    monkeypatch.setattr(field_parser, "extract_fields_via_llm", lambda _text: None)


# ---- amounts ----------------------------------------------------------------

@pytest.mark.parametrize(
    "text, expected",
    [
        ("€ 1.234,56", 1234.56),
        ("EUR 349,69", 349.69),
        ("12.345.678,90", 12345678.90),
        ("1234,56", 1234.56),
        ("$1,234.56", 1234.56),
        ("184.32", 184.32),
        ("1234.56", 1234.56),
    ],
)
def test_amount_notations(text, expected):
    assert first_amount(text) == expected


@pytest.mark.parametrize("text", ["1.234", "14.03.2026", "14-03-2026", "1.234.56", "21%", "NL861234567B01"])
def test_not_an_amount_is_not_read_as_one(text):
    assert find_amounts(text) == []


def test_dutch_thousands_amount_is_no_longer_read_as_one_point_twenty_three():
    fields = parse_fields("Bakkerij Jansen\nOmschrijving: Catering\nTotaal: € 1.234,56")
    assert fields.amount == 1234.56


# ---- a whole Dutch invoice --------------------------------------------------

DUTCH_INVOICE = """Noordkade Kantoorartikelen B.V.
Havenstraat 112, 3024 SK Rotterdam
KVK-nummer: 71234567
Btw-nummer: NL861234567B01
FACTUUR
Factuurnummer: 2026-0417
Factuurdatum: 1 oktober 2026
Leverdatum: 29-09-2026
Omschrijving: Printerpapier, toners en ordners
Subtotaal excl. btw: € 1.289,00
Btw 21%: € 270,69
Totaal te betalen: € 1.559,69
Gelieve binnen 30 dagen te betalen.
"""


def test_dutch_invoice_fields():
    fields = parse_fields(DUTCH_INVOICE)
    assert fields.vendor == "Noordkade Kantoorartikelen B.V."
    assert fields.description == "Printerpapier, toners en ordners"
    assert fields.amount == 1559.69
    assert fields.date == "1 oktober 2026"  # the Factuurdatum, not the Leverdatum
    assert fields.paid is False


def test_dutch_legal_suffix_finds_vendor_below_a_boilerplate_first_line():
    text = "FACTUUR\nGroothandel De Vries B.V.\nOmschrijving: Schoonmaakmiddelen\nTotaal: 84,70"
    assert parse_fields(text).vendor == "Groothandel De Vries B.V."


def test_two_dutch_companies_are_ambiguous_not_guessed():
    text = "Leverancier Noord B.V.\nKlant Zuid B.V.\nOmschrijving: Advies\nTotaal: 100,00"
    with pytest.raises(FieldParseError, match="vendor"):
        parse_fields(text)


def test_factuur_alone_is_never_the_vendor():
    with pytest.raises(FieldParseError, match="vendor"):
        parse_fields("Factuur\nOmschrijving: Advies\nTotaal: 100,00")


def test_table_header_omschrijving_takes_the_row_below():
    text = "Fietsenwinkel Peters\nOmschrijving Aantal Bedrag\nOnderhoudsbeurt stadsfiets 1 65,00\nTotaal 65,00"
    fields = parse_fields(text)
    assert fields.description == "Onderhoudsbeurt stadsfiets 1 65,00"
    assert fields.amount == 65.00


def test_two_totaal_lines_escalate_instead_of_guessing():
    text = "Bakkerij Jansen\nOmschrijving: Catering\nTotaal excl. btw 100,00\nTotaal 121,00"
    with pytest.raises(FieldParseError, match="amount"):
        parse_fields(text)


def test_subtotaal_is_not_a_total():
    text = "Bakkerij Jansen\nOmschrijving: Catering\nSubtotaal 100,00\nTotaal 121,00"
    assert parse_fields(text).amount == 121.00


@pytest.mark.parametrize("date_text", ["14 maart 2026", "3 mrt 2026", "14-03-2026"])
def test_dutch_dates(date_text):
    text = f"Bakkerij Jansen\nDatum: {date_text}\nOmschrijving: Catering\nTotaal: 121,00"
    assert parse_fields(text).date == date_text


@pytest.mark.parametrize(
    "line, paid",
    [
        ("Status: BETAALD", True),
        ("Status BETAALD", True),
        ("Voldaan per pinbetaling", True),
        ("Status: ONBETAALD", False),
        ("Nog niet betaald", False),
        ("Vervaldatum: 31-10-2026", False),
    ],
)
def test_dutch_paid_and_unpaid(line, paid):
    text = f"Bakkerij Jansen\nOmschrijving: Catering\nTotaal: 121,00\n{line}"
    assert parse_fields(text).paid is paid


# ---- faults found by an independent measurement of the first draft ----------

# Amounts that used to come back wrong without any error.

@pytest.mark.parametrize(
    "text, expected",
    [
        ("€ 349,-", 349.00),
        ("€ 1.250,-", 1250.00),
        ("-€ 121,00", -121.00),
        ("€ -121,00", -121.00),
        ("€-121,00", -121.00),
        ("-121,00", -121.00),
        ("−121,00", -121.00),
        ("121,00-", -121.00),
        ("Totaal incl. 21,00% btw € 121,00", 121.00),
        ("21,00 % btw over € 100,00", 100.00),
    ],
)
def test_amount_notations_whole_euros_minus_and_percentages(text, expected):
    assert find_amounts(text) == [expected]
    assert single_amount(text) == expected


@pytest.mark.parametrize(
    "text",
    [
        "€ 1 234,56",          # a gap inside the number: 234,56 is only its tail
        "€ 1. 234,56",         # OCR gap after the thousands point
        "1 234 567,89",
        "- € 121,00",          # minus sign or separator?
        "€ - 121,00",
        "(121,00)",            # bookkeeping notation for a negative, or an aside
        "(€ 121,00)",
        "€ 1.250",             # no decimals: 1250 or 1,25
        "$1,234",
        "$45.129",
        "-121,00-",
    ],
)
def test_amount_that_cannot_be_read_safely_is_refused_not_half_read(text):
    assert find_amounts(text) == []
    with pytest.raises(AmountError):
        single_amount(text)


@pytest.mark.parametrize("text", ["Totaal per 31.12 € 1.250,00", "€ 100,00 + € 21,00"])
def test_two_amounts_in_one_text_are_not_chosen_between(text):
    with pytest.raises(AmountError, match="more than one"):
        single_amount(text)


def test_reference_with_a_hyphen_is_not_a_negative_amount():
    assert find_amounts("INV-12,50") == [12.50]
    assert find_amounts("10,00-20,00") == [10.00, 20.00]


@pytest.mark.parametrize(
    "total_line",
    [
        "Totaal: € 1 234,56",
        "Totaal: € 1. 234,56",
        "Totaal per 31.12 € 1.250,00",
        "Totaal: € 1.250",
        "Totaal: 1.250",
    ],
)
def test_total_line_that_cannot_be_read_safely_raises(total_line):
    with pytest.raises(FieldParseError, match="amount"):
        parse_fields(f"Bakkerij Jansen\nOmschrijving: Catering\n{total_line}")


def test_percentage_with_decimals_on_the_total_line_is_not_the_total():
    text = "Bakkerij Jansen\nOmschrijving: Catering\nSubtotaal 100,00\nTotaal incl. 21,00% btw € 121,00"
    assert parse_fields(text).amount == 121.00


def test_whole_euro_total_is_read():
    assert parse_fields("Bakkerij Jansen\nOmschrijving: Catering\nTotaal: € 349,-").amount == 349.00


def test_credit_note_total_keeps_its_minus_sign():
    text = "Noordkade Kantoorartikelen B.V.\nCreditfactuur\nOmschrijving: Retour toners\nTotaal: -€ 121,00"
    assert parse_fields(text).amount == -121.00


@pytest.mark.parametrize(
    "second_total", ["Totaal incl. btw: € 121,00", "Te betalen: € 121,00", "Totaal te betalen € 121,00"]
)
def test_different_total_labels_with_different_values_escalate(second_total):
    text = f"Bakkerij Jansen\nOmschrijving: Catering\nTotaal: € 100,00\nBtw 21%: € 21,00\n{second_total}"
    with pytest.raises(FieldParseError, match="amount"):
        parse_fields(text)


def test_different_total_labels_with_the_same_value_agree():
    text = "Bakkerij Jansen\nOmschrijving: Catering\nTotaal: € 121,00\nTe betalen: € 121,00"
    assert parse_fields(text).amount == 121.00


# Vendor.

@pytest.mark.parametrize(
    "customer_line",
    ["Aan: Atelier Zuidwijk B.V.", "Factuuradres: Atelier Zuidwijk B.V.", "Klant: Atelier Zuidwijk B.V."],
)
def test_company_under_a_customer_label_is_the_customer_not_the_vendor(customer_line):
    text = f"Bakkerij Jansen\nFactuur\n{customer_line}\nOmschrijving: Catering\nTotaal: € 121,00"
    assert parse_fields(text).vendor == "Bakkerij Jansen"


def test_supplier_and_customer_on_bare_lines_are_still_ambiguous():
    text = (
        "Noordkade Kantoorartikelen B.V.\nFactuur aan:\nAtelier Zuidwijk B.V.\n"
        "Omschrijving: Toners\nTotaal: € 349,69"
    )
    with pytest.raises(FieldParseError, match="vendor"):
        parse_fields(text)


@pytest.mark.parametrize("first_line", ["FACTUUR 2026-0417", "Factuur nr. 2026-0417", "Kassabon 000123"])
def test_document_word_with_its_number_is_never_the_vendor(first_line):
    with pytest.raises(FieldParseError, match="vendor"):
        parse_fields(f"{first_line}\nBakkerij Jansen\nOmschrijving: Catering\nTotaal: € 121,00")


def test_dutch_only_legal_forms_count_on_a_dutch_document():
    text = "FACTUUR\nBrouwerij De Hoop NV\nOmschrijving: Fusten\nTotaal: 84,70"
    assert parse_fields(text).vendor == "Brouwerij De Hoop NV"
    # ... but not after a comma, which is how an address writes a US state.
    text = "Bakkerij Jansen\nReno, NV\nOmschrijving: Catering\nTotaal: 84,70"
    assert parse_fields(text).vendor == "Bakkerij Jansen"


# Dates.

def test_factuurdatum_in_words_beats_a_numeric_vervaldatum():
    text = (
        "Bakkerij Jansen\nFactuurdatum: 1 oktober 2026\nVervaldatum: 31-10-2026\n"
        "Omschrijving: Catering\nTotaal: € 121,00"
    )
    assert parse_fields(text).date == "1 oktober 2026"


@pytest.mark.parametrize(
    "date_line",
    ["Vervaldatum: 31-10-2026", "Leverdatum 29-09-2026", "Klantnummer: 31-45-2026", "Datum: 31 februari 2026"],
)
def test_other_dates_and_impossible_dates_are_not_the_invoice_date(date_line):
    text = f"Bakkerij Jansen\n{date_line}\nOmschrijving: Catering\nTotaal: € 121,00"
    assert parse_fields(text).date is None


# Paid.

def test_paid_statement_outweighs_the_vervaldatum_label():
    text = (
        "Noordkade Kantoorartikelen B.V.\nVervaldatum: 31-10-2026\nOmschrijving: Toners\n"
        "Totaal: € 349,69\nBetaald via iDEAL op 02-10-2026"
    )
    fields = parse_fields(text)
    assert fields.paid is True
    assert fields.date == "02-10-2026"  # the only date not labelled as another kind of date


def test_receipt_with_te_betalen_and_a_pin_line_for_the_total_is_paid():
    text = (
        "Jumbo Supermarkten B.V.\nOmschrijving Bedrag\nHalfvolle melk 1,29\nVolkoren brood 2,49\n"
        "Subtotaal 3,78\nTE BETALEN 3,78\nPIN 3,78"
    )
    fields = parse_fields(text)
    assert fields.amount == 3.78
    assert fields.paid is True


def test_cash_and_change_cover_the_total():
    text = "Slagerij De Boer\nOmschrijving: Rundergehakt\nTotaal 4,95\nContant 10,00\nWisselgeld 5,05"
    assert parse_fields(text).paid is True


def test_split_payment_adds_up_and_a_short_payment_does_not():
    base = "Slagerij De Boer\nOmschrijving: Rundergehakt\nTe betalen 4,95\n"
    assert parse_fields(base + "Contant 2,00\nPIN 2,95").paid is True
    assert parse_fields(base + "PIN 2,95").paid is False


def test_paid_and_unpaid_statements_together_raise():
    text = "Bakkerij Jansen\nOmschrijving: Catering\nTotaal: 121,00\nGelieve te betalen\nReeds betaald: 50,00"
    with pytest.raises(FieldParseError, match="paid"):
        parse_fields(text)


# Description.

def test_item_count_is_not_a_description():
    text = "Slagerij De Boer\nRundergehakt 500g 4,95\nArtikelen: 3\nTotaal: 4,95\nPinbetaling"
    with pytest.raises(FieldParseError, match="description"):
        parse_fields(text)


def test_stray_mark_before_omschrijving_still_finds_the_label():
    text = (
        "Noordkade Kantoorartikelen B.V.\n"
        "‘Omschrijving: Printerpapier en ordners\n"
        "Artikel Aantal Netto\nA4 printerpapier 4 EUR 98,00\n"
        "Totaal te betalen: EUR 98,00"
    )
    assert parse_fields(text).description == "Printerpapier en ordners"
