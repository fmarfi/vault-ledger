# Vault Ledger MVP

Invoice-in -> journal-entry-out pipeline. See `report-1-mvp-technicalities.md`,
`report-3-building-with-claude-code.md`, and `report-4-paper-reference-digest.md`
for the full design rationale this scaffold implements.

## Pipeline

```
document (image or PDF) -> OCR -> field parsing (vendor, description, date, amount)
                 -> two-field fusion classifier -> account + confidence
                 -> confidence gate -> deterministic debit/credit rules
                 -> proposed journal entry
```

PDFs (`src/vault_ledger/extraction/pdf.py`) try the native text layer first
(exact, no OCR needed, for born-digital PDFs) and fall back to
rasterize + OCR only for scanned/image-only PDFs. First page only. OCR
itself is deliberately **local-only** (Tesseract) -- hosted Document AI
APIs were researched and rejected for privacy reasons (see the
`vault-ledger-ocr-extraction` skill); this is a considered decision, not a
gap to fill in later.

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

**Optional, for field-parsing tier 3 (local LLM fallback):**

```
brew install --cask ollama-app   # NOT `brew install ollama` -- that formula
                                   # builds Go from source on unsupported
                                   # platforms; the cask ships a prebuilt app
ollama pull qwen2.5:1.5b-instruct
```

Only reached when tiers 1-2 (exact label match, real-world heuristics) both
fail -- see the `vault-ledger-ocr-extraction` skill. Without Ollama
installed, this tier fails closed and you just get tier 2's normal error
message; nothing breaks.

## Running the demo

### CLI

```
.venv/bin/python data/synthetic/generate_documents.py   # generates sample docs (png + native/scanned pdf)
.venv/bin/python -m vault_ledger.pipeline data/synthetic/documents/invoice_office_supplies.png
.venv/bin/python -m vault_ledger.pipeline data/synthetic/documents/invoice_office_supplies_native.pdf
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

## Chart of accounts (fixed, 9 accounts)

Cash/Bank, Accounts Payable, Utilities Expense, Office Supplies Expense,
Professional Services Expense, Rent Expense, Travel & Transport Expense,
Software & Subscriptions Expense, General/Other Expense. See
`src/vault_ledger/coa.py`. (Grown from 8 to 9 after a real SaaS billing
receipt had no honest home in the original list -- see git history and the
`vault-ledger-entry-rules` skill.)

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
- PDFs are read **first page only** -- multi-page statements aren't handled.
- Field parsing is now 3 tiers (exact label match -> real-world heuristics
  -> local LLM fallback), validated against a real SaaS billing receipt and
  a fabricated document containing none of the heuristic tiers' trigger
  words at all. The LLM tier requires Ollama running locally (optional --
  see Setup) and is slower (seconds, not milliseconds); without it, parsing
  is limited to tiers 1-2. See the `vault-ledger-ocr-extraction` skill for
  the full design, including the amount-grounding check that keeps the LLM
  from hallucinating a number.

## Milestone status

See `.claude/skills/vault-ledger-milestone-check/SKILL.md` for the full
M1-M8 definitions. As of this scaffold: M1-M7 implemented and tested
(M7's retraining step is manual/periodic by design, run via
`python -m vault_ledger.classifier.apply_corrections`); M8 not started
(needs real data).
