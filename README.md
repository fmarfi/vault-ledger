# Vault Ledger

**On-device bookkeeping for small companies.** Drop in an invoice, utility bill
or receipt, and Vault Ledger reads it, picks the expense account, and proposes
a balanced debit/credit journal entry for a bookkeeper to confirm or correct.

Nothing leaves the machine. OCR, the neural classifier and the optional LLM
fallback all run locally, so no invoice is ever sent to a cloud service.

It runs as a Windows desktop app (a native window around a local Flask app) or
as a multi-user web app.

---

## Highlights

- **Document to journal entry, end to end.** It reads both born-digital PDFs
  and scans (Tesseract OCR), and both English and Dutch documents.
- **A cascade of models, most engineered first.** A DragoNet-style neural
  network built on a multilingual transformer answers first. Simpler models
  only take over when it isn't confident.
- **Accounting that can't drift.** Debits and credits come from deterministic,
  spec-driven rules, never from a model. An entry that wouldn't balance is
  refused rather than guessed.
- **A human in the loop by design.** Low-confidence suggestions go to a review
  queue, and corrections are stored as training signal.
- **Built like a product.** Per-user data isolation, CSRF protection, login
  throttling, security headers, backup and restore, CSV exports, a demo mode,
  a single-file Windows build, and 400+ tests.

## How it works

```
 invoice / bill / receipt (PDF or image)
        │
        ▼
 ┌──────────────┐   PDF text layer, or Tesseract OCR for scans (English + Dutch)
 │  Extraction  │   field parsing: vendor · description · date · amount · paid
 └──────┬───────┘   optional local LLM (Ollama) for hard cases, verified against the text
        ▼
 ┌──────────────┐   1. DragoNet  ─ pretrained encoder, top 2 layers fine-tuned
 │  Classifier  │   2. DragoNet  ─ frozen encoder + VAT / paid side features
 │   cascade    │   3. TF-IDF fusion model (lightweight, always available)
 └──────┬───────┘
        ▼
 ┌──────────────┐   confidence ≥ 0.75  → ready to post
 │ Confidence   │   confidence < 0.75  → manual review queue
 │    gate      │
 └──────┬───────┘
        ▼
 ┌──────────────┐   debit the expense account; credit Cash/Bank if paid,
 │ Entry rules  │   otherwise Accounts Payable; debits must equal credits
 └──────────────┘
```

## The model: a DragoNet-style two-field network

Categorizing a transaction depends on two different kinds of text: **who** was
paid ("Eneco", "NS Reizigers B.V.") and **what** for ("stroom en gas
oktober"). Blending them into one string throws that structure away. Following
*Two-headed DragoNet* (Busson et al., [arXiv:2312.07730](https://arxiv.org/abs/2312.07730)),
the network keeps them as separate inputs and learns how they relate.

```
 Field A: vendor name ─────► encoder ─► pool ─► proj ─► hA ┐
                                                           │  concat[hA, hB, hA·hB, |hA−hB|, hN]
 Field B: description ─────► encoder ─► pool ─► proj ─► hB ├─► Linear ─► GELU ─► Dropout ─► z
                                                           │
 13 numeric features ─────────────────► Linear ─► GELU ─► hN ┘
                                                                  │
                                    macro head (main category) ◄──┤
                                    micro head (account)       ◄──┴── z + softmax(macro)
```

- **Encoder.** `multilingual-e5-small`, a pretrained multilingual transformer,
  is shared by both fields so it is stored once. Training data is scarce, so
  starting from pretrained weights beats training from scratch. The best run
  also fine-tunes the encoder's top 2 layers at a low learning rate. The
  weights are fetched once at build time and never downloaded at runtime.
- **Fusion.** The product and absolute difference of the two field vectors let
  the network model how vendor and description agree or conflict, not just
  what each says.
- **Numeric side features.** Log amount, day-of-month bucket, round-amount
  flag, VAT rate, reverse-charge VAT, paid status and IBAN presence.
- **Two heads, hierarchy guaranteed.** One head predicts the main category, and
  the account head is conditioned on it. A taxonomy-aware joint decoder makes
  sure the predicted account always belongs to the predicted category, so the
  output never breaks the hierarchy.
- **Honest validation.** Validation and test splits are *vendor-disjoint*, so
  the model is scored on suppliers it has never seen. That prevents the score
  from rewarding memorized vendor names.

| Run (test split, vendor-disjoint) | Account accuracy | Account macro-F1 |
|---|---|---|
| DragoNet, top 2 encoder layers fine-tuned | **76.3%** | **0.707** |
| DragoNet, frozen encoder + VAT/paid features | 65.4% | 0.605 |
| DragoNet, frozen encoder, earlier feature set (ablation, not shipped) | 64.5% | 0.612 |

> These numbers come from **synthetic** invoice data with deliberate label
> noise. They compare design choices; they are not a claim about accuracy on
> real customer documents, which gets measured on a customer's own export
> before any number is promised.

**Why a cascade.** The app asks the models in order of sophistication. The
first one whose confidence clears the gate decides. A model that is unsure, or
can't load (no PyTorch, missing weights), hands over to the next. The last
stage is the original two-field TF-IDF + logistic-regression model, which
needs only a few dozen lines of pure Python at inference time, so the app
always has an answer. Every suggestion records which model made it.

## Design decisions worth calling out

- **ML proposes, rules decide.** The classifier only ever supplies an account
  label. All arithmetic and validity checks are deterministic code with
  invariants written down in `rules_spec.json` and enforced by tests. A hook
  re-runs those tests on every edit to the rules layer.
- **Privacy is a hard constraint, not a setting.** There are no network calls
  in the inference path, the server binds to loopback by default, and each
  user's data lives in its own directory.
- **The LLM is never trusted on numbers.** The optional local LLM's answer is
  rejected unless the amount it returns actually appears in the document text.
- **Fail closed.** A retired account, an unbalanced entry or an ambiguous
  document goes to a human instead of being guessed.

## Tech stack

**Python** · PyTorch + Hugging Face Transformers (CPU) · scikit-learn ·
Tesseract (pytesseract) · pypdfium2 · Flask · pywebview (WebView2) ·
PyInstaller · pytest + Hypothesis · Ollama (optional)

## Quick start

```bash
python -m venv .venv
.venv/bin/pip install -e ".[dev,desktop]"          # Windows: .venv\Scripts\pip

# optional: the DragoNet models (without them the TF-IDF model is used)
.venv/bin/pip install -e vaultledger-ml
.venv/bin/python vaultledger-ml/scripts/fetch_encoder.py   # once, ~490 MB

python -m vault_ledger.desktop                     # desktop app
```

Install [Tesseract](https://github.com/tesseract-ocr/tesseract) for OCR (on
macOS `brew install tesseract`, on Windows the UB-Mannheim installer). For
Dutch documents, put `nld.traineddata` in Tesseract's `tessdata` folder or in
`data/tessdata/`.

Try a single document from the command line:

```bash
python data/synthetic/generate_documents.py
python -m vault_ledger.pipeline data/synthetic/documents/invoice_office_supplies.png
```

Run the tests:

```bash
python -m pytest tests/                # app
python -m pytest vaultledger-ml/tests  # model package
```

The end-to-end OCR tests skip automatically when Tesseract isn't installed.

## Project layout

```
src/vault_ledger/
  extraction/     OCR, PDF text, field parsing (EN/NL), local LLM fallback
  classifier/     model cascade, DragoNet adapter, TF-IDF fusion model
  rules/          deterministic debit/credit construction + spec
  webapp/         Flask app, templates, static assets
  desktop.py      native desktop window around the app
vaultledger-ml/   DragoNet package: model, taxonomy, training, evaluation
packaging/        desktop launcher and PyInstaller spec
data/synthetic/   synthetic training data and document generators
tests/            pytest suite
```

## Status

This is an MVP. The training data is synthetic and a pilot on real documents
hasn't been run yet. Only the first page of a PDF is read. There's no
encryption at rest and no password reset or 2FA. The chart of accounts has 9
default accounts and can be customized in Settings.

<details>
<summary><b>Running it as a multi-user web app</b></summary>

```bash
python -m vault_ledger.auth add-user alice      # also: list-users, set-password, delete-user
python -m vault_ledger.webapp.app               # http://127.0.0.1:5050
VAULT_DEMO=1 python -m vault_ledger.webapp.app  # adds "Try the demo" with seeded, invented data
```

| Variable | Meaning |
|---|---|
| `VAULT_SECRET_KEY` | Session signing key. If unset, one is generated once into `data/.secret_key`. |
| `VAULT_COOKIE_SECURE=1` | Mark the session cookie `Secure`. Set it whenever the app is served over HTTPS. |
| `VAULT_ALLOW_SIGNUP=1` | Enable the self-service `/signup` page. Off by default. |
| `VAULT_SKIP_LOGIN=1` | Offer "Continue without signing in" on this machine (the desktop app sets it). |
| `VAULT_DEMO=1` | Demo mode: a throwaway user per visitor with seeded, invented data. |
| `VAULT_HOST` / `VAULT_PORT` | Bind address (default `127.0.0.1`) and port (default `5050`). |
| `VAULT_DEBUG=1` | Flask debug mode; refused on a non-loopback host. |
| `VAULT_TRUST_PROXY=1` | Trust one `X-Forwarded-*` hop from a reverse proxy. |
| `VAULT_DATA_DIR` | Where `users.json`, `.secret_key` and `users/` live (default `data/`). |
| `VAULT_CLASSIFIER` | `tfidf` for the lightweight model only, or `dragonet:<run folder>` to put a run first. |

Use a WSGI server with exactly one process (threads are fine), because the
login throttle and per-user locks live in that process, for example
`waitress-serve --threads 8 vault_ledger.webapp.wsgi:app`. Serve it behind HTTPS
with `VAULT_COOKIE_SECURE=1`.

</details>

## License

MIT, see [LICENSE](LICENSE).
