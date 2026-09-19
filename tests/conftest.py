import pytest

from vault_ledger import coa


@pytest.fixture(autouse=True)
def isolated_accounts_file(tmp_path, monkeypatch):
    """Never let a developer's real data/accounts.json leak into tests."""
    monkeypatch.setattr(coa, "ACCOUNTS_PATH", tmp_path / "accounts.json")


@pytest.fixture(autouse=True)
def isolated_data_dir(tmp_path, monkeypatch):
    """users.json, the secret key and per-user dirs all live under tmp_path."""
    monkeypatch.setenv("VAULT_DATA_DIR", str(tmp_path / "vault-data"))
    for var in ("VAULT_SECRET_KEY", "VAULT_COOKIE_SECURE", "VAULT_ALLOW_SIGNUP", "VAULT_TRUST_PROXY"):
        monkeypatch.delenv(var, raising=False)
    from vault_ledger.webapp import security

    security.throttle.clear()
    security._key_cache.clear()
