# Vault Ledger background

Every agent reads this before doing anything. It is kept current by the main
executive (`executive`); each team executive keeps its own team's lines right.
If something here is wrong or missing, say so before you act on it.

Last updated: 2026-10-13 (session start, after all five team executives
reported and the main executive's briefing)

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
| Data revision 3 goes ahead with a stop rule: if the round-4 realism review fails on new kinds of fault, synthetic work stops until real rows exist (user, 2026-10-12) | Three failed rounds, each on different faults; without real rows there is nothing to aim at |
| Real categorised rows (the gold set) are not being sought now; the user will come back to it (user, 2026-10-12) | User's call |

Not a decision, do not repeat to a customer: the action list (line 65) says
the Dutch audit file (XAF 4.0) is "mandatory as of Jan 1, 2026" and marks it
"not yet verified". It is still unverified and the research skeptic has not
ruled on it. Both scout drafts that touch it say the date is probably wrong
(they point to the tax office's developer portal: older versions phased out
per 1 January 2027; no official page found saying a small company must
produce the file). Those drafts are not passed either. Until the skeptic
rules, say nothing about XAF to anyone outside.

## This machine (2026-10-13)

The work moved to a fresh clone on a Windows machine, made 2026-10-13 from
`origin` (github.com/fmarfi/vault-ledger). Things that are different from
yesterday and that every agent must know:

- Everything on `origin` is what exists. No worktrees, no `private/`, no real
  PDFs, no `data/gold/`, no trained model file. Anything yesterday's notes
  describe as "in a worktree" or "being built" and that is not on `origin`
  does not exist here. Whether it still exists on the other machine is an
  open question to the user.
- All four branches are on `origin`. The user has not yet said who pushed
  them. No agent pushes anything.
- Python is `.venv/Scripts/python.exe`. The project is installed in it
  (`pip install -e ".[dev]"`, done by the session, not by a team).
- Full test suite on this machine, `demo-mode` at 322df07: 250 passed,
  1 failed, 3 skipped. The failure is
  `tests/test_stats_hardware.py::test_hardware_reads_real_memory_on_this_machine`
  (`hardware.total_ram_gb()` returns None on Windows). Yesterday's
  "254 passed" was on the other machine.
- Tesseract 5.4.0, English and orientation data only, at
  `C:\Program Files\Tesseract-OCR` (not on PATH). Yesterday's extraction
  review was measured with 5.5.3. Ollama is not installed, so the local-model
  tier of field parsing cannot run here.
- The rules hook in `.claude/settings.json` (runs the entry-rules tests after
  any edit to the rules or their test file) calls `python3` and
  `.venv/bin/python`, so on this machine it very probably does nothing.
  Anyone who edits `src/vault_ledger/rules/*` or `tests/test_entry_rules.py`
  runs `.venv/Scripts/python.exe -m pytest tests/test_entry_rules.py -q` by
  hand and reports the count. Changing the hook needs the user.
- Five agent definitions did not load at session start (exec-site and the
  four research specialists) because of a formatting fault in their
  description line. The session fixed the five lines (uncommitted); they
  load from the next session. Until then: scouts and exec-site may run as
  stand-ins that follow the definition file word for word. The research
  skeptic is a gate and runs only as the real agent, after a restart.

## Where things stand

Numbers carry their source. "Synthetic" means measured on our own generated
data and says nothing about real documents.

| Team | State on 2026-10-13 | Evidence |
|---|---|---|
| Data | Generator revision 2 (5f755b4): two draws of 4,000 rows, seeds 1234 and 4321. The test file has 38 cases; no stored run backs "38 passing" and it has not been run on this machine. Realism gate FAILED three times in a row: 0.25, 0.80, then 46/60 = 0.767 against 0.85 (round 3, draw 4321 only, synthetic), each time on different faults. Round-3 faults: description language unrelated to the vendor 15.8% of rows (limit 10%), Monday pile-up of invoice dates 12.3% excess, whole-string Title Case or lowercase 10.1%, payment channel not fitting the vendor 9.0-9.6%, 35 "ambiguous" rows with nothing ambiguous in them. Round-3 statistical gate: conditional pass on both draws; class vocabulary fails on draw 1234 (0.314 against 0.30) and passes 4321 at 0.271 without margin; the unseen-vendor gap fails on both (36.7 and 34.3 points against 10), which the auditor calls a property of the design (one vendor, one account), not a generator fault. Two thresholds pass only in their revised form (top-10 vendor share 40% became 55%; keyword band 45-65% became 20-65%), changed by the team after the round-1 failure and not yet confirmed by the user; the auditor reports both forms. Revision 3 is approved by the user with the stop rule (see decisions) but is written down nowhere except here: vendor-type profiles (language, bank channel, invoice dating, allowed typo types), a narrower "vendor and description disagree" case, lower recasing rate, counters clean on three seeds (1234, 4321, 1337) before any gate. Stage 6 and classifier retraining stay blocked until both gates pass. No gold set exists, so every realism judgement and every generator parameter is an assumption. | `origin/synth-data` (head 5edc240): `data/synthetic/reports/realism_round3_4321.md`, `audit_round3.md`, `CREW.md` revisions 1 and 2. Read with `git show origin/synth-data:<path>` until the worktree exists |
| Extraction | Nothing has changed in the code since the review. The fix round described yesterday left nothing on `origin`: `extraction-locale` is identical to `master` (f9fa142). Review findings stand and have not been re-measured: 9 of 9 on our English synthetic samples; no output on the real Dutch bill; `€ 1.234,56` read as 1.23 with no error; silently wrong values on a low-resolution copy; 15 of 24 degraded copies fully correct; no real scan or phone photo tested. Those numbers were taken on another machine with a different Tesseract and a local model, so they are not a baseline for this machine; a baseline here is the first step. The fix round is cut into slices. Slice 1 (needs neither Tesseract nor the model): English locale profile, one strict amount reader that refuses or escalates on `€ 1.234,56`, calendar-checked dates, model-proposed fields accepted only if found in the text. Slice 2 (orientation, local contrast, word-confidence gate to human review) needs the site and model teams and comes later. Dutch profile stays postponed. | `docs/reports/2026-10-12-ocr-extraction-review.md` (2 real PDFs, 9 synthetic samples, 24 degraded copies, other machine); `origin/extraction-locale` = f9fa142 |
| Model and rules | Rule tests 8 of 8 at 322df07 on this machine; the rules folder, rule tests, classifier code and the 22-row training file are identical to `master`. Gap: no test for Accounts Payable (or Cash/Bank) as an expense target; an in-memory check by exec-model shows it is rejected today as R2, so the test should pass once written. Classifier tests 5 of 5 on a 4-row toy set. There is no trained model file in this checkout, so yesterday's "highest confidence 0.62 against the 0.75 gate" is not verified here; the 0.75 gate itself is confirmed in `confidence_gate.py`. With 22 training rows the classifier is not usable whatever the exact figure. Three possible rule weaknesses reported by exec-model from its own probe, NOT confirmed by the gate: an amount of 0.004 passes the "greater than zero" check and rounds to a 0.00/0.00 entry; an infinite amount produces an entry; if "Accounts Payable" is written into `data/accounts.json` by hand, the rules build an entry that debits and credits it (whether that can be reached through the product is unknown). Nobody builds on these until rules-validator reproduces them. | `tests/test_entry_rules.py`, `tests/test_fusion_classifier.py`, `src/vault_ledger/confidence_gate.py`; exec-model briefing 2026-10-13. Yesterday's rules-validator and site-builder reports were never files in the repository |
| Site | Login, per-user data, review queue, ledger, overview, export, settings on `master`. Demo mode on `demo-mode` (bf7bffe), not merged; four site test files 128 passed, 2 skipped on this machine. Still nobody has looked at it in a browser. Faults known today, none fixed: (1) `webapp/static/shared.js:12` uses 0.6 as its own "high confidence" line while the gate is 0.75 (also on `master`), so an item between the two shows "Matched" while flagged for review; (2) every page loads its fonts from Google (`templates/base.html:8`) under a header that says nothing has left the machine; (3) five of the seven demo queue items carry hand-set confidence (0.86 to 0.95, `QUEUE_SEED` in `src/vault_ledger/demo.py`), the other two are real model output (0.26, 0.33), and only the banner says "illustrative"; (4) demo queue items have no document picture; (5) memory reads as "unknown" on Windows, so the low-memory warning can never show; (6) amounts show a hard-coded `$` (`webapp/static/shared.js:6`). | branch `demo-mode`; `tests/test_demo.py`; exec-site stand-in briefing 2026-10-13 |
| Research | Nothing is passed, so no team may build on any research finding. `requests.md` has five rows: three from the user (drafts written, skeptic pending) and two from exec-data (unassigned). The three drafts are committed (e7c52fc). The skeptic has never run. Code-checked gaps named in the drafts, still unpassed as requirements: the uploaded document is deleted after processing (`webapp/app.py:279`); the books export has five columns with no account code or VAT (`reports.py:18`); monthly grouping uses the confirmation date (`reports.py:60`). | `docs/reports/research/requests.md` and the three `2026-10-12-*.md` drafts |

Milestones: M1-M7 implemented and tested, M8 (real pilot run) not started. See
`.claude/skills/vault-ledger-milestone-check/SKILL.md`. Read M4 with care: the
classifier meets the milestone's test, but on 22 training rows it is not
usable (see Model and rules above).

Branches, all on `origin`: `master` f9fa142; `demo-mode` 322df07 (demo mode,
agent structure, this file); `synth-data` 5edc240; `extraction-locale`
f9fa142 (same as `master`). Nothing is merged to `master`. Worktrees and
other branches do not have this file; agents working there read it from the
main checkout (`C:\Users\ilhan\Desktop\vault-ledger_repo\docs\background.md`).

## Settled between teams on 2026-10-13 (main executive)

- Accounts Payable test: written by site-builder (the model team has nobody
  with write tools who is not the gate), in its own worktree on a branch from
  `master`, touching only `tests/test_entry_rules.py`. rules-validator judges
  it. It does not wait for the hook; the author runs the rule tests by hand.
- Windows memory reading (`src/vault_ledger/hardware.py`): owned by the site
  team, built by site-builder, standard library only. The judge is the
  existing test, which site-builder did not write, run by the session.
- Fonts: site-builder removes the Google font link and falls back to the
  fonts already on the machine. Shipping IBM Plex with the product waits for
  the skeptic to pass its licence.
- Browser check of demo mode: done by the session if it has a browser, with
  screenshots to `private/` for the user; otherwise by the user. Never by
  site-builder. It runs once now on bf7bffe and once more on the fixed build.
- Data revision 3: the spec and the counters start now. Two limits. The
  unseen-vendor test and its 10-point limit are not touched until research
  request 2 has passed the skeptic. The round-4 draw is not handed to the
  gates until research request 1 (which lines reach the classifier, who
  writes the description) has a skeptic ruling, because under the stop rule
  round 4 is the last try and that answer decides whether bank lines and
  description language belong in the data at all. Until then the document
  mix and the description language are single spec parameters marked
  `assumption`.
- Extraction slice 1 starts now on a new local branch and stays uncommitted.
  If unpushed fix-round work turns up on the other machine, the user chooses
  which to keep.
- The site's `$` waits for the locale profile from extraction slice 1; no
  second mechanism.
- No team starts VAT capture, keeping the original document, or supplier
  memory. All three rest on unpassed research, and VAT capture would touch
  the load-bearing rules spec.
- If round 4 passes realism but the unseen-vendor gap still fails, stage 6
  does not run and the limit is not changed; the question goes to the user
  together with the gated answer to research request 2.

## Where to find things

| What | Where |
|---|---|
| Who does what | `docs/agents.md` |
| Design reports and reviews | `docs/reports/` |
| Research findings, and the log of research requests | `docs/reports/research/` |
| Action list and UI brief | `docs/planning/` |
| Synthetic-data charter and gate reports | Only on branch `synth-data`: `git show origin/synth-data:data/synthetic/CREW.md` and `.../reports/`. Once the worktree is made: `.claude/worktrees/synth-data/data/synthetic/`. The `CREW.md` on `demo-mode` is the old charter |
| How each area works and its limits | `.claude/skills/` |
| Real documents and screenshots for testing | `private/` (git-ignored, never committed, never copied into reports). Does not exist on this machine yet; the two real PDFs from the extraction review are not here |

## Open questions waiting for the user

Each has the default the teams follow until the user answers.

1. Is there work from 2026-10-12 on the other machine that is not on GitHub
   (extraction fix round, the two real PDFs, the rules-validator and
   site-builder reports), and did you push the four branches yourself?
   Default: assume nothing else exists; extraction slice 1 starts fresh and
   uncommitted.
2. May the two real PDFs be put in `private/` here, and Ollama with
   `qwen2.5:1.5b-instruct` be installed here (local only)? Default: neither;
   extraction is measured on synthetic samples only and the local-model tier
   is reported as not tested.
3. Rules: may the hook in `.claude/settings.json` be pointed at the Windows
   Python, and, if rules-validator confirms the three weaknesses, may the
   rule code be tightened with the spec text unchanged (tests first, then
   rules-validator)? Default: hook untouched, rule tests run by hand; no
   change to rule code.
4. Data gate: judge 120 rows across both draws instead of 60 from one, same
   0.85 bar; and confirm or reject the two thresholds changed after round 1.
   Default: 60 rows from one draw; the auditor keeps reporting the old and
   the revised threshold side by side and no result is called a pass without
   saying which.
5. Demo: keep the five hand-set confidence scores with an "illustrative" mark
   on each row, or remove them? Default: keep, add the per-row mark.
6. Customer: may we ask the first customer three questions now (their
   accountant's bookkeeping package; whether they receive XML invoices; which
   machine and system they would run it on), and should every Dutch tax or
   legal statement be confirmed by a Dutch accountant before it is said to
   them? Default: nothing is sent; no tax or legal statement is made to the
   customer at all; teams assume a Windows or Mac laptop without a graphics
   card and 8-16 GB of memory.
7. May the session commit today's five agent-definition fixes and this file
   to `demo-mode`? Default: left uncommitted.

Not asked yet, coming with a recommendation when the evidence exists: when to
merge `demo-mode` (after the browser check passes and the suite is at 0
failed on this machine), `synth-data` and `extraction-locale` into `master`.

## Open items not waiting for the user

- Accounts Payable and Cash/Bank as expense target: test only, no change to
  the rules spec; rules-validator checks it afterwards.
- rules-validator reproduces the three reported rule weaknesses without
  editing anything.
- Extraction baseline on this machine, unchanged code.
- Site: confidence line taken from the server's single 0.75 value; Windows
  memory reading; Google font link removed.
- Browser check of demo mode before anyone outside sees it.
- Research: skeptic gates the three drafts (after restart) and rules on
  action list line 65; the two data requests are assigned.
- Revision 3 written into the spec and `CREW.md` on `synth-data`, including
  the stop rule, so it no longer lives only in this file.

## ML categorization engine track (appended by the main executive, 2026-10-13)

Appended as one block because another session has uncommitted edits to this
file; nothing above this heading was changed. Where this block and a line
above disagree, this block is newer.

What it is: the user put `docs/reports/vaultledger-ml-implementation-spec.md`
in the repository on 2026-10-13, said "do that" and "use agents for this
project too". It specifies a bank-row categorization engine (normalization,
categorisation rules as JSON, counterparty memory, a two-encoder model with a
taxonomy mask plus a TF-IDF baseline, per-company account mapping,
calibration and abstention, correction log, export writers, a synthetic
pipeline-test generator, an evaluation harness). The reason for the work is
the user's instruction; no research finding is needed to start it.

Its milestones are written ML-M1 to ML-M11 everywhere, because M1 to M8
already mean the product milestones in the milestone-check skill.

State: an unreviewed, untested draft by the session exists in `vaultledger-ml/`
(untracked; about 1,100 lines covering ML-M1 and parts of ML-M3). No tests.
The package's own environment was still installing (torch only) when checked.

Rulings by the main executive. Those marked (user to confirm) are the default
the teams follow until the user answers.

- Standalone. The engine is built as its own package and touches nothing in
  `src/vault_ledger`, `data/`, the rules spec or the site. It is a second
  input path (bank export row), not a replacement for document-in. Joining it
  to the product is a separate, later user decision. (user to confirm)
- No entry construction in the new package. Spec section 6.2's
  `entries.py` is not built: the product's existing debit/credit rules stay
  the only place entries are made. The new package ranks categories only.
  Its "rules" are categorisation rules and are not what rules-validator gates.
- Its generator is a pipeline-test fixture, not training data. It is outside
  the two data gates and outside the revision-3 stop rule, on one condition:
  nothing trained on it is shipped, loaded by the product, or quoted as
  accuracy to anyone. A base model meant for a customer needs gated or real
  data and the user's decision. The data team's revision 3 is unaffected.
  (user to confirm)
- Counterparty memory (L2) goes ahead inside the new package. The line above
  under "Settled between teams" that no team starts supplier memory still
  holds for `src/vault_ledger`.
- The classifier skill's "no Transformer, no hierarchy masking" still holds
  for `src/vault_ledger`; the user's spec overrides it for the new package only.
- XAF: only an empty writer interface. The sentence "mandatory in NL since
  2026-01-01" is not copied into any code, comment, README, log or report.
- `rgs_code` stays null and the activity (SBI) field stays empty or
  export-learned until research passes. VAT code in the export is an empty
  pass-through column; no VAT logic.
- "pytest runs in CI" means one local command. No workflow file, no push.
- Builder and checker: two new agent definitions under the model and rules
  team, `ml-builder` and `ml-reviewer`. The session's draft is reviewed by
  `ml-reviewer`, never by the session. (user to confirm)
- Place: worktree `.claude/worktrees/ml-engine` on a new local branch
  `ml-engine` from `master`. Uncommitted until the user allows local commits.

Open questions waiting for the user (continuing the list above):

8. Is the bank-row engine a separate track built standalone now, with the
   first customer's demo staying document-in, or the new main path for the
   first customer? Default: separate track, no integration.
9. Confirm that the spec's generator is a pipeline-test fixture outside the
   data gates and the stop rule, with nothing trained on it shipped or quoted.
   Default: yes.
10. Two new agent definitions (`ml-builder`, `ml-reviewer`) under exec-model,
    and a session restart so they and the research skeptic load. Default:
    definitions written, run as stand-ins following the file word for word.
11. Local commits on branch `ml-engine`, one per milestone the reviewer has
    passed, never pushed. Default: uncommitted.

Research requests to be filed by exec-research (none blocks ML-M1 to ML-M11):
offline source for KvK SBI codes (licence, personal data, updates); official
RGS code list and its licence; licences of the new package's dependencies
(`hypothesis` is MPL-2.0: test-only, never a runtime dependency) and the
figures the spec quotes from the DragoNet paper.

### Model and rules team on the ML engine track (appended by exec-model, 2026-10-13)

Standing rules for `ml-builder` and `ml-reviewer`, on top of the main
executive's rulings above. Details and briefs are in exec-model's report of
2026-10-13, not in a repository file.

- Shared files are frozen once ML-M1 passes: `pyproject.toml`,
  `configs/default.yaml`, `vaultledger/{__init__,schemas,config}.py`,
  `vaultledger/taxonomy/*`, `.gitignore`, `README.md`, `tests/conftest.py`.
  A builder never edits them; it puts the exact change it wants in its
  hand-back, works around it locally, and exec-model rules.
- One file has one owner per wave. `vaultledger/model/mask.py` belongs to
  ML-M4; the feature and model-interface files belong to ML-M3; everything
  under `vaultledger/io/` and `vaultledger/synth/` to ML-M2; `export/` to ML-M11.
- Hidden ground truth of the test generator lives only in a `_truth/` folder
  and is read only by code under `vaultledger/eval/`. No adapter, model,
  memory or cascade code opens it.
- Evaluation splits vendors globally across companies by default (the spec's
  per-company split is also reported). Memory is filled from training rows only.
- Until calibration exists (ML-M9) no suggestion gets status AUTO. Rule and
  memory confidences are hand-set and are reported as such, next to the
  measured precision and the number of rows.
- Every timing names the machine; every number says "synthetic" and how many
  rows. No figure from the DragoNet paper appears anywhere in the package
  until the skeptic passes it. torch and scikit-learn are not assumed
  shippable; they stay in the optional training extra.
- The SQLite files (memory, later the correction log) are unencrypted. Only
  generated rows go into them until the user decides on encryption at rest.
