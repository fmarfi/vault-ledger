"""Investor/customer-facing demo web app for the Vault Ledger MVP.

A thin Flask layer over the existing pipeline (`vault_ledger.pipeline`) --
no business logic lives here, it only calls the same functions the CLI and
test suite already use. Run with:

    python -m vault_ledger.webapp.app

Then open http://127.0.0.1:5050
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from flask import Flask, jsonify, request, send_from_directory
from flask import render_template

from vault_ledger.classifier.fusion_classifier import FusionClassifier
from vault_ledger.coa import EXPENSE_ACCOUNTS
from vault_ledger.corrections import record_correction
from vault_ledger.pipeline import PipelineResult, _load_or_train_classifier, run_pipeline
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


def _serialize_result(result: PipelineResult) -> dict:
    return {
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
    return render_template("index.html")


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
        suffix = Path(upload.filename).suffix or ".png"
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            upload.save(tmp.name)
            document_path = tmp.name
    else:
        sample_name = (request.json or {}).get("sample")
        matching = [s for s in SAMPLES if s.name == sample_name]
        if not matching:
            return jsonify({"error": "no document uploaded and no valid sample selected"}), 400
        document_path = DOCUMENTS_DIR / f"{sample_name}.png"

    try:
        result = run_pipeline(document_path, classifier)
    except Exception as exc:  # noqa: BLE001 -- surfaced to the demo UI, not swallowed
        return jsonify({"error": str(exc)}), 422

    return jsonify(_serialize_result(result))


@app.route("/api/correct", methods=["POST"])
def api_correct():
    body = request.json or {}
    corrected_account = body.get("corrected_account")

    if corrected_account not in EXPENSE_ACCOUNTS:
        return jsonify({"error": f"'{corrected_account}' is not in the fixed chart of accounts"}), 400

    try:
        entry = construct_entry(corrected_account, float(body["amount"]), bool(body["paid"]))
    except RuleViolation as exc:
        return jsonify({"error": str(exc)}), 422

    record_correction(
        vendor=body.get("vendor", ""),
        description=body.get("description", ""),
        predicted_account=body.get("predicted_account", ""),
        corrected_account=corrected_account,
        amount=float(body["amount"]),
        date=body.get("date"),
    )

    return jsonify({"entry": _serialize_entry(entry)})


def main() -> None:
    app.run(debug=True, port=5050)


if __name__ == "__main__":
    main()
