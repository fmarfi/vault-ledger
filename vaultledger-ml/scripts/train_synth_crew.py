"""Train DragoNet on the synthetic data crew's rows (branch synth-data) and
score it on the crew's held-out test split.

    python scripts/train_synth_crew.py [--seed 4321] [--encoder pretrained|scratch]

Synthetic data that has NOT passed the data team's realism gate: an internal
experiment, never quoted as accuracy.
"""
from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

import numpy as np

from vaultledger.eval.metrics import SYNTHETIC_BANNER, summarize
from vaultledger.io.adapters import SynthCrewAdapter
from vaultledger.model.infer import Predictor
from vaultledger.model.train import load_config, train
from vaultledger.taxonomy import load_taxonomy

ROOT = Path(__file__).resolve().parents[1]
TAX_PATH = ROOT / "vaultledger" / "taxonomy" / "app_accounts.yaml"


def fetch(seed: str) -> tuple[Path, Path]:
    out = ROOT / "data" / "synth-crew"
    out.mkdir(parents=True, exist_ok=True)
    paths = []
    for name in (f"transactions_{seed}.csv", f"metadata_{seed}.csv"):
        dst = out / name
        if not dst.exists():
            blob = subprocess.run(["git", "show", f"origin/synth-data:data/synthetic/generated/{name}"],
                                  cwd=ROOT, capture_output=True, check=True).stdout
            dst.write_bytes(blob)
        paths.append(dst)
    return paths[0], paths[1]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", default="4321")
    ap.add_argument("--encoder", default="pretrained")
    ap.add_argument("--set", action="append", default=[])
    ap.add_argument("--tag", default="")
    a = ap.parse_args()
    tax = load_taxonomy(TAX_PATH)
    txns, labels, split = SynthCrewAdapter().load(*fetch(a.seed))
    ids = {s: {t for t, v in split.items() if v == s} for s in ("train", "val", "test")}
    cfg = load_config(overrides=[f"encoder.kind={a.encoder}", *a.set])
    run = ROOT / "runs" / f"synth-crew-{a.seed}-{a.encoder}{a.tag}"
    m = train(cfg, txns, labels, run, tax=tax, split_ids=(ids["train"], ids["val"]))

    pred = Predictor.load(run)
    test = [t for t in txns if t.txn_id in ids["test"]]
    by_id = {lab.txn_id: lab for lab in labels}
    sug = pred.predict(test)
    y_mi = np.array([tax.micro_index[by_id[t.txn_id].ref_micro] for t in test])
    p_mi = np.array([tax.micro_index[s.ref_micro] for s in sug])
    p_ma = np.array([tax.macro_index[s.ref_macro] for s in sug])
    res = summarize(tax.parent, tax.parent[y_mi], y_mi, p_ma, p_mi)
    res["banner"] = SYNTHETIC_BANNER + " Data has not passed the realism gate."
    res["rows"] = {k: len(v) for k, v in ids.items()}
    (run / "test_metrics.json").write_text(json.dumps(res, indent=1), encoding="utf-8")
    print(json.dumps({"test": res, "val_best_epoch": m["best_epoch"], "train_seconds": m["train_seconds"]}, indent=1))


if __name__ == "__main__":
    main()
