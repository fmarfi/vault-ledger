"""Chart of accounts (Report 1, item 1).

The module-level constants below are the *default* 9-account set. Each
install can customize the expense accounts (diagnostics report, feature 3)
via data/accounts.json -- see the "Customizable expense accounts" section
at the bottom. Rules-layer validation goes through is_valid_expense_account(),
which reads the customized set, so nothing else needs to know about it.

Still flat, not hierarchical -- see Report 1 "Explicitly NOT ASAP" and
Report 4's note on the DragoNet taxonomy as the future expansion path.

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


# ---------------------------------------------------------------------------
# Customizable expense accounts
#
# Only the expense side is customizable: Cash/Bank and Accounts Payable stay
# fixed because the rules layer builds the credit line from them (R4).
#
# Retiring an account hides it from new entries but never deletes it, and
# renaming is "retire old + add new": existing ledger rows and training rows
# carry the old label string, so mutating it in place would orphan history.
#
# The classifier needs no change -- its label space is whatever labels its
# training data contains -- but a brand-new account has zero training rows, so
# it can't be *predicted* until a few documents have been corrected into it
# (the existing corrections -> retrain loop). See pipeline.run_pipeline for
# how predictions of a since-retired account are handled.
# ---------------------------------------------------------------------------
import json
from pathlib import Path

ACCOUNTS_PATH = Path(__file__).resolve().parents[2] / "data" / "accounts.json"
MAX_ACCOUNT_NAME_LEN = 60

TEMPLATES = {
    "default": sorted(EXPENSE_ACCOUNTS),
    "generic-us": [
        "Advertising & Marketing Expense",
        "Cost of Goods Sold",
        GENERAL_EXPENSE,
        "Insurance Expense",
        "Office Supplies Expense",
        "Payroll Expense",
        "Professional Fees Expense",
        "Rent Expense",
        SOFTWARE_SUBSCRIPTIONS_EXPENSE,
        "Travel & Meals Expense",
        "Utilities Expense",
    ],
    "generic-eu": [
        "Bank Charges Expense",
        GENERAL_EXPENSE,
        "Insurance Expense",
        "Marketing Expense",
        "Office Supplies Expense",
        "Professional Services Expense",
        "Purchases (Goods for Resale)",
        "Rent Expense",
        SOFTWARE_SUBSCRIPTIONS_EXPENSE,
        "Travel & Transport Expense",
        "Utilities Expense",
    ],
}


class AccountError(ValueError):
    """Raised for an invalid add/retire request (bad name, duplicate, protected)."""


def _load(path) -> dict:
    path = Path(path)
    if not path.exists():
        return {"active": sorted(EXPENSE_ACCOUNTS), "retired": []}
    return json.loads(path.read_text())


def _save(state: dict, path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=2, sort_keys=True))


def active_expense_accounts(path=None) -> set:
    return set(_load(path or ACCOUNTS_PATH)["active"])


def retired_expense_accounts(path=None) -> list:
    return sorted(_load(path or ACCOUNTS_PATH)["retired"])


def is_valid_expense_account(account: str) -> bool:
    return account in active_expense_accounts()


def add_expense_account(name: str, path=None) -> None:
    path = path or ACCOUNTS_PATH
    name = " ".join((name or "").split())
    if not name:
        raise AccountError("account name can't be empty")
    if len(name) > MAX_ACCOUNT_NAME_LEN:
        raise AccountError(f"account name is longer than {MAX_ACCOUNT_NAME_LEN} characters")
    if name.lower() in {a.lower() for a in MECHANICAL_ACCOUNTS}:
        raise AccountError(f"'{name}' is a fixed system account and can't be added as an expense")

    state = _load(path)
    if name.lower() in {a.lower() for a in state["active"]}:
        raise AccountError(f"'{name}' already exists")
    state["retired"] = [a for a in state["retired"] if a.lower() != name.lower()]
    state["active"] = sorted(state["active"] + [name])
    _save(state, path)


def retire_expense_account(name: str, path=None) -> None:
    path = path or ACCOUNTS_PATH
    if name == GENERAL_EXPENSE:
        raise AccountError(f"'{GENERAL_EXPENSE}' is the fallback account and can't be retired")
    state = _load(path)
    if name not in state["active"]:
        raise AccountError(f"'{name}' is not an active account")
    state["active"] = [a for a in state["active"] if a != name]
    state["retired"] = sorted(state["retired"] + [name])
    _save(state, path)


def apply_template(template: str, path=None) -> None:
    """Switch the active set to a starter template. Accounts that were active
    but aren't in the template are retired, not deleted."""
    path = path or ACCOUNTS_PATH
    if template not in TEMPLATES:
        raise AccountError(f"unknown template '{template}'")
    state = _load(path)
    new_active = set(TEMPLATES[template])
    dropped = set(state["active"]) - new_active
    state["active"] = sorted(new_active)
    state["retired"] = sorted((set(state["retired"]) | dropped) - new_active)
    _save(state, path)
