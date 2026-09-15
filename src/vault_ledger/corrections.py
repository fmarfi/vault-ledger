"""Minimal correction loop (Report 1, Milestone 7).

Accountant corrections get appended to corrections.csv rather than fed into
a live retraining pipeline -- Report 1 explicitly scopes live/automatic
retraining out of the MVP; periodic manual re-training on accumulated
corrections is enough. See classifier/apply_corrections.py for folding
these back into the training set when you're ready to retrain.
"""

from __future__ import annotations

import csv
from pathlib import Path

CORRECTIONS_PATH = Path(__file__).resolve().parents[2] / "corrections.csv"
FIELDNAMES = ["vendor", "description", "predicted_account", "corrected_account", "amount", "date"]


def record_correction(
    vendor: str,
    description: str,
    predicted_account: str,
    corrected_account: str,
    amount: float,
    date: str | None,
    path: str | Path = CORRECTIONS_PATH,
) -> None:
    path = Path(path)
    is_new = not path.exists()
    with path.open("a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        if is_new:
            writer.writeheader()
        writer.writerow(
            {
                "vendor": vendor,
                "description": description,
                "predicted_account": predicted_account,
                "corrected_account": corrected_account,
                "amount": amount,
                "date": date or "",
            }
        )
