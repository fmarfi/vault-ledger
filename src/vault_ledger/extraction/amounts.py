"""One reader for currency amounts, English and Dutch notation.

    1,234.56   184.32   1234.56      -> point is the decimal mark
    1.234,56   184,32   1234,56      -> comma is the decimal mark
    349,-      1.250,-               -> whole euros, written with a dash

An amount always has exactly two decimals (or the `,-` that stands for them);
the decimal mark is whichever of `.` and `,` sits before them, and the other
one may group thousands in threes. Anything else is not read as an amount at
all, rather than read wrongly: `1.234` has no decimals, `14.03.2026` is a
date, `1.234.56` uses the same mark for both jobs, `1,23,456.78` does not
group in threes, and `21,00%` is a percentage. This replaces a point-only
pattern that read `€ 1.234,56` as 1.23 without any error.

Some amounts can be seen but not read safely: `€ 1 234,56` (a gap inside the
number, so 234,56 is only its tail), `- € 121,00` (a dash that may or may not
be a minus), `(121,00)`, `€ 1.250`. Those come back as doubtful readings.
find_amounts() leaves them out; single_amount() refuses the whole text.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from vault_ledger.extraction.locale_profile import CURRENCY_MARKS

# Not preceded by a digit or separator, and not followed by more of the same
# number (a third date part, a longer decimal).
AMOUNT_PATTERN = re.compile(
    r"(?<![0-9.,])(?:"
    r"(?P<decimal>[0-9]{1,3}(?:[.,][0-9]{3})+[.,][0-9]{2}|[0-9]+[.,][0-9]{2})(?![0-9]|[.,][0-9])"
    r"|(?P<whole>[0-9]{1,3}(?:\.[0-9]{3})+|[0-9]+),-(?![0-9A-Za-z-])"
    r")"
)

_MINUS = "-−–"  # hyphen-minus, minus sign, en dash (what OCR makes of either)
_CURRENCY = "(?:" + "|".join(
    rf"(?<![A-Za-z]){mark}" if mark.isalpha() else re.escape(mark) for mark in CURRENCY_MARKS
) + ")"
_CURRENCY_BEFORE = re.compile(rf"{_CURRENCY}[ \t]*$")
_PERCENT_AFTER = re.compile(r"[ \t]*%")
_DIGITS_THEN_GAP_BEFORE = re.compile(r"[0-9][.,]?[ \t]+$")
_MINUS_THEN_GAP_BEFORE = re.compile(rf"(?:^|[ \t(:])[{_MINUS}][ \t]+$")
_TRAILING_MINUS_AFTER = re.compile(r"-(?![0-9A-Za-z])")
# A currency mark with a number behind it; if no amount starts at that number,
# the document shows money this reader cannot read.
_MONEY_START = re.compile(rf"{_CURRENCY}[ \t]*[{_MINUS}]?[ \t]*(?=[0-9])")


class AmountError(ValueError):
    """The text does not hold exactly one amount that can be read safely."""


@dataclass(frozen=True)
class AmountReading:
    value: float | None
    doubt: str | None  # why this reading must not be used, or None


def to_number(raw: str) -> float | None:
    """The value of one decimal AMOUNT_PATTERN match, or None if its separators are
    inconsistent (the same mark used for thousands and decimals)."""
    whole, decimal_mark, decimals = raw[:-3], raw[-3], raw[-2:]
    if decimal_mark in whole:
        return None
    return float(whole.replace("," if decimal_mark == "." else ".", "") + "." + decimals)


def _is_sign_position(before_minus: str) -> bool:
    """A dash is a minus at the start, after a gap, bracket, colon or currency
    mark -- not inside a word or reference ("INV-12.50")."""
    return (
        not before_minus
        or before_minus[-1] in " \t(:"
        or _CURRENCY_BEFORE.search(before_minus) is not None
    )


def _scan_line(line: str) -> list[AmountReading]:
    readings = []
    token_starts = set()
    for match in AMOUNT_PATTERN.finditer(line):
        token_starts.add(match.start())
        before, after = line[: match.start()], line[match.end():]
        if match.group("decimal"):
            if _PERCENT_AFTER.match(after):
                continue  # "21,00%" is a rate, not money
            value = to_number(match.group("decimal"))
            if value is None:
                continue
        else:
            value = float(match.group("whole").replace(".", ""))

        doubt = None
        negative = False
        if _DIGITS_THEN_GAP_BEFORE.search(before):
            doubt = "digits and a gap directly before it (possibly one number split in two)"

        unmarked = _CURRENCY_BEFORE.sub("", before)
        if before and before[-1] in _MINUS:
            negative = _is_sign_position(before[:-1])
        elif unmarked != before and unmarked and unmarked[-1] in _MINUS:
            negative = _is_sign_position(unmarked[:-1])
        elif _MINUS_THEN_GAP_BEFORE.search(unmarked):
            doubt = "a dash and a gap before it (minus sign or separator)"

        if match.group("decimal") and _TRAILING_MINUS_AFTER.match(after):
            if negative:
                doubt = "a minus sign on both sides"
            negative = True
        if unmarked.endswith("(") and after.lstrip(" \t").startswith(")"):
            doubt = "written in brackets (possibly a negative amount)"

        readings.append(AmountReading(-value if negative else value, doubt))

    for match in _MONEY_START.finditer(line):
        if match.end() not in token_starts:
            readings.append(AmountReading(None, "a currency mark followed by a number that is not an amount"))
    return readings


def scan(text: str) -> list[AmountReading]:
    """Every amount reading in the text, doubtful ones included."""
    return [reading for line in text.splitlines() for reading in _scan_line(line)]


def find_amounts(text: str) -> list[float]:
    """Every amount in the text that can be read safely, in order."""
    return [reading.value for reading in scan(text) if reading.doubt is None]


def first_amount(text: str) -> float | None:
    amounts = find_amounts(text)
    return amounts[0] if amounts else None


def single_amount(text: str) -> float:
    """The one amount this text holds. Raises AmountError when there is none,
    when any reading is doubtful, or when it holds two different amounts --
    which of two is never guessed here."""
    readings = scan(text)
    for reading in readings:
        if reading.doubt is not None:
            raise AmountError(f"an amount in '{text}' has {reading.doubt}")
    values = sorted({reading.value for reading in readings})
    if not values:
        raise AmountError(f"could not parse a currency amount from '{text}'")
    if len(values) > 1:
        raise AmountError(f"more than one amount in '{text}'")
    return values[0]
