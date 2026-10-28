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
import os
import tempfile
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
    # Queue item id the document was stored under (documents.py), so the
    # Documents page can show the original. Empty for entries posted before
    # it was recorded and for the demo's invented history.
    "document_id",
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
    document_id: str = "",
) -> None:
    """`confirmed_at` (ISO timestamp) defaults to now. Only the demo seed
    passes it, to backdate invented history so the Overview page has a
    previous month to compare against."""
    path = resolve("ledger.csv", LEDGER_PATH, path)
    path.parent.mkdir(parents=True, exist_ok=True)
    _upgrade_header(path)
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
                "document_id": document_id or "",
            }
        )


def _upgrade_header(path: Path) -> None:
    """A ledger written before a column was added is rewritten once (to a
    temp file, then swapped in) with the current header, so a longer row is
    never appended under a shorter header."""
    if not path.exists() or path.stat().st_size == 0:
        return
    with path.open(newline="") as f:
        header = next(csv.reader(f), [])
    if header == FIELDNAMES:
        return
    rows = read_entries(path)
    fd, tmp = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    with os.fdopen(fd, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)
    os.replace(tmp, path)


def read_entries(path: str | Path | None = None) -> list[dict]:
    path = resolve("ledger.csv", LEDGER_PATH, path)
    if not path.exists():
        return []
    with path.open(newline="") as f:
        # Normalised to the current columns: a missing one (an older row) is "".
        return [{name: row.get(name) or "" for name in FIELDNAMES} for row in csv.DictReader(f)]


def entries_by_account(path: str | Path | None = None) -> dict[str, list[dict]]:
    grouped: dict[str, list[dict]] = {}
    for entry in read_entries(path):
        grouped.setdefault(entry["account"], []).append(entry)
    return grouped
