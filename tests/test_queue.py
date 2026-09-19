from vault_ledger.queue import enqueue, get_pending, read_pending, remove_pending


def _enqueue(path, **overrides):
    fields = dict(
        filename="invoice_office_supplies.png",
        vendor="Acme Office Supplies Inc",
        description="Printer paper and toner cartridges",
        date="03/14/2026",
        amount=184.32,
        paid=True,
        predicted_account="Office Supplies Expense",
        confidence=0.91,
        needs_review=False,
        rejection_reason=None,
        entry_json='{"lines": [], "total_debits": 184.32, "total_credits": 184.32}',
    )
    fields.update(overrides)
    return enqueue(path=path, **fields)


def test_enqueue_and_read_pending(tmp_path):
    path = tmp_path / "pending_queue.csv"
    item_id = _enqueue(path)

    items = read_pending(path)
    assert len(items) == 1
    assert items[0]["id"] == item_id
    assert items[0]["vendor"] == "Acme Office Supplies Inc"
    assert items[0]["paid"] == "True"
    assert items[0]["needs_review"] == "False"


def test_read_pending_empty_when_no_file(tmp_path):
    assert read_pending(tmp_path / "does_not_exist.csv") == []


def test_get_pending_finds_by_id(tmp_path):
    path = tmp_path / "pending_queue.csv"
    id_a = _enqueue(path, filename="a.png", vendor="Vendor A")
    id_b = _enqueue(path, filename="b.png", vendor="Vendor B")

    assert get_pending(id_a, path)["vendor"] == "Vendor A"
    assert get_pending(id_b, path)["vendor"] == "Vendor B"
    assert get_pending("not-a-real-id", path) is None


def test_remove_pending_deletes_only_that_item(tmp_path):
    path = tmp_path / "pending_queue.csv"
    id_a = _enqueue(path, filename="a.png")
    id_b = _enqueue(path, filename="b.png")

    assert remove_pending(id_a, path) is True

    remaining = read_pending(path)
    assert len(remaining) == 1
    assert remaining[0]["id"] == id_b


def test_remove_pending_returns_false_for_unknown_id(tmp_path):
    path = tmp_path / "pending_queue.csv"
    _enqueue(path)

    assert remove_pending("not-a-real-id", path) is False
    assert len(read_pending(path)) == 1
