"""Posted-entry ledger: the record of every document that's been reviewed
and confirmed (accepted as-is or accepted after a correction).

Distinct from corrections.py, which exists purely as training signal
(predicted vs. corrected account, feeding classifier retraining) --
this module is the bookkeeping record itself: what got posted, to which
account, from which source file. The Documents and Account Ledger views
read from here. An entry lands here only on confirm, never on a bare
`/api/process` call -- matching real bookkeeping, where a proposed entry
isn't part of the books until an accountant confirms it.

CSV-backed for the same reason corrections.py is: this is an MVP, and a
flat file needs no setup. The read/write functions are the whole
interface -- swapping the storage (SQLite, etc.) later only means
rewriting this module, not any caller.
"""

from __future__ import annotations

import csv
from datetime import datetime, timezone
from pathlib import Path

from vault_ledger.userdata import resolve

LEDGER_PATH = Path(__file__).resolve().parents[2] / "data" / "ledger.csv"
FIELDNAMES = [
    "confirmed_at",
    "filename",
    "vendor",
    "description",
    "date",
    "amount",
    "account",
    "confidence",
    "was_corrected",
]


def append_entry(
    filename: str,
    vendor: str,
    description: str,
    date: str | None,
    amount: float,
    account: str,
    confidence: float,
    was_corrected: bool,
    path: str | Path | None = None,
    confirmed_at: str | None = None,
) -> None:
    """`confirmed_at` (ISO timestamp) defaults to now. Only the demo seed
    passes it, to backdate invented history so the Overview page has a
    previous month to compare against."""
    path = resolve("ledger.csv", LEDGER_PATH, path)
    path.parent.mkdir(parents=True, exist_ok=True)
    is_new = not path.exists()
    with path.open("a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        if is_new:
            writer.writeheader()
        writer.writerow(
            {
                "confirmed_at": confirmed_at or datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "filename": filename,
                "vendor": vendor,
                "description": description,
                "date": date or "",
                "amount": amount,
                "account": account,
                "confidence": confidence,
                "was_corrected": was_corrected,
            }
        )


def read_entries(path: str | Path | None = None) -> list[dict]:
    path = resolve("ledger.csv", LEDGER_PATH, path)
    if not path.exists():
        return []
    with path.open(newline="") as f:
        return list(csv.DictReader(f))


def entries_by_account(path: str | Path | None = None) -> dict[str, list[dict]]:
    grouped: dict[str, list[dict]] = {}
    for entry in read_entries(path):
        grouped.setdefault(entry["account"], []).append(entry)
    return grouped
