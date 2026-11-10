# Where we left off (2026-11-10)

Read this first. Full plan: `C:\Users\SID-DRW\.claude\plans\serialized-frolicking-quokka.md`.
Results so far: `notebooks/model_experiments.ipynb` (rebuild: `.venv/Scripts/python notebooks/build_results_notebook.py`).
Nothing is committed yet.

## Goal now
Make the synthetic data more realistic using the real public data, so a model trained on it works on real
transactions. Today, synthetic-only training scores 0.14 (TF-IDF) / 0.22 (DragoNet) macro F1 on real data.
Target: 0.35 or more.

## Done in this step (plan step 1: A1 + A3 + A6)
- `data/synthetic/spec/fine_categories.py`: the 29 detailed categories, their parent account, and `fine_of()`.
- `data/synthetic/spec/build_real_lexicon.py`: builds `spec/corpus/real_vendors.json`, about 15k real vendors.
  - Test-set vendors are removed.
  - Vendor names are cleaned and person names dropped.
- Generator (`data/synthetic/generate_transactions.py`) and spec (`generative_spec.yaml`):
  - `real_vendors` (share 0.55): real vendors are mixed in.
  - `missing_fields`: 12% bank-feed rows (vendor only inside the description) and 25% rows with no VAT.
  - New metadata column `fine_category`.
- `tests/test_synthetic_generator.py`:
  - 3 new tests: detailed category matches the account, real-vendor and missing-field rates, no test-set vendor in
    the real list.
  - The split test now skips empty vendors.

## Update (same day): step 1 finished
- The vendor list was rebuilt without any test-set or corpus vendors (exact name overlap with the test set: 0).
  9/9 tests pass.
- Trained on synthetic data only (macro F1, `notebooks/results/synth_gap_2027.json`):

  | Seed | Synthetic test | Real public data | ZeraBooks |
  |---|---|---|---|
  | 2026 | 0.57 | 0.19 | 0.14 |
  | 2027 | 0.63 | 0.32 | 0.25 |

- Audit: `data/synthetic/generated/audit_2027.md`. Vendor realism AUC 0.94 → 0.75, measured before the leak fix.
- Open from the audit: legal-suffix variants are on 9% of rows vs 14% in the spec, because real vendors have few
  aliases.
- **Next: plan step 2** (description styles from real bank lines and e-invoices, hard cases from real mistakes, and
  generated alias variants).

## (Older) Stopped mid-run
1. **Fixing a leak**: 6 vendors were in both the real list and our corpus under different names (Zoom / ZOOM.US,
   Atlassian, AWS, JetBrains, TransIP, EasyPark), so they landed in two splits. The fix is written in
   `build_real_lexicon.py` (it removes corpus vendors and brand words) but has **not run yet**. Run:
   ```
   .venv/Scripts/python -I data/synthetic/spec/build_real_lexicon.py
   .venv/Scripts/python -I data/synthetic/generate_transactions.py --seed 2027 --n 10000
   .venv/Scripts/python -m pytest -q tests/test_synthetic_generator.py      # all 9 should pass
   ```
2. **Gates (not built yet):**
   - Adversarial AUC, synthetic vs. real, on the vendor field.
   - Train TF-IDF on seed 2027 only and score it on `data/external/combined/test_external_real.csv` and
     `test_zerabooks.csv`.
   - Compare with seed 2026 (0.14).
   - Reuse `notebooks/experiments/bench.py`.
3. If it improves: retrain DragoNet on seed 2027 (about 10 min) with `notebooks/experiments/train_dragonet_mix.py`
   or `vaultledger-ml/scripts/train_synth_crew.py --seed 2027`, then score it with `dragonet_eval.py`.

## Not touched
- Seed 2026 data and the DragoNet models used by the app are unchanged.
- The retrained DragoNet is saved separately (`vaultledger-ml/runs/synth-crew-2026-pretrained-top2-mix14k`) and the
  app doesn't use it.

## Next plan steps after that
- **Plan step 2:** description styles from real bank lines and e-invoice XMLs; hard cases from real mistakes.
- **Plan step 3:** loaders for the description-rich sources (Canada, Atlanta, Montgomery, Austin, ...), then the
  mixed retrain.
- **Open decisions:**
  - Put the input-type routing into the cascade: blend for vendor documents, DragoNet old for bank lines.
  - A Dutch pilot customer's data.
  - A licence check before training a model we sell.
