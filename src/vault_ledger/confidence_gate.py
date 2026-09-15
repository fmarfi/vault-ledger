"""Confidence gate (Report 1, item 6).

Below CONFIDENCE_THRESHOLD -> manual review queue.
Above -> proposed entry with edit/confirm.

The threshold is a tuning knob, not a one-time decision -- expect to adjust
once real accuracy numbers exist (Report 1). It lives here as a single named
constant precisely so it's easy to find and change later.
"""

CONFIDENCE_THRESHOLD = 0.75


def needs_manual_review(confidence: float) -> bool:
    return confidence < CONFIDENCE_THRESHOLD
