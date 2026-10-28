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
  -> classifier cascade -> expense account + confidence
  -> confidence gate (low confidence goes to manual review)
  -> deterministic debit/credit rules -> balanced journal entry
```

- **Extraction** (`src/vault_ledger/extraction/`). Born-digital PDFs are read
  from their text layer and scans are rasterized and OCR'd. Field parsing has
  three tiers: exact label match, then real-world heuristics, then an optional
  local LLM (Ollama, `qwen2.5:1.5b-instruct`). The LLM's answer is only
  accepted if the amount it returns actually appears in the document text, so
  it can't make up a number.
- **Classifier** (`src/vault_ledger/classifier/`). A cascade of models, most
  engineered first (`cascade.py`): three DragoNet runs from `vaultledger-ml/`
  (pretrained multilingual encoder with its top 2 layers fine-tuned, then the
  VAT/paid-feature run, then the frozen-encoder run), and last the two-field
  TF-IDF fusion model. The first model whose confidence reaches the gate
  decides; a model that is unsure, or can't load or run, passes to the next.
  Each result records which model decided. `VAULT_CLASSIFIER=tfidf` uses only
  the TF-IDF model; `VAULT_CLASSIFIER=dragonet:<run folder>` puts that run
  first.
- **Entry rules** (`src/vault_ledger/rules/`). The debit/credit logic is
  deterministic and spec-driven (`rules_spec.json`). It runs a balance-check
  invariant and refuses to build an entry that wouldn't balance.
- **App** (`src/vault_ledger/webapp/`, `desktop.py`). A Flask app, shown in
  its own window by the desktop app, with a review
  queue with bulk confirm, a documents history, per-account ledgers, an
  overview, export, a customizable chart of accounts, and single-file backup
  and restore. Each user's data lives in its own directory. The app has
  CSRF protection, login throttling, security headers and an opt-in demo
  mode.

## Tech stack

Python 3.9+ (3.11+ for the DragoNet models), scikit-learn, PyTorch +
transformers (DragoNet, CPU only),
Tesseract (pytesseract), pypdfium2, Flask, pywebview (desktop), pandas, pytest.
Ollama is optional.

## Quick start

```
python -m venv .venv
.venv/bin/pip install -e ".[dev]"        # Windows: .venv\Scripts\pip
```

Install [Tesseract](https://github.com/tesseract-ocr/tesseract) for OCR. On
macOS run `brew install tesseract`, and on Windows use the UB-Mannheim
installer. For Dutch documents put `nld.traineddata` in Tesseract's `tessdata`
folder or in `data/tessdata/`. Everything except the end-to-end OCR tests
works without Tesseract.

**DragoNet models** (optional; without them the cascade uses the TF-IDF model):

```
.venv/bin/pip install -e vaultledger-ml
.venv/bin/python vaultledger-ml/scripts/fetch_encoder.py    # once, ~490 MB
```

Trained runs go in `vaultledger-ml/runs/<run name>/`. Weights, runs and
training data are not in git.

**Desktop app**

```
.venv/bin/pip install -e ".[desktop]"
python -m vault_ledger.desktop
```

It opens the app in its own window on a loopback port, with "Continue without
signing in" for the local account. `packaging/vault_ledger.spec` builds the
single-file Windows executable (PyInstaller).

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

Manage users with `python -m vault_ledger.auth add-user | list-users |
set-password | delete-user <name>`. Each user's data lives in its own
`data/users/<random id>/` directory.

| Variable | Meaning |
|---|---|
| `VAULT_SECRET_KEY` | Session signing key. If unset, a random one is generated once into `data/.secret_key`. |
| `VAULT_COOKIE_SECURE=1` | Mark the session cookie `Secure`. Set it whenever the app is served over HTTPS. |
| `VAULT_ALLOW_SIGNUP=1` | Enable the self-service `/signup` page. Off by default. |
| `VAULT_SKIP_LOGIN=1` | Offer "Continue without signing in" to this machine (the desktop app sets it). |
| `VAULT_DEMO=1` | Demo mode: a "Try the demo" button that creates a throwaway user with seeded, invented data. |
| `VAULT_HOST` / `VAULT_PORT` | Bind address (default `127.0.0.1`) and port (default `5050`). |
| `VAULT_DEBUG=1` | Flask debug mode; refused on a non-loopback host. |
| `VAULT_TRUST_PROXY=1` | Trust one `X-Forwarded-*` hop from a reverse proxy. |
| `VAULT_DATA_DIR` | Where `users.json`, `.secret_key` and `users/` live (default `data/`). |
| `VAULT_CLASSIFIER` | `tfidf`, or `dragonet:<run folder>` to put a run first (see Classifier). |

To serve it for several people, use a WSGI server with exactly one process
(threads are fine), because the login throttle and per-user locks live in that
process, e.g. `waitress-serve --threads 8 vault_ledger.webapp.wsgi:app`, behind
HTTPS with `VAULT_COOKIE_SECURE=1`.

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
vaultledger-ml/   DragoNet categorization engine (separate package)
packaging/        desktop launcher and PyInstaller spec
.claude/          Claude Code agents, skills and hooks used to build this
```

## Built with Claude Code

The project was developed with a team of
[Claude Code](https://claude.com/claude-code) subagents. Each part of the
product has its own team: extraction, model and rules, synthetic data, site,
and research. Every team has an executive agent, and a main executive
coordinates the teams. Domain rules such as the entry rules and the OCR
procedure are written as skills. A hook re-runs the entry-rules tests on every
edit to the rules layer. The agent definitions are in `.claude/agents/`. The
design reports and research notes are kept locally and are not part of the
repository.

## Status and limitations

- This is an MVP. The training data is synthetic, so classifier accuracy
  numbers are pipeline sanity checks, not validated performance. A pilot on
  real documents hasn't been run yet.
- Only the first page of a PDF is read.
- There's no encryption at rest, no password reset or 2FA, and the server runs
  as a single process. The trained models are shared and read-only; a user's
  corrections stay in their own directory and are not trained on yet.
- The chart of accounts has 9 default accounts (`src/vault_ledger/coa.py`),
  and users can customize it in Settings.

## License

MIT, see [LICENSE](LICENSE).
