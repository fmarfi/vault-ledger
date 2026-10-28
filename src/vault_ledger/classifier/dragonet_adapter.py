"""A trained DragoNet run (package `vaultledger-ml`) as an app classifier.

Used by the classifier cascade (classifier/cascade.py), which is on by
default. To put one run first:

    VAULT_CLASSIFIER=dragonet:<path to a DragoNet run folder>

The run must be trained on the app-accounts taxonomy
(`vaultledger/taxonomy/app_accounts.yaml`), so its categories map back to the
app's accounts. Same interface as FastClassifier: predict() returns
(account, confidence); the confidence gate and the debit/credit rules are
unchanged.
"""

from __future__ import annotations

import os
from datetime import date as _date
from pathlib import Path

ENV = "VAULT_CLASSIFIER"


def requested_run_dir() -> Path | None:
    value = os.environ.get(ENV, "")
    if not value.startswith("dragonet:"):
        return None
    return Path(value.split(":", 1)[1])


class DragoNetClassifier:
    def __init__(self, run_dir: Path):
        import vaultledger
        from vaultledger.io.adapters import APP_ACCOUNT_MAP
        from vaultledger.model.infer import Predictor

        # The checkpoint stores the absolute taxonomy path it was trained
        # with; load the installed package's copy so a run keeps working
        # after the folder it was trained in moves or is deleted.
        taxonomy = Path(vaultledger.__file__).parent / "taxonomy" / "app_accounts.yaml"
        self._predictor = Predictor.load(run_dir, taxonomy_path=taxonomy)
        self._account_of = {micro: account for account, (_, micro) in APP_ACCOUNT_MAP.items()}
        missing = set(self._predictor.tax.micro_names) - set(self._account_of)
        if missing:
            raise ValueError(f"DragoNet run {run_dir} predicts categories with no app account: {sorted(missing)}")
        self.run_dir = run_dir

    def predict(self, vendor: str, description: str) -> tuple[str, float]:
        return self.predict_document(vendor, description, None, None, None)

    def predict_document(self, vendor: str, description: str, amount, paid, date) -> tuple[str, float]:
        from vaultledger.schemas import Transaction

        try:
            when = _date.fromisoformat(date) if date else _date.today()
        except ValueError:
            when = _date.today()
        txn = Transaction(
            txn_id="doc", company_id="app", date=when,
            amount=abs(float(amount or 0)), direction="OUT",
            counterparty_name=vendor or "", description=description or "",
            paid=paid if isinstance(paid, bool) else None,
        )
        s = self._predictor.predict([txn])[0]
        return self._account_of[s.ref_micro], float(s.confidence)
