"""Read-side views over the posted ledger: the Overview page's period
summary and the Export page's CSV files. Pure functions over the entry
dicts that ledger.read_entries() returns, so they're testable without
Flask or a ledger file.

Periods are calendar months in the machine's local time, keyed off
`confirmed_at` (when the entry was posted), not the document's own `date`
-- that field is OCR output and can be blank or in any format.
"""

from __future__ import annotations

import calendar
import csv
import io
from datetime import datetime

BOOKS_HEADER = ["Date", "Vendor", "Description", "Amount", "Account"]
AUDIT_HEADER = [
    "Confirmed at",
    "Source file",
    "Date",
    "Vendor",
    "Description",
    "Amount",
    "Account",
    "Model confidence",
    "Corrected by reviewer",
]


def _local_month(timestamp: str) -> tuple[int, int] | None:
    try:
        moment = datetime.fromisoformat(timestamp)
    except (TypeError, ValueError):
        return None
    if moment.tzinfo is not None:
        moment = moment.astimezone()
    return (moment.year, moment.month)


def _shift_month(year_month: tuple[int, int], delta: int) -> tuple[int, int]:
    index = year_month[0] * 12 + (year_month[1] - 1) + delta
    return (index // 12, index % 12 + 1)


def _posted_day(timestamp: str) -> str:
    # Blank OCR'd dates fall back to the (local) day the entry was posted,
    # so no row is undated in an import.
    try:
        moment = datetime.fromisoformat(timestamp)
    except (TypeError, ValueError):
        return ""
    if moment.tzinfo is not None:
        moment = moment.astimezone()
    return moment.date().isoformat()


def _entries_in(entries: list[dict], year_month: tuple[int, int]) -> list[dict]:
    return [e for e in entries if _local_month(e.get("confirmed_at", "")) == year_month]


def _total(entries: list[dict]) -> float:
    return round(sum(float(e["amount"]) for e in entries), 2)


def period_summary(entries: list[dict], period: str, now: datetime | None = None) -> dict:
    """Spend for this calendar month (`period="this"`) or the previous one
    (`"last"`), compared against the month before it, broken down by
    account with the biggest first."""
    now = now or datetime.now().astimezone()
    current = (now.year, now.month)
    target = current if period == "this" else _shift_month(current, -1)
    prior = _shift_month(target, -1)

    in_target = _entries_in(entries, target)
    total = _total(in_target)
    prior_total = _total(_entries_in(entries, prior))

    if prior_total > 0:
        pct = round((total - prior_total) / prior_total * 100)
        comparison = {
            "available": True,
            "direction": "up" if pct > 0 else "down" if pct < 0 else "flat",
            "pct": abs(pct),
        }
    else:
        comparison = {"available": False, "direction": None, "pct": None}
    comparison["label"] = "last month" if period == "this" else "the month before"

    by_account: dict[str, float] = {}
    for entry in in_target:
        by_account[entry["account"]] = by_account.get(entry["account"], 0.0) + float(entry["amount"])
    lines = [
        {"account": account, "amount": round(amount, 2)}
        for account, amount in sorted(by_account.items(), key=lambda kv: kv[1], reverse=True)
    ]

    return {
        "period": period,
        "month_label": f"{calendar.month_name[target[1]]} {target[0]}",
        "total": total,
        "entry_count": len(in_target),
        "comparison": comparison,
        "lines": lines,
    }


def _safe_cell(value) -> str:
    # Vendor/description come from OCR of arbitrary documents; a leading
    # = + - @ would run as a formula when the CSV is opened in a spreadsheet.
    text = "" if value is None else str(value)
    return "'" + text if text[:1] in ("=", "+", "-", "@", "\t", "\r") else text


def _write_csv(header: list[str], rows: list[list]) -> str:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(header)
    writer.writerows(rows)
    return buffer.getvalue()


def books_csv(entries: list[dict]) -> str:
    """Minimal transactional export: one row per posted entry."""
    rows = [
        [
            _safe_cell(e.get("date") or _posted_day(e.get("confirmed_at", ""))),
            _safe_cell(e.get("vendor")),
            _safe_cell(e.get("description")),
            e.get("amount", ""),
            _safe_cell(e.get("account")),
        ]
        for e in entries
    ]
    return _write_csv(BOOKS_HEADER, rows)


def audit_csv(entries: list[dict]) -> str:
    """Complete record: everything the ledger stores, including when each
    entry was posted, the model's confidence, and whether a reviewer
    overrode the prediction."""
    rows = [
        [
            e.get("confirmed_at", ""),
            _safe_cell(e.get("filename")),
            _safe_cell(e.get("date", "")),
            _safe_cell(e.get("vendor")),
            _safe_cell(e.get("description")),
            e.get("amount", ""),
            _safe_cell(e.get("account")),
            e.get("confidence", ""),
            "Yes" if str(e.get("was_corrected")) == "True" else "No",
        ]
        for e in entries
    ]
    return _write_csv(AUDIT_HEADER, rows)
