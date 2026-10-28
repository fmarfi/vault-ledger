import pytest

from vault_ledger.classifier import cascade
from vault_ledger.classifier.cascade import CascadeClassifier, build_cascade
from vault_ledger.pipeline import propose_entry


class Fixed:
    def __init__(self, account, confidence):
        self.account, self.confidence, self.calls = account, confidence, 0

    def predict(self, vendor, description):
        self.calls += 1
        return self.account, self.confidence


class DocModel(Fixed):
    def predict_document(self, vendor, description, amount, paid, date):
        self.calls += 1
        self.seen = (amount, paid, date)
        return self.account, self.confidence


def _broken():
    raise ImportError("no torch here")


class Crashes:
    def predict(self, vendor, description):
        raise RuntimeError("bad input")


def test_first_confident_model_decides_and_later_ones_are_not_asked():
    first, second = DocModel("Rent Expense", 0.9), Fixed("Utilities Expense", 0.99)
    c = CascadeClassifier([("a", lambda: first), ("b", lambda: second)])
    assert c.decide("Landlord BV", "huur", 1200.0, True, "2026-10-01") == ("Rent Expense", 0.9, "a")
    assert first.seen == (1200.0, True, "2026-10-01")
    assert second.calls == 0


def test_low_confidence_falls_through_to_the_next_model():
    c = CascadeClassifier([("a", lambda: Fixed("Rent Expense", 0.4)),
                           ("b", lambda: Fixed("Utilities Expense", 0.8))])
    assert c.decide("Eneco", "stroom") == ("Utilities Expense", 0.8, "b")


def test_nobody_confident_returns_the_most_confident_answer():
    c = CascadeClassifier([("a", lambda: Fixed("Rent Expense", 0.5)),
                           ("b", lambda: Fixed("Utilities Expense", 0.6)),
                           ("c", lambda: Fixed("General/Other Expense", 0.3))])
    assert c.decide("x", "y") == ("Utilities Expense", 0.6, "b")


def test_models_that_fail_to_load_or_run_are_skipped():
    c = CascadeClassifier([("broken", _broken), ("crashes", lambda: Crashes()),
                           ("tfidf", lambda: Fixed("Rent Expense", 0.95))])
    assert c.decide("x", "y") == ("Rent Expense", 0.95, "tfidf")


def test_fallbacks_load_only_when_needed():
    loads = []

    def loader(name, conf):
        def load():
            loads.append(name)
            return Fixed("Rent Expense", conf)
        return load

    c = CascadeClassifier([("a", loader("a", 0.9)), ("b", loader("b", 0.9))])
    assert loads == ["a"]
    c.decide("x", "y")
    assert loads == ["a"]


def test_no_working_model_raises():
    c = CascadeClassifier([("broken", _broken)])
    with pytest.raises(RuntimeError):
        c.decide("x", "y")


def test_default_order_is_most_engineered_dragonet_first_tfidf_last(monkeypatch):
    monkeypatch.delenv(cascade.ENV, raising=False)
    c = build_cascade(lambda: Fixed("Rent Expense", 0.9))
    assert c.stage_names == [f"dragonet:{n}" for n in cascade.DEFAULT_RUNS] + ["tfidf"]


def test_env_can_put_a_run_first_or_force_tfidf(monkeypatch, tmp_path):
    monkeypatch.setenv(cascade.ENV, "tfidf")
    assert build_cascade(lambda: Fixed("Rent Expense", 0.9)).stage_names == ["tfidf"]
    monkeypatch.setenv(cascade.ENV, f"dragonet:{tmp_path / 'mine'}")
    names = build_cascade(lambda: Fixed("Rent Expense", 0.9)).stage_names
    assert names[0] == "dragonet:mine" and names[-1] == "tfidf"


def test_pipeline_records_which_model_decided():
    c = CascadeClassifier([("a", lambda: Fixed("Rent Expense", 0.2)),
                           ("tfidf", lambda: Fixed("Rent Expense", 0.9))])
    result = propose_entry("Landlord BV", "huur oktober", 1200.0, True, None, c)
    assert result.decided_by == "tfidf"
    assert result.confidence == 0.9
    assert not result.needs_review
