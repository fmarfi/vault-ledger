# Report 4 — Paper Reference Digest for the MVP Build

**Purpose:** every piece of information from the four uploaded papers that's actually usable while building — concrete numbers, techniques, prompt structures, and design patterns, organized by which part of the pipeline (Report 1) each one feeds. This is a reference document to pull from during the build, not something to read start-to-finish once and set aside.

**Papers covered:**
1. Two-headed DragoNet (Busson et al., BTG Pactual, arXiv:2312.07730) — hierarchical transaction classification
2. VERAFI (Akinfaderin & Subramanian, AWS, arXiv:2512.14744) — verified agentic financial intelligence
3. AI in Automated Bookkeeping for SMEs (Azman et al., UiTM, JOIV 2021) — SME bookkeeping automation literature review
4. Prototype Generation (Tagade & Rumbelow, Leap Labs, arXiv:2309.17144) — data-independent interpretability

---

## 1. For the classifier (Step 3 — Account judgment)

### From DragoNet: the two-field fusion finding, in full

DragoNet ran a controlled 3-way experiment (merchant name alone / description alone / both fused) across two real datasets (151,867 card transactions, 151,838 current-account transactions), evaluated with 10-fold cross-validation, comparing shallow models (KNN, SVC, Random Forest with TF-IDF/HashingVectorizer) against deep models (GRU, LSTM, BLSTM, Transformer).

**Exact numbers, macro-category F1:**

| Input | Card dataset (best model) | Current account dataset (best model) |
|---|---|---|
| Merchant name only | 56.78% (Transformer) | 59.14% (Transformer) |
| Description/activity only | 89.07% (Transformer) | 93.24% (Transformer) |
| Both fused | **93.02%** (Transformer + Context Fusion) | **95.07%** (Transformer + Context Fusion) |

**Micro-category F1 (fine-grained subcategory) with both fields fused:** 84.54% (card), 86.66% (current account) — and the Taxonomy-aware Attention layer specifically added ~0.9–1 percentage point on top of the plain fused model on micro-category accuracy, by masking out invalid subcategory predictions.

**What this means concretely for the classifier build:**
- Even the *simplest* classical model (TF-IDF + shallow classifier) benefited from having both fields — e.g. TF-IDF+RF jumped from ~38.6% F1 (name only) to ~80.9% F1 (both fields, card dataset) — so this finding is not specific to deep learning. **A simple TF-IDF-based fusion classifier should see most of this same gain.**
- The single biggest practical implication: merchant/vendor name is a weak, ambiguous signal on its own (their own example: "Red Shop", "Thunder", "Bluebird" — names with no inherent category signal). Don't expect vendor name alone to carry classification — it needs a second field.
- Their "business activity descriptor" was a formal field (ISO-18245 Merchant Category Code text for card data, Brazilian CNAE economic-activity text for account data) — a cleaner signal than what invoice OCR will typically produce. **Realistic expectation:** your "Field B" (extracted line-item/description text) will likely be noisier than their activity descriptor, so treat their ~89-93% description-only number as an upper bound, not a target to expect immediately.

### From DragoNet: encoding technique comparison (useful if TF-IDF underperforms)

They tested three text-encoding techniques: **TF-IDF, HashingVectorizer, and Tokenizer** (index-based, fed to deep models' embedding layers). TF-IDF and HashingVectorizer were paired with shallow models; Tokenizer was used for deep models. If a from-scratch TF-IDF fusion classifier underperforms, HashingVectorizer is a documented, easy-to-swap alternative that performed comparably in their shallow-model experiments (and scales better to larger vocabularies since it doesn't require a fit vocabulary pass).

### From DragoNet: the taxonomy structure itself (reusable when the COA grows)

Their full 15-macro/82-micro taxonomy (reproduced in the technical notes memory file and the original paper) is a validated real-world spending taxonomy. Concretely useful categories that map onto SME accounting needs: **Bill** (Water, Condominium/Rental, Energy, Gas, Telecommunication, Credit Card, Other Bill), **Tax & Tribute** (House Taxes, Car Taxes, Income Tax, Other), **Health**, **Home**, **Transport**. When the fixed 8-account MVP chart of accounts needs to expand, this taxonomy — already validated at 150k+ transaction scale — is a better starting point than inventing categories from scratch.

### From DragoNet: the Taxonomy-aware Attention mechanism, precisely

This is worth understanding exactly, since it's directly reusable as a design pattern (not the code, the mechanism):

> Given the macro-category prediction output `O^α` and micro-category prediction output `O^β`, construct a mask `M` where `M[i] = 1` if micro-category `i` is a valid child of `argmax(O^α)` (the predicted macro category), else `0`. The corrected micro-category output is `M · O^β` (element-wise multiplication) — this zeroes out the score of any micro-category that doesn't belong under the predicted macro category, before taking the final argmax.

This is pure post-hoc masking at inference time — no retraining required, and it's exactly the same "deterministic layer enforces validity, ML layer only predicts" pattern already used in the debit/credit rules design. **Applicable the moment the COA gets a second hierarchy level** (e.g. "Expense > Utilities > Water/Energy/Telecom").

---

## 2. For the entry-construction / validation layer (Step 4)

### From VERAFI: why free-text model reasoning fails at financial math, with numbers

VERAFI's central empirical finding, and the reason the debit/credit rules layer is deterministic code rather than model output:

| Approach | Factual correctness | Completeness |
|---|---|---|
| Dense retrieval + reranker only (no agent) | 52.4% | 72.6% |
| + Agentic processing (tool-based calculator/Python + web search) | 90.4% | 96.4% |
| + Neurosymbolic policy validation (full VERAFI) | **94.7%** | **96.4%** |

The jump from 52.4% → 90.4% came from giving the model **tools** (a calculator and a Python REPL) instead of letting it compute in free text — this is the most directly transferable lesson. The further 90.4% → 94.7% jump came from embedding **formal validation rules** into the prompt as contextual guidance (not as post-hoc rejection) — a smaller but real additional gain.

### From VERAFI: their actual policy rule format (directly reusable structure)

VERAFI encodes financial rules as JSON objects with two parallel representations — a formal SMT-lib logical expression and a natural-language "alternate expression." Real examples from their appendix (80+ rule set, these are representative):

```json
{"id": "ID8", "alternateExpression": "returnOnAssets is equal to netIncome / averageTotalAssets"}
{"id": "ID9", "alternateExpression": "debtToEquityRatio is equal to totalDebt / totalShareholdersEquity"}
{"id": "ID11", "alternateExpression": "currentRatio is equal to currentAssets / currentLiabilities"}
{"id": "ID15", "alternateExpression": "freeCashFlow is equal to operatingCashFlow - capitalExpenditures"}
{"id": "ID19", "alternateExpression": "if dataSource is equal to SEC_FILING, then usesMostAuthoritativeSource is true"}
```

**Directly applicable to the debit/credit rules spec:** the existing spec's invariants (total debits = total credits; predicted account must be in the fixed COA; amount must be positive) could be written in exactly this style — a JSON rule set with an `id` and a plain-language `alternateExpression` — even without the SMT-lib formal layer. This gives you a versioned, readable rule list rather than logic buried in code, and it's a natural fit for the `vault-ledger-entry-rules` skill from Report 3.

### From VERAFI: their actual agent system prompt structure (adaptable template)

Their baseline (tool-using, pre-validation) agent prompt:
```
You are a financial analyst. Answer this question using ONLY the provided documents.
Instructions:
- Use only the information in the provided documents
- Use calculator for basic math operations
- Use python_repl for complex calculations or data analysis
- Show your calculations clearly
- Cite document sources in your answer
- If information is missing, state that clearly
```

Their full neurosymbolic (rule-embedded) version adds a rules block before the question and an instruction to check work against it — but explicitly tells the model **not** to expose the validation mechanics in its output ("DO NOT mention rule IDs or validation details in your response... Your response should read like a professional financial report, not a technical validation log"). **This distinction is worth carrying over:** if an LLM-based step is ever added to Vault Ledger's pipeline (e.g. an explanation-generation step), keep the validation/rule-checking internal and separate from the user-facing output — don't surface rule IDs or technical validation chatter to the accountant.

---

## 3. For OCR / extraction and product framing (Step 1/2, and go-to-market)

### From the SME paper: OCR technique accuracy benchmarks (Table 3 in the original)

A literature survey of prior invoice-recognition results — useful as a rough accuracy bar to sanity-check extraction against, not something to reimplement from scratch:

| Method | Result | Note |
|---|---|---|
| Linear whole block moving + slant detection (Chinese/Arabic invoice OCR) | 97.2% (Chinese), 95.2% (Arabic) accuracy | Character segmentation is the hard part |
| k-NN classifier on graphical layout features (invoice type classification) | 99% (closed-world), 79% (open-world) | Big gap between seen/unseen formats — relevant caution for the "3 target formats" scoping decision |
| ANN-based character recognition | 84.8% recognition rate | Older technique, weaker baseline |
| Logistic regression on document-layout word features (first-page invoice recognition) | 95.02% accuracy | NLP/layout-feature approach, closer to what field-parsing heuristics might look like |
| CTPN (Connectionist Text Proposal Network) for receipt text detection | 71.9% F1 | Harder task (handwriting-adjacent), lower ceiling |
| Template matching OCR for invoice info identification | 95% precision, 14ms average runtime | Fast and accurate when templates are known in advance |
| CNN (AlexNet) + KNN for invoice type classification (handwritten/printed/receipt) | 97.92% accuracy (KNN) | Directly relevant — this is the 3-way format classification the MVP needs |

**Practical takeaway:** template-matching and layout-feature approaches (not deep OCR models) get you into the 95%+ range on structured documents cheaply — consistent with Report 1's guidance to treat extraction as an engineering problem, not a research one, for the 3 target formats.

### From the SME paper: the ML-type taxonomy for bookkeeping automation

The paper categorizes automated-bookkeeping ML use cases into three types (their Table 4) — useful as a checklist of what's been tried and validated in this exact domain:

| ML type | Subcategory | Use case |
|---|---|---|
| Supervised learning | Classification | Extract info via template matching |
| Unsupervised learning | Clustering | Separate invoices by category (e.g. handwritten vs. machine-printed) |
| Reinforced learning | Mapping | Journal/inventory management |

Vault Ledger's classifier (Step 3) is squarely in the first row — validated territory, not a novel application.

### From the SME paper: real-world case study benefits (usable for the pitch, not the build)

Three real automated-bookkeeping deployments, with concrete outcomes:
- **Case Study A** (Finnish events company): moved from manual invoice submission to automated flow via Procountor/Scoro — eliminated manual entry, real-time invoice sync.
- **Case Study B** (US beverage distributor, ~2,000 invoices/month): automated approval routing via Beanworks — enabled remote/mobile approval, notably useful during COVID-19 disruption.
- **Case Study C** (UK accountancy firm): adopted AutoEntry for data capture across purchase/sales invoices and bank statements — **grew bookkeeping-client turnover by over 50%** by automating data entry, now processing 300+ documents/month per client.

**Case Study C's 50%+ turnover growth is the strongest single borrowed data point for an investor narrative** — it's a real, cited, third-party-verified outcome from the same category of product.

### From the SME paper: the challenge ranking (informs onboarding/positioning)

Literature-reviewed challenge frequency for SME bookkeeping automation adoption, ranked: **knowledge constraints** (most cited) → **cost** → **record errors** → **poor management**. This suggests onboarding friction and perceived complexity are bigger adoption barriers than price for the target segment — worth factoring into how the correction UI and onboarding flow are framed, not just the technical build.

---

## 4. For model auditing / bias-checking (Step 3, post-training — not required for MVP, but cheap to keep in mind)

### From the interpretability paper: the reusable pattern, stripped of its image-specific mechanics

The paper's actual technique (generating synthetic "prototype" images that maximally activate a class) doesn't transfer to a text classifier. But its **workflow** — independent of modality — is directly restatable as a lightweight auditing habit:

> **Generate → Extract insight → Targeted retrain.** Rather than only checking aggregate accuracy on a test set, look at *what the model considers most representative of a category* and ask whether that reveals an unwanted pattern — then fix the training data specifically for that pattern, not just add more data broadly.

Their own case study (Resnet-18's "academic gown" prototype skewing toward lighter-skinned faces, traced back to an imbalanced training set) is a concrete demonstration that a model can pass ordinary test-set accuracy checks while carrying a hidden pattern that only shows up when you inspect what it's actually keying on.

**Concrete, cheap analogue for Vault Ledger's classifier**, once real training data exists: periodically pull the highest-TF-IDF-weight terms per predicted account (the classifier already effectively computes this as model coefficients/feature weights) and sanity-check them by eye — e.g., is "Utilities Expense" keying on genuinely utility-related terms, or has it picked up a spurious pattern (like always predicting the same account for a specific vendor regardless of description)? This costs almost nothing to do periodically and catches the kind of silent bias the paper demonstrates test-set accuracy alone won't surface.

**Not a build requirement** — flagged here because it's nearly free to do once the classifier exists, and it directly targets Report 1's flagged risk that extraction/classification quality is the single point of failure for the whole pipeline.

---

## Quick-reference: which report/step each paper feeds

| Paper | Primary relevance | Pipeline step |
|---|---|---|
| DragoNet | Two-field input design, taxonomy structure, hierarchy-masking pattern | Step 3 (classifier), future COA expansion |
| VERAFI | Tool-based (not free-text) computation, rule-as-data format, prompt design | Step 4 (rules layer), any future LLM-based step |
| SME bookkeeping paper | OCR/extraction accuracy benchmarks, case-study pitch data, adoption-barrier ranking | Step 1/2 (extraction), go-to-market framing |
| Interpretability paper | Lightweight bias-auditing habit for the trained classifier | Post-Step-3, optional/cheap ongoing practice |
