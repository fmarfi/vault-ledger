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

import json
import tempfile
from pathlib import Path

from flask import Flask, jsonify, request, send_from_directory
from flask import render_template

from vault_ledger.classifier.fusion_classifier import FusionClassifier
from vault_ledger.coa import EXPENSE_ACCOUNTS
from vault_ledger.corrections import record_correction
from vault_ledger.ledger import append_entry, entries_by_account, read_entries
from vault_ledger.pipeline import PipelineResult, _load_or_train_classifier, run_pipeline
from vault_ledger.queue import enqueue, get_pending, read_pending, remove_pending
from vault_ledger.rules.entry_rules import RuleViolation, construct_entry
from vault_ledger.synthetic_samples import SAMPLES

DOCUMENTS_DIR = Path(__file__).resolve().parents[3] / "data" / "synthetic" / "documents"

app = Flask(__name__)
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
    return jsonify(sorted(EXPENSE_ACCOUNTS))


@app.route("/api/process", methods=["POST"])
def api_process():
    classifier = _get_classifier()

    if "document" in request.files and request.files["document"].filename:
        upload = request.files["document"]
        filename = upload.filename
        suffix = Path(filename).suffix or ".png"
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            upload.save(tmp.name)
            document_path = tmp.name
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


def _confirm_pending_item(item_id: str, corrected_account: str | None) -> dict:
    """Shared by /api/confirm, /api/correct, and bulk confirm: look up a
    pending item, post it to the ledger under `corrected_account` (or its
    own predicted_account if None), and remove it from the queue. Raises
    ValueError (bad id / bad account) or RuleViolation (unbalanced entry)
    -- callers translate those into the right HTTP response."""
    row = get_pending(item_id)
    if row is None:
        raise ValueError(f"no pending item with id '{item_id}'")

    account = corrected_account or row["predicted_account"]
    if account not in EXPENSE_ACCOUNTS:
        raise ValueError(f"'{account}' is not in the fixed chart of accounts")

    amount = float(row["amount"])
    paid = _str_to_bool(row["paid"])
    entry = construct_entry(account, amount, paid)  # raises RuleViolation

    if corrected_account and corrected_account != row["predicted_account"]:
        record_correction(
            vendor=row["vendor"],
            description=row["description"],
            predicted_account=row["predicted_account"],
            corrected_account=corrected_account,
            amount=amount,
            date=row["date"],
        )

    append_entry(
        filename=row["filename"],
        vendor=row["vendor"],
        description=row["description"],
        date=row["date"],
        amount=amount,
        account=account,
        confidence=float(row["confidence"]),
        was_corrected=bool(corrected_account and corrected_account != row["predicted_account"]),
    )
    remove_pending(item_id)
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
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 404 if "no pending item" in str(exc) else 400
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
    if corrected_account not in EXPENSE_ACCOUNTS:
        return jsonify({"error": f"'{corrected_account}' is not in the fixed chart of accounts"}), 400

    try:
        result = _confirm_pending_item(item_id, corrected_account=corrected_account)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 404 if "no pending item" in str(exc) else 400
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
    for item_id in ids:
        try:
            _confirm_pending_item(item_id, corrected_account=None)
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


@app.route("/api/ledger")
def api_ledger():
    grouped = entries_by_account()
    return jsonify(
        {
            account: {
                "total": round(sum(float(e["amount"]) for e in entries), 2),
                "entries": sorted(entries, key=lambda e: e.get("date", ""), reverse=True),
            }
            for account, entries in grouped.items()
        }
    )


def main() -> None:
    app.run(debug=True, port=5050)


if __name__ == "__main__":
    main()
