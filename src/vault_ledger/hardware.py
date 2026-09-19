"""Preflight hardware check (feature 6).

Vault Ledger runs its classifier and an optional local LLM on the user's own
machine. On a low-memory laptop that can quietly hang instead of failing, so
say so up front. Stdlib only -- no psutil dependency for one number.

Thresholds come from real experience on an 8GB / no-GPU Intel laptop: the
classifier and OCR worked, but the local LLM tier and heavy multitasking
stalled repeatedly.
"""

from __future__ import annotations

import os
import subprocess
import sys

MIN_RAM_GB = 8
RECOMMENDED_RAM_GB = 16
_SLACK = 0.93  # OS-reported totals run a little under the marketed size


def total_ram_gb() -> float | None:
    try:
        if sys.platform == "darwin":  # macOS has no SC_PHYS_PAGES
            out = subprocess.run(["sysctl", "-n", "hw.memsize"], capture_output=True, text=True, timeout=5)
            return int(out.stdout.strip()) / 1024**3
        return os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES") / 1024**3
    except (ValueError, OSError, AttributeError, subprocess.SubprocessError):
        return None


def assess(ram_gb: float | None, cpu_count: int | None = None) -> dict:
    cpu_count = cpu_count if cpu_count is not None else os.cpu_count()
    if ram_gb is None:
        return {"level": "unknown", "ram_gb": None, "cpu_count": cpu_count,
                "message": "Couldn't read this machine's memory, so no hardware check was possible."}

    rounded = round(ram_gb, 1)
    if ram_gb < MIN_RAM_GB * _SLACK:
        level = "critical"
        message = (f"This machine has {rounded} GB of memory, below the {MIN_RAM_GB} GB minimum. "
                   "Expect slowdowns or hangs; the local-LLM fallback is likely unusable.")
    elif ram_gb < RECOMMENDED_RAM_GB * _SLACK:
        level = "low"
        message = (f"This machine has {rounded} GB of memory ({RECOMMENDED_RAM_GB} GB recommended). "
                   "Core processing works, but close other heavy apps, and the local-LLM fallback will be slow.")
    else:
        level = "ok"
        message = f"{rounded} GB of memory — comfortably above the recommended {RECOMMENDED_RAM_GB} GB."
    return {"level": level, "ram_gb": rounded, "cpu_count": cpu_count, "message": message}


def check() -> dict:
    return assess(total_ram_gb())
