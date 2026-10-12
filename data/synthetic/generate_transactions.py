"""Seeded generator for synthetic Vault Ledger transactions (crew stage 3, revision 2).

Run:  PYTHONPATH=src .venv/bin/python data/synthetic/generate_transactions.py \
          [--seed 1234] [--rows 4000] [--out-dir data/synthetic/generated]

Everything is sampled from data/synthetic/spec/generative_spec.yaml and the corpus in
data/synthetic/spec/corpus/*.json. Same seed + spec + corpus gives byte-identical output.
Synthetic-only: never quote accuracy on this data as real-world accuracy. This script never
writes labeled_transactions.csv or any model path.

Design (revision 1): a vendor's ARCHETYPE (corpus `archetypes`) fixes its description family
(`pools`), price model, VAT treatment and document-type mix. Description, amount, BTW text and
payment text are all generated from that one archetype, so vendor and description agree on
every easy row. Only hard rows (generic_description, vendor_description_disagree, brand cases)
may break that link, and they are labelled as such.

Outputs (out-dir):
  transactions_<seed>.csv          vendor,description,date,amount,paid,account
  metadata_<seed>.csv              per-row ground truth (row-aligned, id = row order)
  manifest_<seed>.json             seed, hashes, realised stats
  train_<seed>.csv val_<seed>.csv test_<seed>.csv   vendor,description,account ONLY
"""
import argparse
import csv
import datetime as dt
import hashlib
import json
import math
import random
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from gen_helpers import (abbrev_candidates, add_months, chi2_sf_even,  # noqa: E402
                         fmt_num, invoice_date, last_bdays, legal_form, mk_date, money,
                         month_name, multinomial, op_abbrev, op_case, op_ocr, op_typo,
                         prev_month, receipt_date, roll_bd, wchoice, zipf_mle, zm_weights)

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
META_COLS = ["id", "source", "archetype", "difficulty", "escalate", "noise_applied", "language",
             "vendor_unverified", "vendor_canonical", "true_account", "hard_case", "split",
             "desc_family", "doc_type", "vat_rate", "net_amount"]
TX_COLS = ["vendor", "description", "date", "amount", "paid", "account"]

LINKS = [("Google", "Google Workspace"), ("Amazon.nl", "AWS"),
         ("Microsoft 365", "Microsoft Azure"), ("NS", "NS Flex"),
         ("Vodafone", "VodafoneZiggo"), ("VodafoneZiggo", "Ziggo"),
         ("Odido", "T-Mobile Thuis"), ("Nuon", "Vattenfall"),
         ("Budget Energie", "Budget Thuis")]

HOURS = [1, 1.5, 2, 2.5, 3, 4, 5, 6, 8, 10, 12, 16, 20, 24, 32, 40]
CITIES = ["Amsterdam", "Rotterdam", "Utrecht", "Den Haag", "Eindhoven", "Groningen", "Arnhem",
          "Breda", "Zwolle", "Leiden", "Haarlem", "Nijmegen"]
STATIONS = ["Utrecht Centraal", "Amsterdam Zuid", "Rotterdam Centraal", "Den Haag Centraal",
            "Eindhoven Centraal", "Schiphol Airport", "Arnhem Centraal", "Zwolle", "Breda",
            "Groningen", "Leiden Centraal", "Amersfoort Centraal"]
AIRPORTS = ["Amsterdam - London", "Amsterdam - Berlin", "Rotterdam - Barcelona", "Amsterdam - Madrid",
            "Eindhoven - Milan", "Amsterdam - Paris", "Amsterdam - Copenhagen", "Amsterdam - Lisbon"]
DOMAIN_WORDS = ["studio", "atelier", "werk", "bureau", "denk", "bouw", "groen", "blauw", "oost",
                "west", "noord", "zuid", "ambacht", "kompas", "vonk", "lijn", "hout", "steen"]
GENERIC_FALLBACK = [{"text": "Betaling", "lang": "nl"}, {"text": "Diversen", "lang": "nl"},
                    {"text": "Invoice {inv}", "lang": "en"}, {"text": "Factuur {inv}", "lang": "nl"}]
MIX_FRAG = {"nl": ["Invoice {inv}", "Payment ref {ref}", "Ref. {ref}"],
            "en": ["Factuurnr {inv}", "Betaling {ref}", "Referentie {ref}"]}


REF_FRAG = {"nl": ["Kenmerk {ref}", "Betreft factuur {inv}", "Referentie {ref}", "Uw kenmerk {ref}"],
            "en": ["Ref {ref}", "Payment reference {ref}", "Re: invoice {inv}", "Your reference {ref}"]}
ORDER_RX = re.compile(r"\b(order|bestelling)\b", re.I)
PERIOD_ONLY_RX = re.compile(r"^(Betaling|Payment) \{period\}$")
INVOICE_WORD_RX = re.compile(r"factuur|invoice|services|dienstverlening", re.I)
BANNED_DIGITS = ("1234", "4321", "5514")   # run seeds and the artifact literal seen in the old draw


def scrub_digits(text):
    """Random reference numbers must never contain a run seed / the old artifact literal: bump the
    last digit of the offending digit run. Money tokens (digits followed by a decimal part) are
    derived from the amount column and are left alone."""
    def fix(m):
        run = m.group(0)
        for b in BANNED_DIGITS:
            if b in run:
                run = run.replace(b, b[:-1] + str((int(b[-1]) + 1) % 10))
        return run
    return re.sub(r"(?<![\d.,])\d{4,}(?![\d]|[.,]\d)", fix, text)


def norm(s):
    return re.sub(r"[^a-z0-9]+", " ", s.lower()).strip()


def sha256_bytes(b):
    return hashlib.sha256(b).hexdigest()


def sub_rng(seed, stage):
    return random.Random("vault-ledger-synth:%s:%s" % (seed, stage))


def vrng(name, tag):
    """Vendor-level deterministic RNG (independent of the run seed)."""
    return random.Random("vault-ledger-synth-vendor:%s:%s" % (name, tag))


# ------------------------------------------------------------------ loading

def load_world():
    spec_bytes = SPEC_PATH.read_bytes()
    spec = yaml.safe_load(spec_bytes)
    h = hashlib.sha256()
    corpus, hard = {}, None
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
    def __init__(self, d, account, cfg, rank):
        self.name = d["name"]
        self.aliases = d.get("aliases", [])
        self.archetype = d["archetype"]
        self.unverified = bool(d.get("unverified"))
        self.account = account
        self.cfg = cfg
        self.rank = rank
        self.sub = cfg.get("sub")
        self.family = cfg.get("family", "")
        self.country = d.get("country", "NL")
        self.suffixes = d.get("suffixes", [])
        self.product = d.get("product", d["name"])
        self.plans = d.get("plans")
        self.gid = None
        self.legal_aliases = [a for a in self.aliases if a != a.upper() and a != a.lower()
                              and "*" not in a]
        self.descriptors = [a for a in self.aliases if a == a.upper() or "*" in a]

    def allowed_forms(self):
        f = set(legal_form(s) for s in [self.name] + self.aliases)
        f.update(legal_form("x " + s) for s in self.suffixes)
        f.discard("")
        return f


def build_vendors(corpus, hard):
    vendors = {}
    for acct, j in corpus.items():
        vendors[acct] = [Vendor(v, acct, j["archetypes"][v["archetype"]], i)
                         for i, v in enumerate(j["vendors"])]
    hard_v = {v["name"]: Vendor(v, "hard", hard["archetypes"][v["archetype"]], i)
              for i, v in enumerate(hard["vendors"])}
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
    """Zipf-Mandelbrot weight per vendor: subtype weight x (rank+q)^-s inside the subtype pool."""
    vf = spec["vendor_frequency"]
    s, q = vf["exponent_s"], vf["offset_q"]
    sw = vf["subtype_weights"].get(account, {"": 1.0})
    pools = defaultdict(list)
    for v in pool:
        pools[v.sub or ""].append(v)
    live = {k: p for k, p in pools.items() if k in sw and p}
    tot = sum(sw[k] for k in live)
    w = {}
    for k in sorted(live):
        z = zm_weights(len(live[k]), s, q)
        zs = sum(z)
        for v, zz in zip(live[k], z):
            w[v.name] = sw[k] / tot * zz / zs
    return w


# ------------------------------------------------------------------ pricing

def vat_state(v):
    cfg = v.cfg
    if cfg.get("rc_foreign") and v.country != "NL":
        return 0.0, True
    return float(cfg.get("vat", 0.21)), False


def apply_vat(amount, is_total, rate, rc):
    """Return (net, vat, total) with net + vat == total exactly (to the cent)."""
    if rc or rate == 0:
        a = money(amount)
        return a, 0.0, a
    net = money(amount / (1 + rate)) if is_total else money(amount)
    vat = round(net * rate + 1e-9, 2)
    return net, vat, round(net + vat, 2)


def log_uniform(rng, lo, hi):
    return math.exp(rng.uniform(math.log(lo), math.log(hi)))


def round_to(x, step):
    return max(step, round(x / step) * step) if step else x


# revision 2: prices of a recurring contract move (yearly change, seat changes, USD billing, extras)

def fx_rate(spec, d):
    """Synthetic EUR/USD level for the month of d: ONE deterministic random walk shared by every
    vendor and every seed. An assumption, not market data."""
    fx = spec["price_dynamics"]["fx"]
    if not fx_rate.cache:
        r = vrng("eurusd", "fx")
        x = fx["start"]
        for _ in range(24):
            fx_rate.cache.append(x)
            x = min(fx["max"], max(fx["min"], x * math.exp(r.gauss(0, fx["monthly_sigma"]))))
    return fx_rate.cache[(d.year - 2025) * 12 + d.month - 1]


fx_rate.cache = []


def usd_billed(spec, v):
    return v.cfg["mode"] == "plan" and v.country in spec["price_dynamics"]["usd_billed_countries"]


def vendor_unit(v, plan):
    """Archetype menus are placeholder price points shared by every vendor of the archetype; a vendor
    without its own menu gets a nearby price of its own, so two vendors never share one price list."""
    if v.plans:
        return plan[1]
    r = vrng(v.name, "unit:" + plan[0])
    x = plan[1] * math.exp(r.uniform(-0.2, 0.2))
    return max(1.0, math.floor(x) + r.choice([0.0, 0.0, 0.5, 0.95, 0.99]))


def evolve(rng, spec, v, seg, d, prev):
    """Between two consecutive rows of one contract: a price change (most likely at the turn of the
    year) and, on per-seat plans, a seat added or removed."""
    pdyn = spec["price_dynamics"]
    cfg = v.cfg
    if not cfg.get("fixed_price") and not cfg.get("index_p"):
        months = max(1, (d.year - prev.year) * 12 + d.month - prev.month)
        p = pdyn["annual_change_p"] if d.year != prev.year else min(1.0, pdyn["midyear_change_p_per_month"] * months)
        if rng.random() < p:
            seg.mult *= 1 + rng.uniform(*pdyn["change_range"])
    if seg.plan and seg.plan[2] and rng.random() < pdyn["seat_change_p_per_step"]:
        seg.seats = max(1, seg.seats + rng.choice([1, 1, -1]))


def invoicing(cfg):
    """Does this archetype normally send invoices (so a bank line may quote an invoice number)?"""
    return cfg["doc"].get("invoice", 0.0) >= 0.35


def order_like(cfg):
    """Webshop-style archetypes (iDEAL checkout) are the only ones with order numbers."""
    return bool(cfg.get("orders", cfg["doc"].get("receipt_ideal", 0.0) >= 0.2))


def allowed(t, cfg, doc):
    """Can template t appear on document type doc for this archetype? No order numbers outside
    webshop orders, no invoice numbers on receipts or on bank lines of vendors that do not invoice,
    no bare 'payment <month>' on a till receipt."""
    text = t["text"]
    if ORDER_RX.search(text) and "{ref}" in text and not (order_like(cfg) and doc in ("invoice", "receipt_ideal")):
        return False
    if "{inv}" in text and (doc.startswith("receipt") or (doc == "bank" and not invoicing(cfg))):
        return False
    if doc.startswith("receipt") and PERIOD_ONLY_RX.match(text):
        return False
    return True


def for_doc(pool, cfg, doc):
    t = [x for x in pool if allowed(x, cfg, doc)]
    return t or pool


def generic_for(texts, cfg, doc):
    t = [x for x in texts if allowed(x, cfg, doc)
         and not (doc.startswith("receipt") and INVOICE_WORD_RX.search(x["text"]))]
    return t or [{"text": "Betaling", "lang": "nl"}]


def distinct(r, text, rng, taken):
    """Make a repeated (vendor, description) pair distinct with context the document really has:
    the invoice number where one exists, otherwise the date, and a time only if the date is not
    enough (two purchases at one vendor on one day). taken(text) tells whether text is in use."""
    if r["doc"] == "invoice" or (r["doc"] == "bank" and invoicing(r["cv"].cfg)):
        return "Factuur %s - %s" % (r["inv"], text)
    date = r["date"].strftime("%d-%m-%Y")
    if date not in text:
        text = "%s %s" % (text, date)
        if not taken(text):
            return text
    return "%s %02d:%02d" % (text, rng.randint(7, 21), rng.randint(0, 59))


class Seg(object):
    """One contract / customer: fixed plan, seats, base amounts."""


def plans_for(v):
    menu = v.plans or v.cfg.get("plans") or []
    if not menu:
        return []
    r = vrng(v.name, "plans")
    n = 1 if len(menu) == 1 else min(len(menu), 2 if r.random() < 0.6 else 3)
    idx = list(range(len(menu)))
    r.shuffle(idx)
    return [menu[i] for i in sorted(idx[:n])]


def new_segment(rng, spec, v):
    cfg = v.cfg
    seg = Seg()
    seg.cust = rng.randint(100000, 9999999)
    seg.plan = None
    seg.seats = 1
    seg.bases = {}
    seg.mult = 1.0
    sj = cfg.get("seg_jitter", 0)
    seg.jit = math.exp(max(-0.5, min(0.5, rng.gauss(0, sj)))) if sj else 1.0
    if cfg["mode"] == "plan":
        offered = plans_for(v)
        seg.plan = offered[0] if len(offered) == 1 or rng.random() < 0.6 else rng.choice(offered[1:])
        if seg.plan[2]:
            se = spec["amounts"][SW]["params"]["seats"]
            seg.seats = wchoice(rng, list(se.keys()), list(se.values()))
    elif cfg["mode"] == "usage":
        u = cfg["usage"]
        seg.scale = math.exp(vrng(v.name, "usage").gauss(u["mu"], u["sigma"])) * seg.jit
    elif cfg["mode"] == "hourly":
        seg.rate = vrng(v.name, "rate").choice(cfg["rates"])
    return seg


def fixed_base(v, tmpl, cfg):
    lo, hi = tmpl.get("amt") or cfg["amt"]
    r = vrng(v.name, "fixed:" + tmpl.get("grp", tmpl["text"]))
    return log_uniform(r, lo, hi)


def draw_price(rng, spec, v, seg, tmpl, d, annual):
    """(net, vat, total, hrs, rate, rc) for one row."""
    cfg = v.cfg
    rate, rc = vat_state(v)
    mode = cfg["mode"]
    hrs = None
    is_total = cfg.get("amt_is", "total") == "total"
    if mode == "plan":
        unit, per_seat, cad = vendor_unit(v, seg.plan) * seg.mult, seg.plan[2], seg.plan[3]
        amount = unit * (seg.seats if per_seat else 1)
        if annual and cad == "m":
            ann = spec["amounts"][SW]["params"]["annual_multiplier"]
            amount = amount * ann["factor"] * ann["discount"]
        if usd_billed(spec, v):
            # list price in USD, debited in EUR at the month's rate plus a small card-rate spread
            j = spec["price_dynamics"]["fx"]["card_rate_jitter"]
            amount = amount / fx_rate(spec, d) * (1 + rng.uniform(-j, j))
        is_total = False
    elif mode == "usage":
        amount = seg.scale * rng.lognormvariate(0, 0.25)
        is_total = False
    elif mode == "hourly":
        hrs = rng.choice(HOURS)
        amount = hrs * seg.rate
        is_total = False
    else:
        lo, hi = tmpl.get("amt") or cfg["amt"]
        if tmpl.get("fixed"):
            key = tmpl.get("grp", tmpl["text"])
            if key not in seg.bases:
                seg.bases[key] = fixed_base(v, tmpl, cfg) * seg.jit
            amount = seg.bases[key] * seg.mult
        else:
            amount = log_uniform(rng, lo, hi)
        if cfg.get("seasonal") and not tmpl.get("fixed"):
            amount *= 1.30 if (d.month >= 10 or d.month <= 3) else 0.85
        is_total = tmpl.get("amt_is", cfg.get("amt_is", "total")) == "total"
        step = tmpl.get("rnd") or cfg.get("rnd")
        if step:
            amount = round_to(amount, step)
    ex = spec["price_dynamics"]["extras"].get(v.family)
    if ex and rng.random() < ex["p"]:
        amount += log_uniform(rng, *ex["range"])   # out-of-bundle usage, meeting rooms, add-ons
    net, vat, total = apply_vat(amount, is_total, rate, rc)
    return net, vat, total, hrs, rate, rc


# ------------------------------------------------------------------ content rows

def pick_doc(rng, doc_weights, recurring):
    keys = [k for k in doc_weights if not (recurring and k.startswith("receipt"))]
    return wchoice(rng, keys, [doc_weights[k] for k in keys])


def date_for(rng, doc, cluster_p):
    if doc.startswith("receipt"):
        return receipt_date(rng)
    return invoice_date(rng, cluster_p)


def contracts(k, cap):
    out, rem = [], k
    while rem > 0:
        out.append(min(rem, cap))
        rem -= out[-1]
    return out


def suitable(pool, style):
    cad = "y" if style == "annual" else "m"
    t = [x for x in pool if x.get("cad", "any") in ("any", cad)]
    return t or pool


def make_row(rng, spec, v, seg, tmpl, doc, d, recurring, annual):
    net, vat, total, hrs, rate, rc = draw_price(rng, spec, v, seg, tmpl, d, annual)
    pdate = prev_month(d) if v.cfg.get("billing") == "arrears" else d
    return {"date": d, "doc": doc, "net": net, "vat": vat, "total": total, "vrate": rate, "rc": rc,
            "tmpl": tmpl, "lang": tmpl["lang"], "seg": seg, "hrs": hrs, "pdate": pdate,
            "recurring": recurring, "cv": v,
            # snapshot: seg is shared by all rows of a contract and evolve() changes its seat count,
            # while descriptions are rendered later -- the text must quote the seats this row was priced at
            "seats": seg.seats}


def vendor_rows(rng, spec, v, k, pool):
    """Pre-render rows for k transactions of vendor v (template text unresolved)."""
    cfg = v.cfg
    cad = cfg.get("cadence", {"irregular": 1.0})
    if k == 1:
        style = "irregular"
    else:
        opts = [c for c in sorted(cad) if k <= 4 or c != "annual"] or ["irregular"]
        style = wchoice(rng, opts, [cad.get(c, 1.0) for c in opts])
    cluster_p = spec["date_model"]["month_end_cluster"].get(v.account, 0.0)
    rows = []
    if style == "irregular":
        for _ in range(k):
            annual = (cfg["mode"] == "plan" and rng.random() < spec["amounts"][SW]["params"]["annual_multiplier"]["p"])
            doc = pick_doc(rng, cfg["doc"], False)
            tmpl = rng.choice(for_doc(suitable(pool, "annual" if annual else style), cfg, doc))
            seg = new_segment(rng, spec, v)
            d = date_for(rng, doc, cluster_p)
            rows.append(make_row(rng, spec, v, seg, tmpl, doc, d, False, annual or tmpl.get("cad") == "y"))
        return rows
    step = {"monthly": 1, "quarterly": 3, "annual": 12}[style]
    cap = {"monthly": 20, "quarterly": 6, "annual": 2}[style]
    for L in contracts(k, cap):
        span = (L - 1) * step
        start = rng.randint(0, max(0, 19 - span))
        qe = style == "quarterly" and cfg.get("quarter_end")
        if qe:
            # start in a quarter-end month (Mar/Jun/Sep/Dec = index 2 mod 3)
            start = (start // 3) * 3 + 2
            while start + span > 19:
                start -= 3
            start = max(2, start)
        doc = pick_doc(rng, cfg["doc"], True)
        rec = for_doc([t for t in suitable(pool, style) if t.get("rec", True)] or pool, cfg, doc)
        primary = rng.choice(rec)
        alts = [t for t in rec if cfg["mode"] != "template"
                or t.get("grp", t["text"]) == primary.get("grp", primary["text"])]
        seg = new_segment(rng, spec, v)
        prev = None
        day = rng.randint(1, 28) if style == "annual" else cfg.get("day") or rng.choice(cfg.get("days", list(range(1, 29))))
        idx = bool(cfg.get("index_p")) and rng.random() < cfg["index_p"]
        idx_mult = 1 + rng.uniform(0.02, 0.04)
        indexed = False
        for j in range(L):
            y, m = add_months(2025, 1, start + j * step)
            d0 = last_bdays(y, m, 1)[0] if qe else roll_bd(mk_date(y, m, day))
            tm = primary if rng.random() < 0.7 else rng.choice(alts)
            dc = doc if rng.random() < 0.85 else pick_doc(rng, cfg["doc"], True)
            if not allowed(tm, cfg, dc):
                dc = doc
            if prev is not None:
                evolve(rng, spec, v, seg, d0, prev)
            prev = d0
            if idx and y == 2026 and not indexed:
                # yearly indexation of the contract price; extras are billed on top of it
                seg.mult *= idx_mult
                indexed = True
            rows.append(make_row(rng, spec, v, seg, tm, dc, d0, True,
                                 style == "annual" and cfg["mode"] == "plan"))
    return rows


# ------------------------------------------------------------------ rendering

def render_ctx(row, rng):
    v, seg, d, lang = row["cv"], row["seg"], row["date"], row["lang"]
    seats = row["seats"]
    pd = row["pdate"]
    last = mk_date(pd.year, pd.month, 31).day
    if lang == "nl":
        users = "%d gebruiker%s" % (seats, "" if seats == 1 else "s")
    else:
        users = "%d user%s" % (seats, "" if seats == 1 else "s")
    hrs = row["hrs"]
    hs = ""
    if hrs is not None:
        hs = ("%g" % hrs).replace(".", ",") if lang == "nl" else "%g" % hrs
    return {
        "product": v.product, "plan": seg.plan[0] if seg.plan else "", "users": users,
        "seats": seats, "period": "%s %d" % (month_name(pd, lang), pd.year),
        "month": month_name(pd, lang), "year": pd.year,
        "fy": d.year - 1 if d.month <= 9 else d.year,
        "pperiod": "01-%02d-%d t/m %02d-%02d-%d" % (pd.month, pd.year, last, pd.month, pd.year),
        "q": "Q%d %d" % ((pd.month - 1) // 3 + 1, pd.year), "date": d.strftime("%d-%m-%Y"),
        "inv": row["inv"], "ref": rng.randint(100000, 99999999), "cust": seg.cust,
        "city": rng.choice(CITIES), "route": "%s - %s" % tuple(rng.sample(STATIONS, 2)),
        "flight": rng.choice(AIRPORTS), "hrs": hs,
        "domain": "%s-%s.nl" % (rng.choice(DOMAIN_WORDS), rng.choice(DOMAIN_WORDS)),
        "total": fmt_num(row["total"], lang), "net": fmt_num(row["net"], lang),
        "vat": fmt_num(row["vat"], lang),
    }


def inv_numbers(rows_by_vendor):
    """Strictly increasing invoice numbers per content vendor, in date order."""
    styles = ["{y}-{n:04d}", "INV-{y}-{n:05d}", "F{y}/{n:04d}", "{n:07d}", "INV{n:06d}", "{y}{n:05d}"]
    for name, rows in sorted(rows_by_vendor.items()):
        r = vrng(name, "inv")
        style = r.choice(styles)
        n = r.randint(20, 900)
        for row in sorted(rows, key=lambda x: (x["date"], x["total"])):
            n += r.randint(1, 35)
            row["inv"] = style.format(y=row["date"].year, n=n)


def btw_fragment(row, rng):
    lang, rate = row["lang"], int(round(row["vrate"] * 100))
    nt, vt, tt = (fmt_num(row[k], lang) for k in ("net", "vat", "total"))
    if row["rc"]:
        return rng.choice(["BTW verlegd naar afnemer", "BTW verlegd"] if lang == "nl"
                          else ["VAT reverse charged", "Reverse charge - VAT 0%"])
    if rate == 0:
        return rng.choice(["BTW 0%", "Geen BTW van toepassing"] if lang == "nl"
                          else ["VAT 0%", "No VAT applicable"])
    if lang == "nl":
        return rng.choice(["excl. BTW %s, BTW %d%% %s, totaal %s" % (nt, rate, vt, tt),
                           "Bedrag excl. BTW %s + %d%% BTW %s = %s" % (nt, rate, vt, tt),
                           "incl. %d%% BTW" % rate, "BTW %d%% %s" % (rate, vt)])
    return rng.choice(["Subtotal %s + %d%% VAT %s = %s" % (nt, rate, vt, tt),
                       "Total %s incl. %d%% VAT" % (tt, rate), "VAT %d%% %s" % (rate, vt)])


def payment_text(row, rng, paid, spec):
    """ONE payment field chosen by document type."""
    doc, lang = row["doc"], row["lang"]
    pm = spec["payment_text"]
    if doc == "invoice":
        terms = wchoice(rng, [int(k) for k in pm["terms_days"]], list(pm["terms_days"].values()))
        if paid:
            if rng.random() < pm["invoice_paid_terms_p"]:
                return "Betaaltermijn %d dagen" % terms if lang == "nl" else "Payment terms %d days" % terms
            return ""
        if rng.random() < pm["invoice_unpaid_terms_p"]:
            due = row["date"] + dt.timedelta(days=terms)
            if lang == "nl":
                return "Te betalen voor %s" % due.strftime("%d-%m-%Y")
            return rng.choice(["Payable within %d days" % terms, "Total due %s" % fmt_num(row["total"], lang)])
        return ""
    if doc == "bank":
        return rng.choice(pm["bank_recurring"] if row["recurring"] else pm["bank_oneoff"])
    if doc == "receipt_ideal":
        return rng.choice(pm["ideal"])
    return rng.choice(pm["pos"])


def assemble(row, core, rng, spec, paid, term_code):
    """Combine core text, BTW fragment and the single payment field."""
    doc = row["doc"]
    pm = spec["payment_text"]
    parts = [core]
    p = pm["btw_fragment_p"].get(doc, 0.0)
    if p and rng.random() < p:
        parts.append(btw_fragment(row, rng))
    rp = pm.get("reference_fragment_p", {}).get(doc, 0.0)
    if doc == "bank" and not invoicing(row["cv"].cfg):
        rp *= pm["reference_fragment_non_invoicing_factor"]
    if rp and rng.random() < rp:
        frags = REF_FRAG[row["lang"]]
        if (doc == "bank" and not invoicing(row["cv"].cfg)) or str(row["inv"]) in core:
            # no invoice number where no invoice exists, and never the same number twice in one line
            frags = [f for f in frags if "{inv}" not in f]
        parts.append(rng.choice(frags).format_map({"ref": rng.randint(100000, 99999999), "inv": row["inv"]}))
    pay = payment_text(row, rng, paid, spec)
    body = " - ".join(parts)
    if not pay:
        text = body
    elif doc == "invoice":
        text = body + " - " + pay
    else:
        if "%" in pay:
            pay = pay % rng.randint(1000, 9999)
        if doc == "bank":
            text = pay + " " + body if rng.random() < 0.7 else body + " - " + pay
        else:
            text = pay + " " + body if rng.random() < 0.7 else body + " " + pay
    if term_code and doc == "receipt_pos":
        text += " " + rng.choice(pm["terminal_codes"]) % rng.randint(1, 99)
    return text


# ------------------------------------------------------------------ hard rows

def plan_hard(rng, spec, hard, N, all_w, vendors, hard_v):
    H = sum(1 for _ in range(N) if rng.random() < spec["difficulty_mix"]["hard_ambiguous"])
    cases = spec["hard_cases"]["cases"]
    by = defaultdict(list)
    for d in hard["descriptions"]:
        by[(d["case"], d["kind"])].append(d)
    prior = spec["class_prior"]["values"]
    accts = sorted(prior)
    acct_w = [prior[a] for a in accts]
    names = {a: [v.name for v in vendors[a]] for a in accts}
    vmap = {v.name: v for a in accts for v in vendors[a]}

    def draw_vendor(a):
        return vmap[wchoice(rng, names[a], [all_w[a][x] for x in names[a]])]

    counts = multinomial(rng, H, [c["weight"] for c in cases])
    plan = []
    for c, n in zip(cases, counts):
        for _ in range(n):
            if c["id"] == "generic_description":
                if rng.random() < c["ambiguous_vendor_share"]:
                    v = hard_v[rng.choice(sorted(hard_v))]
                    plan.append(dict(case=c["id"], kind="generic", cv=v, label=GE, true=GE,
                                     escalate=True, generic=True, shown=v))
                else:
                    a = wchoice(rng, accts, acct_w)
                    v = draw_vendor(a)
                    plan.append(dict(case=c["id"], kind="generic", cv=v, label=a, true=a,
                                     escalate=False, generic=True, shown=v))
            elif c["id"] == "vendor_description_disagree":
                a = wchoice(rng, accts, acct_w)
                va = draw_vendor(a)
                others = [x for x in accts if x != a]
                b = wchoice(rng, others, [prior[x] for x in others])
                vb = draw_vendor(b)
                plan.append(dict(case=c["id"], kind="disagree", cv=vb, shown=va, label=GE, true=b,
                                 escalate=True, generic=False))
            else:
                kinds = c["kinds"]
                ks = sorted(kinds)
                kn = wchoice(rng, ks, [kinds[k]["p"] for k in ks])
                d = rng.choice(by[(c["id"], kn)])
                kd = kinds[kn]
                esc = bool(kd["escalate"])
                plan.append(dict(case=c["id"], kind=kn, desc=d, cv=hard_v[d["vendor"]], shown=hard_v[d["vendor"]],
                                 label=GE if esc else kd["account"], true=kd["account"] if not esc else GE,
                                 escalate=esc, generic=False))
    rng.shuffle(plan)
    return plan


def hard_row(rng, spec, hard, item, corpus):
    cv = item["cv"]
    cfg = cv.cfg
    if item["kind"] == "disagree":
        # content generated as vendor cv (target account), shown under another vendor
        doc = pick_doc(rng, cfg["doc"], False)
        tmpl = rng.choice(for_doc(corpus[cv.account]["pools"][cfg["family"]], cfg, doc))
        seg = new_segment(rng, spec, cv)
        d = date_for(rng, doc, 0.0)
        return make_row(rng, spec, cv, seg, tmpl, doc, d, False, tmpl.get("cad") == "y")
    if item["generic"]:
        doc0 = pick_doc(rng, cfg["doc"], False)
        g = rng.choice(generic_for(hard["generic"], cfg, doc0))
        if cv.account == "hard":
            tmpl = {"text": g["text"], "lang": g["lang"], "amt": cfg["amt"]}
        else:
            base = rng.choice(corpus[cv.account]["pools"][cfg["family"]])
            tmpl = dict(base, text=g["text"], lang=g["lang"])
        seg = new_segment(rng, spec, cv)
        d = date_for(rng, doc0, 0.0)
        return make_row(rng, spec, cv, seg, tmpl, doc0, d, False, False)
    dsc = item["desc"]
    tmpl = {"text": dsc["text"], "lang": dsc["lang"], "amt": dsc["amt"]}
    seg = new_segment(rng, spec, cv)
    doc = pick_doc(rng, dsc.get("doc") or cfg["doc"], False)
    d = date_for(rng, doc, 0.0)
    return make_row(rng, spec, cv, seg, tmpl, doc, d, False, False)


# ------------------------------------------------------------------ splitting

def assign_splits(spec, row_groups):
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
    for _ in range(80):
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
                gsplit[cand[0]] = s
                moved = True
                break
        if not moved:
            break
    return {g: SPLITS[s] for g, s in gsplit.items()}


# ------------------------------------------------------------------ vendor string, noise

def base_vendor_string(rng, v, doc):
    if doc == "invoice":
        if v.legal_aliases and rng.random() < 0.45:
            return rng.choice(v.legal_aliases)
        return v.name
    if v.descriptors and rng.random() < 0.55:
        return rng.choice(v.descriptors)
    return v.name


def compatible(t, base):
    """Can template t replace base without breaking the price/description link?"""
    return (t.get("cad", "any") == base.get("cad", "any") and t.get("amt") == base.get("amt")
            and bool(t.get("fixed")) == bool(base.get("fixed"))
            and t.get("grp", t["text"]) == base.get("grp", base["text"]) or
            (t.get("amt") is None and base.get("amt") is None and t.get("cad", "any") == base.get("cad", "any")))


def noise_plan(spec, cores, shown, docs, n_rows, cvs):
    """Per-op selection probability and eligibility mask so the realised rate ~= spec rate."""
    plan = {}
    for o in spec["noise_model"]["operations"]:
        name = o["name"]
        if name == "abbreviation_nl_en":
            e = [bool(abbrev_candidates(c)) for c in cores]
        elif name == "typo_char_swap_drop_dup":
            e = [len(c) >= 6 for c in cores]
        elif name == "ocr_confusion":
            e = [bool(re.search(r"[OlISBm]|\d{5,}", c)) for c in cores]
        elif name == "vendor_legal_suffix_variation":
            e = [bool(v.suffixes) and not legal_form(v.name) for v in shown]
        elif name == "store_terminal_code":
            e = [d == "receipt_pos" for d in docs]
        elif name == "truncated_description":
            e = [len(c) > 40 for c in cores]
        elif name == "nl_en_mix_in_one_row":
            # the mixed-in fragment quotes an invoice / payment reference: only where one exists
            e = [d == "invoice" or (d == "bank" and invoicing(c.cfg)) for d, c in zip(docs, cvs)]
        elif name == "missing_or_generic_description":
            e = [not d.startswith("receipt") for d in docs]
        else:
            e = [True] * len(cores)
        n_e = sum(e)
        plan[name] = dict(o, elig=e, p=min(1.0, o["rate"] * n_rows / n_e) if n_e else 0.0)
    return plan


def apply_core_noise(rng, trig, core, lang, generic_texts, inv):
    applied = []
    language = lang
    ref = rng.randint(100000, 99999999)
    if "missing_or_generic_description" in trig:
        g = rng.choice(generic_texts)
        core = g["text"].format_map({"inv": inv, "ref": ref})
        applied.append("missing_or_generic_description")
    if "nl_en_mix_in_one_row" in trig:
        frag = rng.choice([f for f in MIX_FRAG[lang] if "{inv}" not in f or str(inv) not in core]
                          ).format_map({"inv": inv, "ref": ref})
        core = (frag + " - " + core) if rng.random() < 0.5 else (core + " - " + frag)
        language = "mixed"
        applied.append("nl_en_mix_in_one_row")
    for name, fn in (("abbreviation_nl_en", op_abbrev), ("typo_char_swap_drop_dup", op_typo),
                     ("ocr_confusion", op_ocr)):
        if name in trig:
            r = fn(core, rng)
            if r is not None and r != core:
                core = r
                applied.append(name)
    return core, language, applied


def add_suffix(vs, v, rng):
    """Append the vendor's own Dutch form to its canonical name (never to aliases/descriptors)."""
    if not v.suffixes or legal_form(v.name):
        return vs, False
    return v.name + " " + rng.choice(v.suffixes), True


# ------------------------------------------------------------------ main generation

def generate(seed, N, spec=None, corpus=None, hard=None):
    if spec is None:
        spec, corpus, hard, _, _ = load_world()
    vendors, hard_v, allv, by_name = build_vendors(corpus, hard)
    prior = spec["class_prior"]["values"]
    accts = sorted(prior)
    all_w = {a: vendor_weights(spec, a, vendors[a]) for a in accts}
    generic_texts = hard["generic"] or GENERIC_FALLBACK

    plan = plan_hard(sub_rng(seed, "hard-plan"), spec, hard, N, all_w, vendors, hard_v)
    H = len(plan)
    hl = Counter(p["label"] for p in plan)
    resid = [max(0.0, prior[a] * N - hl[a]) for a in accts]
    counts_a = multinomial(sub_rng(seed, "class-mix"), N - H, resid)

    rows = []
    for a, na in zip(accts, counts_a):
        names = [v.name for v in vendors[a]]
        cnt = multinomial(sub_rng(seed, "vendor-mix:" + a), na, [all_w[a][x] for x in names])
        by_v = {v.name: v for v in vendors[a]}
        pools = corpus[a]["pools"]
        for name, k in zip(names, cnt):
            if not k:
                continue
            v = by_v[name]
            r = sub_rng(seed, "vendor:%s:%s" % (a, name))
            for row in vendor_rows(r, spec, v, k, pools[v.cfg["family"]]):
                row.update(show=v, label=a, true=a, difficulty="easy", escalate=False,
                           hard_case="", generic=False)
                rows.append(row)
    r_hard = sub_rng(seed, "hard-rows")
    for item in plan:
        row = hard_row(r_hard, spec, hard, item, corpus)
        row.update(show=item["shown"], label=item["label"], true=item["true"],
                   difficulty="ambiguous" if item["escalate"] else "hard",
                   escalate=item["escalate"], hard_case=item["case"], generic=item["generic"])
        rows.append(row)

    rows.sort(key=lambda r: (r["date"], r["label"], r["show"].name, r["cv"].name, r["total"], r["doc"]))
    by_cv = defaultdict(list)
    for r in rows:
        by_cv[r["cv"].name].append(r)
    inv_numbers(by_cv)

    pp = spec["paid_unpaid"]
    seed_str = str(seed)
    cores, docs, shown = [], [], []
    seen_core = set()
    redraws = 0
    for i, r in enumerate(rows):
        rng = sub_rng(seed, "render:%d" % i)
        core = None
        for attempt in range(6):
            core = r["tmpl"]["text"].format_map(_Ctx(render_ctx(r, rng)))
            key = (r["show"].name, norm(core))
            if key not in seen_core and seed_str not in re.findall(r"\d+", core):
                break
            redraws += 1
            pool = None if r["cv"].account == "hard" else corpus[r["cv"].account]["pools"].get(r["cv"].cfg.get("family"))
            if attempt >= 1 and pool and not r["generic"]:
                cands = [t for t in pool if compatible(t, r["tmpl"]) and allowed(t, r["cv"].cfg, r["doc"])]
                if cands:
                    r["tmpl"] = dict(rng.choice(cands))
                    r["lang"] = r["tmpl"]["lang"]
        else:
            # genuinely distinct context instead of a repair tag: the row's unique invoice number
            # where the document has one, otherwise its date (see distinct)
            if (r["show"].name, norm(core)) in seen_core:
                core = distinct(r, core, rng, lambda c: (r["show"].name, norm(c)) in seen_core)
        seen_core.add((r["show"].name, norm(core)))
        r["core"] = core
        cores.append(core)
        docs.append(r["doc"])
        shown.append(r["show"])

    ops = noise_plan(spec, cores, shown, docs, len(rows), [r["cv"] for r in rows])
    out = []
    seen_final = set()
    for i, r in enumerate(rows):
        rng = sub_rng(seed, "row:%d" % i)
        v = r["show"]
        trig = [n for n in sorted(ops) if rng.random() < ops[n]["p"] and ops[n]["elig"][i]]
        mx = spec["noise_model"]["max_ops_per_row"]
        if len(trig) > mx:
            keep = set(rng.sample(trig, mx))
            trig = [t for t in trig if t in keep]
        if r["doc"] == "invoice":
            key = r["true"] if r["true"] in pp["invoice_paid_fraction"] else GE
            paid = (r["cv"].archetype in pp["card_charged_archetypes"]
                    or rng.random() < pp["invoice_paid_fraction"][key])
        else:
            paid = True
        core, language, applied = apply_core_noise(rng, trig, r["core"], r["lang"],
                                                   generic_for(generic_texts, r["cv"].cfg, r["doc"]), r["inv"])
        text = assemble(r, core, rng, spec, paid, "store_terminal_code" in trig)
        if "store_terminal_code" in trig:
            applied.append("store_terminal_code")
        vs = base_vendor_string(rng, v, r["doc"])
        if "vendor_legal_suffix_variation" in trig:
            vs, ok = add_suffix(vs, v, rng)
            if ok:
                applied.append("vendor_legal_suffix_variation")
        if "truncated_description" in trig:
            keep = rng.choice(ops["truncated_description"]["widths"])
            if len(text) > keep:
                text = text[:keep].rstrip(" -")
                applied.append("truncated_description")
        if "casing_variation" in trig:
            modes = ops["casing_variation"]["modes"]
            mode = wchoice(rng, list(modes.keys()), list(modes.values()))
            text = op_case(text, mode)
            if mode != "Title" and rng.random() < 0.5:
                vs = op_case(vs, mode)
            applied.append("casing_variation")
        text = scrub_digits(text.strip())
        vs = scrub_digits(vs)
        key = (norm(vs), norm(text))
        if key in seen_final:
            redraws += 1
            text = scrub_digits(distinct(r, text, rng, lambda c: (norm(vs), norm(scrub_digits(c))) in seen_final))
            key = (norm(vs), norm(text))
        seen_final.add(key)
        out.append({"id": "s%s-%05d" % (seed, i), "vendor": vs, "description": text,
                    "date": r["date"].isoformat(), "amount": r["total"], "paid": paid,
                    "account": r["label"], "meta": {
                        "archetype": v.archetype, "difficulty": r["difficulty"],
                        "escalate": r["escalate"], "noise_applied": "|".join(applied),
                        "language": language, "vendor_unverified": v.unverified,
                        "vendor_canonical": v.name, "true_account": r["true"],
                        "hard_case": r["hard_case"], "gid": v.gid,
                        "desc_family": r["cv"].cfg.get("family", ""), "doc_type": r["doc"],
                        "vat_rate": "rc" if r["rc"] else "%g" % r["vrate"],
                        "net_amount": r["net"], "content_vendor": r["cv"].name}})

    gsplit = assign_splits(spec, [(o["meta"]["gid"], o["account"]) for o in out])
    for o in out:
        o["split"] = gsplit[o["meta"]["gid"]]
    seen = defaultdict(set)
    for o in out:
        seen[norm(o["vendor"])].add(o["split"])
    name_index = {v.name: v for v in allv}
    for o in out:
        if len(seen[norm(o["vendor"])]) > 1:
            v = name_index.get(o["meta"]["vendor_canonical"])
            o["vendor"] = v.name if v else o["vendor"]
    generate.redraws = redraws
    return out, vendors


class _Ctx(dict):
    def __missing__(self, k):
        raise KeyError("unknown placeholder {%s}" % k)


# ------------------------------------------------------------------ output / stats

def write_csv(path, cols, rows):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(cols)
        for r in rows:
            w.writerow(r)


def stats(out, spec, corpus=None):
    N = len(out)
    st = {"rows": N}
    st["rows_per_split"] = {s: sum(1 for o in out if o["split"] == s) for s in SPLITS}
    st["row_fraction_per_split"] = {s: round(st["rows_per_split"][s] / N, 4) for s in SPLITS}
    prior = spec["class_prior"]["values"]
    accts = sorted(prior)
    st["rows_per_account"] = {a: sum(1 for o in out if o["account"] == a) for a in accts}
    st["account_fraction"] = {a: round(st["rows_per_account"][a] / N, 4) for a in accts}
    chi = sum((st["rows_per_account"][a] - prior[a] * N) ** 2 / (prior[a] * N) for a in accts)
    st["class_mix_chi2"] = {"chi2": round(chi, 3), "df": len(accts) - 1,
                            "p": round(chi2_sf_even(chi, len(accts) - 1), 4)}
    st["rows_per_account_per_split"] = {a: {s: sum(1 for o in out if o["account"] == a and o["split"] == s)
                                            for s in SPLITS} for a in accts}
    st["vendor_groups_per_account_per_split"] = {
        a: {s: len(set(o["meta"]["gid"] for o in out if o["account"] == a and o["split"] == s))
            for s in SPLITS} for a in accts}
    st["difficulty"] = {d: round(sum(1 for o in out if o["meta"]["difficulty"] == d) / N, 4)
                        for d in ("easy", "hard", "ambiguous")}
    nh = sum(1 for o in out if o["meta"]["difficulty"] != "easy")
    ne = sum(1 for o in out if o["meta"]["escalate"])
    st["escalate_fraction_of_all"] = round(ne / N, 4)
    st["escalate_fraction_of_hard"] = round(ne / max(1, nh), 4)
    st["language"] = {l: round(sum(1 for o in out if o["meta"]["language"] == l) / N, 4)
                      for l in ("en", "nl", "mixed")}
    nz = Counter()
    for o in out:
        for op in filter(None, o["meta"]["noise_applied"].split("|")):
            nz[op] += 1
    st["noise_realised_rate"] = {k: round(nz[k] / N, 4) for k in sorted(nz)}
    st["noise_spec_rate"] = {o["name"]: o["rate"] for o in spec["noise_model"]["operations"]}
    st["paid_rate"] = {a: round(sum(1 for o in out if o["account"] == a and o["paid"]) /
                                max(1, st["rows_per_account"][a]), 3) for a in accts}
    top10, top10_clear, zipf = {}, {}, {}
    q = spec["vendor_frequency"]["offset_q"]
    for a in accts:
        c = Counter(o["meta"]["vendor_canonical"] for o in out if o["account"] == a)
        top10[a] = round(sum(x for _, x in c.most_common(10)) / max(1, sum(c.values())), 3)
        c2 = Counter(o["meta"]["vendor_canonical"] for o in out
                     if o["account"] == a and o["meta"]["difficulty"] == "easy")
        top10_clear[a] = round(sum(x for _, x in c2.most_common(10)) / max(1, sum(c2.values())), 3)
        if corpus:
            vals = list(c2.values()) + [0] * max(0, len(corpus[a]["vendors"]) - len(c2))
            zipf[a] = {"pure_zipf_q0": round(zipf_mle(vals, 0.0), 3),
                       "zipf_mandelbrot_q%g" % q: round(zipf_mle(vals, q), 3)}
    st["top10_vendor_share_all_rows"] = top10
    st["top10_vendor_share_clear_rows_only_NOT_THE_GATE"] = top10_clear
    st["zipf_exponent_mle_easy_rows"] = zipf
    ge = Counter(o["meta"]["vendor_canonical"] for o in out if o["account"] == GE)
    st["general_other_max_single_vendor_share"] = round(max(ge.values()) / sum(ge.values()), 3)
    keys = [norm(o["vendor"]) + "|" + norm(o["description"]) for o in out]
    st["dup_rate_vendor_description"] = round(1 - len(set(keys)) / N, 4)
    vs = defaultdict(set)
    for o in out:
        vs[norm(o["vendor"])].add(o["split"])
    st["vendor_strings_in_multiple_splits"] = sum(1 for s in vs.values() if len(s) > 1)
    gs = defaultdict(set)
    for o in out:
        gs[o["meta"]["gid"]].add(o["split"])
    st["vendor_groups_in_multiple_splits"] = sum(1 for s in gs.values() if len(s) > 1)
    st["integer_euro_amount_share"] = round(sum(1 for o in out if ("%.2f" % o["amount"]).endswith(".00")) / N, 4)

    def wk(rs):
        return round(sum(1 for o in rs if dt.date.fromisoformat(o["date"]).weekday() >= 5) / max(1, len(rs)), 4)
    dts = lambda d: [o for o in out if o["meta"]["doc_type"] == d]
    st["weekend_share"] = {"invoice": wk(dts("invoice")), "bank": wk(dts("bank")),
                           "receipt": wk(dts("receipt_pos") + dts("receipt_ideal"))}
    st["doc_type_share"] = {d: round(len(dts(d)) / N, 4) for d in ("invoice", "bank", "receipt_pos", "receipt_ideal")}
    pro = [o for o in dts("invoice") if o["meta"]["true_account"] == PR and o["account"] == PR]

    def last3(o):
        d = dt.date.fromisoformat(o["date"])
        return d in last_bdays(d.year, d.month, 3)
    st["prof_invoice_last3_bdays_share"] = round(sum(1 for o in pro if last3(o)) / max(1, len(pro)), 4)
    kvk = [o for o in out if o["meta"]["vendor_canonical"] == "Kamer van Koophandel" and o["account"] == PR]
    st["kvk_constant_share_of_professional"] = round(
        sum(1 for o in kvk if abs(o["amount"] - 85.15) < 0.005) / max(1, st["rows_per_account"][PR]), 4)
    sw = sorted(o["amount"] for o in out if o["account"] == SW)
    st["software_q95"] = sw[int(0.95 * (len(sw) - 1))] if sw else None
    st["suffix_share_of_vendor_strings"] = round(sum(1 for o in out if legal_form(o["vendor"])) / N, 4)
    return st


def escalate_arithmetic(spec):
    tot = 0.0
    for c in spec["hard_cases"]["cases"]:
        if c["id"] == "vendor_description_disagree":
            e = 1.0
        elif c["id"] == "generic_description":
            e = c["ambiguous_vendor_share"]
        else:
            e = sum(k["p"] for k in c["kinds"].values() if k["escalate"])
        tot += c["weight"] * e
    return round(tot / sum(c["weight"] for c in spec["hard_cases"]["cases"]), 4)


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
                o["meta"]["true_account"], o["meta"]["hard_case"], o["split"],
                o["meta"]["desc_family"], o["meta"]["doc_type"], o["meta"]["vat_rate"],
                "%.2f" % o["meta"]["net_amount"]] for o in out])
    for s in SPLITS:
        write_csv(out_dir / ("%s_%s.csv" % (s, seed)), ["vendor", "description", "account"],
                  [[o["vendor"], o["description"], o["account"]] for o in out if o["split"] == s])
    st = stats(out, spec, corpus)
    st["escalate_fraction_of_hard_from_case_weights"] = escalate_arithmetic(spec)
    st["template_redraws"] = generate.redraws
    manifest = {"seed": seed, "rows_requested": rows,
                "spec_sha256": spec_hash, "corpus_sha256": corpus_hash,
                "generator_sha256": sha256_bytes(Path(__file__).read_bytes()),
                "spec_path": "data/synthetic/spec/generative_spec.yaml",
                "source": "synthetic",
                "notes": ["escalate rows carry account=General/Other Expense and escalate=true in metadata",
                          "metadata is row-aligned with transactions and never a feature",
                          "top-10 vendor share is a heuristic gate measured over ALL rows of a class",
                          "synthetic-only: do not quote accuracy on this data as real-world accuracy"],
                "stats": st}
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
