from vaultledger.eval.splits import group_split, vendor_key
from vaultledger.synth.generator import SynthConfig, generate

SMALL = SynthConfig(seed=3, n_companies=2, rows_per_company=(300, 400))


def test_group_split_is_vendor_disjoint():
    ds = generate(SMALL)
    tr, te = group_split(ds.transactions, 0.2, seed=0)
    assert te and tr
    assert not {vendor_key(ds.transactions[i]) for i in tr} & {vendor_key(ds.transactions[i]) for i in te}
