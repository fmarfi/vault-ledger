"""Per-user data directory resolution.

Storage modules (queue, ledger, corrections, coa, backup) never hard-code
where their files live any more. They ask `resolve(name, legacy_path)`:

- No user directory set (CLI, classifier scripts, tests): the legacy path is
  returned unchanged, so everything that worked before still works.
- A user directory set (a web request by an authenticated user): the file is
  `<data>/users/<user_id>/<name>`. `name` must be one of a fixed allow-list
  and the result is checked to be inside that one user's directory, so a
  storage call made while user A is authenticated cannot touch user B's files.

Filesystem paths are built from the random user id only, never from a
username or any other user-controlled string.
"""

from __future__ import annotations

import contextlib
import contextvars
import os
import re
import threading
from pathlib import Path

_DEFAULT_DATA_DIR = Path(__file__).resolve().parents[2] / "data"
USER_ID_RE = re.compile(r"[0-9a-f]{32}")
ALLOWED_NAMES = frozenset(
    {"ledger.csv", "pending_queue.csv", "corrections.csv", "accounts.json", "training.csv", "backups", "documents",
     "preferences.json"}
)

current_user_dir: contextvars.ContextVar[Path | None] = contextvars.ContextVar(
    "vault_ledger_current_user_dir", default=None
)


class UserDataError(RuntimeError):
    """A path escaped the current user's directory, or an id/name was invalid."""


def data_dir() -> Path:
    """Root for users.json, .secret_key and users/. VAULT_DATA_DIR overrides
    it (read at call time). Legacy single-user files keep their old locations."""
    override = os.environ.get("VAULT_DATA_DIR")
    return Path(override).expanduser() if override else _DEFAULT_DATA_DIR


def users_root() -> Path:
    return data_dir() / "users"


def user_dir_for(user_id: str, create: bool = False) -> Path:
    """The directory for a user id. The id must be a 32-char lowercase hex
    string (a uuid4 hex), which cannot contain separators or dots."""
    if not isinstance(user_id, str) or not USER_ID_RE.fullmatch(user_id):
        raise UserDataError("invalid user id")
    path = users_root() / user_id
    if create:
        path.mkdir(parents=True, exist_ok=True)
        with contextlib.suppress(OSError):
            os.chmod(path, 0o700)
    return path


@contextlib.contextmanager
def use_user_dir(path: str | Path | None):
    token = current_user_dir.set(Path(path) if path is not None else None)
    try:
        yield
    finally:
        current_user_dir.reset(token)


def current_user_id() -> str | None:
    base = current_user_dir.get()
    return base.name if base is not None else None


def _inside(path: Path, base: Path) -> bool:
    try:
        Path(os.path.realpath(path)).relative_to(os.path.realpath(base))
    except ValueError:
        return False
    return True


def resolve(name: str, legacy_path: str | Path, explicit: str | Path | None = None) -> Path:
    """Where to read/write `name` right now.

    `explicit` is a caller-supplied path (a `path=` argument). Outside a user
    context it wins, as before. Inside one it is only accepted if it is
    already within the current user's directory.
    """
    base = current_user_dir.get()
    if base is None:
        return Path(explicit) if explicit is not None else Path(legacy_path)
    if not USER_ID_RE.fullmatch(base.name):
        raise UserDataError("current user directory is not a per-user directory")
    if explicit is not None:
        if not _inside(Path(explicit), base):
            raise UserDataError("path is outside the current user's data directory")
        return Path(explicit)
    if name not in ALLOWED_NAMES:
        raise UserDataError(f"unknown per-user file {name!r}")
    path = base / name
    if not _inside(path, base):
        raise UserDataError("resolved path escapes the current user's data directory")
    return path


# One lock per user id (and one for "no user"), created under a guard lock.
_locks: dict[str, threading.RLock] = {}
_locks_guard = threading.Lock()


def lock_for(user_id: str | None) -> threading.RLock:
    key = user_id or ""
    with _locks_guard:
        lock = _locks.get(key)
        if lock is None:
            lock = _locks[key] = threading.RLock()
        return lock
