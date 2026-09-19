import pytest

from vault_ledger.classifier.fusion_classifier import FusionClassifier
from vault_ledger.coa import UTILITIES_EXPENSE, OFFICE_SUPPLIES_EXPENSE


def _toy_classifier() -> FusionClassifier:
    classifier = FusionClassifier()
    classifier.fit(
        vendors=[
            "CityPower & Gas Utility Co",
            "Aqua Municipal Water",
            "Acme Office Supplies Inc",
            "Staples Business Depot",
        ],
        descriptions=[
            "Electricity and gas usage for March",
            "Water usage for February",
            "Printer paper and toner cartridges",
            "Boxes of pens and sticky notes",
        ],
        accounts=[
            UTILITIES_EXPENSE,
            UTILITIES_EXPENSE,
            OFFICE_SUPPLIES_EXPENSE,
            OFFICE_SUPPLIES_EXPENSE,
        ],
    )
    return classifier


def test_predict_returns_account_and_confidence():
    classifier = _toy_classifier()
    account, confidence = classifier.predict(
        "CityPower & Gas Utility Co", "Electricity and gas usage for March"
    )
    assert account == UTILITIES_EXPENSE
    assert 0.0 <= confidence <= 1.0


def test_uses_both_fields_not_just_vendor():
    """An unseen vendor should still classify correctly from description alone,
    proving the fusion isn't silently degenerating into vendor-only lookup."""
    classifier = _toy_classifier()
    account, _ = classifier.predict(
        "Totally New Vendor Ltd", "Water usage for February"
    )
    assert account == UTILITIES_EXPENSE


def test_predict_before_fit_raises():
    classifier = FusionClassifier()
    try:
        classifier.predict("x", "y")
        assert False, "expected RuntimeError"
    except RuntimeError:
        pass


def test_fast_classifier_matches_sklearn(tmp_path):
    from vault_ledger.classifier.fast_inference import FastClassifier, export_fast_model

    classifier = _toy_classifier()
    path = tmp_path / "model.json"
    export_fast_model(classifier, path)
    fast = FastClassifier.load(path)

    cases = [
        ("CityPower & Gas Utility Co", "Electricity and gas usage for March"),
        ("Unseen Vendor Ltd", "Printer paper and toner"),
        ("", ""),
        ("Ünïcode Café", "water; 100% (usage)"),
    ]
    for vendor, description in cases:
        expected_account, expected_conf = classifier.predict(vendor, description)
        account, conf = fast.predict(vendor, description)
        assert account == expected_account
        assert conf == pytest.approx(expected_conf, abs=1e-9)


def test_fusion_module_import_is_light():
    import subprocess
    import sys

    code = (
        "import sys; import vault_ledger.pipeline, vault_ledger.classifier.fusion_classifier;"
        "assert 'sklearn' not in sys.modules and 'scipy' not in sys.modules "
        "and 'pandas' not in sys.modules"
    )
    subprocess.run([sys.executable, "-c", code], check=True)
