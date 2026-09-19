# Synthetic data crew

Purpose: give the classifier enough realistic, statistically defensible
training data to start with, given that no real company data exists yet.

## Honest limits (read first)
- Synthetic data is a **cold-start and testing tool, not a substitute for real
  data.** Accuracy measured only on synthetic data is circular and must never be
  quoted as real-world accuracy.
- The synthetic distribution is only as good as its stated assumptions. Every
  assumption is labelled `assumption` or `sourced` in the spec.
- Nothing here ever includes real personal data. Public business names are used
  as vendor archetypes only.
- Real data (a QuickBooks/Xero export, or hand-verified rows in `data/gold/`)
  always outranks synthetic and phases it out via the `source` column.

## Pipeline

```
1 spec-architect -> 2 corpus-builder -> 3 generator -> 4 auditor (GATE)
                                                     -> 5 realism-critic (GATE)
                                                     -> 6 ml-evaluator
```

A failing gate sends its named fix back to the earlier stage; the generator
reruns with the same seed. Only data that passes stages 4 and 5 may be merged
into the training set (`source=synthetic`).

| Stage | Agent | Output | Gate to pass |
|---|---|---|---|
| 1 | synth-spec-architect | `spec/generative_spec.yaml` | every parameter tagged sourced/assumption |
| 2 | synth-corpus-builder | `spec/corpus/*.json` | >=40 vendors, archetype-linked description pools (>=8 templates/family), vendor legal forms valid |
| 3 | synth-generator | `generated/transactions_<seed>.csv` | deterministic; vendor-disjoint splits; tests green |
| 4 | synth-statistical-auditor | PASS/FAIL table | chi-square, KS, Zipf, leakage, dup < 2% |
| 5 | synth-realism-critic | realism score + artifacts | score >= 0.85, no artifact on > 10% rows |
| 6 | synth-ml-evaluator | held-out + gold-gap report | adopt / caveats / reject |

## Statistical principles
- Class prior, amounts, vendor frequency and recurrence follow explicit
  distributions (lognormal amounts, Zipf vendors), not uniform draws.
- 10-15% of rows are deliberately hard/ambiguous, tagged with the reason.
- Splits are **vendor-disjoint**; random row splits leak and are forbidden.
- Ground-truth metadata (`archetype`, `difficulty`, `noise_applied`) lives in a
  separate file and is never a model feature.
- Multiple seeds are run to show results are stable, not one lucky draw.

## Gold set
`data/gold/` holds a small (target 100-200) set of real or hand-verified rows
never used for training. It is the only thing that measures the
synthetic-to-real gap. Until it exists, all reported numbers are labelled
"synthetic-only".

## Running the crew
Run stages in order via the Agent tool by name. After a generation run, always
run 4 and 5 before 6. The master (orchestrating) session decides whether to
merge, and reports gate results to the user.

## Research-derived design (see spec/research_nl_expenses.md and notes below)
Sourced: attribute-crossed prompting (AttrPrompt, arXiv 2306.15895) beats plain
class-conditional generation on diversity; few-shot seeding from real rows beat
zero-shot by ~9-11% (arXiv 2310.07849); weighting synthetic rows by quality helped
on financial text (arXiv 2410.21526). Everything below marked *heuristic* is our
own tunable threshold, not a published standard.

**Generation recipe.** Per account build a vendor-archetype taxonomy, cross it with
noise attributes (bank format, prefix/suffix such as `BEA NR:` / `SEPA Incasso`,
casing, truncation, store/terminal codes, language, amount band, date). Vendor names
come from the corpus; description strings are rendered from *randomized* bank/invoice
format templates. No class may own an exclusive vocabulary. Deduplicate on
normalized strings. Include deliberately ambiguous vendors (Bol.com, Amazon, Action,
Albert Heijn/HEMA, Google Ads) that carry an escalate label, not a guess.

**Acceptance gates (heuristic, tunable; 2k-10k rows).**
- >= 95% unique after normalization; >= 15 (prefer 30) vendor strings per class.
- No description pattern > 3% of a class; top-10 vendors <= 55% of any class, measured over ALL rows of the class (heuristic; see revision 1 below).
- Of top-20 discriminative tokens per class, <= 30% exclusive to that class.
- Real-vs-synthetic discriminator (TF-IDF logistic regression) AUC <= 0.75, target ~0.6;
  > 0.9 means template artifacts. Needs real rows (gold set).
- Synthetic-in-domain accuracy <= 98% (higher = artifacts); never report it as a result.
- Vendor-disjoint TSTR within 10 points of non-disjoint TSTR.
- TSTR macro-F1 on the gold set >= 70% of TRTR macro-F1, no class F1 < 0.5.
- ECE < 0.10 on gold; confidence >= 20% lower on ambiguous than clear rows.

**Mixing with real data (heuristic).** No fine-tuning for TF-IDF+LR, so use
`sample_weight`: real rows 5-20x a synthetic row. 0-50 real rows: synthetic only,
results marked provisional. 50-500: mixed, real upweighted. When real-only matches
real+synthetic on gold (paired bootstrap), taper synthetic to ~0, keeping it only for
rare classes. The number of real rows needed is found from the learning curve, not
assumed.

**Format references.** DoDataThings/us-bank-transaction-categories-v2 (MIT, synthetic,
US bank formats, different taxonomy) is a format-realism reference only, not a gold
set. No open real labeled transaction dataset exists; the gold set must be our own
hand-labeled rows (target 200-500, split by vendor). Verify licenses before using any
external dataset.

**Unverified.** NL category shares, most NL amounts and vendor wording, and paid/unpaid
shares are assumptions until checked against real documents.

## Generator (stage 3)

Run: `PYTHONPATH=src .venv/bin/python data/synthetic/generate_transactions.py [--seed 1234] [--rows 4000] [--out-dir data/synthetic/generated]`

Same seed + spec + corpus gives byte-identical output (per-stage `random.Random` streams; no set/hash ordering).

Outputs in `data/synthetic/generated/` (never `labeled_transactions.csv`):
- `transactions_<seed>.csv`: vendor, description, date, amount, paid, account.
- `metadata_<seed>.csv`: row-aligned ground truth (id, source=synthetic, archetype, difficulty, escalate, noise_applied, language, vendor_unverified, vendor_canonical, true_account, hard_case, split). Never a feature.
- `train_/val_/test_<seed>.csv`: `vendor,description,account` only.
- `manifest_<seed>.json`: seed, spec/corpus/generator SHA-256, realised stats.

Conventions and deviations (honest limits):
- **Escalate rows** carry `account = General/Other Expense` with `escalate=true` in metadata; `true_account` holds the account the row would otherwise have.
- **Vendor-disjoint splits** assign whole brand groups (aliases, alias-string collisions, and linked brands such as Google/Google Workspace) to one split, greedily stratified per account. Row fractions are reported in the manifest, not forced.
- **Top-10 gate vs Zipf (SPEC DECISION, revision 1)**: pure Zipf s=1.1 over ~50 vendors puts ~65% in the top 10, contradicting the old `< 40%` gate. Decision: keep a realistic heavy head. Model = Zipf-Mandelbrot p(r) ~ (r+q)^-s with **s = 1.0, q = 3.0**; gate = **top-10 vendor share <= 55% of any class, measured over ALL rows of the class** (heuristic; the manifest's `top10_vendor_share_clear_rows_only_NOT_THE_GATE` is informational only). The manifest reports the realised exponent by MLE (not OLS): ~0.8-1.4 for the generating family (q fixed; noisy for small pools) and 0.55-0.90 for pure Zipf (lower by construction because of the offset). Vendors are no longer forced to appear exactly once; singletons are a by-product of the multinomial draw.
- **Class counts are sampled** (multinomial from the prior, residual after the hard rows), not exact quotas; `class_mix_chi2` in the manifest (df 6) should look like a draw.
- **Vendor-disjoint splits** assign whole brand groups to one split, greedily stratified per account, with a repair loop that guarantees every account has a vendor group in every split. Row fractions are reported, not forced.
- **Credit notes**: not generated. The entry rules reject amount <= 0 (R3), so negative utility credit notes cannot enter the pipeline; the ~5% negative share was removed from the spec.

## Revision 1 (after both gates failed on draw 1234)

Root cause: vendors and descriptions were independent lists per account, so "Dropbox billing for Slack Pro" happened by construction. Now:
- Corpus per account = `archetypes` (family, price model, VAT, doc-type mix) + `pools` (description templates per family) + `vendors` (each tied to ONE archetype). A description is drawn only from the vendor's family pool and its amount from the same archetype (plan menu x seats, hourly rate x hours, usage scale, template amount range, fixed rent per vendor). Only hard rows (`generic_description`, `vendor_description_disagree`, brand cases) may break the link. Metadata carries `desc_family`, `doc_type`, `vat_rate`, `net_amount`.
- Amount column = document total; net + BTW = total exactly; foreign SaaS = reverse charge; KvK and international flights = 0%. Any amount quoted in a description is derived from the row.
- ONE payment field by document type: invoice -> terms only, bank line -> SEPA text, receipt -> card terminal/iDEAL. Card-terminal text only on archetypes that have receipts.
- Dates: invoices and bank lines on business days (rent rolls to the first business day); receipts may fall on weekends (Sat 0.55 / Sun 0.30 weight); Professional invoices cluster in the last 3 business days; accountant quarterly series sit on quarter-end.
- Legal suffixes: only the vendor's own Dutch form (B.V./N.V.) is appended to its canonical name; foreign forms appear only via curated aliases; no "Holding" except on landlords. Duplicates are avoided with distinct invoice numbers/dates, not a repair tag.
- Noise: each op's probability is scaled by its eligible rows so the realised rate matches the spec. Typos are keyboard-adjacent / dropped / doubled / swapped letters; OCR uses real confusions (0/O, 1/l, 5/S, rn/m).
- Ambiguity labels: `vendor_description_disagree` rows are always `escalate=true` (label General/Other, `true_account` = the account the description implies); `generic_description` rows escalate only for ambiguous brand vendors, otherwise keep the vendor's account with difficulty `hard`. The headline escalate share is computed from the case table (0.5305 of hard rows) and a test asserts agreement.
- Vocabulary exclusivity: `measure_vocab.py` reports description tokens with vendor-name tokens removed (the gate), raw description, vendor and vendor+description tokens. Every pool carries shared business vocabulary (factuur/invoice/betaling/order/periode); the price is a higher keyword-free template share (spec `keyword_shortcut_band`).
- Tools: `check_corpus.py` (corpus structure and hygiene), `measure_vocab.py`, tests in `tests/test_synth_generator.py`.
