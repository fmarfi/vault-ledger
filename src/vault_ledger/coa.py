"""Fixed chart of accounts for the MVP (Report 1, item 1).

Deliberately flat and small (9 accounts). Not per-client, not hierarchical yet
-- see Report 1 "Explicitly NOT ASAP" and Report 4's note on the DragoNet
taxonomy as the future expansion path once this needs to grow.

Grown from 8 to 9 accounts (added Software & Subscriptions Expense) after a
real SaaS billing receipt (GitHub Copilot) had no honest home in the
original 8 -- see git history. entry_rules.py checks membership in
EXPENSE_ACCOUNTS dynamically, so adding an account here is the only code
change needed; it doesn't touch the rules layer itself.
"""

CASH_BANK = "Cash/Bank"
ACCOUNTS_PAYABLE = "Accounts Payable"
UTILITIES_EXPENSE = "Utilities Expense"
OFFICE_SUPPLIES_EXPENSE = "Office Supplies Expense"
PROFESSIONAL_SERVICES_EXPENSE = "Professional Services Expense"
RENT_EXPENSE = "Rent Expense"
TRAVEL_EXPENSE = "Travel & Transport Expense"
SOFTWARE_SUBSCRIPTIONS_EXPENSE = "Software & Subscriptions Expense"
GENERAL_EXPENSE = "General/Other Expense"

# Mechanical accounts: never a classifier prediction target, only used by the
# rules layer to construct the credit side of an entry.
MECHANICAL_ACCOUNTS = {CASH_BANK, ACCOUNTS_PAYABLE}

# Expense accounts: the classifier's label space (step 3 in Report 1).
EXPENSE_ACCOUNTS = {
    UTILITIES_EXPENSE,
    OFFICE_SUPPLIES_EXPENSE,
    PROFESSIONAL_SERVICES_EXPENSE,
    RENT_EXPENSE,
    TRAVEL_EXPENSE,
    SOFTWARE_SUBSCRIPTIONS_EXPENSE,
    GENERAL_EXPENSE,
}

ALL_ACCOUNTS = MECHANICAL_ACCOUNTS | EXPENSE_ACCOUNTS


def is_valid_expense_account(account: str) -> bool:
    return account in EXPENSE_ACCOUNTS
