"""Read-side view for the Dashboard page: where the books stand today.

Pure functions over the rows that ledger.read_entries() and
queue.read_pending() return, plus `now`, so every figure is testable without
Flask or a data file. Nothing here is illustrative: each number is counted
from the caller's own ledger and queue, and an empty ledger gives zeros and
`None` rates rather than placeholders.

Month logic is reports.py's (calendar months in the machine's local time,
keyed off `confirmed_at`); the posted tile and the expense mix come straight
from reports.period_summary, and the acceptance rate from stats.compute_stats
run over the same month's rows.

There is deliberately no "journal balance" figure. A ledger row stores one
account and one amount, not the debit/credit lines construct_entry built, so
"n of n balanced" could not be computed from the stored data -- only
asserted.
"""

from __future__ import annotations

import calendar
import math
from datetime import datetime

from vault_ledger.reports import _entries_in, _local_month, _shift_month, period_summary
from vault_ledger.stats import compute_stats

REVIEW_TABLE_SIZE = 5
ACTIVITY_SIZE = 8


def _amount(row: dict) -> float | None:
    try:
        value = float(row.get("amount", ""))
    except (TypeError, ValueError):
        return None
    return value if math.isfinite(value) else None


def _confidence(row: dict) -> float | None:
    try:
        value = float(row.get("confidence", ""))
    except (TypeError, ValueError):
        return None
    return value if math.isfinite(value) else None


def _moment(timestamp: str) -> datetime | None:
    # Naive timestamps are read as machine-local, the same as reports.py.
    try:
        moment = datetime.fromisoformat(timestamp)
    except (TypeError, ValueError):
        return None
    return moment.astimezone()


def is_flagged(row: dict) -> bool:
    """A pending item the pipeline sent to a human: low confidence, an
    ambiguous field, or a rule rejection."""
    return row.get("needs_review") == "True" or bool(row.get("rejection_reason"))


def greeting(now: datetime) -> str:
    if 5 <= now.hour < 12:
        return "Good morning"
    if 12 <= now.hour < 18:
        return "Good afternoon"
    return "Good evening"


def header(username: str, now: datetime) -> dict:
    return {
        "greeting": f"{greeting(now)}, {username}",
        "today": f"{now:%A} {now.day} {now:%B %Y}",
    }


def relative_time(moment: datetime | None, now: datetime) -> str:
    if moment is None:
        return ""
    seconds = (now - moment).total_seconds()
    if seconds < 60:
        return "just now"
    if seconds < 3600:
        return f"{int(seconds // 60)} min ago"
    if seconds < 86400:
        return f"{int(seconds // 3600)} h ago"
    days = (now.date() - moment.astimezone(now.tzinfo).date()).days
    if days <= 1:
        return "yesterday"
    if days < 7:
        return f"{days} days ago"
    return f"{moment.day} {moment:%b %Y}"


def review_summary(pending: list[dict]) -> dict:
    return {"pending": len(pending), "flagged": sum(1 for row in pending if is_flagged(row))}


def open_value(pending: list[dict]) -> dict:
    """Sum of the proposed amounts still in the queue. Items whose amount
    could not be read are counted separately, never guessed."""
    amounts = [_amount(row) for row in pending]
    readable = [a for a in amounts if a is not None]
    return {
        "total": round(sum(readable), 2),
        "count": len(readable),
        "unreadable": len(amounts) - len(readable),
    }


def acceptance(entries: list[dict], period: str, now: datetime) -> dict:
    """Share of the period's posted entries accepted as proposed (no
    correction), with the counts behind it and whether the sample is big
    enough to mean anything (stats.MIN_MEANINGFUL_SAMPLE)."""
    current = (now.year, now.month)
    target = current if period == "this" else _shift_month(current, -1)
    stats = compute_stats(_entries_in(entries, target), now=now)
    return {
        "rate": stats["first_pass_rate"],
        "total": stats["total"],
        "accepted": stats["total"] - stats["corrected"],
        "corrected": stats["corrected"],
        "meaningful": stats["meaningful"],
        "min_sample": stats["min_sample"],
    }


def needs_review(pending: list[dict], limit: int = REVIEW_TABLE_SIZE) -> list[dict]:
    """The items most in need of a human: flagged first, then the lowest
    confidence, then the oldest. Unreadable confidence sorts as lowest."""

    def key(row):
        confidence = _confidence(row)
        return (not is_flagged(row), confidence if confidence is not None else -1.0, row.get("queued_at", ""))

    return [
        {
            "id": row.get("id", ""),
            "vendor": row.get("vendor", ""),
            "filename": row.get("filename", ""),
            "date": row.get("date", ""),
            "amount": _amount(row),
            "confidence": _confidence(row),
            "flagged": is_flagged(row),
            "predicted_account": row.get("predicted_account", ""),
        }
        for row in sorted(pending, key=key)[:limit]
    ]


def activity(entries: list[dict], pending: list[dict], now: datetime, limit: int = ACTIVITY_SIZE) -> list[dict]:
    """Ledger confirmations and queue arrivals merged, newest first.
    Rows with an unreadable timestamp are left out rather than misplaced."""
    events = []
    for entry in entries:
        moment = _moment(entry.get("confirmed_at", ""))
        if moment is None:
            continue
        corrected = entry.get("was_corrected") == "True"
        events.append(
            {
                "moment": moment,
                "kind": "corrected" if corrected else "posted",
                "vendor": entry.get("vendor", ""),
                "amount": _amount(entry),
                "text": f"{'corrected to' if corrected else 'posted to'} {entry.get('account', '')}",
            }
        )
    for row in pending:
        moment = _moment(row.get("queued_at", ""))
        if moment is None:
            continue
        events.append(
            {
                "moment": moment,
                "kind": "queued",
                "vendor": row.get("vendor", ""),
                "amount": _amount(row),
                "text": "added to review queue",
            }
        )
    events.sort(key=lambda e: e["moment"], reverse=True)
    return [
        {
            "at": e["moment"].isoformat(timespec="seconds"),
            "when": relative_time(e["moment"], now),
            "kind": e["kind"],
            "vendor": e["vendor"],
            "amount": e["amount"],
            "text": e["text"],
        }
        for e in events[:limit]
    ]


def readiness(entries: list[dict], pending: list[dict], now: datetime) -> dict:
    """Month-end readiness for the current month: entries posted this month
    against everything still waiting in the queue (an item queued last month
    and not yet posted still stands between you and a closed month)."""
    current = (now.year, now.month)
    posted = sum(1 for e in entries if _local_month(e.get("confirmed_at", "")) == current)
    waiting = len(pending)
    total = posted + waiting
    return {
        "posted": posted,
        "pending": waiting,
        "pct": round(posted / total * 100) if total else None,
    }


def expense_mix(summary: dict) -> list[dict]:
    """period_summary's per-account lines, biggest first, with each line's
    share of the period total."""
    total = summary["total"]
    return [
        {
            "account": line["account"],
            "amount": line["amount"],
            "share": round(line["amount"] / total * 100, 1) if total > 0 else None,
        }
        for line in summary["lines"]
    ]


def build(entries: list[dict], pending: list[dict], period: str, now: datetime) -> dict:
    """Everything the Dashboard page shows. `period` ("this" / "last")
    applies to the posted tile, the acceptance rate and the expense mix;
    the queue, activity and readiness are always about today."""
    period = "last" if period == "last" else "this"
    summary = period_summary(entries, period, now=now)
    return {
        "period": period,
        "month_label": summary["month_label"],
        "current_month_label": f"{calendar.month_name[now.month]} {now.year}",
        "review": review_summary(pending),
        "posted": {
            "count": summary["entry_count"],
            "total": summary["total"],
            "comparison": summary["comparison"],
        },
        "open_value": open_value(pending),
        "acceptance": acceptance(entries, period, now),
        "needs_review": needs_review(pending),
        "activity": activity(entries, pending, now),
        "readiness": readiness(entries, pending, now),
        "mix": expense_mix(summary),
        "has_ledger": bool(entries),
    }
