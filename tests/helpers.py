"""Shared helpers for the auth/isolation tests: a Flask test client that
carries the CSRF token on state-changing requests, and a logged-in client
factory."""

import re

from flask.testing import FlaskClient

from vault_ledger import auth, userdata

PASSWORD = "correct horse battery"
_MUTATING = {"POST", "PUT", "PATCH", "DELETE"}
_META = re.compile(r'<meta name="csrf-token" content="([^"]*)"')


class AuthClient(FlaskClient):
    """Adds X-CSRF-Token to mutating requests once `csrf` is set."""

    csrf = None

    def open(self, *args, **kwargs):
        if self.csrf and kwargs.get("method", "GET").upper() in _MUTATING:
            headers = dict(kwargs.get("headers") or {})
            headers.setdefault("X-CSRF-Token", self.csrf)
            kwargs["headers"] = headers
        return super().open(*args, **kwargs)

    def page_token(self, path="/login"):
        html = self.get(path).get_data(as_text=True)
        found = _META.search(html)
        return found.group(1) if found else None


def new_client(app):
    app.config["TESTING"] = True
    app.test_client_class = AuthClient
    return app.test_client()


def login(client, username, password=PASSWORD):
    token = client.page_token("/login")
    res = client.post("/login", data={"username": username, "password": password, "csrf_token": token})
    assert res.status_code == 302, res.status_code
    client.csrf = client.page_token("/settings")
    assert client.csrf
    return client


def make_user_client(app, username, password=PASSWORD):
    user = auth.create_user(username, password)
    client = login(new_client(app), username, password)
    client.user = user
    client.user_dir = userdata.user_dir_for(user["id"])
    return client
