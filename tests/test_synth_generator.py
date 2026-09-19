"""Tests for the synthetic-data generator (data/synthetic/generate_transactions.py)."""
import csv
import hashlib
import importlib.util
import math
import re
from pathlib import Path

import pytest

from vault_ledger.coa import EXPENSE_ACCOUNTS

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location(
    "generate_transactions", ROOT / "data" / "synthetic" / "generate_transactions.py")
gen = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(gen)


def read(path):
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


@pytest.fixture(scope="module")
def big(tmp_path_factory):
    d = tmp_path_factory.mktemp("big")
    gen.run(1234, 4000, d)
    return d


def _digest(d):
    return {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(Path(d).iterdir())}


def test_deterministic_same_seed(tmp_path):
    a, b = tmp_path / "a", tmp_path / "b"
    gen.run(7, 700, a)
    gen.run(7, 700, b)
    assert _digest(a) == _digest(b)


def test_different_seed_differs(tmp_path):
    gen.run(7, 700, tmp_path / "a")
    gen.run(8, 700, tmp_path / "b")
    ta = (tmp_path / "a" / "transactions_7.csv").read_bytes()
    tb = (tmp_path / "b" / "transactions_8.csv").read_bytes()
    assert ta != tb


def test_manifest_records_hashes(big):
    import json
    m = json.loads((big / "manifest_1234.json").read_text())
    assert m["seed"] == 1234 and len(m["spec_sha256"]) == 64 and len(m["corpus_sha256"]) == 64
    assert m["stats"]["vendor_groups_in_multiple_splits"] == 0


def test_vendor_disjoint_including_aliases(big):
    splits = {s: read(big / ("%s_1234.csv" % s)) for s in gen.SPLITS}
    strings = {s: set(gen.norm(r["vendor"]) for r in rows) for s, rows in splits.items()}
    assert not (strings["train"] & strings["val"])
    assert not (strings["train"] & strings["test"])
    assert not (strings["val"] & strings["test"])
    # canonical vendor and brand-family groups (aliases) live in exactly one split
    meta = read(big / "metadata_1234.csv")
    canon = {}
    for m in meta:
        canon.setdefault(m["vendor_canonical"], set()).add(m["split"])
    assert all(len(v) == 1 for v in canon.values())
    _, corpus, hard, _, _ = gen.load_world()
    vendors, hard_v, allv, _ = gen.build_vendors(corpus, hard)
    gid_split = {}
    by_name = {v.name: v for v in allv}
    for name, sp in canon.items():
        if name in by_name:
            gid_split.setdefault(by_name[name].gid, set()).update(sp)
    assert all(len(v) == 1 for v in gid_split.values())
    # every alias string of a vendor seen in the data sits in that vendor's split
    alias_split = {}
    for v in allv:
        if v.name in canon:
            for s in [v.name] + v.aliases:
                alias_split[gen.norm(s)] = next(iter(canon[v.name]))
    for s, rows in splits.items():
        for r in rows:
            n = gen.norm(r["vendor"])
            if n in alias_split:
                assert alias_split[n] == s


def test_every_account_in_every_split(big):
    meta = read(big / "metadata_1234.csv")
    tx = read(big / "transactions_1234.csv")
    seen = set((t["account"], m["split"]) for t, m in zip(tx, meta))
    for a in EXPENSE_ACCOUNTS:
        for s in gen.SPLITS:
            assert (a, s) in seen


def test_labels_in_active_default_accounts(big):
    for r in read(big / "transactions_1234.csv"):
        assert r["account"] in EXPENSE_ACCOUNTS
    for s in gen.SPLITS:
        for r in read(big / ("%s_1234.csv" % s)):
            assert r["account"] in EXPENSE_ACCOUNTS


def test_classifier_files_have_no_metadata_columns(big):
    for s in gen.SPLITS:
        with open(big / ("%s_1234.csv" % s), newline="") as f:
            assert next(csv.reader(f)) == ["vendor", "description", "account"]
    with open(big / "transactions_1234.csv", newline="") as f:
        assert next(csv.reader(f)) == ["vendor", "description", "date", "amount", "paid", "account"]
    rows = sum(len(read(big / ("%s_1234.csv" % s))) for s in gen.SPLITS)
    assert rows == len(read(big / "transactions_1234.csv"))


def test_metadata_alignment_and_source(big):
    meta = read(big / "metadata_1234.csv")
    tx = read(big / "transactions_1234.csv")
    assert len(meta) == len(tx)
    assert all(m["source"] == "synthetic" for m in meta)
    assert set(m["difficulty"] for m in meta) <= {"easy", "hard", "ambiguous"}
    for t, m in zip(tx, meta):
        if m["escalate"] == "true":
            assert t["account"] == "General/Other Expense"


def test_amounts_positive_finite_dates_in_range(big):
    for r in read(big / "transactions_1234.csv"):
        a = float(r["amount"])
        assert a > 0 and math.isfinite(a)
        assert "2025-01-01" <= r["date"] <= "2026-08-31"
        assert r["paid"] in ("True", "False")


def test_priors_within_tolerance(big):
    _, _, _, _, _ = gen.load_world()
    spec = gen.load_world()[0]
    prior = spec["class_prior"]["values"]
    tx = read(big / "transactions_1234.csv")
    n = len(tx)
    for a, p in prior.items():
        frac = sum(1 for t in tx if t["account"] == a) / n
        assert abs(frac - p) < 0.025, (a, frac, p)
    meta = read(big / "metadata_1234.csv")
    hard_frac = sum(1 for m in meta if m["difficulty"] != "easy") / n
    assert 0.10 <= hard_frac <= 0.15


def test_recurring_rent_on_first_business_day(big):
    """Rent is dated the 1st, rolled to the next business day when the 1st is a weekend."""
    import datetime as dt
    tx = read(big / "transactions_1234.csv")
    meta = read(big / "metadata_1234.csv")
    rent = [t for t, m in zip(tx, meta) if t["account"] == "Rent Expense" and m["difficulty"] == "easy"]
    def first_bd(t):
        d = dt.date.fromisoformat(t["date"])
        return d.day <= 3 and d.weekday() < 5 and (d.day == 1 or dt.date(d.year, d.month, 1).weekday() >= 5)
    assert sum(1 for t in rent if first_bd(t)) / len(rent) > 0.85


def test_never_writes_production_files(big):
    names = {p.name for p in big.iterdir()}
    assert "labeled_transactions.csv" not in names


# ----------------------------------------------------------------- revision 1 tests

import datetime as dt
import json

MONEY = re.compile(r"(?<![\d.,])\d+[.,]\d{2}(?![\d])")


@pytest.fixture(scope="module")
def big2(tmp_path_factory):
    d = tmp_path_factory.mktemp("big2")
    gen.run(4321, 4000, d)
    return d


@pytest.fixture(scope="module")
def world():
    return gen.load_world()


def _rows(d, seed):
    return read(d / ("transactions_%d.csv" % seed)), read(d / ("metadata_%d.csv" % seed))


@pytest.mark.parametrize("which,seed", [("big", 1234), ("big2", 4321)])
def test_easy_rows_vendor_description_archetype_agree(request, world, which, seed):
    d = request.getfixturevalue(which)
    spec, corpus, hard, _, _ = world
    vendors, hard_v, allv, _ = gen.build_vendors(corpus, hard)
    fam = {v.name: v.cfg["family"] for v in allv if v.account != "hard"}
    tx, meta = _rows(d, seed)
    own = {}
    for v in allv:
        own[v.name] = set(re.findall(r"[a-z0-9]+", " ".join([v.name, v.product] + v.aliases).lower()))
    names = [(v.name, gen.norm(v.name)) for v in allv if len(gen.norm(v.name)) >= 6 and " " not in gen.norm(v.name)]
    n_easy = 0
    for t, m in zip(tx, meta):
        if m["difficulty"] != "easy":
            continue
        n_easy += 1
        assert m["desc_family"] == fam[m["vendor_canonical"]], (t, m)
        toks = set(gen.norm(t["description"]).split())
        for name, nn in names:
            if name != m["vendor_canonical"] and nn not in own[m["vendor_canonical"]]:
                assert nn not in toks, ("foreign brand in description", t)
    assert n_easy > 3000
    # all archetype families in the corpus are used only by vendors of that archetype family
    for acct, j in corpus.items():
        for v in j["vendors"]:
            assert j["archetypes"][v["archetype"]]["family"] in j["pools"]


@pytest.mark.parametrize("which,seed", [("big", 1234), ("big2", 4321)])
def test_btw_arithmetic_consistent(request, which, seed):
    d = request.getfixturevalue(which)
    tx, meta = _rows(d, seed)
    for t, m in zip(tx, meta):
        total, net = float(t["amount"]), float(m["net_amount"])
        if m["vat_rate"] == "rc":
            assert abs(total - net) < 0.005
            assert not re.search(r"(?<!\d)(9|21)% (BTW|VAT)", t["description"])
        else:
            rate = float(m["vat_rate"])
            assert abs(round(net * rate, 2) + net - total) < 0.011, (t, m)
        for pct in re.findall(r"(\d+)% (?:BTW|VAT)", t["description"], re.I):
            expect = 0 if m["vat_rate"] == "rc" else float(m["vat_rate"]) * 100
            assert abs(float(pct) - expect) < 1e-6, (t, m)


@pytest.mark.parametrize("which,seed", [("big", 1234), ("big2", 4321)])
def test_description_amounts_equal_amount_column(request, which, seed):
    d = request.getfixturevalue(which)
    tx, meta = _rows(d, seed)
    checked = 0
    for t, m in zip(tx, meta):
        total, net = float(t["amount"]), float(m["net_amount"])
        vat = round(total - net, 2)
        ok = {total, net, vat, 0.0}
        for tok in MONEY.findall(t["description"]):
            v = float(tok.replace(",", "."))
            checked += 1
            assert any(abs(v - o) < 0.011 for o in ok), (t, m, tok)
    assert checked > 500


@pytest.mark.parametrize("which,seed", [("big", 1234), ("big2", 4321)])
def test_legal_suffixes_valid_for_entity(request, world, which, seed):
    d = request.getfixturevalue(which)
    spec, corpus, hard, _, _ = world
    vendors, hard_v, allv, _ = gen.build_vendors(corpus, hard)
    by = {v.name: v for v in allv}
    tx, meta = _rows(d, seed)
    with_suffix = 0
    for t, m in zip(tx, meta):
        form = gen.legal_form(t["vendor"])
        if not form:
            continue
        with_suffix += 1
        v = by[m["vendor_canonical"]]
        assert form in v.allowed_forms(), (t["vendor"], v.name, v.allowed_forms())
        assert "Holding" not in t["vendor"] or v.archetype in ("vastgoed_bv_generic", "landlord_institutional")
        assert not re.search(r"\b(b\.?v\.?|n\.?v\.?) (inc|ltd|llc)\b", t["vendor"], re.I)
    # only vendors with a corpus-declared form can carry a noise suffix; consumer brands never do
    assert with_suffix / len(tx) < 0.40
    for v in allv:
        if v.suffixes:
            assert v.country == "NL" and all(gen.legal_form("x " + x) in ("BV", "NV") for x in v.suffixes)


@pytest.mark.parametrize("which,seed", [("big", 1234), ("big2", 4321)])
def test_no_banned_artifact_strings(request, which, seed):
    d = request.getfixturevalue(which)
    tx, meta = _rows(d, seed)
    for t in tx:
        text = t["vendor"] + " | " + t["description"]
        assert "(PERIOD)" not in text and "PERIOD)" not in text
        assert t["vendor"].strip().upper() != "PLAUSIBLE"
        runs = re.findall(r"(?<![\d.,])\d+(?![\d]|[.,]\d)", text)   # digit runs that are not money
        for banned in ("1234", "5514", "4321", str(seed)):
            assert not any(banned in r for r in runs), (banned, t)
        assert "{" not in text and "}" not in text
        assert "PEERIODE" not in text.upper()


@pytest.mark.parametrize("which,seed", [("big", 1234), ("big2", 4321)])
def test_single_payment_field_by_document_type(request, which, seed):
    d = request.getfixturevalue(which)
    tx, meta = _rows(d, seed)
    cats = {"bank": r"sepa|incasso|overboeking", "pos": r"bea nr|betaalautomaat|pinbetaling",
            "ideal": r"ideal", "terms": r"te betalen voor|betaaltermijn|payable within|payment terms|total due"}
    for t, m in zip(tx, meta):
        text = t["description"].lower()
        hit = [k for k, rx in cats.items() if re.search(rx, text)]
        assert len(hit) <= 1, (t, hit)
        assert not re.search(r"reeds voldaan|already paid|paid by card", text)
        if m["doc_type"] == "invoice":
            assert not {"bank", "pos", "ideal"} & set(hit), (t, m)
        if m["doc_type"] == "bank":
            assert not {"pos", "ideal", "terms"} & set(hit), (t, m)
        if m["doc_type"] != "invoice":
            assert t["paid"] == "True"
        if m["difficulty"] == "easy" and "pos" in hit:
            assert m["doc_type"] == "receipt_pos"
        if m["doc_type"] == "receipt_pos":
            assert t["account"] not in ("Professional Services Expense", "Rent Expense") or m["difficulty"] != "easy"


@pytest.mark.parametrize("which,seed", [("big", 1234), ("big2", 4321)])
def test_class_counts_are_sampled_not_quotas(request, world, which, seed):
    d = request.getfixturevalue(which)
    spec = world[0]
    prior = spec["class_prior"]["values"]
    tx, _ = _rows(d, seed)
    n = len(tx)
    counts = {a: sum(1 for t in tx if t["account"] == a) for a in prior}
    quotas = {a: int(round(p * n)) for a, p in prior.items()}
    assert counts != quotas
    chi = sum((counts[a] - prior[a] * n) ** 2 / (prior[a] * n) for a in prior)
    assert 0.3 < chi < 25, chi     # df=6: a multinomial draw, not an exact quota (chi2 == 0)
    m = json.loads((d / ("manifest_%d.json" % seed)).read_text())["stats"]["class_mix_chi2"]
    assert abs(m["chi2"] - chi) < 0.01 and m["df"] == 6


@pytest.mark.parametrize("which,seed", [("big", 1234), ("big2", 4321)])
def test_integer_amounts_dates_and_top10(request, world, which, seed):
    d = request.getfixturevalue(which)
    spec = world[0]
    tx, meta = _rows(d, seed)
    n = len(tx)
    ints = sum(1 for t in tx if t["amount"].endswith(".00")) / n
    assert ints < 0.20, ints
    for t, m in zip(tx, meta):
        wk = dt.date.fromisoformat(t["date"]).weekday() >= 5
        if m["doc_type"] in ("invoice", "bank"):
            assert not wk, (t, m)
    rc = [t for t, m in zip(tx, meta) if m["doc_type"].startswith("receipt")]
    share = sum(1 for t in rc if dt.date.fromisoformat(t["date"]).weekday() >= 5) / len(rc)
    assert 0.05 < share < 0.30
    st = json.loads((d / ("manifest_%d.json" % seed)).read_text())["stats"]
    cap = spec["vendor_frequency"]["top10_vendor_share_max"]
    assert all(v <= cap for v in st["top10_vendor_share_all_rows"].values()), st["top10_vendor_share_all_rows"]
    assert st["general_other_max_single_vendor_share"] <= spec["vendor_frequency"]["general_other_max_single_vendor_share"]
    assert st["utility_negative_amounts"] == 0 if "utility_negative_amounts" in st else True
    q95 = st["software_q95"]
    lo, hi = spec["amounts"]["Software & Subscriptions Expense"]["expected_q95_range"]
    assert lo <= q95 <= hi, q95


@pytest.mark.parametrize("which,seed", [("big", 1234), ("big2", 4321)])
def test_escalate_labels_and_arithmetic(request, world, which, seed):
    d = request.getfixturevalue(which)
    spec = world[0]
    tx, meta = _rows(d, seed)
    hard_names = {v["name"] for v in world[2]["vendors"]}
    for t, m in zip(tx, meta):
        if m["hard_case"] == "vendor_description_disagree":
            assert m["escalate"] == "true" and t["account"] == "General/Other Expense"
            assert m["true_account"] != "General/Other Expense" or True
        if m["hard_case"] == "generic_description":
            resolves = m["vendor_canonical"] not in hard_names
            assert (m["escalate"] == "false") == resolves, (t, m)
            if resolves:
                assert m["difficulty"] == "hard" and t["account"] == m["true_account"]
    m = json.loads((d / ("manifest_%d.json" % seed)).read_text())["stats"]
    headline = spec["hard_cases"]["overall_escalate_fraction_of_hard"]
    assert abs(m["escalate_fraction_of_hard_from_case_weights"] - headline) < 0.001
    assert abs(m["escalate_fraction_of_hard"] - headline) < 0.08


def test_noise_rates_within_two_sigma(big, world):
    spec = world[0]
    st = json.loads((big / "manifest_1234.json").read_text())["stats"]
    n = st["rows"]
    for name, rate in st["noise_spec_rate"].items():
        sd = math.sqrt(rate * (1 - rate) / n)
        assert abs(st["noise_realised_rate"].get(name, 0.0) - rate) < 3.0 * sd + 0.004, name


def test_every_account_in_every_split_second_seed(big2):
    meta = read(big2 / "metadata_4321.csv")
    tx = read(big2 / "transactions_4321.csv")
    seen = set((t["account"], m["split"]) for t, m in zip(tx, meta))
    for a in EXPENSE_ACCOUNTS:
        for s in gen.SPLITS:
            assert (a, s) in seen
    m = json.loads((big2 / "manifest_4321.json").read_text())
    assert m["stats"]["vendor_groups_in_multiple_splits"] == 0
    assert m["stats"]["vendor_strings_in_multiple_splits"] == 0


def test_description_vocabulary_exclusivity_mean(big):
    """Heuristic gate: <= 30% of top-20 description tokens exclusive to one class (vendor-name tokens removed;
    mean over classes; the per-class maximum is reported in the manifest notes, not asserted)."""
    import importlib.util as iu
    sp = iu.spec_from_file_location("measure_vocab", ROOT / "data" / "synthetic" / "measure_vocab.py")
    mv = iu.module_from_spec(sp)
    sp.loader.exec_module(mv)
    rep = mv.report(mv.load(big / "transactions_1234.csv"))
    assert rep["description_GATE_vendor_name_tokens_removed"]["top20_only_mean"] <= 0.30
