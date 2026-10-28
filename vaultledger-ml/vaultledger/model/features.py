"""Turn a Transaction into the model's inputs (spec 6.4.1).

Field A: normalized counterparty name.
Field B: normalized description + " [ACT] " + activity text (may be empty).
Numeric side features: small, cheap, not in DragoNet.
"""
from __future__ import annotations

import math

import numpy as np

from ..normalize import normalize_counterparty, normalize_description
from ..schemas import Transaction

ACT_SEP = " [ACT] "
N_NUMERIC = 13


def field_a(t: Transaction) -> str:
    return normalize_counterparty(t.counterparty_name)


def has_activity(t: Transaction) -> bool:
    return bool((t.activity_text or "").strip())


def field_b(t: Transaction, with_activity: bool = True) -> str:
    desc = normalize_description(t.description)
    act = (t.activity_text or "").strip().lower() if with_activity else ""
    return desc + ACT_SEP + act if act else desc


def numeric(t: Transaction) -> np.ndarray:
    day = t.date.day
    amount = float(t.amount)
    is_round = float(amount > 0 and t.amount % 10 == 0)
    vat_missing = t.vat_rate is None
    return np.array(
        [
            math.log1p(amount) / 10.0,
            float(t.direction == "IN"),
            float(t.direction == "OUT"),
            float(day <= 10),
            float(10 < day <= 20),
            float(day > 20),
            is_round,
            0.0 if vat_missing else float(t.vat_rate),
            float(vat_missing),
            float(bool(t.counterparty_iban)),
            float(t.paid is True),
            float(t.paid is None),
            float(t.vat_reverse_charge),
        ],
        dtype=np.float32,
    )


def numeric_batch(txns: list[Transaction]) -> np.ndarray:
    return np.stack([numeric(t) for t in txns]) if txns else np.zeros((0, N_NUMERIC), np.float32)
