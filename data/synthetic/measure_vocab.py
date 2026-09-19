"""Vocabulary-exclusivity and diagnostic measurements for a generated draw (read-only).

Run: PYTHONPATH=src .venv/bin/python data/synthetic/measure_vocab.py data/synthetic/generated/transactions_1234.csv

Gate (heuristic, CREW.md): of the top-20 discriminative TF-IDF tokens per class, at most 30% are
exclusive to that class. Vendor-name tokens are legitimately exclusive (a vendor lives in one
class), so the exclusivity is reported for DESCRIPTION tokens (the gate), VENDOR tokens, and
vendor+description tokens. Two definitions are reported:
  top20_only  - token is in exactly one class's top-20 list (the auditor's reading; the gate)
  df_zero     - token never occurs in any row of another class (stricter about "never appears")
Top-20 per class = highest mean TF-IDF over that class's rows (sklearn TfidfVectorizer, alphabetic
tokens of >= 2 letters, lower-cased).
"""
import csv
import json
import re
import sys
from collections import Counter
from pathlib import Path

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer

K = 20
TOKEN = r"(?u)\b[^\W\d_]{2,}\b"


def load(path):
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


CORPUS = Path(__file__).resolve().parent / "spec" / "corpus"


def vendor_tokens():
    """Alphabetic tokens of every corpus vendor name/alias/product (the 'vendor-name tokens')."""
    toks = set()
    for p in sorted(CORPUS.glob("*.json")):
        for v in json.loads(p.read_text())["vendors"]:
            for s in [v["name"], v.get("product", "")] + v.get("aliases", []):
                toks.update(re.findall(r"[^\W\d_]{2,}", s.lower()))
    return toks


def strip_vendor_tokens(text, vt):
    return " ".join(w for w in re.findall(r"[^\W\d_]{2,}", text.lower()) if w not in vt)


def exclusivity(rows, fields, k=K, drop_vendor_tokens=False):
    accts = sorted(set(r["account"] for r in rows))
    txt = [" ".join(r[f] for f in fields) for r in rows]
    if drop_vendor_tokens:
        vt = vendor_tokens()
        txt = [strip_vendor_tokens(t, vt) for t in txt]
    X = TfidfVectorizer(lowercase=True, token_pattern=TOKEN).fit_transform(txt)
    lab = np.array([r["account"] for r in rows])
    B = (X > 0).tocsc()
    tops, dfc = {}, {}
    for a in accts:
        m = np.asarray(X[lab == a].mean(0)).ravel()
        tops[a] = list(np.argsort(-m)[:k])
        dfc[a] = np.asarray(B[lab == a].sum(0)).ravel()
    cnt = Counter(t for a in accts for t in tops[a])
    only = {a: sum(1 for t in tops[a] if cnt[t] == 1) / k for a in accts}
    dfz = {a: sum(1 for t in tops[a] if sum(dfc[b][t] for b in accts if b != a) == 0) / k for a in accts}
    return only, dfz


def report(rows):
    out = {}
    for label, fields, drop in (("description_GATE_vendor_name_tokens_removed", ["description"], True),
                                ("description_raw", ["description"], False), ("vendor", ["vendor"], False),
                                ("vendor+description", ["vendor", "description"], False)):
        only, dfz = exclusivity(rows, fields, drop_vendor_tokens=drop)
        out[label] = {"top20_only": {a: round(v, 2) for a, v in only.items()},
                      "top20_only_mean": round(float(np.mean(list(only.values()))), 3),
                      "top20_only_max": round(max(only.values()), 2),
                      "df_zero_mean": round(float(np.mean(list(dfz.values()))), 3)}
    return out


if __name__ == "__main__":
    import json
    print(json.dumps(report(load(sys.argv[1])), indent=1))
