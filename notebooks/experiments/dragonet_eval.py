import sys, json, time
from datetime import date
import numpy as np, pandas as pd
from sklearn.metrics import accuracy_score, f1_score

R = "C:/Users/SID-DRW/Desktop/allrepos/vault-ledger/"
sys.path.insert(0, R + "src")
from vault_ledger.classifier.dragonet_adapter import DragoNetClassifier
from vault_ledger.classifier.cascade import RUNS_DIR, DEFAULT_RUNS
from vaultledger.schemas import Transaction

C = R + "data/external/combined/"
ext = pd.read_csv(C + "test_external_real.csv", low_memory=False).sample(5000, random_state=0)
zera = pd.read_csv(C + "test_zerabooks.csv", low_memory=False)
s = pd.read_csv(R + "data/synthetic/generated/transactions_2026.csv")
m = pd.read_csv(R + "data/synthetic/generated/metadata_2026.csv")
syn = s[m.split.values == "test"]
tests = {"synthetic": syn, "external_real (5k sample)": ext, "zerabooks": zera}

def txns(d):
    out = []
    for i, r in enumerate(d.itertuples()):
        amt = r.amount if isinstance(r.amount, (int, float)) and not pd.isna(r.amount) else 0
        out.append(Transaction(txn_id=str(i), company_id="eval", date=date(2025, 6, 1), amount=abs(float(amt)),
                               direction="OUT", counterparty_name="" if pd.isna(r.vendor) else str(r.vendor),
                               description="" if pd.isna(r.description) else str(r.description), paid=None))
    return out

res = {}
for run in (sys.argv[2:] or DEFAULT_RUNS):
    clf = DragoNetClassifier(RUNS_DIR / run)
    for name, d in tests.items():
        t0 = time.time(); preds = []
        T = txns(d)
        for i in range(0, len(T), 256):
            preds += clf._predictor.predict(T[i:i + 256])
        ms = (time.time() - t0) / len(T) * 1000
        p = np.array([clf._account_of[x.ref_micro] for x in preds], dtype=object)
        conf = np.array([float(x.confidence) for x in preds]); y = d.account.to_numpy(dtype=object)
        o = np.argsort(-conf); prec = np.cumsum((p == y)[o]) / np.arange(1, len(y) + 1)
        ok = np.where(prec >= 0.95)[0]
        r = dict(acc=accuracy_score(y, p), f1=f1_score(y, p, average="macro"),
                 cov95=(ok.max() + 1) / len(y) if len(ok) else 0.0, ms_per_txn=ms)
        res[f"{run} | {name}"] = r; print(run, name, {k: round(v, 3) for k, v in r.items()}, flush=True)
json.dump(res, open(sys.argv[1], "w"), indent=1)
