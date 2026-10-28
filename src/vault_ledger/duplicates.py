"""Possible-duplicate check for the review queue.

A pending item is a possible duplicate when another document with the same
vendor (case and spacing ignored), the same amount (to the cent) and the
same date is already in the ledger or elsewhere in the queue -- the same
invoice scanned twice, or uploaded again after it was posted.

It is a warning, never a block: two genuinely separate invoices can share
all three. Only bulk confirm acts on it (it skips such items so a human
looks at them one by one). An item with no date or no readable amount is
never matched -- too little to call it the same document.

Dates are compared as written. The same date in two notations
(`03/14/2026` and `2026-03-14`) does not match; which of day and month
comes first is not guessed here either (see extraction/dates.py).
"""

from __future__ import annotations

import math
from typing import Iterable


def match_key(vendor: str | None, amount, date: str | None) -> tuple[str, float, str] | None:
    """(normalised vendor, amount in cents' precision, date), or None if any
    of the three is missing or unreadable."""
    name = " ".join((vendor or "").split()).casefold()
    day = (date or "").strip()
    try:
        value = float(amount)
    except (TypeError, ValueError):
        return None
    if not name or not day or not math.isfinite(value):
        return None
    return name, round(value, 2), day


def find_match(item: dict, pending: Iterable[dict], ledger: Iterable[dict]) -> dict | None:
    """The first document `item` looks like a copy of: a ledger entry first,
    then another pending item (never itself, by id). Returns
    {"source": "ledger" | "queue", "id": ..., "filename": ...} or None.
    Ledger rows have no id, so theirs is ""."""
    key = match_key(item.get("vendor"), item.get("amount"), item.get("date"))
    if key is None:
        return None
    for entry in ledger:
        if match_key(entry.get("vendor"), entry.get("amount"), entry.get("date")) == key:
            return {"source": "ledger", "id": "", "filename": entry.get("filename", "")}
    for other in pending:
        if other.get("id") == item.get("id"):
            continue
        if match_key(other.get("vendor"), other.get("amount"), other.get("date")) == key:
            return {"source": "queue", "id": other.get("id", ""), "filename": other.get("filename", "")}
    return None


def find_duplicates(pending: list[dict], ledger: list[dict]) -> dict[str, dict]:
    """Every pending item that has a match, by id (see find_match). Two
    pending copies of each other are both reported, each pointing at the other."""
    found = {}
    for item in pending:
        match = find_match(item, pending, ledger)
        if match is not None:
            found[item["id"]] = match
    return found


def describe(match: dict) -> str:
    """One line for an error or a warning."""
    where = "already in the ledger" if match["source"] == "ledger" else "also in the review queue"
    return f"possible duplicate of {match['filename'] or 'another document'} ({where})"
