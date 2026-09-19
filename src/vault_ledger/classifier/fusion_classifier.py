"""Two-field fusion classifier (Report 1, item 4; Report 4 SS1).

Vendor and description are vectorized separately, then concatenated before
classification -- NOT blended into one text field. This is the core finding
from the DragoNet reference paper (vendor alone ~57% F1, fused ~93-95% F1)
and the reason the earlier single-blended-field notebook approach was
dropped. Do not regress to `vendor + " " + description` as a single
TfidfVectorizer input -- that reintroduces the dropped design.

TF-IDF + LogisticRegression is enough at this scale; a Transformer
architecture is BTG's infrastructure choice for 150k+ rows, not an MVP
requirement.
"""

from __future__ import annotations

from pathlib import Path

# sklearn/scipy/pandas/joblib are imported lazily inside the methods that
# need them: serving uses fast_inference.FastClassifier, and importing this
# module (e.g. for a type hint) must not pull in the whole scientific stack.


class FusionClassifier:
    def __init__(self) -> None:
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.linear_model import LogisticRegression

        self.vendor_vectorizer = TfidfVectorizer()
        self.description_vectorizer = TfidfVectorizer()
        self.model = LogisticRegression(max_iter=1000)
        self._fitted = False

    def _fuse(self, vendors: list[str], descriptions: list[str], fit: bool):
        from scipy.sparse import hstack

        if fit:
            vendor_features = self.vendor_vectorizer.fit_transform(vendors)
            description_features = self.description_vectorizer.fit_transform(descriptions)
        else:
            vendor_features = self.vendor_vectorizer.transform(vendors)
            description_features = self.description_vectorizer.transform(descriptions)
        return hstack([vendor_features, description_features])

    def fit(self, vendors: list[str], descriptions: list[str], accounts: list[str]) -> None:
        features = self._fuse(vendors, descriptions, fit=True)
        self.model.fit(features, accounts)
        self._fitted = True

    def predict(self, vendor: str, description: str) -> tuple[str, float]:
        """Return (predicted_account, confidence) for a single transaction."""
        if not self._fitted:
            raise RuntimeError("classifier has not been trained yet")

        features = self._fuse([vendor], [description], fit=False)
        probabilities = self.model.predict_proba(features)[0]
        best_index = probabilities.argmax()
        account = self.model.classes_[best_index]
        confidence = float(probabilities[best_index])
        return account, confidence

    def save(self, path: str | Path) -> None:
        import joblib

        joblib.dump(self, path)

    @staticmethod
    def load(path: str | Path) -> "FusionClassifier":
        import joblib

        return joblib.load(path)


def load_training_data(csv_path: str | Path):
    import pandas as pd

    return pd.read_csv(csv_path)
