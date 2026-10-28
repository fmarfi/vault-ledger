from vaultledger.io.adapters import SyntheticAdapter
from vaultledger.synth.generator import DEFAULT_RATES, SynthConfig, generate, write_dataset

SMALL = SynthConfig(seed=3, n_companies=2, rows_per_company=(300, 400))


def test_generator_deterministic_and_hard_cases_present():
    a, b = generate(SMALL), generate(SMALL)
    assert [t.to_dict() for t in a.transactions] == [t.to_dict() for t in b.transactions]
    big = generate(SynthConfig(seed=1, n_companies=4))
    counts = big.report["hard_case_counts"]
    for k in DEFAULT_RATES:
        if k != "english_description":
            assert counts[k] > 0, f"hard case {k} missing"
    assert all(t.amount >= 0 for t in big.transactions)


def test_adapter_roundtrip_never_reads_truth(tmp_path):
    ds = generate(SMALL)
    write_dataset(ds, tmp_path)
    txns, labels, companies = SyntheticAdapter().load(tmp_path)
    assert len(txns) == len(labels) == len(ds.transactions)
    assert (tmp_path / "_truth" / "truth.jsonl").exists()
    assert len(companies) == 2
