# Report 3 — Building Vault Ledger's MVP with Claude Code and Agents

**Purpose:** a practical, well-worked-through plan for actually using Claude Code — subagents, skills, and hooks — to build the pipeline described in Reports 1 and 2. This assumes the technical scope from Report 1 (two-field fusion classifier, deterministic rules layer, fixed COA) and the milestone sequence from Report 2.

A note on sourcing: the mechanics below (subagent files, skill files, hooks) are drawn from Anthropic's own Claude Code documentation. Anything that reads as a suggested workflow or project-specific setup is this report's own proposal, not something documented by Anthropic — treat those parts as a starting point to adapt, not a spec to follow exactly.

---

## Part 1 — The three primitives, and which one this project actually needs for what

Claude Code gives you three distinct customization tools. They solve different problems, and the biggest mistake in setting up an agentic build like this is using the wrong one for a given job.

| Primitive | What it is | When to reach for it |
|---|---|---|
| **Skill** | A folder at `.claude/skills/<name>/SKILL.md` containing instructions (+ optional scripts/resources) that Claude loads automatically when the task matches, or invokes directly as `/skill-name` | Repeatable domain knowledge or a procedure you'll want followed the same way every time — "how we build the debit/credit rules layer," "how we validate OCR output against ground truth" |
| **Subagent** | A file at `.claude/agents/<name>.md` with `name`/`description`/`tools`/`model` frontmatter — a separate Claude instance with its own context window that the main session delegates to and gets back only a summary from | Isolated, scoped work you don't want flooding the main conversation — running a batch of OCR extractions, reviewing a diff, exploring an unfamiliar part of the codebase |
| **Hook** | A shell command that fires deterministically at a lifecycle event (before/after a tool call, on session stop, etc.) | Enforcing a rule with code, not a prompt — e.g. "never let a commit go through if the debit/credit balance-check test is failing" |

The rule of thumb worth keeping in mind throughout: **skills teach the how, subagents isolate the work, hooks enforce the rule.** For this project specifically, that maps onto Report 1's own architecture surprisingly well — the deterministic rules layer (Report 1, item 5) is exactly the kind of thing a hook is built for; the multi-stage pipeline (OCR → parsing → classification → construction) is exactly the kind of thing subagents are built for; and the recurring "how do we build/test each stage" knowledge is exactly what skills are for.

---

## Part 2 — Skills to build for this project

Each of these should be a real `.claude/skills/<name>/SKILL.md` in the repo, not just a mental model. Writing them down means every future session (yours or a subagent's) follows the same procedure instead of reinventing it.

### `vault-ledger-ocr-extraction`
**Purpose:** encodes how to run and validate OCR extraction against the three target document formats (invoice, utility bill, receipt).
**Should include:** which OCR tool/library is in use, how to run it against a sample document, and — critically, given Report 1's flagged risk — an explicit validation step that checks vendor name and description came out as **separate fields**, not blended. This skill is the natural home for the "is extraction actually working" checkpoint from Report 2's Milestone 3.

### `vault-ledger-classifier`
**Purpose:** encodes the two-field fusion classifier approach (Report 1, item 4) — two vectorizers, concatenation, fixed COA as label space, confidence score output.
**Should include:** how to (re)train on a new batch of labeled data, how to evaluate against a held-out set, and explicitly *not* how to build the old single-text-blob notebook approach — worth stating outright in the skill so a future session doesn't regress toward the dropped approach.

### `vault-ledger-entry-rules`
**Purpose:** encodes the deterministic debit/credit construction logic from the companion rules spec.
**Should include:** the fixed COA, the paid-vs-unpaid heuristic, the balance-check invariant, and the required test cases (paid, unpaid, zero/negative amount, unknown account). This skill should be treated as close to "load-bearing spec," since Report 1 explicitly calls this the part that must never be wrong.

### `vault-ledger-milestone-check`
**Purpose:** a lightweight skill that, given a milestone number from Report 2, tells Claude what "done" looks like for that milestone and what to demo.
**Why this is worth having as its own skill rather than just re-reading Report 2 each time:** it keeps the milestone definitions authoritative and versioned in the repo rather than living only in a chat conversation, and it means a subagent can be handed "get milestone 3 working" and know exactly what that means without the full report in context.

---

## Part 3 — Subagents to define for this project

Subagents are worth defining where a stage of the pipeline is (a) self-contained, (b) produces a lot of intermediate noise you don't want in your main session, and (c) something you'll invoke repeatedly. Three stages of the pipeline fit that description well.

### `ocr-runner` subagent
```yaml
---
name: ocr-runner
description: Runs OCR extraction on a document image/PDF and reports structured field extraction results. Use when testing extraction against sample documents or validating a new document format.
tools: Read, Bash, Write
---
```
**Why isolate this:** running OCR against a batch of sample documents produces a lot of raw text output you don't want cluttering your main context — you want the summary (did vendor/description separate correctly, what fields were extracted) not the raw dump.

### `classifier-eval` subagent
```yaml
---
name: classifier-eval
description: Trains or evaluates the two-field fusion classifier against a labeled dataset and reports accuracy/confidence metrics. Use when checking classifier performance after adding new training data.
tools: Read, Bash, Write
---
```
**Why isolate this:** training runs and evaluation output are long and mostly irrelevant once you have the final metric — the main session should see "94% accuracy on N samples, here's where it's weakest" not the full training log.

### `rules-validator` subagent
```yaml
---
name: rules-validator
description: Runs the debit/credit construction rules test suite and reports pass/fail with specifics on any failing case. Use before merging any change that touches the entry-construction layer.
tools: Read, Bash
---
```
**Why isolate this, and why it pairs with a hook (Part 4):** this is the layer Report 1 flags as highest-consequence to get wrong. A dedicated subagent that only ever runs and reports on this test suite — never edits code itself — keeps a clean, auditable signal on the one part of the system where "probably fine" isn't good enough.

**Note on scope:** three subagents is enough for MVP. Don't over-fragment into one subagent per pipeline stage before there's evidence a given stage actually produces enough noise to warrant isolation — Claude Code also ships built-in subagents (Explore, for codebase search; Plan) that cover general-purpose delegation without needing a custom definition for everything.

---

## Part 4 — One hook worth setting up now

Given Report 1's explicit flag that the debit/credit rules layer must never silently break, this is the one place a hook (deterministic enforcement, not a prompt) is worth setting up early rather than leaving to discipline:

**A `PostToolUse` or pre-commit-style hook that runs the rules-layer test suite whenever the relevant files change, and blocks the action if any balance-check test fails.**

This turns "the rules layer must always balance" from a thing someone has to remember into a thing that's mechanically impossible to violate silently — which is exactly the same design principle Report 1 applies to the product itself (keep deterministic logic out of the probabilistic layer), just applied to the build process this time.

---

## Part 5 — Suggested build sequence using these tools, mapped to Report 2's milestones

This is the part that's this report's own proposal, not documented Claude Code guidance — react to it, don't treat it as fixed.

| Report 2 milestone | Claude Code approach |
|---|---|
| M1 — COA + rules layer | Build the `vault-ledger-entry-rules` skill first (it's the spec), then have Claude implement against it directly in the main session — small enough not to need a subagent. Set up the rules-layer hook here too, since the code exists to test against. |
| M2 — OCR on real samples | Write the `vault-ledger-ocr-extraction` skill, then delegate actual extraction runs to the `ocr-runner` subagent as you test against each sample document — keeps repeated OCR output out of your main thread. |
| M3 — Field separation | Same skill/subagent pair as M2 — this is really "M2, but validated for the vendor/description split specifically." Worth having the OCR skill explicitly check for this, per Part 2 above. |
| M4 — Two-field classifier | Write the `vault-ledger-classifier` skill, then use the `classifier-eval` subagent for actual training/evaluation runs — especially once you're iterating on multiple training data batches and don't want every run's full output in context. |
| M5 — End-to-end wiring | Main session work — this is integration, best done with full context of all the pieces, not a good candidate for delegation. |
| M6 — Confidence gate | Small, main-session work — a thin layer on top of M4's output. |
| M7 — Correction loop | Main session for the UI/logging mechanism; can delegate periodic re-training runs to `classifier-eval` once corrections accumulate. |
| M8 — Real pilot run | Main session — this is validation and observation, not a coding task suited to delegation. |

**General pattern worth internalizing rather than following rigidly:** skills are worth writing as soon as a procedure will be repeated more than once or handed to a subagent; subagents are worth defining once a stage produces enough repetitive noise to justify context isolation; hooks are worth setting up specifically where "this must never silently fail" is true, which in this project is really just the rules layer.

---

## Part 6 — What this setup buys you that a single long chat session wouldn't

- **Milestone 2–4 work stays out of your main context.** OCR runs and classifier training/eval produce a lot of intermediate noise; subagents mean your main session stays focused on integration decisions, not scrollback.
- **The rules layer gets a hard guarantee, not a reminder.** The hook makes "entries always balance" a build-time invariant instead of something that depends on someone remembering to run the tests.
- **Knowledge survives across sessions.** Skills written to the repo mean a new Claude Code session (or you, six weeks from now) picks up the same procedures without re-explaining the two-field fusion decision or the debit/credit rules from scratch — the skill files themselves become part of the project's institutional memory, which matters given how much of this plan came from synthesizing several reference papers into decisions worth not re-litigating.
