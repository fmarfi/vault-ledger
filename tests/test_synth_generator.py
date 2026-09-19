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
        assert abs(frac - p) < 0.02, (a, frac, p)
    meta = read(big / "metadata_1234.csv")
    hard_frac = sum(1 for m in meta if m["difficulty"] != "easy") / n
    assert 0.10 <= hard_frac <= 0.15


def test_recurring_rent_on_first(big):
    tx = read(big / "transactions_1234.csv")
    meta = read(big / "metadata_1234.csv")
    rent = [t for t, m in zip(tx, meta) if t["account"] == "Rent Expense" and m["difficulty"] == "easy"]
    on_first = sum(1 for t in rent if t["date"].endswith("-01")) / len(rent)
    assert on_first > 0.85


def test_never_writes_production_files(big):
    names = {p.name for p in big.iterdir()}
    assert "labeled_transactions.csv" not in names
