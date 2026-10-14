# Vault Ledger

On-device bookkeeping for small companies: a document (invoice, utility bill,
receipt) goes in, a balanced debit/credit journal entry comes out. A
bookkeeper reviews the proposal, confirms or corrects it, and corrections feed
the next training round.

Everything runs locally. OCR, classification and the optional LLM fallback
never send a document to a hosted service; this was a deliberate privacy
decision.

## How it works

```
document (image or PDF)
  -> text: native PDF text layer, or Tesseract OCR for scans
  -> field parsing: vendor, description, date, amount, paid
  -> two-field fusion classifier -> expense account + confidence
  -> confidence gate (low confidence goes to manual review)
  -> deterministic debit/credit rules -> balanced journal entry
```

- **Extraction** (`src/vault_ledger/extraction/`). Born-digital PDFs are read
  from their text layer and scans are rasterized and OCR'd. Field parsing has
  three tiers: exact label match, then real-world heuristics, then an optional
  local LLM (Ollama, `qwen2.5:1.5b-instruct`). The LLM's answer is only
  accepted if the amount it returns actually appears in the document text, so
  it can't make up a number.
- **Classifier** (`src/vault_ledger/classifier/`). Vendor and description get
  separate vectorizers. The two feature sets are concatenated and fed to one
  model, whose labels are the chart of accounts. It returns a confidence
  score along with the predicted account.
- **Entry rules** (`src/vault_ledger/rules/`). The debit/credit logic is
  deterministic and spec-driven (`rules_spec.json`). It runs a balance-check
  invariant and refuses to build an entry that wouldn't balance.
- **Web app** (`src/vault_ledger/webapp/`). It's a Flask app with a review
  queue with bulk confirm, a documents history, per-account ledgers, an
  overview, export, a customizable chart of accounts, and single-file backup
  and restore. Each user's data lives in its own directory. The app has
  CSRF protection, login throttling, security headers and an opt-in demo
  mode.

## Tech stack

Python 3.9+, scikit-learn, Tesseract (pytesseract), pypdfium2, Flask, pandas,
pytest. Ollama is optional.

## Quick start

```
python -m venv .venv
.venv/bin/pip install -e ".[dev]"        # Windows: .venv\Scripts\pip
```

Install [Tesseract](https://github.com/tesseract-ocr/tesseract) for OCR. On
macOS run `brew install tesseract`, and on Windows use the UB-Mannheim
installer. Everything except the end-to-end OCR tests works without it.

**CLI**

```
python data/synthetic/generate_documents.py     # sample invoice/bill/receipt (png + pdf)
python -m vault_ledger.pipeline data/synthetic/documents/invoice_office_supplies.png
```

This prints the parsed fields, the predicted account and confidence, and the
proposed journal entry, or the reason the rules layer refused to build one.

**Web app**

```
python -m vault_ledger.auth add-user alice
python -m vault_ledger.webapp.app               # http://127.0.0.1:5050
VAULT_DEMO=1 python -m vault_ledger.webapp.app  # adds a "Try the demo" button with seeded data
```

[docs/deployment.md](docs/deployment.md) covers accounts, environment
variables, the security model, running the app for several users, and demo
mode.

## Testing

```
python -m pytest tests/
```

The test suite covers the rules layer, field parsing, the classifier, auth
and per-user isolation, backup/restore, the web API and demo mode. The
end-to-end OCR tests skip automatically if `tesseract` isn't on PATH.

## Project layout

```
src/vault_ledger/
  extraction/     OCR, PDF text, field parsing, local LLM fallback
  classifier/     fusion classifier: train, evaluate, apply corrections
  rules/          deterministic debit/credit construction
  webapp/         Flask app, templates, static assets
  auth.py, userdata.py, backup.py, queue.py, ledger.py, ...
data/synthetic/   synthetic training data and document generator
tests/            pytest suite
docs/             design reports, research, agent structure
.claude/          Claude Code agents, skills and hooks used to build this
```

## Built with Claude Code

The project was developed with a team of
[Claude Code](https://claude.com/claude-code) subagents. Each part of the
product has its own team: extraction, model and rules, synthetic data, site,
and research. Every team has an executive agent, and a main executive
coordinates the teams. Domain rules such as the entry rules and the OCR
procedure are written as skills. A hook re-runs the entry-rules tests on every
edit to the rules layer. See [docs/agents.md](docs/agents.md) for the
structure, and `docs/reports/` for the design reports.

## Status and limitations

- This is an MVP. The training data is synthetic, so classifier accuracy
  numbers are pipeline sanity checks, not validated performance. A pilot on
  real documents hasn't been run yet.
- Only the first page of a PDF is read.
- There's no encryption at rest, and the server runs as a single process. See
  [docs/deployment.md](docs/deployment.md) for the full list.
- The chart of accounts has 9 default accounts (`src/vault_ledger/coa.py`),
  and users can customize it in Settings.

## License

MIT, see [LICENSE](LICENSE).
