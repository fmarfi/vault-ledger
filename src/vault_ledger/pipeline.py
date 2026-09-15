"""End-to-end wiring (Report 1, item 7 / Milestone 5).

document path -> proposed journal entry (or manual-review flag).

This is the first real internal milestone: one function that chains every
stage together. Deliberately raw (a function you can call from a CLI or a
test), not a UI -- Report 1 explicitly scopes a polished correction UI out
of the MVP.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

from vault_ledger.classifier.fusion_classifier import FusionClassifier
from vault_ledger.classifier.train import MODEL_PATH, main as train_and_save_model
from vault_ledger.confidence_gate import needs_manual_review
from vault_ledger.extraction.field_parser import parse_fields
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


def run_pipeline(document_path: str | Path, classifier: FusionClassifier) -> PipelineResult:
    raw_text = extract_raw_text(document_path)
    fields = parse_fields(raw_text)

    predicted_account, confidence = classifier.predict(fields.vendor, fields.description)
    review_flag = needs_manual_review(confidence)

    try:
        entry = construct_entry(predicted_account, fields.amount, fields.paid)
        rejection_reason = None
    except RuleViolation as exc:
        entry = None
        rejection_reason = str(exc)
        review_flag = True

    return PipelineResult(
        vendor=fields.vendor,
        description=fields.description,
        predicted_account=predicted_account,
        confidence=confidence,
        needs_review=review_flag,
        entry=entry,
        rejection_reason=rejection_reason,
        amount=fields.amount,
        paid=fields.paid,
        date=fields.date,
    )


def _load_or_train_classifier() -> FusionClassifier:
    if not Path(MODEL_PATH).exists():
        train_and_save_model()
    return FusionClassifier.load(MODEL_PATH)


def main() -> None:
    if len(sys.argv) != 2:
        print("usage: python -m vault_ledger.pipeline <document_image_path>")
        raise SystemExit(1)

    classifier = _load_or_train_classifier()
    result = run_pipeline(sys.argv[1], classifier)

    print(f"vendor:      {result.vendor}")
    print(f"description: {result.description}")
    print(f"account:     {result.predicted_account}  (confidence {result.confidence:.2f})")
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
