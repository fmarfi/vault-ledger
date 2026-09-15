import pytest

from vault_ledger.extraction.field_parser import parse_fields
from vault_ledger.synthetic_samples import SAMPLES


@pytest.mark.parametrize("sample", SAMPLES, ids=[s.name for s in SAMPLES])
def test_vendor_and_description_are_separate_fields(sample):
    """M3 checkpoint: vendor and description must never blend into one string.

    This is Report 1's explicitly flagged risk -- test it directly rather
    than trusting it as a side effect of the other field assertions below.
    """
    fields = parse_fields(sample.text)
    assert fields.vendor != fields.description
    assert fields.description not in fields.vendor
    assert fields.vendor not in fields.description


@pytest.mark.parametrize("sample", SAMPLES, ids=[s.name for s in SAMPLES])
def test_all_fields_parsed_correctly(sample):
    fields = parse_fields(sample.text)
    assert fields.vendor == sample.expected_vendor
    assert fields.description == sample.expected_description
    assert fields.amount == pytest.approx(sample.expected_amount)
    assert fields.paid == sample.expected_paid
    assert fields.date is not None
