"""Login, sessions, CSRF, throttling, access control and hardening."""

import json
import os
import re
import stat
import sys

import pytest

from vault_ledger import auth, userdata
from vault_ledger.webapp import app as app_mod, security

from tests.helpers import PASSWORD, login, make_user_client, new_client

# demo_start: 404 unless VAULT_DEMO=1; skip_login: 404 unless VAULT_SKIP_LOGIN=1 and from this machine
PUBLIC = {"login", "logout", "signup", "healthz", "static", "demo_start", "skip_login"}


@pytest.fixture
def anon():
    return new_client(app_mod.app)


@pytest.fixture
def user():
    return auth.create_user("carol", PASSWORD)


def _post_login(client, username, password, next_url=None):
    token = client.page_token("/login")
    data = {"username": username, "password": password, "csrf_token": token}
    if next_url:
        data["next"] = next_url
    return client.post("/login", data=data)


# ---- login ------------------------------------------------------------------

def test_login_success_redirects_and_grants_access(anon, user):
    assert anon.get("/api/queue").status_code == 401
    res = _post_login(anon, "carol", PASSWORD)
    assert res.status_code == 302 and res.headers["Location"] == "/"
    assert anon.get("/api/queue").status_code == 200
    page = anon.get("/").get_data(as_text=True)
    assert "carol" in page and "Sign out" in page and 'name="csrf-token"' in page


def test_username_is_case_insensitive_at_login(anon, user):
    assert _post_login(anon, "CaRoL", PASSWORD).status_code == 302


def test_failures_give_identical_generic_errors(anon, user):
    wrong = _post_login(anon, "carol", "wrong password!!")
    unknown = _post_login(anon, "nobody", "wrong password!!")
    assert wrong.status_code == unknown.status_code == 401
    def error_of(r):
        return re.search(r'role="alert">([^<]*)<', r.get_data(as_text=True)).group(1)
    assert error_of(wrong) == error_of(unknown) == security.GENERIC_LOGIN_ERROR


def test_unknown_user_still_costs_a_hash(anon, monkeypatch):
    calls = []
    real = auth.check_password_hash
    monkeypatch.setattr(auth, "check_password_hash", lambda h, p: calls.append(h) or real(h, p))
    _post_login(anon, "ghost", "whatever-password")
    assert calls == [auth._DUMMY_HASH]


def test_throttle_after_five_failures(anon, user):
    for _ in range(5):
        assert _post_login(anon, "carol", "bad-password-1").status_code == 401
    res = _post_login(anon, "carol", PASSWORD)  # even the right password is refused
    assert res.status_code == 429
    assert security.THROTTLED_ERROR in res.get_data(as_text=True)
    assert anon.get("/api/queue").status_code == 401
    # another username from the same IP is a separate key
    auth.create_user("dave", PASSWORD)
    assert _post_login(new_client(app_mod.app), "dave", PASSWORD).status_code == 302


def test_throttle_applies_to_unknown_usernames_and_resets_on_success(anon, user):
    for _ in range(5):
        _post_login(anon, "ghost", "bad-password-1")
    assert _post_login(anon, "ghost", "bad-password-1").status_code == 429
    for _ in range(3):
        _post_login(anon, "carol", "bad-password-1")
    assert _post_login(anon, "carol", PASSWORD).status_code == 302
    assert not security.throttle.blocked(("127.0.0.1", "carol"), 1)


def test_passwords_are_not_logged(anon, user, caplog):
    caplog.set_level("DEBUG")
    _post_login(anon, "carol", "super-secret-attempt")
    assert "super-secret-attempt" not in caplog.text


def test_logout_clears_session(user):
    c = login(new_client(app_mod.app), "carol")
    assert c.post("/logout").status_code == 302
    assert c.get("/api/queue").status_code == 401
    assert c.get_cookie("session") is None or "uid" not in json.dumps(_session_payload(c))


def _session_payload(c):
    with c.session_transaction() as s:
        return dict(s)


def test_logout_requires_csrf_when_logged_in(user):
    c = login(new_client(app_mod.app), "carol")
    c.csrf = None
    assert c.post("/logout").status_code == 403
    assert c.get("/api/queue").status_code == 200


def test_login_rotates_session_and_csrf_token(anon, user):
    before = anon.page_token("/login")
    _post_login(anon, "carol", PASSWORD)
    after = anon.page_token("/settings")
    assert before and after and before != after


def test_password_change_and_user_delete_invalidate_sessions(user):
    c = login(new_client(app_mod.app), "carol")
    auth.set_password("carol", "another long password")
    assert c.get("/api/queue").status_code == 401
    c2 = login(new_client(app_mod.app), "carol", "another long password")
    auth.delete_user("carol")
    assert c2.get("/api/queue").status_code == 401


# ---- cookies ----------------------------------------------------------------

def _login_cookie_header(anon):
    res = _post_login(anon, "carol", PASSWORD)
    return next(h for h in res.headers.getlist("Set-Cookie") if h.startswith("session="))


def test_session_cookie_flags(anon, user):
    header = _login_cookie_header(anon)
    assert "HttpOnly" in header and "SameSite=Lax" in header
    assert "Secure" not in header
    assert re.search(r"Expires=|Max-Age=", header)


def test_session_cookie_secure_when_configured(anon, user, monkeypatch):
    monkeypatch.setenv("VAULT_COOKIE_SECURE", "1")
    assert "Secure" in _login_cookie_header(anon)


def test_session_lifetime_is_eight_hours():
    assert app_mod.app.config["PERMANENT_SESSION_LIFETIME"].total_seconds() == 8 * 3600


# ---- CSRF -------------------------------------------------------------------

def _fill(rule):
    path = str(rule)
    for arg in rule.arguments:
        path = path.replace(f"<{arg}>", "x").replace(f"<path:{arg}>", "x")
    return re.sub(r"<[^>]+>", "x", path)


def _rules(mutating):
    out = []
    for rule in app_mod.app.url_map.iter_rules():
        methods = rule.methods - {"HEAD", "OPTIONS"}
        if mutating:
            methods &= {"POST", "PUT", "PATCH", "DELETE"}
        else:
            methods &= {"GET"}
        for m in methods:
            out.append((rule, m))
    return out


def test_every_mutating_endpoint_requires_csrf(user):
    c = login(new_client(app_mod.app), "carol")
    good = c.csrf
    checked = 0
    for rule, method in _rules(mutating=True):
        path = _fill(rule)
        for bad in (None, "wrong-token"):
            c.csrf = None
            headers = {"X-CSRF-Token": bad} if bad else {}
            res = c.open(path, method=method, headers=headers, json={})
            assert res.status_code == 403, (method, path, bad)
            assert "CSRF" in res.get_json()["error"]
        checked += 1
    assert checked >= 10
    # with the token the request gets past CSRF (any other status is fine)
    c.csrf = good
    assert c.post("/api/queue/bulk_confirm", json={"ids": []}).status_code == 400
    assert c.delete("/api/queue/nonexistent").status_code == 404


def test_login_and_signup_forms_need_csrf(anon, user, monkeypatch):
    anon.get("/login")
    res = anon.post("/login", data={"username": "carol", "password": PASSWORD})
    assert res.status_code == 403
    monkeypatch.setenv("VAULT_ALLOW_SIGNUP", "1")
    anon.get("/signup")
    assert anon.post("/signup", data={"username": "newuser", "password": PASSWORD, "password2": PASSWORD}).status_code == 403


def test_csrf_token_in_form_field_is_accepted_but_not_cross_session(user):
    a = login(new_client(app_mod.app), "carol")
    b = login(new_client(app_mod.app), "carol")
    b.csrf = a.csrf  # a token from another session must not work
    assert b.post("/api/queue/bulk_confirm", json={"ids": []}).status_code == 403


# ---- access control ---------------------------------------------------------

def test_public_endpoint_set_is_exactly_the_reviewed_one():
    assert set(security.PUBLIC_ENDPOINTS) == PUBLIC


def test_every_registered_route_requires_login(anon):
    covered = 0
    for rule in app_mod.app.url_map.iter_rules():
        if rule.endpoint in PUBLIC:
            continue
        path = _fill(rule)
        for method in rule.methods - {"HEAD", "OPTIONS"}:
            res = anon.open(path, method=method)
            if method != "GET" or path.startswith(("/api/", "/samples/")):
                assert res.status_code == 401, (method, path)
                assert res.get_json() == {"error": "authentication required"}
            else:
                assert res.status_code == 302, (method, path)
                assert res.headers["Location"].startswith("/login?next=")
            covered += 1
    assert covered >= 25


def test_health_and_samples_require_login_and_healthz_leaks_nothing(anon, user):
    assert anon.get("/api/health").status_code == 401
    assert anon.get("/samples/whatever.png").status_code == 401
    res = anon.get("/healthz")
    assert res.status_code == 200 and res.get_json() == {"status": "ok"}
    assert anon.get("/static/style.css").status_code == 200


def test_unauthenticated_page_redirects_with_safe_next(anon):
    res = anon.get("/ledger")
    assert res.status_code == 302 and res.headers["Location"] == "/login?next=/ledger"


@pytest.mark.parametrize("target", [
    "https://evil.example/", "//evil.example", "/\\evil.example", "http:evil.example", "javascript:alert(1)",
    "///evil.example", "/ok\r\nSet-Cookie: x=y", "evil.example", "/\t/evil.example", "/login", "",
])
def test_open_redirect_is_refused(anon, user, target):
    res = _post_login(anon, "carol", PASSWORD, next_url=target)
    assert res.status_code == 302 and res.headers["Location"] == "/"


def test_safe_relative_next_is_honoured(anon, user):
    res = _post_login(anon, "carol", PASSWORD, next_url="/ledger?x=1")
    assert res.headers["Location"] == "/ledger?x=1"


def test_login_page_redirects_when_already_signed_in(user):
    c = login(new_client(app_mod.app), "carol")
    assert c.get("/login?next=//evil.example").headers["Location"] == "/"


def test_signup_is_off_by_default_and_works_when_enabled(anon, monkeypatch):
    assert anon.get("/signup").status_code == 404
    monkeypatch.setenv("VAULT_ALLOW_SIGNUP", "1")
    token = anon.page_token("/signup")
    short = anon.post("/signup", data={"username": "newuser", "password": "short", "password2": "short", "csrf_token": token})
    assert short.status_code == 400
    ok = anon.post("/signup", data={"username": "newuser", "password": PASSWORD, "password2": PASSWORD, "csrf_token": token})
    assert ok.status_code == 302
    assert anon.get("/api/queue").status_code == 200


# ---- headers ----------------------------------------------------------------

def test_security_headers(user):
    c = login(new_client(app_mod.app), "carol")
    for path in ("/api/queue", "/", "/healthz", "/login"):
        h = c.get(path).headers
        assert h["X-Content-Type-Options"] == "nosniff"
        assert h["X-Frame-Options"] == "DENY"
        assert h["Referrer-Policy"] == "same-origin"
        assert h["Cache-Control"] == "no-store"
        for part in ("frame-ancestors 'none'", "base-uri 'self'", "form-action 'self'"):
            assert part in h["Content-Security-Policy"]
        assert "script-src" not in h["Content-Security-Policy"]
    assert "no-store" not in c.get("/static/style.css").headers.get("Cache-Control", "")


# ---- users store ------------------------------------------------------------

def test_password_hashes_are_never_plaintext(user):
    raw = auth.users_file().read_text()
    assert PASSWORD not in raw
    stored = json.loads(raw)["users"][0]
    assert stored["password_hash"].startswith("scrypt:")
    assert set(stored) == {"id", "username", "password_hash", "created_at", "is_admin"}
    assert re.fullmatch(r"[0-9a-f]{32}", stored["id"])
    if os.name == "posix":
        assert stat.S_IMODE(auth.users_file().stat().st_mode) == 0o600


def test_users_json_written_atomically(user, monkeypatch):
    before = auth.users_file().read_text()

    def boom(*a, **k):
        raise OSError("disk full")

    monkeypatch.setattr(auth.os, "replace", boom)
    with pytest.raises(OSError):
        auth.create_user("second", PASSWORD)
    assert auth.users_file().read_text() == before
    assert not list(auth.users_file().parent.glob("*.tmp"))


def test_usernames_are_unique_case_insensitive(user):
    with pytest.raises(auth.AuthError):
        auth.create_user("CAROL", PASSWORD)


@pytest.mark.parametrize("bad", ["ab", "x" * 33, "has space", "a/b", "../x", "..", "...", "/etc/passwd", "C:\\x",
                                 "ａｄｍｉｎ", "İstanbul", "us\x00er", "ünïcode", "a b", "%2e%2e", ""])
def test_bad_usernames_rejected(bad):
    with pytest.raises(auth.AuthError):
        auth.create_user(bad, PASSWORD)


@pytest.mark.parametrize("pw,name", [("short", "x1234"), ("a" * 300, "x1234"), ("samename123", "samename123"),
                                     ("SameName123", "samename123")])
def test_password_policy(pw, name):
    with pytest.raises(auth.AuthError):
        auth.create_user(name, pw)


def test_paths_come_from_ids_never_usernames(user):
    assert userdata.user_dir_for(user["id"]).name == user["id"]
    for bad in ("../x", "/etc", "carol", user["id"].upper(), user["id"] + "/..", user["id"][:-1], "", None):
        with pytest.raises(userdata.UserDataError):
            userdata.user_dir_for(bad)
    assert not any(p.name == "carol" for p in userdata.users_root().iterdir())


# ---- secret key ---------------------------------------------------------------

@pytest.mark.skipif(sys.platform == "win32", reason="POSIX modes")
def test_secret_key_file_is_0600_random_and_reused(tmp_path, monkeypatch):
    key = security.secret_key()
    path = userdata.data_dir() / ".secret_key"
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    assert len(key) >= 64 and key == security.secret_key()
    security._key_cache.clear()
    assert security.secret_key() == key  # persisted, not regenerated
    monkeypatch.setenv("VAULT_DATA_DIR", str(tmp_path / "other"))
    assert security.secret_key() != key  # no hardcoded default


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX modes")
def test_loose_secret_key_mode_is_tightened():
    security.secret_key()
    path = userdata.data_dir() / ".secret_key"
    path.chmod(0o644)
    security._key_cache.clear()
    security.secret_key()
    assert stat.S_IMODE(path.stat().st_mode) == 0o600


def test_env_secret_key_wins(monkeypatch):
    monkeypatch.setenv("VAULT_SECRET_KEY", "from-env-" + "x" * 40)
    assert security.secret_key().startswith("from-env-")
    assert not (userdata.data_dir() / ".secret_key").exists()


def test_no_hardcoded_secret_in_source():
    src = open(security.__file__).read() + open(app_mod.__file__).read()
    assert not re.search(r"secret_key\s*=\s*['\"]", src)
    assert not re.search(r"SECRET_KEY['\"]\s*[:=,]\s*['\"]", src)


# ---- startup config -----------------------------------------------------------

def test_debug_defaults_off_and_binds_loopback(monkeypatch):
    seen = {}
    monkeypatch.setattr(app_mod.app, "run", lambda **kw: seen.update(kw))
    monkeypatch.setattr(app_mod.hardware, "check", lambda: {"level": "ok"})
    for var in ("VAULT_DEBUG", "VAULT_HOST", "VAULT_PORT"):
        monkeypatch.delenv(var, raising=False)
    app_mod.main()
    assert seen == {"host": "127.0.0.1", "port": 5050, "debug": False}
    monkeypatch.setenv("VAULT_PORT", "5099")
    monkeypatch.setenv("VAULT_HOST", "0.0.0.0")
    app_mod.main()
    assert seen["port"] == 5099 and seen["host"] == "0.0.0.0" and seen["debug"] is False


@pytest.mark.parametrize("host", ["0.0.0.0", "192.168.1.5", "example.com", "::"])
def test_debug_with_non_loopback_host_refuses_to_start(monkeypatch, host):
    monkeypatch.setattr(app_mod.app, "run", lambda **kw: pytest.fail("must not start"))
    monkeypatch.setenv("VAULT_DEBUG", "1")
    monkeypatch.setenv("VAULT_HOST", host)
    with pytest.raises(SystemExit):
        app_mod.main()


def test_debug_on_loopback_is_allowed(monkeypatch):
    seen = {}
    monkeypatch.setattr(app_mod.app, "run", lambda **kw: seen.update(kw))
    monkeypatch.setattr(app_mod.hardware, "check", lambda: {"level": "ok"})
    monkeypatch.setenv("VAULT_DEBUG", "1")
    monkeypatch.setenv("VAULT_HOST", "127.0.0.1")
    app_mod.main()
    assert seen["debug"] is True


def test_wsgi_module_exposes_app():
    from vault_ledger.webapp import wsgi

    assert wsgi.app is app_mod.app


def test_max_upload_is_20mb():
    assert app_mod.app.config["MAX_CONTENT_LENGTH"] == 20 * 1024 * 1024


# ---- CLI + legacy migration ---------------------------------------------------

def test_cli_add_list_set_password_delete(monkeypatch, capsys):
    answers = iter([PASSWORD, PASSWORD, "different long pw", "different long pw"])
    monkeypatch.setattr(auth.getpass, "getpass", lambda prompt="": next(answers))
    assert auth.main(["add-user", "Erin"]) == 0
    user = auth.find_by_username("erin")
    assert userdata.user_dir_for(user["id"]).is_dir()
    assert auth.authenticate("erin", PASSWORD)
    assert auth.main(["set-password", "erin"]) == 0
    assert auth.authenticate("erin", PASSWORD) is None and auth.authenticate("erin", "different long pw")
    auth.main(["list-users"])
    assert "erin" in capsys.readouterr().out
    (userdata.user_dir_for(user["id"]) / "ledger.csv").write_text("x")
    other = auth.create_user("frank", PASSWORD)
    monkeypatch.setattr("builtins.input", lambda prompt="": "no")
    assert auth.main(["delete-user", "erin"]) == 1 and auth.find_by_username("erin")
    monkeypatch.setattr("builtins.input", lambda prompt="": "erin")
    assert auth.main(["delete-user", "erin"]) == 0
    assert auth.find_by_username("erin") is None
    assert not userdata.user_dir_for(user["id"]).exists()
    assert userdata.user_dir_for(other["id"]).is_dir()  # only that user's data was removed


def test_cli_password_mismatch_and_policy(monkeypatch):
    answers = iter([PASSWORD, "different"])
    monkeypatch.setattr(auth.getpass, "getpass", lambda prompt="": next(answers))
    assert auth.main(["add-user", "gina"]) == 1
    assert auth.find_by_username("gina") is None


def test_migrate_legacy_copies_verifies_and_keeps_originals(tmp_path):
    repo = tmp_path / "repo"
    (repo / "data" / "backups").mkdir(parents=True)
    (repo / "data" / "ledger.csv").write_text("ledger-data")
    (repo / "data" / "accounts.json").write_text("{}")
    (repo / "data" / "backups" / "b.zip").write_bytes(b"zip")
    (repo / "corrections.csv").write_text("corr")
    user = auth.create_user("henry", PASSWORD)
    copied = auth.migrate_legacy("henry", repo=repo)
    dest = userdata.user_dir_for(user["id"])
    assert len(copied) == 4
    assert (dest / "ledger.csv").read_text() == "ledger-data"
    assert (dest / "corrections.csv").read_text() == "corr"
    assert (dest / "backups" / "b.zip").read_bytes() == b"zip"
    assert (repo / "data" / "ledger.csv").exists()  # originals never deleted
    assert (repo / "data" / ".migrated").exists()
    with pytest.raises(auth.AuthError):
        auth.migrate_legacy("henry", repo=repo)
    with pytest.raises(auth.AuthError):
        auth.migrate_legacy("nobody", repo=repo)


def test_upload_too_large_gets_a_json_413(user):
    c = login(new_client(app_mod.app), "carol")
    import io
    res = c.post("/api/process", data={"document": (io.BytesIO(b"0" * (21 * 1024 * 1024)), "big.png")},
                 content_type="multipart/form-data")
    assert res.status_code == 413 and "too large" in res.get_json()["error"]
