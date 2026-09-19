import pytest

from vault_ledger import coa


@pytest.fixture(autouse=True)
def isolated_accounts_file(tmp_path, monkeypatch):
    """Never let a developer's real data/accounts.json leak into tests."""
    monkeypatch.setattr(coa, "ACCOUNTS_PATH", tmp_path / "accounts.json")
