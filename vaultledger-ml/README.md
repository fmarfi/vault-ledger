# vaultledger-ml — DragoNet-style categorization engine

Standalone package. It ranks categories for a transaction row; it never builds
debit/credit entries and is not wired into the Vault Ledger app.

> **Results on synthetic data. Not indicative of real-world accuracy.**
> The built-in generator is a pipeline-test fixture. Nothing trained on it is
> shipped or quoted as accuracy. Real accuracy is measured on a customer's own
> export, against a baseline, before any number is promised.

## What is here (Tier 1)

| Part | File |
|---|---|
| Reference taxonomy (12 macro / 41 micro + SUSPENSE) | `vaultledger/taxonomy/` |
| Data shapes (Transaction, Label, Suggestion) | `vaultledger/schemas.py` |
| Text normalization (processor prefixes, refs, store numbers) | `vaultledger/normalize.py` |
| Taxonomy mask: joint decoding + DragoNet's argmax-then-mask | `vaultledger/model/mask.py` |
| DragoNet: two encoders, fusion, macro + micro heads | `vaultledger/model/dragonet.py` |
| Encoders: pretrained (default) or from scratch | `vaultledger/model/encoders.py` |
| Training (Phase A), vendor-disjoint validation, early stopping | `vaultledger/model/train.py` |
| Inference (PyTorch; ONNX comes in ML-M7) | `vaultledger/model/infer.py` |
| Synthetic generator with the spec's hard cases | `vaultledger/synth/` |
| Export adapter interface (real exports plug in here) | `vaultledger/io/adapters.py` |

Change from the spec: the encoders start from a small pretrained multilingual
model (`intfloat/multilingual-e5-small`, MIT per its model card) instead of
being trained from scratch, because training data is scarce. It is fetched once
at build time and ships with the app; nothing is downloaded at runtime. The
spec's from-scratch encoder remains available (`encoder.kind: scratch`).

## Use

```
python -m venv .venv && .venv\Scripts\pip install -e .[dev,fetch]
.venv\Scripts\python scripts\fetch_encoder.py         # once, build time (~490 MB)
.venv\Scripts\python -m vaultledger.model.train       # synthetic fixture -> runs/<timestamp>/
.venv\Scripts\python -m vaultledger.model.train --data <folder> --out runs/x
.venv\Scripts\python -m vaultledger.model.train --set encoder.kind=scratch --set train.epochs=3
.venv\Scripts\python -m pytest -q
```

Each run writes `model.pt` (without the frozen encoder weights), `metrics.json`,
`report.md` and `config.yaml`.

## Not built yet

Baseline TF-IDF model and full eval harness (ML-M5), ablations, ONNX export
(ML-M7), company COA mapping (ML-M8), calibration and AUTO status (ML-M9),
per-company fine-tuning and correction loop (ML-M10), export writers (ML-M11),
rules and counterparty memory (ML-M3).
