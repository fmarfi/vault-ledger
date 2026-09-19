"""Honest accuracy stats, computed from the posted ledger (feature 5).

The ledger already records `was_corrected` for every posted entry, so this
is a pure view over existing data. It measures how often a reviewer accepted
the proposal as-is -- a real, observed number -- not accuracy on unseen
documents, and it says so rather than dressing up a tiny sample.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

MIN_MEANINGFUL_SAMPLE = 20
RECENT_DAYS = 30


def _rate(entries: list[dict]) -> float | None:
    if not entries:
        return None
    accepted = sum(1 for e in entries if e["was_corrected"] != "True")
    return round(accepted / len(entries), 4)


def compute_stats(entries: list[dict], now: datetime | None = None) -> dict:
    now = now or datetime.now(timezone.utc)
    cutoff = (now - timedelta(days=RECENT_DAYS)).isoformat(timespec="seconds")
    recent = [e for e in entries if e.get("confirmed_at", "") >= cutoff]

    corrected_into: dict[str, int] = {}
    for e in entries:
        if e["was_corrected"] == "True":
            corrected_into[e["account"]] = corrected_into.get(e["account"], 0) + 1

    return {
        "total": len(entries),
        "corrected": sum(1 for e in entries if e["was_corrected"] == "True"),
        "first_pass_rate": _rate(entries),
        "recent_total": len(recent),
        "recent_first_pass_rate": _rate(recent),
        "recent_days": RECENT_DAYS,
        "corrected_into": sorted(corrected_into.items(), key=lambda kv: -kv[1]),
        "meaningful": len(entries) >= MIN_MEANINGFUL_SAMPLE,
        "min_sample": MIN_MEANINGFUL_SAMPLE,
    }
