"""Investor/customer-facing demo web app for the Vault Ledger MVP.

A thin Flask layer over the existing pipeline (`vault_ledger.pipeline`) --
no business logic lives here, it only calls the same functions the CLI and
test suite already use. Run with:

    python -m vault_ledger.webapp.app

Then open http://127.0.0.1:5050

Three pages, sharing templates/base.html and static/style.css's token
system (see that file's :root for the whole design system in one place):
- / -- Review Queue. Process a document (upload or a sample) and it's
  persisted server-side the moment it's processed (queue.py) -- a real
  multi-item queue that survives a page refresh, not just in-tab state.
  Confirm or correct items one at a time, or select several and bulk-
  confirm them in one action.
- /documents -- every document that's been confirmed, from ledger.py.
- /ledger -- confirmed entries grouped by account, with running totals.

An item lands in queue.py the moment /api/process runs, and leaves the
moment it's confirmed, corrected, or dismissed. It only reaches ledger.py
once confirmed -- matches real bookkeeping, where a proposal isn't part of
the books until an accountant confirms it.
"""

from __future__ import annotations

import io
import json
import logging
import math
import tempfile
from datetime import datetime
from pathlib import Path

from flask import Flask, jsonify, request, send_file, send_from_directory
from flask import render_template

from vault_ledger.classifier.fusion_classifier import FusionClassifier
from vault_ledger import backup, coa, hardware
from vault_ledger.stats import compute_stats
from vault_ledger.corrections import record_correction
from vault_ledger.ledger import append_entry, read_entries
from vault_ledger.pipeline import PipelineResult, _load_or_train_classifier, run_pipeline
from vault_ledger.queue import QUEUE_LOCK, enqueue, get_pending, read_pending, remove_pending
from vault_ledger.rules.entry_rules import RuleViolation, construct_entry
from vault_ledger.synthetic_samples import SAMPLES

DOCUMENTS_DIR = Path(__file__).resolve().parents[3] / "data" / "synthetic" / "documents"

app = Flask(__name__)
log = logging.getLogger(__name__)


class PendingNotFound(ValueError):
    """The queue has no item with that id (already confirmed, dismissed, or stale)."""


class NeedsIndividualReview(ValueError):
    """A flagged item was submitted through the bulk path. Ambiguity escalates
    to a human -- only a per-item confirm/correct may post it."""
_classifier: FusionClassifier | None = None


def _get_classifier() -> FusionClassifier:
    global _classifier
    if _classifier is None:
        _classifier = _load_or_train_classifier()
    return _classifier


def _str_to_bool(value: str) -> bool:
    return value == "True"


def _serialize_result(result: PipelineResult, filename: str, item_id: str | None = None) -> dict:
    return {
        "id": item_id,
        "filename": filename,
        "vendor": result.vendor,
        "description": result.description,
        "date": result.date,
        "amount": result.amount,
        "paid": result.paid,
        "predicted_account": result.predicted_account,
        "confidence": round(result.confidence, 4),
        "needs_review": result.needs_review,
        "rejection_reason": result.rejection_reason,
        "entry": _serialize_entry(result.entry),
    }


def _serialize_entry(entry) -> dict | None:
    if entry is None:
        return None
    return {
        "lines": [
            {"account": line.account, "debit": line.debit, "credit": line.credit}
            for line in entry.lines
        ],
        "total_debits": entry.total_debits,
        "total_credits": entry.total_credits,
    }


@app.route("/")
def index():
    return render_template("index.html", active_page="review")


@app.route("/documents")
def documents_page():
    return render_template("documents.html", active_page="documents")


@app.route("/ledger")
def ledger_page():
    return render_template("ledger.html", active_page="ledger")


@app.route("/api/samples")
def api_samples():
    return jsonify(
        [
            {
                "name": sample.name,
                "format_type": sample.format_type,
                "image_url": f"/samples/{sample.name}.png",
            }
            for sample in SAMPLES
        ]
    )


@app.route("/samples/<path:filename>")
def sample_image(filename: str):
    return send_from_directory(DOCUMENTS_DIR, filename)


@app.route("/api/accounts")
def api_accounts():
    return jsonify(sorted(coa.active_expense_accounts()))


@app.route("/settings")
def settings_page():
    return render_template("settings.html", active_page="settings")


@app.route("/api/accounts/manage")
def api_accounts_manage():
    return jsonify(
        {
            "active": sorted(coa.active_expense_accounts()),
            "retired": coa.retired_expense_accounts(),
            "templates": {name: accounts for name, accounts in coa.TEMPLATES.items()},
            "protected": coa.GENERAL_EXPENSE,
        }
    )


def _account_action(action):
    try:
        action()
    except coa.AccountError as exc:
        return jsonify({"error": str(exc)}), 400
    return api_accounts_manage()


@app.route("/api/accounts/add", methods=["POST"])
def api_accounts_add():
    name = (request.json or {}).get("name", "")
    return _account_action(lambda: coa.add_expense_account(name))


@app.route("/api/accounts/retire", methods=["POST"])
def api_accounts_retire():
    name = (request.json or {}).get("name", "")
    return _account_action(lambda: coa.retire_expense_account(name))


@app.route("/api/accounts/template", methods=["POST"])
def api_accounts_template():
    template = (request.json or {}).get("template", "")
    return _account_action(lambda: coa.apply_template(template))


@app.route("/api/backup")
def api_backup():
    stamp = datetime.now().strftime("%Y-%m-%d")
    return send_file(
        io.BytesIO(backup.create_backup()),
        mimetype="application/zip",
        as_attachment=True,
        download_name=f"vault-ledger-backup-{stamp}.zip",
    )


@app.route("/api/restore", methods=["POST"])
def api_restore():
    upload = request.files.get("backup")
    if upload is None or not upload.filename:
        return jsonify({"error": "choose a backup file first"}), 400

    # Safety net: snapshot current data next to the live files before
    # overwriting anything, so a wrong restore is itself recoverable.
    safety_dir = coa.ACCOUNTS_PATH.parent / "backups"
    safety_dir.mkdir(parents=True, exist_ok=True)
    safety_name = f"pre-restore-{datetime.now().strftime('%Y%m%d-%H%M%S')}.zip"
    (safety_dir / safety_name).write_bytes(backup.create_backup())

    try:
        restored = backup.restore_backup(upload.read())
    except backup.BackupError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify({"restored": restored, "safety_copy": safety_name})


@app.route("/api/process", methods=["POST"])
def api_process():
    classifier = _get_classifier()

    temp_path: str | None = None
    if "document" in request.files and request.files["document"].filename:
        upload = request.files["document"]
        filename = upload.filename
        suffix = Path(filename).suffix or ".png"
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            upload.save(tmp.name)
            document_path = temp_path = tmp.name
    else:
        sample_name = (request.json or {}).get("sample")
        matching = [s for s in SAMPLES if s.name == sample_name]
        if not matching:
            return jsonify({"error": "no document uploaded and no valid sample selected"}), 400
        filename = f"{sample_name}.png"
        document_path = DOCUMENTS_DIR / filename

    try:
        result = run_pipeline(document_path, classifier)
    except Exception as exc:  # noqa: BLE001 -- surfaced to the demo UI, not swallowed
        return jsonify({"error": str(exc)}), 422
    finally:
        # An uploaded document is sensitive; don't leave copies in the temp dir.
        if temp_path:
            Path(temp_path).unlink(missing_ok=True)

    item_id = enqueue(
        filename=filename,
        vendor=result.vendor,
        description=result.description,
        date=result.date,
        amount=result.amount,
        paid=result.paid,
        predicted_account=result.predicted_account,
        confidence=result.confidence,
        needs_review=result.needs_review,
        rejection_reason=result.rejection_reason,
        entry_json=json.dumps(_serialize_entry(result.entry)),
    )

    return jsonify(_serialize_result(result, filename, item_id))


@app.route("/api/queue")
def api_queue():
    """Every processed-but-not-yet-confirmed document, oldest first --
    the persistent review queue (diagnostics report, feature 1)."""
    items = read_pending()
    items.sort(key=lambda row: row.get("queued_at", ""))
    return jsonify(items)


@app.route("/api/queue/<item_id>", methods=["DELETE"])
def api_queue_dismiss(item_id: str):
    """Discard a pending item without posting it anywhere -- e.g. a bad
    scan the user doesn't want to keep re-seeing in the queue."""
    if not remove_pending(item_id):
        return jsonify({"error": f"no pending item with id '{item_id}'"}), 404
    return jsonify({"dismissed": item_id})


def _confirm_pending_item(
    item_id: str, corrected_account: str | None, allow_flagged: bool = True
) -> dict:
    """Shared by /api/confirm, /api/correct, and bulk confirm: look up a
    pending item, post it to the ledger under `corrected_account` (or its
    own predicted_account if None), and remove it from the queue. Raises
    PendingNotFound / NeedsIndividualReview / ValueError (bad account or
    amount) or RuleViolation (unbalanced entry) -- callers translate those
    into the right HTTP response.

    Runs under QUEUE_LOCK so a double-click or two tabs can't both post the
    same item. Bulk confirm passes allow_flagged=False: an item the pipeline
    flagged needs_review (vendor/amount ambiguity, low confidence gate) must
    be resolved by a human individually, never posted on a guess."""
    with QUEUE_LOCK:
        row = get_pending(item_id)
        if row is None:
            raise PendingNotFound(f"no pending item with id '{item_id}'")

        if not allow_flagged and (row["needs_review"] == "True" or row["rejection_reason"]):
            raise NeedsIndividualReview("flagged for review -- confirm or correct it individually")

        account = corrected_account or row["predicted_account"]
        if account not in coa.active_expense_accounts():
            raise ValueError(f"'{account}' is not an active account in the chart of accounts")

        try:
            amount = float(row["amount"])
        except (TypeError, ValueError):
            raise ValueError(f"queued item has an unreadable amount: {row['amount']!r}") from None
        if not math.isfinite(amount) or amount <= 0:
            raise ValueError(f"queued item has an invalid amount: {amount}")
        paid = _str_to_bool(row["paid"])
        entry = construct_entry(account, amount, paid)  # raises RuleViolation

        was_corrected = bool(corrected_account and corrected_account != row["predicted_account"])
        # Post first, then log the correction: if the ledger write fails the
        # item stays pending and no training signal was recorded yet.
        append_entry(
            filename=row["filename"],
            vendor=row["vendor"],
            description=row["description"],
            date=row["date"],
            amount=amount,
            account=account,
            confidence=float(row["confidence"]),
            was_corrected=was_corrected,
        )
        remove_pending(item_id)
        if was_corrected:
            record_correction(
                vendor=row["vendor"],
                description=row["description"],
                predicted_account=row["predicted_account"],
                corrected_account=corrected_account,
                amount=amount,
                date=row["date"],
            )
    return {"entry": _serialize_entry(entry)}


@app.route("/api/confirm", methods=["POST"])
def api_confirm():
    """Accept a queued item's predicted account as-is -- it becomes part
    of the posted ledger and leaves the pending queue. No training signal
    here (the prediction wasn't wrong); see /api/correct for the case that
    also logs a correction."""
    body = request.json or {}
    item_id = body.get("id")
    if not item_id:
        return jsonify({"error": "'id' is required"}), 400

    try:
        result = _confirm_pending_item(item_id, corrected_account=None)
    except PendingNotFound as exc:
        return jsonify({"error": str(exc)}), 404
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except RuleViolation as exc:
        return jsonify({"error": str(exc)}), 422

    return jsonify(result)


@app.route("/api/correct", methods=["POST"])
def api_correct():
    body = request.json or {}
    item_id = body.get("id")
    corrected_account = body.get("corrected_account")
    if not item_id:
        return jsonify({"error": "'id' is required"}), 400
    if corrected_account not in coa.active_expense_accounts():
        return jsonify({"error": f"'{corrected_account}' is not an active account in the chart of accounts"}), 400

    try:
        result = _confirm_pending_item(item_id, corrected_account=corrected_account)
    except PendingNotFound as exc:
        return jsonify({"error": str(exc)}), 404
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except RuleViolation as exc:
        return jsonify({"error": str(exc)}), 422

    return jsonify(result)


@app.route("/api/queue/bulk_confirm", methods=["POST"])
def api_bulk_confirm():
    """Confirm several pending items at once, each under its own predicted
    account (diagnostics report, feature 2). Not all-or-nothing -- one bad
    id or rule violation doesn't block the rest of the batch; every outcome
    is reported back so the UI can show exactly what happened."""
    body = request.json or {}
    ids = body.get("ids") or []
    if not isinstance(ids, list) or not ids:
        return jsonify({"error": "'ids' must be a non-empty list"}), 400

    confirmed, failed = [], []
    for item_id in dict.fromkeys(ids):  # dedupe, keep order
        try:
            _confirm_pending_item(item_id, corrected_account=None, allow_flagged=False)
            confirmed.append(item_id)
        except ValueError as exc:
            failed.append({"id": item_id, "error": str(exc)})
        except RuleViolation as exc:
            failed.append({"id": item_id, "error": str(exc)})

    return jsonify({"confirmed": confirmed, "failed": failed})


@app.route("/api/documents")
def api_documents():
    entries = read_entries()
    entries.sort(key=lambda e: e.get("confirmed_at", ""), reverse=True)
    return jsonify(entries)


@app.route("/api/stats")
def api_stats():
    return jsonify(compute_stats(read_entries()))


@app.route("/api/health")
def api_health():
    return jsonify({"hardware": hardware.check()})


@app.route("/api/ledger")
def api_ledger():
    grouped: dict[str, list[dict]] = {}
    for e in read_entries():
        try:
            float(e["amount"])
            account = e["account"]
        except (KeyError, TypeError, ValueError):
            log.warning("skipping malformed ledger row: %r", e)
            continue
        grouped.setdefault(account, []).append(e)
    return jsonify(
        {
            account: {
                "total": round(sum(float(e["amount"]) for e in entries), 2),
                "entries": sorted(entries, key=lambda e: e.get("date") or "", reverse=True),
            }
            for account, entries in grouped.items()
        }
    )


def main() -> None:
    report = hardware.check()
    if report["level"] in {"low", "critical"}:
        print(f"[hardware] {report['level'].upper()}: {report['message']}")
    app.run(debug=True, port=5050)


if __name__ == "__main__":
    main()
