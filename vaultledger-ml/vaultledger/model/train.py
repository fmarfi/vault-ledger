"""Phase A training (spec 6.4.5): train the base DragoNet model.

    python -m vaultledger.model.train                       # synthetic fixture, default config
    python -m vaultledger.model.train --data path/to/export --out runs/my-run
    python -m vaultledger.model.train --set encoder.kind=scratch --set train.epochs=3

With a frozen pretrained encoder (the default) the text encodings are computed
once and cached, so each epoch only trains projection + fusion + heads.
Validation is vendor-disjoint: the model is scored on vendors it never saw.
"""
from __future__ import annotations

import argparse
import copy
import json
import math
import platform
import random
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import numpy as np
import torch
import torch.nn.functional as F
import yaml

from ..eval.metrics import SYNTHETIC_BANNER, summarize
from ..eval.splits import group_split
from ..schemas import Label, Transaction
from ..taxonomy import Taxonomy, load_taxonomy
from .dragonet import DragoNet
from .encoders import PROJECT_ROOT
from .features import field_a, field_b, has_activity, numeric_batch
from .infer import build_model, compute_logits, decode_all

DEFAULT_CONFIG = PROJECT_ROOT / "configs" / "default.yaml"


# -- config -------------------------------------------------------------------
def load_config(path: str | Path | None = None, overrides: list[str] | None = None) -> dict:
    cfg = yaml.safe_load(Path(path or DEFAULT_CONFIG).read_text(encoding="utf-8"))
    for item in overrides or []:
        key, _, raw = item.partition("=")
        node = cfg
        *parents, leaf = key.split(".")
        for p in parents:
            node = node.setdefault(p, {})
        node[leaf] = yaml.safe_load(raw)
    return cfg


# -- data ---------------------------------------------------------------------
@dataclass
class Examples:
    txns: list[Transaction]
    y_macro: np.ndarray
    y_micro: np.ndarray
    text_a: list[str]
    text_b: list[str]
    text_b_noact: list[str]
    has_act: np.ndarray
    num: np.ndarray

    def subset(self, idx: list[int]) -> "Examples":
        return Examples([self.txns[i] for i in idx], self.y_macro[idx], self.y_micro[idx],
                        [self.text_a[i] for i in idx], [self.text_b[i] for i in idx],
                        [self.text_b_noact[i] for i in idx], self.has_act[idx], self.num[idx])

    def __len__(self) -> int:
        return len(self.txns)


def prepare(txns: list[Transaction], labels: list[Label], tax: Taxonomy,
            train_on_low_quality: bool = False) -> tuple[Examples, dict]:
    by_id = {lab.txn_id: lab for lab in labels}
    keep, ym, yu = [], [], []
    skipped = {"no_label": 0, "low_quality": 0, "not_trainable": 0}
    for t in txns:
        lab = by_id.get(t.txn_id)
        if lab is None:
            skipped["no_label"] += 1
        elif lab.quality == "LOW" and not train_on_low_quality:
            skipped["low_quality"] += 1
        elif lab.ref_micro not in tax.micro_index:
            skipped["not_trainable"] += 1
        else:
            keep.append(t)
            yu.append(tax.micro_index[lab.ref_micro])
            ym.append(tax.parent[tax.micro_index[lab.ref_micro]])
    ex = Examples(
        txns=keep, y_macro=np.array(ym, dtype=np.int64), y_micro=np.array(yu, dtype=np.int64),
        text_a=[field_a(t) for t in keep], text_b=[field_b(t, True) for t in keep],
        text_b_noact=[field_b(t, False) for t in keep],
        has_act=np.array([has_activity(t) for t in keep], dtype=bool), num=numeric_batch(keep),
    )
    return ex, skipped


def _class_weights(y: np.ndarray, n: int) -> torch.Tensor:
    counts = np.bincount(y, minlength=n).astype(np.float64)
    w = 1.0 / np.sqrt(counts + 1.0)
    w = w / w[counts > 0].mean() if (counts > 0).any() else w
    return torch.tensor(w, dtype=torch.float32)


@torch.no_grad()
def _encode_cached(model: DragoNet, ex: Examples, bs: int = 128) -> dict[str, torch.Tensor]:
    """Pooled encodings for a frozen encoder: A, B with activity, B without, and empties."""
    model.eval()

    def run(enc, texts):
        return torch.cat([enc(texts[s:s + bs]) for s in range(0, len(texts), bs)]) if texts else None

    return {
        "a": run(model.encode_a, ex.text_a),
        "b": run(model.encode_b, ex.text_b),
        "b_noact": run(model.encode_b, ex.text_b_noact),
        "empty_a": model.encode_a([""]),
        "empty_b": model.encode_b([""]),
    }


def _evaluate(model: DragoNet, tax: Taxonomy, ex: Examples, method: str,
              cache: dict | None = None) -> dict:
    if cache is not None:
        model.eval()
        with torch.no_grad():
            lM, lm = model.forward_pooled(cache["a"], cache["b"], torch.from_numpy(ex.num))
        lM, lm = lM.numpy(), lm.numpy()
    else:
        lM, lm = compute_logits(model, ex.text_a, ex.text_b, ex.num)
    dec = decode_all(tax, lM, lm, [t.direction for t in ex.txns], method)
    return summarize(tax.parent, ex.y_macro, ex.y_micro,
                     np.array([d.macro for d in dec]), np.array([d.micro for d in dec]))


# -- training -----------------------------------------------------------------
def train(cfg: dict, txns: list[Transaction], labels: list[Label], out_dir: str | Path,
          tax: Taxonomy | None = None, synthetic: bool = True, log=print,
          split_ids: tuple[set, set] | None = None) -> dict:
    """split_ids=(train_ids, val_ids) uses a given split instead of the vendor-disjoint one."""
    tax = tax or load_taxonomy()
    tc = cfg["train"]
    seed = int(tc["seed"])
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    rng = np.random.default_rng(seed)

    ex, skipped = prepare(txns, labels, tax, tc.get("train_on_low_quality", False))
    if len(ex) < 20:
        raise ValueError(f"only {len(ex)} usable labeled rows; need at least 20")
    if split_ids:
        tr_idx = [i for i, t in enumerate(ex.txns) if t.txn_id in split_ids[0]]
        va_idx = [i for i, t in enumerate(ex.txns) if t.txn_id in split_ids[1]]
    else:
        tr_idx, va_idx = group_split(ex.txns, tc["val_frac"], seed)
    tr, va = ex.subset(tr_idx), ex.subset(va_idx)
    log(f"rows: train {len(tr)}, validation {len(va)} (vendor-disjoint); skipped {skipped}")

    t0 = time.time()
    tok_texts = tr.text_a + tr.text_b if cfg["encoder"]["kind"] == "scratch" else None
    model = build_model(cfg, tax, train_texts=tok_texts)
    params = model.count_parameters()
    log(f"model: encoder={cfg['encoder']['kind']} params total={params['total']:,} trainable={params['trainable']:,}")

    cached = model.encoders_frozen
    if cached:
        log("encoder frozen: caching text encodings once ...")
        c_tr, c_va = _encode_cached(model, tr), _encode_cached(model, va)
        log(f"  cached in {time.time() - t0:.1f}s")
    else:
        c_tr = c_va = None

    enc_params = [p for n, p in model.named_parameters() if n.startswith("encoder_") and p.requires_grad]
    enc_ids = {id(p) for p in enc_params}
    head_params = [p for p in model.parameters() if p.requires_grad and id(p) not in enc_ids]
    is_pre = cfg["encoder"]["kind"] == "pretrained"
    groups = [{"params": head_params, "lr": tc["lr"]}]
    if enc_params:
        groups.append({"params": list({id(p): p for p in enc_params}.values()),
                       "lr": tc["encoder_lr"] if is_pre else tc["lr"]})
    opt = torch.optim.AdamW(groups, weight_decay=tc["weight_decay"])
    bs = int(tc["batch_size"])
    steps_per_epoch = math.ceil(len(tr) / bs)
    total = steps_per_epoch * int(tc["epochs"])
    warm = max(1, int(tc["warmup_frac"] * total))
    sched = torch.optim.lr_scheduler.LambdaLR(
        opt, lambda s: (s + 1) / warm if s < warm else 0.5 * (1 + math.cos(math.pi * (s - warm) / max(1, total - warm))))

    w_M = _class_weights(tr.y_macro, tax.n_macro) if tc["class_weights"] else None
    w_m = _class_weights(tr.y_micro, tax.n_micro) if tc["class_weights"] else None
    ls, lam = float(tc["label_smoothing"]), float(tc["lambda_micro"])
    p_act, p_field = float(tc["activity_dropout"]), float(tc["field_dropout"])
    method = cfg["decode"]["method"]

    best, best_state, best_epoch, bad, history = -1.0, None, 0, 0, []
    for epoch in range(1, int(tc["epochs"]) + 1):
        model.train()
        order = rng.permutation(len(tr))
        total_loss = 0.0
        for s in range(0, len(tr), bs):
            b = order[s:s + bs]
            drop_act = (rng.random(len(b)) < p_act) & tr.has_act[b]
            blank_a = rng.random(len(b)) < p_field
            blank_b = (rng.random(len(b)) < p_field) & ~blank_a  # never blank both
            num = torch.from_numpy(tr.num[b])
            if cached:
                pa = c_tr["a"][b].clone()
                pb = torch.where(torch.from_numpy(drop_act)[:, None], c_tr["b_noact"][b], c_tr["b"][b])
                pa[torch.from_numpy(blank_a)] = c_tr["empty_a"]
                pb[torch.from_numpy(blank_b)] = c_tr["empty_b"]
                lM, lm = model.forward_pooled(pa, pb, num)
            else:
                ta = ["" if blank_a[k] else tr.text_a[i] for k, i in enumerate(b)]
                tb = ["" if blank_b[k] else (tr.text_b_noact[i] if drop_act[k] else tr.text_b[i])
                      for k, i in enumerate(b)]
                lM, lm = model(ta, tb, num)
            loss = (F.cross_entropy(lM, torch.from_numpy(tr.y_macro[b]), weight=w_M, label_smoothing=ls)
                    + lam * F.cross_entropy(lm, torch.from_numpy(tr.y_micro[b]), weight=w_m, label_smoothing=ls))
            opt.zero_grad()
            loss.backward()
            torch.nn.utils.clip_grad_norm_([p for g in groups for p in g["params"]], 1.0)
            opt.step()
            sched.step()
            total_loss += loss.item() * len(b)
        val = _evaluate(model, tax, va, method, c_va)
        score = val["micro_level"]["macro_f1"]
        history.append({"epoch": epoch, "train_loss": total_loss / len(tr), "val": val})
        log(f"epoch {epoch:2d}  loss {total_loss / len(tr):.4f}  val micro macro-F1 {score:.3f}  "
            f"val macro-level macro-F1 {val['macro_level']['macro_f1']:.3f}")
        if score > best:
            best, best_epoch, bad = score, epoch, 0
            best_state = copy.deepcopy(model.saveable_state_dict())
        else:
            bad += 1
            if bad >= int(tc["patience"]):
                log(f"early stop at epoch {epoch} (best {best_epoch})")
                break

    model.load_state_dict(best_state, strict=False)
    train_seconds = time.time() - t0
    final_val = _evaluate(model, tax, va, method, c_va)
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    run_id = out.name
    spm_proto = getattr(getattr(model.encoder_a, "tokenizer", None), "proto", None) \
        if cfg["encoder"]["kind"] == "scratch" else None
    torch.save({
        "state": model.saveable_state_dict(), "config": cfg, "run_id": run_id,
        "taxonomy_version": tax.version, "taxonomy_path": getattr(tax, "path", None), "macro_names": tax.macro_names, "micro_names": tax.micro_names,
        "spm_proto": spm_proto,
    }, out / "model.pt")
    if spm_proto:
        (out / "spm.model").write_bytes(spm_proto)
    metrics = {
        "banner": SYNTHETIC_BANNER if synthetic else "Results on real labeled data.",
        "run_id": run_id, "created": datetime.now().isoformat(timespec="seconds"),
        "machine": f"{platform.processor() or platform.machine()} / {platform.system()} {platform.release()}",
        "torch": torch.__version__, "encoder": cfg["encoder"]["kind"],
        "encoder_path": cfg["encoder"]["pretrained"]["path"] if is_pre else None,
        "params": params, "rows": {"train": len(tr), "validation": len(va), "skipped": skipped},
        "best_epoch": best_epoch, "train_seconds": round(train_seconds, 1),
        "decode": method, "validation": final_val, "history": history,
    }
    (out / "metrics.json").write_text(json.dumps(metrics, indent=1), encoding="utf-8")
    (out / "config.yaml").write_text(yaml.safe_dump(cfg, sort_keys=False), encoding="utf-8")
    (out / "report.md").write_text(_report_md(metrics), encoding="utf-8")
    log(f"saved {out}  ({train_seconds:.0f}s)")
    return metrics


def _report_md(m: dict) -> str:
    v = m["validation"]
    return "\n".join([
        f"*{m['banner']}*", "", f"# Training run {m['run_id']}", "",
        f"- Machine: {m['machine']}; torch {m['torch']}; time {m['train_seconds']} s",
        f"- Encoder: {m['encoder']} ({m['encoder_path'] or 'trained from scratch'})",
        f"- Parameters: {m['params']['total']:,} total, {m['params']['trainable']:,} trained",
        f"- Rows: {m['rows']['train']} train, {m['rows']['validation']} validation (vendors not seen in training)",
        f"- Best epoch: {m['best_epoch']}; decoding: {m['decode']}", "",
        "| Level | Macro-F1 | Accuracy |", "|---|---|---|",
        f"| Main category | {v['macro_level']['macro_f1']:.3f} | {v['macro_level']['accuracy']:.3f} |",
        f"| Sub-category | {v['micro_level']['macro_f1']:.3f} | {v['micro_level']['accuracy']:.3f} |", "",
        f"Hierarchy violations: {v['hierarchy_violations']} (must be 0).", "",
        "Validation labels include the generator's label noise; scores are measured against them.", "",
    ])


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description="Train the base DragoNet model (Phase A).")
    ap.add_argument("--config", default=None)
    ap.add_argument("--data", default=None, help="folder an adapter can read; default: generate synthetic")
    ap.add_argument("--adapter", default="synthetic", choices=["synthetic"])
    ap.add_argument("--out", default=None)
    ap.add_argument("--set", action="append", default=[], metavar="KEY=VALUE")
    a = ap.parse_args(argv)
    cfg = load_config(a.config, a.set)
    if a.data:
        from ..io.adapters import SyntheticAdapter

        txns, labels, _ = SyntheticAdapter().load(a.data)
        synthetic = a.adapter == "synthetic"
    else:
        from ..synth.generator import generate

        ds = generate(cfg.get("synth"))
        txns, labels, synthetic = ds.transactions, ds.labels, True
        print(f"generated synthetic fixture: {len(txns)} rows, {ds.report['n_vendors']} vendors")
    out = a.out or PROJECT_ROOT / "runs" / datetime.now().strftime("%Y%m%d-%H%M%S")
    train(cfg, txns, labels, out, synthetic=synthetic)


if __name__ == "__main__":
    main()
