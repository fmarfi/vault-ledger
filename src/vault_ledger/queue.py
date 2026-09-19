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
"""

from __future__ import annotations

import csv
import os
import tempfile
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path

PENDING_PATH = Path(__file__).resolve().parents[2] / "data" / "pending_queue.csv"
# One lock for every read-modify-write on the queue file, and for the
# confirm flow in app.py (get -> post to ledger -> remove) so two tabs or a
# double-click can't both post the same item. RLock: confirm holds it while
# calling remove_pending, which takes it again. Single-process only, which
# matches the on-device, single-user deployment.
QUEUE_LOCK = threading.RLock()
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
]


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
    path: str | Path = PENDING_PATH,
) -> str:
    """Persist a processed-but-unconfirmed result and return its id."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    item_id = uuid.uuid4().hex[:12]
    with QUEUE_LOCK, path.open("a", newline="") as f:
        is_new = f.tell() == 0
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        if is_new:
            writer.writeheader()
        writer.writerow(
            {
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
            }
        )
    return item_id


def read_pending(path: str | Path = PENDING_PATH) -> list[dict]:
    path = Path(path)
    if not path.exists():
        return []
    with path.open(newline="") as f:
        return list(csv.DictReader(f))


def get_pending(item_id: str, path: str | Path = PENDING_PATH) -> dict | None:
    for row in read_pending(path):
        if row["id"] == item_id:
            return row
    return None


def remove_pending(item_id: str, path: str | Path = PENDING_PATH) -> bool:
    """Remove one item (confirmed, corrected, or dismissed). Returns False
    if the id wasn't found -- lets callers 404 instead of silently no-op'ing
    on a stale id (e.g. two tabs racing to confirm the same document)."""
    path = Path(path)
    with QUEUE_LOCK:
        rows = read_pending(path)
        remaining = [row for row in rows if row["id"] != item_id]
        if len(remaining) == len(rows):
            return False
        # Write a temp file then os.replace: a crash or full disk mid-write
        # leaves the old queue intact instead of a truncated one.
        fd, tmp_name = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
        try:
            with os.fdopen(fd, "w", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
                writer.writeheader()
                writer.writerows(remaining)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp_name, path)
        except BaseException:
            Path(tmp_name).unlink(missing_ok=True)
            raise
    return True
