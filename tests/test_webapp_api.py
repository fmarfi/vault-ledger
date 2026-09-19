"""Endpoint tests for the review queue / confirm / bulk-confirm / ledger API.

The app now requires a login and stores each user's files under
data/users/<id>/ (VAULT_DATA_DIR is a tmp dir here, see conftest), so the
fixture logs in a throwaway user and the tests read that user's real files
-- nothing touches the real data/ directory.
"""

import csv
import threading

import pytest

from vault_ledger import queue as queue_mod
from vault_ledger.userdata import use_user_dir
from vault_ledger.webapp import app as app_mod

from tests.helpers import PASSWORD, login, make_user_client, new_client


@pytest.fixture
def client(tmp_path):
    c = make_user_client(app_mod.app, "tester")
    c.pending_path = c.user_dir / "pending_queue.csv"
    c.ledger_path = c.user_dir / "ledger.csv"
    c.corrections_path = c.user_dir / "corrections.csv"
    return c


def _add(client, **overrides):
    fields = dict(
        filename="a.png",
        vendor="Acme Office Supplies Inc",
        description="Printer paper",
        date="03/14/2026",
        amount=100.0,
        paid=True,
        predicted_account="Office Supplies Expense",
        confidence=0.9,
        needs_review=False,
        rejection_reason=None,
        entry_json="{}",
    )
    fields.update(overrides)
    with use_user_dir(client.user_dir):
        return app_mod.enqueue(**fields)


def _rows(path):
    with open(path, newline="") as f:
        return list(csv.DictReader(f))


def test_confirm_posts_and_dequeues(client):
    item_id = _add(client)
    res = client.post("/api/confirm", json={"id": item_id})
    assert res.status_code == 200
    entry = res.get_json()["entry"]
    assert entry["total_debits"] == entry["total_credits"] == 100.0
    assert len(_rows(client.ledger_path)) == 1
    assert client.get("/api/queue").get_json() == []
    assert not client.corrections_path.exists()  # no training signal on plain confirm


def test_confirm_twice_second_is_404_and_posts_once(client):
    item_id = _add(client)
    assert client.post("/api/confirm", json={"id": item_id}).status_code == 200
    assert client.post("/api/confirm", json={"id": item_id}).status_code == 404
    assert len(_rows(client.ledger_path)) == 1


def test_concurrent_confirm_posts_once(client):
    item_id = _add(client)
    statuses = []

    def go():
        c = login(new_client(app_mod.app), "tester")
        if True:
            statuses.append(c.post("/api/confirm", json={"id": item_id}).status_code)

    threads = [threading.Thread(target=go) for _ in range(8)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert sorted(statuses) == [200] + [404] * 7
    assert len(_rows(client.ledger_path)) == 1


def test_correct_logs_correction_only_when_account_changed(client):
    same = _add(client)
    client.post("/api/correct", json={"id": same, "corrected_account": "Office Supplies Expense"})
    assert not client.corrections_path.exists()

    changed = _add(client, vendor="Other")
    res = client.post("/api/correct", json={"id": changed, "corrected_account": "Utilities Expense"})
    assert res.status_code == 200
    assert len(_rows(client.corrections_path)) == 1


def test_correct_rejects_unknown_account(client):
    item_id = _add(client)
    res = client.post("/api/correct", json={"id": item_id, "corrected_account": "Bogus"})
    assert res.status_code == 400
    assert len(client.get("/api/queue").get_json()) == 1


def test_bulk_confirm_refuses_flagged_items(client):
    ok = _add(client, vendor="Fine")
    flagged = _add(client, vendor="Ambiguous", needs_review=True, rejection_reason="vendor ambiguity")
    res = client.post("/api/queue/bulk_confirm", json={"ids": [ok, flagged]}).get_json()
    assert res["confirmed"] == [ok]
    assert [f["id"] for f in res["failed"]] == [flagged]
    assert len(_rows(client.ledger_path)) == 1
    assert [i["id"] for i in client.get("/api/queue").get_json()] == [flagged]


def test_bulk_confirm_unknown_and_duplicate_ids(client):
    ok = _add(client)
    res = client.post("/api/queue/bulk_confirm", json={"ids": [ok, ok, "nope"]}).get_json()
    assert res["confirmed"] == [ok]
    assert [f["id"] for f in res["failed"]] == ["nope"]
    assert len(_rows(client.ledger_path)) == 1


def test_bulk_confirm_requires_ids(client):
    assert client.post("/api/queue/bulk_confirm", json={"ids": []}).status_code == 400


def test_invalid_stored_amount_is_rejected_not_posted(client):
    item_id = _add(client, amount=float("nan"))
    res = client.post("/api/confirm", json={"id": item_id})
    assert res.status_code == 400
    assert not client.ledger_path.exists()
    assert len(client.get("/api/queue").get_json()) == 1


def test_dismiss(client):
    item_id = _add(client)
    assert client.delete(f"/api/queue/{item_id}").status_code == 200
    assert client.delete(f"/api/queue/{item_id}").status_code == 404


def test_ledger_skips_malformed_rows(client):
    client.ledger_path.write_text(
        "confirmed_at,filename,vendor,description,date,amount,account,confidence,was_corrected\n"
        "2026-01-01T00:00:00+00:00,a.png,V,D,,12.5,Office Supplies Expense,0.9,False\n"
        "2026-01-01T00:00:00+00:00,b.png,V,D,,not-a-number,Office Supplies Expense,0.9,False\n"
    )
    res = client.get("/api/ledger")
    assert res.status_code == 200
    assert res.get_json()["Office Supplies Expense"]["total"] == 12.5


def test_queue_round_trips_awkward_text(client):
    item_id = _add(client, description='line "quoted", with comma\nand newline')
    row = client.get("/api/queue").get_json()[0]
    assert row["id"] == item_id
    assert row["description"] == 'line "quoted", with comma\nand newline'


def test_remove_pending_is_atomic_on_write_failure(client, monkeypatch):
    item_id = _add(client)
    before = client.pending_path.read_text()

    def boom(*a, **k):
        raise OSError("disk full")

    monkeypatch.setattr(queue_mod.os, "replace", boom)
    with pytest.raises(OSError):
        queue_mod.remove_pending(item_id, path=client.pending_path)
    assert client.pending_path.read_text() == before
    assert not list(client.pending_path.parent.glob("*.tmp"))
