"""Fixed chart of accounts for the MVP (Report 1, item 1).

Deliberately flat and small (8 accounts). Not per-client, not hierarchical yet
-- see Report 1 "Explicitly NOT ASAP" and Report 4's note on the DragoNet
taxonomy as the future expansion path once this needs to grow.
"""

CASH_BANK = "Cash/Bank"
ACCOUNTS_PAYABLE = "Accounts Payable"
UTILITIES_EXPENSE = "Utilities Expense"
OFFICE_SUPPLIES_EXPENSE = "Office Supplies Expense"
PROFESSIONAL_SERVICES_EXPENSE = "Professional Services Expense"
RENT_EXPENSE = "Rent Expense"
TRAVEL_EXPENSE = "Travel & Transport Expense"
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
    GENERAL_EXPENSE,
}

ALL_ACCOUNTS = MECHANICAL_ACCOUNTS | EXPENSE_ACCOUNTS


def is_valid_expense_account(account: str) -> bool:
    return account in EXPENSE_ACCOUNTS
