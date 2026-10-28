"""Persistent review queue: documents that have been processed but not yet
confirmed or corrected (diagnostics report, feature 1).

Before this module, a processed-but-unreviewed result lived only in the
browser tab's JS state -- refresh the page and it was gone, and there was
no way to hold more than one document "in flight" at once. This is the
missing server-side counterpart to ledger.py's confirmed-entry store: an
item lands here the moment /api/process runs, and leaves the moment it's
confirmed, corrected, or dismissed (see app.py). Bulk confirm (feature 2)
is built directly on top of this -- it's just confirming several pending
ids in one call instead of one at a time.

CSV-backed for the same reason ledger.py and corrections.py are -- no new
storage concept for this MVP, just a third flat file next to the other two.

`entry_json` stores the already-constructed proposed journal entry
(serialized by the caller, app.py) so the review queue can show the
debit/credit breakdown on a reload without re-running the rules engine --
it's a cache of a pure-function result, not a second source of truth.

`decided_by` names the model in the classifier cascade that made the
prediction (classifier/cascade.py). Rows written before it existed load
with it as "".
"""

from __future__ import annotations

import csv
import os
import re
import tempfile
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path

from vault_ledger import preferences
from vault_ledger.extraction.dates import to_iso
from vault_ledger.userdata import current_user_id, lock_for, resolve

_ISO_DATE = re.compile(r"\d{4}-\d{2}-\d{2}")

PENDING_PATH = Path(__file__).resolve().parents[2] / "data" / "pending_queue.csv"


def queue_lock() -> threading.RLock:
    """The lock for the current user's queue (one RLock per user id, so users
    don't block each other). It guards every read-modify-write on the queue
    file and the confirm flow in app.py (get -> post to ledger -> remove) so
    two tabs or a double-click can't both post the same item. RLock: confirm
    holds it while calling remove_pending, which takes it again. In-process
    only: run ONE server process (threads are fine)."""
    return lock_for(current_user_id())


FIELDNAMES = [
    "id",
    "queued_at",
    "filename",
    "vendor",
    "description",
    "date",
    "amount",
    "paid",
    "predicted_account",
    "confidence",
    "needs_review",
    "rejection_reason",
    "entry_json",
    "decided_by",
    "date_written",
    "date_assumed",
    "scored_with",  # pipeline.scoring_version() of the stored score
]

# What update_pending may rewrite: everything but the row's identity.
EDITABLE_FIELDS = frozenset(FIELDNAMES) - {"id", "queued_at", "filename"}


def enqueue(
    filename: str,
    vendor: str,
    description: str,
    date: str | None,
    amount: float,
    paid: bool,
    predicted_account: str,
    confidence: float,
    needs_review: bool,
    rejection_reason: str | None,
    entry_json: str,
    path: str | Path | None = None,
    decided_by: str = "",
    date_written: str = "",
    date_assumed: bool = False,
    scored_with: str = "",
) -> str:
    """Persist a processed-but-unconfirmed result and return its id."""
    path = resolve("pending_queue.csv", PENDING_PATH, path)
    path.parent.mkdir(parents=True, exist_ok=True)
    item_id = uuid.uuid4().hex[:12]
    with queue_lock():
        _upgrade_header(path)
        with path.open("a", newline="") as f:
            is_new = f.tell() == 0
            writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
            if is_new:
                writer.writeheader()
            writer.writerow({
                "id": item_id,
                "queued_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "filename": filename,
                "vendor": vendor,
                "description": description,
                "date": date or "",
                "amount": amount,
                "paid": paid,
                "predicted_account": predicted_account,
                "confidence": confidence,
                "needs_review": needs_review,
                "rejection_reason": rejection_reason or "",
                "entry_json": entry_json,
                "decided_by": decided_by or "",
                "date_written": date_written or "",
                "date_assumed": "True" if date_assumed else "",
                "scored_with": scored_with or "",
            })
    return item_id


def _upgrade_header(path: Path) -> None:
    """A queue file written before a column was added is rewritten once with
    the current header, so appending a longer row never shifts columns."""
    if not path.exists() or path.stat().st_size == 0:
        return
    with path.open(newline="") as f:
        header = next(csv.reader(f), [])
    if header != FIELDNAMES:
        _write_rows(path, read_pending(path))


def read_pending(path: str | Path | None = None) -> list[dict]:
    path = resolve("pending_queue.csv", PENDING_PATH, path)
    if not path.exists():
        return []
    with path.open(newline="") as f:
        # Normalised to the current columns: a missing one (an old row) is "".
        rows = [{name: row.get(name) or "" for name in FIELDNAMES} for row in csv.DictReader(f)]
    order = None
    for row in rows:
        # A row queued before dates were stored as YYYY-MM-DD keeps the
        # date as written; read it the same way a new document is.
        if row["date"] and not _ISO_DATE.fullmatch(row["date"]):
            order = order or preferences.date_order()
            reading = to_iso(row["date"], order)
            if reading is not None:
                row["date_written"] = row["date_written"] or row["date"]
                row["date"] = reading.iso
                row["date_assumed"] = "True" if reading.assumed else ""
    return rows


def get_pending(item_id: str, path: str | Path | None = None) -> dict | None:
    for row in read_pending(path):
        if row["id"] == item_id:
            return row
    return None


def remove_pending(item_id: str, path: str | Path | None = None) -> bool:
    """Remove one item (confirmed, corrected, or dismissed). Returns False
    if the id wasn't found -- lets callers 404 instead of silently no-op'ing
    on a stale id (e.g. two tabs racing to confirm the same document)."""
    path = resolve("pending_queue.csv", PENDING_PATH, path)
    with queue_lock():
        rows = read_pending(path)
        remaining = [row for row in rows if row["id"] != item_id]
        if len(remaining) == len(rows):
            return False
        _write_rows(path, remaining)
    return True


def update_pending(item_id: str, fields: dict, path: str | Path | None = None) -> bool:
    """Rewrite some fields of one pending item (an edited draft). Returns
    False if the id wasn't found. Only EDITABLE_FIELDS may change; anything
    else is a programming error and raises ValueError."""
    unknown = set(fields) - EDITABLE_FIELDS
    if unknown:
        raise ValueError(f"not an editable queue field: {sorted(unknown)}")
    path = resolve("pending_queue.csv", PENDING_PATH, path)
    with queue_lock():
        rows = read_pending(path)
        for row in rows:
            if row["id"] == item_id:
                row.update({key: "" if value is None else value for key, value in fields.items()})
                break
        else:
            return False
        _write_rows(path, rows)
    return True


def _write_rows(path: Path, rows: list[dict]) -> None:
    # Write a temp file then os.replace: a crash or full disk mid-write
    # leaves the old queue intact instead of a truncated one.
    fd, tmp_name = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
            writer.writeheader()
            writer.writerows(rows)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_name, path)
    except BaseException:
        Path(tmp_name).unlink(missing_ok=True)
        raise
