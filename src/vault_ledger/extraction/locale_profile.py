"""Locale profiles: every language-specific closed set the extraction code uses.

One profile per language. The parsing code (field_parser, amounts, dates,
paid, llm_fallback) holds no words of its own -- it reads them from here, so
adding a language means adding a profile, not editing the parsers.

Only closed sets belong here: field labels, legal forms, month names,
document-type words, currency marks. Nothing in a profile decides which of
several plausible values is the right one; that is never done by a word list
(see the design rule in field_parser's module docstring).
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# Not per language: a Dutch company invoices in USD and an English one in EUR.
CURRENCY_MARKS = ("€", "$", "£", "EUR", "USD", "GBP")


@dataclass(frozen=True)
class LocaleProfile:
    code: str
    amount_labels: tuple[str, ...]
    description_labels: tuple[str, ...]
    # First word of a table header row ("Description Amount Qty").
    description_headers: tuple[str, ...]
    # Labels of the document's own date. Any other labelled date (due,
    # delivery, order) is not the document date.
    invoice_date_labels: tuple[str, ...]
    # The word every date label of this language is built from
    # ("Due date", "Vervaldatum").
    date_word: str
    month_names: dict[str, int]
    # Legal forms as they read once trailing dots are stripped.
    legal_suffixes: frozenset[str]
    # Legal forms that read as something else outside this language ("NV" is
    # Nevada, "C.V." a curriculum vitae). Only used on a document that shows
    # this language's own labels.
    legal_suffixes_local: frozenset[str]
    # Labels of the party the document is addressed to -- never the vendor.
    customer_labels: frozenset[str]
    document_words: tuple[str, ...]
    # What may stand between a document word and its number ("Invoice no. 12").
    number_words: tuple[str, ...]
    page_words: tuple[str, str]
    status_label: str
    paid_status_values: frozenset[str]
    unpaid_status_values: frozenset[str]
    # Statements say the document was (not) paid. Hints are labels and
    # document-type words that only make one side likelier ("Amount due" is
    # printed on a settled invoice too) and never outweigh a statement.
    paid_statements: tuple[str, ...]
    unpaid_statements: tuple[str, ...]
    paid_hints: tuple[str, ...]
    unpaid_hints: tuple[str, ...]
    payment_methods: tuple[str, ...]


ENGLISH = LocaleProfile(
    code="en",
    amount_labels=("Amount Due", "Total Amount", "Total"),
    description_labels=("Description", "Service", "Items"),
    description_headers=("description", "items", "item", "service"),
    invoice_date_labels=("Invoice date", "Date of issue", "Issue date", "Date"),
    date_word="date",
    month_names={
        "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
        "july": 7, "august": 8, "september": 9, "october": 10, "november": 11, "december": 12,
        "jan": 1, "feb": 2, "mar": 3, "apr": 4, "jun": 6, "jul": 7, "aug": 8,
        "sep": 9, "sept": 9, "oct": 10, "nov": 11, "dec": 12,
    },
    legal_suffixes=frozenset({
        "inc", "incorporated", "llc", "ltd", "limited", "corp", "corporation",
        "company", "co", "gmbh", "plc",
    }),
    legal_suffixes_local=frozenset(),
    customer_labels=frozenset({
        "bill to", "billed to", "sold to", "ship to", "invoice to", "customer", "to",
    }),
    document_words=("invoice", "receipt"),
    number_words=("no", "number"),
    page_words=("page", "of"),
    status_label="Status",
    paid_status_values=frozenset({"PAID"}),
    unpaid_status_values=frozenset({"UNPAID"}),
    paid_statements=("payment received", "received payment", "charged to", "paid in full"),
    unpaid_statements=("please pay",),
    paid_hints=("receipt",),
    unpaid_hints=("amount due", "balance due", "payment due", "invoice due"),
    payment_methods=("cash", "card", "credit card", "debit card", "visa", "mastercard"),
)

DUTCH = LocaleProfile(
    code="nl",
    amount_labels=(
        "Totaal te betalen", "Te betalen", "Totaalbedrag", "Totaal bedrag", "Factuurbedrag", "Totaal",
    ),
    description_labels=("Omschrijving", "Beschrijving", "Betreft", "Dienst", "Artikelen"),
    description_headers=("omschrijving", "beschrijving", "artikelen", "artikel"),
    invoice_date_labels=("Factuurdatum", "Datum"),
    date_word="datum",
    month_names={
        "januari": 1, "februari": 2, "maart": 3, "april": 4, "mei": 5, "juni": 6,
        "juli": 7, "augustus": 8, "september": 9, "oktober": 10, "november": 11, "december": 12,
        "jan": 1, "feb": 2, "mrt": 3, "apr": 4, "jun": 6, "jul": 7, "aug": 8,
        "sep": 9, "sept": 9, "okt": 10, "nov": 11, "dec": 12,
    },
    legal_suffixes=frozenset({"b.v", "bv", "n.v", "v.o.f", "vof"}),
    legal_suffixes_local=frozenset({"nv", "c.v", "cv", "u.a"}),
    customer_labels=frozenset({
        "aan", "factuur aan", "factuuradres", "afleveradres", "klant", "t.a.v", "geadresseerde",
    }),
    document_words=(
        "factuur", "creditfactuur", "creditnota", "rekening", "nota", "kassabon", "bon", "kwitantie",
    ),
    number_words=("nr", "nummer"),
    page_words=("pagina", "van"),
    status_label="Status",
    paid_status_values=frozenset({"BETAALD", "VOLDAAN"}),
    unpaid_status_values=frozenset({"ONBETAALD", "NIET BETAALD", "OPENSTAAND"}),
    paid_statements=("betaald", "voldaan", "pinbetaling"),
    # Matched before the paid words, so "niet betaald" never reads as paid.
    unpaid_statements=("onbetaald", "niet betaald", "niet voldaan", "openstaand", "gelieve"),
    paid_hints=("kassabon",),
    unpaid_hints=("te betalen", "te voldoen", "vervaldatum", "betalingstermijn"),
    payment_methods=("pin", "pinnen", "pinbetaling", "contant", "ideal", "maestro"),
)

# English first: the product is English first, Dutch is the first addition.
PROFILES = (ENGLISH, DUTCH)


def words_pattern(words) -> str:
    """Regex alternation of whole words or phrases, longest first so that
    "Totaal te betalen" is tried before "Totaal". Inner spaces match any gap."""
    ordered = sorted(set(words), key=len, reverse=True)
    return "(?:" + "|".join(r"\s+".join(map(re.escape, word.split())) for word in ordered) + ")"


def collect(field: str) -> tuple[str, ...]:
    """One closed set across every profile, in profile order."""
    return tuple(word for profile in PROFILES for word in getattr(profile, field))


# A line "is a total line" when one of these stands on it as a whole word;
# the word boundary keeps "Subtotal" / "Subtotaal" out. Shared by the locator
# and by the check on what the local model claims.
AMOUNT_LABEL_PATTERN = re.compile(
    rf"(?<!\w){words_pattern(collect('amount_labels'))}(?!\w)", re.IGNORECASE
)
