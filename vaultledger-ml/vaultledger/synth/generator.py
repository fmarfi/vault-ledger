"""Seeded synthetic transaction generator (spec section 7).

A PIPELINE-TEST FIXTURE: it proves the code runs end to end and that each
hard case is handled. Nothing trained on it is shipped or quoted as accuracy.

Output (write_dataset):
  transactions.jsonl, labels.jsonl, companies.json   -- what a real adapter gives
  _truth/truth.jsonl                                  -- hidden ground truth; eval only
  generator_report.json                               -- counts per hard case
"""
from __future__ import annotations

import json
import random
from collections import Counter
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

import yaml

from ..schemas import CompanyConfig, Label, Transaction
from ..taxonomy import Taxonomy, load_taxonomy

CATALOG_PATH = Path(__file__).with_name("vendors.yaml")

DEFAULT_RATES = {
    "processor_prefix": 0.15,  # CCV*ALBERT HEIJN 1234 DELFT
    "truncation": 0.05,
    "case_noise": 0.15,
    "typo": 0.04,
    "empty_description": 0.06,
    "empty_name": 0.02,
    "ambiguous_vendor": 0.04,
    "generic_name": 0.03,
    "misregistered_activity": 0.05,
    "missing_activity": 0.5,
    "label_noise": 0.03,
    "uncategorized_label": 0.05,
    "english_description": 0.25,  # templates already mix NL/EN; this is informational
}

_PROCESSORS = ["CCV*", "SumUp *", "BEA, Betaalautomaat ", "Zettle_*", "SQ *", "PP*", "Mollie*", "iDEAL "]
_RECURRENCE_WEIGHT = {"weekly": 4.0, "monthly": 2.0, "adhoc": 1.0}
_MONTHS = ["januari", "februari", "maart", "april", "mei", "juni", "juli", "augustus",
           "september", "oktober", "november", "december"]
_ACCOUNT_NAMES_NL = {
    "sales_domestic": "Omzet binnenland", "sales_eu": "Omzet EU", "sales_non_eu": "Omzet buiten EU",
    "other_income": "Overige opbrengsten", "purchases_inventory": "Inkoop goederen",
    "subcontracting": "Uitbesteed werk", "freight_in": "Vrachtkosten inkoop", "salaries": "Lonen en salarissen",
    "payroll_tax_pension": "Sociale lasten en pensioen", "travel_reimbursement": "Reiskostenvergoeding",
    "training_education": "Opleidingskosten", "rent": "Huur", "energy": "Energie", "water": "Water",
    "cleaning_maintenance": "Schoonmaak en onderhoud", "software_subscriptions": "Software en abonnementen",
    "hardware": "Computerapparatuur", "telecom_internet": "Telefoon en internet",
    "office_supplies": "Kantoorbenodigdheden", "fuel": "Brandstof", "public_transport": "Openbaar vervoer",
    "parking": "Parkeerkosten", "car_lease": "Leasekosten auto", "taxi_ride_hailing": "Taxikosten",
    "advertising": "Reclame en advertenties", "representation_meals": "Representatiekosten",
    "gifts_relations": "Relatiegeschenken", "accounting_fees": "Accountantskosten",
    "legal_fees": "Juridische kosten", "consulting": "Advieskosten", "bank_fees": "Bankkosten",
    "interest": "Rente", "insurance": "Verzekeringen", "vat_payment": "Af te dragen btw",
    "vat_refund": "Te vorderen btw", "corporate_income_tax": "Vennootschapsbelasting",
    "other_taxes": "Overige belastingen", "own_account_transfer": "Kruisposten",
    "loan_repayment": "Lening o/g", "owner_withdrawal": "Privé-opnamen", "owner_deposit": "Privé-stortingen",
}


@dataclass
class SynthConfig:
    seed: int = 7
    n_companies: int = 8
    rows_per_company: tuple[int, int] = (400, 900)
    months: int = 12
    start: date = date(2025, 1, 1)
    generated_vendors_per_micro: int = 10
    rates: dict | None = None

    @classmethod
    def from_dict(cls, d: dict) -> "SynthConfig":
        d = dict(d or {})
        if "rows_per_company" in d:
            d["rows_per_company"] = tuple(d["rows_per_company"])
        if isinstance(d.get("start"), str):
            d["start"] = date.fromisoformat(d["start"])
        return cls(**d)


@dataclass
class Dataset:
    transactions: list[Transaction]
    labels: list[Label]
    companies: list[CompanyConfig]
    truth: list[dict]
    report: dict


class _Gen:
    def __init__(self, cfg: SynthConfig, tax: Taxonomy):
        self.cfg = cfg
        self.tax = tax
        self.rng = random.Random(cfg.seed)
        self.rates = {**DEFAULT_RATES, **(cfg.rates or {})}
        cat = yaml.safe_load(CATALOG_PATH.read_text(encoding="utf-8"))
        self.cities = cat["_cities"]
        self.people = cat["_people"]
        self.generic = cat["_generic_names"]
        self.ambiguous = cat["_ambiguous"]
        self.cat = {k: v for k, v in cat.items() if not k.startswith("_")}
        missing = set(tax.micro_names) - set(self.cat)
        if missing:
            raise ValueError(f"vendor catalog has no entry for {sorted(missing)}")
        self.pool = {m: self._vendor_pool(m) for m in tax.micro_names}
        # A stable activity text per vendor (as a registry would give).
        self.vendor_activity: dict[str, str] = {}
        self.counts: Counter = Counter()

    # -- catalog ------------------------------------------------------------
    def _vendor_pool(self, micro: str) -> list[str]:
        spec = self.cat[micro]
        names: list[str] = []
        for v in spec.get("vendors", []):
            if "{person}" in v:
                names += [v.replace("{person}", p) for p in self.people]
            else:
                names.append(v)
        gen = spec.get("gen")
        if gen:
            combos = [f"{p} {s} {x}".strip() for p in gen["prefix"] for s in gen["stem"] for x in gen["suffix"]]
            local = random.Random(f"{self.cfg.seed}-{micro}")
            local.shuffle(combos)
            names += combos[: self.cfg.generated_vendors_per_micro]
        return list(dict.fromkeys(names))

    def _activity_for(self, vendor: str, micro: str) -> str:
        if vendor not in self.vendor_activity:
            acts = self.cat[micro].get("activity") or []
            self.vendor_activity[vendor] = self.rng.choice(acts) if acts else ""
        return self.vendor_activity[vendor]

    # -- text ---------------------------------------------------------------
    def _fill(self, template: str, d: date, n: int) -> str:
        return (template.replace("{month}", _MONTHS[d.month - 1]).replace("{year}", str(d.year))
                .replace("{n}", str(n)).replace("{city}", self.rng.choice(self.cities)))

    def _typo(self, s: str) -> str:
        if len(s) < 4:
            return s
        i = self.rng.randrange(1, len(s) - 1)
        op = self.rng.choice(["swap", "drop", "dup"])
        if op == "swap":
            return s[:i] + s[i + 1] + s[i] + s[i + 2:]
        if op == "drop":
            return s[:i] + s[i + 1:]
        return s[:i] + s[i] + s[i:]

    def _noisy_name(self, name: str, hard: list[str]) -> str:
        r = self.rates
        if self.rng.random() < r["processor_prefix"]:
            store = self.rng.randint(100, 9999)
            name = f"{self.rng.choice(_PROCESSORS)}{name.upper()} {store} {self.rng.choice(self.cities).upper()}"
            hard.append("processor_prefix")
        if self.rng.random() < r["typo"]:
            name = self._typo(name)
            hard.append("typo")
        if self.rng.random() < r["case_noise"]:
            name = self.rng.choice([name.upper(), name.lower(), "  ".join(name.split())])
            hard.append("case_noise")
        if len(name) > 24 and self.rng.random() < r["truncation"]:
            name = name[:24]
            hard.append("truncation")
        return name

    # -- companies ----------------------------------------------------------
    def _company_coa(self, cid: str) -> tuple[dict[str, str], dict[str, str]]:
        """Per-company COA (spec 7.4): renames with codes, random merges inside a macro.

        Returns (micro -> account id, account id -> name). Splits (one-to-many)
        are left to ML-M8, where the company mapping is built.
        """
        micro_to_acc: dict[str, str] = {}
        accounts: dict[str, str] = {}
        code = 4000
        for macro in self.tax.macro_names:
            children = [m for m in self.tax.micro_names if self.tax.macro_of(m) == macro]
            i = 0
            while i < len(children):
                group = [children[i]]
                if i + 1 < len(children) and self.rng.random() < 0.15:  # merge two
                    group.append(children[i + 1])
                acc_id = str(code)
                name = " / ".join(_ACCOUNT_NAMES_NL[m] for m in group)
                accounts[acc_id] = f"{acc_id} {name}"
                for m in group:
                    micro_to_acc[m] = acc_id
                code += 10
                i += len(group)
        accounts["9999"] = "9999 Nog te verdelen"  # the company's Uncategorized bucket
        return micro_to_acc, accounts

    def company(self, idx: int):
        cid = f"synth-{idx:02d}"
        micros = list(self.tax.micro_names)
        # Each company uses 60-95% of the categories, with its own long-tailed mix.
        used = [m for m in micros if self.rng.random() < self.rng.uniform(0.6, 0.95)]
        weights = {m: _RECURRENCE_WEIGHT[self.cat[m]["recurrence"]] * self.rng.lognormvariate(0, 1.0) for m in used}
        vendors = {m: self.rng.sample(self.pool[m], k=min(len(self.pool[m]), self.rng.randint(1, 4))) for m in used}
        micro_to_acc, accounts = self._company_coa(cid)
        n_rows = self.rng.randint(*self.cfg.rows_per_company)
        own_iban = f"NL{self.rng.randint(10, 99)}INGB{self.rng.randint(10**9, 10**10 - 1)}"
        return cid, weights, vendors, micro_to_acc, accounts, n_rows, own_iban

    # -- rows ---------------------------------------------------------------
    def row(self, cid: str, k: int, micro: str, vendor: str, d: date):
        r = self.rates
        spec = self.cat[micro]
        hard: list[str] = []
        allowed = self.tax.micros[micro].allowed_direction
        direction = allowed if allowed != "BOTH" else ("OUT" if self.rng.random() < 0.85 else "IN")
        mu, sigma = spec["amount"]
        amount = Decimal(str(self.rng.lognormvariate(mu, sigma))).quantize(Decimal("0.01"), ROUND_HALF_UP)
        if self.rng.random() < 0.1:
            amount = amount.quantize(Decimal("1")) // 10 * 10 or Decimal("10")
        desc = self._fill(self.rng.choice(spec["desc"]), d, self.rng.randint(1, 9999))
        name = vendor

        if micro in {m for opts in self.ambiguous.values() for m in opts} and self.rng.random() < r["ambiguous_vendor"]:
            choices = [v for v, opts in self.ambiguous.items() if micro in opts]
            name = self.rng.choice(choices)
            desc = self._fill(self.rng.choice(self.ambiguous[name][micro]), d, self.rng.randint(1, 9999))
            hard.append("ambiguous_vendor")
        elif self.rng.random() < r["generic_name"]:
            name = self.rng.choice(self.generic)
            hard.append("generic_name")

        activity = self._activity_for(name, micro)
        if activity and self.rng.random() < r["misregistered_activity"]:
            wrong = self.rng.choice([m for m in self.tax.micro_names if m != micro and self.cat[m].get("activity")])
            activity = self.rng.choice(self.cat[wrong]["activity"])
            hard.append("misregistered_activity")
        if self.rng.random() < r["missing_activity"]:
            activity = ""
            hard.append("missing_activity")

        if self.rng.random() < r["empty_description"]:
            desc = ""
            hard.append("empty_description")
        canonical = name
        name = self._noisy_name(name, hard)
        if self.rng.random() < r["empty_name"]:
            name = ""
            hard.append("empty_name")

        iban = None
        if direction == "IN" or self.cat[micro]["recurrence"] == "monthly":
            iban = f"NL{self.rng.randint(10, 99)}RABO{self.rng.randint(10**9, 10**10 - 1)}"
        vat = spec.get("vat")
        txn = Transaction(
            txn_id=f"{cid}-{k:05d}", company_id=cid, date=d, amount=amount, direction=direction,
            counterparty_name=name, description=desc, counterparty_iban=iban,
            activity_text=activity or None,
            vat_rate=None if vat is None or self.rng.random() < 0.6 else Decimal(str(vat)),
        )
        for h in hard:
            self.counts[h] += 1
        return txn, canonical, hard


def generate(cfg: SynthConfig | dict | None = None, tax: Taxonomy | None = None) -> Dataset:
    cfg = cfg if isinstance(cfg, SynthConfig) else SynthConfig.from_dict(cfg or {})
    tax = tax or load_taxonomy()
    g = _Gen(cfg, tax)
    txns: list[Transaction] = []
    labels: list[Label] = []
    truth: list[dict] = []
    companies: list[CompanyConfig] = []
    days = cfg.months * 30
    for ci in range(cfg.n_companies):
        cid, weights, vendors, micro_to_acc, accounts, n_rows, own_iban = g.company(ci)
        companies.append(CompanyConfig(cid, [own_iban], accounts))
        micros = list(weights)
        w = [weights[m] for m in micros]
        for k in range(n_rows):
            micro = g.rng.choices(micros, weights=w)[0]
            vendor = g.rng.choice(vendors[micro])
            d = cfg.start + timedelta(days=g.rng.randrange(days))
            txn, canonical, hard = g.row(cid, k, micro, vendor, d)
            label_micro, quality, acc = micro, "OK", micro_to_acc[micro]
            if g.rng.random() < g.rates["uncategorized_label"]:
                label_micro, quality, acc = "uncategorized", "LOW", "9999"
                g.counts["uncategorized_label"] += 1
            elif g.rng.random() < g.rates["label_noise"]:
                ok = tax.direction_ok(txn.direction)
                label_micro = g.rng.choice([m for j, m in enumerate(tax.micro_names) if ok[j] and m != micro])
                acc = micro_to_acc[label_micro]
                g.counts["label_noise"] += 1
            txns.append(txn)
            labels.append(Label(txn.txn_id, acc, tax.macro_of(label_micro), label_micro, "SYNTHETIC", quality))
            truth.append({"txn_id": txn.txn_id, "true_macro": tax.macro_of(micro), "true_micro": micro,
                          "vendor_canonical": canonical, "hard_cases": hard})
    report = {
        "disclaimer": "Synthetic pipeline-test fixture. Not indicative of real-world accuracy.",
        "seed": cfg.seed, "taxonomy_version": tax.version, "n_companies": cfg.n_companies,
        "n_transactions": len(txns), "rates": g.rates,
        "hard_case_counts": {k: g.counts.get(k, 0) for k in DEFAULT_RATES if k != "english_description"},
        "class_counts": dict(Counter(t["true_micro"] for t in truth).most_common()),
        "n_vendors": len({t["vendor_canonical"] for t in truth}),
    }
    return Dataset(txns, labels, companies, truth, report)


def write_dataset(ds: Dataset, out_dir: str | Path) -> Path:
    out = Path(out_dir)
    (out / "_truth").mkdir(parents=True, exist_ok=True)
    with open(out / "transactions.jsonl", "w", encoding="utf-8") as f:
        for t in ds.transactions:
            f.write(json.dumps(t.to_dict(), ensure_ascii=False) + "\n")
    with open(out / "labels.jsonl", "w", encoding="utf-8") as f:
        for lab in ds.labels:
            f.write(json.dumps(lab.to_dict(), ensure_ascii=False) + "\n")
    (out / "companies.json").write_text(json.dumps([c.__dict__ for c in ds.companies], indent=1, ensure_ascii=False), encoding="utf-8")
    with open(out / "_truth" / "truth.jsonl", "w", encoding="utf-8") as f:
        for t in ds.truth:
            f.write(json.dumps(t, ensure_ascii=False) + "\n")
    (out / "generator_report.json").write_text(json.dumps(ds.report, indent=1, ensure_ascii=False), encoding="utf-8")
    return out


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser(description="Write the synthetic pipeline-test fixture.")
    ap.add_argument("--out", default="data/synth")
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--companies", type=int, default=8)
    a = ap.parse_args()
    path = write_dataset(generate(SynthConfig(seed=a.seed, n_companies=a.companies)), a.out)
    print(f"wrote {path} ({json.loads((path / 'generator_report.json').read_text())['n_transactions']} rows)")
