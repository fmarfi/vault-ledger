"""Metrics without scikit-learn (spec 8.2, the parts that exist before calibration)."""
from __future__ import annotations

import numpy as np

SYNTHETIC_BANNER = "Results on synthetic data. Not indicative of real-world accuracy."


def macro_f1(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    """Unweighted mean F1 over classes present in y_true or y_pred."""
    y_true, y_pred = np.asarray(y_true), np.asarray(y_pred)
    classes = np.union1d(y_true, y_pred)
    if len(classes) == 0:
        return 0.0
    f1s = []
    for c in classes:
        tp = np.sum((y_pred == c) & (y_true == c))
        fp = np.sum((y_pred == c) & (y_true != c))
        fn = np.sum((y_pred != c) & (y_true == c))
        denom = 2 * tp + fp + fn
        f1s.append(0.0 if denom == 0 else 2 * tp / denom)
    return float(np.mean(f1s))


def accuracy(y_true, y_pred) -> float:
    y_true, y_pred = np.asarray(y_true), np.asarray(y_pred)
    return float(np.mean(y_true == y_pred)) if len(y_true) else 0.0


def hierarchy_violations(parent: np.ndarray, macro_pred, micro_pred) -> int:
    return int(np.sum(parent[np.asarray(micro_pred)] != np.asarray(macro_pred)))


def summarize(parent, macro_true, micro_true, macro_pred, micro_pred) -> dict:
    return {
        "n": int(len(micro_true)),
        "macro_level": {"macro_f1": macro_f1(macro_true, macro_pred), "accuracy": accuracy(macro_true, macro_pred)},
        "micro_level": {"macro_f1": macro_f1(micro_true, micro_pred), "accuracy": accuracy(micro_true, micro_pred)},
        "hierarchy_violations": hierarchy_violations(parent, macro_pred, micro_pred),
    }
