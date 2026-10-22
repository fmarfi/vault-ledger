"""One reader for dates, English and Dutch notation.

    03/14/2026   14-03-2026      -> day and month in either order
    2026-03-14                   -> ISO
    March 14, 2026   14 maart 2026

A date is only a date if it exists in the calendar. `12-45-9087` (a policy
number) and `31-45-2026` (a customer number) have the shape of one and are
not read as one. The text of the date is returned as written; this module
does not decide between day-first and month-first.
"""

from __future__ import annotations

import datetime
import re

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
