"""Evaluation splits (spec 8.1). Never a random row split: that leaks vendors."""
from __future__ import annotations

import random

from ..normalize import normalize_counterparty
from ..schemas import Transaction


def vendor_key(t: Transaction) -> str:
    return normalize_counterparty(t.counterparty_name) or f"<empty:{t.txn_id}>"


def group_split(txns: list[Transaction], test_frac: float, seed: int,
                per_company: bool = False) -> tuple[list[int], list[int]]:
    """Split row indices so no vendor appears on both sides.

    Default groups vendors globally across companies (background.md ruling);
    per_company=True gives the spec's within-company variant.
    """
    groups: dict[str, list[int]] = {}
    for i, t in enumerate(txns):
        key = (t.company_id + "|" if per_company else "") + vendor_key(t)
        groups.setdefault(key, []).append(i)
    keys = sorted(groups)
    random.Random(seed).shuffle(keys)
    target = test_frac * len(txns)
    test: list[int] = []
    for k in keys:
        if len(test) >= target:
            break
        test.extend(groups[k])
    test_set = set(test)
    train = [i for i in range(len(txns)) if i not in test_set]
    return train, sorted(test)


def time_split(txns: list[Transaction], train_frac: float = 0.8) -> tuple[list[int], list[int]]:
    """Train on the earliest months, test on the rest."""
    months = sorted({(t.date.year, t.date.month) for t in txns})
    cut = months[max(1, int(len(months) * train_frac)) - 1]
    train = [i for i, t in enumerate(txns) if (t.date.year, t.date.month) <= cut]
    test = [i for i, t in enumerate(txns) if (t.date.year, t.date.month) > cut]
    return train, test
