"""Inference: load a trained run and suggest categories.

Uses PyTorch for now. The ONNX/onnxruntime path without torch is ML-M7.
No network access: encoders load from local folders only.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import torch

from ..schemas import Suggestion, Transaction
from ..taxonomy import Taxonomy, load_taxonomy
from .dragonet import DragoNet
from .encoders import build_encoders
from .features import N_NUMERIC, field_a, field_b, numeric_batch
from .mask import DECODERS


def build_model(cfg: dict, tax: Taxonomy, train_texts: list[str] | None = None,
                spm_proto: bytes | None = None) -> DragoNet:
    enc_a, enc_b = build_encoders(cfg, train_texts=train_texts, spm_proto=spm_proto)
    m = cfg["model"]
    return DragoNet(enc_a, enc_b, N_NUMERIC, tax.n_macro, tax.n_micro, d=m["d"], dropout=m["dropout"],
                    use_field_a=m.get("use_field_a", True), use_field_b=m.get("use_field_b", True))


@torch.no_grad()
def compute_logits(model: DragoNet, texts_a: list[str], texts_b: list[str], num: np.ndarray,
                   batch_size: int = 128) -> tuple[np.ndarray, np.ndarray]:
    model.eval()
    outs_M, outs_m = [], []
    for s in range(0, len(texts_a), batch_size):
        lM, lm = model(texts_a[s:s + batch_size], texts_b[s:s + batch_size],
                       torch.from_numpy(num[s:s + batch_size]))
        outs_M.append(lM.numpy())
        outs_m.append(lm.numpy())
    if not outs_M:
        return np.zeros((0, model.head_macro.out_features)), np.zeros((0, model.head_micro.out_features))
    return np.concatenate(outs_M), np.concatenate(outs_m)


def decode_all(tax: Taxonomy, logits_M: np.ndarray, logits_m: np.ndarray, directions: list[str],
               method: str = "joint", top_k: int = 3):
    fn = DECODERS[method]
    return [fn(tax, logits_M[i], logits_m[i], directions[i], top_k) for i in range(len(directions))]


class Predictor:
    def __init__(self, model: DragoNet, tax: Taxonomy, cfg: dict, model_version: str = ""):
        self.model, self.tax, self.cfg, self.model_version = model, tax, cfg, model_version

    @classmethod
    def load(cls, run_dir: str | Path, taxonomy_path: str | Path | None = None) -> "Predictor":
        run_dir = Path(run_dir)
        ckpt = torch.load(run_dir / "model.pt", map_location="cpu", weights_only=False)
        tax = load_taxonomy(taxonomy_path or ckpt.get("taxonomy_path"))
        if tax.version != ckpt["taxonomy_version"]:
            raise ValueError(f"model trained on taxonomy {ckpt['taxonomy_version']}, loaded {tax.version}")
        if tax.micro_names != ckpt["micro_names"] or tax.macro_names != ckpt["macro_names"]:
            raise ValueError("taxonomy label order differs from the one the model was trained on")
        cfg = ckpt["config"]
        model = build_model(cfg, tax, spm_proto=ckpt.get("spm_proto"))
        missing, unexpected = model.load_state_dict(ckpt["state"], strict=False)
        frozen = set(model.state_dict()) - set(model.saveable_state_dict())
        if unexpected or set(missing) - frozen:
            raise ValueError(f"checkpoint mismatch: missing={sorted(set(missing) - frozen)[:5]} unexpected={unexpected[:5]}")
        model.eval()
        return cls(model, tax, cfg, model_version=ckpt.get("run_id", run_dir.name))

    def predict(self, txns: list[Transaction]) -> list[Suggestion]:
        A = [field_a(t) for t in txns]
        B = [field_b(t) for t in txns]
        lM, lm = compute_logits(self.model, A, B, numeric_batch(txns))
        dec = self.cfg.get("decode", {})
        decoded = decode_all(self.tax, lM, lm, [t.direction for t in txns],
                             dec.get("method", "joint"), dec.get("top_k", 3))
        out = []
        for t, d in zip(txns, decoded):
            out.append(Suggestion(
                txn_id=t.txn_id,
                ref_macro=self.tax.macro_names[d.macro],
                ref_micro=self.tax.micro_names[d.micro],
                confidence=d.prob,
                status="REVIEW",  # no AUTO before calibration (ML-M9)
                alternatives=[(self.tax.micro_names[j], p) for _, j, p in d.top[1:]],
                model_version=self.model_version,
            ))
        return out
