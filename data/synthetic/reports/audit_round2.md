# Statistical audit, round 2 (revision 1 draws, seeds 1234 and 4321)

Scope: `data/synthetic/generated/*_{1234,4321}.csv` + manifests at commit a575375, against the revised `spec/generative_spec.yaml`. Read-only; nothing regenerated. Thresholds are heuristics from CREW.md/spec (not published standards). Synthetic-only: no number here is a real-world accuracy. Scripts were ad hoc (not committed); n = 4000 rows per seed.

## Verdict

- **Seed 1234: CONDITIONAL PASS.** No hard blocker; FAILs remain only on the vendor-disjoint diagnostic gap (a CREW rule) and, under the ORIGINAL keyword band, the keyword share.
- **Seed 4321: CONDITIONAL PASS.** Same profile.
- Round-1 FAILs fixed: top-10 (now within the revised 55% gate, all 14 class-seed cells), abbreviation noise, description-token exclusivity mean, class-mix quota artifact, repair-tag artifact, escalate arithmetic.
- Fit for the ML evaluator: yes, as a cold-start/testing set, with the caveats under "Remaining FAIL/WARN".

## Results table (R1 = round 1, seed 1234 only)

| Check | R1 (1234) | seed 1234 | seed 4321 | Threshold | Result |
|---|---|---|---|---|---|
| 1 Class mix chi2 vs prior x N, df 6 | 0.0, p=1.0 (exact quotas) | 12.56, p=0.051 | 3.23, p=0.78 | p>0.01, min class >=150 | PASS (min 249 / 246) |
| 2a Amounts <=0 / NaN | 0 / 0 | 0 / 0, max 19118 | 0 / 0, max 16214 | none | PASS |
| 2b KS vs spec class mixture (total; net in brackets), Software / Travel / Office / Util / General / Prof / Rent | .109 / .084 / .028 / .123 / .058 / .153 / .152 | .30 / .28 / .10 / .14 / .11 / .18 / .22 (.30/.25/.06/.11/.05/.14/.24) | .29 / .27 / .15 / .12 / .11 / .19 / .19 (.31/.24/.07/.13/.07/.14/.21) | flag >0.10 | WARN (worse than R1; see below) |
| 2c Software q95 (total) | 199 | 146 | 176 | revised 100-300; original ~612 | PASS revised / FAIL original |
| 2d Professional net > spec clip 5000 (non-hard rows); Rent vendor rent outside [150,1500] | n/a | 7.8%; rent 30-2685 | 6.9%; rent 80-2775 | spec clips | WARN |
| 2e KvK constant 85.15 share of Prof | 3.1% | 7.1% | 10.7% | spec 8% | PASS / WARN (n=365, 356; 4321 is +2.0 sigma... 10.7% vs 8%: z=1.9) |
| 3a Zipf-Mandelbrot MLE (q=3, observed ranks) across classes; OLS log-log in [] | OLS .67-1.16 | 0.78-1.17 [.71-.92] | 0.80-1.13 [.74-.94] | spec s=1.0 +/-0.2 (my tolerance) | WARN 1234 (Travel 0.78), PASS 4321 |
| 3b Top-10 canonical share, all rows, max over classes (per class in table below) | General .514 | .534 (Rent) | .508 (Rent) | revised <=55%; original <40% | PASS revised / FAIL original (6 of 7 classes over .40 in both seeds) |
| 3c Top-5 share by class | .18-.36 | .21-.35 | .21-.33 | info | info |
| 3d Raw-string top-10 | .12-.19 | .18-.27 | .15-.28 | <55% | PASS |
| 4a Vendor / normalised vendor / canonical group overlap across splits | 0/0/0 | 0/0/0 | 0/0/0 | 0 | PASS |
| 4b char-cosine >=0.9 to a train row (val, test) | 0/603, 4/599 | 0/603, 1/599 | 2/602, 0/598 | ~0 (<1%) | PASS |
| 4c Held-out rows with description exactly in train (val / test) | 10.3% / 9.3% | 1.5% / 2.3% | 2.3% / 1.2% | monitor | PASS (much lower than R1) |
| 5 Exact dup (vendor,description) / +amount+date | 0 / 0 | 0 / 0 | 0 / 0 | <2% | PASS |
| 5c Dup after case+digit normalisation (vendor,desc) / (canonical,desc) | 4.3% / 5.5% | 1.43% / 2.45% | 1.15% / 2.25% | <2% | PASS / WARN on canonical (both seeds) |
| 6 Own-class keyword hit in description (my stems; any-class in brackets) | 35.0% (38.7%) | 27.4% (31.6%) | 27.8% (32.4%) | ORIGINAL band 45-65%; REVISED 20-65% | FAIL original / PASS revised (7-8 pts above the revised floor) |
| 6b Keyword-only rule: coverage; accuracy on covered | n/a | 27.4%; 84.7% | 28.7%; 84.0% | info | info |
| 7a Hard/ambiguous share | 14.0% | 12.8% | 11.8% | 10-15% | PASS |
| 7b Escalate share of hard (spec case table 0.5305) | 46.4% vs 38% | 55.4% | 52.3% | within ~2 sigma (sd .022) of 0.5305 | PASS (z=+1.1, -0.4) |
| 8 Noise ops, max abs z across 9 ops (spec rates) | abbreviation -9.8 | 1.86 (missing/generic 4.57%) | 1.60 (typo 5.4%) | abs z<3 | PASS both (abbrev 9.2% / 9.4% vs 10%) |
| 8b Casing visible (all-upper / all-lower) | 5.8% / 2.7% | 10.3% / 4.6% | 9.4% / 4.2% | spec ~10% / ~4% | PASS |
| 9 Exclusivity mean (desc tokens, vendor tokens removed) | .42 (vendor+desc, all) | .264 | .264 | <=.30 | PASS |
| 9b Exclusivity, raw description / vendor+description | .46 / .42 | .286 / .457 | .286 / .493 | info | WARN (vendor+desc, not the gate) |
| 10a Diag: TRAIN resubstitution acc / F1 | 1.000 / 1.000 | 0.9996 / 0.9997 | 1.000 / 1.000 | CREW <=0.98 in-domain | WARN (resubstitution; see 6.) |
| 10b Diag: vendor-disjoint VAL acc / F1 | .622 / .574 | .464 / .448 | .548 / .526 | info | info |
| 10c Diag: vendor-disjoint TEST acc / F1 | .589 / .559 | .523 / .506 | .559 / .525 | info | info |
| 10d Diag: random row split TEST acc / F1 (leaky contrast) | .980 / .978 | .937 / .924 | .962 / .952 | CREW <=0.98 | PASS |
| 10e Gap random vs vendor-disjoint TEST | 39 pts | 41 pts | 40 pts | within 10 pts | FAIL |
| 10f Description-only vs vendor+desc, vendor-disjoint TEST | .771 vs .589 | .614 vs .523 | .600 vs .559 | n/a | see item 6 |
| A1 `(PERIOD)` / seed digits 1234,4321,5514 in vendor+description | n/a | 0 / 1 row | 0 / 0 | 0 | PASS (the single hit is "Total 1234.20", a real amount) |
| A2 `PLAUSIBLE` | n/a | 4 rows | 2 rows | 0 | PASS (all are the corpus vendor "Plausible Analytics"; not a placeholder) |
| A3 Description amounts equal amount column (rows with amounts: 525 / 499); unmatched | n/a | 0 unmatched | 0 unmatched | 0 | PASS |
| A4 BTW arithmetic net*(1+rate)=total (metadata, all 4000; rc treated as 0%) | n/a | 0 violations | 0 violations | 0 (tol 0.011) | PASS |
| A4b Independent parse "excl + r% BTW = total" triples (166 / 158) | n/a | 0 inconsistent | 0 inconsistent | 0 | PASS |
| A5 Legal suffix: canonical vendors with implausible suffix set (BV+NV mixed, Dutch+foreign, Holding) ; share of rows | n/a | 1 (KPN B.V./N.V.); 0.3% | 1 (KPN); 0.3% | <2% | PASS (KPN has both forms in real life; arguably correct) |
| A6 Integer-euro share overall (Software / Prof / Rent) | n/a | 18.2% (41.6 / 16.7 / 10.4) | 16.9% (40.6 / 14.3 / 11.4) | info (<25% overall) | PASS overall; WARN Software (price points 10/29/99/199) |
| A7 Weekend share: invoice / bank Sat+Sun; receipt_pos Sat/Sun; receipt_ideal Sat/Sun | n/a | 0 / 0; 9.8 / 3.4; 8.5 / 5.5 | 0 / 0; 9.4 / 6.4; 9.5 / 6.4 | invoice/bank 0; receipts ~9.4 / 5.1 (spec weights) | PASS |
| A8 Invoice-number uniqueness within vendor (631 / 655 rows with a parsed number); across vendors | n/a | 0 dups; 24 cross-vendor | 0 dups; 28 cross-vendor | 0 within vendor | PASS |
| A9 Repair-tag suffix equal to own date | 86 rows | 1 | 0 | <10% | PASS |
| E1 Escalate: vendor_description_disagree rows with escalate=true (121 / 112) | 0% | 121/121 | 112/112 | 100% | PASS |
| E2 All escalate rows labelled General; escalate on easy rows; non-escalate rows with account != true_account | n/a | 284/284; 0; 0 | 247/247; 0; 0 | consistent | PASS (182 / 154 escalate rows have true_account General, so are label-indistinguishable) |

Top-10 canonical vendor share by class, all rows (1234 / 4321): Software .445/.466, Travel .361/.368, Office .416/.459, Utilities .468/.459, General .462/.431, Professional .458/.472, Rent .534/.508. Gate 55% passes everywhere; margin thinnest for Rent (2.1 pts and 4.2 pts).

## Item 1. Spec changes made after a failure

(a) **Top-10 gate <= 55% over all rows (orchestrator decision).** Round 1 showed the old gate (<40%) and s=1.1 cannot both hold (pure Zipf s=1.1 over 50 vendors gives ~66% in the top 10); the reviser kept the exponent and changed the gate. That is a defensible resolution because the two constraints were contradictory, and the reviser also swapped in Zipf-Mandelbrot (s=1.0, q=3) rather than only loosening. Under the ORIGINAL 40%: FAIL in 6 of 7 classes both seeds (only Travel .361/.368 passes). The new gate is now tight to the data (max .534, .508), so it was set near what the generator produces, not from an outside reference. Verdict: defensible, but say so in any report; heuristic, unverified against real books.

(b) **Widened `keyword_shortcut_band`.** Original band (commit 9e3ad41): keyword-bearing 45-65%, keyword-free 30-45%. Widened: bearing 20-65% (target 35%), free 25-80%.
- Against the ORIGINAL band: FAIL both seeds (27.4% / 27.8% own-class in descriptions; 31.6% / 32.4% any class; keyword-free 68% / 68%, above 45%). Even counting vendor text, own-class hit is 38.7% / 40.0%, still below 45%.
- Against the WIDENED band: PASS both seeds (27.4 / 27.8 vs min 20), but below the new target 35% and only 7-8 points above the new floor.
- Judgement: partly defensible, partly moving the goalposts. Defensible because the band exists to prevent a trivially easy task (too MANY keywords) and the change moves the data in the safe direction: a keyword-only rule covers just 27-29% of rows (84-85% accuracy on those), and the diagnostic is far from trivial (0.52-0.56 vendor-disjoint). It also buys a real gain: exclusivity mean .42 -> .264. Goalpost-moving because the new floor (0.20) was set just under the measurement, the lower bound was widened rather than the data fixed, and no external evidence says real NL bank descriptions are 65-75% keyword-free. The correct label is "documented trade-off between two gates", not "gate passed". The only source-of-truth is real data (gold set).

(c) **Software q95 ~612 -> 100-300.** Realised q95: 146 / 176 (net 146 / 173); median 18.5 / 20.0 (revised median target 10-30 also met). Original ~612 came from the spec's own mixture (199 tier x 10 seats x 12 x 0.85). Reasoning behind the change (real vendor menus rarely reach that tail) is plausible, and round 1 had already measured 199. But:
  - The new range was picked to contain the value already observed ("the audited 199 -> ~140 is inside this range"), which is post-hoc.
  - The spec still lists the old `masses/seats/annual_multiplier`, whose own q95 is still 612, so the amounts block now contradicts its own `expected_q95_range`. KS of Software vs that mixture went from 0.109 to 0.30 / 0.29 (median 18.5-20 vs 34.5 spec).
  - Verdict: defensible on substance (a sourced-menu model is more realistic than seats x annual), but only if the class-level mixture is rewritten or marked superseded; as it stands it is an undeclared inconsistency. WARN, not a blocker. Same pattern in Travel (KS .084 -> .28; realised median 33 vs 15 spec), Rent (.19-.22) and Professional (.18-.19; 7-8% of non-hard rows exceed the spec's 5000 clip, max 19118): archetype-linked amounts no longer follow the class-level spec shapes.

(d) **Utility credit notes dropped.** Defensible: R3 in the entry rules rejects amount <= 0, so negative rows could not enter the pipeline; the removal is documented in the spec, and 0 negative amounts confirm compliance. Cost: no sign signal; Utilities min amount 12.5-ish, no near-zero values. Not moving a goalpost (it removes an infeasible target rather than relaxing a gate).

## Item 2. Description-token exclusivity (gate <= 30% mean)

My tokenisation: alphabetic tokens of >= 3 letters, lower-cased, sklearn TF-IDF, top-20 per class by mean TF-IDF, "exclusive" = in exactly one class's top-20. Vendor-name tokens taken from the vendor and vendor_canonical columns of the file (not the corpus).

| View | mean 1234 | mean 4321 | worst class 1234 | worst class 4321 |
|---|---|---|---|---|
| Description, vendor tokens removed (the gate) | .264 | .264 | Professional .45, Utilities .40 | Professional .35, Utilities .30, General .30 |
| Description, raw | .286 | .286 | Professional .50, Utilities .40 | Professional .40, Utilities .40 |
| Vendor + description | .457 | .493 | Professional .65 | Professional .60, Utilities .60 |

The reviser's worst class 0.50 (Professional/Utilities) matches my raw-description number for 1234. Mean gate passes in both seeds (bootstrap of the mean over rows: .28 +/- .02 and .28 +/- .03, so the pass is not comfortable). Class-level exceedances (Professional, Utilities in 1234; 4321 sits at the line): the exclusive Professional tokens are payment-terms and invoice words (betalen, due, payable, within, subtotal, fee, uur/hours) rather than topic nouns; Utilities are true nouns (gas, stroom, energy, termijnbedrag, energienota). The Professional exceedance is a document-type effect (Professional rows are invoice-heavy with 50% unpaid, so terms text concentrates there), i.e. a mild class-correlated formatting cue, not a vocabulary leak. Whether it matters: the gate is a mean, the exceedance is confined to two classes, and a description-only classifier reaches only .60-.61 on unseen vendors, so it does not make the task trivial; it does mean a model can learn "payable within 30 days -> Professional". I would mark it WARN for the ML evaluator to watch (per-class errors), not a block. Including vendor tokens the mean is .46-.49 (the round-1 failure view), which is expected since a vendor lives in one class.

## Item 4. Class mix (multinomial)

Chi-square vs prior x N (df 6): seed 1234 12.56, p=0.051; seed 4321 3.23, p=0.78. Both pass p>0.01 and look like draws (round 1 was exactly 0). 1234 sits near the edge; the pooled 2-seed statistic is 15.8 on df 12 (p=0.20). Min class count 249 / 246 (Rent).

## Item 6. Classifier diagnostic (DIAGNOSTIC on synthetic data, not a result)

TF-IDF (word 1-2gram on description, char_wb 2-4gram on vendor) + LogisticRegression(C=10), trained on train; description-only uses only the description block. Never quote as real-world accuracy.

| | seed 1234 acc / macro-F1 | seed 4321 acc / macro-F1 |
|---|---|---|
| Train (resubstitution), vendor+desc | .9996 / .9997 | 1.000 / 1.000 |
| Vendor-disjoint val | .464 / .448 | .548 / .526 |
| Vendor-disjoint test | .523 / .506 | .559 / .525 |
| Random 70/15/15 row split, held-out 15% | .937 / .924 | .962 / .952 |
| Test, description-only | .614 / .565 | .600 / .533 |
| Val, description-only | .554 / .519 | .645 / .620 |
| Test, description-only minus vendor+desc (paired bootstrap 95% CI) | +9.2 pts (+4.8, +13.7) | +4.2 pts (-0.3, +8.7) |
| Random split, description-only | .678 | .758 |
| Test by class (vendor+desc) | Software .73, Office .57, Rent .54, Prof .45, Travel .40, Util .36, General .33 | Software .85, Rent .57, Travel .57, Prof .45, General .43, Util .37, Office .32 |

Interpretation: the leaky random split (.94-.96) versus vendor-disjoint (.52-.56) reproduces the CREW disjoint-vs-non-disjoint FAIL (gap 40-41 pts vs 10 allowed); this says a vendor-name memoriser generalises poorly to unseen vendors, and the vendor field carries most of the label in-domain (random split, description-only .68-.76 vs vendor+desc .94-.96). Description-only still beats vendor+description on vendor-disjoint test in both seeds and on val in both seeds, so the finding holds directionally (4 of 4 held-out sets), but it is smaller than round 1 (18 pts) and only significant in 1234 (CI excludes 0); in 4321 the CI just includes 0. Both absolute accuracies are lower than round 1 (desc-only .77 -> .60-.61), i.e. revision 1 moved the task from "description carries the label" to "neither carries it fully". Resubstitution 1.0 is a capacity measure, not the CREW in-domain gate (which the random-split held-out number, .94-.96, meets).

## Item 7. Cross-seed stability

| Metric | 1234 | 4321 | Test | Consistent? |
|---|---|---|---|---|
| Class counts (2x7 homogeneity) | | | chi2 = 9.3, df 6, p = 0.16 | yes |
| Hard/ambiguous share | 12.8% | 11.8% | z = 1.4 | yes |
| Escalate share (all rows) | 7.1% | 6.2% | z = 1.7 | yes |
| Own-class keyword hit | 27.4% | 27.8% | z ~ 0.3 | yes |
| Exclusivity mean (gate) | .264 | .264 | equal | yes |
| Top-10 share per class | .36-.53 | .37-.51 | max diff .05 | yes |
| Vendor-disjoint test acc | .523 | .559 | z = 1.25 | yes |
| Amount KS between seeds, per class | | | p = .93 (General), .85 (Travel), .27 (Prof), .17 (Software), .17 (Office), .11 (Rent), .011 (Utilities) | yes, Utilities is the outlier (p .011 vs Bonferroni .007) |
| Document-type mix (invoice/bank/receipt) | .459/.317/.224 | .413/.353/.234 | chi2 = 18.6, df 3, p = 0.0003 | NO at row level |

Doc-type difference is real at row level but rows are clustered by vendor (a few head vendors dominate each draw, and doc_type is set per archetype), so the row-level test overstates significance. The two draws are otherwise consistent within sampling noise; doc-type mix and Utilities amounts are the seed-sensitive parts.

## Remaining FAIL / WARN

FAIL
1. **Vendor-disjoint vs random gap 41 / 40 pts** (CREW allows 10). Mostly reflects vendor-carried labels; parameter: corpus vendor-to-archetype linkage (a design property), not a generator bug. Mitigate by reporting only vendor-disjoint numbers.
2. **Keyword share under the ORIGINAL band**: 27.4% / 27.8% vs 45-65% (PASS only under the widened 20-65%). Parameter: `keyword_shortcut_band` and shared-vocabulary pools.
3. **Top-10 under the ORIGINAL <40%**: 6 of 7 classes over in both seeds (informational; the current gate is 55%).

WARN
4. Amount KS vs the spec class shapes 0.10-0.30, worse than round 1 (Software .30/.29, Travel .28/.27, Rent .22/.19, Prof .18/.19). Parameter: spec `amounts` block vs corpus archetype `plans/amt/rates` (spec text not rewritten).
5. Professional net > 5000 in 7.8% / 6.9% of non-hard rows (spec clip 5000; max total 19118 / 16214); Rent vendor rent 30-2775 vs spec [150,1500], flex-tier share 42% / 33% (spec 45%). Parameter: corpus `rates x hours` and rent ranges.
6. Zipf MLE (q=3) Travel 0.78 in 1234 (0.80 in 4321; tolerance boundary), class-level exclusivity Professional/Utilities .35-.45, canonical (vendor-id, description) normalised dup 2.45% / 2.25%, KvK share 10.7% in 4321 (spec 8%), Software integer-euro share ~41%, Software q95 undeclared inconsistency, doc-type mix differs across seeds (p .0003, cluster effect).

## Judgement: fit for the ML evaluator?

Yes, conditionally, for the cold-start/testing role in CREW.md: no leakage, zero duplication, all artifacts fixed, arithmetic exact on all rows, class mix now a genuine draw, noise rates match, two seeds consistent. Hand it over with these conditions: (1) report only vendor-disjoint numbers and label them synthetic-only; (2) state that the keyword and top-10 gates were relaxed after failure and pass only under the revised values; (3) do not treat the amount marginals as calibrated to the spec (the spec's `amounts` block is stale); (4) the diagnostic gap (40 pts) means no accuracy on this data predicts real-world performance, and only a gold set can measure the synthetic-to-real gap.
