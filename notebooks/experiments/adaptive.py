"""Robustness to a changeable chart of accounts.

Train once on ~30 fine categories, then roll predictions up to any chart (a grouping of the fine
categories). Compare with retraining a model directly on each chart, and test adding a brand-new
account from a few examples."""
import sys, re, json, time
import numpy as np, pandas as pd
from scipy.sparse import hstack
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import SGDClassifier, LogisticRegression
from sklearn.model_selection import GroupShuffleSplit
from sklearn.metrics import accuracy_score, f1_score

R = "C:/Users/SID-DRW/Desktop/allrepos/vault-ledger/"
sys.path.insert(0, R + "notebooks"); sys.path.insert(0, R + "src")
import data_sources as ds
OUT = sys.argv[1]
SW, OF, PR, RE_, SO, TR, UT, GE = ("Software & Subscriptions Expense", "Office Supplies Expense",
    "Professional Services Expense", "Rent Expense", "Software & Subscriptions Expense",
    "Travel & Transport Expense", "Utilities Expense", "General/Other Expense")
FINE = [  # (fine category, parent account, pattern)  -- first match wins
    ("insurance_bank", GE, r"insurance|verzeker|\bbank|merchant fee"),
    ("registry_fees", PR, r"kvk|ip_registry|registry|taxes and licen|chamber of commerce"),
    ("legal_notary", PR, r"legal|\blaw|advocat|notar|solicitor|lawyer|attorney|ip_firm"),
    ("accounting_tax", PR, r"accountan|boekhoud|audit|tax_advice|tax advi|big_four|payroll_service|bookkeep"),
    ("consulting", PR, r"consult|advis|advies|hr_|recruit|translation|interpret|subcontract|contractor|"
                       r"uitbesteden|professional|temporary|contract labo"),
    ("cloud_hosting", SW, r"cloud|hosting|domain|server|api_saas"),
    ("software", SW, r"software|saas|subscription|\bict\b|\bit\b|computer serv|digital|\bapps?\b|web_builder|"
                     r"dev_tools|information and comm|information communication|internet services"),
    ("telecom", UT, r"telecom|telephone|phone|mobile|broadband|internet|communications"),
    ("energy", UT, r"energy|electric|\bgas\b|grid|energie|utilit|nutsvoorz"),
    ("water", UT, r"water"),
    ("coworking", RE_, r"cowork|flexwerk"),
    ("rent_lease", RE_, r"\brent|lease|leasing|\brates\b|huisvesting|office space|real estate|kantoorverhuur|"
                        r"vastgoed|landlord|property"),
    ("fuel_ev", TR, r"fuel|petrol|ev_charging|charging|mileage|motor|vehicle|automotive|roadside"),
    ("air_travel", TR, r"airline|air travel|flight"),
    ("hotel", TR, r"hotel|accommodation|lodging|verblijf|subsistence"),
    ("parking_toll", TR, r"parking|toll"),
    ("car_rental_taxi", TR, r"taxi|ride_share|car_rental|car_share|contract hire|car allowance|\bcar\b"),
    ("public_transport", TR, r"rail|train|transit|ov_tap|coach|\bbus|ferry|bike|scooter|commuter|transport|"
                             r"travel|vervoer|\breis"),
    ("it_hardware", OF, r"hardware|electronics|peripherals|cables|computer equip"),
    ("furniture", OF, r"furniture|furnishing"),
    ("printing", OF, r"print|copier|inkt|toner"),
    ("office_supplies", OF, r"office|stationery|papier|supplies|benodigdheden|kantoor|packaging|equipment|"
                            r"materials|wholesale"),
    ("meals_catering", GE, r"meal|catering|food|restaurant|\bbars?\b|cafe|kantine|representatie|entertain|"
                           r"hospitality"),
    ("advertising", GE, r"advertis|marketing|publicity|promotion|search_cloud_ads"),
    ("postage_shipping", GE, r"postage|shipping|courier|\bmail|freight"),
    ("training_membership", GE, r"training|education|opleiding|membership|dues|contribution|conference|"
                                r"seminar|sportschool|books|periodical"),
    ("repairs_cleaning", GE, r"repair|maintenance|cleaning|schoonmaak|sleutel|diy|garden"),
    ("retail_misc", GE, r"grocer|supermarket|department store|discount|drugstore|household|marketplace|gift|"
                        r"bloemist|liquor|kapper|retail|clothing|uniform|leisure"),
    ("other_general", GE, r"misc|general|other|overig|expenses?\b|services|diensten|cost of goods|events?\b"),
]
PARENT = {f: p for f, p, _ in FINE}
RX = [(f, re.compile(p, re.I)) for f, _, p in FINE]
DEFAULT = {OF: "office_supplies", SW: "software", UT: "energy", RE_: "rent_lease", TR: "public_transport",
           PR: "consulting", GE: "other_general"}
EXCL = re.compile(ds._RULES[0][1], re.I)

def fine_of(text):
    t = str(text)
    if not t.strip() or EXCL.search(t): return None
    for f, rx in RX:
        if rx.search(t): return f
    return None

# ---- data -------------------------------------------------------------------------------------
s = pd.read_csv(R + "data/synthetic/generated/transactions_2026.csv")
m = pd.read_csv(R + "data/synthetic/generated/metadata_2026.csv")
f = [fine_of(a) for a in m.archetype]
syn = pd.DataFrame(dict(vendor=s.vendor, description=s.description, split=m.split, source="vault_synthetic_2026",
                        fine=[x if x and PARENT[x] == acc else DEFAULT[acc] for x, acc in zip(f, s.account)]))
names = [n for n, v in ds.SOURCES.items() if v[2] == "business" and n not in ("vault_synthetic_2026", "zerabooks_benchmark")]
pub = ds.load_all(names, verbose=False)
pub["fine"] = pub.label_raw.map(fine_of)
pub = ds.cap_per_source(pub.dropna(subset=["fine"]), 25000)
for d in (syn, pub):
    for c in ("vendor", "description"): d[c] = d[c].fillna("").astype(str).str.lower()
g = pub.vendor.where(pub.vendor != "", pub.description.str[:20])
a, b = next(GroupShuffleSplit(1, test_size=0.2, random_state=0).split(pub, groups=g))
train = pd.concat([syn[syn.split != "test"], pub.iloc[a]], ignore_index=True)
test = pd.concat([syn[syn.split == "test"], pub.iloc[b]], ignore_index=True)
cats = sorted(PARENT)
print("train", len(train), "test", len(test), "fine cats", train.fine.nunique(), flush=True)
print(train.fine.value_counts().to_string(), flush=True)

# ---- model ------------------------------------------------------------------------------------
CLF = sys.argv[2] if len(sys.argv) > 2 else "sgd"
def vecs():
    return [("vendor", TfidfVectorizer(sublinear_tf=True, max_features=60000)),
            ("description", TfidfVectorizer(sublinear_tf=True, max_features=60000, ngram_range=(1, 2))),
            ("vendor", TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 5), max_features=120000, sublinear_tf=True)),
            ("description", TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 5), max_features=120000, sublinear_tf=True))]
V = vecs(); Xtr = hstack([v.fit_transform(train[c]) for c, v in V]).tocsr()
Xte = hstack([v.transform(test[c]) for c, v in V]).tocsr()
def clf():
    if CLF == "lr": return LogisticRegression(max_iter=1000, C=4)
    return SGDClassifier(loss="modified_huber", alpha=2e-6, max_iter=30, random_state=0)
def fit(y, w=None, rows=None):
    X = Xtr if rows is None else Xtr[rows]
    return clf().fit(X, y, sample_weight=w)

def score(y, p): return dict(acc=accuracy_score(y, p), f1=f1_score(y, p, average="macro"))
res = {}
t0 = time.time(); fm = fit(train.fine); pf = fm.predict(Xte)
res["fine_model_on_fine"] = score(test.fine, pf); print("fine", res["fine_model_on_fine"], round(time.time()-t0), "s", flush=True)

# ---- random charts of accounts ----------------------------------------------------------------
rng = np.random.default_rng(0); charts = [("vault 7 accounts", PARENT)]
for n in (4, 10, 16, 22):
    for seed in range(2):
        perm = rng.permutation(cats); grp = {c: f"acct{i % n}" for i, c in enumerate(perm)}
        charts.append((f"random {n} accounts #{seed+1}", grp))
charts.append(("all 29 fine accounts", {c: c for c in cats}))
rows = []
for name, mp in charts:
    yt = test.fine.map(mp); roll = pd.Series(pf).map(mp).values
    r = dict(chart=name, n=len(set(mp.values())), **{f"rollup_{k}": v for k, v in score(yt, roll).items()})
    if name != "all 29 fine accounts":
        t0 = time.time(); pd_ = fit(train.fine.map(mp)).predict(Xte)
        r.update({f"retrained_{k}": v for k, v in score(yt, pd_).items()}); r["retrain_s"] = time.time() - t0
    rows.append(r); print(r, flush=True)
res["charts"] = rows

# ---- adding a brand-new account from a few examples ------------------------------------------
new = []
for c in ("air_travel", "legal_notary", "telecom", "advertising", "furniture", "coworking"):
    base = np.where(train.fine != c)[0]; pool = np.where(train.fine == c)[0]
    tmask = (test.fine == c).values
    for k in (5, 20, 100):
        if len(pool) < k: continue
        pick = rng.choice(pool, k, replace=False); idx = np.concatenate([base, pick])
        w = np.where(train.fine.values[idx] == c, 30.0, 1.0)  # same x30 upweight as the personal model
        p = fit(train.fine.values[idx], w, idx).predict(Xte)
        r = dict(new_account=c, examples=k, recall_new=float((p[tmask] == c).mean()),
                 precision_new=float((test.fine.values[p == c] == c).mean()) if (p == c).any() else 0.0,
                 others_acc=float(accuracy_score(test.fine[~tmask], p[~tmask])), test_rows=int(tmask.sum()))
        new.append(r); print(r, flush=True)
res["new_account"] = new
json.dump(res, open(OUT, "w"), indent=1, default=float)
print("DONE")
