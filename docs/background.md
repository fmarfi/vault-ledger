# Vault Ledger background

Every agent reads this before doing anything. It is kept current by the main
executive (`executive`); each team executive keeps its own team's lines right.
If something here is wrong or missing, say so before you act on it.

Last updated: 2026-10-12 (evening, after the main executive's briefing)

## What the product is

An on-device bookkeeping tool. A document (invoice, utility bill, receipt)
goes in. OCR and field parsing pull out vendor, description, date, amount and
paid. A small classifier proposes the expense account with a confidence score.
Fixed rules build a balanced debit/credit entry. A bookkeeper confirms or
corrects it in a review queue. Confirmed entries go to a ledger and exports.

## Who it is for, right now

We are preparing to sell to a first customer: a startup in the Netherlands.
The product stays English first. Dutch support is deliberately postponed, but
everything language-specific must be easy to convert later.

## Decisions already made (do not reopen without the user)

| Decision | Why |
|---|---|
| No customer document or transaction leaves the machine: no hosted OCR, LLM or document API | Privacy is the product's promise; hosted services process and may train on customer content |
| No AGPL or other copyleft dependency (so no PyMuPDF) | The product is closed source |
| The debit/credit rules are deterministic and load-bearing; models propose, rules decide | An entry that does not balance or hits the wrong account type is the costliest error |
| Vendor and description are always two separate fields | The classifier's gain comes from reading them separately |
| A heuristic with more than one candidate escalates instead of guessing | A wrong value with no error is the worst outcome |
| Low-confidence predictions go to a human, never straight to the ledger | The bookkeeper is professionally liable |
| Synthetic data is a cold-start tool; its results are never quoted as real-world accuracy | No real company data exists yet; a gold set of real rows does not exist yet either |
| The classifier for a customer is meant to be tuned on that customer's own already-categorised export (QuickBooks, Xero or similar), on their machine (action list, 2026-09-16) | Labels come from the customer's books, not from us; synthetic data only covers the start |
| Gates (two data gates, rules gate, research skeptic) cannot be skipped or loosened except by the user | They are the only independent check on our own work |
| Whoever wrote a change never judges it | Same reason |
| Nothing is merged to `master`, pushed, or shown to a customer without the user's approval | The user decides what ships |
| Work runs through the team structure in `docs/agents.md`; research serves every team; nobody acts without this background (user, 2026-10-12) | One picture, and no work started on a guess |
| The site change for the first customer is demo mode (user, 2026-10-12) | The customer needs something to look at without their own data |

Not a decision, do not repeat to a customer: the action list says the Dutch
audit file (XAF 4.0) is "mandatory as of Jan 1, 2026" and marks it "not yet
verified". It is still unverified; the research skeptic has not ruled on it.

## Where things stand

| Team | State on 2026-10-12 | Evidence |
|---|---|---|
| Data | Generator revision 2 committed (5f755b4, 38 generator tests passing, 2 draws of 4000 rows). Realism gate FAILED for the third time in a row: 0.25, then 0.80, then 0.767 against 0.85, each time on different artifacts. Round-3 statistical audit is running, no result. Stage 6 and any classifier retraining are blocked until both gates pass. No gold set of real rows exists (`data/gold/` is absent), so every realism judgement and every generator parameter is an assumption. Two statistical thresholds were changed after the round-1 failure (top-10 vendor share under 40% became 55% or less; keyword band widened); the user has not yet confirmed or rejected that. | branch `synth-data` (head dcf35ab); `data/synthetic/reports/realism_round3_4321.md`, `audit_round2.md`, `CREW.md` "Revision 1" on that branch |
| Extraction | Measured on 9 synthetic samples, 2 real PDFs, 24 degraded copies: works on our English samples (9 of 9), gives no output on the real Dutch bill, reads `€ 1.234,56` as 1.23 with no error, and returned silently wrong values on a low-resolution copy. No real scan or phone photo has been tested. A fix round (locale profiles with English only, one strict amount reader, validated dates, grounding of every model-proposed field, orientation, local contrast, word-confidence gate to human review) is being built; nothing is committed on the branch yet and nothing has been re-measured. | `docs/reports/2026-10-12-ocr-extraction-review.md`; branch `extraction-locale` (still at f9fa142) |
| Model and rules | Rules R1-R5 confirmed on `demo-mode` by rules-validator: rules directory identical to `master`, 8 of 8 rule tests, test_pipeline 10, test_ledger 3. Gap: R5 has no test for Accounts Payable as an expense target (same on `master`). The shipped classifier is trained on 22 rows; its highest confidence on anything is 0.62 against the 0.75 gate, so the real product flags every document for review and bulk confirm never triggers. | `tests/test_entry_rules.py`; rules-validator and site-builder reports of 2026-10-12 |
| Site | Login, per-user data, review queue, ledger, overview, export, settings on `master`. Demo mode committed on `demo-mode` (bf7bffe), full suite 254 passed, not merged. Checked over HTTP only; nobody has looked at it in a browser. Five demo queue items carry hand-set confidence (0.86-0.95), labelled on screen as illustrative. Amounts show a hard-coded `$` (`webapp/static/shared.js`). | branch `demo-mode`, `tests/test_demo.py`, `src/vault_ledger/demo.py` |
| Research | Crew created. Three scouting requests open. All three scout drafts are now in the folder (untracked files). The skeptic has not run. No finding is passed, so no team may build on any of it. | `docs/reports/research/requests.md` |

Milestones: M1-M7 implemented and tested, M8 (real pilot run) not started. See
`.claude/skills/vault-ledger-milestone-check/SKILL.md`. Read M4 with care: the
classifier meets the milestone's test, but on 22 training rows it is not
usable (see Model and rules above).

Branches: `master` f9fa142; `demo-mode` 05085da (demo mode, agent structure,
this file); `synth-data` dcf35ab; `extraction-locale` still at f9fa142 with a clean
worktree (the build in flight has not written or committed anything visible yet). Nothing is merged to `master` and nothing is pushed.
Worktrees do not have this file; agents working there read it from the main
checkout.

## Where to find things

| What | Where |
|---|---|
| Who does what | `docs/agents.md` |
| Design reports and reviews | `docs/reports/` |
| Research findings, and the log of research requests | `docs/reports/research/` |
| Action list and UI brief | `docs/planning/` |
| Synthetic-data charter and gate reports | `data/synthetic/CREW.md`; the gate reports and the revised charter exist only on branch `synth-data`, checked out at `.claude/worktrees/synth-data/data/synthetic/` |
| How each area works and its limits | `.claude/skills/` |
| Real documents for testing | `private/` and the two PDFs in the repository root (never committed, never copied into reports) |

## Open questions waiting for the user

- Data gate, after three failed realism reviews: one more revision that fixes
  the cause in the spec with a stop rule, or stop and wait for real rows, or
  change the gate. Decides when the classifier can be retrained.
- Can we get real rows: an already-categorised export from the first customer
  (or from the user's own books) to start the gold set.
- Confirm or reject the two statistical thresholds that were changed after the
  round-1 audit failure (top-10 vendor share 40% to 55%; keyword band).
- Keep or remove the five hand-set confidence scores in the demo until the
  classifier is retrained.
- When to merge `demo-mode`, `synth-data` and `extraction-locale` into `master`.

## Open items not waiting for the user

- R5 needs a test for Accounts Payable as an expense target (test only, no
  change to the rules spec); rules-validator checks it afterwards.
- The site's `$` sign should come from the same locale profile that
  `extraction-locale` introduces, not from a second mechanism; wait for that
  branch's profile before changing the site.
- The demo has to be looked at in a real browser before anyone outside sees it.
