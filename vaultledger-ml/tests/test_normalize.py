from vaultledger.normalize import normalize_counterparty


def test_normalize_strips_processor_prefix():
    assert normalize_counterparty("CCV*ALBERT HEIJN 1234 DELFT") == "albert heijn delft"
    assert normalize_counterparty("BEA, Betaalautomaat Shell 12345678") == "shell"
    assert normalize_counterparty("") == ""
