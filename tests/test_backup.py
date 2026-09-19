import io
import json
import zipfile

import pytest

from vault_ledger import backup
from vault_ledger.ledger import append_entry, read_entries


def _files(tmp_path):
    return {
        "ledger.csv": tmp_path / "ledger.csv",
        "pending_queue.csv": tmp_path / "pending_queue.csv",
        "corrections.csv": tmp_path / "corrections.csv",
        "labeled_transactions.csv": tmp_path / "labeled.csv",
        "accounts.json": tmp_path / "accounts.json",
    }


def test_round_trip_restores_ledger_on_a_fresh_machine(tmp_path):
    src = _files(tmp_path / "old")
    append_entry("a.png", "Acme", "paper", "03/01/2026", 10.0, "Rent Expense", 0.9, False, path=src["ledger.csv"])
    data = backup.create_backup(src)

    dst = _files(tmp_path / "new")
    restored = backup.restore_backup(data, dst, model_path=tmp_path / "m.joblib")

    assert restored == ["ledger.csv"]
    assert read_entries(dst["ledger.csv"])[0]["vendor"] == "Acme"


def test_restore_deletes_stale_model_when_training_data_restored(tmp_path):
    src = _files(tmp_path / "old")
    src["labeled_transactions.csv"].parent.mkdir(parents=True)
    src["labeled_transactions.csv"].write_text("vendor,description,account\nA,b,Rent Expense\n")
    model = tmp_path / "m.joblib"
    model.write_text("stale")

    backup.restore_backup(backup.create_backup(src), _files(tmp_path / "new"), model_path=model)

    assert not model.exists()


def test_rejects_non_zip(tmp_path):
    with pytest.raises(backup.BackupError):
        backup.restore_backup(b"not a zip", _files(tmp_path))


def test_rejects_zip_without_manifest(tmp_path):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("ledger.csv", "x")
    with pytest.raises(backup.BackupError):
        backup.restore_backup(buf.getvalue(), _files(tmp_path))


def test_rejects_path_traversal_and_unexpected_members_without_writing(tmp_path):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("manifest.json", json.dumps({"format_version": 1}))
        zf.writestr("../evil.txt", "boom")
    dst = _files(tmp_path)
    with pytest.raises(backup.BackupError):
        backup.restore_backup(buf.getvalue(), dst)
    assert not (tmp_path.parent / "evil.txt").exists()


def test_rejects_wrong_csv_columns_and_leaves_live_data_alone(tmp_path):
    dst = _files(tmp_path)
    dst["ledger.csv"].write_text("keep,me\n")
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("manifest.json", json.dumps({"format_version": 1}))
        zf.writestr("ledger.csv", "wrong,columns\n1,2\n")
    with pytest.raises(backup.BackupError):
        backup.restore_backup(buf.getvalue(), dst)
    assert dst["ledger.csv"].read_text() == "keep,me\n"


def test_rejects_accounts_json_without_fallback_account(tmp_path):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("manifest.json", json.dumps({"format_version": 1}))
        zf.writestr("accounts.json", json.dumps({"active": ["Rent Expense"], "retired": []}))
    with pytest.raises(backup.BackupError):
        backup.restore_backup(buf.getvalue(), _files(tmp_path))
