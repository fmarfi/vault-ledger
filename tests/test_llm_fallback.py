import json
import urllib.error
from unittest.mock import MagicMock, patch

import pytest

from vault_ledger.extraction.llm_fallback import extract_fields_via_llm

try:
    import urllib.request

    urllib.request.urlopen("http://localhost:11434/api/tags", timeout=1)
    OLLAMA_AVAILABLE = True
except Exception:
    OLLAMA_AVAILABLE = False


def _mock_response(response_dict: dict) -> MagicMock:
    mock = MagicMock()
    mock.read.return_value = json.dumps({"response": json.dumps(response_dict)}).encode()
    mock.__enter__.return_value = mock
    return mock


def test_returns_none_when_ollama_unreachable():
    with patch("urllib.request.urlopen", side_effect=urllib.error.URLError("refused")):
        result = extract_fields_via_llm("some text")
    assert result is None


def test_returns_none_when_amount_is_hallucinated():
    """The model claims an amount that doesn't actually appear in the
    source text -- must be rejected, not trusted."""
    response = {
        "vendor": "Acme Inc",
        "description": "Widgets",
        "date": "2026-01-01",
        "amount": "999.99",
        "paid": True,
    }
    with patch("urllib.request.urlopen", return_value=_mock_response(response)):
        result = extract_fields_via_llm("Acme Inc\nTotal $10.00")
    assert result is None


def test_returns_fields_when_amount_is_grounded_in_source_text():
    response = {
        "vendor": "Acme Inc",
        "description": "Widgets",
        "date": "2026-01-01",
        "amount": "$10.00",
        "paid": True,
    }
    with patch("urllib.request.urlopen", return_value=_mock_response(response)):
        result = extract_fields_via_llm("Acme Inc\nTotal $10.00")
    assert result == {
        "vendor": "Acme Inc",
        "description": "Widgets",
        "date": "2026-01-01",
        "amount": 10.0,
        "paid": True,
    }


def test_returns_none_when_amount_is_real_but_not_on_the_total_line():
    """Grounded in the text, but it's the tax line, not the total."""
    response = {"vendor": "Acme Inc", "description": "Widgets", "amount": "$2.00", "paid": True}
    text = "Acme Inc\nSubtotal $10.00\nTax $2.00\nTotal $12.00"
    with patch("urllib.request.urlopen", return_value=_mock_response(response)):
        assert extract_fields_via_llm(text) is None


def test_accepts_largest_amount_when_total_lines_are_only_tax_or_subtotal_style():
    response = {"vendor": "Acme Inc", "description": "Widgets", "amount": "12.00", "paid": False}
    text = "Acme Inc\nTotal Tax $2.00\nAmount due $12.00"
    with patch("urllib.request.urlopen", return_value=_mock_response(response)):
        result = extract_fields_via_llm(text)
    assert result is not None and result["amount"] == 12.0


def test_accepts_amount_due_smaller_than_total_on_partial_payment():
    response = {"vendor": "Acme Inc", "description": "Widgets", "amount": "40.00", "paid": False}
    text = "Acme Inc\nTotal Amount 100.00\nAmount Due 40.00"
    with patch("urllib.request.urlopen", return_value=_mock_response(response)):
        result = extract_fields_via_llm(text)
    assert result is not None and result["amount"] == 40.0


def test_rejects_cash_tendered_even_though_it_is_the_largest_amount():
    response = {"vendor": "Acme Inc", "description": "Widgets", "amount": "50.00", "paid": True}
    text = "Acme Inc\nTotal 45.00\nCash 50.00"
    with patch("urllib.request.urlopen", return_value=_mock_response(response)):
        assert extract_fields_via_llm(text) is None


def test_logs_a_distinct_warning_when_ollama_is_unreachable(caplog):
    with patch("urllib.request.urlopen", side_effect=urllib.error.URLError("refused")):
        extract_fields_via_llm("some text")
    assert "unavailable" in caplog.text


def test_returns_none_when_vendor_or_description_missing():
    response = {"vendor": "", "description": "Widgets", "amount": "10.00", "paid": True}
    with patch("urllib.request.urlopen", return_value=_mock_response(response)):
        result = extract_fields_via_llm("Total $10.00")
    assert result is None


def test_returns_none_on_malformed_json_response():
    mock = MagicMock()
    mock.read.return_value = json.dumps({"response": "not valid json"}).encode()
    mock.__enter__.return_value = mock
    with patch("urllib.request.urlopen", return_value=mock):
        result = extract_fields_via_llm("some text")
    assert result is None


@pytest.mark.skipif(not OLLAMA_AVAILABLE, reason="Ollama not running locally")
def test_real_llm_extracts_from_realworld_receipt_text():
    """Integration test against the actual local model -- only runs when
    Ollama is reachable, so the rest of the suite stays fast/hermetic."""
    text = (
        "We received payment for your Example Corp subscription. Thanks!\n"
        "Date 2026-07-11\n"
        "Description Amount\n"
        "Widget Pro Plan - month\n"
        "$10.00 USD\n"
        "Tax $0.00 USD\n"
        "Total $10.00 USD*\n"
        "Example Corp, Inc."
    )
    result = extract_fields_via_llm(text)
    assert result is not None
    assert result["amount"] == pytest.approx(10.00)
    assert "Example Corp" in result["vendor"]
