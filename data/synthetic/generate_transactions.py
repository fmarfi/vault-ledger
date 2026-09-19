"""Seeded generator for synthetic Vault Ledger transactions (crew stage 3).

Run:  PYTHONPATH=src .venv/bin/python data/synthetic/generate_transactions.py \
          [--seed 1234] [--rows 4000] [--out-dir data/synthetic/generated]

Everything is sampled from data/synthetic/spec/generative_spec.yaml and the
corpus in data/synthetic/spec/corpus/*.json. Same seed + spec + corpus gives
byte-identical output. Synthetic-only: never quote accuracy on this data as
real-world accuracy. This script never writes labeled_transactions.csv or any
model path.

Outputs (out-dir):
  transactions_<seed>.csv          vendor,description,date,amount,paid,account
  metadata_<seed>.csv              per-row ground truth (row-aligned, id = row order)
  manifest_<seed>.json             seed, spec/corpus hashes, realised stats
  train_<seed>.csv val_<seed>.csv test_<seed>.csv   vendor,description,account ONLY
"""
import argparse
import bisect
import calendar
import csv
import datetime as dt
import hashlib
import json
import math
import random
import re
from collections import Counter, defaultdict
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
SPEC_PATH = HERE / "spec" / "generative_spec.yaml"
CORPUS_DIR = HERE / "spec" / "corpus"
DEFAULT_OUT = HERE / "generated"

SW = "Software & Subscriptions Expense"
TR = "Travel & Transport Expense"
OF = "Office Supplies Expense"
UT = "Utilities Expense"
GE = "General/Other Expense"
PR = "Professional Services Expense"
RE = "Rent Expense"

SPLITS = ("train", "val", "test")
META_COLS = ["id", "source", "archetype", "difficulty", "escalate", "noise_applied",
             "language", "vendor_unverified", "vendor_canonical", "true_account",
             "hard_case", "split"]
TX_COLS = ["vendor", "description", "date", "amount", "paid", "account"]

# Brand families that must share one split (in addition to alias collisions).
LINKS = [("Google", "Google Workspace"), ("Amazon.nl", "AWS"),
         ("Microsoft 365", "Microsoft Azure"), ("NS", "NS Flex"),
         ("Vodafone", "VodafoneZiggo"), ("VodafoneZiggo", "Ziggo"),
         ("Odido", "T-Mobile Thuis"), ("Nuon", "Vattenfall"),
         ("Budget Energie", "Budget Thuis")]

# ------------------------------------------------------------------ utilities


def norm(s):
    return re.sub(r"[^a-z0-9]+", " ", s.lower()).strip()


def sha256_bytes(b):
    return hashlib.sha256(b).hexdigest()


def sub_rng(seed, stage):
    return random.Random("vault-ledger-synth:%s:%s" % (seed, stage))


def wchoice(rng, items, weights):
    tot = float(sum(weights))
    x = rng.random() * tot
    acc = 0.0
    for it, w in zip(items, weights):
        acc += w
        if x < acc:
            return it
    return items[-1]


def clipped(rng, fn, lo, hi, tries=30):
    for _ in range(tries):
        v = fn()
        if lo <= v <= hi:
            return v
    return min(max(fn(), lo), hi)


def month_index(d):
    return (d.year - 2025) * 12 + d.month - 1


def add_months(y, m, k):
    t = y * 12 + (m - 1) + k
    return t // 12, t % 12 + 1


def mk_date(y, m, day):
    return dt.date(y, m, min(day, calendar.monthrange(y, m)[1]))


# ------------------------------------------------------------------ loading


def load_world():
    spec_bytes = SPEC_PATH.read_bytes()
    spec = yaml.safe_load(spec_bytes)
    h = hashlib.sha256()
    corpus = {}
    hard = None
    for p in sorted(CORPUS_DIR.glob("*.json")):
        b = p.read_bytes()
        h.update(p.name.encode() + b"\0" + b)
        j = json.loads(b)
        if p.stem == "hard_cases":
            hard = j
        else:
            corpus[j["account"]] = j
    return spec, corpus, hard, sha256_bytes(spec_bytes), h.hexdigest()


class Vendor(object):
    def __init__(self, name, aliases, archetype, unverified, account, sub, rank):
        self.name, self.aliases, self.archetype = name, aliases, archetype
        self.unverified, self.account, self.sub, self.rank = unverified, account, sub, rank
        self.gid = None


# archetype -> amount/description subtype, per account
TRAVEL_SUB = {}
for _a, _s in [("rail", "ov"), ("rail_intl", "ov"), ("ov_tap", "ov"), ("city_transit", "ov"),
               ("regional_transit", "ov"), ("coach", "ov"), ("ferry", "ov"),
               ("fuel", "fuel"), ("fuel_local", "fuel"), ("ev_charging", "fuel"),
               ("parking", "parking"),
               ("taxi", "taxi"), ("taxi_local", "taxi"), ("ride_share", "taxi"),
               ("scooter_share", "taxi"), ("bike_share", "taxi"), ("car_share", "taxi"),
               ("roadside", "taxi"),
               ("airline", "ovsub"), ("car_rental", "ovsub"), ("bike_subscription", "ovsub")]:
    TRAVEL_SUB[_a] = _s
UTIL_SUB = {"energy": "energy", "grid": "energy", "telecom": "telecom", "water": "water"}
PROF_SUB = {"accountant": "accountant", "accountantskantoor_generic": "accountant",
            "boekhouder_zzp": "accountant", "tax_advice": "accountant",
            "payroll_service": "accountant", "kvk": "kvk",
            "notaris": "notaris", "notariskantoor_generic": "notaris"}


def vendor_sub(account, archetype):
    if account == TR:
        return TRAVEL_SUB.get(archetype, "ov")
    if account == UT:
        return UTIL_SUB.get(archetype, "energy")
    if account == PR:
        return PROF_SUB.get(archetype, "consultant")
    return None


DESC_RE = {
    UT: [("water", r"water|riool|waterbedrijf|vitens"),
         ("telecom", r"mobiel|mobile|internet|glasvezel|telefo|\bsim\b|roaming|broadband|sip trunk|landline|televisie|bundel|bundle|fibre|data-"),
         ("energy", r"energ|stroom|electri|elektri|\bgas|voorschot|netbeheer|grid|meter|stadsverwarming|heating|\bode\b|jaarnota|afrekening|settlement|electricity|kwh|standing charge|creditnota")],
    TR: [("parking", r"park"),
         ("fuel", r"fuel|brandstof|tank|petrol|diesel|laad|charging|kwh|e10|euro 95|unleaded"),
         ("ovsub", r"flight|vlucht|vliegticket|airline|abonnement|season|subscription|lease|autohuur|car rental|klm|seat selection|omboeking|change fee"),
         ("taxi", r"taxi|uber|\brit\b|\bride\b|scooter|deelauto|car sharing|shuttle|ritten|wegenwacht|roadside|pech"),
         ("ov", r"trein|train|\bov\b|ov-|tram|\bbus|dagkaart|rail|ferry|veerboot|public transport|retour|return fare|chipkaart|opwaarderen|reis|travel|day pass|top-up|toll|tol en")],
    PR: [("kvk", r"kvk|handelsregister|chamber of commerce|trade register"),
         ("notaris", r"notari|\bakte\b|deed|statuten|articles of association|volmacht|power of attorney|aandelen"),
         ("accountant", r"accountant|accountancy|boekhou|bookkeep|jaarrekening|jaarwerk|btw|vat return|aangifte|tax return|loonadmin|payroll|honorarium|audit"),
         ("consultant", r"advies|advice|advis|consult|legal|juridisch|advocaat|attorney|solicitor|merk|trademark|vertaling|translation|coaching|compliance|strategy|uur\b|uren|hours|hourly|uurtarief|hr |gdpr|business plan|ondernemingsplan")],
}


def desc_sub(account, text):
    for key, rx in DESC_RE.get(account, []):
        if re.search(rx, text, re.I):
            return key
    return None


# ------------------------------------------------------------------ amounts


def sample_amount(rng, spec, account, sub=None, annual=False):
    a = spec["amounts"][account]
    if account == SW:
        p = a["params"]
        base = wchoice(rng, [m[0] for m in p["masses"]], [m[1] for m in p["masses"]])
        seats = wchoice(rng, list(p["seats"].keys()), list(p["seats"].values()))
        v = base * seats
        if annual:
            v *= p["annual_multiplier"]["factor"] * p["annual_multiplier"]["discount"]
        return v
    if account in (OF, GE):
        p = a["params"]
        return clipped(rng, lambda: rng.lognormvariate(p["mu"], p["sigma"]), *p["clip"])
    if account == TR:
        comps = {c["name"]: c for c in a["components"]}
        key = {"ov": "ns_ov_tap", "fuel": "fuel", "parking": "parking",
               "taxi": "taxi_ride_share", "ovsub": "ov_subscription_or_flight"}.get(sub)
        c = comps[key] if key else wchoice(rng, a["components"], [x["weight"] for x in a["components"]])
        return clipped(rng, lambda: rng.lognormvariate(c["mu"], c["sigma"]), *c["clip"])
    if account == UT:
        comps = {c["name"]: c for c in a["components"]}
        key = {"energy": "energy", "telecom": "telecom", "water": "water"}.get(sub)
        c = comps[key] if key else wchoice(rng, a["components"], [x["weight"] for x in a["components"]])
        if c["name"] == "telecom":
            return rng.choice(c["values"])
        if c["name"] == "energy_annual_settlement":
            return max(1.0, abs(rng.gauss(c["mu"], c["sd"])))  # credit notes emitted positive
        return clipped(rng, lambda: rng.lognormvariate(c["mu"], c["sigma"]), *c["clip"])
    if account == PR:
        comps = {c["name"]: c for c in a["components"]}
        key = {"accountant": "accountant", "consultant": "consultant_legal",
               "notaris": "notaris", "kvk": "kvk_registration"}.get(sub)
        c = comps[key] if key else wchoice(rng, a["components"], [x["weight"] for x in a["components"]])
        if c["family"] == "constant":
            return c["value"]
        v = clipped(rng, lambda: rng.lognormvariate(c["mu"], c["sigma"]), *c["clip"])
        rt = c.get("round_to")
        if rt and rng.random() < c.get("round_prob", 1.0):
            v = max(rt, round(v / rt) * rt)
        return v
    if account == RE:
        tiers = a["params"]["tiers"]
        t = wchoice(rng, tiers, [x["weight"] for x in tiers])
        lo, hi = t["value_range"]
        return round(rng.uniform(lo, hi) / 5.0) * 5.0
    raise KeyError(account)


def money(v):
    return round(max(float(v), 0.01) + 1e-9, 2)


# ------------------------------------------------------------------ text restamping

NL_M = ["januari", "februari", "maart", "april", "mei", "juni", "juli", "augustus",
        "september", "oktober", "november", "december"]
EN_M = ["January", "February", "March", "April", "May", "June", "July", "August",
        "September", "October", "November", "December"]
EN_ABBR = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
_month_rx = re.compile(r"\b(" + "|".join(NL_M + EN_M + EN_ABBR) + r")\b(\.?)( 20\d\d)?", re.I)


def _month_sub(d):
    def fn(m):
        w = m.group(1)
        low = w.lower()
        if low in NL_M:
            name = NL_M[d.month - 1]
        elif low in [x.lower() for x in EN_M]:
            name = EN_M[d.month - 1]
        else:
            name = EN_ABBR[d.month - 1]
        if w.isupper():
            name = name.upper()
        elif w[0].isupper():
            name = name[0].upper() + name[1:]
        yr = (" %d" % d.year) if m.group(3) else ""
        return name + m.group(2) + yr
    return fn


def restamp(text, d, rng, amount):
    """Re-time / re-number a corpus description so series and rows differ."""
    last = calendar.monthrange(d.year, d.month)[1]
    text = re.sub(r"\d{2}-\d{2}-\d{4} t/m \d{2}-\d{2}-\d{4}",
                  "01-%02d-%d t/m %02d-%02d-%d" % (d.month, d.year, last, d.month, d.year), text)
    text = _month_rx.sub(_month_sub(d), text)
    text = re.sub(r"\bQ[1-4] 20\d\d", "Q%d %d" % ((d.month - 1) // 3 + 1, d.year), text)
    text = re.sub(r"\b\d{2}/20\d\d\b", "%02d/%d" % (d.month, d.year), text)
    text = re.sub(r"\b\d{2}-\d{2}-\d{4}\b",
                  lambda m: "%02d-%02d-%d" % (rng.randint(1, last), d.month, d.year), text)
    text = re.sub(r"\b(INV-|F)?(20\d\d)([-/])(\d{4,5})\b",
                  lambda m: "%s%d%s%0*d" % (m.group(1) or "", d.year, m.group(3), len(m.group(4)),
                                            rng.randint(1, 10 ** len(m.group(4)) - 1)), text)
    text = re.sub(r"(?<![\d.,-])\d{6,}(?![\d.,])",
                  lambda m: "".join(str(rng.randint(1 if i == 0 else 0, 9)) for i in range(len(m.group(0)))),
                  text)

    def amt(m):
        s = m.group(2)
        comma = re.search(r"[.,]\d{2}$", s).group(0)[0] == ","
        out = "%.2f" % amount
        return m.group(1) + (out.replace(".", ",") if comma else out)
    text = re.sub(r"((?:EUR |Total due |Total |Amount due |Amount |Bedrag |Maandbedrag )~?)(\d[\d.,]*[.,]\d{2})(?![\d/]|\s*(?:per|/))",
                  amt, text)
    return text


# ------------------------------------------------------------------ noise

ABBR = [(r"\bfactuur\b", "fact."), (r"\binvoice\b", "inv."), (r"\bmaandbedrag\b", "mnd bedrag"),
        (r"\bmaandelijks\b", "mnd"), (r"\bmaand\b", "mnd"), (r"\bmonthly\b", "mthly"),
        (r"\babonnement\b", "abon."), (r"\bsubscription\b", "subscr."), (r"\bbetaling\b", "bet."),
        (r"\bkwartaal\b", "kw."), (r"\bperiode\b", "per."), (r"\bkenmerk\b", "kenm."),
        (r"\bnummer\b", "nr."), (r"\bservices\b", "svcs"),
        (r"\bpayment\b", "pmt"), (r"\bperiod\b", "per."), (r"\bmonths?\b", "mo."),
        (r"\bannual\b", "ann."), (r"\bjaarlijkse?\b", "jaarl."), (r"\bhours\b", "hrs"),
        (r"\buren\b", "u."), (r"\bcustomer\b", "cust."), (r"\bklantnummer\b", "klantnr"),
        (r"\breference\b", "ref."), (r"\bquarterly\b", "qtrly"), (r"\bstatement\b", "stmt"),
        (r"\bservice\b", "svc"), (r"\bdienstverlening\b", "dienstverl."),
        (r"\bregistration\b", "reg."), (r"\bsession\b", "sess."), (r"\bticket\b", "tkt"),
        (r"\btotal\b", "tot."), (r"\bkosten\b", "kst."), (r"\bbetreft\b", "betr."),
        (r"\bwith\b", "w/"), (r"\band\b", "&"), (r"\ben\b", "&"), (r"\bper\b", "p.")]
MIX_EN = ["invoice", "monthly", "payment", "period", "ref"]
MIX_NL = ["factuur", "maandelijks", "betaling", "periode", "kenmerk"]
OCR = [("0", "O"), ("O", "0"), ("1", "l"), ("l", "1"), ("5", "S"), ("S", "5"), ("rn", "m"), ("m", "rn")]
PREFIXES = ["BEA NR:%04d", "SEPA Incasso algemeen doorlopend", "iDEAL", "Betaalautomaat",
            "SEPA Overboeking", "Pinbetaling", "Betaling"]
SUFFIXES = ["- SEPA Incasso", "Betaalautomaat", "via iDEAL", "SEPA Overboeking"]
TERMS = ["Term %d", "POS %d", "Kassa %d", "Pas %03d", "#%d", "Terminal %d"]
LEGAL = ["B.V.", "BV", "Holding", "Inc"]
GENERIC_FALLBACK = ["Factuur 2026-0142", "Betaling", "Invoice", "Diversen", "Overboeking"]


def op_typo(s, rng):
    idx = [i for i, c in enumerate(s) if c.isalpha()]
    if len(idx) < 4:
        return None
    i = rng.choice(idx)
    k = rng.randint(0, 2)
    if k == 0 and i + 1 < len(s):
        return s[:i] + s[i + 1] + s[i] + s[i + 2:]
    if k == 1:
        return s[:i] + s[i + 1:]
    return s[:i] + s[i] + s[i:]


def op_abbrev(s, rng):
    cands = [(rx, rep) for rx, rep in ABBR if re.search(rx, s, re.I)]
    if not cands:
        return None
    rx, rep = rng.choice(cands)
    return re.sub(rx, rep, s, count=1, flags=re.I)


def op_ocr(s, rng):
    cands = [(a, b) for a, b in OCR if a in s]
    if not cands:
        return None
    a, b = rng.choice(cands)
    pos = [m.start() for m in re.finditer(re.escape(a), s)]
    i = rng.choice(pos)
    return s[:i] + b + s[i + len(a):]


def op_case(s, mode):
    return s.upper() if mode == "UPPER" else s.lower() if mode == "lower" else s.title()


def apply_noise(rng, spec, vendor, desc, lang, recurring, generic_texts):
    """Return (vendor, desc, language, [ops actually applied])."""
    nm = spec["noise_model"]
    trig = [o["name"] for o in nm["operations"] if rng.random() < o["rate"]]
    if len(trig) > nm["max_ops_per_row"]:
        keep = set(rng.sample(trig, nm["max_ops_per_row"]))
        trig = [t for t in trig if t in keep]
    ops = {o["name"]: o for o in nm["operations"]}
    applied = []
    language = lang
    if "missing_or_generic_description" in trig:
        desc = rng.choice(generic_texts)
        applied.append("missing_or_generic_description")
    if "nl_en_mix_in_one_row" in trig:
        frag = rng.choice(MIX_EN if lang == "nl" else MIX_NL)
        desc = ("%s - %s" % (frag, desc)) if rng.random() < 0.5 else ("%s (%s)" % (desc, frag))
        language = "mixed"
        applied.append("nl_en_mix_in_one_row")
    for name, fn in (("abbreviation_nl_en", op_abbrev), ("typo_char_swap_drop_dup", op_typo),
                     ("ocr_confusion", op_ocr)):
        if name in trig:
            r = fn(desc, rng)
            if r is not None and r != desc:
                desc = r
                applied.append(name)
                if name != "abbreviation_nl_en" and rng.random() < 0.3:
                    rv = fn(vendor, rng)
                    if rv:
                        vendor = rv
    if "truncated_description" in trig:
        lo, hi = ops["truncated_description"]["keep_chars"]
        keep = rng.randint(lo, hi)
        if len(desc) <= keep and len(desc) >= 14:
            keep = int(len(desc) * 0.75)
        if len(desc) > keep:
            desc = desc[:keep].rstrip()
            applied.append("truncated_description")
    if "casing_variation" in trig:
        modes = ops["casing_variation"]["modes"]
        mode = wchoice(rng, list(modes.keys()), list(modes.values()))
        desc = op_case(desc, mode)
        if mode != "Title" and rng.random() < 0.5:
            vendor = op_case(vendor, mode)
        applied.append("casing_variation")
    if "bank_prefix_suffix" in trig:
        w_inc = 0.6 if recurring else 0.15
        pref = wchoice(rng, PREFIXES, [w_inc if "Incasso" in p else (1 - w_inc) / 3.0 for p in PREFIXES])
        if "%" in pref:
            pref = pref % rng.randint(1000, 9999)
        if rng.random() < 0.7:
            desc = pref + " " + desc
        else:
            desc = desc + " " + rng.choice(SUFFIXES)
        applied.append("bank_prefix_suffix")
    if "store_terminal_code" in trig:
        desc = desc + " " + rng.choice(TERMS) % rng.randint(1, 99999)
        applied.append("store_terminal_code")
    if "vendor_legal_suffix_variation" in trig:
        m = re.search(r"\s(B\.V\.|BV|Holding|Inc|Ltd)$", vendor)
        base = vendor[:m.start()] if m else vendor
        new = rng.choice([x for x in LEGAL if not m or x != m.group(1)])
        vendor = base + " " + new
        applied.append("vendor_legal_suffix_variation")
    return vendor, desc, language, applied


# ------------------------------------------------------------------ vendors, groups


def build_vendors(corpus, hard):
    vendors = {}          # account -> [Vendor]
    for acct, j in corpus.items():
        vendors[acct] = [Vendor(v["name"], v["aliases"], v["archetype"], bool(v.get("unverified")),
                                acct, vendor_sub(acct, v["archetype"]), i)
                         for i, v in enumerate(j["vendors"])]
    hard_v = {v["name"]: Vendor(v["name"], v["aliases"], v["archetype"], bool(v.get("unverified")),
                                "hard", None, i) for i, v in enumerate(hard["vendors"])}
    allv = [v for a in sorted(vendors) for v in vendors[a]] + [hard_v[k] for k in hard_v]
    parent = list(range(len(allv)))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[max(ra, rb)] = min(ra, rb)
    seen = {}
    for i, v in enumerate(allv):
        for s in [v.name] + v.aliases:
            n = norm(s)
            if n in seen:
                union(i, seen[n])
            else:
                seen[n] = i
    by_name = {}
    for i, v in enumerate(allv):
        by_name.setdefault(v.name, i)
    for a, b in LINKS:
        if a in by_name and b in by_name:
            union(by_name[a], by_name[b])
    for i, v in enumerate(allv):
        v.gid = find(i)
    return vendors, hard_v, allv, by_name


def vendor_weights(spec, account, pool):
    """Per-vendor sampling weight: spec sub-type weight x Zipf within sub-type pool,
    with the top-10 share capped (spec gate) and one-off tail removed."""
    s = spec["vendor_frequency"]["exponent_s"]
    tail_frac = spec["vendor_frequency"]["one_off_tail_fraction"]
    cap = spec["vendor_frequency"]["top10_vendor_share_max"] - 0.05
    if account == UT:
        sw = {"energy": 0.5, "telecom": 0.4, "water": 0.1}
    elif account == TR:
        sw = {"ov": 0.40, "fuel": 0.20, "parking": 0.20, "taxi": 0.10, "ovsub": 0.10}
    elif account == PR:
        sw = {"accountant": 0.35, "consultant": 0.45, "notaris": 0.12, "kvk": 0.08}
    else:
        sw = {None: 1.0}
    pools = defaultdict(list)
    for v in pool:
        pools[v.sub].append(v)
    tail = []
    w = {}
    live = {k: p for k, p in pools.items() if k in sw and p}
    tot = sum(sw[k] for k in live)
    for k in sorted(live, key=str):
        p = live[k]
        nt = int(round(tail_frac * len(p))) if len(p) >= 4 else 0
        head, tl = p[:len(p) - nt], p[len(p) - nt:]
        tail.extend(tl)
        z = [(r + 1) ** (-s) for r in range(len(head))]
        if account == TR and k == "ovsub":
            bike = [i for i, v in enumerate(head) if v.archetype == "bike_subscription"]
            if bike:
                z[bike[0]] = sum(z) - z[bike[0]]
        zs = sum(z)
        for v, zz in zip(head, z):
            w[v.name] = sw[k] / tot * zz / zs
    # Enforce the spec gate top-10 share < cap by iteratively flattening the head. A pure
    # Zipf(s=1.1) over ~40-60 vendors puts ~65% of mass in the top 10, so the gate and the
    # exponent cannot both hold; the gate wins and the head is flattened (see CREW.md).
    for _ in range(400):
        order = sorted(w, key=lambda n: (-w[n], n))
        top = order[:10]
        A = sum(w[n] for n in top)
        B = sum(w.values()) - A
        if B <= 0 or A / (A + B) <= cap:
            break
        f = max(0.5, cap * B / ((1 - cap) * A))
        for n in top:
            w[n] *= f
    return w, tail


# ------------------------------------------------------------------ series building


def contracts(k, cap):
    out, rem = [], k
    while rem > 0:
        out.append(min(rem, cap))
        rem -= out[-1]
    return out


def rand_day(rng, account):
    for _ in range(10):
        d = dt.date(2025, 1, 1) + dt.timedelta(days=rng.randint(0, (dt.date(2026, 8, 31) - dt.date(2025, 1, 1)).days))
        if account in (SW, UT, RE) or d.weekday() < 5 or rng.random() < 0.15:
            return d
    return d


def vendor_rows(rng, spec, account, v, k, desc_pool, tail_row):
    """Pre-noise rows for k transactions of vendor v: dict(date, amount, desc, recurring)."""
    rows = []
    compat = [d for d in desc_pool if desc_sub(account, d["text"]) in (None, v.sub)] or desc_pool
    prof_style = None
    if account == SW:
        if k == 1:
            style = "irregular"
        elif k <= 4:
            style = wchoice(rng, ["monthly", "annual", "irregular"], [0.75, 0.15, 0.10])
        else:
            style = wchoice(rng, ["monthly", "irregular"], [0.88, 0.12])
    elif account == RE:
        style = "irregular" if tail_row or rng.random() < 0.02 else "monthly"
    elif account == UT:
        style = "monthly" if k > 1 else "irregular"
    elif account == PR:
        if v.sub == "kvk":
            style = "annual"
        elif v.sub == "accountant" and k > 1:
            style = wchoice(rng, ["monthly", "quarterly", "irregular"], [0.30, 0.30, 0.40])
        else:
            style = "irregular"
    elif account == TR and v.archetype == "bike_subscription":
        style = "monthly"
    else:
        style = "irregular"

    def emit(d, amount, primary, recurring):
        if recurring and primary and rng.random() < 0.65:
            raw = primary
        else:
            raw = rng.choice(compat)
        text = restamp(raw["text"], d, rng, amount)
        rows.append({"date": d, "amount": money(amount), "desc": text, "lang": raw["lang"],
                     "recurring": recurring})

    if style == "irregular":
        for _ in range(k):
            d = rand_day(rng, account)
            sub = v.sub
            amt = sample_amount(rng, spec, account, sub)
            if account == UT and v.sub == "energy":
                pass
            emit(d, amt, None, False)
        return rows
    cap = {"monthly": 20, "quarterly": 6, "annual": 2}[style]
    step = {"monthly": 1, "quarterly": 3, "annual": 12}[style]
    for L in contracts(k, cap):
        span = (L - 1) * step
        start = rng.randint(0, max(0, 19 - span))
        if style == "annual":
            day = rng.randint(1, 28)
        elif account == RE:
            day = 1
        elif account == UT:
            day = rng.choice([1, 15, 25] if v.sub == "energy" else [3, 10, 20, 28])
        else:
            day = rng.randint(1, 28)
        primary = rng.choice(compat)
        base = sample_amount(rng, spec, account, v.sub, annual=(style == "annual" and account == SW))
        idx_step = (rng.random() < 0.3 and account == RE)
        idx_mult = 1 + rng.uniform(0.02, 0.04)
        for j in range(L):
            y, m = add_months(2025, 1, start + j * step)
            d = mk_date(y, m, day)
            amt = base
            if account == UT and v.sub == "energy":
                up = 1.30 if (m >= 10 or m <= 3) else 0.85
                amt = base * up * (1 + rng.uniform(-0.05, 0.05))
            if idx_step and y == 2026:
                amt = base * idx_mult
            emit(d, amt, primary, True)
    return rows


# ------------------------------------------------------------------ hard rows


def alloc(rng, total, weights):
    raw = [total * w / sum(weights) for w in weights]
    n = [int(x) for x in raw]
    order = sorted(range(len(raw)), key=lambda i: (-(raw[i] - n[i]), rng.random()))
    for i in order[:total - sum(n)]:
        n[i] += 1
    return n


def plan_hard(rng, spec, hard, N):
    H = int(round(spec["difficulty_mix"]["hard_ambiguous"] * N))
    cases = spec["hard_cases"]["cases"]
    counts = alloc(rng, H, [c["weight"] for c in cases])
    by_case = defaultdict(list)
    for d in hard["descriptions"]:
        by_case[d["case"]].append(d)
    plan = []
    for c, n in zip(cases, counts):
        pool = by_case[c["id"]]
        for _ in range(n):
            plan.append(rng.choice(pool))
    rng.shuffle(plan)
    return plan


# ------------------------------------------------------------------ splitting


def assign_splits(spec, row_groups):
    """row_groups: list of (gid, account_label). Greedy stratified vendor-group assignment."""
    fr = spec["splits"]["fractions"]
    target = [fr["train"], fr["val"], fr["test"]]
    g_acct = defaultdict(Counter)
    for gid, a in row_groups:
        g_acct[gid][a] += 1
    acct_tot = Counter(a for _, a in row_groups)
    assigned = {a: [0, 0, 0] for a in acct_tot}
    gsplit = {}
    order = sorted(g_acct, key=lambda g: (-sum(g_acct[g].values()), g))
    for g in order:
        best, bs = 0, None
        for s in range(3):
            sc = sum(n * (target[s] * acct_tot[a] - assigned[a][s]) / acct_tot[a]
                     for a, n in g_acct[g].items())
            if bs is None or sc > bs + 1e-12:
                best, bs = s, sc
        gsplit[g] = best
        for a, n in g_acct[g].items():
            assigned[a][best] += n
    # guarantee: every account has at least one vendor group in every split
    for _ in range(50):
        moved = False
        for a in sorted(acct_tot):
            groups = defaultdict(list)
            for g in g_acct:
                if a in g_acct[g]:
                    groups[gsplit[g]].append(g)
            for s in range(3):
                if groups[s]:
                    continue
                donors = [t for t in range(3) if len(groups[t]) >= 2]
                if not donors:
                    continue
                donor = max(donors, key=lambda t: len(groups[t]))
                cand = sorted(groups[donor], key=lambda g: (g_acct[g][a], g))
                g = cand[0]
                gsplit[g] = s
                moved = True
                break
        if not moved:
            break
    return {g: SPLITS[s] for g, s in gsplit.items()}


# ------------------------------------------------------------------ main generation


def generate(seed, N, spec=None, corpus=None, hard=None):
    if spec is None:
        spec, corpus, hard, _, _ = load_world()
    vendors, hard_v, allv, by_name = build_vendors(corpus, hard)
    name_index = {v.name: v for v in allv}
    prior = spec["class_prior"]["values"]
    accounts = sorted(prior)
    generic_texts = [d["text"] for d in hard["descriptions"] if d["case"] == "generic_description"
                     and len(d["text"]) > 1] or GENERIC_FALLBACK

    # --- hard rows plan and clear quotas
    r_plan = sub_rng(seed, "hard-plan")
    hplan = plan_hard(r_plan, spec, hard, N)
    hard_label = Counter()
    hard_items = []
    r_hard = sub_rng(seed, "hard-rows")
    for d in hplan:
        true_acct = d["true_account"]
        if d["case"] == "generic_description":
            true_acct = wchoice(r_hard, accounts, [prior[a] for a in accounts])
        label = GE if d["escalate"] else true_acct
        hard_label[label] += 1
        hard_items.append((d, true_acct, label))
    H = len(hard_items)
    raw = [max(0.0, prior[a] * N - hard_label[a]) for a in accounts]
    quota = alloc(sub_rng(seed, "quota"), N - H, raw)

    rows = []   # dict per row

    # --- clear rows
    for a, qa in zip(accounts, quota):
        rng = sub_rng(seed, "clear:" + a)
        pool = vendors[a]
        w, tail = vendor_weights(spec, a, pool)
        n_tail = min(len(tail), qa // 4)
        rng.shuffle(tail)
        tail_used = tail[:n_tail]
        counts = Counter({v.name: 1 for v in tail_used})
        names = sorted(w, key=lambda n: n)
        # stratified allocation: floor of expected count, remainder drawn from the fractional
        # parts (keeps realised shares close to the weights, so the top-10 gate is not
        # broken by multinomial noise while the draw stays seeded and random).
        n_head = qa - n_tail
        tw = sum(w[n] for n in names)
        exp = {n: w[n] / tw * n_head for n in names}
        for n in names:
            counts[n] += int(exp[n])
        rem = n_head - sum(int(exp[n]) for n in names)
        fr = [exp[n] - int(exp[n]) for n in names]
        for _ in range(rem):
            j = wchoice(rng, list(range(len(names))), fr)
            counts[names[j]] += 1
            fr[j] = 0.0
            if sum(fr) <= 0:
                fr = [1.0] * len(names)
        by_vendor = {v.name: v for v in pool}
        descs = corpus[a]["descriptions"]
        tail_names = set(v.name for v in tail_used)
        for name in sorted(counts):
            v = by_vendor[name]
            vr = sub_rng(seed, "vendor:%s:%s" % (a, name))
            for r in vendor_rows(vr, spec, a, v, counts[name], descs, name in tail_names):
                r.update(vendor=v, label=a, true_account=a, difficulty="easy", escalate=False,
                         hard_case="")
                rows.append(r)

    # --- hard rows
    for d, true_acct, label in hard_items:
        gen_key = d["case"]
        if d["case"] == "generic_description":
            pool = vendors[true_acct]
            _, tail = vendor_weights(spec, true_acct, pool)
            v = r_hard.choice(tail or pool)
        else:
            v = name_index.get(d["vendor"])
            if v is None:
                v = Vendor(d["vendor"], [], "unlisted", True, "hard", None, 0)
                v.gid = -abs(hash_int(d["vendor"]))
        date = rand_day(r_hard, GE)
        if d["case"] == "generic_description":
            amt_acct = true_acct
        else:
            amt_acct = GE if d["escalate"] else true_acct
        sub = "fuel" if (d["case"] == "fuel_station_shop" and amt_acct == TR) else None
        if amt_acct == RE:
            amt = sample_amount(r_hard, spec, RE)
        else:
            amt = sample_amount(r_hard, spec, amt_acct, sub)
        text = restamp(d["text"], date, r_hard, amt)
        rows.append({"date": date, "amount": money(amt), "desc": text, "lang": d["lang"],
                     "recurring": False, "vendor": v, "label": label, "true_account": true_acct,
                     "difficulty": "ambiguous" if d["escalate"] else "hard",
                     "escalate": bool(d["escalate"]), "hard_case": d["case"]})

    # --- finalize: sort, noise, paid, vendor string
    rows.sort(key=lambda r: (r["date"], r["label"], r["vendor"].name, r["desc"], r["amount"]))
    pp = spec["paid_unpaid"]
    out = []
    seen_keys = set()
    repairs = 0
    for i, r in enumerate(rows):
        rng = sub_rng(seed, "row:%d" % i)
        v = r["vendor"]
        vs = v.name if rng.random() < 0.45 or not v.aliases else rng.choice(v.aliases)
        vs, desc, language, applied = apply_noise(rng, spec, vs, r["desc"], r["lang"],
                                                  r["recurring"], generic_texts)
        paid = rng.random() < pp["paid_at_document_date_fraction"][r["true_account"]]
        if paid and rng.random() < 0.25:
            lang = "nl" if r["lang"] == "nl" else "en"
            desc = desc + " " + rng.choice(pp["paid_markers"][lang])
        elif not paid and rng.random() < 0.35:
            terms = wchoice(rng, list(pp["payment_terms_days"].keys()), list(pp["payment_terms_days"].values()))
            due = r["date"] + dt.timedelta(days=terms)
            if r["lang"] == "nl":
                desc = desc + " Te betalen voor %s" % due.strftime("%d-%m-%Y")
            else:
                desc = desc + " Payable within %d days" % terms
        desc = desc.strip()
        key = norm(vs) + "|" + norm(desc)
        if key in seen_keys:
            repairs += 1
            tag = r["date"].strftime("%m/%Y") if rng.random() < 0.5 else r["date"].strftime("%d-%m")
            desc = desc + (" " + tag)
            key = norm(vs) + "|" + norm(desc)
            while key in seen_keys:
                desc = desc + " %d" % rng.randint(10, 99)
                key = norm(vs) + "|" + norm(desc)
        seen_keys.add(key)
        out.append({"id": "s%s-%05d" % (seed, i), "vendor": vs, "description": desc,
                    "date": r["date"].isoformat(), "amount": r["amount"], "paid": paid,
                    "account": r["label"], "meta": {
                        "archetype": v.archetype, "difficulty": r["difficulty"],
                        "escalate": r["escalate"], "noise_applied": "|".join(applied),
                        "language": language, "vendor_unverified": v.unverified,
                        "vendor_canonical": v.name, "true_account": r["true_account"],
                        "hard_case": r["hard_case"], "gid": v.gid}})

    # --- vendor-disjoint splits
    gsplit = assign_splits(spec, [(o["meta"]["gid"], o["account"]) for o in out])
    for o in out:
        o["split"] = gsplit[o["meta"]["gid"]]
    # noisy vendor strings must not collide across splits: revert offenders to a clean alias
    seen = defaultdict(set)
    for o in out:
        seen[norm(o["vendor"])].add(o["split"])
    all_by_gid = defaultdict(list)
    for v in allv:
        all_by_gid[v.gid].append(v)
    for o in out:
        if len(seen[norm(o["vendor"])]) > 1:
            v = name_index.get(o["meta"]["vendor_canonical"])
            o["vendor"] = v.name if v else o["vendor"]
    generate.dedup_repairs = repairs
    return out, vendors


def hash_int(s):
    return int(hashlib.sha256(s.encode()).hexdigest()[:8], 16)


# ------------------------------------------------------------------ output


def write_csv(path, cols, rows):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(cols)
        for r in rows:
            w.writerow(r)


def stats(out, spec):
    N = len(out)
    st = {"rows": N}
    st["rows_per_split"] = {s: sum(1 for o in out if o["split"] == s) for s in SPLITS}
    st["row_fraction_per_split"] = {s: round(st["rows_per_split"][s] / N, 4) for s in SPLITS}
    accts = sorted(spec["class_prior"]["values"])
    st["rows_per_account"] = {a: sum(1 for o in out if o["account"] == a) for a in accts}
    st["account_fraction"] = {a: round(st["rows_per_account"][a] / N, 4) for a in accts}
    st["rows_per_account_per_split"] = {a: {s: sum(1 for o in out if o["account"] == a and o["split"] == s)
                                            for s in SPLITS} for a in accts}
    st["vendor_groups_per_account_per_split"] = {
        a: {s: len(set(o["meta"]["gid"] for o in out if o["account"] == a and o["split"] == s))
            for s in SPLITS} for a in accts}
    st["difficulty"] = {d: round(sum(1 for o in out if o["meta"]["difficulty"] == d) / N, 4)
                        for d in ("easy", "hard", "ambiguous")}
    st["escalate_fraction_of_all"] = round(sum(1 for o in out if o["meta"]["escalate"]) / N, 4)
    nh = sum(1 for o in out if o["meta"]["difficulty"] != "easy")
    st["escalate_fraction_of_hard"] = round(sum(1 for o in out if o["meta"]["escalate"]) / max(1, nh), 4)
    st["language"] = {l: round(sum(1 for o in out if o["meta"]["language"] == l) / N, 4)
                      for l in ("en", "nl", "mixed")}
    nz = Counter()
    for o in out:
        for op in filter(None, o["meta"]["noise_applied"].split("|")):
            nz[op] += 1
    st["noise_realised_rate"] = {k: round(nz[k] / N, 4) for k in sorted(nz)}
    st["paid_rate"] = {a: round(sum(1 for o in out if o["account"] == a and o["paid"]) /
                                max(1, st["rows_per_account"][a]), 3) for a in accts}
    top10 = {}
    for a in accts:
        c = Counter(o["meta"]["vendor_canonical"] for o in out if o["account"] == a and o["meta"]["difficulty"] == "easy")
        tot = sum(c.values())
        top10[a] = round(sum(x for _, x in c.most_common(10)) / max(1, tot), 3)
    st["top10_vendor_share_clear_rows"] = top10
    st["distinct_vendor_strings_per_account"] = {a: len(set(norm(o["vendor"]) for o in out if o["account"] == a)) for a in accts}
    keys = [norm(o["vendor"]) + "|" + norm(o["description"]) for o in out]
    st["dup_rate_vendor_description"] = round(1 - len(set(keys)) / N, 4)
    keys2 = [k + "|" + o["date"] + "|" + str(o["amount"]) for k, o in zip(keys, out)]
    st["dup_rate_vendor_description_date_amount"] = round(1 - len(set(keys2)) / N, 4)
    vs = defaultdict(set)
    for o in out:
        vs[norm(o["vendor"])].add(o["split"])
    st["vendor_strings_in_multiple_splits"] = sum(1 for s in vs.values() if len(s) > 1)
    gs = defaultdict(set)
    for o in out:
        gs[o["meta"]["gid"]].add(o["split"])
    st["vendor_groups_in_multiple_splits"] = sum(1 for s in gs.values() if len(s) > 1)
    return st


def run(seed, rows, out_dir):
    spec, corpus, hard, spec_hash, corpus_hash = load_world()
    out, _ = generate(seed, rows, spec, corpus, hard)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    write_csv(out_dir / ("transactions_%s.csv" % seed), TX_COLS,
              [[o["vendor"], o["description"], o["date"], "%.2f" % o["amount"], o["paid"], o["account"]]
               for o in out])
    write_csv(out_dir / ("metadata_%s.csv" % seed), META_COLS,
              [[o["id"], "synthetic", o["meta"]["archetype"], o["meta"]["difficulty"],
                str(o["meta"]["escalate"]).lower(), o["meta"]["noise_applied"], o["meta"]["language"],
                str(o["meta"]["vendor_unverified"]).lower(), o["meta"]["vendor_canonical"],
                o["meta"]["true_account"], o["meta"]["hard_case"], o["split"]] for o in out])
    for s in SPLITS:
        write_csv(out_dir / ("%s_%s.csv" % (s, seed)), ["vendor", "description", "account"],
                  [[o["vendor"], o["description"], o["account"]] for o in out if o["split"] == s])
    manifest = {"seed": seed, "rows_requested": rows,
                "spec_sha256": spec_hash, "corpus_sha256": corpus_hash,
                "generator_sha256": sha256_bytes(Path(__file__).read_bytes()),
                "spec_path": "data/synthetic/spec/generative_spec.yaml",
                "source": "synthetic",
                "notes": ["escalate rows carry account=General/Other Expense and escalate=true in metadata",
                          "metadata is row-aligned with transactions and never a feature",
                          "synthetic-only: do not quote accuracy on this data as real-world accuracy"],
                "stats": dict(stats(out, spec), dedup_repairs=generate.dedup_repairs)}
    (out_dir / ("manifest_%s.json" % seed)).write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    return manifest


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=1234)
    ap.add_argument("--rows", type=int, default=None)
    ap.add_argument("--out-dir", default=str(DEFAULT_OUT))
    a = ap.parse_args()
    rows = a.rows
    if rows is None:
        rows = yaml.safe_load(SPEC_PATH.read_text())["meta"]["target_rows"]
    m = run(a.seed, rows, a.out_dir)
    print(json.dumps(m["stats"], indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
