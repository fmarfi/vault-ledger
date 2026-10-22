"""Paid or unpaid, from what the document itself says.

Three kinds of evidence, strongest first:

    a status line          "Status: PAID", "Status BETAALD"
    a statement            "Payment received", "Betaald via iDEAL", "Please pay",
                           or a payment line that covers the total ("PIN 3,78")
    a hint                 "Amount due", "Vervaldatum", "Receipt"

A hint is a label or a document-type word that a settled invoice prints as
well, so it never outweighs a statement: "Vervaldatum" next to "Betaald via
iDEAL" is a paid invoice. Two statements that contradict each other are not
weighed against each other at all -- that is a conflict, and it raises.
"""

from __future__ import annotations

import re

from vault_ledger.extraction.amounts import AmountError, single_amount
from vault_ledger.extraction.locale_profile import CURRENCY_MARKS, PROFILES, collect, words_pattern


class PaidConflict(ValueError):
    """The document states both that it was paid and that it was not."""


def _whole_words(field: str) -> re.Pattern:
    return re.compile(rf"(?<!\w){words_pattern(collect(field))}(?!\w)", re.IGNORECASE)


_PAID_STATEMENTS = _whole_words("paid_statements")
_UNPAID_STATEMENTS = _whole_words("unpaid_statements")
_PAID_HINTS = _whole_words("paid_hints")
_UNPAID_HINTS = _whole_words("unpaid_hints")
_PAID_STATUS_VALUES = frozenset().union(*(profile.paid_status_values for profile in PROFILES))
_UNPAID_STATUS_VALUES = frozenset().union(*(profile.unpaid_status_values for profile in PROFILES))
STATUS_VALUES = _PAID_STATUS_VALUES | _UNPAID_STATUS_VALUES

_PAID_STATUS_LINE = re.compile(
    r"(?<!\w)"
    + words_pattern(profile.status_label for profile in PROFILES)
    + r"\s*:?\s*"
    + words_pattern(_PAID_STATUS_VALUES)
    + r"(?!\w)",
    re.IGNORECASE,
)
_PAYMENT_LINE = re.compile(rf"^{words_pattern(collect('payment_methods'))}(?!\w)(.*)$", re.IGNORECASE)
_CURRENCY_CODES = re.compile("|".join(mark for mark in CURRENCY_MARKS if mark.isalpha()))


def _payments_cover(raw_text: str, total: float | None) -> bool:
    """True when the lines that name a payment method and nothing but an
    amount ("PIN 3,78", "Contant 10,00") add up to the total or more."""
    if total is None or total <= 0:
        return False
    tendered = 0.0
    for line in raw_text.splitlines():
        match = _PAYMENT_LINE.match(line.strip())
        if match is None or re.search(r"[A-Za-z]", _CURRENCY_CODES.sub("", match.group(1))):
            continue
        try:
            tendered += single_amount(match.group(1))
        except AmountError:
            continue
    return round(tendered, 2) >= round(total, 2)


def has_paid_evidence(raw_text: str, status_raw: str | None = None, total: float | None = None) -> bool:
    """Whether anything in the document supports "paid" -- the check a
    model's claim of paid has to pass."""
    if status_raw and status_raw.strip().upper() in _PAID_STATUS_VALUES:
        return True
    if _PAID_STATUS_LINE.search(raw_text):
        return True
    remainder = _UNPAID_STATEMENTS.sub(" ", raw_text)
    return bool(
        _PAID_STATEMENTS.search(remainder)
        or _PAID_HINTS.search(remainder)
        or _payments_cover(raw_text, total)
    )


def infer_paid(raw_text: str, status_raw: str | None, total: float | None = None) -> bool | None:
    """True, False, or None when the document gives no signal either way.
    Raises PaidConflict when it states both."""
    if status_raw:
        status = status_raw.strip().upper()
        if status in _PAID_STATUS_VALUES:
            return True
        if status in _UNPAID_STATUS_VALUES:
            return False

    stated_unpaid = _UNPAID_STATEMENTS.search(raw_text) is not None
    # The unpaid statements are taken out first: "niet betaald" holds "betaald".
    remainder = _UNPAID_STATEMENTS.sub(" ", raw_text)
    stated_paid = _PAID_STATEMENTS.search(remainder) is not None or _payments_cover(raw_text, total)

    if stated_paid and stated_unpaid:
        raise PaidConflict("the document states both that it was paid and that it is still to be paid")
    if stated_unpaid:
        return False
    if stated_paid:
        return True
    if _UNPAID_HINTS.search(raw_text):
        return False
    if _PAID_HINTS.search(remainder):
        return True
    return None
