# Vault Ledger background

Every agent reads this before doing anything. It is kept current by the main
executive (`executive`); each team executive keeps its own team's lines right.
If something here is wrong or missing, say so before you act on it.

Last updated: 2026-10-12

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
| Gates (two data gates, rules gate, research skeptic) cannot be skipped or loosened except by the user | They are the only independent check on our own work |
| Whoever wrote a change never judges it | Same reason |
| Nothing is merged to `master`, pushed, or shown to a customer without the user's approval | The user decides what ships |

## Where things stand

| Team | State on 2026-10-12 | Evidence |
|---|---|---|
| Data | Synthetic data, revision 2 generated (2 draws of 4000 rows). Realism gate FAILED a third time (0.767 against 0.85). Classifier training on this data has not run. | branch `synth-data`, `data/synthetic/reports/realism_round3_4321.md` |
| Extraction | Measured: works on our English samples, fails on Dutch and on poor scans, with some silent wrong values. A fix round (locale profiles, strict amounts, validated dates, grounding, scan quality gate) is being built. | `docs/reports/2026-10-12-ocr-extraction-review.md`, branch `extraction-locale` |
| Model and rules | Rules R1-R5 enforced and passing. The shipped classifier is trained on 22 rows and never reaches the 0.75 confidence gate, so every document is flagged for review. | `tests/test_entry_rules.py`; site-builder's demo-mode report |
| Site | Login, per-user data, review queue, ledger, overview, export, settings on `master`. Demo mode built on branch `demo-mode`, not merged; five demo queue items use hand-set confidence, labelled on screen as illustrative. Amounts show a `$` sign. | branch `demo-mode`, `tests/test_demo.py` |
| Research | Crew created. First scouting round (product functions, technical options, customer requirements) in progress; nothing has passed the skeptic yet. | `docs/reports/research/` |

Milestones: M1-M7 implemented and tested, M8 (real pilot run) not started. See
`.claude/skills/vault-ledger-milestone-check/SKILL.md`.

## Where to find things

| What | Where |
|---|---|
| Who does what | `docs/agents.md` |
| Design reports and reviews | `docs/reports/` |
| Research findings, and the log of research requests | `docs/reports/research/` |
| Action list and UI brief | `docs/planning/` |
| Synthetic-data charter and gate reports | `data/synthetic/CREW.md`, `data/synthetic/reports/` (branch `synth-data`, checked out at `.claude/worktrees/synth-data`) |
| How each area works and its limits | `.claude/skills/` |
| Real documents for testing | `private/` and the two PDFs in the repository root (never committed, never copied into reports) |

## Open questions waiting for the user

- Keep or remove the five hand-set confidence scores in the demo until the classifier is retrained.
- When to merge `demo-mode`, `synth-data` and `extraction-locale` into `master`.
