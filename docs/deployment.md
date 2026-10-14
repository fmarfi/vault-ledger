# Running Vault Ledger for other people

Accounts, sessions, security behaviour and demo mode for the web app. For setup and the pipeline overview, see the [README](../README.md).

## Accounts and sessions

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
| `VAULT_DEMO=1` | Enable demo mode: a "Try the demo" button on the sign-in page. Off by default. See [Demo mode](#demo-mode). |
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

## Demo mode

For walking someone through the whole flow without any real data. Off by
default; turn it on with an environment variable (read on every request, like
`VAULT_ALLOW_SIGNUP`):

```
VAULT_DEMO=1 .venv/bin/python -m vault_ledger.webapp.app
```

While it is off, `/demo/*` answers 404 and no demo button is rendered.

**What happens.** The sign-in page gets a separate "Try the demo" button.
Each click creates a brand-new throwaway user (`demo-<8 hex>`, random id,
random password that is never shown and cannot be used: demo users are
refused at password login), seeds that user's own directory under
`data/users/<id>/`, and signs the browser in. Two people trying the demo at
the same time get two separate users and never see each other's data. A red
banner stays on every page with **Reset demo** (wipe and reseed this demo
user) and **Exit demo** (sign out and delete the user and its directory).

**What it seeds** (`src/vault_ledger/demo.py`, a fixed list with dates
relative to today):

- 34 posted ledger entries over the last three months, covering every default
  expense account: office rent, energy, water, internet and mobile, SaaS
  subscriptions, train travel, an accountant, office supplies and so on.
- 7 documents waiting in the review queue: 5 ready for bulk confirm and 2
  flagged for individual review.

Everything goes through the normal code paths (classifier, confidence gate,
`construct_entry`, `append_entry`, `enqueue`), so every entry balances.

**The data is invented.** The vendor names are plausible suppliers for a small
Dutch startup, but no such invoices exist. Two things to know before
presenting it:

- The confidence and "corrected" flag on the posted history are the real
  classifier's output on this invented data. With the current small training
  set that confidence is low (roughly 0.2 to 0.5), so the Documents page marks
  those entries "Uncertain".
- The five bulk-confirmable queue items carry a **hand-set, illustrative**
  account and confidence (0.86 to 0.95). The shipped classifier does not clear
  the 0.75 confidence gate on anything yet, so without this every item would
  be flagged and bulk confirm could not be shown. They are not a measurement of
  the model; the banner says so on screen. The two flagged items are untouched
  real classifier output. A document uploaded live during a demo also gets the
  real (low) confidence.

Amounts are plain numbers at euro scale; the UI still prints a fixed `$`
(there is no currency setting yet).

**Limits for demo users.** They can do everything in their own directory
(process documents, confirm, correct, edit their chart of accounts, export,
download a backup) but cannot restore a backup from an upload (HTTP 403), and
have no access to any other user's data, like every other user.

**Cleanup.** A demo user is deleted, record and directory, on Exit demo, or
when it is more than 24 hours old: expired demo users are purged whenever
someone starts a new demo (there is no background job, so the last ones stay
on disk until the next start). Turning `VAULT_DEMO` off ends all demo
sessions at once. Starts are limited to 10 per IP per 15 minutes and 100 live
demo users in total.

