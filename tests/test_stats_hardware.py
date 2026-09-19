from datetime import datetime, timedelta, timezone

from vault_ledger import hardware
from vault_ledger.stats import compute_stats

NOW = datetime(2026, 9, 19, tzinfo=timezone.utc)


def _entry(days_ago, corrected, account="Rent Expense"):
    return {
        "confirmed_at": (NOW - timedelta(days=days_ago)).isoformat(timespec="seconds"),
        "was_corrected": str(corrected),
        "account": account,
    }


def test_empty_ledger_has_no_rate():
    stats = compute_stats([], NOW)
    assert stats["total"] == 0 and stats["first_pass_rate"] is None and not stats["meaningful"]


def test_first_pass_rate_counts_uncorrected_entries():
    entries = [_entry(1, False), _entry(1, False), _entry(1, True), _entry(1, False)]
    stats = compute_stats(entries, NOW)
    assert stats["first_pass_rate"] == 0.75 and stats["corrected"] == 1


def test_recent_window_excludes_old_entries():
    stats = compute_stats([_entry(5, False), _entry(90, True)], NOW)
    assert stats["recent_total"] == 1 and stats["recent_first_pass_rate"] == 1.0
    assert stats["total"] == 2


def test_small_sample_is_flagged_not_meaningful_and_large_is():
    assert not compute_stats([_entry(1, False)] * 19, NOW)["meaningful"]
    assert compute_stats([_entry(1, False)] * 20, NOW)["meaningful"]


def test_corrected_into_ranks_accounts():
    entries = [_entry(1, True, "A"), _entry(1, True, "B"), _entry(1, True, "B")]
    assert compute_stats(entries, NOW)["corrected_into"][0] == ("B", 2)


def test_hardware_levels():
    assert hardware.assess(4.0)["level"] == "critical"
    assert hardware.assess(7.8)["level"] == "low"      # a marketed-8GB machine
    assert hardware.assess(15.6)["level"] == "ok"      # a marketed-16GB machine
    assert hardware.assess(None)["level"] == "unknown"


def test_hardware_reads_real_memory_on_this_machine():
    # Regression: macOS lacks os.sysconf("SC_PHYS_PAGES"), which once made
    # every Mac report "unknown".
    ram = hardware.total_ram_gb()
    assert ram is not None and ram > 1


def test_hardware_unknown_when_memory_unreadable(monkeypatch):
    def boom(*a, **k):
        raise OSError

    monkeypatch.setattr(hardware.subprocess, "run", boom)
    monkeypatch.setattr(hardware.os, "sysconf", boom, raising=False)
    assert hardware.total_ram_gb() is None
