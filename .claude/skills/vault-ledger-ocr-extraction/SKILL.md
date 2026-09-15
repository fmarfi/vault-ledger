---
name: vault-ledger-ocr-extraction
description: How to run and validate OCR extraction against Vault Ledger's 3 target document formats (invoice, utility bill, receipt), including the mandatory vendor/description separation checkpoint.
---

# Vault Ledger OCR extraction

## Scope

Exactly 3 target document formats for the MVP: generic itemized vendor
invoice, utility-style bill, retail receipt. No other formats are in scope
yet (Report 1, "Explicitly NOT ASAP").

## Tooling

- OCR: `pytesseract` wrapping the `tesseract` binary
  (`src/vault_ledger/extraction/ocr.py`). Requires `tesseract` installed via
  `brew install tesseract` on macOS -- this is a real external dependency,
  check `which tesseract` before assuming OCR tests will run.
- Field parsing: regex/position heuristics, not ML
  (`src/vault_ledger/extraction/field_parser.py`). Report 1 is explicit that
  this doesn't need ML for the 3 target formats.
- Synthetic samples: `src/vault_ledger/synthetic_samples.py` is the single
  source of truth for the 3 canonical sample documents, used by both the
  image generator (`data/synthetic/generate_documents.py`) and the tests.

## The mandatory checkpoint: vendor/description separation

Report 1's single biggest flagged risk: the two-field classifier gain is
entirely dependent on extraction quality. If vendor and description bleed
together into one string, the classifier never gets the benefit that
justified the two-field design.

**Every time extraction or field-parsing logic changes, run
`tests/test_field_parser.py::test_vendor_and_description_are_separate_fields`
and treat a failure as blocking** -- not a warning, not a "fix later." This
is a standalone checkpoint independent of classifier accuracy, per Report 1.

## How to run and validate against a new sample

1. Add the new sample to `src/vault_ledger/synthetic_samples.py` (or, once
   real documents exist, a real-document equivalent) with its expected
   vendor/description/amount/paid values.
2. Regenerate images: `python data/synthetic/generate_documents.py`.
3. Run OCR: `extract_raw_text(path)` from `ocr.py`.
4. Run field parsing: `parse_fields(raw_text)` from `field_parser.py`.
5. Assert the separation checkpoint above, then assert the parsed fields
   match expectations.

## What NOT to do

- Don't optimize OCR accuracy yet -- the loop working end-to-end is the
  priority, not extraction accuracy (Report 1, item 2).
- Don't reach for deep OCR models. Report 4's SME-paper benchmarks show
  template-matching and layout-feature approaches hit 95%+ on structured
  documents cheaply -- consistent with treating this as an engineering
  problem, not a research one.
- Don't let extraction merge vendor and description "just this once" for
  convenience -- see the checkpoint above.
