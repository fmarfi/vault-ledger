import csv
import io
from datetime import datetime, timezone

from vault_ledger.reports import audit_csv, books_csv, period_summary

NOW = datetime(2026, 9, 18, 12, 0, tzinfo=timezone.utc).astimezone()


def _entry(confirmed_at, amount, account="Utilities Expense", **extra):
    base = {
        "confirmed_at": confirmed_at,
        "filename": "a.png",
        "vendor": "Acme",
        "description": "stuff",
        "date": "2026-09-01",
        "amount": str(amount),
        "account": account,
        "confidence": "0.9",
        "was_corrected": "False",
    }
    base.update(extra)
    return base


def test_this_month_totals_and_groups_by_account_biggest_first():
    entries = [
        _entry("2026-09-10T12:00:00+00:00", 100, "Utilities Expense"),
        _entry("2026-09-11T12:00:00+00:00", 300, "Rent Expense"),
        _entry("2026-09-12T12:00:00+00:00", 50, "Utilities Expense"),
        _entry("2026-08-10T12:00:00+00:00", 999),
    ]
    summary = period_summary(entries, "this", now=NOW)
    assert summary["total"] == 450.0
    assert summary["entry_count"] == 3
    assert [line["account"] for line in summary["lines"]] == ["Rent Expense", "Utilities Expense"]
    assert summary["lines"][1]["amount"] == 150.0


def test_comparison_up_down_and_unavailable():
    entries = [
        _entry("2026-08-10T12:00:00+00:00", 100),
        _entry("2026-09-10T12:00:00+00:00", 150),
    ]
    up = period_summary(entries, "this", now=NOW)["comparison"]
    assert (up["available"], up["direction"], up["pct"]) == (True, "up", 50)

    # Last month has nothing before it to compare against.
    last = period_summary(entries, "last", now=NOW)["comparison"]
    assert last["available"] is False

    down = period_summary(
        [_entry("2026-08-10T12:00:00+00:00", 200), _entry("2026-09-10T12:00:00+00:00", 100)],
        "this",
        now=NOW,
    )["comparison"]
    assert (down["direction"], down["pct"]) == ("down", 50)


def test_last_month_across_year_boundary():
    jan = datetime(2027, 1, 15, 12, 0, tzinfo=timezone.utc).astimezone()
    summary = period_summary([_entry("2026-12-20T12:00:00+00:00", 80)], "last", now=jan)
    assert summary["total"] == 80.0
    assert summary["month_label"] == "December 2026"


def test_empty_ledger_and_bad_timestamps_do_not_crash():
    summary = period_summary([_entry("not-a-date", 10)], "this", now=NOW)
    assert summary["total"] == 0.0
    assert summary["lines"] == []


def test_books_csv_shape_and_date_fallback():
    rows = list(csv.reader(io.StringIO(books_csv([_entry("2026-09-10T12:00:00+00:00", 42.5, date="")]))))
    assert rows[0] == ["Date", "Vendor", "Description", "Amount", "Account"]
    assert rows[1][0] == "2026-09-10"
    assert rows[1][3] == "42.5"


def test_csv_neutralizes_formula_injection():
    entry = _entry("2026-09-10T12:00:00+00:00", 1, vendor="=HYPERLINK(\"http://x\")", description="@cmd")
    for text in (books_csv([entry]), audit_csv([entry])):
        rows = list(csv.reader(io.StringIO(text)))
        assert all(not cell.startswith(("=", "@")) for row in rows[1:] for cell in row)


def test_audit_csv_includes_confidence_and_correction_flag():
    rows = list(csv.reader(io.StringIO(audit_csv([_entry("2026-09-10T12:00:00+00:00", 5, was_corrected="True")]))))
    assert rows[1][-2:] == ["0.9", "Yes"]
