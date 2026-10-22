# VaultLedger — ML Categorization Engine: Implementation Spec

**Audience:** an implementing Claude agent (e.g. Claude Code) with no prior context.
**Status:** approved direction, ready to implement. Written 2026-10-13.
**Scope:** the transaction-categorization engine only (bank transaction → ledger account suggestion), with DragoNet as the core model. Document extraction (OCR), LLM summaries, fraud detection and API integrations are out of scope.

---

## 0. How to use this document

1. Read sections 1–3 before writing any code. They contain constraints that change design choices.
2. Implement in the milestone order in section 9. Each milestone has acceptance criteria; don't start the next until the current one passes.
3. Anything marked **[OPEN]** is an unresolved product question. Don't decide it — make it a config value with the stated default.
4. Anything marked **[VERIFY]** is a fact this spec isn't certain of. Check it before relying on it.
5. **There is no real data yet.** Everything is built and tested on synthetic data (section 7). Accuracy numbers from synthetic data say *nothing* about real-world performance. Never report them as product accuracy, in code comments, READMEs, logs or summaries.

---

## 1. Product context (short)

VaultLedger is a privacy-first AI bookkeeping tool, Netherlands-first, aimed at accountants and SMBs.

Core loop: transactions come in → the engine suggests a ledger account for each → the accountant confirms or corrects → corrections improve future suggestions → results export to the customer's bookkeeping software.

Onboarding (planned): each company provides an export of its already-categorized historical transactions (QuickBooks/Xero/etc.). The model adapts to that company **on the device** before going live.

---

## 2. Hard constraints

| # | Constraint | Consequence for implementation |
|---|---|---|
| C1 | **On-device. No company data leaves the device.** | No network calls anywhere in the inference or per-company training path. No cloud APIs, no remote model hosting, no telemetry containing transaction data. |
| C2 | **Ordinary office hardware, CPU only.** | Inference model must be small (target < 25 MB on disk after quantization) and fast (target < 5 ms per transaction on one CPU core, batch 1). Per-company fine-tuning must finish in minutes on a laptop CPU. |
| C3 | **Deterministic logic stays out of the ML layer.** | Debit/credit construction, arithmetic, tax rules and hierarchy validity are code/rules, never model outputs. The model only *ranks categories*. |
| C4 | **No real data yet.** | Build a synthetic data generator first. Design every data path so a real export can be swapped in via one adapter, with no other code changes. |
| C5 | **NL first.** | Taxonomy aligned to RGS (Dutch reference chart of accounts). Text is mixed Dutch/English. Audit export eventually targets XAF 4.0. |
| C6 | **Accountant trust matters more than raw automation.** | Every suggestion carries a calibrated confidence and the name of the layer that produced it. Low confidence means "send to review", never a silent guess. |

---

## 3. Architecture overview

The engine is a cascade. Each layer either decides with high confidence or passes the transaction on. Every decision records which layer made it.

```
                raw transaction (bank export row)
                              │
                     ┌────────▼────────┐
                     │ L0 Normalize    │  clean counterparty name, parse fields
                     └────────┬────────┘
                     ┌────────▼────────┐
                     │ L1 Rules        │  deterministic (tax office, own-account
                     │  (JSON, versioned)│  transfers, salary batches...) → decide
                     └────────┬────────┘
                     ┌────────▼────────┐
                     │ L2 Counterparty │  "this vendor went to account X 47/48
                     │    memory       │  times" → decide if consistent enough
                     └────────┬────────┘
                     ┌────────▼────────┐
                     │ L3 DragoNet     │  two-field fused model → macro + micro
                     │  + taxonomy mask│  probabilities, hierarchy enforced
                     └────────┬────────┘
                     ┌────────▼────────┐
                     │ L4 Company map  │  reference category (RGS-level) →
                     │                 │  this company's own account
                     └────────┬────────┘
                     ┌────────▼────────┐
                     │ L5 Calibrate +  │  auto-suggest / needs-review / unknown
                     │    abstain      │
                     └────────┬────────┘
                              ▼
                 Suggestion {account, confidence, layer, alternatives}
                              │
               accountant confirms/corrects ──► L6 Correction log
                                               (updates L2 instantly,
                                                retrains L3 head/L4 in batch)
```

### The key design idea: shared reference taxonomy + per-company mapping

- The DragoNet model predicts categories in a **shared reference taxonomy** (RGS-aligned, section 5). This model is generic and identical for every customer.
- Each company has its **own** chart of accounts. Layer L4 maps reference category → company account, learned from that company's export (a "brugstaat", i.e. bridge table — the same concept RGS itself uses).
- This answers the open "one generic base model vs. fully independent per-company models" question: the shared base keeps improving centrally on synthetic or public data, while personalization stays local and lightweight.

---

## 4. Data schemas

All schemas are defined in `vaultledger/schemas.py` as dataclasses or pydantic models. Everything downstream consumes these, never raw CSVs.

### 4.1 `Transaction` (input)

| Field | Type | Required | Notes |
|---|---|---|---|
| `txn_id` | str | yes | Stable unique id (hash of source row if none given). |
| `company_id` | str | yes | |
| `date` | date | yes | |
| `amount` | Decimal | yes | Always positive. Use `Decimal`, never float, for money. |
| `direction` | enum `IN`/`OUT` | yes | |
| `currency` | str | yes | Default `EUR`. |
| `counterparty_name` | str | yes (may be empty) | Raw, as in bank export. |
| `counterparty_iban` | str \| None | no | Used by rules and memory, never sent anywhere. |
| `description` | str | yes (may be empty) | Bank "omschrijving" / memo. |
| `activity_code` | str \| None | no | Counterparty business-activity code (KvK SBI) if known. See 6.4.2. |
| `vat_rate` | Decimal \| None | no | If known from linked invoice. |
| `own_account_ibans` | — | — | Not a field: company-level config used by rules. |

### 4.2 `Label` (training target, from export or correction)

| Field | Type | Notes |
|---|---|---|
| `txn_id` | str | |
| `company_account_id` | str | The company's own account code/name. |
| `ref_macro` | str \| None | Reference macro category (filled via L4 mapping or synthetic generator). |
| `ref_micro` | str \| None | Reference micro category. |
| `source` | enum `EXPORT`/`CORRECTION`/`SYNTHETIC` | |
| `quality` | enum `OK`/`LOW` | `LOW` = came from an Uncategorized/Misc/Suspense bucket or flagged as inconsistent. `LOW` labels are excluded from training (configurable). |

### 4.3 `Suggestion` (output)

| Field | Type | Notes |
|---|---|---|
| `txn_id` | str | |
| `company_account_id` | str \| None | None means "unknown, needs review". |
| `ref_macro`, `ref_micro` | str \| None | |
| `confidence` | float [0,1] | Calibrated (section 6.6). |
| `status` | enum `AUTO`/`REVIEW`/`UNKNOWN` | |
| `layer` | enum `RULE`/`MEMORY`/`MODEL`/`COA_FALLBACK` | Which layer decided. |
| `rule_id` | str \| None | Internal only; never shown to end users. |
| `alternatives` | list[(account, confidence)] | Top-3 for the review UI. |
| `model_version` | str | |

### 4.4 `CompanyConfig`

`company_id`, `own_account_ibans`, `chart_of_accounts` (list of `{account_id, name, type}`), `ref_to_company_map` (learned), and thresholds.

---

## 5. Reference taxonomy (starter)

File: `vaultledger/taxonomy/reference_taxonomy.yaml`. Two levels, macro → micro. This is a **starter**, roughly RGS-shaped, to be refined against the real RGS later.

**[VERIFY]** Map each micro category to actual RGS reference codes (at least at the "Rekeningen"/account level) before any real customer use. Don't invent RGS codes. Leave `rgs_code: null` until verified.

| Macro | Micro categories |
|---|---|
| `REVENUE` | sales_domestic, sales_eu, sales_non_eu, other_income |
| `COGS` | purchases_inventory, subcontracting, freight_in |
| `PERSONNEL` | salaries, payroll_tax_pension, travel_reimbursement, training_education |
| `HOUSING` | rent, energy, water, cleaning_maintenance |
| `OFFICE_IT` | software_subscriptions, hardware, telecom_internet, office_supplies |
| `TRANSPORT` | fuel, public_transport, parking, car_lease, taxi_ride_hailing |
| `MARKETING` | advertising, representation_meals, gifts_relations |
| `PROFESSIONAL` | accounting_fees, legal_fees, consulting |
| `FINANCIAL` | bank_fees, interest, insurance |
| `TAX` | vat_payment, vat_refund, corporate_income_tax, other_taxes |
| `BALANCE` | own_account_transfer, loan_repayment, owner_withdrawal, owner_deposit |
| `SUSPENSE` | uncategorized (never a training target; a sink for `LOW` labels) |

Rules:

- Every micro has exactly one macro parent. The taxonomy loader validates this at startup and fails loudly otherwise.
- Each micro has an `allowed_direction` (`IN`, `OUT`, or `BOTH`). Example: `salaries` is `OUT`, `sales_domestic` is `IN`. The mask (6.4.4) uses it.
- The taxonomy is versioned (`taxonomy_version`). Models store the version they were trained on, and loading a mismatched model raises an error.

---

## 6. Components

### 6.1 L0 — Normalization (`vaultledger/normalize.py`)

Pure functions with unit tests for each rule.

- `normalize_counterparty(name) -> str`:
  - lowercase, strip accents, collapse whitespace
  - strip payment-processor prefixes and patterns: `ccv*`, `sumup *`, `zettle_*`, `paypal *`, `bea`, `gea`, `ideal`, `sepa`, `incasso`, etc. Keep the list in `normalize_prefixes.yaml`.
  - strip store/terminal numbers and trailing location tokens: `albert heijn 1234 delft` → `albert heijn`
  - strip legal suffixes: `b.v.`, `bv`, `n.v.`, `v.o.f.`, `vof`, `ltd`, `gmbh`, `inc`
- `normalize_description(text) -> str`: lowercase, then mask digits runs (≥4 digits → `<num>`), dates → `<date>`, IBANs → `<iban>`, reference codes → `<ref>`.
- Keep the raw value too. Normalized values are only used for features and memory keys.

**Acceptance:** at least 30 table-driven unit tests covering real-looking NL bank strings.

### 6.2 L1 — Deterministic rules (`vaultledger/rules/`)

Rules are **data, not code**, following the VERAFI paper's pattern (arXiv:2512.14744): versioned JSON, each with a machine condition plus a plain-language explanation.

```json
{
  "id": "R-NL-001",
  "version": 1,
  "description": "Payments to the Belastingdienst with 'omzetbelasting' or 'btw' in the description are VAT payments.",
  "when": {
    "all": [
      {"field": "counterparty_norm", "op": "in", "value": ["belastingdienst"]},
      {"field": "description_norm", "op": "contains_any", "value": ["omzetbelasting", "btw"]},
      {"field": "direction", "op": "eq", "value": "OUT"}
    ]
  },
  "then": {"ref_micro": "vat_payment"},
  "confidence": 0.99,
  "alternate_expression": "If we pay the tax office for VAT, book it as a VAT payment."
}
```

- Ops to support: `eq`, `in`, `contains_any`, `regex`, `amount_between`, `iban_in_own_accounts`.
- Starter rules: VAT payment and refund, other Belastingdienst payments, own-account transfers (counterparty IBAN in `own_account_ibans`), bank fees (description patterns like `kosten`, `rente`), salary batch payments.
- Conflict handling: if two rules fire with different outcomes, decide nothing, pass the transaction on, and log the conflict.
- Debit/credit entry construction (which side of the ledger, VAT split) is also rule-based and lives here or in `vaultledger/entries.py`. The model never produces it.
- `rule_id` is internal. It must never appear in user-facing text (VERAFI recommendation).

**Acceptance:** a rules engine with unit tests per op, a JSON schema validated on load, and conflict detection tested.

### 6.3 L2 — Counterparty memory (`vaultledger/memory.py`)

- Key: `(company_id, counterparty_norm)`. Fall back to `(company_id, iban)` if the name is empty.
- Value: counts of `company_account_id` observed (from export labels and corrections).
- Decide when total count ≥ `memory_min_count` (default 3) **and** top account share ≥ `memory_min_share` (default 0.9).
- Confidence = smoothed share, e.g. `(top + 1) / (total + 2)`.
- Corrections update memory **immediately**, and a correction outweighs an export label (weight `correction_weight`, default 3).
- Storage: a local SQLite file per company. No network.

**Acceptance:** unit tests for thresholds, correction weighting, and the empty-name IBAN fallback.

### 6.4 L3 — DragoNet-style model (the core)

Reference: Busson et al., *Two-headed DragoNet* (BTG Pactual), arXiv:2312.07730. What carries over:

- Two text fields, each encoded by its own Transformer encoder.
- A context-fusion layer joining them.
- Two output heads: macro and micro category.
- A deterministic taxonomy-aware mask at inference that removes micro predictions inconsistent with the macro.

Their findings that motivate this design: merchant name alone is weak (about 57–59% macro-F1) because names are generic or ambiguous. The activity field alone is strong (about 89–93%) but breaks when a merchant is registered under the wrong activity. Fusing both was best (about 93% macro-F1 at macro level). The mask added about 1 point on micro.

**[VERIFY]** The exact layer sizes and fusion operator in the paper. The values below are this spec's choices sized for CPU and small data. They are not the paper's.

#### 6.4.1 Inputs

- **Field A — name:** `counterparty_norm`.
- **Field B — context:** a concatenation of `description_norm` + `" [ACT] "` + activity text (the SBI description if `activity_code` is known, else empty).
- **Numeric side features** (not in DragoNet; cheap and useful): `log1p(amount)`, `direction` (one-hot), day-of-month bucket, `is_round_amount`, `vat_rate` (or missing flag), `has_iban`.

#### 6.4.2 About the activity field (important)

DragoNet's strongest signal was the merchant's registered business activity. The closest NL equivalent is the **KvK SBI code**. Constraint C1 rules out looking it up online at inference time, since that would send vendor names off the device. Options, in order of preference:

1. An offline lookup table (normalized name → SBI code) shipped with the app. **[VERIFY]** whether KvK open data or another licensed source allows this, and how it can be updated.
2. Learn the activity from the company's own export (vendors the company already used).
3. Leave it empty. The model must work without it, so train with the activity text randomly dropped (`activity_dropout`, default 0.5).

The mis-registration failure mode from the paper (activity says one thing, reality another) must be represented in the synthetic data (section 7).

#### 6.4.3 Architecture (`vaultledger/model/dragonet.py`, PyTorch)

```
Field A tokens ──► Embedding(V, d) + pos ──► TransformerEncoder(L layers) ──► mean-pool ──► hA (d)
Field B tokens ──► Embedding(V, d) + pos ──► TransformerEncoder(L layers) ──► mean-pool ──► hB (d)
numeric feats  ──► Linear(n, d/2) ──► GELU ──────────────────────────────────────────────► hN (d/2)

Context fusion:  h = concat[hA, hB, hA*hB, |hA-hB|, hN] ──► Linear ──► GELU ──► Dropout ──► z (d)

Macro head:  logits_M = Linear(d, n_macro)(z)
Micro head:  logits_m = Linear(d + n_macro, n_micro)(concat[z, softmax(logits_M)])
```

Default hyperparameters (config, not hard-coded):

| Param | Default | Notes |
|---|---|---|
| tokenizer | SentencePiece unigram, vocab 8000, trained locally on the training text | Handles Dutch/English and vendor-name noise. No downloads at runtime. |
| `d` | 128 | |
| `L` | 2 encoder layers per field | |
| heads | 4 | |
| ff dim | 256 | |
| max_len A / B | 16 / 48 tokens | |
| dropout | 0.1 | |
| `activity_dropout` | 0.5 | Drops the activity part of Field B during training. |
| field dropout | 0.1 | Randomly blanks a whole field so the model survives empty names or descriptions. |
| loss | `CE(macro) + λ·CE(micro)`, λ = 1.0 | Use label smoothing 0.05. Use class weights if classes are imbalanced. |
| optimizer | AdamW, lr 1e-3 (warmup 5%, cosine decay), wd 0.01 | |
| early stopping | on validation micro macro-F1, patience 3 | |

The two encoders do **not** share weights by default (`share_encoders: false`), as in DragoNet. Keep weight sharing as a config option to test, since it halves the size.

#### 6.4.4 Taxonomy-aware mask (inference, deterministic)

Implement in `vaultledger/model/mask.py`, separate from the network, so it is testable without a model.

1. Compute `p_M = softmax(logits_M)` and `p_m = softmax(logits_m)`.
2. Direction mask: zero out micro classes whose `allowed_direction` conflicts with the transaction's direction. Zero out macro classes with no remaining valid children.
3. **Joint decoding** (preferred over plain argmax-then-mask): for every valid (macro, micro) pair where micro is a child of macro, `score = log p_M[macro] + log p_m[micro]`. Pick the best pair, and renormalize the scores over valid pairs to get pair probabilities.
4. Also implement DragoNet's original version (argmax macro, then mask micro to its children) behind a flag, for the ablation in 8.3.

**Guarantee:** the output micro is always a valid child of the output macro, and always direction-consistent. Property-test this with random logits.

#### 6.4.5 Training phases

- **Phase A — base model (central, not on-device):** train on synthetic data, and later on any public or licensed data in the reference taxonomy. Produces `dragonet_base_vX.onnx` plus the tokenizer.
- **Phase B — per-company adaptation (on-device):** freeze the tokenizer and both encoders. Fine-tune only the fusion layer and heads on the company's export labels (mapped to the reference taxonomy via L4), for a few epochs.
  - Skip Phase B entirely if the company has fewer than `min_finetune_labels` usable labels (default 300) **[OPEN]**. Use the base model only.
  - Keep Phase B only if it beats the base model on a held-out slice of the company's own data. Otherwise keep the base model and log the result.
  - It must run in about 5 minutes or less on a laptop CPU for 10k transactions.

#### 6.4.6 Deployment format

- Export to ONNX. Run inference with `onnxruntime`. Apply dynamic int8 quantization, and check the accuracy drop is under 1 point on the validation set.
- The inference path needs no PyTorch, only `onnxruntime`, `sentencepiece` and `numpy`.
- Phase B training on-device needs PyTorch CPU. **[OPEN]** whether to ship PyTorch in the app or implement head-only fine-tuning in numpy. The heads are small, so numpy is feasible. Default: PyTorch in a separate training process.

#### 6.4.7 Baseline (build this FIRST, before DragoNet)

`vaultledger/model/baseline.py`, scikit-learn:

- Char n-gram TF-IDF (2–5 grams) on Field A, plus word and char TF-IDF on Field B, plus the numeric features, all concatenated.
- Two `LogisticRegression` models (macro and micro) using the same taxonomy mask and joint decoding.

Reasons it comes first: it validates the whole pipeline in an afternoon. It's the bar DragoNet has to beat. And it's the fallback if DragoNet doesn't beat it on real data. **Do not delete it when DragoNet works.**

### 6.5 L4 — Company mapping (`vaultledger/company_map.py`)

Maps reference micro categories to the company's own accounts.

- **Learned from the export:** for each company account, take the model's predicted reference micro over that account's transactions. Build a count matrix (reference micro × company account) and derive `P(company_account | ref_micro)`.
- **Many-to-one** (several reference categories into one company account, e.g. a company that books everything to "Algemene kosten"): handled naturally by the matrix.
- **One-to-many** (one reference category split across several company accounts): when `P(company_account | ref_micro)` has no dominant account (top share < 0.8), train a small per-company logistic-regression head on the frozen DragoNet fusion vector `z`, only for that reference category's transactions.
- **t=0 fallback (COA similarity), when no usable export exists:** match company account names to reference categories using keyword lists plus fuzzy string similarity (`rapidfuzz`), e.g. "Huur kantoor" → `rent`. Mark these suggestions `layer=COA_FALLBACK` and always `status=REVIEW`.

**Acceptance:** works on synthetic companies with deliberately different COAs (section 7.4), including one many-to-one and one one-to-many case.

### 6.6 L5 — Calibration and abstention (`vaultledger/calibrate.py`)

- **Temperature scaling** per head, fitted on the validation set. Report ECE (expected calibration error) before and after.
- Final confidence = the calibrated pair probability × the L4 mapping probability.
- Status:
  - `AUTO` if confidence ≥ `auto_threshold`. Default: choose the threshold that achieves `target_precision` (default 0.95) on validation.
  - `REVIEW` if `review_floor` (default 0.3) ≤ confidence < `auto_threshold`.
  - `UNKNOWN` below the floor. The account is left empty and the top-3 alternatives are shown.
- **Launch mode** (C6): a company-level flag `suggest_only = true` by default. Everything is `REVIEW` until the accountant's agreement rate over the last N=200 reviewed suggestions exceeds a configurable level. **[OPEN]** the exact policy. Implement the flag and the agreement-rate metric only.
- **Out-of-distribution guard:** if the transaction's normalized name contains no token known to the tokenizer's training data, or the fusion vector's distance to the nearest training centroid is above a threshold, cap the status at `REVIEW`.

### 6.7 L6 — Correction loop (`vaultledger/corrections.py`)

- An append-only correction log (SQLite), recording: txn, old suggestion (full `Suggestion` object), new account, timestamp, user id.
- On each correction: update L2 memory immediately, and add the item as a `CORRECTION` label.
- Retraining: the Phase B head and L4 mapping retrain after every `retrain_every_n` corrections (default 50) or on demand. **[OPEN]** cadence. Make it configurable, including `retrain_every_n = 1` for "instant" mode.
- The log is also the source for the audit export (6.8).

### 6.8 Export (`vaultledger/export/`)

Two **separate** files (decided):

1. **Bookkeeping import file:** a minimal clean row per transaction (date, amount, account, VAT code, description). Make the format a pluggable writer per target platform. **[OPEN]** which platforms come first (QuickBooks/Xero suspected). Build a generic CSV writer plus a writer interface. **[VERIFY]** each platform's *import* schema (it often differs from the export schema) before writing platform-specific writers.
2. **Audit file:** everything per transaction: suggestion, confidence, layer, model version, rule_id, correction history, timestamps. Generic CSV/JSON now. **[VERIFY]** the XAF 4.0 spec (Auditfile Financieel, mandatory in NL since 2026-01-01, RGS-aligned XML) before building an XAF writer. Leave a stub interface for it.

---

## 7. Synthetic data generator (`vaultledger/synth/`)

**Purpose:** test that the pipeline works end to end and that each layer behaves as intended. **Not** for estimating real accuracy.

The generator must be seeded and deterministic, and configurable via YAML.

### 7.1 Vendor catalog

`synth/vendors.yaml`: for each reference micro category, 10–40 vendors. Each vendor has a canonical name, name variants, an optional SBI-like activity text, typical description templates, an amount distribution (lognormal μ, σ), recurrence (monthly, weekly, ad hoc), and a direction.

Use realistic NL examples, e.g. `energy`: Eneco, Vattenfall, Essent; `telecom_internet`: KPN, Odido, Ziggo; `public_transport`: NS, GVB, RET; `software_subscriptions`: Microsoft, Google Workspace, Adobe, Exact; `representation_meals`: restaurants and cafés with generic names.

### 7.2 Noise and hard cases (must all be present, each with a config rate)

- Processor prefixes and store numbers: `CCV*ALBERT HEIJN 1234 DELFT`
- Truncation (bank exports cut long names), case and spacing noise, typos
- Mixed Dutch/English descriptions; empty descriptions; empty names
- **Ambiguous vendors** that legitimately map to more than one category depending on context (e.g. a supermarket as `representation_meals` vs `office_supplies`; Amazon/bol.com as `hardware` vs `office_supplies`). Context like amount or description should be the only way to tell.
- **Generic names** with no signal ("Red Shop", "Thunder" style — the paper's examples)
- **Mis-registered activity codes:** the activity text belongs to the wrong category (DragoNet's failure mode), default rate 5%
- Missing activity (default 50%)
- **Label noise:** wrong labels at a configurable rate (default 3%); `Uncategorized` labels (default 5%, marked `quality=LOW`)
- Vendors appearing only in the test set (unseen vendors), so generalization is actually tested

### 7.3 Volume

Default: 30 synthetic companies × 1–5k transactions over 12–24 months, about 80k transactions in total, with a long-tailed class distribution.

### 7.4 Per-company COAs

Each synthetic company gets its own chart of accounts, generated from the reference taxonomy by random merges (many-to-one), splits (one-to-many, e.g. `software_subscriptions` split into "Software – Microsoft" and "Software – other"), renames (Dutch names, numbered codes) and an Uncategorized account. This tests L4.

### 7.5 Output

The generator writes data in the same `Transaction`/`Label` schema a real export adapter will produce, plus the hidden ground-truth reference labels for evaluation only.

### 7.6 Real-data adapter interface

`vaultledger/io/adapters.py`: `class ExportAdapter: def load(path) -> (list[Transaction], list[Label], CompanyConfig)`. Implement `SyntheticAdapter` now and stub `QuickBooksCsvAdapter` and `XeroCsvAdapter` raising `NotImplementedError` with a TODO. When a real export arrives, only an adapter needs writing.

---

## 8. Evaluation harness (`vaultledger/eval/`)

### 8.1 Splits (important)

- **Group split by counterparty** within each company (`GroupShuffleSplit` on `counterparty_norm`), so the test set contains vendors the model never saw. A random row split leaks vendors and makes every layer look far better than it is.
- Also report a **time split** (train on the first 80% of months, test on the rest), since that matches real usage.
- Hold out entire synthetic companies (default 5 of 30) to test base-model generalization and the cold start.

### 8.2 Metrics (reported for every run, into `reports/<run_id>.json` and a markdown summary)

- Macro-F1 and micro-F1 (averaging), at both the macro and micro category level
- Company-account accuracy (after L4)
- **Coverage at precision 95%:** the share of transactions marked `AUTO` while those `AUTO` suggestions are ≥95% correct. **This is the headline product metric.**
- ECE before and after calibration
- Per-layer breakdown: share of transactions decided by each layer, and precision per layer
- Hierarchy-violation count (must be 0 after the mask)
- Latency: p50/p95 per transaction for ONNX inference

### 8.3 Required ablations (mirroring DragoNet)

| Run | Purpose |
|---|---|
| Field A only | Reproduce the "name alone is weak" finding |
| Field B only | |
| A + B fused | The full model |
| Fused, mask off | Measure what the mask adds |
| DragoNet argmax mask vs. joint decoding | |
| Baseline (TF-IDF + LR) vs. DragoNet | DragoNet must beat this to justify itself |
| Full cascade (L1–L5) vs. model only | |
| Phase B fine-tune vs. base only, by label count (100/300/1k/3k) | Informs `min_finetune_labels` |

Every report must open with this line: *"Results on synthetic data. Not indicative of real-world accuracy."*

---

## 9. Milestones (implement in this order)

| # | Milestone | Acceptance criteria |
|---|---|---|
| M1 | Repo skeleton, schemas, taxonomy loader | Taxonomy validation test passes; schemas importable; `pytest` runs in CI. |
| M2 | Synthetic generator | Deterministic with a seed; all hard cases in 7.2 present, with counts in a generator report; per-company COAs generated. |
| M3 | L0 normalization + L1 rules + L2 memory | Unit tests as specified; cascade runs with stub model. |
| M4 | Mask + joint decoding module | Property test: zero hierarchy/direction violations over 10k random logit draws. |
| M5 | Baseline model + eval harness | Group-split eval runs end to end and produces a report with all 8.2 metrics. |
| M6 | DragoNet model + training (Phase A) | Trains on synthetic data in < 30 min on CPU; ablations in 8.3 run; report generated. |
| M7 | ONNX export + quantization + inference path | ONNX output matches PyTorch within tolerance; accuracy drop < 1 pt; latency targets met; inference has no torch import. |
| M8 | L4 company mapping + COA fallback | Correct handling of many-to-one and one-to-many synthetic companies. |
| M9 | L5 calibration/abstention + suggest-only mode | ECE reported; thresholds set from target precision; status logic tested. |
| M10 | Phase B fine-tune + L6 correction loop | Fine-tune finishes in ≤ 5 min on 10k txns; kept only if it beats base on held-out slice; corrections update memory instantly. |
| M11 | Export writers (generic CSV + audit file) + adapter stubs | Two separate files written; audit file includes full history. |

---

## 10. Repo layout

```
vaultledger-ml/
  pyproject.toml
  README.md                     # includes the synthetic-data disclaimer
  configs/
    default.yaml                # all thresholds and hyperparameters in one place
    synth.yaml
  vaultledger/
    schemas.py
    normalize.py
    normalize_prefixes.yaml
    taxonomy/
      reference_taxonomy.yaml
      loader.py
    rules/
      engine.py
      rules_nl.json
      rule_schema.json
    memory.py
    model/
      tokenizer.py              # SentencePiece train/load
      baseline.py
      dragonet.py
      mask.py
      train.py                  # Phase A
      finetune.py               # Phase B
      export_onnx.py
      infer.py                  # onnxruntime-only inference
    company_map.py
    calibrate.py
    cascade.py                  # wires L0–L5, returns Suggestion
    corrections.py
    export/
      bookkeeping_csv.py
      audit.py
      xaf_stub.py
    io/
      adapters.py
    synth/
      generator.py
      vendors.yaml
    eval/
      splits.py
      metrics.py
      run_eval.py
      ablations.py
  tests/
  reports/                      # gitignored
```

Stack: Python 3.11+, PyTorch (CPU) for training, onnxruntime for inference, scikit-learn, sentencepiece, numpy, pandas, rapidfuzz, pydantic, pytest, hypothesis (for property tests). Nothing that needs a GPU or a network connection at runtime.

---

## 11. Do NOT

- Don't let the model compute amounts, VAT splits or debit/credit sides.
- Don't add any network call in the inference or per-company training path (including model downloads at runtime, telemetry with transaction content, or online KvK lookups).
- Don't use a pretrained model that requires downloading weights at app runtime. If you add a pretrained encoder later, it must ship inside the app bundle.
- Don't report synthetic-data metrics as product accuracy anywhere.
- Don't use a random row split for evaluation. Use the group split by counterparty.
- Don't train on `quality=LOW` labels by default.
- Don't show `rule_id`, internal layer names or thresholds in user-facing text.
- Don't add an LLM, fraud/anomaly detection, DP-SGD, federated learning or bookkeeping-platform API integrations. These are all out of scope for this phase.
- Don't decide **[OPEN]** items. Make them configurable with the stated default.

---

## 12. Open questions (leave as config)

| Item | Default | Config key |
|---|---|---|
| Minimum labels before Phase B fine-tuning | 300 | `min_finetune_labels` |
| Retrain cadence after corrections | every 50 | `retrain_every_n` |
| Suggest-only exit policy | stay on | `suggest_only`, `agreement_window` |
| Target precision for AUTO | 0.95 | `target_precision` |
| On-device training runtime (PyTorch vs numpy heads) | PyTorch subprocess | `finetune_backend` |
| First bookkeeping platforms for import files | generic CSV | `export.platforms` |
| Source of activity (SBI) data | none / learned from export | `activity_source` |

---

## 13. What happens when real data arrives

1. Write the adapter for that export format (7.6).
2. Run the label-quality report: share of Uncategorized, inconsistent vendor labels, class distribution.
3. Run the full eval (section 8) on the real data with group and time splits.
4. Compare baseline vs DragoNet vs full cascade on **coverage at 95% precision**. This decides what ships.
5. Retune thresholds and `min_finetune_labels` from the real numbers.

---

## 14. References

- Busson et al., *Two-headed DragoNet: A Hierarchical Transaction Classifier* (BTG Pactual), arXiv:2312.07730 — core model design, two-field fusion, taxonomy mask.
- Akinfaderin & Subramanian, *VERAFI* (AWS), arXiv:2512.14744 — rules-as-data format, tool routing for arithmetic, hide rule mechanics from users.
- Azman et al., *SME Automated Bookkeeping AI* (UiTM), JOIV 2021 — adoption barriers (knowledge constraints rank above cost), which motivates suggest-only mode and visible confidence.
- Tagade & Rumbelow, *Prototype Generation* (Leap Labs), arXiv:2309.17144 — post-MVP practice: periodically inspect what each class has learned to catch shortcut patterns that accuracy doesn't reveal.
- RGS (Referentie GrootboekSchema) and XAF 4.0 (Auditfile Financieel) — NL chart-of-accounts reference standard and mandatory audit-file format. **[VERIFY]** details against the official specs.
