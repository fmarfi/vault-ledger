import pytest

from vault_ledger.coa import CASH_BANK, ACCOUNTS_PAYABLE, UTILITIES_EXPENSE
from vault_ledger.rules.entry_rules import RuleViolation, construct_entry


def test_paid_entry_credits_cash_bank():
    entry = construct_entry(UTILITIES_EXPENSE, 120.0, paid=True)
    assert entry.total_debits == entry.total_credits == 120.0
    accounts = {line.account for line in entry.lines}
    assert accounts == {UTILITIES_EXPENSE, CASH_BANK}


def test_unpaid_entry_credits_accounts_payable():
    entry = construct_entry(UTILITIES_EXPENSE, 75.5, paid=False)
    assert entry.total_debits == entry.total_credits == 75.5
    accounts = {line.account for line in entry.lines}
    assert accounts == {UTILITIES_EXPENSE, ACCOUNTS_PAYABLE}


def test_debit_line_is_the_expense_account():
    entry = construct_entry(UTILITIES_EXPENSE, 50.0, paid=True)
    debit_line = next(line for line in entry.lines if line.debit > 0)
    assert debit_line.account == UTILITIES_EXPENSE
    assert debit_line.debit == 50.0


@pytest.mark.parametrize("amount", [0, -10.0])
def test_zero_or_negative_amount_rejected(amount):
    with pytest.raises(RuleViolation, match="R3"):
        construct_entry(UTILITIES_EXPENSE, amount, paid=True)


def test_unknown_account_rejected_not_guessed():
    with pytest.raises(RuleViolation, match="R2"):
        construct_entry("Not A Real Account", 10.0, paid=True)


def test_mechanical_account_rejected_as_expense_target():
    with pytest.raises(RuleViolation, match="R2"):
        construct_entry(CASH_BANK, 10.0, paid=True)


def test_entries_always_balance():
    for amount in (1.0, 99.99, 4200.5):
        entry = construct_entry(UTILITIES_EXPENSE, amount, paid=True)
        assert entry.total_debits == entry.total_credits
