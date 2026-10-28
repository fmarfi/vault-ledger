import numpy as np
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from vaultledger.model.mask import argmax_then_mask, joint_decode, valid_pairs
from vaultledger.taxonomy import load_taxonomy

TAX = load_taxonomy()


def _check(d, direction):
    ok = valid_pairs(TAX, direction)
    assert ok[d.macro, d.micro], "micro must be a child of macro and allowed for the direction"
    assert 0.0 <= d.prob <= 1.0 + 1e-9


@pytest.mark.parametrize("decoder", [joint_decode, argmax_then_mask])
def test_10k_random_draws_no_violations(decoder):
    rng = np.random.default_rng(0)
    for i in range(10_000):
        direction = "IN" if i % 2 else "OUT"
        d = decoder(TAX, rng.normal(0, 5, TAX.n_macro), rng.normal(0, 5, TAX.n_micro), direction)
        _check(d, direction)


@settings(max_examples=300, deadline=None)
@given(
    st.lists(st.floats(-50, 50), min_size=TAX.n_macro, max_size=TAX.n_macro),
    st.lists(st.floats(-50, 50), min_size=TAX.n_micro, max_size=TAX.n_micro),
    st.sampled_from(["IN", "OUT"]),
)
def test_property_joint(lM, lm, direction):
    d = joint_decode(TAX, np.array(lM), np.array(lm), direction)
    _check(d, direction)
    assert abs(sum(p for *_, p in d.top) - 1.0) < 1e-6 or len(d.top) < valid_pairs(TAX, direction).sum()


def test_joint_prefers_consistent_pair():
    # Model says OUT-only "salaries" strongly, but the row is money IN: must not pick it.
    lM = np.zeros(TAX.n_macro)
    lm = np.zeros(TAX.n_micro)
    lm[TAX.micro_index["salaries"]] = 20
    d = joint_decode(TAX, lM, lm, "IN")
    assert TAX.micro_names[d.micro] != "salaries"
