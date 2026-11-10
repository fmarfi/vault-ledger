"""Build corpus/real_vendors.json: real vendor names from the public data, each with a detailed category.

    .venv/Scripts/python data/synthetic/spec/build_real_lexicon.py

The generator mixes these in next to the hand-made corpus vendors (spec: real_vendors).
Every vendor in the real test sets (data/external/combined/test_*.csv) is left out, so a model
trained on the synthetic data is never tested on a vendor name it saw.
"""
from __future__ import annotations

import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path[:0] = [str(HERE), str(ROOT / "notebooks"), str(ROOT / "src")]
import data_sources as ds  # noqa: E402
from fine_categories import PARENT, fine_of  # noqa: E402
from vault_ledger.classifier.memory import vendor_key  # noqa: E402

OUT = HERE / "corpus" / "real_vendors.json"
PER_CATEGORY = 1500        # cap, so big categories don't swamp the small ones
MIN_AGREE = 0.6            # share of a vendor's rows that must carry its majority category
MIN_ROWS = 2              # one-off vendors carry too much label noise
JUNK = re.compile(r"redact|personal data|withheld|various|anoniem|�|^\W*$|^\d+$|^n/?a$|unknown|"
                  r"private individual|\bmr\b|\bmrs\b|\bms\b|^[a-z]\.? [a-z]+$", re.I)
BUSINESS = re.compile(r"\b(ltd|llc|inc|bv|b\.v|nv|gmbh|plc|co|corp|company|group|services?|and|the|of|"
                      r"stichting|vereniging|centre|center|shop|store|hotel|council|school|uk|limited)\b|&", re.I)
NL_SOURCES = {"nl_rijksoverheid_inkoop"}


def clean_name(v: str) -> str:
    """'Amazon* 026-0005339-53' -> 'Amazon', 'STAPLS7111179113000002' -> 'STAPLS'."""
    v = re.sub(r"[#*]\s*\S*\d\S*", " ", v)
    v = re.sub(r"\d[\d\- /]{2,}", " ", v)
    v = re.sub(r"(?<=[A-Za-z])\d{3,}", " ", v)
    return re.sub(r"\s+", " ", v).strip(" -*#")


def person_like(v: str) -> bool:
    """'Christopher Machin' (a person paid directly), not a business."""
    w = v.split()
    return (2 <= len(w) <= 3 and all(x[:1].isupper() and x[1:].islower() and x.isalpha() for x in w)
            and not BUSINESS.search(v))


# legal-form spellings a vendor name shows up with on invoices and bank lines; each group is one form
LEGAL_FORMS = [["B.V.", "BV", "bv", "B.V"], ["N.V.", "NV"], ["Ltd", "Ltd.", "Limited", "LTD"],
               ["Inc", "Inc.", "INC"], ["LLC", "L.L.C."], ["GmbH", "GMBH"], ["PLC", "plc"]]
BANK_CUT = 22              # bank feeds cut the counterparty name to about 22 characters


def alias_variants(canon: str) -> list[str]:
    """Generated spellings of one vendor: other legal-suffix forms, the other case, the bank-feed cut.

    'Stavoor B.V.' -> ['Stavoor BV', 'Stavoor bv', 'STAVOOR B.V.']; no legal form is added to a name
    that has none, because the real form is unknown.
    """
    out = []
    for forms in LEGAL_FORMS:
        for f in forms:
            m = re.match(rf"^(.*\S)[\s,]+{re.escape(f)}$", canon)
            if m:
                out += [f"{m.group(1)} {g}" for g in forms if g != f][:2]
                break
        else:
            continue
        break
    out.append(canon.upper() if canon != canon.upper() else canon.title())
    if len(canon) > BANK_CUT:
        out.append(canon.upper()[:BANK_CUT].rstrip(" ,.-&"))
    return [a for a in dict.fromkeys(out) if a and a != canon and not person_like(a)]


def main() -> None:
    names = [n for n, v in ds.SOURCES.items() if v[2] == "business" and v[3] == "real"]
    df = ds.load_all(names, verbose=False)
    df = df[df.vendor.str.strip() != ""]
    df["fine"] = df.label_raw.map(fine_of)
    df = df.dropna(subset=["fine"])
    df["clean"] = df.vendor.map(clean_name)
    df["key"] = df.clean.map(vendor_key)
    df = df[(df.key.str.len() >= 3) & ~df.vendor.str.contains(JUNK) & ~df.clean.map(person_like)]

    held = set()
    for p in (ROOT / "data" / "external" / "combined").glob("test_*.csv"):
        held |= {k for v in pd.read_csv(p, usecols=["vendor"]).vendor.dropna().astype(str) for k in (vendor_key(v), vendor_key(clean_name(v)))}
    before = df.key.nunique()
    df = df[~df.key.isin(held)]
    print(f"vendors {before:,} -> {df.key.nunique():,} after removing {len(held):,} test-set vendors")
    # a real vendor that is also a corpus vendor ('ZOOM.US' vs 'Zoom') would sit in two splits under two names
    corpus = json.loads((HERE / "corpus" / "vendors.json").read_text(encoding="utf-8"))
    ckeys = {vendor_key(clean_name(a)) for v in corpus for a in [v["canonical"], *v["aliases"]]}
    brands = {k.split()[0].split(".")[0] for k in ckeys if k} - {"the", "van", "de", "het"}
    brands = {b for b in brands if len(b) >= 3}
    first = df.key.str.split().str[0].str.split(".").str[0]
    before = df.key.nunique()
    df = df[~df.key.isin(ckeys) & ~first.isin(brands)]
    print(f"vendors {before:,} -> {df.key.nunique():,} after removing corpus vendors")

    out = []
    for key, g in df.groupby("key"):
        cnt = Counter(g.fine)
        fine, n = cnt.most_common(1)[0]
        if len(g) < MIN_ROWS or n / len(g) < MIN_AGREE:
            continue
        spell = Counter(g.vendor.str.strip())
        canon = Counter(g.clean).most_common(1)[0][0]
        nl = g.source.isin(NL_SOURCES).mean()
        aliases = {canon, *[a for a, _ in spell.most_common(4)]}
        for a in alias_variants(canon):   # a generated spelling must not land on a held-out or corpus vendor
            k = vendor_key(clean_name(a))
            if k == key or (k and k not in held and k not in ckeys and k.split()[0].split(".")[0] not in brands):
                aliases.add(a)
        out.append({"canonical": canon, "account": PARENT[fine], "fine_category": fine,
                    "archetype": f"real_{fine}", "aliases": sorted(aliases), "families": {},
                    "languages": {"nl": 8, "en": 2} if nl > 0.5 else {"nl": 3, "en": 7},
                    "freq_4321": 0, "vendor_unverified": True, "rows": int(len(g)),
                    "sources": sorted(set(g.source))})
    by = defaultdict(list)
    for v in out:
        by[v["fine_category"]].append(v)
    final = []
    for f in sorted(by):   # keep the most frequent vendors per category
        final += sorted(by[f], key=lambda v: (-v["rows"], v["canonical"]))[:PER_CATEGORY]
    OUT.write_text(json.dumps(final, ensure_ascii=False, indent=0), encoding="utf-8")
    c = Counter(v["fine_category"] for v in final)
    print(f"wrote {len(final):,} vendors to {OUT}")
    print(json.dumps(dict(sorted(c.items())), indent=0))


if __name__ == "__main__":
    main()
