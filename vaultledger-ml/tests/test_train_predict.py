from datetime import date
from decimal import Decimal

import pytest

from vaultledger.model.encoders import resolve_path
from vaultledger.model.infer import Predictor
from vaultledger.model.train import load_config, train
from vaultledger.schemas import Transaction
from vaultledger.synth.generator import SynthConfig, generate

SMALL = SynthConfig(seed=3, n_companies=2, rows_per_company=(300, 400))


def _cfg(**sets):
    cfg = load_config(overrides=[f"{k}={v}" for k, v in sets.items()])
    return cfg


def test_scratch_train_and_predict(tmp_path):
    ds = generate(SMALL)
    cfg = _cfg(**{"encoder.kind": "scratch", "encoder.scratch.vocab_size": 500, "encoder.scratch.d": 32,
                  "encoder.scratch.ff": 64, "model.d": 32, "train.epochs": 2})
    m = train(cfg, ds.transactions, ds.labels, tmp_path / "run", log=lambda *_: None)
    assert m["validation"]["hierarchy_violations"] == 0
    assert m["banner"].startswith("Results on synthetic data")
    pred = Predictor.load(tmp_path / "run")
    t = Transaction("x1", "c", date(2025, 3, 1), Decimal("45.10"), "OUT", "CCV*SHELL 1234 DELFT", "tanken")
    s = pred.predict([t])[0]
    assert s.status == "REVIEW"  # never AUTO before calibration
    assert pred.tax.macro_of(s.ref_micro) == s.ref_macro


@pytest.mark.pretrained
@pytest.mark.skipif(not (resolve_path("models/encoders/multilingual-e5-small") / "config.json").exists(),
                    reason="pretrained encoder not fetched (scripts/fetch_encoder.py)")
def test_pretrained_train_and_predict(tmp_path):
    ds = generate(SMALL)
    cfg = _cfg(**{"train.epochs": 2})
    m = train(cfg, ds.transactions, ds.labels, tmp_path / "run", log=lambda *_: None)
    assert m["validation"]["hierarchy_violations"] == 0
    # Frozen backbone is not saved in the run: the checkpoint stays small.
    assert (tmp_path / "run" / "model.pt").stat().st_size < 10_000_000
    pred = Predictor.load(tmp_path / "run")
    assert pred.predict(ds.transactions[:5])

