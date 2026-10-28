"""Fetch the pretrained encoder once, at BUILD time, into models/encoders/.

The app never downloads anything at runtime; this folder ships in the bundle.
Needs the `fetch` extra:  pip install huggingface_hub

    python scripts/fetch_encoder.py                      # model from configs/default.yaml
    python scripts/fetch_encoder.py --hf-id ... --out models/encoders/name
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    cfg = yaml.safe_load((ROOT / "configs" / "default.yaml").read_text(encoding="utf-8"))
    pre = cfg["encoder"]["pretrained"]
    ap = argparse.ArgumentParser()
    ap.add_argument("--hf-id", default=pre["hf_id"])
    ap.add_argument("--out", default=pre["path"])
    a = ap.parse_args()
    out = Path(a.out) if Path(a.out).is_absolute() else ROOT / a.out
    os.environ.pop("HF_HUB_OFFLINE", None)
    from huggingface_hub import snapshot_download

    # Only what inference needs: PyTorch weights, config and tokenizer files.
    snapshot_download(
        repo_id=a.hf_id, local_dir=out,
        allow_patterns=["config.json", "model.safetensors", "tokenizer*", "sentencepiece*",
                        "special_tokens_map.json", "LICENSE*", "README.md"],
    )
    size = sum(f.stat().st_size for f in out.rglob("*") if f.is_file()) / 1e6
    print(f"fetched {a.hf_id} -> {out} ({size:.0f} MB). Check its licence before shipping.")


if __name__ == "__main__":
    main()
