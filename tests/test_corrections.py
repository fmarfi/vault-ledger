import csv

from vault_ledger.classifier.apply_corrections import apply_corrections
from vault_ledger.corrections import record_correction


def test_record_correction_writes_header_and_row(tmp_path):
    path = tmp_path / "corrections.csv"
    record_correction(
        vendor="Acme Office Supplies Inc",
        description="Printer paper and toner cartridges",
        predicted_account="Utilities Expense",
        corrected_account="Office Supplies Expense",
        amount=184.32,
        date="03/14/2026",
        path=path,
    )

    with path.open() as f:
        rows = list(csv.DictReader(f))

    assert len(rows) == 1
    assert rows[0]["corrected_account"] == "Office Supplies Expense"
    assert rows[0]["predicted_account"] == "Utilities Expense"


def test_record_correction_appends_without_duplicating_header(tmp_path):
    path = tmp_path / "corrections.csv"
    for i in range(3):
        record_correction(
            vendor=f"Vendor {i}",
            description="desc",
            predicted_account="Utilities Expense",
            corrected_account="Office Supplies Expense",
            amount=10.0,
            date=None,
            path=path,
        )

    with path.open() as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 3


def test_apply_corrections_folds_into_training_data_and_resets_log(tmp_path):
    corrections_path = tmp_path / "corrections.csv"
    training_path = tmp_path / "labeled_transactions.csv"
    training_path.write_text("vendor,description,account\nExisting Vendor,existing desc,Rent Expense\n")

    record_correction(
        vendor="New Vendor Ltd",
        description="a new kind of expense",
        predicted_account="Rent Expense",
        corrected_account="General/Other Expense",
        amount=42.0,
        date="01/01/2026",
        path=corrections_path,
    )

    count = apply_corrections(corrections_path=corrections_path, training_data_path=training_path)
    assert count == 1

    with training_path.open() as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 2
    assert rows[-1] == {
        "vendor": "New Vendor Ltd",
        "description": "a new kind of expense",
        "account": "General/Other Expense",
    }

    with corrections_path.open() as f:
        remaining = list(csv.DictReader(f))
    assert remaining == []


def test_apply_corrections_is_a_noop_on_empty_log(tmp_path):
    corrections_path = tmp_path / "corrections.csv"
    training_path = tmp_path / "labeled_transactions.csv"
    training_path.write_text("vendor,description,account\n")

    count = apply_corrections(corrections_path=corrections_path, training_data_path=training_path)
    assert count == 0
