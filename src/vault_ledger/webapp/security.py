"""Login, sessions, CSRF, login throttling, access control and security
headers for the web app. `init_app(app)` wires everything up; app.py calls it
once. Nothing here knows about ledgers or queues -- it only decides who the
caller is, and points the storage layer (vault_ledger.userdata) at that
user's private directory for the duration of the request.

Deliberately in-process: the throttle and the per-user locks live in this
Python process, so run ONE server process (threads are fine).
"""

from __future__ import annotations

import collections
import contextlib
import hmac
import ipaddress
import os
import secrets
import threading
import time
from datetime import timedelta
from urllib.parse import quote, urlsplit

from flask import (
    Flask, g, jsonify, redirect, render_template, request, session, url_for,
)
from flask.sessions import SecureCookieSessionInterface
from werkzeug.exceptions import HTTPException

from vault_ledger import auth, userdata

# Endpoints reachable without a login. Everything else is protected by default,
# so a route added later is protected unless someone opts it out here.
PUBLIC_ENDPOINTS = frozenset({"login", "logout", "signup", "healthz", "static", "demo_start", "skip_login"})
# Skip sign-in (VAULT_SKIP_LOGIN=1): the account the button signs in as.
SKIP_LOGIN_USERNAME = "local"
# Demo mode (VAULT_DEMO=1). These do not exist while the switch is off.
DEMO_ENDPOINTS = frozenset({"demo_start", "demo_reset", "demo_exit"})
MUTATING = frozenset({"POST", "PUT", "PATCH", "DELETE"})
SESSION_HOURS = 8
# Where a sign-in (password, signup, "Continue without signing in") lands when
# there is no other safe page to return to. "/" stays the review queue.
LANDING_PATH = "/dashboard"
MAX_UPLOAD_BYTES = 20 * 1024 * 1024
CSRF_HEADER = "X-CSRF-Token"
GENERIC_LOGIN_ERROR = "Invalid username or password."
THROTTLED_ERROR = "Too many failed attempts. Please wait a few minutes and try again."
DEMO_THROTTLED_ERROR = "Too many demos started from here. Please wait a few minutes and try again."
DEMO_FULL_ERROR = "The demo is busy right now. Please try again later."
MAX_DEMO_STARTS = 10      # per IP per throttle window; every start counts
MAX_DEMO_USERS = 100      # live demo users at once, bounds disk use


# ---- secret key ------------------------------------------------------------

_key_cache: dict[str, str] = {}


def secret_key() -> str:
    """VAULT_SECRET_KEY, else a random key generated once into
    <data>/.secret_key (mode 0600). There is no built-in default."""
    env = os.environ.get("VAULT_SECRET_KEY")
    if env:
        return env
    path = userdata.data_dir() / ".secret_key"
    cached = _key_cache.get(str(path))
    if cached:
        return cached
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w") as f:
            f.write(secrets.token_hex(32))
    except FileExistsError:
        pass
    with contextlib.suppress(OSError):
        if os.stat(path).st_mode & 0o077:
            os.chmod(path, 0o600)
    key = path.read_text().strip()
    if len(key) < 32:
        raise RuntimeError(f"{path} is empty or too short; delete it to generate a new key")
    _key_cache[str(path)] = key
    return key


class _SessionInterface(SecureCookieSessionInterface):
    """Looks the signing key and the Secure flag up per request, so nothing
    touches the data dir at import time and tests can point at a tmp dir."""

    def get_signing_serializer(self, app):
        app.secret_key = secret_key()
        return super().get_signing_serializer(app)

    def get_cookie_secure(self, app):
        return os.environ.get("VAULT_COOKIE_SECURE") == "1"


# ---- login throttle --------------------------------------------------------

class Throttle:
    """Sliding window of failures per key, in memory (resets on restart)."""

    def __init__(self, window: float = 15 * 60):
        self.window = window
        self._hits: dict[tuple, collections.deque] = {}
        self._lock = threading.Lock()

    def _prune(self, key, now):
        q = self._hits.get(key)
        while q and now - q[0] > self.window:
            q.popleft()
        if q is not None and not q:
            del self._hits[key]
        return self._hits.get(key)

    def blocked(self, key: tuple, limit: int) -> bool:
        with self._lock:
            q = self._prune(key, time.monotonic())
            return bool(q) and len(q) >= limit

    def fail(self, key: tuple) -> None:
        with self._lock:
            now = time.monotonic()
            if len(self._hits) > 20000:  # bound memory under a username spray
                for k in list(self._hits):
                    self._prune(k, now)
                if len(self._hits) > 20000:
                    self._hits.clear()
            self._hits.setdefault(key, collections.deque()).append(now)

    def reset(self, key: tuple) -> None:
        with self._lock:
            self._hits.pop(key, None)

    def clear(self) -> None:
        with self._lock:
            self._hits.clear()


throttle = Throttle()
MAX_FAILURES = 5          # per (ip, username)
MAX_FAILURES_PER_IP = 30  # across usernames, so one IP can't spray usernames forever


def _client_ip() -> str:
    return request.remote_addr or "?"


# ---- helpers ---------------------------------------------------------------

def safe_next(target: str | None) -> str:
    """Only same-site relative paths; anything else becomes LANDING_PATH."""
    if not target or not isinstance(target, str) or len(target) > 512:
        return LANDING_PATH
    if not target.startswith("/") or target.startswith("//") or "\\" in target:
        return LANDING_PATH
    if any(ord(c) < 32 or ord(c) == 127 for c in target):
        return LANDING_PATH
    parts = urlsplit(target)
    if parts.scheme or parts.netloc:
        return LANDING_PATH
    if parts.path.rstrip("/") in ("/login", "/logout", "/signup"):
        return LANDING_PATH
    return target


def csrf_token() -> str:
    token = session.get("csrf")
    if not token:
        token = session["csrf"] = secrets.token_urlsafe(32)
        session.permanent = True
    return token


def _csrf_ok() -> bool:
    expected = session.get("csrf")
    supplied = request.headers.get(CSRF_HEADER) or request.form.get("csrf_token") or ""
    return bool(expected) and hmac.compare_digest(str(expected), str(supplied))


def _wants_json() -> bool:
    return (
        request.path.startswith(("/api/", "/samples/"))
        or request.method not in ("GET", "HEAD")
    )


def _session_user() -> dict | None:
    uid = session.get("uid")
    if not uid:
        return None
    try:
        user = auth.get_user(uid)
    except (OSError, ValueError, KeyError):
        user = None
    if user is not None and auth.is_demo(user) and not demo_enabled():
        user = None  # switching demo mode off ends every demo session
    if user is None or not hmac.compare_digest(session.get("ph", ""), auth.password_stamp(user)):
        session.pop("uid", None)
        session.pop("ph", None)
        return None
    return user


def _start_session(user: dict) -> None:
    session.clear()
    session.permanent = True
    session["uid"] = user["id"]
    session["ph"] = auth.password_stamp(user)
    session["csrf"] = secrets.token_urlsafe(32)


def signup_enabled() -> bool:
    return os.environ.get("VAULT_ALLOW_SIGNUP") == "1"


def demo_enabled() -> bool:
    return os.environ.get("VAULT_DEMO") == "1"


def skip_login_enabled() -> bool:
    """A "Continue without signing in" button on the sign-in page, for one
    person on their own machine. Off unless VAULT_SKIP_LOGIN=1 (the desktop app
    sets it), and never offered to a request that did not come from this
    machine, so serving the app to other people cannot expose it."""
    if os.environ.get("VAULT_SKIP_LOGIN") != "1":
        return False
    try:
        return ipaddress.ip_address(request.remote_addr or "").is_loopback
    except ValueError:
        return False


def start_skip_login_session() -> dict:
    """Sign this browser in as the local account, creating it on first use
    with a random password nobody needs to know."""
    user = auth.find_by_username(SKIP_LOGIN_USERNAME)
    if user is None:
        user = auth.create_user(SKIP_LOGIN_USERNAME, secrets.token_urlsafe(32))
    _start_session(user)
    return user


def start_demo_session() -> tuple[dict | None, str | None]:
    """Create a throwaway demo user and sign this browser in as it. Returns
    (user, None), or (None, error) when throttled or full. The caller seeds
    the new user's directory. Expired demo users are purged first."""
    key = (_client_ip(), "*demo")
    if throttle.blocked(key, MAX_DEMO_STARTS):
        return None, DEMO_THROTTLED_ERROR
    throttle.fail(key)  # every start counts
    auth.purge_expired_demo_users()
    if len(auth.demo_users()) >= MAX_DEMO_USERS:
        return None, DEMO_FULL_ERROR
    if auth.is_demo(getattr(g, "user", None)):
        auth.delete_demo_user(g.user["id"])  # starting over: don't orphan the old one
    user = auth.create_demo_user()
    _start_session(user)
    return user, None


def end_demo_session(user: dict) -> None:
    """Delete a demo user and its directory and clear the session.
    auth.delete_demo_user refuses anything not flagged demo."""
    auth.delete_demo_user(user["id"])
    session.clear()


# ---- wiring ----------------------------------------------------------------

def init_app(app: Flask) -> None:
    app.session_interface = _SessionInterface()
    app.config.update(
        MAX_CONTENT_LENGTH=MAX_UPLOAD_BYTES,
        PERMANENT_SESSION_LIFETIME=timedelta(hours=SESSION_HOURS),
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_REFRESH_EACH_REQUEST=False,  # absolute 8h lifetime, not sliding
    )
    if os.environ.get("VAULT_TRUST_PROXY") == "1":
        from werkzeug.middleware.proxy_fix import ProxyFix

        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

    @app.before_request
    def _gate():
        g.user = None
        g._dir_token = None
        endpoint = request.endpoint
        if endpoint is None:  # 404 / 405: nothing to protect, nothing served
            return None
        user = _session_user()
        if endpoint not in PUBLIC_ENDPOINTS and user is None:
            if _wants_json():
                return jsonify({"error": "authentication required"}), 401
            # Opening the app's root (the desktop window, a bookmark) means
            # "open the app", so it lands on the dashboard after sign-in.
            target = request.full_path.rstrip("?")
            return redirect(url_for("login", next=LANDING_PATH if target == "/" else safe_next(target)))
        if user is not None:
            g.user = user
            g._dir_token = userdata.current_user_dir.set(userdata.user_dir_for(user["id"], create=True))
        if request.method in MUTATING and not _csrf_ok():
            if endpoint == "logout" and user is None:
                return None  # stale page, nothing to protect: the view just clears
            return jsonify({"error": "missing or invalid CSRF token; reload the page and try again"}), 403
        # Demo routes, checked after CSRF like everything else: none of them
        # exist while the switch is off, and reset/exit only for a demo user.
        if endpoint in DEMO_ENDPOINTS and not demo_enabled():
            return jsonify({"error": "not found"}), 404
        if endpoint in DEMO_ENDPOINTS - {"demo_start"} and not auth.is_demo(user):
            return jsonify({"error": "not found"}), 404
        return None

    @app.teardown_request
    def _release(_exc):
        token = getattr(g, "_dir_token", None)
        if token is not None:
            with contextlib.suppress(ValueError):
                userdata.current_user_dir.reset(token)

    @app.after_request
    def _headers(resp):
        resp.headers["X-Content-Type-Options"] = "nosniff"
        resp.headers["X-Frame-Options"] = "DENY"
        resp.headers["Referrer-Policy"] = "same-origin"
        resp.headers["Content-Security-Policy"] = "frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
        if not request.path.startswith("/static/"):
            resp.headers["Cache-Control"] = "no-store"
        return resp

    @app.errorhandler(HTTPException)
    def _http_error(exc):
        if _wants_json():
            message = "that upload is too large (limit 20 MB)" if exc.code == 413 else exc.description
            return jsonify({"error": message}), exc.code
        return exc

    @app.context_processor
    def _inject():
        user = getattr(g, "user", None)
        return {
            "current_user": user,
            "csrf_token": csrf_token,
            "signup_enabled": signup_enabled(),
            "demo_enabled": demo_enabled(),
            "skip_login_enabled": skip_login_enabled(),
            "is_demo": auth.is_demo(user),
        }

    @app.route("/healthz")
    def healthz():
        return jsonify({"status": "ok"})

    @app.route("/login", methods=["GET", "POST"])
    def login():
        next_url = safe_next(request.values.get("next"))
        if request.method == "GET":
            if g.user is not None:
                return redirect(next_url)
            return render_template("login.html", next_url=next_url, error=None, username="")

        username = (request.form.get("username") or "")[:64].strip().lower()
        password = request.form.get("password") or ""
        ip = _client_ip()
        key, ip_key = (ip, username), (ip, "*")
        if throttle.blocked(key, MAX_FAILURES) or throttle.blocked(ip_key, MAX_FAILURES_PER_IP):
            return render_template("login.html", next_url=next_url, error=THROTTLED_ERROR, username=username), 429
        user = auth.authenticate(username, password)
        if user is None:
            throttle.fail(key)
            throttle.fail(ip_key)
            return render_template("login.html", next_url=next_url, error=GENERIC_LOGIN_ERROR, username=username), 401
        throttle.reset(key)
        _start_session(user)
        return redirect(next_url)

    @app.route("/login/skip", methods=["POST"])
    def skip_login():
        if not skip_login_enabled():
            return jsonify({"error": "not found"}), 404
        start_skip_login_session()
        return redirect(safe_next(request.form.get("next")))

    @app.route("/logout", methods=["POST"])
    def logout():
        if auth.is_demo(g.user):  # a demo user can't sign back in: don't leave it behind
            auth.delete_demo_user(g.user["id"])
        session.clear()
        return redirect(url_for("login"))

    @app.route("/signup", methods=["GET", "POST"])
    def signup():
        if not signup_enabled():
            return jsonify({"error": "not found"}), 404
        if request.method == "GET":
            return render_template("signup.html", error=None, username="")
        username = (request.form.get("username") or "")[:64]
        key = (_client_ip(), "*signup")
        if throttle.blocked(key, 10):
            return render_template("signup.html", error=THROTTLED_ERROR, username=username), 429
        throttle.fail(key)  # every attempt counts
        password = request.form.get("password") or ""
        try:
            if password != (request.form.get("password2") or ""):
                raise auth.AuthError("passwords did not match")
            user = auth.create_user(username, password)
        except auth.AuthError as exc:
            return render_template("signup.html", error=str(exc), username=username), 400
        _start_session(user)
        return redirect(LANDING_PATH)
