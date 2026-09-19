"""Dependency-free serving path for the fusion classifier.

Training stays on scikit-learn (FusionClassifier). Serving only needs
TF-IDF -> per-field L2 norm -> linear scores -> softmax, which is a few
dozen lines of pure Python. Importing sklearn/scipy/pandas just to do that
cost seconds of CPU per process (and minutes under memory pressure on the
8GB dev machine), so the web app and CLI load this instead.

The exported JSON is produced by `export_fast_model` from a fitted
FusionClassifier; tests assert probability parity against sklearn.
"""

from __future__ import annotations

import json
import math
import re
from pathlib import Path

FAST_MODEL_PATH = (
    Path(__file__).resolve().parents[3] / "data" / "synthetic" / "fusion_classifier.json"
)

# Same default token pattern scikit-learn's TfidfVectorizer uses.
_TOKEN_PATTERN = re.compile(r"(?u)\b\w\w+\b")


def export_fast_model(classifier, path: str | Path) -> None:
    vendor_vec = classifier.vendor_vectorizer
    desc_vec = classifier.description_vectorizer
    payload = {
        "classes": [str(c) for c in classifier.model.classes_],
        "vendor_vocab": {t: int(i) for t, i in vendor_vec.vocabulary_.items()},
        "vendor_idf": [float(x) for x in vendor_vec.idf_],
        "description_vocab": {t: int(i) for t, i in desc_vec.vocabulary_.items()},
        "description_idf": [float(x) for x in desc_vec.idf_],
        "coef": [[float(x) for x in row] for row in classifier.model.coef_],
        "intercept": [float(x) for x in classifier.model.intercept_],
    }
    Path(path).write_text(json.dumps(payload), encoding="utf-8")


def _tfidf(text: str, vocab: dict[str, int], idf: list[float]) -> dict[int, float]:
    counts: dict[int, int] = {}
    for token in _TOKEN_PATTERN.findall(text.lower()):
        index = vocab.get(token)
        if index is not None:
            counts[index] = counts.get(index, 0) + 1
    weights = {i: c * idf[i] for i, c in counts.items()}
    norm = math.sqrt(sum(w * w for w in weights.values()))
    if norm > 0:
        weights = {i: w / norm for i, w in weights.items()}
    return weights


class FastClassifier:
    def __init__(self, payload: dict) -> None:
        self.classes = payload["classes"]
        self._vendor_vocab = payload["vendor_vocab"]
        self._vendor_idf = payload["vendor_idf"]
        self._description_vocab = payload["description_vocab"]
        self._description_idf = payload["description_idf"]
        self._coef = payload["coef"]
        self._intercept = payload["intercept"]
        self._description_offset = len(self._vendor_idf)

    @staticmethod
    def load(path: str | Path) -> "FastClassifier":
        return FastClassifier(json.loads(Path(path).read_text(encoding="utf-8")))

    def predict(self, vendor: str, description: str) -> tuple[str, float]:
        vendor_w = _tfidf(vendor, self._vendor_vocab, self._vendor_idf)
        desc_w = _tfidf(description, self._description_vocab, self._description_idf)
        offset = self._description_offset

        scores = []
        for row, bias in zip(self._coef, self._intercept):
            score = bias
            for i, w in vendor_w.items():
                score += w * row[i]
            for i, w in desc_w.items():
                score += w * row[offset + i]
            scores.append(score)

        if len(self.classes) == 2:
            # sklearn stores one coefficient row for the binary case: sigmoid.
            p_pos = 1.0 / (1.0 + math.exp(-max(min(scores[0], 500.0), -500.0)))
            probs = [1.0 - p_pos, p_pos]
        else:
            top = max(scores)
            exps = [math.exp(s - top) for s in scores]
            total = sum(exps)
            probs = [e / total for e in exps]

        best = max(range(len(probs)), key=probs.__getitem__)
        return self.classes[best], float(probs[best])
