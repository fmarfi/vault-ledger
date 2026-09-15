"""Train the fusion classifier on the labeled transactions CSV and save it.

    python -m vault_ledger.classifier.train
"""

from __future__ import annotations

from pathlib import Path

from vault_ledger.classifier.fusion_classifier import FusionClassifier, load_training_data

DATA_PATH = Path(__file__).resolve().parents[3] / "data" / "synthetic" / "labeled_transactions.csv"
MODEL_PATH = Path(__file__).resolve().parents[3] / "data" / "synthetic" / "fusion_classifier.joblib"


def main() -> None:
    df = load_training_data(DATA_PATH)
    classifier = FusionClassifier()
    classifier.fit(
        vendors=df["vendor"].tolist(),
        descriptions=df["description"].tolist(),
        accounts=df["account"].tolist(),
    )
    classifier.save(MODEL_PATH)
    print(f"trained on {len(df)} rows, saved to {MODEL_PATH}")


if __name__ == "__main__":
    main()
