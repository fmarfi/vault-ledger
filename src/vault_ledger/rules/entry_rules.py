"""Deterministic debit/credit entry construction (Report 1, item 5).

Pure code, no ML. This is the layer Report 1 flags as highest-consequence:
must enforce total debits == total credits and must reject (not guess) any
predicted account outside the fixed COA. See rules_spec.json for the
versioned, readable invariants this module enforces -- keep the two in sync.
"""

from __future__ import annotations

from dataclasses import dataclass

from vault_ledger.coa import ACCOUNTS_PAYABLE, CASH_BANK, is_valid_expense_account


class RuleViolation(Exception):
    """Raised when a proposed entry would violate a rules_spec.json invariant."""


@dataclass(frozen=True)
class JournalLine:
    account: str
    debit: float
    credit: float


@dataclass(frozen=True)
class JournalEntry:
    lines: tuple[JournalLine, ...]

    @property
    def total_debits(self) -> float:
        return round(sum(line.debit for line in self.lines), 2)

    @property
    def total_credits(self) -> float:
        return round(sum(line.credit for line in self.lines), 2)


def construct_entry(expense_account: str, amount: float, paid: bool) -> JournalEntry:
    """Build a two-line journal entry from a classified expense account.

    Raises RuleViolation (R2, R3) rather than silently guessing or clamping.
    """
    if amount <= 0:
        raise RuleViolation(f"R3 violated: amount must be > 0, got {amount}")

    if not is_valid_expense_account(expense_account):
        raise RuleViolation(
            f"R2 violated: '{expense_account}' is not in the fixed chart of accounts"
        )

    amount = round(amount, 2)
    credit_account = CASH_BANK if paid else ACCOUNTS_PAYABLE  # R4

    entry = JournalEntry(
        lines=(
            JournalLine(account=expense_account, debit=amount, credit=0.0),  # R5
            JournalLine(account=credit_account, debit=0.0, credit=amount),
        )
    )

    if entry.total_debits != entry.total_credits:  # R1 -- should be unreachable
        raise RuleViolation(
            f"R1 violated: debits {entry.total_debits} != credits {entry.total_credits}"
        )

    return entry
