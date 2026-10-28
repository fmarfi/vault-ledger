import pytest

from vaultledger.taxonomy import TaxonomyError, load_taxonomy

TAX = load_taxonomy()


def test_taxonomy_shape():
    assert TAX.n_micro == 41  # uncategorized is not a training target
    assert "SUSPENSE" not in TAX.macro_names
    assert "uncategorized" not in TAX.micro_names
    for j, m in enumerate(TAX.micro_names):
        assert TAX.macro_names[TAX.parent[j]] == TAX.macro_of(m)


def test_duplicate_micro_rejected(tmp_path):
    p = tmp_path / "t.yaml"
    p.write_text("taxonomy_version: x\nmacros:\n  A: {m: {allowed_direction: IN}}\n  B: {m: {allowed_direction: OUT}}\n")
    with pytest.raises(TaxonomyError):
        load_taxonomy(p)


def test_bad_direction_rejected(tmp_path):
    p = tmp_path / "t.yaml"
    p.write_text("taxonomy_version: x\nmacros:\n  A: {m: {allowed_direction: SIDEWAYS}}\n")
    with pytest.raises(TaxonomyError):
        load_taxonomy(p)
