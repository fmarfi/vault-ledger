# Vault Ledger MVP

Invoice-in -> journal-entry-out pipeline. See `report-1-mvp-technicalities.md`,
`report-3-building-with-claude-code.md`, and `report-4-paper-reference-digest.md`
for the full design rationale this scaffold implements.

## Pipeline

```
document (image) -> OCR -> field parsing (vendor, description, date, amount)
                 -> two-field fusion classifier -> account + confidence
                 -> confidence gate -> deterministic debit/credit rules
                 -> proposed journal entry
```

## Setup

```
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"
brew install tesseract   # required for OCR; see note below
```

**Known local blocker:** on this machine, `brew install tesseract` was
blocked by a pre-existing permissions issue unrelated to tesseract itself
(`/usr/local/share/man/man5` not writable by the current user). Fix once:

```
sudo chown -R $(whoami) /usr/local/share/man/man5
brew install tesseract
```

Everything except the real-OCR integration tests works without tesseract
installed (see Testing below) -- field parsing, the classifier, and the
rules layer are all tested independently of it.

## Running the demo

### CLI

```
.venv/bin/python data/synthetic/generate_documents.py   # generates 3 sample doc images
.venv/bin/python -m vault_ledger.pipeline data/synthetic/documents/invoice_office_supplies.png
```

Prints the parsed fields, predicted account + confidence, review flag, and
the proposed journal entry (or the rejection reason if the rules layer
refused it).

### Web app (investor/customer-facing demo)

```
.venv/bin/python -m vault_ledger.webapp.app
```

Opens a Flask dev server at http://127.0.0.1:5050 — a single-page demo with
the pipeline diagram, one-click sample documents (or upload your own),
extracted fields, predicted account with a confidence bar, the proposed
journal entry, and an accept/correct control that exercises the M7
correction loop live. It's a thin UI layer over `vault_ledger.pipeline` --
no separate business logic. Not a production deployment (Flask dev server,
single in-memory classifier instance).

## Testing

```
.venv/bin/python -m pytest tests/ -v
```

The 3 end-to-end OCR tests in `test_pipeline.py` auto-skip if `tesseract`
isn't on PATH; everything else (rules layer, field parsing, classifier)
runs without it.

## Chart of accounts (fixed, 8 accounts)

Cash/Bank, Accounts Payable, Utilities Expense, Office Supplies Expense,
Professional Services Expense, Rent Expense, Travel & Transport Expense,
General/Other Expense. See `src/vault_ledger/coa.py`.

## Claude Code tooling

- `.claude/skills/` -- domain procedures (OCR extraction, classifier,
  entry rules, milestone definitions).
- `.claude/agents/` -- `ocr-runner`, `classifier-eval`, `rules-validator`
  subagents for isolated, repeatable work on each pipeline stage.
- `.claude/settings.json` -- a hook that runs the entry-rules test suite
  automatically on edits to the rules layer and blocks on failure.

## Known limitations (by design, for this pass)

- **All data is synthetic/placeholder**: `data/synthetic/labeled_transactions.csv`
  (17 hand-written rows) and the 3 generated document images exist only to
  prove the pipeline runs end-to-end. Any accuracy number from
  `classifier/evaluate.py` is a pipeline sanity check, not a validated metric
  -- do not quote it as real performance.
- No real pilot run (M8), no per-client custom COA, no fraud/anomaly
  detection, no live retraining, no polished correction UI -- all explicitly
  out of scope for this MVP pass per Report 1.
- The web app is a demo UI, not a production accountant tool -- no auth,
  no persistence beyond `corrections.csv`, single-process Flask dev server.

## Milestone status

See `.claude/skills/vault-ledger-milestone-check/SKILL.md` for the full
M1-M8 definitions. As of this scaffold: M1-M7 implemented and tested
(M7's retraining step is manual/periodic by design, run via
`python -m vault_ledger.classifier.apply_corrections`); M8 not started
(needs real data).
