"""Combine DragoNet (old, new) and TF-IDF. Tune only on calibration data; report on untouched tests."""
import sys, re, json, time, itertools
from datetime import date
import numpy as np, pandas as pd
from scipy.sparse import hstack
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import GroupShuffleSplit
from sklearn.metrics import accuracy_score, f1_score

R = "C:/Users/SID-DRW/Desktop/allrepos/vault-ledger/"
sys.path.insert(0, R + "src")
from vault_ledger.classifier.dragonet_adapter import DragoNetClassifier
from vault_ledger.classifier.cascade import RUNS_DIR
from vaultledger.schemas import Transaction
OUT = sys.argv[1]
ACC = ["General/Other Expense", "Office Supplies Expense", "Professional Services Expense", "Rent Expense",
       "Software & Subscriptions Expense", "Travel & Transport Expense", "Utilities Expense"]
AI = {a: i for i, a in enumerate(ACC)}

def norm(d):
    d = d.copy()
    for c in ("vendor", "description"): d[c] = d[c].fillna("").astype(str)
    d["amount"] = pd.to_numeric(d.get("amount"), errors="coerce")
    return d.reset_index(drop=True)

C = R + "data/external/combined/"
mix = norm(pd.read_csv(C + "train_mix_B.csv", low_memory=False))
ext = norm(pd.read_csv(C + "test_external_real.csv", low_memory=False))
zera = norm(pd.read_csv(C + "test_zerabooks.csv", low_memory=False))
s = pd.read_csv(R + "data/synthetic/generated/transactions_2026.csv"); m = pd.read_csv(R + "data/synthetic/generated/metadata_2026.csv")
syn_val, syn_test = norm(s[m.split.values == "val"]), norm(s[m.split.values == "test"])
# TF-IDF must not have seen synthetic val -> drop those rows from its training mix
vkey = set(zip(syn_val.vendor, syn_val.description))
mix = mix[~((mix.source == "vault_synthetic_2026") & np.array([k in vkey for k in zip(mix.vendor, mix.description)]))]
# split the real external test by vendor: 40% calibration, 60% untouched test
g = ext.vendor.str.lower().where(ext.vendor != "", ext.description.str[:20])
ci, ti = next(GroupShuffleSplit(1, test_size=0.6, random_state=1).split(ext, groups=g))
ext_cal, ext_test = ext.iloc[ci].reset_index(drop=True), ext.iloc[ti].reset_index(drop=True)
sets = {"syn_val": syn_val, "ext_cal": ext_cal, "synthetic_test": syn_test, "external_real_test": ext_test, "zerabooks": zera}
print({k: len(v) for k, v in sets.items()}, "tfidf train", len(mix), flush=True)

# ---- member 1: TF-IDF word+char LR, public weight 0.3 -----------------------------------------
def vecs():
    return [("vendor", TfidfVectorizer(sublinear_tf=True, max_features=60000)),
            ("description", TfidfVectorizer(sublinear_tf=True, max_features=60000, ngram_range=(1, 2))),
            ("vendor", TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 5), max_features=150000, sublinear_tf=True)),
            ("description", TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 5), max_features=150000, sublinear_tf=True))]
t0 = time.time(); V = vecs(); low = lambda d, c: d[c].str.lower()
X = hstack([v.fit_transform(low(mix, c)) for c, v in V]).tocsr()
lr = LogisticRegression(max_iter=1000, C=4).fit(X, mix.account, sample_weight=np.where(mix.source == "vault_synthetic_2026", 1.0, 0.3))
order = [list(lr.classes_).index(a) for a in ACC]
def p_tfidf(d): return lr.predict_proba(hstack([v.transform(low(d, c)) for c, v in V]).tocsr())[:, order]
print("tfidf fit", round(time.time() - t0), "s", flush=True)

# ---- members 2, 3: DragoNet with the full distribution ---------------------------------------
def dragonet(run):
    clf = DragoNetClassifier(RUNS_DIR / run); clf._predictor.cfg.setdefault("decode", {})["top_k"] = 7
    def f(d):
        T = [Transaction(txn_id=str(i), company_id="ens", date=date(2025, 6, 1),
                         amount=0.0 if pd.isna(a) else abs(float(a)), direction="OUT",
                         counterparty_name=v, description=x, paid=None)
             for i, (v, x, a) in enumerate(zip(d.vendor, d.description, d.amount))]
        P = np.zeros((len(T), len(ACC)))
        for i in range(0, len(T), 256):
            for j, sg in enumerate(clf._predictor.predict(T[i:i + 256])):
                for micro, p in [(sg.ref_micro, sg.confidence), *sg.alternatives]:
                    if micro in clf._account_of: P[i + j, AI[clf._account_of[micro]]] += p
        P = np.where(P.sum(1, keepdims=True) > 0, P, 1.0)  # no prediction -> uniform
        return P / P.sum(1, keepdims=True)
    return f
members = {"tfidf": p_tfidf, "dragonet_old": dragonet("synth-crew-2026-pretrained-top2"),
           "dragonet_new": dragonet("synth-crew-2026-pretrained-top2-mix14k")}
P = {}
for mn, fn in members.items():
    t0 = time.time()
    for sn, d in sets.items(): P[mn, sn] = fn(d)
    n = sum(len(d) for d in sets.values()); print(mn, "ms/txn", round((time.time() - t0) / n * 1000, 2), flush=True)

# ---- meta features (input shape) --------------------------------------------------------------
BANK = re.compile(r"card purchase|pos |sepa|incasso|debit|ach |\d{2}/\d{2}|xx\d|ref[: ]|pin |betaalautomaat", re.I)
def meta(d):
    return np.c_[d.vendor.str.strip() != "", d.description.str.strip() != "", d.amount.notna(),
                 np.log1p(d.description.str.len()), d.description.map(lambda x: bool(BANK.search(x))),
                 d.description.map(lambda x: x.isupper() and len(x) > 5)].astype(float)

def report(p, d):
    y = d.account.map(AI).values; pr = p.argmax(1); conf = p.max(1)
    o = np.argsort(-conf); prec = np.cumsum((pr == y)[o]) / np.arange(1, len(y) + 1); ok = np.where(prec >= 0.95)[0]
    return dict(acc=accuracy_score(y, pr), f1=f1_score(y, pr, average="macro", labels=range(len(ACC))),
                top2=float((np.argsort(-p, 1)[:, :2] == y[:, None]).any(1).mean()),
                cov95=float((ok.max() + 1) / len(y)) if len(ok) else 0.0)
CAL, TESTS = ["syn_val", "ext_cal"], ["synthetic_test", "external_real_test", "zerabooks"]
def cal_score(fn):  # balanced: mean macro-F1 over the two calibration sets
    return np.mean([report(fn(s_), sets[s_])["f1"] for s_ in CAL])

combos = {}
for mn in members: combos[f"single: {mn}"] = lambda s_, mn=mn: P[mn, s_]
names = list(members)
combos["average (equal)"] = lambda s_: sum(P[n, s_] for n in names) / 3
best_w, best = None, -1
for w in itertools.product(np.arange(0, 1.01, 0.1), repeat=2):
    if w[0] + w[1] > 1.0001: continue
    ww = (w[0], w[1], 1 - w[0] - w[1])
    sc = cal_score(lambda s_: sum(wi * P[n, s_] for wi, n in zip(ww, names)))
    if sc > best: best, best_w = sc, ww
combos[f"weighted {dict(zip(names, np.round(best_w, 1)))}"] = lambda s_: sum(wi * P[n, s_] for wi, n in zip(best_w, names))

# stacking: LR on log-probs + input-shape features (and their interactions), trained on calibration sets
def Z(s_):
    L = np.hstack([np.log(np.clip(P[n, s_], 1e-6, 1)) for n in names]); M = meta(sets[s_])
    return np.hstack([L, M, (M[:, [1, 4]][:, :, None] * L[:, None, :]).reshape(len(L), -1)])
Zc = np.vstack([Z(s_) for s_ in CAL]); yc = np.concatenate([sets[s_].account.map(AI).values for s_ in CAL])
wc = np.concatenate([np.full(len(sets[s_]), 1.0 / len(sets[s_])) for s_ in CAL]) * len(yc) / 2
stk = LogisticRegression(max_iter=3000, C=1.0).fit(Zc, yc, sample_weight=wc)
def stacked(s_):
    out = np.zeros((len(sets[s_]), len(ACC))); out[:, stk.classes_] = stk.predict_proba(Z(s_)); return out
combos["stacking (learned per input type)"] = stacked

# disagreement rule on top of stacking: if DragoNet-old and TF-IDF disagree, halve confidence
def stacked_gate(s_):
    p = stacked(s_).copy(); dis = P["tfidf", s_].argmax(1) != P["dragonet_old", s_].argmax(1)
    p[dis] *= 0.5; return p
combos["stacking + disagreement -> review"] = stacked_gate

res = {}
for cn, fn in combos.items():
    res[cn] = {t: report(fn(t), sets[t]) for t in TESTS}
    print(f"{cn:60s}", " | ".join(f"{t}: f1 {r['f1']:.3f} acc {r['acc']:.3f} top2 {r['top2']:.3f} cov95 {r['cov95']:.3f}"
                                   for t, r in res[cn].items()), flush=True)
json.dump(res, open(OUT, "w"), indent=1)
