from vault_ledger.duplicates import describe, find_duplicates, find_match, match_key


def _item(item_id, vendor="Acme Office Supplies Inc", amount="100.0", date="2026-03-14", filename=None):
    return {"id": item_id, "vendor": vendor, "amount": amount, "date": date, "filename": filename or f"{item_id}.png"}


def test_key_ignores_case_and_spacing_and_rounds_to_the_cent():
    assert match_key("  ACME   office Supplies inc ", "100", "2026-03-14") == match_key(
        "Acme Office Supplies Inc", 100.001, " 2026-03-14 "
    )


def test_key_is_none_without_vendor_date_or_readable_amount():
    assert match_key("", 100, "2026-03-14") is None
    assert match_key("Acme", 100, "") is None
    assert match_key("Acme", "not-a-number", "2026-03-14") is None
    assert match_key("Acme", float("nan"), "2026-03-14") is None


def test_different_amount_date_or_vendor_is_not_a_match():
    item = _item("a")
    assert find_match(item, [_item("b", amount="100.01")], []) is None
    assert find_match(item, [_item("b", date="2026-03-15")], []) is None
    assert find_match(item, [_item("b", vendor="Acme Office")], []) is None


def test_the_same_day_in_another_notation_matches():
    # 03/14/2026 has only one reading (no 14th month), so it is 2026-03-14.
    assert find_match(_item("a"), [_item("b", date="03/14/2026")], [])["id"] == "b"


def test_a_different_day_does_not_match():
    assert find_match(_item("a"), [_item("b", date="2026-03-15")], []) is None


def test_ledger_match_wins_over_queue_match():
    ledger = [{"vendor": "acme office supplies inc", "amount": "100.0", "date": "2026-03-14", "filename": "posted.pdf"}]
    match = find_match(_item("a"), [_item("b")], ledger)
    assert match == {"source": "ledger", "id": "", "filename": "posted.pdf"}
    assert "already in the ledger" in describe(match) and "posted.pdf" in describe(match)


def test_item_never_matches_itself():
    item = _item("a")
    assert find_match(item, [item], []) is None


def test_two_pending_copies_point_at_each_other():
    found = find_duplicates([_item("a"), _item("b"), _item("c", amount="5")], [])
    assert set(found) == {"a", "b"}
    assert found["a"] == {"source": "queue", "id": "b", "filename": "b.png"}
    assert found["b"]["id"] == "a"
    assert "also in the review queue" in describe(found["a"])
