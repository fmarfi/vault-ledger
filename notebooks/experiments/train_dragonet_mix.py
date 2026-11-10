"""Retrain DragoNet (top2 config) on synthetic train + a public real/synthetic business sample.
Validation stays the synthetic vendor-disjoint val split, so the run is comparable."""
import sys, json
from datetime import date
from pathlib import Path
import pandas as pd, yaml

ML = Path("C:/Users/SID-DRW/Desktop/allrepos/vault-ledger/vaultledger-ml")
from vaultledger.io.adapters import SynthCrewAdapter, APP_ACCOUNT_MAP
from vaultledger.schemas import Transaction, Label
from vaultledger.model.train import train
from vaultledger.taxonomy import load_taxonomy

N_PUBLIC = int(sys.argv[1]) if len(sys.argv) > 1 else 14000
TAG = sys.argv[2] if len(sys.argv) > 2 else "mix14k"
tax = load_taxonomy(ML / "vaultledger" / "taxonomy" / "app_accounts.yaml")
G = Path("C:/Users/SID-DRW/Desktop/allrepos/vault-ledger/data/synthetic/generated")
txns, labels, split = SynthCrewAdapter().load(G / "transactions_2026.csv", G / "metadata_2026.csv")
tr_ids = {t for t, v in split.items() if v == "train"}; va_ids = {t for t, v in split.items() if v == "val"}

mix = pd.read_csv("C:/Users/SID-DRW/Desktop/allrepos/vault-ledger/data/external/combined/train_mix_B.csv", low_memory=False)
pub = mix[mix.source != "vault_synthetic_2026"]
pub = pub.groupby("source", group_keys=False)[pub.columns.tolist()].apply(
    lambda g: g.sample(min(len(g), max(300, N_PUBLIC // pub.source.nunique())), random_state=0))
pub = pub.sample(min(N_PUBLIC, len(pub)), random_state=0)
for i, r in enumerate(pub.itertuples()):
    tid = f"pub-{i}"; macro, micro = APP_ACCOUNT_MAP[r.account]
    amt = 0.0 if pd.isna(r.amount) else abs(float(r.amount))
    txns.append(Transaction(txn_id=tid, company_id=f"pub-{r.source}", date=date(2025, 6, 1), amount=amt,
                            direction="OUT", counterparty_name="" if pd.isna(r.vendor) else str(r.vendor),
                            description="" if pd.isna(r.description) else str(r.description), paid=None))
    labels.append(Label(tid, r.account, macro, micro, "EXPORT", "OK")); tr_ids.add(tid)
print("public rows", len(pub), pub.source.value_counts().head(12).to_dict(), flush=True)

cfg = yaml.safe_load((ML / "runs" / "synth-crew-2026-pretrained-top2" / "config.yaml").read_text())
cfg["encoder"]["pretrained"]["path"] = str(ML / cfg["encoder"]["pretrained"]["path"])
run = ML / "runs" / f"synth-crew-2026-pretrained-top2-{TAG}"
m = train(cfg, txns, labels, run, tax=tax, split_ids=(tr_ids, va_ids))
print(json.dumps({"best_epoch": m["best_epoch"], "train_seconds": m["train_seconds"], "run": str(run)}))
