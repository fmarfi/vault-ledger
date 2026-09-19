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

Opens a Flask dev server at http://127.0.0.1:5050 with three pages
(`templates/base.html` + `static/style.css`'s token system are shared
across all of them -- see that CSS file's `:root` to change the whole
look in one place):

- **/ — Review Queue.** Process one document at a time (sample or
  upload), see the extracted fields, predicted account, and confidence --
  shown as a pencil/ink mark, not a percentage bar (the raw number is
  there on hover). Accept posts the entry to the ledger as shown; Correct
  posts it under a different account and logs the correction for the next
  training pass (M7). Still single-document, not a true multi-item queue --
  see the honest limitation in `webapp/app.py`'s module docstring.
- **/documents — Documents.** Every document that's been confirmed, with
  what it turned into and whether it needed a correction. Backed by
  `vault_ledger/ledger.py`, a new CSV-backed posted-entry record (separate
  from `corrections.py`, which is training signal only).
- **/ledger — Account ledger.** Confirmed entries grouped by account, with
  running totals -- styled as a ledger book's thumb-index tabs, not a plain
  tab bar.

- **/settings — Settings.** Customize the expense chart of accounts (add,
  retire, or start from a US/EU template -- `coa.py`, stored in
  `data/accounts.json`), and download/restore a single-file backup of all
  local data (`backup.py`; the trained model is deliberately excluded and
  retrains from the restored training data).

The Review Queue is a persistent multi-item queue (`queue.py`) with bulk
confirm; the Documents page shows an honest "accepted as-is" rate computed
from the ledger (`stats.py`); every page shows a banner when this machine is
under the recommended 16 GB RAM (`hardware.py`).


It's a thin UI layer over `vault_ledger.pipeline` and `vault_ledger.ledger`
-- no separate business logic. Not a production deployment (Flask dev
server, single in-memory classifier instance).

## Accounts, sessions and running it for other people

The web app requires a login. Every user gets a private directory
`data/users/<random id>/` holding their own `ledger.csv`, `pending_queue.csv`,
`corrections.csv`, `accounts.json`, `backups/` and `training.csv`. Paths are
built from the random id only, never from the username, and the storage layer
(`src/vault_ledger/userdata.py`) refuses any path outside the signed-in user's
directory. The CLI, the classifier scripts and the tests still use the old
single-user locations when no user is set.

**Create users** (there is no open registration):

```
.venv/bin/python -m vault_ledger.auth add-user alice        # asks for a password twice
.venv/bin/python -m vault_ledger.auth list-users
.venv/bin/python -m vault_ledger.auth set-password alice     # also ends alice's sessions
.venv/bin/python -m vault_ledger.auth delete-user alice      # asks you to retype the name; deletes only alice's data dir
```

Usernames are 3-32 characters of `a-z 0-9 _ . -`, unique case-insensitively.
Passwords: at least 10 characters and not equal to the username; stored as
salted scrypt hashes in `data/users.json` (mode 0600, written atomically).

**Move your existing single-user data** (the pre-login `data/ledger.csv`,
`data/pending_queue.csv`, `corrections.csv`, `data/accounts.json`,
`data/backups/`) into a user, once:

```
.venv/bin/python -m vault_ledger.auth add-user alice
.venv/bin/python -m vault_ledger.auth migrate-legacy alice
```

It copies, verifies each copy byte for byte, and writes `data/.migrated`. The
originals are left where they are (never deleted for you); delete them by hand
once you have checked. It refuses to run twice.

**Environment variables**

| Variable | Meaning |
|---|---|
| `VAULT_SECRET_KEY` | Session signing key. If unset, a random one is generated once into `data/.secret_key` (0600). There is no built-in default. |
| `VAULT_COOKIE_SECURE=1` | Mark the session cookie `Secure`. **Set this whenever the app is served over HTTPS**, and serve it over HTTPS (reverse proxy such as Caddy/nginx) if it is reachable by anyone else. |
| `VAULT_ALLOW_SIGNUP=1` | Enable a self-service `/signup` page. Off by default. |
| `VAULT_HOST` / `VAULT_PORT` | Bind address (default `127.0.0.1`) and port (default `5050`). |
| `VAULT_DEBUG=1` | Flask debug mode. Off by default; the app refuses to start with it on a non-loopback host. |
| `VAULT_TRUST_PROXY=1` | Trust one `X-Forwarded-For/Proto/Host` hop from a reverse proxy (so the login throttle sees real client IPs). Only set behind a proxy that overwrites those headers. |
| `VAULT_DATA_DIR` | Where `users.json`, `.secret_key` and `users/` live (default `data/`). |

**How it behaves.** Signed-cookie sessions (HttpOnly, SameSite=Lax, 8-hour
lifetime, replaced on login, cleared on `POST /logout`). Every state-changing
request needs the per-session `X-CSRF-Token` header (the pages read it from a
`<meta>` tag). 5 failed logins per (IP, username) in 15 minutes gives HTTP 429;
unknown user and wrong password produce the same message. Everything except
`/login`, `/logout`, `/healthz` and `/static/*` requires login (`/api/*` answers
401, pages redirect to `/login`). Responses carry `nosniff`, `X-Frame-Options:
DENY`, `Referrer-Policy: same-origin`, `Cache-Control: no-store`, and a CSP with
`frame-ancestors 'none'`. Uploads are capped at 20 MB. Backup restore accepts
only the fixed member names, refuses symlinks and oversized archives, and only
ever writes the caller's own directory.

**Running it for several people.** Use a real WSGI server, and run exactly ONE
process (threads are fine), because the login throttle and the per-user locks
live in that process:

```
.venv/bin/pip install waitress      # or gunicorn; not a project dependency
VAULT_COOKIE_SECURE=1 .venv/bin/waitress-serve --host 127.0.0.1 --port 5050 --threads 8 vault_ledger.webapp.wsgi:app
# gunicorn equivalent: gunicorn -w 1 --threads 8 vault_ledger.webapp.wsgi:app
```

**What this does NOT do** (be honest with your users):

- No encryption at rest: anyone with read access to the machine's disk or
  backups can read every user's files. Users are separated by the app, not by
  the operating system.
- No password reset flow, no email, no 2FA, no account lockout beyond the
  throttle. The operator resets passwords with the CLI.
- No per-user classifier. The trained model is shared and read-only; a user's
  corrections are stored in their own `corrections.csv` and never folded into
  the shared training data or model, so one user's data cannot influence
  another's predictions. The web app has no retrain button; the existing CLI
  (`apply_corrections`, `train`) still works on the legacy single-user files
  and is not per-user. Per-user `training.csv` exists (and is in backups) but
  nothing trains on it yet.
- The login throttle is in memory: it resets on restart and is not shared
  between processes.
- Sessions are stateless signed cookies: "Sign out" clears the browser's copy
  but a stolen cookie stays valid until it expires (8 h) unless the user's
  password is changed or the user is deleted.
- Single process only. `is_admin` is recorded but currently grants nothing.
- Uploaded documents' OCR temp files pass through the shared OS temp dir
  briefly and are deleted immediately.

## Testing

```
.venv/bin/python -m pytest tests/ -v
```

The 3 end-to-end OCR tests in `test_pipeline.py` auto-skip if `tesseract`
isn't on PATH; everything else (rules layer, field parsing, classifier)
runs without it.

## Chart of accounts (9 by default, customizable)

Defaults: Cash/Bank, Accounts Payable, Utilities Expense, Office Supplies Expense,
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
- No real pilot run (M8), no multi-client/multi-company support, no fraud/anomaly
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
