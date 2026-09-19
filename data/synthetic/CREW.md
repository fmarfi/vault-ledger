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
| 2 | synth-corpus-builder | `spec/corpus/*.json` | >=40 vendors, >=80 descriptions/account; ~1/3 keyword-free |
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
- No description pattern > 3% of a class; top-10 vendors < 40% of any class.
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
