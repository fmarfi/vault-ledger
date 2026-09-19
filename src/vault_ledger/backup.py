"""Manual backup & restore (diagnostics report, feature 4).

One zip holding everything a business needs to move to a new machine or
recover from a lost one: the posted ledger, the pending queue, the
corrections log, the training data, and the customized chart of accounts.
The user stores the file wherever they choose -- nothing uploads anywhere,
so the on-device promise holds.

The trained model (*.joblib) is intentionally NOT included. Unpickling a
file out of an arbitrary zip can execute code, and the model is fully
reproducible from the included training data; restore deletes any stale
model so it retrains from what was restored.
"""

from __future__ import annotations

import csv
import io
import json
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from vault_ledger import coa, corrections, ledger, queue
from vault_ledger.classifier import apply_corrections as _apply
from vault_ledger.classifier.train import MODEL_PATH

BACKUP_FORMAT_VERSION = 1
MAX_MEMBER_BYTES = 50 * 1024 * 1024

# Expected CSV header per archive member (None = JSON, validated separately).
_CSV_HEADERS = {
    "ledger.csv": ledger.FIELDNAMES,
    "pending_queue.csv": queue.FIELDNAMES,
    "corrections.csv": corrections.FIELDNAMES,
    "labeled_transactions.csv": ["vendor", "description", "account"],
}


class BackupError(ValueError):
    """Raised for an unusable backup file. Nothing has been changed when this is raised."""


def default_files() -> dict[str, Path]:
    """archive member name -> live file. Read at call time so tests can monkeypatch."""
    return {
        "ledger.csv": ledger.LEDGER_PATH,
        "pending_queue.csv": queue.PENDING_PATH,
        "corrections.csv": corrections.CORRECTIONS_PATH,
        "labeled_transactions.csv": _apply.TRAINING_DATA_PATH,
        "accounts.json": coa.ACCOUNTS_PATH,
    }


def create_backup(files: dict[str, Path] | None = None) -> bytes:
    files = files or default_files()
    buffer = io.BytesIO()
    included = []
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, path in files.items():
            if Path(path).exists():
                zf.write(path, name)
                included.append(name)
        zf.writestr(
            "manifest.json",
            json.dumps(
                {
                    "format_version": BACKUP_FORMAT_VERSION,
                    "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                    "files": included,
                },
                indent=2,
            ),
        )
    return buffer.getvalue()


def _validate(zf: zipfile.ZipFile, allowed: set[str]) -> dict[str, bytes]:
    names = set(zf.namelist())
    if "manifest.json" not in names:
        raise BackupError("this doesn't look like a Vault Ledger backup (no manifest)")
    try:
        manifest = json.loads(zf.read("manifest.json"))
    except ValueError:
        raise BackupError("backup manifest is unreadable")
    if manifest.get("format_version") != BACKUP_FORMAT_VERSION:
        raise BackupError("this backup was made by an incompatible version")

    contents: dict[str, bytes] = {}
    for info in zf.infolist():
        if info.filename == "manifest.json":
            continue
        if info.filename not in allowed:
            raise BackupError(f"unexpected file in backup: {info.filename!r}")
        if info.file_size > MAX_MEMBER_BYTES:
            raise BackupError(f"{info.filename} is too large to be a real backup member")
        contents[info.filename] = zf.read(info)

    for name, data in contents.items():
        if name == "accounts.json":
            try:
                state = json.loads(data)
                assert isinstance(state["active"], list) and isinstance(state["retired"], list)
                assert coa.GENERAL_EXPENSE in state["active"]
            except (ValueError, KeyError, AssertionError):
                raise BackupError("accounts.json in the backup is invalid")
        else:
            try:
                header = next(csv.reader(io.StringIO(data.decode("utf-8"))), [])
            except UnicodeDecodeError:
                raise BackupError(f"{name} in the backup isn't valid text")
            if header != _CSV_HEADERS[name]:
                raise BackupError(f"{name} in the backup has unexpected columns")
    return contents


def restore_backup(data: bytes, files: dict[str, Path] | None = None, model_path: Path | None = None) -> list[str]:
    """Validate everything first; only then replace live files. Returns the
    names restored. A file the backup doesn't contain is left untouched."""
    files = files or default_files()
    try:
        zf = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile:
        raise BackupError("that file isn't a zip archive")
    with zf:
        contents = _validate(zf, set(files))

    for name, payload in contents.items():
        target = Path(files[name])
        target.parent.mkdir(parents=True, exist_ok=True)
        tmp = target.with_suffix(target.suffix + ".restoring")
        tmp.write_bytes(payload)
        tmp.replace(target)

    stale_model = Path(model_path or MODEL_PATH)
    if "labeled_transactions.csv" in contents and stale_model.exists():
        stale_model.unlink()
    return sorted(contents)
