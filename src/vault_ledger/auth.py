"""User accounts: the users.json store and the admin CLI.

    python -m vault_ledger.auth add-user <username>
    python -m vault_ledger.auth list-users
    python -m vault_ledger.auth set-password <username>
    python -m vault_ledger.auth delete-user <username>
    python -m vault_ledger.auth migrate-legacy <username>

There is no open registration (see VAULT_ALLOW_SIGNUP in the README). A user
record holds a random id (the only thing ever used to build a filesystem
path), the lowercased unique username, and a salted scrypt password hash.
"""

from __future__ import annotations

import argparse
import contextlib
import getpass
import hashlib
import json
import os
import re
import shutil
import sys
import tempfile
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path

from werkzeug.security import check_password_hash, generate_password_hash

from vault_ledger import userdata

USERNAME_RE = re.compile(r"[a-z0-9_.-]{3,32}")
MIN_PASSWORD_LEN = 10
MAX_PASSWORD_LEN = 256

_store_lock = threading.RLock()
_cache: dict[str, tuple[tuple[int, int], list[dict]]] = {}


class AuthError(ValueError):
    """Invalid username/password or a user-management conflict."""


def users_file() -> Path:
    return userdata.data_dir() / "users.json"


def normalize_username(username: str) -> str:
    name = (username or "").strip().lower()
    if not USERNAME_RE.fullmatch(name) or not re.search(r"[a-z0-9]", name):
        raise AuthError("username must be 3-32 characters of a-z, 0-9, '_', '.' or '-'")
    return name


def validate_password(password: str, username: str) -> None:
    if not isinstance(password, str) or len(password) < MIN_PASSWORD_LEN:
        raise AuthError(f"password must be at least {MIN_PASSWORD_LEN} characters")
    if len(password) > MAX_PASSWORD_LEN:
        raise AuthError(f"password must be at most {MAX_PASSWORD_LEN} characters")
    if password.lower() == (username or "").strip().lower():
        raise AuthError("password must not be the same as the username")


# ---- store -----------------------------------------------------------------

def _read_users() -> list[dict]:
    path = users_file()
    try:
        st = path.stat()
    except FileNotFoundError:
        return []
    sig = (st.st_mtime_ns, st.st_size)
    hit = _cache.get(str(path))
    if hit and hit[0] == sig:
        return hit[1]
    with path.open(encoding="utf-8") as f:
        users = json.load(f)["users"]
    _cache[str(path)] = (sig, users)
    return users


def _write_users(users: list[dict]) -> None:
    """Atomic: temp file in the same dir, fsync, os.replace; mode 0600."""
    path = users_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".users-", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump({"users": users}, f, indent=2)
            f.flush()
            os.fsync(f.fileno())
        with contextlib.suppress(OSError):
            os.chmod(tmp, 0o600)
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise
    _cache.pop(str(path), None)


def list_users() -> list[dict]:
    with _store_lock:
        return [dict(u) for u in _read_users()]


def find_by_username(username: str) -> dict | None:
    name = (username or "").strip().lower()
    for user in _read_users():
        if user["username"] == name:
            return user
    return None


def get_user(user_id: str) -> dict | None:
    for user in _read_users():
        if user["id"] == user_id:
            return user
    return None


def create_user(username: str, password: str, is_admin: bool = False) -> dict:
    name = normalize_username(username)
    validate_password(password, name)
    with _store_lock:
        users = list(_read_users())
        if any(u["username"] == name for u in users):
            raise AuthError("that username is already taken")
        user = {
            "id": uuid.uuid4().hex,
            "username": name,
            "password_hash": generate_password_hash(password),
            "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "is_admin": bool(is_admin),
        }
        userdata.user_dir_for(user["id"], create=True)
        _write_users(users + [user])
    return user


def set_password(username: str, password: str) -> None:
    name = normalize_username(username)
    validate_password(password, name)
    with _store_lock:
        users = [dict(u) for u in _read_users()]
        for u in users:
            if u["username"] == name:
                u["password_hash"] = generate_password_hash(password)
                _write_users(users)
                return
    raise AuthError("no such user")


def delete_user(username: str) -> str:
    """Remove the user and only that user's data dir. Returns the user id."""
    name = normalize_username(username)
    with _store_lock:
        users = list(_read_users())
        victim = next((u for u in users if u["username"] == name), None)
        if victim is None:
            raise AuthError("no such user")
        _write_users([u for u in users if u["id"] != victim["id"]])
        target = userdata.user_dir_for(victim["id"])
        if target.is_dir() and not target.is_symlink():
            shutil.rmtree(target)
    return victim["id"]


# Dummy hash so an unknown username costs about as much as a wrong password.
_DUMMY_HASH = generate_password_hash("dummy-password-for-timing")


def authenticate(username: str, password: str) -> dict | None:
    user = find_by_username(username)
    if user is None:
        check_password_hash(_DUMMY_HASH, password or "")
        return None
    return user if check_password_hash(user["password_hash"], password or "") else None


def password_stamp(user: dict) -> str:
    """Short fingerprint of the current hash; sessions carry it so a password
    change (or user delete/recreate) invalidates old cookies."""
    return hashlib.sha256(user["password_hash"].encode()).hexdigest()[:16]


# ---- legacy migration ------------------------------------------------------

_REPO = Path(__file__).resolve().parents[2]


def legacy_sources(repo: Path = _REPO) -> dict[str, list[Path]]:
    """destination name -> candidate legacy locations (first existing wins)."""
    return {
        "ledger.csv": [repo / "data" / "ledger.csv", repo / "ledger.csv"],
        "pending_queue.csv": [repo / "data" / "pending_queue.csv", repo / "pending_queue.csv"],
        "corrections.csv": [repo / "corrections.csv", repo / "data" / "corrections.csv"],
        "accounts.json": [repo / "data" / "accounts.json"],
        "backups": [repo / "data" / "backups"],
    }


def _digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def migrate_legacy(username: str, repo: Path = _REPO) -> list[str]:
    """Copy the legacy single-user files into the user's directory, verify the
    copies byte for byte, then drop a `.migrated` marker in the legacy data
    dir. The originals are NEVER deleted or altered; remove them yourself
    once you have checked the result. Refuses to run twice."""
    user = find_by_username(normalize_username(username))
    if user is None:
        raise AuthError("no such user (create it first with add-user)")
    marker = repo / "data" / ".migrated"
    if marker.exists():
        raise AuthError(f"legacy data was already migrated ({marker}); refusing to do it twice")

    dest = userdata.user_dir_for(user["id"], create=True)
    plan = []
    for name, candidates in legacy_sources(repo).items():
        src = next((c for c in candidates if c.exists()), None)
        if src is None:
            continue
        if (dest / name).exists():
            raise AuthError(f"{dest / name} already exists; refusing to overwrite")
        plan.append((name, src))

    copied = []
    for name, src in plan:
        target = dest / name
        if src.is_dir():
            shutil.copytree(src, target, symlinks=False)
            for f in (p for p in src.rglob("*") if p.is_file()):
                if _digest(f) != _digest(target / f.relative_to(src)):
                    raise AuthError(f"verification failed for {f}; nothing was removed")
        else:
            shutil.copy2(src, target)
            if _digest(src) != _digest(target):
                raise AuthError(f"verification failed for {src}; nothing was removed")
        copied.append(f"{src} -> {target}")

    marker.write_text(
        json.dumps(
            {"migrated_to_user": user["username"], "user_id": user["id"], "files": copied,
             "at": datetime.now(timezone.utc).isoformat(timespec="seconds")},
            indent=2,
        )
    )
    return copied


# ---- CLI -------------------------------------------------------------------

def _ask_password(prompt_user: str) -> str:
    first = getpass.getpass(f"Password for {prompt_user}: ")
    if first != getpass.getpass("Repeat password: "):
        raise AuthError("passwords did not match")
    return first


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m vault_ledger.auth")
    sub = parser.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("add-user", help="create a user")
    p.add_argument("username")
    p.add_argument("--admin", action="store_true", help="mark as admin (informational for now)")
    sub.add_parser("list-users", help="list users")
    sub.add_parser("set-password", help="change a user's password").add_argument("username")
    p = sub.add_parser("delete-user", help="delete a user AND that user's data")
    p.add_argument("username")
    p.add_argument("--yes", action="store_true", help="skip the confirmation prompt")
    sub.add_parser("migrate-legacy", help="copy the pre-login single-user data into a user").add_argument("username")
    args = parser.parse_args(argv)

    try:
        if args.cmd == "add-user":
            name = normalize_username(args.username)
            user = create_user(name, _ask_password(name), is_admin=args.admin)
            print(f"created user {user['username']} (id {user['id']})")
        elif args.cmd == "list-users":
            for u in list_users():
                print(f"{u['username']:<32} {u['id']}  {u['created_at']}{'  admin' if u['is_admin'] else ''}")
        elif args.cmd == "set-password":
            name = normalize_username(args.username)
            set_password(name, _ask_password(name))
            print("password updated; existing sessions for this user are now invalid")
        elif args.cmd == "delete-user":
            name = normalize_username(args.username)
            if not args.yes:
                answer = input(f"This permanently deletes user '{name}' and all of their data. Type the username to confirm: ")
                if answer.strip().lower() != name:
                    print("aborted")
                    return 1
            delete_user(name)
            print(f"deleted {name}")
        elif args.cmd == "migrate-legacy":
            for line in migrate_legacy(args.username):
                print("copied", line)
            print("done. The original files were left in place and a data/.migrated marker was written;"
                  " delete the originals yourself after checking.")
    except AuthError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
