"""Seeded synthetic transaction generator (revision 3-lean).

Samples account from the class prior, vendor from a per-account Zipf law,
description from the corpus (vendor-consistent family and language), amount
from the per-account lognormal, then applies the noise model. Recurring
accounts get monthly series (same vendor, same day of month).

Output (all under --out, default data/synthetic/generated/):
  transactions_<seed>.csv   vendor,description,date,amount,paid,account
  metadata_<seed>.csv       hidden truth, same schema as draw 4321 (never a feature)
  splits/{train,val,test}_<seed>.csv   vendor,description,account (vendor-disjoint)
  manifest_<seed>.json      seed, spec/corpus sha256, counts

Synthetic, cold-start only. Never write into labeled_transactions.csv from here.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import json
import re
from statistics import NormalDist
from collections import Counter, defaultdict
from pathlib import Path

import sys

import numpy as np
import yaml

HERE = Path(__file__).resolve().parent
SPEC = HERE / "spec" / "generative_spec.yaml"
CORPUS = HERE / "spec" / "corpus"
sys.path.insert(0, str(HERE / "spec"))
from fine_categories import PARENT, fine_for  # noqa: E402

META_COLS = ["id", "source", "archetype", "difficulty", "escalate", "noise_applied", "language",
             "vendor_unverified", "vendor_canonical", "true_account", "hard_case", "split",
             "desc_family", "doc_type", "vat_rate", "net_amount", "fine_category"]
# bank-feed lines that carry the vendor inside the description (vendor field empty)
BANK_LINES = ["CARD PURCHASE {mm}/{dd} {VENDOR} CARD {n4}", "POS {VENDOR} {n6}", "{VENDOR} {n8}",
              "BEA, Betaalpas {VENDOR},PAS{n3} NR:{n6} {dd}.{mm}.{yy}", "SEPA Incasso {Vendor} Kenmerk {n10} {short}",
              "iDEAL {Vendor} {n16} {short}", "SEPA Overboeking {Vendor} Omschrijving: {short}",
              "DEBIT CARD {VENDOR} {mm}/{dd}", "Pinbetaling {Vendor} {dd}-{mm}-{yy}", "ACH DEBIT {VENDOR} {n9}"]
TX_COLS = ["vendor", "description", "date", "amount", "paid", "account"]
NL_MONTHS = ["januari", "februari", "maart", "april", "mei", "juni", "juli", "augustus",
             "september", "oktober", "november", "december"]
EN_MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August",
             "September", "October", "November", "December"]
ABBREV = [("Betaling", "bet."), ("betaling", "bet."), ("Factuur", "fact."), ("factuur", "fact."),
          ("Invoice", "inv."), ("invoice", "inv."), ("Payment", "pmt"), ("payment", "pmt"),
          ("Referentie", "ref."), ("Reference", "ref."), ("Kenmerk", "kenm."), ("Overboeking", "overb."),
          ("Incasso", "inc."), ("Abonnement", "abo."), ("abonnement", "abo."), ("Subscription", "subscr.")]
ABBREV += [(m, m[:3]) for m in NL_MONTHS + EN_MONTHS if len(m) > 4] + [
    ("algemeen doorlopend", "alg. doorl."), ("periode", "per."), ("Periode", "per."), ("Referentie", "Ref"),
    ("Factuurnummer", "Factuurnr."), ("Invoice number", "Inv. no."), ("Pinbetaling", "PIN"), ("Bestelling", "best."),
    ("Kenmerk", "Kenm"), ("Total", "Tot."), ("totaal", "tot."), ("Order", "Ord.")]
ABBREV_ELIGIBLE = 0.80   # measured share of rows with an abbreviable word (seed 2026); rescales the rate to all rows
ALIAS_ELIGIBLE = 0.86    # measured share of rows whose vendor has a non-canonical alias
OCR = [("o", "0"), ("O", "0"), ("l", "1"), ("i", "1"), ("S", "5"), ("B", "8"), ("e", "c"), ("rn", "m")]
GENERIC_DESC = ["Diversen", "Payment", "Betaling", "pmt", "Services", "Incasso bet.", "iDEAL Betaling",
                "Overboeking", "Card payment"]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def corpus_hash() -> str:
    h = hashlib.sha256()
    for p in sorted(CORPUS.glob("*.json")):
        h.update(p.name.encode())
        h.update(p.read_bytes())
    return h.hexdigest()


class Gen:
    def __init__(self, seed: int):
        self.seed = seed
        self.rng = np.random.default_rng(seed)
        self.spec = yaml.safe_load(SPEC.read_text(encoding="utf-8"))
        self.vendors = json.loads((CORPUS / "vendors.json").read_text(encoding="utf-8"))
        self.desc = json.loads((CORPUS / "descriptions.json").read_text(encoding="utf-8"))
        self.generic = json.loads((CORPUS / "generic_phrasings.json").read_text(encoding="utf-8"))
        self.hard = json.loads((CORPUS / "hard_cases.json").read_text(encoding="utf-8"))
        s = self.spec
        self.accounts = [a for a in s["class_prior"] if a != "tag"]
        self.start = dt.date.fromisoformat(s["date_range"]["start"])
        self.end = dt.date.fromisoformat(s["date_range"]["end"])
        self.by_acc = defaultdict(list)
        for v in self.vendors:
            if v["account"] in self.desc:
                self.by_acc[v["account"]].append(v)
        expo = s["vendor_zipf"]["exponent"]
        self.zipf = {}
        for a, vs in self.by_acc.items():
            vs.sort(key=lambda v: (-v["freq_4321"], v["canonical"]))
            w = 1.0 / np.arange(1, len(vs) + 1) ** expo
            self.zipf[a] = w / w.sum()
        ws = {a: 1.0 / np.arange(1, len(vs) + 1) ** s["vendor_zipf"]["series_exponent"] for a, vs in self.by_acc.items()}
        self.zipf_series = {a: w / w.sum() for a, w in ws.items()}
        self.kw = json.loads((CORPUS / "keyword_phrasings.json").read_text(encoding="utf-8"))
        self.real, self.real_w = defaultdict(list), {}
        rv = s.get("real_vendors")
        if rv:   # real vendor names, ranked by how often they occur in the public data
            for v in json.loads((CORPUS / rv["file"]).read_text(encoding="utf-8")):
                if v["account"] in self.desc:
                    self.real[v["account"]].append(v)
            for a, vs in self.real.items():
                vs.sort(key=lambda v: (-v["rows"], v["canonical"]))
                w = 1.0 / np.arange(1, len(vs) + 1) ** rv["zipf_exponent"]
                self.real_w[a] = w / w.sum()
        self.vmeta = {v["canonical"]: v for v in self.vendors}
        # brand tokens: a template naming one vendor must not be used for another
        self.brand = {}
        for v in self.vendors:
            tok = re.split(r"[\s.*-]", v["canonical"])[0].lower()
            if len(tok) >= 3:
                self.brand.setdefault(tok, set()).add(v["canonical"])

    def mentions_other(self, text, canon):
        own = re.split(r"[\s.*-]", canon)[0].lower()
        for w in set(re.findall(r"[a-z0-9]{3,}", text.lower())):
            if w in self.brand and w != own and canon not in self.brand[w]:
                return True
        return False

    # ---------- primitives ----------
    def choice(self, seq, p=None):
        return seq[int(self.rng.choice(len(seq), p=p))]

    def pick_vendor(self, acc, series=False):
        """A corpus vendor, or (spec real_vendors.share) a real vendor of the same account."""
        rv = self.spec.get("real_vendors")
        if rv and self.real.get(acc) and self.rng.random() < rv["share"]:
            return self.choice(self.real[acc], p=self.real_w[acc])
        return self.choice(self.by_acc[acc], p=(self.zipf_series if series else self.zipf)[acc])

    def bank_line(self, vendor, desc, date):
        """The vendor inside a bank-feed description, as a bank export shows a card or SEPA payment."""
        name = re.sub(r"\s+(B\.?V\.?|N\.?V\.?|Ltd\.?|LLC|Inc\.?|GmbH)$", "", vendor, flags=re.I)[:22]
        rep = {"VENDOR": name.upper(), "Vendor": name, "mm": f"{date.month:02d}", "dd": f"{date.day:02d}",
               "yy": f"{date.year % 100:02d}", "short": desc[:28].rstrip()}
        t = self.choice(BANK_LINES)
        def sub(m):
            k = m.group(1)
            if k in rep:
                return rep[k]
            return self.digits(int(k[1:])) if k[1:].isdigit() else m.group(0)
        return re.sub(r"\s+", " ", re.sub(r"\{(\w+)\}", sub, t)).strip()

    def amount(self, acc):
        p = self.spec["amount_lognormal"][acc]
        c = self.spec["amount_clip"]
        return float(np.clip(round(float(self.rng.lognormal(p["mu"], p["sigma"])), 2), c["min"], c["max"]))

    def rand_date(self):
        return self.start + dt.timedelta(days=int(self.rng.integers(0, (self.end - self.start).days + 1)))

    def pick_template(self, v):
        acc = v["account"]
        fams = {f: n for f, n in v["families"].items() if f in self.desc[acc]}
        lang = self.choice(sorted(v["languages"]), p=self._norm(v["languages"]))
        ds = self.spec["description_source"]
        x = self.rng.random()
        if x < ds["generic_phrasing_share"] + ds["keyword_phrasing_share"]:
            gl = lang if lang in ("nl", "en") else self.choice(["nl", "en"])
            src = self.generic if x < ds["generic_phrasing_share"] else self.kw[acc]
            pool = [g for g in src if g["language"] == gl]
            t = dict(self.choice(pool))
            fam = self.choice(sorted(fams)) if fams else "_none"
            ref = self.desc[acc].get(fam) or [x for f in self.desc[acc].values() for x in f]
            r0 = self.choice(ref)
            t["vat_rate"] = r0["vat_rate"]
            t["doc_type"] = "bank"
            t["family"] = fam
            return t
        if fams:
            fam = self.choice(sorted(fams), p=self._norm(fams))
            pool = self.desc[acc][fam]
        else:
            fam = "_none"
            pool = [x for f in self.desc[acc].values() for x in f]
        pool = [t for t in pool if not self.mentions_other(t["text"], v["canonical"])] or pool
        same = [t for t in pool if t["language"] == lang] or pool
        t = dict(self.choice(same))
        t["family"] = fam
        return t

    @staticmethod
    def _norm(d):
        k = sorted(d)
        w = np.array([d[x] for x in k], float)
        return w / w.sum()

    def digits(self, n):
        return "".join(str(int(x)) for x in self.rng.integers(0, 10, n))

    def render(self, text, date, total, vat_rate):
        net = total if vat_rate in (None, "rc", "0") else round(total / (1 + float(vat_rate)), 2)
        vat = round(total - net, 2)
        nl = lambda x: f"{x:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        due = date + dt.timedelta(days=30)
        rep = {"date": date.strftime("%d-%m-%Y"), "due": due.strftime("%d-%m-%Y"),
               "isodate": date.isoformat(), "quarter": f"Q{(date.month - 1) // 3 + 1} {date.year}",
               "maand": NL_MONTHS[date.month - 1], "month": EN_MONTHS[date.month - 1], "year": str(date.year),
               "total": f"{total:.2f}", "net": f"{net:.2f}", "vat": f"{vat:.2f}",
               "total_nl": nl(total), "net_nl": nl(net), "vat_nl": nl(vat)}

        def sub(m):
            k = m.group(1)
            if k in rep:
                return rep[k]
            if k.startswith("n") and k[1:].isdigit():
                return self.digits(int(k[1:]))
            return m.group(0)
        return re.sub(r"\{(\w+)\}", sub, text), net

    def pick_alias(self, canon, aliases):
        others = [a for a in aliases if a != canon]
        if others and self.rng.random() < self.spec["noise_rates"]["vendor_legal_suffix_variation"] / ALIAS_ELIGIBLE:
            return self.choice(others)
        return canon

    # ---------- noise ----------
    def noise(self, vendor, desc, doc_type):
        g = self.spec.get("grain", {})
        mult, cap, scaled = g.get("noise_multiplier", 1.0), g.get("max_artifact_rate", 1.0), set(g.get("scaled", []))
        r = {k: (min(v * mult, cap) if k in scaled else v)
             for k, v in self.spec["noise_rates"].items() if k != "tag"}
        applied = []
        u = self.rng.random
        if doc_type == "receipt_pos" and u() < r["store_terminal_code"]:
            tag = self.choice([f"BEA NR:{self.digits(4)} Term {self.digits(2)}", f"Kassa {self.digits(2)}"])
            desc = f"{tag} {desc}" if u() < 0.5 else f"{desc} {tag}"
            applied.append("store_terminal_code")
        hits = [(a, b) for a, b in ABBREV if re.search(rf"\b{re.escape(a)}\b", desc)]
        if hits and u() < min(1.0, r["abbreviation_nl_en"] / ABBREV_ELIGIBLE):
            if hits:
                a, b = self.choice(hits)
                desc = re.sub(rf"\b{re.escape(a)}\b", b, desc, count=1)
                applied.append("abbreviation_nl_en")
        if u() < r["missing_or_generic_description"]:
            desc = self.choice(GENERIC_DESC)
            applied.append("missing_or_generic_description")
        if u() < r["typo_char_swap_drop_dup"]:
            idx = [i for i in range(1, len(desc) - 1) if desc[i].isalpha() and desc[i + 1].isalpha()]
            if idx:
                i = self.choice(idx)
                op = int(self.rng.integers(0, 3))
                desc = (desc[:i] + desc[i + 1] + desc[i] + desc[i + 2:] if op == 0 else
                        desc[:i] + desc[i + 1:] if op == 1 else desc[:i] + desc[i] + desc[i:])
                applied.append("typo_char_swap_drop_dup")
        if u() < r["ocr_confusion"]:
            hits = [(a, b) for a, b in OCR if a in desc]
            if hits:
                a, b = self.choice(hits)
                pos = [m.start() for m in re.finditer(re.escape(a), desc)]
                p = self.choice(pos)
                desc = desc[:p] + b + desc[p + len(a):]
                applied.append("ocr_confusion")
        if u() < r["truncated_description"] and len(desc) > 24:
            desc = desc[: int(self.rng.integers(14, min(len(desc) - 4, 40)))].rstrip()
            applied.append("truncated_description")
        if u() < r["casing_variation"]:
            if u() < 0.5:
                vendor = vendor.upper()
            else:
                desc = desc.upper() if u() < 0.8 else desc.lower()
            applied.append("casing_variation")
        if g:
            if u() < g["punctuation_drop"] and re.search(r" - |[,.]", desc):
                desc = re.sub(r" - ", " ", desc) if " - " in desc else re.sub(r"[,.]", "", desc, count=1)
                applied.append("punctuation_drop")
            if u() < g["vendor_ocr_confusion"]:
                hits = [(a, b) for a, b in OCR if a in vendor]
                if hits:
                    a, b = self.choice(hits)
                    vendor = vendor.replace(a, b, 1)
                    applied.append("vendor_ocr_confusion")
            if u() < g["accent_strip_or_junk"]:
                if u() < 0.5 and " " in desc:
                    desc = desc.rsplit(" ", 1)[0] + " " + desc.rsplit(" ", 1)[1][:2]
                else:
                    desc = self.choice(["*", "#", "/", "~"]) + desc
                applied.append("junk_or_cut_token")
            if u() < g["whitespace_noise"]:
                k = int(self.rng.integers(0, 3))
                desc = desc.replace(" ", "  ", 1) if k == 0 else (" " + desc if k == 1 else desc + " 	")
                applied.append("whitespace_noise")
        return vendor, desc, applied

    # ---------- rows ----------
    def make_row(self, v, date, amount, tpl=None, hard=None):
        if hard is None:
            tpl = tpl or self.pick_template(v)
            alias = self.pick_alias(v["canonical"], v["aliases"])
            applied = ["vendor_legal_suffix_variation"] if alias != v["canonical"] else []
            text, lang, doc_type, vat_rate, fam = tpl["text"], tpl["language"], tpl["doc_type"], tpl["vat_rate"], tpl["family"]
            acc, arch, diff, esc, hc, canon = v["account"], v["archetype"], "easy", False, "", v["canonical"]
            unverified = v["vendor_unverified"]
        else:
            vm = self.vmeta.get(hard["vendor_canonical"])
            aliases = sorted(set((vm["aliases"] if vm else []) + [hard["vendor"]]))
            alias = self.pick_alias(hard["vendor_canonical"], aliases)
            applied = ["vendor_legal_suffix_variation"] if alias != hard["vendor_canonical"] else []
            text, lang, doc_type, vat_rate, fam = hard["text"], hard["language"], hard["doc_type"], hard["vat_rate"], ""
            acc, arch, diff, esc, hc = hard["account"], hard["archetype"], hard["difficulty"], hard["escalate"], hard["hard_case"]
            canon, unverified = hard["vendor_canonical"], bool(vm and vm["vendor_unverified"])
        if lang == "mixed":
            applied.append("nl_en_mix_in_one_row")
        desc, net = self.render(text, date, amount, vat_rate)
        vendor, desc, more = self.noise(alias, desc, doc_type)
        applied += more
        mf = self.spec.get("missing_fields")
        vat_out = vat_rate or "0"
        if mf:
            if self.rng.random() < mf["vendor_in_description"]:
                desc, vendor, doc_type = self.bank_line(vendor, desc, date), "", "bank"
                applied.append("vendor_in_description")
            if self.rng.random() < mf["no_vat"]:
                vat_out = ""
                applied.append("no_vat")
        if hard is None:
            fine = v.get("fine_category") if PARENT.get(v.get("fine_category")) == acc else fine_for(arch, acc)
        else:
            fine = fine_for(arch, acc)
        paid = bool(self.rng.random() < self.spec["paid_prob_by_doc_type"][doc_type])
        return {"vendor": vendor, "description": desc, "date": date.isoformat(), "amount": f"{amount:.2f}",
                "paid": "True" if paid else "False", "account": acc,
                "source": "synthetic", "archetype": arch, "difficulty": diff, "escalate": "true" if esc else "false",
                "noise_applied": "|".join(applied), "language": lang,
                "vendor_unverified": "true" if unverified else "false", "vendor_canonical": canon,
                "true_account": acc, "hard_case": hc, "desc_family": "" if fam == "_none" else fam,
                "doc_type": doc_type, "vat_rate": vat_out,
                "net_amount": f"{net:.2f}", "fine_category": fine}

    def months(self):
        out, d = [], self.start.replace(day=1)
        while d <= self.end:
            out.append(d)
            d = (d.replace(day=28) + dt.timedelta(days=4)).replace(day=1)
        return out

    def generate(self, n):
        s = self.spec
        n_hard = int(round(n * s["hard_cases"]["share"]))
        n_easy = n - n_hard
        prior = np.array([s["class_prior"][a] for a in self.accounts])
        prior = prior / prior.sum()
        # the prior is for all rows; subtract the expected account mix of the hard rows
        mixw = s["hard_cases"]["mix"]
        tot = sum(mixw.values())
        exp_hard = np.zeros(len(self.accounts))
        for kind, wk in mixw.items():
            hs = [h for h in self.hard if h["hard_case"] == kind]
            for h in hs:
                exp_hard[self.accounts.index(h["account"])] += n_hard * wk / tot / len(hs)
        target = np.clip(prior * n - exp_hard, 0, None)
        raw = target / target.sum() * n_easy
        counts = np.floor(raw).astype(int)
        for i in np.argsort(-(raw - counts), kind="stable")[: n_easy - counts.sum()]:
            counts[i] += 1
        rows, seen = [], set()
        months = self.months()
        rec = s["recurring"]

        def add(build):
            for _ in range(s["dedup"]["redraws"]):
                row = build()
                k = (row["vendor"], row["description"], row["amount"])
                if k not in seen:
                    break
            seen.add(k)
            rows.append(row)

        for acc, c in zip(self.accounts, counts):
            vs, w = self.by_acc[acc], self.zipf[acc]
            n_rec = int(round(c * rec["share_of_rows"].get(acc, 0.0)))
            made = 0
            q = float(self.rng.random())   # golden-ratio quantiles: series base amounts spread over the lognormal
            while made < n_rec:
                v = self.pick_vendor(acc, series=True)
                L = min(int(self.rng.integers(rec["series_length"]["min"], rec["series_length"]["max"] + 1)),
                        n_rec - made, len(months))
                m0 = int(self.rng.integers(0, len(months) - L + 1))
                day = int(self.rng.integers(1, 29))
                q = (q + 0.6180339887) % 1.0
                lp = s["amount_lognormal"][acc]
                base = round(float(np.clip(np.exp(lp["mu"] + lp["sigma"] * NormalDist().inv_cdf(min(max(q, 1e-6), 1 - 1e-6))),
                                           s["amount_clip"]["min"], s["amount_clip"]["max"])), 2)
                jit = rec["amount_jitter_sd"].get(acc, 0.0)
                step = int(self.rng.integers(1, L)) if L > 1 and self.rng.random() < rec["price_change_prob"] else None
                tpl = self.pick_template(v)
                for k in range(L):
                    date = months[m0 + k].replace(day=day)
                    a = base * (1 + self.rng.uniform(0.03, 0.10)) if step is not None and k >= step else base
                    a = round(max(1.0, a * (1 + self.rng.normal(0, jit))) if jit else a, 2)
                    first = [True]

                    def build(v=v, date=date, a=a, tpl=tpl, first=first):
                        t = tpl if first[0] else None   # redraw template only on a collision
                        first[0] = False
                        return self.make_row(v, date, a, tpl=t)
                    add(build)
                made += L
            for _ in range(c - n_rec):
                add(lambda: self.make_row(self.pick_vendor(acc), self.rand_date(), self.amount(acc)))

        mix = {k: v for k, v in s["hard_cases"]["mix"].items()}
        kinds = sorted(mix)
        pk = self._norm(mix)
        by_kind = defaultdict(list)
        for h in self.hard:
            by_kind[h["hard_case"]].append(h)
        for _ in range(n_hard):
            kind = self.choice(kinds, p=pk)

            def build(kind=kind):
                h = self.choice(by_kind[kind])
                return self.make_row(None, self.rand_date(), self.amount(h["account"]), hard=h)
            add(build)

        order = sorted(range(len(rows)), key=lambda i: (rows[i]["date"], i))
        rows = [rows[i] for i in order]
        for i, r in enumerate(rows):
            r["id"] = f"s{self.seed}-{i:05d}"
        self.assign_splits(rows)
        return rows

    def assign_splits(self, rows):
        frac = self.spec["split"]["fractions"]
        names = list(frac)
        cnt = Counter(r["vendor_canonical"] for r in rows)
        prim = {}
        for v, a in Counter((r["vendor_canonical"], r["account"]) for r in rows).most_common():
            prim.setdefault(v[0], v[1])
        by_acc = defaultdict(list)
        for v in sorted(cnt):
            by_acc[prim[v]].append(v)
        assign = {}
        for acc in sorted(by_acc):
            vs = by_acc[acc]
            tie = self.rng.random(len(vs))
            vs = [v for _, _, v in sorted(zip([-cnt[v] for v in vs], tie, vs))]
            total = sum(cnt[v] for v in vs)
            got = dict.fromkeys(names, 0)
            for v in vs:
                sp = max(names, key=lambda s: (frac[s] * total - got[s]) / frac[s])
                assign[v] = sp
                got[sp] += cnt[v]
        for r in rows:
            r["split"] = assign[r["vendor_canonical"]]
        ln = self.spec.get("label_noise")
        if ln:
            for r in rows:
                if r["split"] == "train" and self.rng.random() < ln["rate"]:
                    r["account"] = self.choice(ln["neighbours"][r["account"]])
                    r["noise_applied"] = "|".join(x for x in (r["noise_applied"], "label_flip") if x)


def write_csv(path: Path, rows, cols):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore", lineterminator="\n")
        w.writeheader()
        w.writerows(rows)


def run(seed: int, n: int, out: Path):
    g = Gen(seed)
    rows = g.generate(n)
    out = Path(out)
    write_csv(out / f"transactions_{seed}.csv", rows, TX_COLS)
    write_csv(out / f"metadata_{seed}.csv", rows, META_COLS)
    for sp in ("train", "val", "test"):
        write_csv(out / "splits" / f"{sp}_{seed}.csv", [r for r in rows if r["split"] == sp],
                  ["vendor", "description", "account"])
    dup = sum(c - 1 for c in Counter((r["vendor"], r["description"], r["amount"]) for r in rows).values())
    manifest = {"seed": seed, "rows": len(rows), "spec": str(SPEC.relative_to(HERE)),
                "spec_sha256": sha256(SPEC), "corpus_sha256": corpus_hash(),
                "generator_sha256": sha256(Path(__file__)), "dup_rate": round(dup / len(rows), 4),
                "split_rows": dict(sorted(Counter(r["split"] for r in rows).items())),
                "class_rows": dict(sorted(Counter(r["account"] for r in rows).items())),
                "split_class_rows": {sp: dict(sorted(Counter(r["account"] for r in rows if r["split"] == sp).items()))
                                     for sp in ("train", "val", "test")},
                "note": "synthetic, cold-start only; never quote accuracy on it as real-world"}
    (out / f"manifest_{seed}.json").write_text(json.dumps(manifest, indent=1) + "\n", encoding="utf-8")
    return rows, manifest


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--seed", type=int, required=True)
    ap.add_argument("--n", type=int, default=10000)
    ap.add_argument("--out", type=Path, default=HERE / "generated")
    a = ap.parse_args(argv)
    _, m = run(a.seed, a.n, a.out)
    print(json.dumps(m, indent=1))


if __name__ == "__main__":
    main()
