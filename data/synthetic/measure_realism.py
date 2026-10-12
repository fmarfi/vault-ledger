"""Read-only realism counters for a generated draw (revision 2).

Run: PYTHONPATH=src .venv/bin/python data/synthetic/measure_realism.py [seed ...]
Reports, per seed, over data/synthetic/generated/{transactions,metadata}_<seed>.csv:
  frozen_price_row_share   rows of vendors (canonical, >=10 easy rows) whose modal amount covers > 50% of
                           the vendor's rows AND that are not declared fixed-price in the corpus
  frozen_critic_definition rows of vendors with >=10 rows and <= 3 distinct amounts (round-2 critic's count)
  order_number_share       rows whose description carries an order/booking number (Order|Bestelling + digits)
  integer_euro_share       amounts ending in .00
  out_of_range_by_account  easy rows outside the CURRENT spec amount_ranges (total)
  top15_vendors            15 most frequent canonical vendors with their verified flag
This is a measurement tool, not a gate; the enforcing tests live in tests/test_synth_generator.py.
"""
import csv
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
GEN = HERE / "generated"
ORDER_RX = re.compile(r"\b(order|bestelling|bestelnummer|ordernummer)\b[^0-9]{0,12}\d{5,}", re.I)


def load(seed, gen_dir=GEN):
    with open(gen_dir / ("transactions_%s.csv" % seed), newline="", encoding="utf-8") as f:
        tx = list(csv.DictReader(f))
    with open(gen_dir / ("metadata_%s.csv" % seed), newline="", encoding="utf-8") as f:
        meta = list(csv.DictReader(f))
    return tx, meta


def fixed_price_vendors():
    out = set()
    for p in (HERE / "spec" / "corpus").glob("*.json"):
        j = json.loads(p.read_text())
        if "vendors" not in j or "archetypes" not in j:
            continue
        fixed_a = {k for k, a in j["archetypes"].items() if a.get("fixed_price")}
        out.update(v["name"] for v in j["vendors"] if v["archetype"] in fixed_a)
    return out


def frozen(tx, meta, fixed):
    by = defaultdict(list)
    for t, m in zip(tx, meta):
        if m["difficulty"] == "easy":
            by[m["vendor_canonical"]].append(t["amount"])
    rows_f = rows_c = 0
    n = len(tx)
    for name, amts in by.items():
        if len(amts) < 10:
            continue
        c = Counter(amts)
        if c.most_common(1)[0][1] / len(amts) > 0.5 and name not in fixed:
            rows_f += len(amts)
        if len(c) <= 3:
            rows_c += len(amts)
    return round(rows_f / n, 4), round(rows_c / n, 4)


def m_unv(meta, vendor):
    for m in meta:
        if m["vendor_canonical"] == vendor:
            return m["vendor_unverified"]
    return "false"


def report(seed, spec=None):
    tx, meta = load(seed)
    n = len(tx)
    fixed = fixed_price_vendors()
    f_share, c_share = frozen(tx, meta, fixed)
    spec = spec or yaml.safe_load((HERE / "spec" / "generative_spec.yaml").read_text())
    rng = spec.get("amount_ranges")
    oor = Counter()
    cnt = Counter()
    for t, m in zip(tx, meta):
        if m["difficulty"] != "easy":
            continue
        a = t["account"]
        cnt[a] += 1
        if rng:
            lo, hi = rng[a]["total"]
            if not (lo <= float(t["amount"]) <= hi):
                oor[a] += 1
    vc = Counter(m["vendor_canonical"] for m in meta)
    acct_of = {}
    for t, m in zip(tx, meta):
        acct_of.setdefault(m["vendor_canonical"], t["account"])
    per_acct = defaultdict(Counter)
    for t, m in zip(tx, meta):
        if m["difficulty"] == "easy":
            per_acct[t["account"]][m["vendor_canonical"]] += 1
    unv = {m["vendor_canonical"]: m["vendor_unverified"] for m in meta}
    return {
        "seed": seed, "rows": n,
        "frozen_price_row_share": f_share, "frozen_critic_definition": c_share,
        "order_number_share": round(sum(1 for t in tx if ORDER_RX.search(t["description"])) / n, 4),
        "integer_euro_share": round(sum(1 for t in tx if t["amount"].endswith(".00")) / n, 4),
        "out_of_range_by_account": {a: oor[a] for a in sorted(cnt)} if rng else "n/a (no amount_ranges)",
        "top15_vendors": [(v, c, "UNVERIFIED" if unv[v] == "true" else "verified") for v, c in vc.most_common(15)],
        "top5_per_account_verified_share": round(
            sum(1 for a in per_acct for v, _ in per_acct[a].most_common(5) if m_unv(meta, v) != "true")
            / max(1, sum(len(per_acct[a].most_common(5)) for a in per_acct)), 3),
        "unverified_row_share": round(sum(1 for m in meta if m["vendor_unverified"] == "true") / n, 4),
        "top15_verified_share": round(sum(1 for v, _ in vc.most_common(15) if unv[v] != "true") / 15, 3),
    }


if __name__ == "__main__":
    for s in (sys.argv[1:] or ["1234", "4321"]):
        print(json.dumps(report(s), indent=1))
