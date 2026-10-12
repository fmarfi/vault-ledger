# Report 1 — Vault Ledger MVP: Technicalities & What Must Be Done ASAP

**Scope of this report:** the invoice-in → journal-entry-out MVP, updated to the two-field fusion approach (vendor name + description, kept separate through classification) instead of the earlier single-text-blob notebook approach, which is now dropped.

## The pipeline (current version)

```
Document (PDF/image)
      │
      ▼
1. OCR / extraction ──────────► raw text (+ rough layout if available)
      │
      ▼
2. Field parsing ─────────────► vendor name, description/line-item text,
                                 date, amount — vendor and description
                                 kept as SEPARATE fields, not concatenated
      │
      ▼
3. Account judgment (ML) ─────► two-field fusion classifier:
                                 vendor → vectorizer A ┐
                                                        ├─► concat → classifier → account + confidence
                                 description → vectorizer B ┘
      │
      ▼
4. Entry construction (rules) ► deterministic debit/credit construction
                                 (see companion rules spec — unchanged)
      │
      ▼
5. Confidence gate ───────────► auto-suggest vs. manual review
      │
      ▼
Proposed journal entry (accountant reviews/edits/confirms)
      │
      ▼
Correction feeds back into step 3 as labeled training data
```

## What changed from the original plan, and why it matters for build priority

- **Dropped:** the TF-IDF + Linear Regression notebook, trained on a public personal-expense dataset with a single blended text field (`vendor + " " + description`).
- **Why:** a reference paper (Two-headed DragoNet, BTG Pactual) ran a controlled comparison on 150k+ real transactions and found that vendor name alone is a weak signal (~57% F1) and a single blended field underperforms keeping vendor and description as two separate inputs fused before classification (~93% F1 with both fields vs. much lower with either alone). This is a large enough gap that it changes what "step 3" needs to be built as, not just retrained.
- **Practical consequence:** extraction (step 2) now has a harder job — it must reliably output vendor name and description as two distinct fields. If extraction blurs them into one string, the classifier never gets the benefit that justified the two-field design in the first place. **This makes step 2 a higher-priority correctness target than it was under the old plan.**

## ASAP technical must-haves — in priority order

These are the items that block a working end-to-end demo. Nothing here is a nice-to-have.

### 1. Fixed chart of accounts (COA) — trivial but blocking
- 5–10 accounts covering common SME expense categories (e.g. Utilities, Office Supplies, Professional Services, General/Other) plus the mechanical accounts (Cash/Bank, Accounts Payable).
- Blocking because both the classifier's label space and the rules layer's valid-account check depend on this existing first.
- **Effort: trivial. Do this first, today, even before touching code.**

### 2. OCR extraction on 3 target document formats
- Formats: generic itemized vendor invoice, utility-style bill, retail receipt.
- Use the cheapest viable OCR (Tesseract locally, or a hosted OCR/document API) — extraction accuracy is not the bottleneck to optimize yet, the loop working end-to-end is.
- **Effort: small–medium.** Mostly integration work, not research.

### 3. Field parsing that separates vendor from description — now more important than before
- Must output **two distinct fields**, not one concatenated string: vendor name, and a description/line-item text field, plus date and amount.
- For the three target formats, regex/heuristic parsing (currency patterns, date patterns, position-based guesses like "vendor name is near the top") will get far before any ML is needed here.
- **This is the step most likely to silently undercut the whole two-field classifier gain if done carelessly — treat "are vendor and description reliably separated" as its own testable checkpoint, independent of classifier accuracy.**

### 4. Two-field fusion classifier (replaces the old notebook)
- Two separate vectorizers (TF-IDF is enough at this scale — no need for a Transformer architecture, which is BTG's infrastructure choice for 150k+ rows, not an MVP requirement) — one for vendor name, one for description.
- Concatenate the resulting feature vectors, feed into a single classifier over the fixed COA.
- Must output a confidence score per prediction, not just a label — this feeds the confidence gate (item 6).
- Needs real or realistic labeled data — the old Kaggle personal-expense categories do not transfer.
- **Effort: medium. This is the actual new ML work — budget real time here, don't treat it as "just retrain the old thing."**

### 5. Debit/credit entry-construction rules layer
- Deterministic code, not ML — already spec'd in the companion rules document and unaffected by the classifier change above.
- Handles: expense account (from step 4) as debit, Cash/Bank or Accounts Payable as credit depending on paid-vs-unpaid signal.
- Must enforce total debits = total credits before ever surfacing an entry, and must reject/flag any predicted account outside the fixed COA rather than guessing.
- **Effort: small. Can and should be built and unit-tested independently of the ML, using hand-written test cases, in parallel with items 2–4.**

### 6. Confidence gate
- Below threshold → manual review queue. Above threshold → proposed entry with edit/confirm.
- Threshold is a tuning knob, not a one-time decision — expect to adjust once real accuracy numbers exist.
- **Effort: trivial once step 4 outputs confidence scores.**

### 7. End-to-end wiring
- One script/flow: document in → printed proposed journal entry out. This is the first real internal milestone — before any UI exists.
- **This is the point at which you have something to demo, even in raw form.**

## Explicitly NOT ASAP (do not let these block the above)

- Per-client custom chart of accounts (fixed COA only for now)
- Any document format beyond the three target types
- Fraud/anomaly detection
- Differential privacy / DP-SGD training pipeline
- Multi-user firm dashboards
- Live/automatic retraining — periodic manual re-training on accumulated corrections is enough
- Taxonomy/hierarchy masking (DragoNet's Taxonomy-aware Attention idea) — only relevant once the COA grows past a flat list; not needed while it's still 5–10 flat accounts
- A polished correction UI — a minimal one (even spreadsheet-like) is enough until the core loop is proven

## Single biggest risk to flag now

The two-field classifier gain is entirely dependent on extraction quality (item 3). If OCR/field-parsing on real documents turns out messier than expected — vendor and description bleeding together, missing fields, inconsistent layouts even within the 3 target formats — the ML step won't be able to deliver the accuracy the reference paper suggests is possible, no matter how well the classifier itself is built. **Validate item 3 on real sample documents before investing heavily in item 4.**
