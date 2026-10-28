"""Dates stored as YYYY-MM-DD: conversion, the day/month setting, and every
place that reads a date (pipeline, queue, duplicate check, backup)."""

import csv
import io
import json
import zipfile

import pytest

from vault_ledger import backup, duplicates, pipeline, preferences, queue
from vault_ledger.extraction.dates import DAY_FIRST, MONTH_FIRST, DateReading, to_iso
from vault_ledger.extraction.field_parser import ExtractedFields, document_date_order


@pytest.mark.parametrize(
    "written, iso",
    [
        ("2026-03-14", "2026-03-14"),
        ("14 maart 2026", "2026-03-14"),
        ("March 14, 2026", "2026-03-14"),
        ("14-03-2026", "2026-03-14"),  # only one reading: no 14th month
        ("03/14/2026", "2026-03-14"),
        ("04/04/2026", "2026-04-04"),  # both readings are the same day
    ],
)
def test_unambiguous_dates_convert_without_asking(written, iso):
    for order in (DAY_FIRST, MONTH_FIRST):
        assert to_iso(written, order) == DateReading(written, iso, False)


def test_ambiguous_date_follows_the_setting_and_says_so():
    assert to_iso("03/04/2026", DAY_FIRST) == DateReading("03/04/2026", "2026-04-03", True)
    assert to_iso("03/04/2026", MONTH_FIRST) == DateReading("03/04/2026", "2026-03-04", True)


def test_document_order_beats_the_setting_and_is_not_flagged():
    assert to_iso("03/04/2026", MONTH_FIRST, DAY_FIRST) == DateReading("03/04/2026", "2026-04-03", False)


@pytest.mark.parametrize("written", ["31-45-2026", "12-45-9087", "not a date", "", None])
def test_non_dates_give_none(written):
    assert to_iso(written) is None


def test_dutch_document_settles_day_first():
    assert document_date_order("Factuurdatum: 03-04-2026\nTotaal: 10,00") == DAY_FIRST
    assert document_date_order("Invoice date: 03/04/2026\nTotal: 10.00") is None


class _Fixed:
    def predict(self, vendor, description):
        return "Rent Expense", 0.95


def _run(monkeypatch, raw_text, date, order=DAY_FIRST):
    monkeypatch.setattr(pipeline, "extract_raw_text", lambda _p: raw_text)
    monkeypatch.setattr(pipeline, "parse_fields", lambda _t: ExtractedFields("Landlord BV", "rent", date, 1200.0, True))
    return pipeline.run_pipeline("doc.png", _Fixed(), order)


def test_pipeline_stores_iso_and_keeps_the_written_date(monkeypatch):
    result = _run(monkeypatch, "Invoice date: 14 March 2026", "March 14, 2026")
    assert (result.date, result.date_written, result.date_assumed) == ("2026-03-14", "March 14, 2026", False)
    assert not result.needs_review


def test_pipeline_flags_an_assumed_order_for_review(monkeypatch):
    result = _run(monkeypatch, "Invoice date: 03/04/2026", "03/04/2026", MONTH_FIRST)
    assert (result.date, result.date_assumed, result.needs_review) == ("2026-03-04", True, True)


def test_pipeline_does_not_flag_a_dutch_ambiguous_date(monkeypatch):
    result = _run(monkeypatch, "Factuurdatum: 03-04-2026", "03-04-2026", MONTH_FIRST)
    assert (result.date, result.date_assumed, result.needs_review) == ("2026-04-03", False, False)


def _enqueue(path, date, **extra):
    return queue.enqueue(
        filename="a.pdf", vendor="Acme", description="x", date=date, amount=10.0, paid=True,
        predicted_account="Rent Expense", confidence=0.9, needs_review=False, rejection_reason=None,
        entry_json="{}", path=path, **extra,
    )


def test_queue_round_trips_the_new_columns(tmp_path):
    path = tmp_path / "q.csv"
    _enqueue(path, "2026-04-03", date_written="03/04/2026", date_assumed=True)
    row = queue.read_pending(path)[0]
    assert (row["date"], row["date_written"], row["date_assumed"]) == ("2026-04-03", "03/04/2026", "True")


def test_old_queue_rows_are_read_as_iso(tmp_path, monkeypatch):
    monkeypatch.setattr(preferences, "PREFERENCES_PATH", tmp_path / "prefs.json")
    path = tmp_path / "q.csv"
    old = queue.FIELDNAMES[: queue.FIELDNAMES.index("decided_by")]
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=old)
        writer.writeheader()
        writer.writerow({name: "" for name in old} | {"id": "a", "date": "14 maart 2026", "amount": "1"})
        writer.writerow({name: "" for name in old} | {"id": "b", "date": "03/04/2026", "amount": "1"})
    a, b = queue.read_pending(path)
    assert (a["date"], a["date_written"], a["date_assumed"]) == ("2026-03-14", "14 maart 2026", "")
    assert (b["date"], b["date_written"], b["date_assumed"]) == ("2026-04-03", "03/04/2026", "True")


def test_duplicates_match_the_same_day_in_different_notations(tmp_path, monkeypatch):
    monkeypatch.setattr(preferences, "PREFERENCES_PATH", tmp_path / "prefs.json")
    item = {"id": "a", "vendor": "Acme", "amount": "10", "date": "2026-03-14"}
    ledger = [{"vendor": "ACME ", "amount": "10.00", "date": "03/14/2026", "filename": "old.pdf"}]
    assert duplicates.find_match(item, [], ledger)["filename"] == "old.pdf"


def test_preferences_default_validate_and_save(tmp_path):
    path = tmp_path / "prefs.json"
    assert preferences.load(path) == {"date_order": DAY_FIRST}
    assert preferences.save({"date_order": MONTH_FIRST}, path) == {"date_order": MONTH_FIRST}
    assert preferences.date_order(path) == MONTH_FIRST
    with pytest.raises(ValueError):
        preferences.save({"date_order": "sideways"}, path)
    path.write_text("not json")
    assert preferences.load(path) == {"date_order": DAY_FIRST}


def _backup_with(members: dict) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("manifest.json", json.dumps({"format_version": backup.BACKUP_FORMAT_VERSION, "files": list(members)}))
        for name, data in members.items():
            zf.writestr(name, data)
    return buf.getvalue()


def test_restore_accepts_a_backup_from_before_the_new_queue_columns(tmp_path):
    old = ",".join(queue.FIELDNAMES[: queue.FIELDNAMES.index("decided_by")])
    files = {name: tmp_path / name for name in ("ledger.csv", "pending_queue.csv", "corrections.csv",
                                                 "labeled_transactions.csv", "accounts.json", "preferences.json")}
    restored = backup.restore_backup(_backup_with({"pending_queue.csv": old + "\n"}), files=files,
                                     model_path=tmp_path / "model.joblib")
    assert "pending_queue.csv" in restored


@pytest.mark.parametrize("header", ["id,queued_at", "id,queued_at,something_else"])
def test_restore_still_rejects_unknown_queue_columns(tmp_path, header):
    files = {"pending_queue.csv": tmp_path / "q.csv"}
    with pytest.raises(backup.BackupError):
        backup.restore_backup(_backup_with({"pending_queue.csv": header + "\n"}), files=files,
                              model_path=tmp_path / "model.joblib")


def test_restore_rejects_bad_preferences(tmp_path):
    files = {"preferences.json": tmp_path / "prefs.json"}
    with pytest.raises(backup.BackupError):
        backup.restore_backup(_backup_with({"preferences.json": '{"date_order": "x"}'}), files=files,
                              model_path=tmp_path / "model.joblib")
