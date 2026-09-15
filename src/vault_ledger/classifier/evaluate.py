"""Leave-one-out evaluation of the fusion classifier on the synthetic set.

The synthetic dataset is tiny (placeholder, not real data -- see README), so
a held-out split isn't meaningful; leave-one-out gives a rough per-example
signal instead. Treat any number here as a pipeline sanity check, not a
validated accuracy figure -- see Report 4's caution that real OCR-derived
descriptions will be noisier than this hand-written set.

    python -m vault_ledger.classifier.evaluate
"""

from __future__ import annotations

from pathlib import Path

from vault_ledger.classifier.fusion_classifier import FusionClassifier, load_training_data

DATA_PATH = Path(__file__).resolve().parents[3] / "data" / "synthetic" / "labeled_transactions.csv"


def main() -> None:
    df = load_training_data(DATA_PATH)
    vendors = df["vendor"].tolist()
    descriptions = df["description"].tolist()
    accounts = df["account"].tolist()

    correct = 0
    for i in range(len(df)):
        train_idx = [j for j in range(len(df)) if j != i]
        classifier = FusionClassifier()
        classifier.fit(
            vendors=[vendors[j] for j in train_idx],
            descriptions=[descriptions[j] for j in train_idx],
            accounts=[accounts[j] for j in train_idx],
        )
        predicted, confidence = classifier.predict(vendors[i], descriptions[i])
        is_correct = predicted == accounts[i]
        correct += int(is_correct)
        marker = "OK " if is_correct else "MISS"
        print(f"[{marker}] {vendors[i]!r} -> predicted={predicted!r} "
              f"(actual={accounts[i]!r}, confidence={confidence:.2f})")

    print(f"\nleave-one-out accuracy: {correct}/{len(df)} ({correct / len(df):.0%})")


if __name__ == "__main__":
    main()
