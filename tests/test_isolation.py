"""Per-user data isolation: user A must never read or change anything of user B."""

import hashlib
import io
import json
import threading
import zipfile
from pathlib import Path

import pytest

from vault_ledger import backup, coa, queue as queue_mod
from vault_ledger.userdata import UserDataError, current_user_dir, resolve, use_user_dir
from vault_ledger.webapp import app as app_mod

from tests.helpers import make_user_client, new_client


def _enqueue(client, vendor, amount, account="Office Supplies Expense"):
    with use_user_dir(client.user_dir):
        return app_mod.enqueue(
            filename=f"{vendor}.png", vendor=vendor, description=f"desc {vendor}", date="03/14/2026",
            amount=amount, paid=True, predicted_account=account, confidence=0.9,
            needs_review=False, rejection_reason=None, entry_json="{}",
        )


def _seed(client, tag, base):
    """1 posted as-is, 1 corrected into a custom account, 1 still pending."""
    account = f"{tag} Custom Expense"
    assert client.post("/api/accounts/add", json={"name": account}).status_code == 200
    posted = _enqueue(client, f"{tag}-VENDOR-POSTED", base)
    corrected = _enqueue(client, f"{tag}-VENDOR-CORRECTED", base + 1)
    pending = _enqueue(client, f"{tag}-VENDOR-PENDING", base + 2)
    assert client.post("/api/confirm", json={"id": posted}).status_code == 200
    assert client.post("/api/correct", json={"id": corrected, "corrected_account": account}).status_code == 200
    return {"tag": tag, "account": account, "posted": posted, "corrected": corrected, "pending": pending,
            "total": round(base + base + 1, 2)}


@pytest.fixture
def two_users():
    a = make_user_client(app_mod.app, "alice")
    b = make_user_client(app_mod.app, "bobby")
    return a, b, _seed(a, "AAA", 111.0), _seed(b, "BBB", 222.0)


def _snapshot(directory: Path) -> dict:
    return {
        str(p.relative_to(directory)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(directory.rglob("*")) if p.is_file()
    }


def _all_text(client, paths):
    return "\n".join(client.get(p).get_data(as_text=True) for p in paths)


READ_ENDPOINTS = [
    "/api/queue", "/api/documents", "/api/ledger", "/api/stats", "/api/overview", "/api/overview?period=last",
    "/api/export/summary", "/api/export/books", "/api/export/audit", "/api/accounts", "/api/accounts/manage",
    "/api/dashboard", "/api/dashboard?period=last",
]


def test_reads_never_include_the_other_users_rows(two_users):
    a, b, sa, sb = two_users
    text = _all_text(a, READ_ENDPOINTS)
    assert "AAA-VENDOR" in text and "AAA Custom Expense" in text
    assert "BBB" not in text and "222" not in text
    text_b = _all_text(b, READ_ENDPOINTS)
    assert "BBB-VENDOR" in text_b and "AAA" not in text_b


def test_numbers_are_per_user(two_users):
    a, b, sa, sb = two_users
    assert a.get("/api/stats").get_json()["total"] == 2
    assert [r["vendor"] for r in a.get("/api/documents").get_json()] and all(
        r["vendor"].startswith("AAA") for r in a.get("/api/documents").get_json()
    )
    assert a.get("/api/export/summary").get_json() == {"count": 2}
    assert a.get("/api/overview").get_json()["total"] == sa["total"]
    assert b.get("/api/overview").get_json()["total"] == sb["total"]
    ledger = a.get("/api/ledger").get_json()
    assert sum(g["total"] for g in ledger.values()) == sa["total"]
    assert [i["id"] for i in a.get("/api/queue").get_json()] == [sa["pending"]]


def test_custom_accounts_are_private(two_users):
    a, b, sa, sb = two_users
    assert sb["account"] not in a.get("/api/accounts").get_json()
    assert sa["account"] not in b.get("/api/accounts").get_json()
    # A cannot correct into B's custom account, or retire it.
    res = a.post("/api/correct", json={"id": sa["pending"], "corrected_account": sb["account"]})
    assert res.status_code == 400
    assert a.post("/api/accounts/retire", json={"name": sb["account"]}).status_code == 400
    assert sb["account"] in b.get("/api/accounts").get_json()


def test_cannot_act_on_the_other_users_queue_ids(two_users):
    a, b, sa, sb = two_users
    before = _snapshot(b.user_dir)
    target = sb["pending"]
    assert a.post("/api/confirm", json={"id": target}).status_code == 404
    assert a.post("/api/correct", json={"id": target, "corrected_account": "Rent Expense"}).status_code == 404
    assert a.delete(f"/api/queue/{target}").status_code == 404
    bulk = a.post("/api/queue/bulk_confirm", json={"ids": [target, sb["posted"]]}).get_json()
    assert bulk["confirmed"] == [] and len(bulk["failed"]) == 2
    assert _snapshot(b.user_dir) == before
    assert [i["id"] for i in b.get("/api/queue").get_json()] == [target]


def test_a_mutations_never_touch_b_files(two_users):
    a, b, sa, sb = two_users
    before = _snapshot(b.user_dir)
    a.post("/api/accounts/template", json={"template": "generic-us"})
    a.post("/api/accounts/add", json={"name": "Another"})
    a.post("/api/confirm", json={"id": sa["pending"]})
    zipped = a.get("/api/backup").data
    res = a.post("/api/restore", data={"backup": (io.BytesIO(zipped), "b.zip")}, content_type="multipart/form-data")
    assert res.status_code == 200
    assert _snapshot(b.user_dir) == before


def test_backup_contains_only_own_data_and_restore_stays_in_own_dir(two_users):
    a, b, sa, sb = two_users
    with zipfile.ZipFile(io.BytesIO(b.get("/api/backup").data)) as zf:
        blob = b"".join(zf.read(n) for n in zf.namelist())
    assert b"BBB-VENDOR" in blob and b"AAA" not in blob
    # Restoring B's own backup into A only ever writes A's files.
    b_backup = b.get("/api/backup").data
    before_b = _snapshot(b.user_dir)
    a.post("/api/restore", data={"backup": (io.BytesIO(b_backup), "x.zip")}, content_type="multipart/form-data")
    assert _snapshot(b.user_dir) == before_b


def test_restore_rejects_traversal_symlink_and_bombs(tmp_path):
    def zip_of(members, symlink=None):
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("manifest.json", json.dumps({"format_version": 1}))
            for name, data in members.items():
                zf.writestr(name, data)
            if symlink:
                info = zipfile.ZipInfo(symlink)
                info.external_attr = (0o120777 << 16)
                zf.writestr(info, "/etc/passwd")
        return buf.getvalue()

    files = {"ledger.csv": tmp_path / "u" / "ledger.csv"}
    for bad in (
        zip_of({"../ledger.csv": "x"}),
        zip_of({"/abs/ledger.csv": "x"}),
        zip_of({"sub/../ledger.csv": "x"}),
        zip_of({}, symlink="ledger.csv"),
    ):
        with pytest.raises(backup.BackupError):
            backup.restore_backup(bad, files)
    assert not (tmp_path / "u").exists()

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("manifest.json", json.dumps({"format_version": 1}))
        for i in range(30):
            zf.writestr(f"extra{i}.csv", "x")
    with pytest.raises(backup.BackupError):
        backup.restore_backup(buf.getvalue(), files)

    monkey_total = backup.MAX_TOTAL_BYTES
    try:
        backup.MAX_TOTAL_BYTES = 10
        with pytest.raises(backup.BackupError):
            backup.restore_backup(zip_of({"ledger.csv": "wrong,cols\n" * 5}), files)
    finally:
        backup.MAX_TOTAL_BYTES = monkey_total


def test_restore_endpoint_rejects_bad_zip_and_upload_over_limit(two_users):
    a, b, sa, sb = two_users
    res = a.post("/api/restore", data={"backup": (io.BytesIO(b"nope"), "x.zip")}, content_type="multipart/form-data")
    assert res.status_code == 400
    big = io.BytesIO(b"0" * (21 * 1024 * 1024))
    res = a.post("/api/restore", data={"backup": (big, "x.zip")}, content_type="multipart/form-data")
    assert res.status_code == 413 and "error" in res.get_json()


def test_restore_never_replaces_the_shared_model(two_users, tmp_path):
    a, b, *_ = two_users
    model = tmp_path / "model.joblib"
    model.write_text("shared")
    with use_user_dir(a.user_dir):
        data = backup.create_backup()
        (a.user_dir / "training.csv").write_text("vendor,description,account\nA,b,Rent Expense\n")
        data = backup.create_backup()
        backup.restore_backup(data, model_path=model)
    assert model.read_text() == "shared"


def test_no_route_serves_arbitrary_files(two_users):
    a, b, sa, sb = two_users
    bid = b.user_dir.name
    for path in (
        f"/samples/../../users/{bid}/ledger.csv",
        f"/samples/..%2F..%2Fusers%2F{bid}%2Fledger.csv",
        f"/static/../../users/{bid}/ledger.csv",
        f"/samples/%2e%2e/%2e%2e/users.json",
        f"/samples//etc/passwd",
    ):
        res = a.get(path)
        assert res.status_code in (301, 308, 400, 404), path
        assert b"BBB" not in res.data


def test_forged_or_foreign_cookie_is_rejected(two_users):
    a, b, sa, sb = two_users
    from flask.sessions import SecureCookieSessionInterface
    from itsdangerous import URLSafeTimedSerializer

    forged = URLSafeTimedSerializer("not-the-real-key", salt="cookie-session").dumps(
        {"uid": b.user["id"], "ph": "x", "csrf": "t"}
    )
    c = new_client(app_mod.app)
    c.set_cookie("session", forged)
    assert c.get("/api/queue").status_code == 401
    # A's own cookie cannot be edited to point at B (signature check).
    real = a.get_cookie("session").value
    tampered = real[:-3] + ("aaa" if not real.endswith("aaa") else "bbb")
    c2 = new_client(app_mod.app)
    c2.set_cookie("session", tampered)
    assert c2.get("/api/queue").status_code == 401


def test_user_dir_context_is_cleared_after_requests(two_users):
    a, b, *_ = two_users
    a.get("/api/queue")
    assert current_user_dir.get() is None


def test_interleaved_threads_only_see_their_own_data(two_users):
    a, b, sa, sb = two_users
    results, errors = [], []

    def run(client, tag):
        try:
            for _ in range(15):
                text = client.get("/api/documents").get_data(as_text=True) + client.get("/api/queue").get_data(as_text=True)
                results.append((tag, "AAA" in text, "BBB" in text))
        except Exception as exc:  # noqa: BLE001
            errors.append(exc)

    ta = threading.Thread(target=run, args=(a, "A"))
    tb = threading.Thread(target=run, args=(b, "B"))
    ta.start(); tb.start(); ta.join(); tb.join()
    assert not errors
    assert all(has_a and not has_b for tag, has_a, has_b in results if tag == "A")
    assert all(has_b and not has_a for tag, has_a, has_b in results if tag == "B")


# ---- storage-layer defensive check ------------------------------------------

def test_storage_functions_refuse_paths_outside_the_current_user(two_users):
    a, b, *_ = two_users
    with use_user_dir(a.user_dir):
        for fn in (queue_mod.read_pending, app_mod.read_entries):
            with pytest.raises(UserDataError):
                fn(path=b.user_dir / "ledger.csv")
        with pytest.raises(UserDataError):
            coa.add_expense_account("X", path=b.user_dir / "accounts.json")
        with pytest.raises(UserDataError):
            resolve("../../users.json", "legacy")
        with pytest.raises(UserDataError):
            resolve("ledger.csv", "legacy", explicit=Path("/etc/passwd"))
        assert resolve("ledger.csv", "legacy") == a.user_dir / "ledger.csv"


def test_symlink_inside_user_dir_cannot_escape(two_users, tmp_path):
    a, b, *_ = two_users
    (a.user_dir / "ledger.csv").unlink()
    (a.user_dir / "ledger.csv").symlink_to(b.user_dir / "ledger.csv")
    with use_user_dir(a.user_dir):
        with pytest.raises(UserDataError):
            resolve("ledger.csv", "legacy")
    try:  # the request must fail closed, never return B's rows
        body = a.get("/api/documents").data
    except UserDataError:
        body = b""
    assert b"BBB" not in body


def test_user_dir_must_be_a_real_user_id_dir(tmp_path):
    with use_user_dir(tmp_path / "not-a-user-id"):
        with pytest.raises(UserDataError):
            resolve("ledger.csv", "legacy")


def test_no_user_context_keeps_legacy_paths():
    assert resolve("ledger.csv", "/legacy/ledger.csv") == Path("/legacy/ledger.csv")


def test_queue_locks_are_per_user(two_users):
    a, b, *_ = two_users
    with use_user_dir(a.user_dir):
        la = queue_mod.queue_lock()
    with use_user_dir(b.user_dir):
        lb = queue_mod.queue_lock()
    with use_user_dir(a.user_dir):
        assert queue_mod.queue_lock() is la
    assert la is not lb
    with la:  # holding A's lock does not block B
        got = []
        t = threading.Thread(target=lambda: (lb.acquire(), got.append(1), lb.release()))
        t.start(); t.join(2)
        assert got == [1]
