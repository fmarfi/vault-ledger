"""Fold accumulated corrections into the training set.

Report 1 is explicit that live/automatic retraining is out of scope for the
MVP -- periodic manual re-training on accumulated corrections is enough.
This script is that periodic step, run by hand:

    python -m vault_ledger.classifier.apply_corrections
    python -m vault_ledger.classifier.train   # then retrain on the update

Appends each row in corrections.csv (vendor, description, corrected_account)
to data/synthetic/labeled_transactions.csv as a new training example, then
resets corrections.csv back to just the header so corrections aren't
double-applied on a future run.
"""

from __future__ import annotations

import csv
from pathlib import Path

from vault_ledger.corrections import CORRECTIONS_PATH, FIELDNAMES

TRAINING_DATA_PATH = (
    Path(__file__).resolve().parents[3] / "data" / "synthetic" / "labeled_transactions.csv"
)


def apply_corrections(
    corrections_path: str | Path = CORRECTIONS_PATH,
    training_data_path: str | Path = TRAINING_DATA_PATH,
) -> int:
    corrections_path = Path(corrections_path)
    training_data_path = Path(training_data_path)

    if not corrections_path.exists():
        return 0

    with corrections_path.open(newline="", encoding="utf-8") as f:
        corrections = list(csv.DictReader(f))

    if not corrections:
        return 0

    with training_data_path.open("a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        for row in corrections:
            writer.writerow([row["vendor"], row["description"], row["corrected_account"]])

    with corrections_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()

    return len(corrections)


def main() -> None:
    count = apply_corrections()
    print(f"folded {count} correction(s) into {TRAINING_DATA_PATH}")
    if count:
        print("run `python -m vault_ledger.classifier.train` to retrain on the updated set")


if __name__ == "__main__":
    main()
