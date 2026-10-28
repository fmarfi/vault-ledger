"""Export adapters (spec 7.6). When a real customer export arrives, only an
adapter needs writing; everything downstream consumes Transaction/Label."""
from __future__ import annotations

import json
from pathlib import Path

from ..schemas import CompanyConfig, Label, Transaction


class ExportAdapter:
    def load(self, path: str | Path) -> tuple[list[Transaction], list[Label], list[CompanyConfig]]:
        raise NotImplementedError


class SyntheticAdapter(ExportAdapter):
    """Reads what synth.generator.write_dataset wrote. Never opens `_truth/`."""

    def load(self, path):
        path = Path(path)
        with open(path / "transactions.jsonl", encoding="utf-8") as f:
            txns = [Transaction.from_dict(json.loads(line)) for line in f if line.strip()]
        with open(path / "labels.jsonl", encoding="utf-8") as f:
            labels = [Label.from_dict(json.loads(line)) for line in f if line.strip()]
        companies = [CompanyConfig(**c) for c in json.loads((path / "companies.json").read_text(encoding="utf-8"))]
        return txns, labels, companies


# App account name -> (macro, micro) in taxonomy/app_accounts.yaml
APP_ACCOUNT_MAP = {
    "Software & Subscriptions Expense": ("OFFICE_IT", "software_subscriptions"),
    "Office Supplies Expense": ("OFFICE_IT", "office_supplies"),
    "Travel & Transport Expense": ("TRANSPORT", "travel_transport"),
    "Rent Expense": ("HOUSING", "rent"),
    "Utilities Expense": ("HOUSING", "utilities"),
    "Professional Services Expense": ("PROFESSIONAL", "professional_services"),
    "General/Other Expense": ("OTHER", "general_other"),
}


class SynthCrewAdapter:
    """Reads the synthetic data crew's draw (branch `synth-data`,
    data/synthetic/generated/): transactions_<seed>.csv + the `split` column of
    metadata_<seed>.csv. Only `split` and `vat_rate` (printed on the document) are read from metadata; its truth columns
    (true_account, hard_case, ...) are never opened here.

    Rows are invoices/receipts the company paid, so direction is always OUT.
    Returns (transactions, labels, {txn_id: "train"|"val"|"test"}).
    """

    def load(self, transactions_csv, metadata_csv, company_id: str = "synth-crew"):
        import csv
        from datetime import date

        with open(transactions_csv, encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        with open(metadata_csv, encoding="utf-8") as f:
            meta = list(csv.DictReader(f))
        if len(rows) != len(meta):
            raise ValueError("transactions and metadata row counts differ")
        txns, labels, split = [], [], {}
        for r, m in zip(rows, meta):
            tid = m["id"]
            macro, micro = APP_ACCOUNT_MAP[r["account"]]
            txns.append(Transaction(
                txn_id=tid, company_id=company_id, date=date.fromisoformat(r["date"]),
                amount=r["amount"], direction="OUT",
                counterparty_name=r["vendor"], description=r["description"],
                vat_rate=None if m.get("vat_rate") in ("", "rc", None) else m["vat_rate"],
                vat_reverse_charge=m.get("vat_rate") == "rc", paid=r.get("paid") == "True",
            ))
            labels.append(Label(tid, r["account"], macro, micro, "SYNTHETIC", "OK"))
            split[tid] = m["split"]
        return txns, labels, split


class QuickBooksCsvAdapter(ExportAdapter):
    def load(self, path):
        raise NotImplementedError("TODO: write when a real QuickBooks export is available")


class XeroCsvAdapter(ExportAdapter):
    def load(self, path):
        raise NotImplementedError("TODO: write when a real Xero export is available")
