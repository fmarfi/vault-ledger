"""WSGI entry point: `gunicorn -w 1 --threads 8 vault_ledger.webapp.wsgi:app`
or `waitress-serve --threads=8 vault_ledger.webapp.wsgi:app`.

Run exactly ONE process: the login throttle and the per-user locks are
in-process, so several workers would each keep their own and stop protecting
anything. Threads are fine.
"""

from vault_ledger.webapp.app import app

__all__ = ["app"]
