"""One reader for dates, English and Dutch notation.

    03/14/2026   14-03-2026      -> day and month in either order
    2026-03-14                   -> ISO
    March 14, 2026   14 maart 2026

A date is only a date if it exists in the calendar. `12-45-9087` (a policy
number) and `31-45-2026` (a customer number) have the shape of one and are
not read as one. find_dates returns the text as written; to_iso turns one
written date into YYYY-MM-DD.

Day and month order. Most written dates allow only one reading: a month
name, ISO, or a number above 12 (`14-03-2026`). Only a numeric date with
both parts 12 or under (`03/04/2026`) can be either. to_iso takes the order
the document itself shows (a Dutch document is always day first) and,
failing that, the user's setting -- and then says so (`assumed`), so the
reviewer is asked to check it. Nothing is guessed silently.
"""

from __future__ import annotations

import datetime
import re
from dataclasses import dataclass

from vault_ledger.extraction.locale_profile import PROFILES, words_pattern

_MONTH_NUMBERS = {name: number for profile in PROFILES for name, number in profile.month_names.items()}
_MONTH = words_pattern(_MONTH_NUMBERS)

# Not inside a longer run of digits and separators ("010-12-03-2026").
_NOT_BEFORE = r"(?<![0-9/.-])"
_NOT_AFTER = r"(?![0-9/-]|\.[0-9])"
_DATE_PATTERN = re.compile(
    rf"{_NOT_BEFORE}(?P<a>[0-9]{{1,2}})(?P<sep>[/-])(?P<b>[0-9]{{1,2}})(?P=sep)(?P<y1>[0-9]{{4}}){_NOT_AFTER}"
    rf"|{_NOT_BEFORE}(?P<y2>[0-9]{{4}})-(?P<m2>[0-9]{{2}})-(?P<d2>[0-9]{{2}}){_NOT_AFTER}"
    rf"|\b(?P<m3>{_MONTH})\.?\s+(?P<d3>[0-9]{{1,2}}),?\s+(?P<y3>[0-9]{{4}})\b"
    rf"|\b(?P<d4>[0-9]{{1,2}})\s+(?P<m4>{_MONTH})\.?\s+(?P<y4>[0-9]{{4}})\b",
    re.IGNORECASE,
)

# Outside this window a four-digit group is a reference number, not a year.
_MIN_YEAR, _MAX_YEAR = 1900, 2100


def _exists(year: int, month: int, day: int) -> bool:
    if not _MIN_YEAR <= year <= _MAX_YEAR:
        return False
    try:
        datetime.date(year, month, day)
    except ValueError:
        return False
    return True


def _in_calendar(match: re.Match) -> bool:
    if match.group("y1"):
        a, b, year = int(match.group("a")), int(match.group("b")), int(match.group("y1"))
        return _exists(year, b, a) or _exists(year, a, b)
    if match.group("y2"):
        return _exists(int(match.group("y2")), int(match.group("m2")), int(match.group("d2")))
    if match.group("y3"):
        month = _MONTH_NUMBERS[match.group("m3").lower()]
        return _exists(int(match.group("y3")), month, int(match.group("d3")))
    month = _MONTH_NUMBERS[match.group("m4").lower()]
    return _exists(int(match.group("y4")), month, int(match.group("d4")))


def date_matches(line: str) -> list[re.Match]:
    """Every calendar-valid date on one line, in order."""
    return [match for match in _DATE_PATTERN.finditer(line) if _in_calendar(match)]


def find_dates(text: str) -> list[str]:
    """Every calendar-valid date in the text, as written, in order."""
    return [match.group(0) for line in text.splitlines() for match in date_matches(line)]


DAY_FIRST = "day_first"
MONTH_FIRST = "month_first"
DATE_ORDERS = (DAY_FIRST, MONTH_FIRST)


@dataclass(frozen=True)
class DateReading:
    written: str  # as on the document
    iso: str  # YYYY-MM-DD
    assumed: bool  # day/month order came from the setting, not the document


def to_iso(written: str | None, order: str = DAY_FIRST, document_order: str | None = None) -> DateReading | None:
    """One written date as YYYY-MM-DD, or None if it isn't a calendar date.

    `document_order` is the order the document itself shows (see
    field_parser.document_date_order); `order` is the user's setting, used
    only when the document doesn't settle an ambiguous date."""
    text = (written or "").strip()
    match = _DATE_PATTERN.fullmatch(text)
    if match is None or not _in_calendar(match):
        return None
    if match.group("y2"):
        year, month, day = int(match.group("y2")), int(match.group("m2")), int(match.group("d2"))
    elif match.group("y3"):
        year, month, day = int(match.group("y3")), _MONTH_NUMBERS[match.group("m3").lower()], int(match.group("d3"))
    elif match.group("y4"):
        year, month, day = int(match.group("y4")), _MONTH_NUMBERS[match.group("m4").lower()], int(match.group("d4"))
    else:
        a, b, year = int(match.group("a")), int(match.group("b")), int(match.group("y1"))
        readings = {}
        if _exists(year, b, a):
            readings[DAY_FIRST] = (b, a)
        if _exists(year, a, b):
            readings[MONTH_FIRST] = (a, b)
        if len(set(readings.values())) == 1:  # only one reading, or a == b
            month, day = next(iter(readings.values()))
        else:
            chosen = document_order if document_order in DATE_ORDERS else order
            if chosen not in DATE_ORDERS:
                chosen = DAY_FIRST
            month, day = readings[chosen]
            return DateReading(text, datetime.date(year, month, day).isoformat(), document_order not in DATE_ORDERS)
    return DateReading(text, datetime.date(year, month, day).isoformat(), False)
