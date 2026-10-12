# Statistical audit, round 3 (revision 2 draws, seeds 1234 and 4321)

Scope: `data/synthetic/generated/*_{1234,4321}.csv` + manifests at commit 5f755b4, against the current `spec/generative_spec.yaml` (now with `price_dynamics`, `card_charged_archetypes` and the document-type rules for reference text) and the gates in `CREW.md`. Read-only; nothing regenerated, nothing edited. n = 4000 rows per seed. Thresholds are the existing heuristics from CREW.md / the spec (not published standards); none was relaxed. Synthetic-only: no number here is a real-world accuracy.

Provenance checked: the manifests' `spec_sha256`, `generator_sha256` and `corpus_sha256` equal the hashes of the files at 5f755b4 (recomputed). Determinism (same seed gives byte-identical output) was NOT re-verified, because regenerating was out of scope for this round.

How the round-2 column was produced: the round-2 scripts were ad hoc and not kept, so I re-ran this round's script on the round-2 files (`git show b6f765f:...`). Where the recomputed value equals the value printed in `audit_round2.md` only one number is shown. Where it differs because the method could not be reproduced exactly, the round-2 report value is shown first and the recomputed value follows as `[rc ...]`. Round-on-round movement should be read from the `[rc]` value, since it uses the same method as round 3. Method definitions are at the end so round 4 can reproduce them.

## Verdict

- **Seed 1234: CONDITIONAL PASS, weaker than round 2.** One new FAIL on a current threshold: the description-token exclusivity mean is 0.314 against the gate of 0.30 under the round-2 audit method (it is 0.293, a pass, under the stage-3 tool `measure_vocab.py`; that is a second measurement of the same threshold, not a revised threshold, and I do not count it as clearing the gate). The vendor-disjoint diagnostic gap still fails (36.7 pts against 10).
- **Seed 4321: CONDITIONAL PASS.** Exclusivity mean 0.271 passes under both methods, but its bootstrap mean over rows is 0.314 +/- 0.019, so the pass is not robust. Diagnostic gap 34.3 pts still fails.
- No hard blocker in either seed: class mix, leakage, exact duplication, noise rates, difficulty mix, arithmetic and labels all pass, and every revision-2 rule that can be checked from the rows holds on easy rows with zero violations.
- Fit for the ML evaluator: yes, conditionally, as a cold-start / testing set. Conditions are under "Judgement".

Revision 2 in one line: it fixed what it set out to fix (frozen prices 22-24% of rows down to 7-8%, order numbers 12% down to 3-4% with 0 misplaced, invoice wording on receipts 115 / 101 rows down to 0), and paid for it with class vocabulary (exclusivity mean up 0.264 to 0.314 / 0.271, keyword-bearing share up about 8 points) and with a wider distance between the spec's `amounts` block and the data.

## Results table (R2 = round 2, revision 1 draws; R3 = this round)

| Check | R2 (1234 / 4321) | R3 seed 1234 | R3 seed 4321 | Threshold | Result (1234 / 4321) |
|---|---|---|---|---|---|
| 1 Class mix chi2 vs prior x N, df 6 | 12.56, p=0.051 / 3.23, p=0.78 | 12.56, p=0.051 | 3.23, p=0.78 | p>0.01, min class >=150 | PASS / PASS (min 249 / 246; counts identical to R2, same RNG stream) |
| 2a Amounts <=0 / NaN; max | 0 / 0, max 19118 / 16214 | 0 / 0, max 15294 | 0 / 0, max 16214 | none <=0 or NaN | PASS / PASS |
| 2b KS vs spec class mixture, total (net in brackets): Software / Travel / Office / Util / General / Prof / Rent | .29 / .28 / .11 / .13 / .11 / .18 / .22 (.29/.25/.06/.09/.05/.14/.24) and .28 / .28 / .15 / .11 / .12 / .20 / .19 (.30/.25/.07/.12/.07/.14/.21) | .23 / .27 / .09 / .15 / .11 / .20 / .17 (.25/.23/.04/.10/.06/.16/.18) | .29 / .26 / .14 / .08 / .08 / .16 / .21 (.31/.22/.07/.15/.06/.12/.25) | flag >0.10 | WARN / WARN (mixed movement, see Item 2) |
| 2c Software q95 total; median | 146 / 176; 18.5 / 20.0 | 148.7; 20.6 | 137.9; 19.5 | revised q95 100-300, median 10-30; original q95 ~612 (spec mixture gives 597) | PASS revised / FAIL original, both seeds |
| 2d Professional net > spec clip 5000, easy rows; max net | 7.8% / 6.9%; 15800 / 13400 | 7.8% (28 of 361); 12640 | 5.2% (18 of 349); 13400 | spec clip 5000 | WARN / WARN (unchanged / slightly better) |
| 2d Rent net outside [150,1500], easy rows; range | 10.1% / 15.1%; 30-2685 / 80-2775 | 14.2% (8 below, 27 above of 247); 90-2685 | 18.0% (19 below, 24 above of 239); 40-2745 | spec tiers 150-400, 500-1500 | WARN / WARN (worse) |
| 2e KvK constant 85.15, share of Professional | 7.1% / 10.7% | 7.1% (z=-0.6) | 10.7% (z=+1.9) | spec 8% | PASS / PASS, 4321 borderline (unchanged) |
| 2f Software net below the smallest spec mass 6.90, easy rows (new) | [rc 5.5% / 5.7%] | 12.9% | 11.3% | spec masses | WARN / WARN (spec vs data, see Item 3) |
| 3a Zipf-Mandelbrot MLE (q=3, all rows) across classes; OLS log-log in [] | 0.78-1.17 [.71-.92] / 0.80-1.13 [.74-.94] | 0.78-1.17 [.71-.92] | 0.80-1.13 [.74-.94] | spec s=1.0 +/-0.2 (auditor tolerance) | WARN (Travel 0.78) / PASS (Travel 0.80, on the boundary); unchanged |
| 3b Top-10 canonical share, all rows, max over classes | .534 / .508 (Rent) | .534 (Rent) | .508 (Rent) | revised <=55%; original <40% | PASS revised / FAIL original (6 of 7 classes over .40), both seeds |
| 3c Top-5 share by class | .21-.35 / .21-.33 | .21-.35 | .21-.33 | info | info |
| 3d Raw-string top-10, max over classes | .27 / .28 | .27 | .28 | <55% | PASS / PASS |
| 3e Vendor strings per class, min (new) | [rc 94 / 101] | 99 | 102 | >=30 | PASS / PASS |
| 3f Largest single vendor share inside General/Other (new) | [rc .070 / .073] | .070 | .073 | <=0.12 | PASS / PASS |
| 4a Vendor / normalised vendor / canonical group overlap across splits; corpus alias strings spanning splits | 0/0/0 | 0/0/0; 0 | 0/0/0; 0 | 0 | PASS / PASS |
| 4a2 Split row fractions train / val / test; min class rows in test (new) | [rc .6995/.1507/.1497; 37] | .6995 / .1507 / .1497; 37 | .7000 / .1505 / .1495; 37 | +/-0.03 of 70/15/15; >=30 | PASS / PASS |
| 4b char-cosine >=0.9 to a train row (val, test) | 0/603, 1/599 and 2/602, 0/598 [rc 0, 2 and 0, 0] | 0/603, 2/599 | 0/602, 1/598 | ~0 (<1%) | PASS / PASS |
| 4c Held-out rows with description exactly in train (val / test) | 1.5% / 2.3% and 2.3% / 1.2% | 2.8% / 2.3% | 2.2% / 1.7% | monitor | PASS / PASS (flat) |
| 5 Exact dup (vendor,description) / +amount+date | 0 / 0 | 0 / 0 | 0 / 0 | <2% | PASS / PASS |
| 5c Dup after case+digit normalisation (vendor,desc) / (canonical,desc) | 1.43% / 2.45% and 1.15% / 2.25% [rc 1.32 / 2.28 and 1.02 / 2.00] | 1.12% / 2.10% | 1.02% / 2.10% | <2% (audit); CREW >=95% unique | PASS on vendor string; WARN on canonical, both seeds (flat) |
| 5d Most frequent digit-normalised description, share of its class, max (new) | [rc 1.4% / 1.6%] | 1.4% (General) | 1.3% (General) | <=3% | PASS / PASS |
| 6 Own-class keyword hit in description (any-class in brackets) | 27.4% (31.6%) / 27.8% (32.4%), ad hoc stems, not reproducible [rc with the checker lexicon: 34.6% (40.9%) / 35.9% (42.3%)] | 43.2% (50.6%) | 42.9% (49.7%) | ORIGINAL band 45-65%; REVISED 20-65% | FAIL original (below by 1.8 / 2.1 pts) / PASS revised, both seeds |
| 6b Keyword-only rule: coverage; accuracy on covered | 27.4%; 84.7% / 28.7%; 84.0% [rc 34.4%; 82.7% / 35.2%; 82.3%] | 43.5%; 83.9% | 41.7%; 84.1% | info | info (coverage up about 8 pts) |
| 7a Hard/ambiguous share | 12.8% / 11.8% | 12.8% | 11.8% | 10-15% | PASS / PASS |
| 7b Escalate share of hard (spec case table 0.5305) | 55.4% / 52.3% | 55.4% (z=+1.1) | 52.3% (z=-0.3) | within ~2 sigma | PASS / PASS |
| 7c Hard-case mix vs spec weights, chi2 df 7 (new) | [rc 4.07, p=.77 / 5.19, p=.64] | 4.07, p=.77 | 5.19, p=.64 | p>0.01 | PASS / PASS |
| 8 Noise ops, max abs z across 9 ops | 1.86 / 1.60 | 1.57 (truncated 7.3% vs 8%) | 1.95 (NL/EN mix 11.0% vs 12%) | abs z<3 | PASS / PASS |
| 8b Casing visible (all-upper / all-lower) | 10.3% / 4.6% and 9.4% / 4.2% | 11.0% / 4.3% | 9.9% / 3.9% | spec ~10% / ~4% | PASS / PASS |
| 9 Exclusivity mean (desc tokens, vendor tokens removed), round-2 audit method | .264 / .264 | **.314** | .271 | <=.30 | **FAIL** / PASS (4321 not robust: bootstrap .314 +/- .019) |
| 9a Same gate measured by the stage-3 tool `measure_vocab.py` | [rc .264 / .243] | .293 | .279 | <=.30 | PASS / PASS (second measurement, not a revised threshold) |
| 9b Exclusivity, raw description / vendor+description | .286 / .457 and .286 / .493 | .336 / .479 | .307 / .514 | info | WARN / WARN (worse) |
| 10a Diag: TRAIN resubstitution acc / F1 | 0.9996 / 0.9997 and 1.000 / 1.000 | 1.000 / 1.000 | 1.000 / 1.000 | CREW <=0.98 in-domain | WARN (resubstitution is capacity, not the in-domain gate) |
| 10b Diag: vendor-disjoint VAL acc / F1 | .464 / .448 and .548 / .526 | .557 / .528 | .586 / .565 | info | info |
| 10c Diag: vendor-disjoint TEST acc / F1 | .523 / .506 and .559 / .525 | .583 / .548 | .607 / .559 | info | info |
| 10d Diag: random row split held-out 15% acc / F1 (leaky contrast) | .937 / .924 and .962 / .952 [rc .958 / .949 and .950 / .940] | .950 / .939 | .950 / .944 | CREW <=0.98 | PASS / PASS |
| 10e Gap random vs vendor-disjoint TEST | 41 / 40 pts [rc 43.6 / 39.1] | 36.7 pts | 34.3 pts | within 10 pts | FAIL / FAIL (better by 7 / 5 pts) |
| 10f Description-only vs vendor+desc, vendor-disjoint TEST | .614 vs .523 / .600 vs .559 | .624 vs .583 | .684 vs .607 | n/a | see Item 6 |
| A1 `(PERIOD)` / seed digits 1234,4321,5514 in vendor+description | 0 / 1 row and 0 / 0 | 0 / 0 | 0 / 0 | 0 | PASS / PASS |
| A2 `PLAUSIBLE` | 4 / 2 rows | 4 rows | 2 rows | 0 placeholders | PASS (corpus vendor "Plausible Analytics") |
| A3 Description amounts equal amount column (rows with a money token); unmatched | 525 / 499; 0 | 530; 0 | 546; 0 | 0 | PASS / PASS |
| A4 BTW arithmetic net*(1+rate)=total, all 4000 rows | 0 violations | 0 | 0 | 0 (tol 0.011) | PASS / PASS |
| A4b Independent parse of "excl + r% BTW = total" triples | 166 / 158; 0 [rc 243 / 223; 0] | 226; 0 inconsistent | 240; 0 inconsistent | 0 | PASS / PASS |
| A5 Canonical vendors showing both B.V. and N.V.; share of rows | 1 (KPN); 0.3% [rc 0.6%] | 1 (KPN); 0.6% | 2 (KPN, Vattenfall); 1.1% | <2% | PASS / PASS (both come from corpus aliases of real group entities) |
| A6 Integer-euro share overall (Software / Prof / Rent) | 18.2% (41.6 / 16.7 / 10.4) and 16.9% (40.6 / 14.3 / 11.4) | 8.4% (14.3 / 15.9 / 5.2) | 7.3% (10.9 / 11.5 / 12.2) | info (<25% overall) | PASS / PASS; R2 Software WARN resolved |
| A7 Weekend share: invoice / bank; receipt_pos Sat/Sun; receipt_ideal Sat/Sun | 0 / 0; 9.8 / 3.4; 8.5 / 5.5 and 0 / 0; 9.4 / 6.4; 9.5 / 6.4 | 0 / 0; 9.9 / 3.9; 7.6 / 5.6 | 0 / 0; 8.3 / 3.8; 8.4 / 6.1 | invoice/bank 0; receipts ~9.4 / 5.1 | PASS / PASS |
| A8 Invoice numbers: rows with a parsed number; duplicates within vendor | 631 / 655; 0 [rc, wider regex: 1378 / 1417; 0 / 2] | 1286; 0 | 1290; 0 | 0 within vendor | PASS / PASS |
| A8b Same invoice number quoted twice inside one description (new) | [rc 123 / 121 rows] | 0 | 0 | 0 (revision 2 rule) | PASS / PASS (fixed) |
| A9 Repair artifacts: doubled date; time-of-day suffix | 1 / 0 [rc 0 / 0; 0 / 0] | 0; 1 row | 0; 2 rows | <10% | PASS / PASS (the time suffix is the documented last-resort disambiguator) |
| E1 vendor_description_disagree rows with escalate=true | 121/121 and 112/112 | 121/121 | 112/112 | 100% | PASS / PASS |
| E2 Escalate rows labelled General; escalate on easy rows; non-escalate rows with account != true_account | 284/284; 0; 0 and 247/247; 0; 0 | 284/284; 0; 0 | 247/247; 0; 0 | consistent | PASS / PASS (182 / 154 escalate rows have true_account General, as in R2) |
| **Revision-2 rules (new this round)** | | | | | |
| P1 Frozen-price rows: vendors with >=10 easy rows and <=3 distinct amounts (critic's count); modal amount >50% in [] | [rc 23.2% / 25.8%; 22.0% / 23.6%] | 5.5% [7.0%] | 4.3% [7.8%] | <10% (heuristic test gate) | PASS / PASS |
| P2 Plan-priced vendors sharing an identical price list inside an archetype | [rc 30 of 71 / 35 of 70] | 0 of 71 | 0 of 70 | spec: "two vendors do not share one price list" | PASS / PASS |
| P3 USD-billed vendors (22 vendors, 349 / 302 rows): consecutive rows with an identical amount | [rc 50% / 75%] | 1.8% | 1.8% | spec: debited at a moving rate, so ~0 | PASS / PASS |
| P4 Year-turn price change, share of comparable consecutive pairs that step +2% to +9% | [rc 0 of 29 / 0 of 28] | 11 of 16 (69%) | 14 of 21 (67%) | spec 0.60; pooled 25 of 37, z=+0.9 | PASS (low power) |
| P5 Rent indexation: vendors whose modal rent steps +2-4% from 2025 to 2026 | [rc 3 of 9 / 1 of 8, spec then 0.3] | 8 of 9 | 5 of 8 | spec 0.7; pooled 13 of 17 = 76% | PASS (low power) |
| P6 Extras, estimated share of rows above the vendor-year base price: telecom_mobile / telecom_both / telecom_internet / cowork / accounting / hosting / bike_sub | [rc 0 everywhere except cowork and hosting 4% in 4321] | .26 / .29 / .10 / .21 / .14 / .16 / .07 | .46 / .32 / .15 / .33 / .21 / .29 / .06 | spec .35 / .25 / .08 / .25 / .15 / .20 / .10 | PASS (rough estimator, 14-147 rows per family; 4321 runs high because price changes are counted too) |
| P7 KvK fee fixed at 85.15 (fixed_price) | 26 / 37 rows, all 85.15 | 26 of 26 | 37 of 37 | 100% | PASS / PASS |
| D1 Rows with an order number (`Order/Bestelling` + 5+ digits) | [rc 12.5% / 11.9%] | 3.3% (133 rows) | 4.1% (162 rows) | spec states rules, not a target share | info (down by two thirds) |
| D2 Easy rows with an order number outside a webshop-style archetype or on a bank line / till receipt | [rc 353 / 323] | 0 | 0 | 0 | PASS / PASS |
| D2b Hard rows with an order number on a bank line / till receipt | [rc 13 / 24] | 0 | 0 | 0 | PASS / PASS |
| D3 Receipts containing factuur / invoice wording (all rows, easy and hard) | [rc 127 of 896 / 114 of 937] | 0 of 919 | 0 of 935 | 0 | PASS / PASS |
| D4 Bank lines of non-invoicing archetypes with factuur / invoice wording, easy rows | [rc 103 of 257 / 97 of 268] | 0 of 233 | 0 of 273 | 0 | PASS / PASS |
| D5 Bare "Betaling/Payment <month>" on a receipt | [rc 63 / 68] | 0 | 0 | 0 | PASS / PASS |
| D6 Reference fragment share: invoices / bank lines of invoicing archetypes / bank lines of non-invoicing archetypes | [rc 29% / 22% / 28% and 26% / 23% / 26%] | 32% / 32% / 3.4% | 33% / 31% / 3.3% | spec 0.30 / 0.30 / 0.30 x 0.15 = 4.5% | PASS / PASS (counts template references too, so slightly above 30% is expected) |
| D7 NL/EN mix-in on receipts; BTW fragment on bank lines | 0; 0 | 0; 0 | 0; 0 | 0 | PASS / PASS |
| D8 One payment field per document: stacked channels; channel text on invoices; SEPA text off bank lines; card-terminal text on archetypes without till receipts | [rc 0 / 0 / 0 / 0] | 0 / 0 / 0 / 0 | 0 / 0 / 0 / 0 | 0 | PASS / PASS |
| D9 Known and documented in CREW: "Kassabon / Receipt" text on a bank transfer | [rc 2 / 4 rows] | 5 rows | 6 rows | info | info (0.13-0.15% of rows; bank lines on till-receipt archetypes are 2.2% / 2.8% of easy rows) |
| U1 Card-charged archetypes paid, easy rows | [rc 7 of 676 / 12 of 700 unpaid] | 0 of 676 unpaid | 0 of 700 unpaid | spec: always paid | PASS / PASS |
| U2 Card-charged archetypes paid, all rows by the vendor shown | [rc 9 of 712 / 15 of 727 unpaid] | 3 of 712 unpaid | 3 of 727 unpaid | spec: always paid | WARN / WARN (all six are vendor_description_disagree rows, see Item 3) |
| U3 Card-charged, paid easy rows that still print payment terms ("Betaaltermijn 30 dagen") | [rc 17 / 11, some unpaid] | 13 rows | 20 rows | spec: "a paid receipt, never an open payable" | WARN / WARN (0.3-0.5% of rows) |
| U4 Unpaid rows that are not invoices; unpaid-terms text on a paid row | 0; 0 | 0; 0 | 0; 0 | 0 | PASS / PASS |
| U5 Invoice paid fraction vs spec per true account, max abs z over 7 classes (card-charged excluded) | [rc 1.96 / 1.38] | **3.16** (Utilities 80.4% of 184 vs 88%); Professional 42.7% of 342 vs 50%, z=-2.7 | 1.74 | abs z<3 | WARN / PASS (see Item 3) |
| U6 Unpaid-terms text on unpaid rows without text noise | n/a | 51.4% of 222 (z=-1.1) | 51.3% of 187 (z=-1.0) | spec 0.55 | PASS / PASS (46.9% / 46.8% over all unpaid rows, because truncation cuts the trailing terms) |

Top-10 canonical vendor share by class, all rows (1234 / 4321), identical to round 2 because the vendor-mix RNG streams did not change: Software .445/.466, Travel .361/.368, Office .416/.459, Utilities .468/.459, General .462/.431, Professional .458/.472, Rent .534/.508. Margin to the 55% gate is still thinnest for Rent (1.6 and 4.2 pts).

## Item 1. Where round-2 WARN / FAIL items moved

| Round-2 item | R2 (1234 / 4321) | R3 (1234 / 4321) | Direction |
|---|---|---|---|
| FAIL vendor-disjoint diagnostic gap | 43.6 / 39.1 pts [rc] | 36.7 / 34.3 pts | better, still FAIL (limit 10) |
| FAIL keyword share under the ORIGINAL band | 34.6% / 35.9% [rc] | 43.2% / 42.9% | 1.8 / 2.1 pts short of 45% now; passes only under the revised 20-65% band |
| FAIL top-10 under the ORIGINAL <40% | 6 of 7 classes over | 6 of 7 classes over | unchanged; passes only under the revised 55% gate |
| WARN amount KS | see row 2b | see row 2b | mixed: 1234 Software .29 to .23, Rent .22 to .17; 4321 Software flat at .29, Rent .19 to .21; Utilities net .09 / .12 to .10 / .15 (worse) |
| WARN Professional net > 5000 | 7.8% / 6.9% | 7.8% / 5.2% | flat / slightly better |
| WARN Rent outside [150,1500] | 10.1% / 15.1% | 14.2% / 18.0% | worse |
| WARN duplicates after normalisation, canonical vendor | 2.28% / 2.00% [rc] | 2.10% / 2.10% | flat, still just above 2% |
| WARN vocabulary exclusivity (class level) | mean .264 / .264; worst class .45 / .35 | mean .314 / .271; worst class .50 / .40 | worse; 1234 now fails the mean gate |
| WARN Zipf Travel 0.78 (1234) | 0.78 / 0.80 | 0.78 / 0.80 | unchanged |
| WARN KvK share 10.7% (4321) | 7.1% / 10.7% | 7.1% / 10.7% | unchanged |
| WARN Software integer-euro share | 41.6% / 40.6% | 14.3% / 10.9% | resolved |
| WARN Software q95 vs stale spec mixture | 146 / 176 vs ~612 | 149 / 138 vs 597 | unchanged: passes only the revised 100-300 range |
| WARN document-type mix differs between seeds | chi2 18.6, p=.0003 | chi2 1.8, p=.62 | resolved |
| WARN Utilities amounts differ between seeds | KS p=.011 | KS p=.003; also Rent p<.001, Software p=.005 | worse (see Item 5) |

## Item 2. Amounts against the spec's stated families and ranges

Quantiles q05 / q25 / q50 / q75 / q95, spec mixture (200k simulated draws from the `amounts` block, clips applied) against net amounts of easy rows:

| Class | Spec | R3 1234 net | R3 4321 net | Max total 1234 / 4321 |
|---|---|---|---|---|
| Software | 6.9 / 13.8 / 32.8 / 102 / 597 | 5.0 / 11.0 / 20.8 / 44.9 / 149 | 5.1 / 10.9 / 19.2 / 34.5 / 115 | 1121 / 1482 |
| Travel | 3.2 / 7.4 / 15.1 / 50.1 / 180 | 3.3 / 13.8 / 30.4 / 58.5 / 141 | 3.6 / 13.3 / 28.6 / 56.3 / 144 | 592 / 578 |
| Office | 5.8 / 15.2 / 30.0 / 58.9 / 155 | 8.8 / 16.9 / 31.9 / 73.3 / 220 | 8.4 / 19.5 / 36.1 / 78.6 / 270 | 1781 / 1720 |
| Utilities | 12.5 / 29.0 / 58.6 / 104 / 206 | 13.5 / 32.5 / 61.6 / 117 / 263 | 12.0 / 25.9 / 47.5 / 94.2 / 244 | 639 / 617 |
| General | 4.0 / 11.6 / 24.5 / 51.4 / 150 | 4.8 / 14.7 / 27.3 / 46.2 / 101 | 5.1 / 11.1 / 24.6 / 44.1 / 102 | 2662 / 6050 |
| Professional | 85 / 250 / 440 / 800 / 2043 | 85 / 225 / 555 / 1315 / 6600 | 85 / 210 / 480 / 1170 / 5112 | 15294 / 16214 |
| Rent | 178 / 289 / 589 / 1045 / 1408 | 163 / 290 / 450 / 1075 / 1847 | 142 / 270 / 317 / 858 / 1890 | 3249 / 3321 |

- No impossible values: 0 amounts <= 0, 0 NaN, 0 net <= 0.
- Largest values are all explained by the corpus, not by a bug, but they are outside the spec's clips. Professional: every row above the 5000 clip (28 / 18 rows) comes from an hourly archetype (law_firm, big_four, consultancy, ip_firm), where the amount is rate x hours with hours up to 40 and rates up to 395; 39% / 36% of hourly rows exceed 2500 net, while the corpus archetypes themselves state `amt: [150, 2500]`, which hourly mode never reads. Non-hourly Professional rows stay under 2210. General: the 2662 and 6050 maxima are escalated `vendor_description_disagree` rows that carry another class's amount (5 / 7 General rows are above the spec clip of 700).
- Rent: rows below 150 are service-charge, heating-advance and meeting-room templates (40-145 net; 8 / 19 rows); rows above 1500 are office rents of 9 / 8 landlord vendors (27 / 24 rows). The realised flex-tier share (net 150-400) is 41% / 50% against the spec's 45%.
- Software and Travel remain the classes furthest from the spec shape (KS .23-.31 and .21-.27): the realised Software median is 19-21 against the mixture's 33, the realised Travel median is 29-30 against 15. Same finding as round 2; the class-level `amounts` block was not rewritten.

## Item 3. Spec against data: disagreements

1. **`amounts.Utilities.telecom` says `fixed_tiers` with `jitter_sd: 0.0`; `price_dynamics` says otherwise, and the data follows `price_dynamics`.** Share of telecom rows whose net is exactly one of the six listed tiers: 99% / 98% in round 2, 5.4% / 7.9% now (147 / 189 rows). The spec contradicts itself. Owner: stage 1.
2. **`amounts.Software.masses`**: share of easy Software rows whose net equals a listed mass fell from 27% / 28% to 4.9% / 5.2%, and 12.9% / 11.3% of rows are now below the smallest mass (6.90), from the USD conversion and the +/-20% per-vendor price points. The spec comment still calls the masses "the documented target shapes". Owner: stage 1.
3. **`amounts.Rent` says `jitter_sd_frac: 0.0`, "rent identical month to month"**, while `price_dynamics.extras.cowork` adds meeting rooms and day passes on 25% of bills. Realised: consecutive rent rows with an identical amount fell from 95% / 93% to 68% / 65%; coworking vendors show 2.2 / 2.7 distinct amounts per vendor-year, office landlords 1.0. Owner: stage 1.
4. **Card-charged archetypes "are always paid"** (spec and CREW). True for the content vendor, which is what the generator tests (`r["cv"].archetype`); not true for the vendor the row shows. Three rows per seed show a card-charged vendor (EasyPark, Q-Park, Transavia, OV-chipkaart, Apcoa) with an unpaid invoice, all `vendor_description_disagree` hard rows. Either the spec should say "content vendor" or the generator should also test the shown vendor. Owner: stage 3 (or stage 1 for the wording).
5. **Card-charged and paid, yet the text prints payment terms**: 13 / 20 easy rows such as "Parkeerabonnement maart 2025 ... Betaaltermijn 30 dagen" or an airline invoice with "Payment terms 30 days". The paid flag is right; the terms text contradicts "charged at the moment of use". Owner: stage 3 (`payment_text`, skip `invoice_paid_terms_p` for card-charged archetypes).
6. **Invoice paid fraction, seed 1234**: Utilities invoices are 80.4% paid (148 of 184) against the spec's 88%, z=-3.16, which crosses the 3-sigma line I use for rate checks; Professional 42.7% against 50%, z=-2.7. Seed 4321 is on target (86.7%, 51.4%), and pooled over both seeds Utilities is 84.2% of 448, z=-2.5. I found no mechanism in the generator (the paid draw is an independent per-row Bernoulli), so the most likely explanation is one unlucky cell out of 14 (Bonferroni-adjusted p about 0.02), but it is over the line and is reported as such. Owner: stage 3 to confirm there is no coupling; no spec change needed.
7. **Three different keyword-free targets**: `description_formats.keyword_free_fraction: 0.33`, band target 0.60, realised 49% / 50%. The 0.33 line is stale. Owner: stage 1.
8. **`measure_realism.py` reads a spec key `amount_ranges` that does not exist**, so its `out_of_range_by_account` prints "n/a (no amount_ranges)" for both seeds. The spec has no stated per-class range other than the clips inside `amounts`; the tool's docstring promises "the CURRENT spec amount_ranges". Owner: stage 1 (add the block) or stage 3 (drop the counter).
9. **`seed.run_seeds: [1337, 2024, 7]`** does not list the two seeds that were generated and audited (1234, 4321). Owner: stage 1.
10. **Corpus `amt: [150, 2500]` on hourly archetypes is dead configuration** (see Item 2), and the spec clip for `consultant_legal` is 5000. Owner: stage 2 (cap hours or rates) or stage 1 (raise the clip and say so).

Agreements worth stating, since they were the point of revision 2: every reference-text rule (D2 to D8) holds with zero violations on easy rows, and D2b / D3 also hold on hard rows; frozen prices, shared price lists and USD billing behave as the spec describes (P1 to P3); the year-turn change rate, rent indexation and extras are consistent with the stated probabilities at the power the rows allow (P4 to P6); the fixed KvK fee is exempt (P7). Not verifiable from the rows: `seat_change_p_per_step` 0.07 (several contracts of one vendor interleave, so seat sequences cannot be reconstructed; quoted seat counts do now vary inside a vendor) and the FX bounds 0.98-1.22 (list prices are not in the output).

## Item 4. Vocabulary exclusivity and the keyword share (the cost of revision 2)

Gate: of the top-20 TF-IDF tokens per class, at most 30% exclusive to that class, mean over classes, on description tokens with vendor-name tokens removed.

| View | mean 1234 | mean 4321 | Classes over 0.30, 1234 | Classes over 0.30, 4321 |
|---|---|---|---|---|
| Round-2 audit method (tokens of >= 3 letters, vendor tokens from the file) | .314 (R2 .264) | .271 (R2 .264) | General .50, Professional .40, Travel .35 | Travel .40, Utilities .35 |
| Bootstrap of that mean over rows (30 resamples) | .322 +/- .017 (R2 .277) | .314 +/- .019 (R2 .277) | | |
| Stage-3 tool `measure_vocab.py` (>= 2 letters, vendor tokens from the corpus) | .293 (R2 .264) | .279 (R2 .243) | General .45, Professional .35 | Travel, Utilities, Professional .35 |
| Raw description | .336 (R2 .286) | .307 (R2 .286) | | |
| Vendor + description | .479 (R2 .457) | .514 (R2 .493) | | |

Every view moved up. The new exclusive tokens are class nouns in the receipt-heavy classes: Travel gained fare, eur/euro, diesel, tankbeurt, parkeerkosten, reisdeclaratie (round 2: brandstof, fuel, terminal); General gained lunch, koffie, team, bestelnummer on top of kassabon and boodschappen. Mechanism: round 2's shared "Order / Invoice / Payment <number>" lines were the vocabulary those classes had in common with the rest; the document-type rules removed them from till receipts and from bank lines of non-invoicing archetypes (correctly, for realism), so the top-20 of Travel and General filled up with their own nouns. The same mechanism lifts the keyword-bearing share from 34.6% / 35.9% to 43.2% / 42.9% (Travel 38% to 55%, Office 57% to 68%, General 21% to 35%, Rent 34% to 50% in seed 1234).

Does it make the task trivial? No: a keyword-only rule covers 42-44% of rows at 84% accuracy, a description-only classifier reaches .62 / .68 on unseen vendors, and the leaky random split is at .95, under the 0.98 ceiling. But the direction is the one the gate exists to stop, seed 1234 is over the line, and seed 4321 is under it by less than its own sampling noise. Owner: stage 2 (give the transit, fuel, parking, supermarket and cafe pools shared receipt vocabulary that is legitimate on a till receipt or card line, e.g. bon / transactie / pas / terminal wording, instead of the removed invoice scaffolding). Stage 1 should not answer this by raising the 0.30 gate.

## Item 5. Cross-seed stability

| Metric | 1234 | 4321 | Test | Consistent? |
|---|---|---|---|---|
| Class counts (2x7 homogeneity) | | | chi2 = 9.3, df 6, p = 0.16 | yes |
| Hard/ambiguous share | 12.8% | 11.8% | z = 1.4 | yes |
| Escalate share (all rows) | 7.1% | 6.2% | z = 1.7 | yes |
| Own-class keyword hit | 43.2% | 42.9% | z = 0.2 | yes |
| Exclusivity mean (gate) | .314 | .271 | bootstrap sd .02 | marginal (opposite sides of the gate) |
| Top-10 share per class | .36-.53 | .37-.51 | max diff .05 | yes |
| Vendor-disjoint test acc | .583 | .607 | z = 0.9 | yes |
| Frozen-price share (critic's count) | 5.5% | 4.3% | | yes |
| Order-number share | 3.3% | 4.1% | | yes |
| Document-type mix | .447/.323/.155/.075 | .457/.310/.157/.077 | chi2 = 1.8, df 3, p = 0.62 | yes (R2: p = .0003) |
| Amount KS between seeds, per class | | | p = 1.0 (Travel), .60 (General), .52 (Prof), .025 (Office), .005 (Software), .003 (Utilities), <.001 (Rent) | NO for Rent, Utilities, Software at Bonferroni .007 (R2: only Utilities, p .011) |

The amount difference is a cluster effect, as in round 2 but larger: a class has 45-66 vendors, ten of them hold 36-53% of its rows, and since revision 2 a vendor's contract (plan, seats, service-charge or rent series, extras) is a per-seed draw, so two seeds can put a class median far apart (Rent median 450 against 317). Row-level KS overstates the significance, but the practical point stands: one seed is not a stable estimate of an amount marginal. Owner: stage 6 (use both seeds, do not use amount as evidence of calibration); stage 1 if more seeds are wanted.

## Item 6. Classifier diagnostic (DIAGNOSTIC on synthetic data, not a result)

TF-IDF (word 1-2gram on description, char_wb 2-4gram on vendor) + LogisticRegression(C=10), trained on the train file; description-only uses only the description block. Never quote as real-world accuracy. Round-2 values in brackets.

| | seed 1234 acc / macro-F1 | seed 4321 acc / macro-F1 |
|---|---|---|
| Train (resubstitution), vendor+desc | 1.000 / 1.000 (.9996 / .9997) | 1.000 / 1.000 (1.000 / 1.000) |
| Vendor-disjoint val | .557 / .528 (.464 / .448) | .586 / .565 (.548 / .526) |
| Vendor-disjoint test | .583 / .548 (.523 / .506) | .607 / .559 (.559 / .525) |
| Random 85/15 row split, held-out 15%; four more splits in [] | .950 / .939 [.945-.963] (rc .958) | .950 / .944 [.953-.973] (rc .950) |
| Test, description-only | .624 / .578 (.614 / .565) | .684 / .631 (.600 / .533) |
| Val, description-only | .622 / .582 (.554 / .519) | .683 / .652 (.645 / .620) |
| Test, description-only minus vendor+desc (paired bootstrap 95% CI) | +4.2 pts (+0.5, +7.7) (R2 +9.2) | +7.7 pts (+4.0, +11.5) (R2 +4.2) |
| Random split, description-only | .742 (rc .712) | .753 (rc .697) |
| Test by class (vendor+desc) | Software .80, Office .57, Travel .53, Rent .51, Prof .47, Util .46, General .36 | Software .91, Travel .62, Prof .58, Rent .54, General .49, Office .40, Util .31 |

Standard error of a test accuracy is about .02 (n = 599 / 598), so the +6 / +5 point rise in vendor-disjoint test accuracy is 2 to 2.5 sigma per seed and goes the same way in both seeds and in validation: descriptions carry more class signal than in round 2, which is the same fact as Item 4 seen from the classifier's side. The gap between the leaky split and the vendor-disjoint split narrowed to 36.7 / 34.3 points and still fails the 10-point rule; it remains a design property (a vendor lives in one class) rather than a generator bug. Description-only still beats vendor+description on unseen vendors in all four held-out sets, now significant in both seeds.

## Remaining FAIL / WARN, with the stage that should fix each

FAIL

| # | Item | Value (1234 / 4321) | Threshold | Owner stage |
|---|---|---|---|---|
| F1 | Vendor-disjoint vs random diagnostic gap | 36.7 / 34.3 pts | 10 pts | Stage 2 (vendor-to-archetype linkage is the cause; no generator parameter fixes it). Stage 6 mitigates by reporting vendor-disjoint numbers only. |
| F2 | Description-token exclusivity mean, round-2 audit method | .314 / .271 (bootstrap .322 / .314) | <=.30 | Stage 2 (shared receipt vocabulary in the Travel and General pools). Seed 1234 fails; seed 4321 passes without margin. Passes in both seeds only under the stage-3 tool's tokenisation (.293 / .279). |
| F3 | Keyword-bearing share under the ORIGINAL band | 43.2% / 42.9% | 45-65% original; 20-65% revised | Stage 1 (`keyword_shortcut_band`). Passes only under the revised band. |
| F4 | Top-10 vendor share under the ORIGINAL gate | 6 of 7 classes over .40 | <40% original; <=55% revised | Stage 1 (`vendor_frequency`). Passes only under the revised gate; informational. |

WARN

| # | Item | Value (1234 / 4321) | Owner stage |
|---|---|---|---|
| W1 | Amount KS against the spec class shapes | .09-.27 / .08-.29, five of seven classes over .10 in each seed | Stage 1: rewrite or retire the class-level `amounts` families (Item 3, points 1 to 3) |
| W2 | Professional net above the 5000 clip | 7.8% / 5.2%, max total 15294 / 16214 | Stage 2 (`rates` in `corpus/professional.json`) with stage 3 (`HOURS` list), or stage 1 (raise the clip) |
| W3 | Rent net outside [150,1500] | 14.2% / 18.0%, worse than R2 | Stage 2 (`corpus/rent.json` template amounts for service charges and institutional rents) or stage 1 (state the tiers that are really intended) |
| W4 | Software net below the smallest spec mass; spec masses and telecom tiers no longer realised | 12.9% / 11.3%; 5% and 5-8% on a listed value | Stage 1 |
| W5 | Zipf-Mandelbrot exponent, Travel | 0.78 / 0.80 against 1.0 +/- 0.2 | Stage 1 (`vendor_frequency.subtype_weights` flatten Travel); unchanged from R2 |
| W6 | Normalised duplicates by canonical vendor | 2.10% / 2.10% against <2% (CREW's >=95% unique is met at 97.9%) | Stage 3 (the redraw key compares text with digits intact, so "Order <n>" / "Payment of invoice <n>" repeats are not seen) or stage 2 (more short templates); iDEAL receipts carry most of it (5.3% / 5.5%) |
| W7 | Card-charged vendor shown with an unpaid invoice | 3 / 3 hard rows | Stage 3 (test the shown vendor too) or stage 1 (wording) |
| W8 | Card-charged, paid, but payment terms printed | 13 / 20 easy rows | Stage 3 (`payment_text`) |
| W9 | Invoice paid fraction, Utilities, seed 1234 | 80.4% vs 88%, z=-3.16 (4321: z=-0.6) | Stage 3 to confirm no coupling; probably a draw |
| W10 | Amount marginals differ between seeds | Rent p<.001, Utilities p=.003, Software p=.005 | Stage 6 (use both seeds); stage 1 if more seeds are wanted |
| W11 | Stale or missing spec entries | `keyword_free_fraction: 0.33`, missing `amount_ranges`, `run_seeds` without 1234 / 4321 | Stage 1 |
| W12 | KvK share of Professional, seed 4321 | 10.7% vs 8%, z=+1.9 | None needed (inside 2 sigma); unchanged from R2 |
| W13 | Class-level exclusivity above .30 | General .50, Prof .40, Travel .35 / Travel .40, Util .35 | Stage 2, same fix as F2 |

Resolved since round 2: Software integer-euro share (41% to 11-14%), document-type mix between seeds (p .0003 to .62), invoice number repeated inside one description (123 / 121 rows to 0), plus the three realism blockers that revision 2 targeted (frozen prices, misplaced order numbers, invoice wording on receipts).

## Judgement: fit for the ML evaluator?

Yes, conditionally, for the cold-start / testing role in CREW.md. Both seeds are leak-free (0 vendor, alias or canonical overlap; 0-2 near-duplicates of 600 held-out rows), have 0 exact duplicates, exact arithmetic on all 4000 rows, a sampled class mix that passes chi-square, noise and difficulty rates on spec, and consistent escalate labels. Revision 2 did not break any round-2 pass except the exclusivity mean in seed 1234.

Conditions for the hand-over:
1. Report vendor-disjoint numbers only and label every number synthetic-only. The 34-37 point gap to a random split means in-domain accuracy says nothing about unseen vendors.
2. State that the keyword band and the top-10 gate pass only under their revised values, and that the exclusivity gate fails in seed 1234 under the round-2 audit method (0.314) while passing under the stage-3 tool (0.293). Watch per-class errors for Travel and General, where the new class nouns sit.
3. Do not treat amount marginals as calibrated: the spec's `amounts` block is stale against `price_dynamics`, and the two seeds disagree on Rent, Utilities and Software amounts.
4. Evaluate on both seeds; a single seed is not a stable estimate.
5. Only a gold set can measure the synthetic-to-real gap; nothing in this report does.

Recommended before the next regeneration, in order of value: stage 2 shared receipt vocabulary (F2, W13), stage 1 clean-up of the `amounts` block and stale keys (W1, W4, W11), stage 3 payment-terms text and shown-vendor paid rule for card-charged archetypes (W7, W8).

## Method notes (so round 4 can reproduce the numbers)

- Scripts were ad hoc and are not committed. Pandas / scipy / scikit-learn from `.venv`.
- KS: two-sample against 200,000 draws from the spec `amounts` block (fixed RNG seed 20261012); lognormal components clipped with `np.clip`; Software = mass x seats, x 12 x 0.85 with p 0.15; Utilities energy uplift 1.30 for 9 of 20 months, else 0.85; telecom tiers uniform; settlement = |N(0, 180)|; Rent uniform inside each tier. "Total" uses all rows of the label, "net" uses `net_amount`.
- Zipf-Mandelbrot: MLE of s with q fixed at 3 over observed canonical-vendor counts per class, all rows.
- Near-duplicates: TF-IDF of character 3-grams (sublinear tf) on `norm(vendor) | norm(description)` with digit runs replaced by 0; a held-out row counts when its maximum cosine to any train row is >= 0.9. Round 2 used an unrecorded variant; counts agree within 2 rows.
- Normalised duplicates: lower-case, non-alphanumerics to a space, digit runs to 0; rate = 1 - unique / N. Round 2 used a slightly different normaliser (1.43% / 2.45% against 1.32% / 2.28% recomputed).
- Keyword share: the seven class regexes `LEX` in `data/synthetic/check_corpus.py`, case-insensitive, on the description only; "own" = the regex of the row's label matches; keyword-only rule = rows where exactly one class regex matches, predicted as that class. Round 2 used unsaved ad hoc stems (27.4% / 27.8%); with `LEX` round 2 is 34.6% / 35.9%.
- Exclusivity: sklearn TF-IDF, alphabetic tokens of >= 3 letters, top-20 per class by mean TF-IDF, exclusive = in exactly one class's top-20; vendor tokens = all tokens of the `vendor` and `vendor_canonical` columns. This reproduces round 2 exactly (.264 / .264).
- Diagnostic: as in Item 6; the random split is a stratified 85/15 split of all rows (random_state 0, four repeats with 1-4), trained on the 85%.
- Frozen-price share and order-number share: `measure_realism.py` functions and regex, unchanged.
- Price-change estimate (P4): easy rows of non-USD plan-priced vendors and of the fixed-fee General families (insurance, vve, sport, cleaning) and roadside; consecutive rows of one vendor with a net ratio of exactly 1 (no change) or inside [1.02, 1.09] (change); other ratios are ignored as different contracts. Extras fall inside that window for some families, so within-year rates from this estimator are inflated and are not reported; on the subset without extras, USD billing or per-seat plans the within-year count is 1 change in 112 pairs (spec 1.5% per month).
- Card-charged checks use the `archetype` column, which is the archetype of the vendor shown; the generator decides on the content vendor, which the metadata does not carry for hard rows.
- z for a rate = (realised - spec) / sqrt(spec x (1 - spec) / n).
