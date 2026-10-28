"""Desktop app: the web app in its own window instead of a browser tab.

    python -m vault_ledger.desktop        (or the `vault-ledger` launcher)

Starts the same Flask app (`vault_ledger.webapp.app`) on a free loopback port
in this process and shows it in a native window (pywebview; WebView2 on
Windows). No business logic lives here. Closing the window stops the server.

One process, as `webapp/wsgi.py` requires: the login throttle and the per-user
locks are in-process. The server never binds anything but 127.0.0.1.

The sign-in page gets two things the served web app keeps off by default,
unless the variable was set by hand:
- "Continue without signing in" (VAULT_SKIP_LOGIN), which opens the local
  account. `webapp/security.py` only offers it to this machine.
- On a first run, with no account yet, "Create an account" (VAULT_ALLOW_SIGNUP).
"""

from __future__ import annotations

import os
import threading

from werkzeug.serving import BaseWSGIServer, make_server

from vault_ledger import auth

HOST = "127.0.0.1"
TITLE = "Vault Ledger"


def start_server() -> tuple[BaseWSGIServer, str]:
    """Serve the web app on a free loopback port from a background thread.
    Returns the server (call .shutdown() to stop it) and its base URL."""
    from vault_ledger.webapp.app import app

    server = make_server(HOST, 0, app, threaded=True)
    threading.Thread(target=server.serve_forever, name="vault-ledger-server", daemon=True).start()
    # Load the classifier now, while the window opens, so the first document
    # doesn't wait for it (DragoNet takes ~10 s to load).
    from vault_ledger.webapp.app import _get_classifier

    threading.Thread(target=_get_classifier, name="vault-ledger-preload", daemon=True).start()
    return server, f"http://{HOST}:{server.server_port}"


def prepare_environment() -> None:
    """Switch on the desktop-only sign-in options (see the module docstring)."""
    os.environ.setdefault("VAULT_SKIP_LOGIN", "1")
    # Demo users can't sign in, so they don't count as an account.
    if not any(not auth.is_demo(user) for user in auth.list_users()):
        os.environ.setdefault("VAULT_ALLOW_SIGNUP", "1")


def main() -> None:
    try:
        import webview
    except ImportError:
        raise SystemExit('the desktop app needs pywebview: pip install -e ".[desktop]"') from None

    prepare_environment()
    server, base_url = start_server()
    # Backup and the CSV exports are file downloads; pywebview blocks them by default.
    webview.settings["ALLOW_DOWNLOADS"] = True
    webview.create_window(TITLE, base_url, width=1280, height=860, min_size=(960, 640))
    try:
        webview.start()  # blocks until the window is closed
    finally:
        server.shutdown()


if __name__ == "__main__":
    main()
