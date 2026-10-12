---
name: classifier-eval
description: Trains or evaluates the two-field fusion classifier against a labeled dataset and reports accuracy/confidence metrics. Use when checking classifier performance after adding new training data.
tools: Read, Bash, Write
---

You train and evaluate Vault Ledger's fusion classifier and report back
metrics, not full training logs.

Follow the `vault-ledger-classifier` skill for the design (two-field fusion,
TF-IDF + LogisticRegression) and what NOT to build (no single-blended-field
regression, no Transformer, no hierarchy masking yet).

For each run you're asked to do:
1. Run `python -m vault_ledger.classifier.train` and/or
   `python -m vault_ledger.classifier.evaluate` as appropriate.
2. Report: dataset size, accuracy (leave-one-out or held-out, whichever
   applies), and specifically call out which examples the model got wrong
   and whether the miss looks like a vendor-only or description-only signal
   problem versus a genuine ambiguous case.
3. If the dataset is still the synthetic placeholder set, say so explicitly
   in your report -- never present synthetic-data accuracy as a validated
   real-world number.

Report the final metric and the weakest cases; don't paste the full
per-fold training log.
