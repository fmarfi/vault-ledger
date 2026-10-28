"""Per-user preferences that change how documents are read.

Only one so far: the day/month order for a numeric date the document itself
doesn't settle (`03/04/2026`). See extraction/dates.py. Stored per user as
preferences.json; missing or unreadable means the defaults.
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

from vault_ledger.extraction.dates import DATE_ORDERS, DAY_FIRST
from vault_ledger.userdata import resolve

PREFERENCES_PATH = Path(__file__).resolve().parents[2] / "data" / "preferences.json"

DEFAULTS = {"date_order": DAY_FIRST}  # the Netherlands first


def _path(path=None) -> Path:
    return resolve("preferences.json", PREFERENCES_PATH, path)


def validate(state) -> dict:
    """A clean preferences dict; raises ValueError for bad values."""
    if not isinstance(state, dict):
        raise ValueError("preferences must be an object")
    order = state.get("date_order", DEFAULTS["date_order"])
    if order not in DATE_ORDERS:
        raise ValueError(f"date_order must be one of {', '.join(DATE_ORDERS)}")
    return {"date_order": order}


def load(path=None) -> dict:
    try:
        return validate(json.loads(_path(path).read_text(encoding="utf-8")))
    except (OSError, ValueError):
        return dict(DEFAULTS)


def save(changes: dict, path=None) -> dict:
    state = validate(load(path) | changes)
    target = _path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=target.parent, suffix=".tmp")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(state, f)
    os.replace(tmp, target)
    return state


def date_order(path=None) -> str:
    return load(path)["date_order"]
