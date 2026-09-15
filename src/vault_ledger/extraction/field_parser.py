"""Field parsing: raw OCR text -> vendor, description, date, amount, paid.

Report 1, item 3 -- the step flagged as most likely to silently undercut the
two-field classifier gain. Vendor and description MUST come out as two
separate fields, never concatenated. Regex/position heuristics are enough for
the 3 target formats; no ML needed here.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

_AMOUNT_LABELS = ("Amount Due", "Total Amount", "Total")
_DESCRIPTION_LABELS = ("Description", "Service", "Items")

_AMOUNT_PATTERN = re.compile(r"\$?\s*([0-9][0-9,]*\.[0-9]{2})")
_DATE_PATTERN = re.compile(r"\b(\d{1,2}/\d{1,2}/\d{4})\b")


class FieldParseError(Exception):
    """Raised when a required field (vendor, amount) cannot be located."""


@dataclass(frozen=True)
class ExtractedFields:
    vendor: str
    description: str
    date: str | None
    amount: float
    paid: bool


def _find_labeled_value(lines: list[str], labels: tuple[str, ...]) -> str | None:
    for line in lines:
        for label in labels:
            prefix = f"{label}:"
            if line.lower().startswith(prefix.lower()):
                return line[len(prefix):].strip()
    return None


def parse_fields(raw_text: str) -> ExtractedFields:
    lines = [line.strip() for line in raw_text.splitlines() if line.strip()]
    if not lines:
        raise FieldParseError("no text to parse")

    # Vendor: position-based heuristic -- vendor name is near the top
    # (Report 1's own suggested heuristic). Kept as its own field, never
    # merged with description below.
    vendor = lines[0]

    description_raw = _find_labeled_value(lines, _DESCRIPTION_LABELS)
    if description_raw is None:
        raise FieldParseError("could not locate a description/service/items field")
    description = description_raw

    amount_raw = _find_labeled_value(lines, _AMOUNT_LABELS)
    if amount_raw is None:
        raise FieldParseError("could not locate an amount/total field")
    amount_match = _AMOUNT_PATTERN.search(amount_raw)
    if amount_match is None:
        raise FieldParseError(f"could not parse a currency amount from '{amount_raw}'")
    amount = float(amount_match.group(1).replace(",", ""))

    date_match = _DATE_PATTERN.search(raw_text)
    date = date_match.group(1) if date_match else None

    status_raw = _find_labeled_value(lines, ("Status",))
    paid = bool(status_raw) and status_raw.strip().upper() == "PAID"

    return ExtractedFields(
        vendor=vendor,
        description=description,
        date=date,
        amount=amount,
        paid=paid,
    )
