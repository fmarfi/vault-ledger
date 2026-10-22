"""Desktop launcher: local server and first-run start page (no window is opened)."""

import json
import os
import urllib.request

import pytest

from vault_ledger import auth, desktop
from vault_ledger.webapp import app as app_mod, security

from tests.helpers import PASSWORD, new_client


def test_server_answers_on_a_loopback_port():
    server, base_url = desktop.start_server()
    try:
        assert base_url.startswith("http://127.0.0.1:")
        assert server.server_address[0] == "127.0.0.1"
        with urllib.request.urlopen(base_url + "/healthz", timeout=10) as resp:
            assert json.load(resp) == {"status": "ok"}
    finally:
        server.shutdown()
        server.server_close()


@pytest.fixture(autouse=True)
def clean_switches(monkeypatch):
    # setenv-then-delenv so monkeypatch restores whatever the launcher sets
    for var in ("VAULT_SKIP_LOGIN", "VAULT_ALLOW_SIGNUP"):
        monkeypatch.setenv(var, "")
        monkeypatch.delenv(var)


def test_first_run_offers_skip_and_signup():
    desktop.prepare_environment()
    assert os.environ["VAULT_SKIP_LOGIN"] == "1"
    assert os.environ["VAULT_ALLOW_SIGNUP"] == "1"


def test_switches_set_by_hand_are_kept(monkeypatch):
    monkeypatch.setenv("VAULT_SKIP_LOGIN", "0")
    monkeypatch.setenv("VAULT_ALLOW_SIGNUP", "0")
    desktop.prepare_environment()
    assert os.environ["VAULT_SKIP_LOGIN"] == "0"
    assert os.environ["VAULT_ALLOW_SIGNUP"] == "0"


def test_existing_account_does_not_enable_signup():
    auth.create_user("carol", PASSWORD)
    desktop.prepare_environment()
    assert "VAULT_ALLOW_SIGNUP" not in os.environ


def test_demo_user_alone_is_still_a_first_run():
    auth.create_demo_user()
    desktop.prepare_environment()
    assert os.environ["VAULT_ALLOW_SIGNUP"] == "1"


# ---- skip sign-in ------------------------------------------------------------

def _skip(client, **kwargs):
    token = client.page_token("/login")
    return client.post("/login/skip", data={"csrf_token": token}, **kwargs)


def test_skip_login_does_not_exist_while_switched_off():
    client = new_client(app_mod.app)
    assert "Continue without signing in" not in client.get("/login").get_data(as_text=True)
    assert _skip(client).status_code == 404
    assert client.get("/api/queue").status_code == 401


def test_skip_login_signs_in_as_the_local_account(monkeypatch):
    monkeypatch.setenv("VAULT_SKIP_LOGIN", "1")
    client = new_client(app_mod.app)
    assert "Continue without signing in" in client.get("/login").get_data(as_text=True)
    assert _skip(client).status_code == 302
    assert client.get("/api/queue").status_code == 200
    local = auth.find_by_username(security.SKIP_LOGIN_USERNAME)
    # a second use opens the same account, not a new one
    assert _skip(new_client(app_mod.app)).status_code == 302
    assert [u["id"] for u in auth.list_users()] == [local["id"]]


def test_skip_login_needs_the_csrf_token(monkeypatch):
    monkeypatch.setenv("VAULT_SKIP_LOGIN", "1")
    client = new_client(app_mod.app)
    assert client.post("/login/skip").status_code == 403
    assert client.get("/api/queue").status_code == 401


def test_skip_login_is_refused_from_another_machine(monkeypatch):
    monkeypatch.setenv("VAULT_SKIP_LOGIN", "1")
    client = new_client(app_mod.app)
    remote = {"environ_overrides": {"REMOTE_ADDR": "192.168.1.20"}}
    assert "Continue without signing in" not in client.get("/login", **remote).get_data(as_text=True)
    assert _skip(client, **remote).status_code == 404
    assert auth.find_by_username(security.SKIP_LOGIN_USERNAME) is None
