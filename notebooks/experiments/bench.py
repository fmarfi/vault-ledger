import sys, time, json
import numpy as np, pandas as pd
from scipy.sparse import hstack
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression, SGDClassifier
from sklearn.svm import LinearSVC
from sklearn.model_selection import GroupKFold
from sklearn.metrics import accuracy_score, f1_score

R = "C:/Users/SID-DRW/Desktop/allrepos/vault-ledger/"
C = R + "data/external/combined/"
OUT = sys.argv[1]

def clean(d):
    d = d.copy()
    for c in ("vendor", "description"):
        d[c] = d[c].fillna("").astype(str).str.lower()
    return d

tr = clean(pd.read_csv(C + "train_mix_B.csv", low_memory=False))
ext = clean(pd.read_csv(C + "test_external_real.csv", low_memory=False))
zera = clean(pd.read_csv(C + "test_zerabooks.csv", low_memory=False))
s = pd.read_csv(R + "data/synthetic/generated/transactions_2026.csv")
m = pd.read_csv(R + "data/synthetic/generated/metadata_2026.csv")
syn_te = clean(s[m.split.values == "test"])
tests = {"synthetic": syn_te, "external_real": ext, "zerabooks": zera}
print({k: len(v) for k, v in dict(train=tr, **tests).items()}, flush=True)

def feats(kind):
    def mk():
        vs = []
        if kind in ("word", "both"):
            vs += [("vendor", TfidfVectorizer(max_features=60000, sublinear_tf=True)),
                   ("description", TfidfVectorizer(max_features=60000, sublinear_tf=True, ngram_range=(1, 2)))]
        if kind in ("char", "both"):
            vs += [("vendor", TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 5), max_features=150000, sublinear_tf=True)),
                   ("description", TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 5), max_features=150000, sublinear_tf=True))]
        return vs
    return mk

class Model:
    def __init__(self, fk, clf, weight=None):
        self.fk, self.clf, self.weight = fk, clf, weight
    def X(self, d, fit=False):
        return hstack([v.fit_transform(d[c]) if fit else v.transform(d[c]) for c, v in self.vs]).tocsr()
    def fit(self, d):
        self.vs = self.fk()
        w = None if self.weight is None else np.where(d.source == "vault_synthetic_2026", 1.0, self.weight)
        self.clf.fit(self.X(d, True), d.account, sample_weight=w); return self
    def scores(self, d):
        X = self.X(d)
        if hasattr(self.clf, "predict_proba"): return self.clf.predict_proba(X)
        return self.clf.decision_function(X)

def lr(): return LogisticRegression(max_iter=1000, C=4)
MODELS = {
    "1 baseline (word TF-IDF + LR, current)": lambda: Model(feats("word"), LogisticRegression(max_iter=600, C=4)),
    "2 char n-grams + LR": lambda: Model(feats("char"), lr()),
    "3 word+char + LR": lambda: Model(feats("both"), lr()),
    "4 word+char + LR, public weight 0.3": lambda: Model(feats("both"), lr(), 0.3),
    "5 word+char + linear SVM": lambda: Model(feats("both"), LinearSVC(C=0.5)),
    "6 word+char + SGD (modified huber)": lambda: Model(feats("both"), SGDClassifier(loss="modified_huber", alpha=2e-6, max_iter=30, random_state=0)),
}

def evaluate(model, d):
    sc = model.scores(d); cls = model.clf.classes_
    p = cls[sc.argmax(1)]; y = d.account.to_numpy(dtype=object)
    top2 = (cls[np.argsort(-sc, 1)[:, :2]] == y[:, None]).any(1).mean()
    r = dict(acc=accuracy_score(y, p), f1=f1_score(y, p, average="macro"), top2=top2)
    if sc.min() >= 0:  # probability-like: coverage at high-confidence accuracy
        conf = sc.max(1); o = np.argsort(-conf); hit = (p == y)[o]
        prec = np.cumsum(hit) / np.arange(1, len(hit) + 1)
        for t in (0.90, 0.95):
            ok = np.where(prec >= t)[0]
            r[f"cov@{int(t*100)}"] = (ok.max() + 1) / len(hit) if len(ok) else 0.0
    return r

results = {}
for name, mk in MODELS.items():
    t0 = time.time(); mdl = mk().fit(tr); ft = time.time() - t0
    row = {"fit_s": ft}
    for tn, td in tests.items():
        for k, v in evaluate(mdl, td).items(): row[f"{tn}_{k}"] = v
    t0 = time.time(); mdl.scores(zera.head(1000)); row["ms_per_1000"] = (time.time() - t0) * 1000
    results[name] = row
    print(name, {k: round(v, 3) for k, v in row.items()}, flush=True)

# 5-fold vendor-grouped CV over all real public business rows (synthetic always in train)
real = pd.concat([tr[tr.source != "vault_synthetic_2026"], ext])
synr = tr[tr.source == "vault_synthetic_2026"]
groups = real.vendor.where(real.vendor != "", real.description.str[:20])
best = max([k for k in results if "svm" not in k], key=lambda k: results[k]["external_real_f1"] + results[k]["zerabooks_f1"])
cv = {}
for name in ["1 baseline (word TF-IDF + LR, current)", best]:
    f = []
    for i, (a, b) in enumerate(GroupKFold(5).split(real, groups=groups)):
        mdl = MODELS[name]().fit(pd.concat([synr, real.iloc[a]]))
        e = evaluate(mdl, real.iloc[b]); f.append(e); print(name, "fold", i, {k: round(v, 3) for k, v in e.items()}, flush=True)
    cv[name] = {k: (float(np.mean([x[k] for x in f])), float(np.std([x[k] for x in f]))) for k in f[0]}
json.dump(dict(results=results, cv=cv, best=best), open(OUT, "w"), indent=1)
print("BEST", best, json.dumps(cv, indent=1))
