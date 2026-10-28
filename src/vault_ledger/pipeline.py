"""End-to-end wiring (Report 1, item 7 / Milestone 5).

document path -> proposed journal entry (or manual-review flag).

This is the first real internal milestone: one function that chains every
stage together. Deliberately raw (a function you can call from a CLI or a
test), not a UI -- Report 1 explicitly scopes a polished correction UI out
of the MVP.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, replace
from pathlib import Path

from vault_ledger.classifier.fast_inference import FAST_MODEL_PATH, FastClassifier
from vault_ledger.coa import GENERAL_EXPENSE, active_expense_accounts
from vault_ledger.confidence_gate import needs_manual_review
from vault_ledger.extraction.dates import DAY_FIRST, to_iso
from vault_ledger.extraction.field_parser import document_date_order, parse_fields
from vault_ledger.extraction.ocr import extract_raw_text
from vault_ledger.rules.entry_rules import JournalEntry, RuleViolation, construct_entry


@dataclass(frozen=True)
class PipelineResult:
    vendor: str
    description: str
    predicted_account: str
    confidence: float
    needs_review: bool
    entry: JournalEntry | None
    rejection_reason: str | None
    amount: float
    paid: bool
    date: str | None
    decided_by: str = ""  # which model in the cascade made the prediction
    date_written: str = ""  # the date as on the document; `date` is YYYY-MM-DD
    date_assumed: bool = False  # day/month order came from the setting: check it


# Bump when what the classifier is given changes (as when dates became
# YYYY-MM-DD), so queue items scored the old way are scored again.
SCORING_INPUTS_VERSION = "2"


def scoring_version(classifier) -> str:
    """Which models, fed which inputs, produced a score. A queued item whose
    stored version differs from the current one is re-scored (app.py), so the
    card and the edit preview always show the same model's answer."""
    models = getattr(classifier, "stage_names", None) or [type(classifier).__name__]
    return f"{SCORING_INPUTS_VERSION}:" + "|".join(models)


def run_pipeline(document_path: str | Path, classifier, date_order: str = DAY_FIRST) -> PipelineResult:
    raw_text = extract_raw_text(document_path)
    fields = parse_fields(raw_text)
    # Dates leave extraction as written; everything after this point (the
    # model, the queue, the duplicate check) works with YYYY-MM-DD.
    reading = to_iso(fields.date, date_order, document_date_order(raw_text)) if fields.date else None
    result = propose_entry(
        fields.vendor, fields.description, fields.amount, fields.paid,
        reading.iso if reading else None, classifier,
    )
    return replace(
        result,
        date_written=fields.date or "",
        date_assumed=bool(reading and reading.assumed),
        # An order taken from the setting, not the document, is a human's call.
        needs_review=result.needs_review or bool(reading and reading.assumed),
    )


def propose_entry(
    vendor: str, description: str, amount: float, paid: bool, date: str | None, classifier
) -> PipelineResult:
    """Everything after extraction: classify, gate, construct the entry.
    Split out of run_pipeline so a caller that already has the fields (the
    demo seed, vault_ledger.demo) goes through the same classifier, the same
    confidence gate and the same rules layer as a scanned document."""
    if hasattr(classifier, "decide"):  # the cascade: most engineered model first
        predicted_account, confidence, decided_by = classifier.decide(vendor, description, amount, paid, date)
    elif hasattr(classifier, "predict_document"):  # DragoNet also uses amount, paid and date
        predicted_account, confidence = classifier.predict_document(vendor, description, amount, paid, date)
        decided_by = "dragonet"
    else:
        predicted_account, confidence = classifier.predict(vendor, description)
        decided_by = "tfidf"
    review_flag = needs_manual_review(confidence)

    # The model can still predict an account that has since been retired
    # (it was trained on it). Don't propose a retired account: fall back to
    # the always-active catch-all and force a human look.
    if predicted_account not in active_expense_accounts():
        predicted_account = GENERAL_EXPENSE
        review_flag = True

    try:
        entry = construct_entry(predicted_account, amount, paid)
        rejection_reason = None
    except RuleViolation as exc:
        entry = None
        rejection_reason = str(exc)
        review_flag = True

    return PipelineResult(
        vendor=vendor,
        description=description,
        predicted_account=predicted_account,
        confidence=confidence,
        needs_review=review_flag,
        entry=entry,
        rejection_reason=rejection_reason,
        amount=amount,
        paid=paid,
        date=date,
        decided_by=decided_by,
    )


def _load_or_train_classifier():
    """The app's classifier: DragoNet runs first, TF-IDF as the last fallback
    (see classifier/cascade.py)."""
    from vault_ledger.classifier.cascade import build_cascade

    return build_cascade(_load_or_train_tfidf)


def _load_or_train_tfidf() -> FastClassifier:
    fast_path = Path(FAST_MODEL_PATH)
    # Training/export is the only path that needs the sklearn stack.
    from vault_ledger.classifier.train import MODEL_PATH, main as train_and_save_model

    joblib_path = Path(MODEL_PATH)
    if not fast_path.exists():
        train_and_save_model()
    elif joblib_path.exists() and joblib_path.stat().st_mtime > fast_path.stat().st_mtime:
        # The sklearn model was saved by something other than train.main()
        # (older checkout, evaluate script): re-export so serving isn't stale.
        from vault_ledger.classifier.fast_inference import export_fast_model
        from vault_ledger.classifier.fusion_classifier import FusionClassifier

        export_fast_model(FusionClassifier.load(joblib_path), fast_path)
    return FastClassifier.load(fast_path)


def main() -> None:
    if len(sys.argv) != 2:
        print("usage: python -m vault_ledger.pipeline <document_image_path>")
        raise SystemExit(1)

    classifier = _load_or_train_classifier()
    result = run_pipeline(sys.argv[1], classifier)

    print(f"vendor:      {result.vendor}")
    print(f"description: {result.description}")
    print(f"account:     {result.predicted_account}  (confidence {result.confidence:.2f})")
    print(f"model:       {result.decided_by}")
    print(f"review:      {'YES - send to manual review queue' if result.needs_review else 'no'}")

    if result.entry:
        print("proposed journal entry:")
        for line in result.entry.lines:
            print(f"  {line.account:<28} debit={line.debit:>10.2f}  credit={line.credit:>10.2f}")
        print(f"  (debits {result.entry.total_debits} == credits {result.entry.total_credits})")
    else:
        print(f"no entry constructed: {result.rejection_reason}")


if __name__ == "__main__":
    main()
