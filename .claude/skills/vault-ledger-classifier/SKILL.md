---
name: vault-ledger-classifier
description: How to (re)train and evaluate Vault Ledger's two-field fusion classifier -- two vectorizers over vendor and description, concatenated, fixed COA as label space, confidence score output. States explicitly what NOT to build.
---

# Vault Ledger two-field fusion classifier

## The design, and why (Report 1 item 4, Report 4 SS1)

Two separate `TfidfVectorizer`s -- one for vendor, one for description --
concatenated (`scipy.sparse.hstack`) before a single classifier
(`LogisticRegression`) over the fixed 8-account COA. Implementation:
`src/vault_ledger/classifier/fusion_classifier.py`.

This exists because a reference paper (DragoNet, BTG Pactual, 150k+ real
transactions) found vendor name alone is a weak signal (~57% F1) while
fusing vendor + description reaches ~93-95% F1 -- and this gain holds even
for simple TF-IDF+shallow-model setups, not just deep learning.

## Explicitly dropped -- do not rebuild this

The original approach was a single TF-IDF vectorizer over
`vendor + " " + description` concatenated as one text blob, trained on a
public personal-expense Kaggle dataset. **This was dropped because it
underperforms the two-field fusion design and the label space didn't
transfer to SME bookkeeping.** If you find yourself concatenating vendor and
description into one string before vectorizing, or looking for that old
notebook/dataset, stop -- that is the design this project moved away from.

## How to (re)train

```
python -m vault_ledger.classifier.train
```

Reads `data/synthetic/labeled_transactions.csv`, trains, saves to
`data/synthetic/fusion_classifier.joblib`. Swap in a real labeled CSV with
the same three columns (`vendor,description,account`) when real data
exists -- no code changes needed.

## How to evaluate

```
python -m vault_ledger.classifier.evaluate
```

Runs leave-one-out evaluation (appropriate only because the synthetic
dataset is tiny -- switch to a real train/test split once there's enough
real data for one). **Treat any accuracy number from the synthetic set as a
pipeline sanity check, not a validated metric** -- real OCR-derived
descriptions will be noisier than this hand-written set (Report 4 SS1).

## Confidence output is required, not optional

`predict()` must always return `(account, confidence)`, never just a label
-- this feeds `confidence_gate.py` directly (Report 1, item 6).

## If TF-IDF underperforms once real data exists

`HashingVectorizer` is a documented, easy-to-swap alternative (Report 4
SS1) that performed comparably in the reference paper's shallow-model
experiments and scales better to larger vocabularies.

## What NOT to do

- Don't reach for a Transformer architecture -- that's BTG's
  infrastructure choice for 150k+ rows, not an MVP requirement.
- Don't add Taxonomy-aware Attention / hierarchy masking until the COA
  grows past a flat list (not needed at 8 flat accounts).
- Don't add differential privacy / DP-SGD training -- explicitly out of
  scope for the MVP.
