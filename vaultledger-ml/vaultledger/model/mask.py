"""Taxonomy-aware mask and decoding (spec 6.4.4). No model needed.

Guarantee for both decoders: the output micro is a child of the output macro
and allowed for the transaction's direction.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from ..taxonomy import Taxonomy


@dataclass
class Decoded:
    macro: int
    micro: int
    prob: float
    # top pairs as (macro, micro, prob), best first
    top: list[tuple[int, int, float]]


def _log_softmax(x: np.ndarray) -> np.ndarray:
    x = np.asarray(x, dtype=np.float64)
    m = np.max(x)
    return x - m - np.log(np.sum(np.exp(x - m)))


def valid_pairs(tax: Taxonomy, direction: str) -> np.ndarray:
    """(n_macro, n_micro) boolean: micro is a child of macro and direction-consistent."""
    return tax.child & tax.direction_ok(direction)[None, :]


def joint_decode(
    tax: Taxonomy, logits_macro: np.ndarray, logits_micro: np.ndarray, direction: str, top_k: int = 3
) -> Decoded:
    """Pick the best valid (macro, micro) pair by log p_M + log p_m.

    Pair probabilities are the scores renormalised over valid pairs only.
    """
    valid = valid_pairs(tax, direction)
    if not valid.any():
        raise ValueError(f"no category allows direction {direction}")
    lp_M = _log_softmax(logits_macro)
    lp_m = _log_softmax(logits_micro)
    # Each micro has one parent, so a valid pair is fully identified by its micro.
    micros = np.flatnonzero(valid.any(axis=0))
    macros = tax.parent[micros]
    scores = lp_M[macros] + lp_m[micros]
    probs = np.exp(scores - scores.max())
    probs /= probs.sum()
    order = np.argsort(-probs, kind="stable")
    top = [(int(macros[i]), int(micros[i]), float(probs[i])) for i in order[:top_k]]
    best = order[0]
    return Decoded(int(macros[best]), int(micros[best]), float(probs[best]), top)


def argmax_then_mask(
    tax: Taxonomy, logits_macro: np.ndarray, logits_micro: np.ndarray, direction: str, top_k: int = 3
) -> Decoded:
    """DragoNet's original order: choose macro first, then the best micro under it.

    Kept for the ablation in spec 8.3. Macros with no valid child are skipped.
    """
    valid = valid_pairs(tax, direction)
    macro_ok = valid.any(axis=1)
    if not macro_ok.any():
        raise ValueError(f"no category allows direction {direction}")
    lp_M = np.where(macro_ok, _log_softmax(logits_macro), -np.inf)
    macro = int(np.argmax(lp_M))
    children = np.flatnonzero(valid[macro])
    lp_m = _log_softmax(np.asarray(logits_micro, dtype=np.float64)[children])
    probs = np.exp(lp_m)
    order = np.argsort(-probs, kind="stable")
    top = [(macro, int(children[i]), float(probs[i])) for i in order[:top_k]]
    return Decoded(macro, int(children[order[0]]), float(probs[order[0]]), top)


DECODERS = {"joint": joint_decode, "argmax_then_mask": argmax_then_mask}
