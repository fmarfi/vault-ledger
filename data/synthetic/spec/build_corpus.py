"""Rebuild spec/corpus/*.json from the surviving draw 4321 (revision-2 output).

Mines vendors (canonical name, aliases, account, family, language mix) and
description phrasings (turned into templates: dates, months, amounts and
reference numbers become placeholders), then adds attribute-crossed generic
phrasings so every account has >= 80 phrasings, about a third keyword-free.
Deterministic: no randomness. Run:  python data/synthetic/spec/build_corpus.py
"""
from __future__ import annotations

import itertools
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
SRC = ROOT / "vaultledger-ml" / "data" / "synth-crew"
OUT = Path(__file__).resolve().parent / "corpus"

# noise types that damage the text itself; rows carrying them are not mined
# (the generator re-applies noise on its own)
DESTRUCTIVE = {"typo_char_swap_drop_dup", "ocr_confusion", "truncated_description",
               "casing_variation", "abbreviation_nl_en", "missing_or_generic_description",
               "store_terminal_code"}

KEYWORDS = {
    "Rent Expense": ["huur", "rent", "kantoor", "office", "werkplek", "desk", "cowork", "lease", "servicekosten"],
    "Utilities Expense": ["energie", "energy", "stroom", "gas", "water", "internet", "mobiel", "mobile",
                          "telecom", "netbeheer", "elektriciteit", "electricity", "glasvezel", "fiber"],
    "Software & Subscriptions Expense": ["abonnement", "subscription", "licen", "saas", "cloud", "plan",
                                         "seat", "user", "hosting", "software", "storage", "api"],
    "Travel & Transport Expense": ["reis", "trip", "rit", "ride", "parkeren", "parking", "trein", "train",
                                   "vlucht", "flight", "brandstof", "fuel", "tank", "taxi", "ov", "laden"],
    "Office Supplies Expense": ["papier", "paper", "printer", "toner", "inkt", "ink", "pen", "map", "folder",
                                "kantoorartikelen", "supplies", "monitor", "kabel", "cable", "bureau", "stoel"],
    "Professional Services Expense": ["advies", "advice", "consult", "juridisch", "legal", "notaris", "notary",
                                      "accountant", "administratie", "jaarrekening", "salaris", "payroll", "uren", "hours"],
    "General/Other Expense": ["boodschappen", "lunch", "koffie", "coffee", "taart", "gift", "cadeau",
                              "verzekering", "insurance", "porto", "bloemen", "drinks", "snacks"],
}

NL_MONTHS = ["januari", "februari", "maart", "april", "mei", "juni", "juli", "augustus",
             "september", "oktober", "november", "december"]
EN_MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August",
             "September", "October", "November", "December"]


def templatize(s: str) -> str:
    s = re.sub(r"\{|\}", "", s)
    dates = 0

    def _date(m):
        nonlocal dates
        dates += 1
        return "{date}" if dates == 1 else "{due}"
    s = re.sub(r"\b\d{2}-\d{2}-\d{4}\b", _date, s)
    s = re.sub(r"\b\d{4}-\d{2}-\d{2}\b", "{isodate}", s)
    s = re.sub(r"\bQ[1-4] 20\d\d\b", "{quarter}", s)
    for i, (nl, en) in enumerate(zip(NL_MONTHS, EN_MONTHS)):
        s = re.sub(rf"\b{nl}\b", "{maand}", s, flags=re.I)
        s = re.sub(rf"\b{en}\b", "{month}", s, flags=re.I)

    def _money(m):
        pre = s[max(0, m.start() - 14):m.start()].lower()
        nl = "," in m.group(0)
        kind = "net" if "excl" in pre else ("vat" if re.search(r"(btw|vat)[^0-9]*\d*%\s*$", pre) else "total")
        return "{" + kind + ("_nl" if nl else "") + "}"
    s = re.sub(r"(?<![\d{])\d{1,3}(?:\.\d{3})*,\d{2}\b|(?<![\d{])\d+\.\d{2}\b", _money, s)
    s = re.sub(r"(?<![A-Za-z{])20(2[4-7])(?!\d)", "{year}", s)
    s = re.sub(r"(?<![\d{])\d{4,}(?!\d)", lambda m: "{n%d}" % len(m.group(0)), s)
    return s


def keyword_free(tpl: str, account: str) -> bool:
    low = tpl.lower()
    return not any(re.search(r"\b" + re.escape(k), low) for k in KEYWORDS[account])


# attribute-crossed generic phrasings (keyword-free, shared by every account)
CHANNEL_NL = ["SEPA Incasso", "Overboeking", "Incasso", "iDEAL betaling", "Betaling"]
CHANNEL_EN = ["Direct debit", "Transfer", "Card payment", "Payment"]
REF_NL = ["Factuur {n9}", "Factuurnr. {n6}", "Kenmerk {n8}", "Betalingskenmerk {n16}", "Ref. {n8}"]
REF_EN = ["Invoice {n9}", "Invoice no. {n6}", "Reference {n8}", "Ref {n8}", "Order {n8}"]
PER_NL = ["{maand} {year}", "periode {maand} {year}", "{date}", ""]
PER_EN = ["{month} {year}", "period {month} {year}", "{date}", ""]


def generic_phrasings():
    out = []
    for lang, ch, ref, per in (("nl", CHANNEL_NL, REF_NL, PER_NL), ("en", CHANNEL_EN, REF_EN, PER_EN)):
        for c, r, p in itertools.product(ch, ref, per):
            out.append({"text": " ".join(x for x in (c, r, p) if x), "language": lang,
                        "doc_type": "bank", "vat_rate": None, "generic": True})
    return out


KW_NOUNS = {
    "Rent Expense": (["Huur kantoorruimte", "Huur werkplek", "Servicekosten kantoor", "Huur flexplek"],
                     ["Office rent", "Desk rent", "Office lease", "Coworking membership"]),
    "Utilities Expense": (["Energie voorschot", "Stroom en gas", "Internet zakelijk", "Mobiel abonnement", "Water vastrecht"],
                          ["Energy advance", "Electricity and gas", "Business internet", "Mobile plan"]),
    "Software & Subscriptions Expense": (["Abonnement software", "Licentie", "Cloud opslag", "Hosting pakket"],
                                         ["Software subscription", "Licence renewal", "Cloud storage", "Hosting plan", "SaaS seats"]),
    "Travel & Transport Expense": (["Parkeren", "Treinreis", "Brandstof", "Taxirit", "Reiskosten"],
                                   ["Parking", "Train ticket", "Fuel", "Taxi ride", "Flight"]),
    "Office Supplies Expense": (["Kantoorartikelen", "Printpapier A4", "Toner cartridge", "Pennen en mappen", "Bureaustoel"],
                                ["Office supplies", "Printer paper", "Toner", "Monitor cable", "Desk chair"]),
    "Professional Services Expense": (["Advies uren", "Juridisch advies", "Administratie", "Jaarrekening", "Salarisadministratie"],
                                      ["Consulting hours", "Legal advice", "Accountant fee", "Payroll services"]),
    "General/Other Expense": (["Boodschappen kantoor", "Lunch team", "Koffie en thee", "Bloemen", "Verzekering"],
                              ["Team lunch", "Coffee and snacks", "Gift card", "Insurance premium", "Drinks"]),
}


def keyword_phrasings():
    out = {}
    for acc, (nl, en) in KW_NOUNS.items():
        rows = []
        for lang, nouns, ch, per in (("nl", nl, CHANNEL_NL, PER_NL), ("en", en, CHANNEL_EN, PER_EN)):
            for nn, c, pr in itertools.product(nouns, ch, per):
                rows.append({"text": " ".join(x for x in (c, nn, pr) if x), "language": lang})
        out[acc] = rows
    return out


def main():
    t = pd.read_csv(SRC / "transactions_4321.csv", dtype=str, keep_default_na=False)
    m = pd.read_csv(SRC / "metadata_4321.csv", dtype=str, keep_default_na=False)
    d = pd.concat([t, m.drop(columns=["true_account"])], axis=1)
    d["noise"] = d.noise_applied.apply(lambda x: set(x.split("|")) if x else set())
    easy = d[d.difficulty == "easy"]

    # vendors: easy rows only; account = majority account of the canonical vendor
    vendors = []
    for canon, g in easy.groupby("vendor_canonical", sort=True):
        acc = g.account.value_counts().idxmax()
        g = g[g.account == acc]
        clean_alias = g[~g.noise.apply(lambda n: "casing_variation" in n or "typo_char_swap_drop_dup" in n
                                       or "ocr_confusion" in n)].vendor
        aliases = sorted(set(clean_alias) | {canon})
        vendors.append({
            "canonical": canon, "account": acc, "archetype": g.archetype.value_counts().idxmax(),
            "aliases": aliases, "freq_4321": int(len(g)),
            "families": dict(sorted(Counter(f or "_none" for f in g.desc_family).items())),
            "languages": dict(sorted(Counter(g.language).items())),
            "vendor_unverified": bool((g.vendor_unverified == "true").any()),
        })

    # descriptions: per account -> per family templates, mined from easy rows w/o destructive noise
    desc = defaultdict(lambda: defaultdict(dict))
    for _, r in easy.iterrows():
        if r.noise & DESTRUCTIVE:
            continue
        tpl = templatize(r.description)
        key = (tpl, r.language, r.doc_type, r.vat_rate)
        desc[r.account][r.desc_family or "_none"][key] = 1
    descriptions = {}
    for acc in sorted(desc):
        fams = {}
        for fam in sorted(desc[acc]):
            fams[fam] = [{"text": k[0], "language": k[1], "doc_type": k[2], "vat_rate": k[3] or None,
                          "keyword_free": keyword_free(k[0], acc)} for k in sorted(desc[acc][fam])]
        descriptions[acc] = fams

    # hard / ambiguous cases, mined as whole rows (vendor + text + label + reason)
    hard = []
    seen = set()
    for _, r in d[d.difficulty != "easy"].iterrows():
        if r.noise & DESTRUCTIVE:
            continue
        tpl = templatize(r.description)
        k = (r.vendor_canonical, tpl, r.account)
        if k in seen:
            continue
        seen.add(k)
        hard.append({"vendor_canonical": r.vendor_canonical, "vendor": r.vendor, "text": tpl,
                     "account": r.account, "hard_case": r.hard_case, "difficulty": r.difficulty,
                     "escalate": r.escalate == "true", "archetype": r.archetype, "language": r.language,
                     "doc_type": r.doc_type, "vat_rate": r.vat_rate or None})

    OUT.mkdir(parents=True, exist_ok=True)
    gen = generic_phrasings()
    (OUT / "vendors.json").write_text(json.dumps(vendors, indent=1, ensure_ascii=False), encoding="utf-8")
    (OUT / "descriptions.json").write_text(json.dumps(descriptions, indent=1, ensure_ascii=False), encoding="utf-8")
    (OUT / "generic_phrasings.json").write_text(json.dumps(gen, indent=1, ensure_ascii=False), encoding="utf-8")
    (OUT / "keyword_phrasings.json").write_text(json.dumps(keyword_phrasings(), indent=1, ensure_ascii=False), encoding="utf-8")
    (OUT / "hard_cases.json").write_text(json.dumps(hard, indent=1, ensure_ascii=False), encoding="utf-8")

    for acc, fams in descriptions.items():
        n = sum(len(v) for v in fams.values())
        kf = sum(x["keyword_free"] for v in fams.values() for x in v)
        nv = sum(v["account"] == acc for v in vendors)
        print(f"{acc:34s} vendors={nv:4d} mined={n:4d} kw_free={kf/n:.2f} "
              f"with_generic={n+len(gen)} kw_free={(kf+len(gen))/(n+len(gen)):.2f}")
    print("hard templates", len(hard), Counter(h["hard_case"] for h in hard))


if __name__ == "__main__":
    main()
