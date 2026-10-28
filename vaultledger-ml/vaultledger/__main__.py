"""One entry point for the engine.

    python -m vaultledger generate --out data/synth      # write the synthetic fixture
    python -m vaultledger train [--data DIR] [--set k=v]  # Phase A training -> runs/<id>/
    python -m vaultledger predict RUN_DIR DATA_DIR        # print suggestions for a dataset
"""
from __future__ import annotations

import argparse
import sys


def main() -> None:
    if len(sys.argv) < 2 or sys.argv[1] not in ("generate", "train", "predict"):
        print(__doc__)
        sys.exit(2)
    cmd, rest = sys.argv[1], sys.argv[2:]
    if cmd == "train":
        from .model.train import main as train_main

        train_main(rest)
    elif cmd == "generate":
        from .synth.generator import SynthConfig, generate, write_dataset

        ap = argparse.ArgumentParser(prog="vaultledger generate")
        ap.add_argument("--out", default="data/synth")
        ap.add_argument("--seed", type=int, default=7)
        ap.add_argument("--companies", type=int, default=8)
        a = ap.parse_args(rest)
        ds = generate(SynthConfig(seed=a.seed, n_companies=a.companies))
        print(f"wrote {write_dataset(ds, a.out)} ({len(ds.transactions)} rows)")
    else:
        from .io.adapters import SyntheticAdapter
        from .model.infer import Predictor

        ap = argparse.ArgumentParser(prog="vaultledger predict")
        ap.add_argument("run_dir")
        ap.add_argument("data_dir")
        ap.add_argument("--limit", type=int, default=20)
        a = ap.parse_args(rest)
        txns, _, _ = SyntheticAdapter().load(a.data_dir)
        txns = txns[: a.limit]
        for t, s in zip(txns, Predictor.load(a.run_dir).predict(txns)):
            print(f"{t.counterparty_name[:28]:28} | {t.description[:24]:24} -> "
                  f"{s.ref_macro}/{s.ref_micro} ({s.confidence:.2f})")


if __name__ == "__main__":
    main()
