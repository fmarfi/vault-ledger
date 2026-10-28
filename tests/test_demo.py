"""Demo mode (VAULT_DEMO=1): throwaway seeded demo users, isolated from each
other and from real users, deleted on exit and after 24 hours."""

import io
import json
from datetime import date, datetime, timedelta, timezone

import pytest

from vault_ledger import auth, backup, coa, demo, userdata
from vault_ledger.confidence_gate import CONFIDENCE_THRESHOLD
from vault_ledger.rules.entry_rules import construct_entry
from vault_ledger.userdata import use_user_dir
from vault_ledger.webapp import app as app_mod, security

from tests.helpers import PASSWORD, make_user_client, new_client

READS = ["/api/queue", "/api/documents", "/api/ledger", "/api/export/books", "/api/export/audit"]


@pytest.fixture
def demo_on(monkeypatch):
    monkeypatch.setenv("VAULT_DEMO", "1")


def start_demo(client=None):
    """Click "Try the demo" the way a browser does: token from the login page."""
    client = client or new_client(app_mod.app)
    token = client.page_token("/login")
    res = client.post("/demo/start", data={"csrf_token": token})
    assert res.status_code == 302 and res.headers["Location"] == "/", res.status_code
    client.csrf = client.page_token("/settings")
    client.user = next(u for u in auth.list_users() if u["username"] in client.get("/").get_data(as_text=True))
    client.user_dir = userdata.user_dir_for(client.user["id"])
    return client


def _demo_records():
    return [u for u in auth.list_users() if u.get("demo")]


# ---- the switch --------------------------------------------------------------

def test_demo_start_is_404_when_switch_is_off():
    anon = new_client(app_mod.app)
    token = anon.page_token("/login")
    assert anon.post("/demo/start", data={"csrf_token": token}).status_code == 404
    assert anon.post("/demo/start").status_code == 403  # CSRF is checked first, as on every POST
    assert auth.list_users() == []


def test_reset_and_exit_are_404_for_a_real_user_whatever_the_switch(monkeypatch):
    alice = make_user_client(app_mod.app, "alice")
    for switch in (None, "1"):
        if switch:
            monkeypatch.setenv("VAULT_DEMO", switch)
        for path in ("/demo/reset", "/demo/exit"):
            assert alice.post(path).status_code == 404, (switch, path)
    assert auth.get_user(alice.user["id"]) is not None and alice.user_dir.is_dir()
    assert alice.get("/api/queue").status_code == 200  # still signed in, nothing deleted


def test_login_page_shows_the_button_only_when_enabled(monkeypatch):
    anon = new_client(app_mod.app)
    off = anon.get("/login").get_data(as_text=True)
    assert "Try the demo" not in off and "/demo/start" not in off
    monkeypatch.setenv("VAULT_DEMO", "1")
    on = anon.get("/login").get_data(as_text=True)
    assert "Try the demo" in on and 'action="/demo/start"' in on


def test_turning_the_switch_off_ends_demo_sessions(demo_on, monkeypatch):
    client = start_demo()
    assert client.get("/api/queue").status_code == 200
    monkeypatch.delenv("VAULT_DEMO")
    assert client.get("/api/queue").status_code == 401
    assert client.post("/demo/exit").status_code in (401, 403)


# ---- starting a demo ---------------------------------------------------------

def test_start_creates_a_flagged_throwaway_user_with_seeded_data(demo_on):
    client = start_demo()
    user = client.user
    assert user["demo"] is True and user["is_admin"] is False
    assert user["username"].startswith("demo-") and len(user["username"]) == len("demo-") + 8
    assert userdata.USER_ID_RE.fullmatch(user["id"])
    assert client.user_dir.is_dir() and client.user_dir.parent == userdata.users_root()

    documents = client.get("/api/documents").get_json()
    queue = client.get("/api/queue").get_json()
    assert len(documents) == len(demo.LEDGER_SEED) and 25 <= len(documents) <= 35
    assert len(queue) == len(demo.QUEUE_SEED) and 5 <= len(queue) <= 7
    # every default expense account is represented, and only accounts that exist
    assert {d["account"] for d in documents} == coa.EXPENSE_ACCOUNTS
    assert {q["predicted_account"] for q in queue} <= coa.EXPENSE_ACCOUNTS
    # spread over the last three months, relative to today
    days = sorted(date.fromisoformat(d["date"]) for d in documents)
    assert days[-1] <= date.today() and date.today() - days[0] <= timedelta(days=92)
    assert days[-1] - days[0] >= timedelta(days=60)
    assert all(d["filename"].startswith("demo-") for d in documents + queue)


def test_every_seeded_entry_balances(demo_on):
    client = start_demo()
    with use_user_dir(client.user_dir):
        for row in client.get("/api/documents").get_json():
            for paid in (True, False):
                entry = construct_entry(row["account"], float(row["amount"]), paid)
                assert entry.total_debits == entry.total_credits == float(row["amount"]) > 0
    for item in client.get("/api/queue").get_json():
        entry = json.loads(item["entry_json"])
        assert entry["total_debits"] == entry["total_credits"] == float(item["amount"])
        debit, credit = entry["lines"]
        assert debit["account"] == item["predicted_account"]
        assert credit["account"] == (coa.CASH_BANK if item["paid"] == "True" else coa.ACCOUNTS_PAYABLE)
    assert {s.paid for s in demo.LEDGER_SEED} == {True, False}


def test_queue_flags_follow_the_confidence_gate(demo_on):
    client = start_demo()
    queue = client.get("/api/queue").get_json()
    flagged = [q for q in queue if q["needs_review"] == "True"]
    eligible = [q for q in queue if q["needs_review"] != "True"]
    assert len(eligible) >= 3
    assert all(float(q["confidence"]) < CONFIDENCE_THRESHOLD for q in flagged)
    assert all(float(q["confidence"]) >= CONFIDENCE_THRESHOLD for q in eligible)

    res = client.post("/api/queue/bulk_confirm", json={"ids": [q["id"] for q in queue]}).get_json()
    assert sorted(res["confirmed"]) == sorted(q["id"] for q in eligible)
    assert sorted(f["id"] for f in res["failed"]) == sorted(q["id"] for q in flagged)
    # an escalated item, if any, can still be resolved by hand
    for item in flagged:
        assert client.post("/api/confirm", json={"id": item["id"]}).status_code == 200
    assert len(client.get("/api/documents").get_json()) == len(demo.LEDGER_SEED) + len(queue)


def test_seed_refuses_to_run_outside_a_user_directory():
    with pytest.raises(userdata.UserDataError):
        demo.seed(app_mod._get_classifier(), app_mod._serialize_entry)


def test_banner_on_every_page_for_demo_users_only(demo_on):
    client = start_demo()
    for path in ("/", "/documents", "/ledger", "/overview", "/export", "/settings"):
        page = client.get(path).get_data(as_text=True)
        assert 'class="demo-banner"' in page and "nothing here is real" in page, path
        assert 'action="/demo/reset"' in page and 'action="/demo/exit"' in page, path
    alice = make_user_client(app_mod.app, "alice")
    page = alice.get("/").get_data(as_text=True)
    assert "demo-banner" not in page and "/demo/reset" not in page


# ---- isolation ---------------------------------------------------------------

def test_two_demo_sessions_and_a_real_user_never_see_each_other(demo_on):
    one, two = start_demo(), start_demo()
    alice = make_user_client(app_mod.app, "alice")
    assert one.user["id"] != two.user["id"] and one.user_dir != two.user_dir

    marker = "ONLY-IN-DEMO-ONE"
    with use_user_dir(one.user_dir):
        item = app_mod.enqueue(
            filename="m.png", vendor=marker, description="x", date="2026-01-01", amount=5.0, paid=True,
            predicted_account=coa.GENERAL_EXPENSE, confidence=0.9, needs_review=False,
            rejection_reason=None, entry_json="{}",
        )
    assert one.post("/api/confirm", json={"id": item}).status_code == 200
    assert marker in one.get("/api/documents").get_data(as_text=True)

    for other in (two, alice):
        text = "\n".join(other.get(p).get_data(as_text=True) for p in READS)
        assert marker not in text
        assert other.post("/api/confirm", json={"id": item}).status_code == 404
    assert len(two.get("/api/documents").get_json()) == len(demo.LEDGER_SEED)
    # a real user sees no demo data at all
    assert alice.get("/api/documents").get_json() == [] and alice.get("/api/queue").get_json() == []
    assert "Spaces Zuidas" not in alice.get("/api/export/books").get_data(as_text=True)


def test_starting_a_demo_while_signed_in_as_a_real_user_leaves_their_data_alone(demo_on):
    alice = make_user_client(app_mod.app, "alice")
    assert alice.post("/demo/start").status_code == 302
    assert not (alice.user_dir / "ledger.csv").exists() and not (alice.user_dir / "pending_queue.csv").exists()
    assert auth.get_user(alice.user["id"]) is not None
    # the browser is now the demo user, not alice
    assert len(alice.get("/api/documents").get_json()) == len(demo.LEDGER_SEED)
    assert len(_demo_records()) == 1


# ---- reset / exit ------------------------------------------------------------

def test_reset_restores_the_seed_after_changes(demo_on):
    client = start_demo()
    first = client.get("/api/queue").get_json()
    assert client.delete(f"/api/queue/{first[0]['id']}").status_code == 200
    assert client.post("/api/confirm", json={"id": first[1]["id"]}).status_code == 200
    assert client.post("/api/accounts/add", json={"name": "Scratch Expense"}).status_code == 200
    assert len(client.get("/api/queue").get_json()) == len(demo.QUEUE_SEED) - 2

    res = client.post("/demo/reset")
    assert res.status_code == 302 and res.headers["Location"] == "/"
    queue = client.get("/api/queue").get_json()
    documents = client.get("/api/documents").get_json()
    assert len(queue) == len(demo.QUEUE_SEED) and len(documents) == len(demo.LEDGER_SEED)
    key = lambda rows: sorted((r["vendor"], r["description"], r["amount"]) for r in rows)  # noqa: E731
    assert key(queue) == key(first)
    assert "Scratch Expense" not in client.get("/api/accounts").get_json()
    assert auth.get_user(client.user["id"]) is not None  # same user, same session


def test_exit_deletes_the_user_and_directory(demo_on):
    client, other = start_demo(), start_demo()
    res = client.post("/demo/exit")
    assert res.status_code == 302 and res.headers["Location"] == "/login"
    assert auth.get_user(client.user["id"]) is None and not client.user_dir.exists()
    assert client.get("/api/queue").status_code == 401
    # only that one: the other demo user is untouched
    assert auth.get_user(other.user["id"]) is not None and other.user_dir.is_dir()
    assert other.get("/api/queue").status_code == 200


def test_delete_demo_user_refuses_a_real_user():
    real = auth.create_user("carol", PASSWORD)
    assert auth.delete_demo_user(real["id"]) is False
    assert auth.delete_demo_user("0" * 32) is False
    assert auth.get_user(real["id"]) is not None and userdata.user_dir_for(real["id"]).is_dir()


# ---- no password login -------------------------------------------------------

def test_demo_user_cannot_sign_in_with_a_password(demo_on):
    client = start_demo()
    name = client.user["username"]
    # even an operator-set password does not open a demo account
    auth.set_password(name, PASSWORD)
    assert auth.authenticate(name, PASSWORD) is None
    anon = new_client(app_mod.app)
    token = anon.page_token("/login")
    res = anon.post("/login", data={"username": name, "password": PASSWORD, "csrf_token": token})
    assert res.status_code == 401 and security.GENERIC_LOGIN_ERROR in res.get_data(as_text=True)
    assert anon.get("/api/queue").status_code == 401


def test_demo_password_is_never_exposed(demo_on):
    client = start_demo()
    assert set(client.user) == {"id", "username", "password_hash", "created_at", "is_admin", "demo"}
    assert client.user["password_hash"].startswith(("scrypt:", "pbkdf2:"))


def test_demo_prefix_is_reserved_for_demo_users():
    with pytest.raises(auth.AuthError):
        auth.create_user("demo-12345678", PASSWORD)


# ---- cleanup -----------------------------------------------------------------

def _age(user_id, hours):
    users = auth.list_users()
    for u in users:
        if u["id"] == user_id:
            u["created_at"] = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat(timespec="seconds")
    auth._write_users(users)


def test_expired_demo_users_are_cleaned_up_when_a_new_demo_starts(demo_on):
    old, fresh = start_demo(), start_demo()
    real = auth.create_user("carol", PASSWORD)
    _age(old.user["id"], 25)
    _age(fresh.user["id"], 23)
    _age(real["id"], 24 * 30)  # a real user is never purged, however old

    newest = start_demo()
    assert auth.get_user(old.user["id"]) is None and not old.user_dir.exists()
    assert old.get("/api/queue").status_code == 401
    for kept in (fresh.user, newest.user, real):
        assert auth.get_user(kept["id"]) is not None and userdata.user_dir_for(kept["id"]).is_dir()


def test_demo_starts_are_throttled_per_ip(demo_on):
    anon = new_client(app_mod.app)
    token = anon.page_token("/login")
    for _ in range(security.MAX_DEMO_STARTS):
        security.throttle.fail(("127.0.0.1", "*demo"))
    res = anon.post("/demo/start", data={"csrf_token": token})
    assert res.status_code == 429 and security.DEMO_THROTTLED_ERROR in res.get_data(as_text=True)
    assert _demo_records() == []


# ---- CSRF and what a demo user may not do ------------------------------------

def test_csrf_is_enforced_on_all_three_post_routes(demo_on):
    anon = new_client(app_mod.app)
    anon.get("/login")
    assert anon.post("/demo/start").status_code == 403
    assert anon.post("/demo/start", data={"csrf_token": "wrong"}).status_code == 403
    assert _demo_records() == []

    client = start_demo()
    token, client.csrf = client.csrf, None
    for path in ("/demo/reset", "/demo/exit"):
        assert client.post(path).status_code == 403, path
        assert client.post(path, headers={"X-CSRF-Token": "wrong"}).status_code == 403, path
    assert auth.get_user(client.user["id"]) is not None and client.user_dir.is_dir()
    assert client.post("/demo/exit", data={"csrf_token": token}).status_code == 302


def test_demo_routes_require_a_session_for_reset_and_exit(demo_on):
    anon = new_client(app_mod.app)
    for path in ("/demo/reset", "/demo/exit"):
        assert anon.post(path).status_code == 401


def test_demo_user_cannot_restore_a_backup_but_can_download_one(demo_on):
    client = start_demo()
    download = client.get("/api/backup")
    assert download.status_code == 200
    with use_user_dir(client.user_dir):
        before = backup.create_backup()
    res = client.post(
        "/api/restore", data={"backup": (io.BytesIO(download.data), "b.zip")}, content_type="multipart/form-data"
    )
    assert res.status_code == 403 and "demo" in res.get_json()["error"]
    assert not (client.user_dir / "backups").exists()  # refused before the safety copy is written
    assert len(client.get("/api/documents").get_json()) == len(demo.LEDGER_SEED)
    assert before  # sanity: there was something to restore over
    settings = client.get("/settings").get_data(as_text=True)
    assert 'id="restore-btn" class="btn btn-secondary" type="button" disabled' in settings


def test_sign_out_also_removes_a_demo_user(demo_on):
    client = start_demo()
    assert client.post("/logout").status_code == 302
    assert auth.get_user(client.user["id"]) is None and not client.user_dir.exists()
