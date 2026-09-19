import pytest

from vault_ledger import coa
from vault_ledger.rules.entry_rules import RuleViolation, construct_entry


def test_defaults_when_no_file():
    assert coa.active_expense_accounts() == coa.EXPENSE_ACCOUNTS
    assert coa.retired_expense_accounts() == []


def test_added_account_is_usable_by_the_rules_layer():
    coa.add_expense_account("Marketing Expense")
    entry = construct_entry("Marketing Expense", 50.0, paid=True)
    assert entry.total_debits == entry.total_credits == 50.0


def test_unknown_account_still_rejected_not_guessed():
    with pytest.raises(RuleViolation):
        construct_entry("Marketing Expense", 50.0, paid=True)


def test_retired_account_rejected_for_new_entries_but_kept_listed():
    coa.retire_expense_account(coa.RENT_EXPENSE)
    with pytest.raises(RuleViolation):
        construct_entry(coa.RENT_EXPENSE, 10.0, paid=True)
    assert coa.RENT_EXPENSE in coa.retired_expense_accounts()


def test_retired_account_can_be_added_back():
    coa.retire_expense_account(coa.RENT_EXPENSE)
    coa.add_expense_account(coa.RENT_EXPENSE)
    assert coa.RENT_EXPENSE in coa.active_expense_accounts()
    assert coa.RENT_EXPENSE not in coa.retired_expense_accounts()


def test_general_expense_cannot_be_retired():
    with pytest.raises(coa.AccountError):
        coa.retire_expense_account(coa.GENERAL_EXPENSE)


@pytest.mark.parametrize("bad", ["", "   ", "x" * 61, "cash/bank", "Accounts Payable"])
def test_bad_names_rejected(bad):
    with pytest.raises(coa.AccountError):
        coa.add_expense_account(bad)


def test_duplicate_is_case_insensitive():
    coa.add_expense_account("Marketing Expense")
    with pytest.raises(coa.AccountError):
        coa.add_expense_account("marketing expense")


def test_template_retires_dropped_accounts_instead_of_deleting():
    coa.apply_template("generic-us")
    assert "Payroll Expense" in coa.active_expense_accounts()
    assert coa.TRAVEL_EXPENSE in coa.retired_expense_accounts()
    assert coa.GENERAL_EXPENSE in coa.active_expense_accounts()


def test_every_template_keeps_the_fallback_account():
    for accounts in coa.TEMPLATES.values():
        assert coa.GENERAL_EXPENSE in accounts


def test_pipeline_falls_back_to_general_when_prediction_is_retired(monkeypatch):
    from vault_ledger import pipeline
    from vault_ledger.extraction.field_parser import ExtractedFields

    class StubClassifier:
        def predict(self, vendor, description):
            return coa.RENT_EXPENSE, 0.95

    monkeypatch.setattr(pipeline, "extract_raw_text", lambda path: "")
    monkeypatch.setattr(
        pipeline, "parse_fields", lambda text: ExtractedFields("Landlord", "March rent", None, 900.0, True)
    )
    coa.retire_expense_account(coa.RENT_EXPENSE)

    result = pipeline.run_pipeline("ignored.png", StubClassifier())

    assert result.predicted_account == coa.GENERAL_EXPENSE
    assert result.needs_review is True
    assert result.entry is not None
