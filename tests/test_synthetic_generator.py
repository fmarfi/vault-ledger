"""Synthetic generator: determinism, vendor-disjoint splits, dedup, schema."""
import csv
import importlib.util
from collections import Counter
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("gen_tx", ROOT / "data/synthetic/generate_transactions.py")
gen = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gen)

N = 2000


def read(p):
    with open(p, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


@pytest.fixture(scope="module")
def runs(tmp_path_factory):
    a, b, c = (tmp_path_factory.mktemp(x) for x in "abc")
    gen.run(7, N, a)
    gen.run(7, N, b)
    gen.run(8, N, c)
    return a, b, c


FILES = ["transactions_{s}.csv", "metadata_{s}.csv", "manifest_{s}.json",
         "splits/train_{s}.csv", "splits/val_{s}.csv", "splits/test_{s}.csv"]


def test_same_seed_byte_identical(runs):
    a, b, _ = runs
    for f in FILES:
        assert (a / f.format(s=7)).read_bytes() == (b / f.format(s=7)).read_bytes(), f


def test_other_seed_differs(runs):
    a, _, c = runs
    assert (a / "transactions_7.csv").read_bytes() != (c / "transactions_8.csv").read_bytes()


def test_vendor_disjoint_splits(runs):
    a = runs[0]
    meta = read(a / "metadata_7.csv")
    tx = read(a / "transactions_7.csv")
    canon_split, raw_split = {}, {}
    for m, t in zip(meta, tx):
        assert canon_split.setdefault(m["vendor_canonical"], m["split"]) == m["split"]
        if t["vendor"]:   # bank-feed rows have no vendor field; their vendor_canonical still decides the split
            assert raw_split.setdefault(t["vendor"].lower(), m["split"]) == m["split"]
    sizes = Counter(m["split"] for m in meta)
    assert set(sizes) == {"train", "val", "test"}
    assert 0.6 < sizes["train"] / N < 0.8


def test_split_files_match_metadata(runs):
    a = runs[0]
    meta = read(a / "metadata_7.csv")
    for sp in ("train", "val", "test"):
        rows = read(a / f"splits/{sp}_7.csv")
        assert list(rows[0]) == ["vendor", "description", "account"]
        assert len(rows) == sum(m["split"] == sp for m in meta)


def test_schema_dups_and_header(runs):
    a = runs[0]
    tx = read(a / "transactions_7.csv")
    meta = read(a / "metadata_7.csv")
    assert len(tx) == len(meta) == N
    assert list(tx[0]) == gen.TX_COLS and list(meta[0]) == gen.META_COLS
    dup = sum(c - 1 for c in Counter((t["vendor"], t["description"], t["amount"]) for t in tx).values())
    assert dup / N < 0.02
    assert {m["source"] for m in meta} == {"synthetic"}
    assert {m["difficulty"] for m in meta} <= {"easy", "hard", "ambiguous"}
    man = (a / "manifest_7.json").read_text()
    assert gen.sha256(gen.SPEC) in man and '"seed": 7' in man


def test_label_noise_only_in_train(runs):
    meta = read(runs[0] / "metadata_7.csv")
    tx = read(runs[0] / "transactions_7.csv")
    for m, t in zip(meta, tx):
        if t["account"] != m["true_account"]:
            assert m["split"] == "train" and "label_flip" in m["noise_applied"]


def test_fine_category_matches_account(runs):
    import sys
    sys.path.insert(0, str(ROOT / "data/synthetic/spec"))
    from fine_categories import PARENT
    for m in read(runs[0] / "metadata_7.csv"):
        assert PARENT[m["fine_category"]] == m["true_account"]


def test_real_vendors_and_missing_fields(runs):
    meta = read(runs[0] / "metadata_7.csv")
    tx = read(runs[0] / "transactions_7.csv")
    real = sum(m["archetype"].startswith("real_") for m in meta) / N
    bank = [t for m, t in zip(meta, tx) if "vendor_in_description" in m["noise_applied"]]
    assert 0.3 < real < 0.7
    assert 0.07 < len(bank) / N < 0.17 and all(t["vendor"] == "" for t in bank)
    assert 0.15 < sum(m["vat_rate"] == "" for m in meta) / N < 0.35


def test_no_test_set_vendor_in_real_lexicon():
    import json
    import pandas as pd
    lex = ROOT / "data/synthetic/spec/corpus/real_vendors.json"
    tests = list((ROOT / "data/external/combined").glob("test_*.csv"))
    if not tests:
        pytest.skip("public test sets not downloaded")
    from vault_ledger.classifier.memory import vendor_key
    s = importlib.util.spec_from_file_location("lex", ROOT / "data/synthetic/spec/build_real_lexicon.py")
    spec_mod = importlib.util.module_from_spec(s)
    s.loader.exec_module(spec_mod)
    held = set()
    for p in tests:
        held |= {vendor_key(spec_mod.clean_name(v)) for v in pd.read_csv(p, usecols=["vendor"]).vendor.dropna().astype(str)}
    held.discard("")
    lexicon = json.loads(lex.read_text(encoding="utf-8"))
    assert not {vendor_key(spec_mod.clean_name(a)) for v in lexicon for a in [v["canonical"], *v["aliases"]]} & held
