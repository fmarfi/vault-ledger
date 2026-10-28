"""One classifier made of several models, tried in order.

The most engineered model goes first. When it is not confident enough (below
the confidence gate), or it cannot load or run, the next one is asked, and so
on. The first answer at or above the gate wins. If no model reaches the gate,
the most confident answer is returned and the confidence gate sends it to
manual review as usual.

Default order (see DEFAULT_RUNS):
  1. DragoNet, pretrained encoder with its top 2 layers fine-tuned
  2. DragoNet, frozen encoder plus VAT/paid features
  3. TF-IDF fusion model (FastClassifier): no torch needed, always last

A model that fails to load is skipped for the rest of the process and the
cascade keeps working with the others, so a machine without torch or without
the DragoNet runs still gets the TF-IDF model.
"""

from __future__ import annotations

import logging
import os
import threading
from pathlib import Path
from typing import Callable

from vault_ledger.confidence_gate import CONFIDENCE_THRESHOLD

log = logging.getLogger(__name__)

RUNS_DIR = Path(__file__).resolve().parents[3] / "vaultledger-ml" / "runs"

# Most engineered first. Both are trained on the app-accounts taxonomy.
# The older frozen-encoder run (synth-crew-4321-pretrained) is left out: it was
# trained with 10 numeric features, the model now has 13, so it cannot load.
DEFAULT_RUNS = (
    "synth-crew-4321-pretrained-top2",
    "synth-crew-4321-pretrained-vatpaid",
)

ENV = "VAULT_CLASSIFIER"


class _Stage:
    """One model in the cascade, loaded on first use."""

    def __init__(self, name: str, loader: Callable[[], object]) -> None:
        self.name = name
        self._loader = loader
        self._model = None
        self._dead = False
        self._lock = threading.Lock()

    def get(self):
        if self._model is None and not self._dead:
            with self._lock:
                if self._model is None and not self._dead:
                    try:
                        self._model = self._loader()
                    except Exception as exc:  # missing torch, missing run, bad checkpoint
                        log.warning("classifier %s unavailable, skipping it: %s", self.name, exc)
                        self._dead = True
        return self._model


def _ask(model, vendor, description, amount, paid, date) -> tuple[str, float]:
    if hasattr(model, "predict_document"):  # DragoNet also uses amount, paid and date
        return model.predict_document(vendor, description, amount, paid, date)
    return model.predict(vendor, description)


class CascadeClassifier:
    def __init__(self, stages: list[tuple[str, Callable[[], object]]],
                 threshold: float = CONFIDENCE_THRESHOLD, preload: int = 1) -> None:
        if not stages:
            raise ValueError("cascade needs at least one model")
        self.threshold = threshold
        self._stages = [_Stage(name, loader) for name, loader in stages]
        # Load the first `preload` working models now so the first document
        # doesn't wait for them; the rest load only when first needed.
        loaded = 0
        for stage in self._stages:
            if loaded >= preload:
                break
            if stage.get() is not None:
                loaded += 1

    @property
    def stage_names(self) -> list[str]:
        return [s.name for s in self._stages]

    def decide(self, vendor: str, description: str, amount=None, paid=None,
               date=None) -> tuple[str, float, str]:
        """(account, confidence, name of the model that decided)."""
        best: tuple[str, float, str] | None = None
        for stage in self._stages:
            model = stage.get()
            if model is None:
                continue
            try:
                account, confidence = _ask(model, vendor, description, amount, paid, date)
            except Exception as exc:
                log.warning("classifier %s failed on a document, trying the next: %s", stage.name, exc)
                continue
            if confidence >= self.threshold:
                return account, confidence, stage.name
            if best is None or confidence > best[1]:
                best = (account, confidence, stage.name)
        if best is None:
            raise RuntimeError(f"no classifier in the cascade could run: {self.stage_names}")
        return best

    def predict_document(self, vendor, description, amount, paid, date) -> tuple[str, float]:
        account, confidence, _ = self.decide(vendor, description, amount, paid, date)
        return account, confidence

    def predict(self, vendor: str, description: str) -> tuple[str, float]:
        account, confidence, _ = self.decide(vendor, description)
        return account, confidence


def _dragonet_loader(run_dir: Path) -> Callable[[], object]:
    def load():
        from vault_ledger.classifier.dragonet_adapter import DragoNetClassifier

        if not (run_dir / "model.pt").exists():
            raise FileNotFoundError(f"no model.pt in {run_dir}")
        return DragoNetClassifier(run_dir)

    return load


def build_cascade(tfidf_loader: Callable[[], object]) -> CascadeClassifier:
    """The app's classifier. VAULT_CLASSIFIER changes it:
      tfidf                  -> TF-IDF model only
      dragonet:<run folder>  -> that run first, then the default order
    """
    choice = os.environ.get(ENV, "")
    if choice == "tfidf":
        return CascadeClassifier([("tfidf", tfidf_loader)])

    run_dirs = [RUNS_DIR / name for name in DEFAULT_RUNS]
    if choice.startswith("dragonet:"):
        first = Path(choice.split(":", 1)[1])
        run_dirs = [first] + [d for d in run_dirs if d.resolve() != first.resolve()]

    stages = [(f"dragonet:{d.name}", _dragonet_loader(d)) for d in run_dirs]
    stages.append(("tfidf", tfidf_loader))
    # Preloads the first model that works; the fallbacks load when first asked.
    return CascadeClassifier(stages)
