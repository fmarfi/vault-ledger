---
name: synth-generator
description: Stage 3 of the synthetic-data crew. Implements and runs the seeded generator that samples the spec and corpus into labeled transactions with ground-truth metadata. Use after the spec and corpus exist.
tools: Read, Write, Edit, Bash
---

You implement `data/synthetic/generate_transactions.py`. Read
`data/synthetic/CREW.md`, the spec, and the corpus first.

Requirements:
- **Deterministic**: one `--seed`; same seed, same output. Record the seed and
  spec hash in the output header.
- **Sample, don't template**: draw account from the class prior, vendor from
  the Zipf frequency, description from the corpus, amount from the per-account
  distribution, then apply the noise model. Emit recurring series (same vendor,
  monthly cadence, dated) for recurring accounts.
- **Output** `data/synthetic/generated/transactions_<seed>.csv` with columns:
  vendor, description, date, amount, paid, account, plus hidden-truth columns
  `source=synthetic`, `archetype`, `difficulty` (easy|hard|ambiguous),
  `noise_applied`. Keep the classifier-facing training file to
  vendor,description,account -- the metadata stays in a separate file so it can
  never leak into features.
- **Vendor-disjoint split**: write train/val/test so that a vendor (and its
  aliases) appears in exactly one split. Random row splits leak and inflate
  accuracy -- do not do them.
- Never write into `labeled_transactions.csv` directly; the auditor and critic
  must pass first.

Add tests under `tests/` for determinism and the vendor-disjoint guarantee, run
them with `.venv/bin/python -m pytest`, and report row counts per split/class.
