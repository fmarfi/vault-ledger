---
name: vault-ledger-milestone-check
description: Given a Vault Ledger milestone number (M1-M8), states what "done" looks like and what to demo. Keeps milestone definitions authoritative in the repo rather than only in chat history.
---

# Vault Ledger milestone definitions

Reconstructed from Report 1's priority list and Report 3's mapping table
(the original Report 2 milestone document is not present in this repo).

| # | Milestone | Done when... |
|---|---|---|
| M1 | Fixed COA + deterministic debit/credit rules layer | `coa.py` has the 8 accounts; `entry_rules.py` enforces all 5 invariants in `rules_spec.json`; `tests/test_entry_rules.py` passes, covering paid/unpaid/zero/negative/unknown-account/mechanical-account cases. |
| M2 | OCR extraction on 3 target formats | `extract_raw_text()` runs against a real (or synthetic) sample of each of the 3 formats and returns non-empty text. |
| M3 | Field separation validated | `test_vendor_and_description_are_separate_fields` passes for all 3 formats -- this is its own checkpoint, not folded into M2. |
| M4 | Two-field fusion classifier | `FusionClassifier.fit()` trains on labeled data with vendor+description as separate inputs; `predict()` returns `(account, confidence)`; `tests/test_fusion_classifier.py` passes, including the "unseen vendor, known description" case. |
| M5 | End-to-end wiring | `python -m vault_ledger.pipeline <doc>` runs the full chain and prints a proposed journal entry (or a manual-review flag) for a real document. |
| M6 | Confidence gate | `needs_manual_review()` gates on `CONFIDENCE_THRESHOLD`, wired into `pipeline.py`'s output. |
| M7 | Correction loop | Accountant corrections get appended to `corrections.csv` (vendor, description, predicted vs. corrected account) -- manual is fine, no auto-retraining required yet. |
| M8 | Real pilot run | Real documents from an actual SME/accountant, not synthetic data -- not started; requires real sample data first. |

## How to use this

When asked "is M<n> done" or "what's needed for M<n>", check the specific
condition above against the current repo state (run the relevant tests, run
the relevant script) rather than assuming from memory -- the milestone
conditions describe test/behavior outcomes, so verify them fresh each time.
