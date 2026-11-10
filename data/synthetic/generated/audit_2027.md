# Statistical audit, draw seed 2027 (compared with seed 2026)

Background read: `docs/background.md` (whole file), `data/synthetic/CREW.md`, `spec/generative_spec.yaml`, `docs/reports/research/requests.md` (no research finding is passed, and this audit uses none). I also read the round-3 audit on `origin/synth-data` to reuse its thresholds.

Scope: `generated/{transactions,metadata}_{2026,2027}.csv` and `splits/`, checked against the current spec (sha 60488dfa..., which matches `manifest_2027.json`). Seed 2026 was made under an earlier spec (a7658ca5...) without real vendors or missing fields. Each draw has 10,000 rows. I only read the data and edited nothing. Every number here is **synthetic-only**. Script: `.venv/Scripts/python -I`, pandas/scipy/sklearn. Thresholds are the heuristics from CREW.md and round 3 (marked *aud* where the auditor picked them). None is a published standard.

## Verdict

**Seed 2027: FAIL (conditional). The core statistics pass. Two spec-level faults fail, and one gate band fails on both seeds.**

- PASS: class mix, amounts, duplication, vendor-disjoint splits, near-duplicate leakage, difficulty mix, and the new rates (vendor_in_description, no_vat, real-vendor share, fine_category).
- FAIL 1, contamination of the external test set: `spec/corpus/real_vendors.json` still holds **207 normalized / 173 exact vendor names that also appear in `data/external/combined/test_external_real.csv`**, although the spec says "test-set vendors removed". 25 rows of draw 2027 use them (18 names, e.g. `WAL-MART ####`, `LINKEDIN ...`, `UNITED RENTALS ...`). The real vendors are also drawn from the **same public sources** as the external test set (us_oklahoma_pcard, nl_rijksoverheid_inkoop, uk_leeds/stockport/calderdale). So any score on that test set after training on 2027 is not an independent measure of the gap to real data. Likely cause: `spec/build_real_lexicon.py`, which removes test vendors by exact canonical name only (not aliases or digit-normalized names) and takes from the test set's own sources.
- FAIL 2, `vendor_legal_suffix_variation` is 0.089 against a spec rate of 0.14. On corpus-vendor rows it is 0.142, which is correct. On real-vendor rows it is 0.032, because only 2,480 of 14,749 real vendors have more than one alias. Likely cause: spec `real_vendors.share: 0.55` together with the generator's `ALIAS_ELIGIBLE`, which was not recomputed for the real-vendor pool.
- FAIL on both seeds, keyword band: the stem share is 4.5% (2027) and 3.2% (2026). A wider Dutch+English lexicon gives 16.3% and 17.2%. Both are below the revised band of 20-65% and the original band of 45-65%. Being below the band is the **safe direction** for the shortcut risk: the task is not trivially easy. But the band is not met, and it does not match the spec comment "keyword rows ~25%". Parameter: `description_source.keyword_phrasing_share: 0.01`. The band itself is the user's call (open question 4).

## Results table

| # | Check | Seed 2026 | Seed 2027 | Threshold | Result 2026 / 2027 |
|---|---|---|---|---|---|
| 1 | Class mix, chi2 of true_account vs prior x N (df 6) | 0.55, p=0.997, min 613 | 0.128, p=0.99996, min 606 | p>0.01; min class >=150 | PASS / PASS. Note: the fit is "too good" (lower tail P=4e-5 for 2027), so classes are drawn by near-quota, not multinomially. Not a fault |
| 1b | Label noise (account != true_account), train / val / test | 149/6977 = 2.1%; 0; 0 | 155/6996 = 2.2%; 0; 0 | spec 0.02, train only; tag matches | PASS / PASS |
| 2a | Amounts NaN / <=0 / out of clip; max | 0/0/0; 25000 | 0/0/0; 25000 | none; clip 1-25000 | PASS / PASS |
| 2b | KS of gross amount vs clipped lognormal(mu,sigma) per account, max D (account) | 0.049 (Rent, p=0.11) | 0.050 (Rent, p=0.089); all others <=0.028 | flag D>0.10 | PASS / PASS |
| 2c | Quantiles q05/q50/q95, data vs spec (2027) | | Software 4.0/22.2/123 vs 4.0/22.0/122; Prof 83/652/4988 vs 76/620/5092; Rent 117/452/2004 vs 122/493/1994 | close | PASS |
| 3a | Zipf MLE per class, all vendors (min-max) | 0.67-0.79 | 0.67-0.91 | spec 0.74 +/-0.2 *aud* | PASS / PASS |
| 3b | Zipf, corpus vendors only | 0.67-0.79 | 0.71-0.86 | 0.74 +/-0.2 | PASS / PASS |
| 3c | Zipf, real vendors, MLE on the spec's ranks (rows in public data) | n/a | 0.42-0.56 | spec 0.5 +/-0.2 | - / PASS |
| 3d | Share held by the top-5 vendors (all rows) | 10.3% (NS, Microsoft 365, Staples, Q-Park, Adobe) | 6.3% (Microsoft 365, Bol.com, Amazon.nl, NS, HEMA) | info | info |
| 3e | Max top-10 vendor share within a class | 53.8% (Prof) | 40.8% (General) | revised 55% / original 40% | PASS rev, FAIL orig / PASS rev, FAIL orig (by 0.8 pt) |
| 3f | Distinct canonical vendors / vendor strings | 373 / 1169 | 3251 / 3634 | >=15 per class | PASS / PASS |
| 4a | vendor_canonical in more than one split | 0 | 0 | 0 | PASS / PASS |
| 4b | Exact vendor string in more than one split; after normalization | 0; 0 | 0; 1 (`UPS W87` val vs `UPS W52` train: two real canonicals that collide only when digits are masked) | 0 | PASS / PASS (the collision is harmless; see note) |
| 4c | Normalized vendor+description shared across splits, rows | 0 | 0 | ~0 | PASS / PASS |
| 4d | Normalized description alone shared across splits, rows | 2601 | 2620 | info (generic templates) | info |
| 4e | Synthetic vendor strings that appear in the external real test set, rows (train/val/test) | 336 (197/133/6), corpus vendors only (Adobe, Atlassian, KPMG...) | 152 (89/9/54); 25 of them real-lexicon rows | spec: test-set vendors removed | WARN / **FAIL** |
| 5 | Exact duplicates [vendor, description, amount]; full row | 0.00%; 0.00% | 0.00%; 0.00% | <2% | PASS / PASS |
| 5b | Duplicates after normalization (digits masked) on vendor+description | 13.6% | 7.5% | info | info |
| 6 | Account-name stem in vendor+description (wider NL+EN lexicon) | 3.2% (17.2%) | 4.5% (16.3%) | revised band 20-65% / original 45-65% | FAIL / FAIL (below the band: safe for shortcuts) |
| 7 | Hard+ambiguous share | 12.0% (566 h + 634 a) | 12.0% (552 h + 648 a) | 10-15% | PASS / PASS. Escalate only on non-easy rows: yes |
| 8 | Noise rates vs spec effective rate (grain x1.4, cap 0.075) | see below | see below | within +/-20% relative *aud* | 2026: legal suffix PASS; 2027: legal suffix FAIL |
| N1 | vendor_in_description (empty vendor) | 0 | 12.08%; empty vendor <=> tag exact; all doc_type=bank; name visible in description 97.8%; paid 100% | spec 0.12 of all rows | - / PASS (it is 25.1% of bank rows; the spec states 12% of all rows, and the generator follows that) |
| N2 | no_vat (empty vat_rate) | 0 | 24.56%; empty <=> tag exact | 0.25 | - / PASS |
| N3 | Real-vendor share of easy rows (by class) | 0 | 54.8% (51-64%); 0 on hard rows; 48.3% of all rows | 0.55 of easy and recurring rows | - / PASS |
| N4 | fine_category: empty / parent != true_account / distinct | n/a | 0 / 0 / 29 (155 differ from the noisy `account`, all of them label flips: correct) | consistent | - / PASS |
| P | Provenance: spec and generator hashes = manifest_2027; split files = metadata split counts; split fractions | match | 0.700/0.150/0.150; match | 70/15/15 | PASS / PASS |

Noise rates (2026 / 2027 / spec effective): legal suffix 0.139 / **0.089** / 0.14; abbreviation 0.102 / 0.104 / 0.10; truncated 0.058 / 0.060 / 0.07; typo 0.071 / 0.072 / 0.075; ocr 0.064 / 0.065 / 0.066; missing/generic 0.052 / 0.049 / 0.050; casing 0.075 / 0.073 / 0.075; whitespace 0.048 / 0.045 / 0.05; vendor_ocr 0.036 / 0.037 / 0.04; junk 0.030 / 0.029 / 0.03; store code on receipt_pos 4.5% / 4.8% / 0.044; punctuation_drop 0.033 / 0.033 / 0.06. Punctuation_drop is WARN on both seeds: the generator applies it only to the ~53% of rows that have a separator (0.06 x 0.53 = 0.032), so the spec rate is a per-eligible-row rate, not the per-row rate the spec text says. The mixed-language tag fell from 9.7% to 4.8% because real vendors carry no mixed templates. The spec gives no target for it.

## Realism number: adversarial AUC (synthetic vs real vendor strings)

Method: real = non-empty `vendor` in `test_external_real.csv` (25,863 rows, 8 public sources). Synthetic = non-empty `vendor` of the draw. Classes are balanced by subsampling. TF-IDF char_wb 2-5-grams (min_df 2, sublinear) + LogisticRegression, StratifiedKFold(5, shuffle, seed 0), ROC AUC, mean +/- sd.

| Set | Seed 2026 | Seed 2027 |
|---|---|---|
| Unique vendor strings (main figure) | **0.942 +/- 0.008** (n=1169 each) | **0.748 +/- 0.014** (n=3634 each) |
| Rows (vendor repeats count) | 0.996 (n=10000) | 0.936 (n=8792) |
| 2027 corpus-vendor strings only | | 0.930 (n=872) |
| 2027 real-lexicon strings only | | 0.719 (n=2762) |

Reading: 2027 moves just under the CREW gate (<=0.75, target ~0.6), with no margin, and only on unique strings. Row-level AUC stays above 0.9 ("template artifacts"). The corpus vendors are still almost perfectly separable (0.93). The whole improvement comes from swapping in real names taken from the **same public sources as the comparison set**, with 173 exact names shared. So 0.748 overstates realism: it partly measures that the two sets share sources, not that the generator imitates real data. The test set also is not a Dutch-startup gold set (mostly US/UK public-sector purchase cards).

## What to fix, and where

1. `spec/build_real_lexicon.py`: remove test vendors by normalized name across all aliases, and preferably take real vendors from sources that do not feed `test_external_real.csv`. Then rerun the AUC.
2. Generator `ALIAS_ELIGIBLE` / spec `noise_rates.vendor_legal_suffix_variation`: recompute eligibility with the real-vendor pool, or state the rate per eligible row.
3. Spec `description_source.keyword_phrasing_share` against the keyword band. The band (20-65% vs 45-65%) waits for the user's ruling (background open question 4).
4. Spec wording: `punctuation_drop` and `missing_fields.vendor_in_description` should say what their base is (eligible rows / all rows).
