"""Data shapes (spec section 4). Everything downstream uses these, never raw CSVs."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

DIRECTIONS = ("IN", "OUT")
QUALITIES = ("OK", "LOW")
STATUSES = ("AUTO", "REVIEW", "UNKNOWN")


@dataclass
class Transaction:
    txn_id: str
    company_id: str
    date: date
    amount: Decimal  # always positive; the sign lives in `direction`
    direction: str  # IN | OUT
    counterparty_name: str = ""
    description: str = ""
    currency: str = "EUR"
    counterparty_iban: str | None = None
    activity_code: str | None = None  # KvK SBI; stays empty until research passes
    activity_text: str | None = None  # text for the code, or learned from the export
    vat_rate: Decimal | None = None
    paid: bool | None = None  # known for invoices/receipts; None for bank rows
    vat_reverse_charge: bool = False  # "btw verlegd": VAT shifted to the buyer (often foreign services)

    def __post_init__(self) -> None:
        if isinstance(self.date, str):
            self.date = date.fromisoformat(self.date)
        if not isinstance(self.amount, Decimal):
            self.amount = Decimal(str(self.amount))
        if self.vat_rate is not None and not isinstance(self.vat_rate, Decimal):
            self.vat_rate = Decimal(str(self.vat_rate))
        if self.direction not in DIRECTIONS:
            raise ValueError(f"direction must be IN or OUT, got {self.direction!r}")
        if self.amount < 0:
            raise ValueError("amount must be positive; the sign lives in direction")

    def to_dict(self) -> dict:
        return {
            "txn_id": self.txn_id,
            "company_id": self.company_id,
            "date": self.date.isoformat(),
            "amount": str(self.amount),
            "direction": self.direction,
            "currency": self.currency,
            "counterparty_name": self.counterparty_name,
            "counterparty_iban": self.counterparty_iban,
            "description": self.description,
            "activity_code": self.activity_code,
            "activity_text": self.activity_text,
            "vat_rate": None if self.vat_rate is None else str(self.vat_rate),
            "paid": self.paid,
            "vat_reverse_charge": self.vat_reverse_charge,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Transaction":
        return cls(**d)


@dataclass
class Label:
    txn_id: str
    company_account_id: str
    ref_macro: str | None
    ref_micro: str | None
    source: str = "EXPORT"  # EXPORT | CORRECTION | SYNTHETIC
    quality: str = "OK"  # OK | LOW (LOW is not trained on by default)

    def __post_init__(self) -> None:
        if self.quality not in QUALITIES:
            raise ValueError(f"quality must be one of {QUALITIES}")

    def to_dict(self) -> dict:
        return dict(self.__dict__)

    @classmethod
    def from_dict(cls, d: dict) -> "Label":
        return cls(**d)


@dataclass
class CompanyConfig:
    company_id: str
    own_account_ibans: list[str] = field(default_factory=list)
    # company account id -> display name; filled by an adapter
    accounts: dict[str, str] = field(default_factory=dict)


@dataclass
class Suggestion:
    txn_id: str
    ref_macro: str | None
    ref_micro: str | None
    confidence: float  # raw model probability until calibration (ML-M9) exists
    status: str = "REVIEW"  # nothing is AUTO before calibration
    layer: str = "MODEL"
    company_account_id: str | None = None  # filled by company mapping (ML-M8)
    rule_id: str | None = None  # internal only
    alternatives: list[tuple[str, float]] = field(default_factory=list)
    model_version: str = ""
