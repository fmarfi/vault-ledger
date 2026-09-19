from vault_ledger.ledger import append_entry, entries_by_account, read_entries


def test_append_and_read_entry(tmp_path):
    path = tmp_path / "ledger.csv"
    append_entry(
        filename="invoice_office_supplies.png",
        vendor="Acme Office Supplies Inc",
        description="Printer paper and toner cartridges",
        date="03/14/2026",
        amount=184.32,
        account="Office Supplies Expense",
        confidence=0.91,
        was_corrected=False,
        path=path,
    )

    entries = read_entries(path)
    assert len(entries) == 1
    assert entries[0]["vendor"] == "Acme Office Supplies Inc"
    assert entries[0]["account"] == "Office Supplies Expense"
    assert entries[0]["was_corrected"] == "False"


def test_read_entries_empty_when_no_file(tmp_path):
    assert read_entries(tmp_path / "does_not_exist.csv") == []


def test_entries_by_account_groups_correctly(tmp_path):
    path = tmp_path / "ledger.csv"
    append_entry("a.png", "Vendor A", "desc", "03/01/2026", 10.0, "Office Supplies Expense", 0.9, False, path=path)
    append_entry("b.png", "Vendor B", "desc", "03/02/2026", 20.0, "Utilities Expense", 0.8, False, path=path)
    append_entry("c.png", "Vendor C", "desc", "03/03/2026", 30.0, "Office Supplies Expense", 0.7, True, path=path)

    grouped = entries_by_account(path)

    assert set(grouped.keys()) == {"Office Supplies Expense", "Utilities Expense"}
    assert len(grouped["Office Supplies Expense"]) == 2
    assert len(grouped["Utilities Expense"]) == 1
