"""Text encoders for the two DragoNet fields.

Two kinds, chosen in config (`encoder.kind`):

- `pretrained` (default): a small multilingual Transformer that already knows
  Dutch/English, loaded from a local folder. It is fetched once at build time
  (`scripts/fetch_encoder.py`) and ships inside the app; nothing is downloaded
  at runtime. This replaces the spec's from-scratch encoder because we have
  little training data.
- `scratch`: the spec's original design (6.4.3): SentencePiece trained locally
  + Embedding + TransformerEncoder. Kept as a fallback and for fast tests.

Both map a list of strings to a (batch, out_dim) tensor by mean pooling.
"""
from __future__ import annotations

import io
import os
from pathlib import Path

# Never let the Hugging Face libraries reach the network from this package.
os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
os.environ.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")

import torch  # noqa: E402
from torch import nn  # noqa: E402

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def resolve_path(p: str | Path) -> Path:
    p = Path(p)
    return p if p.is_absolute() else PROJECT_ROOT / p


def _mean_pool(hidden: torch.Tensor, mask: torch.Tensor) -> torch.Tensor:
    m = mask.unsqueeze(-1).to(hidden.dtype)
    return (hidden * m).sum(1) / m.sum(1).clamp(min=1.0)


class PretrainedEncoder(nn.Module):
    """Wraps a local Hugging Face encoder (BERT-family) with mean pooling."""

    is_pretrained = True

    def __init__(self, path: str | Path, max_len: int, text_prefix: str = "",
                 freeze: str = "all", unfreeze_top_layers: int = 0):
        super().__init__()
        from transformers import AutoModel, AutoTokenizer

        path = resolve_path(path)
        if not (path / "config.json").exists():
            raise FileNotFoundError(
                f"pretrained encoder not found at {path}. Run `python scripts/fetch_encoder.py` "
                "once (build time), or set encoder.kind: scratch."
            )
        self.path = str(path)
        self.tokenizer = AutoTokenizer.from_pretrained(path, local_files_only=True)
        self.backbone = AutoModel.from_pretrained(path, local_files_only=True)
        self.max_len = max_len
        self.text_prefix = text_prefix
        self.out_dim = int(self.backbone.config.hidden_size)
        self._set_freeze(freeze, unfreeze_top_layers)

    def _set_freeze(self, freeze: str, top_n: int) -> None:
        if freeze not in ("all", "top_n", "none"):
            raise ValueError("encoder freeze must be all | top_n | none")
        for p in self.backbone.parameters():
            p.requires_grad = freeze == "none"
        if freeze == "top_n" and top_n > 0:
            layers = getattr(getattr(self.backbone, "encoder", None), "layer", None)
            if layers is None:
                raise ValueError("top_n unfreezing needs a BERT-style backbone.encoder.layer")
            for layer in layers[-top_n:]:
                for p in layer.parameters():
                    p.requires_grad = True
        self.frozen = not any(p.requires_grad for p in self.backbone.parameters())
        if self.frozen:
            self.backbone.eval()

    def train(self, mode: bool = True):  # keep a frozen backbone in eval mode (no dropout)
        super().train(mode)
        if self.frozen:
            self.backbone.eval()
        return self

    def forward(self, texts: list[str]) -> torch.Tensor:
        batch = self.tokenizer(
            [self.text_prefix + t for t in texts], padding=True, truncation=True,
            max_length=self.max_len, return_tensors="pt",
        )
        with torch.set_grad_enabled(torch.is_grad_enabled() and not self.frozen):
            out = self.backbone(**batch).last_hidden_state
        return _mean_pool(out, batch["attention_mask"])


class SpmTokenizer:
    """SentencePiece unigram tokenizer trained locally on the training text."""

    PAD, UNK = 0, 1

    def __init__(self, model_proto: bytes):
        import sentencepiece as spm

        self.proto = model_proto
        self.sp = spm.SentencePieceProcessor(model_proto=model_proto)

    @classmethod
    def train(cls, texts: list[str], vocab_size: int) -> "SpmTokenizer":
        import sentencepiece as spm

        buf = io.BytesIO()
        spm.SentencePieceTrainer.train(
            sentence_iterator=iter([t for t in texts if t.strip()] or ["empty"]),
            model_writer=buf, vocab_size=vocab_size, model_type="unigram",
            character_coverage=1.0, hard_vocab_limit=False,
            pad_id=cls.PAD, unk_id=cls.UNK, bos_id=-1, eos_id=-1,
            minloglevel=2,
        )
        return cls(buf.getvalue())

    @property
    def vocab_size(self) -> int:
        return self.sp.get_piece_size()

    def __call__(self, texts: list[str], max_len: int) -> tuple[torch.Tensor, torch.Tensor]:
        ids = [self.sp.encode(t)[:max_len] or [self.UNK] for t in texts]
        width = max(len(x) for x in ids)
        out = torch.full((len(ids), width), self.PAD, dtype=torch.long)
        for i, x in enumerate(ids):
            out[i, : len(x)] = torch.tensor(x)
        return out, out != self.PAD


class ScratchEncoder(nn.Module):
    """Spec 6.4.3 encoder: Embedding + positions + TransformerEncoder + mean pool."""

    is_pretrained = False
    frozen = False

    def __init__(self, tokenizer: SpmTokenizer, max_len: int, d: int = 128, layers: int = 2,
                 heads: int = 4, ff: int = 256, dropout: float = 0.1):
        super().__init__()
        self.tokenizer = tokenizer
        self.max_len = max_len
        self.out_dim = d
        self.emb = nn.Embedding(tokenizer.vocab_size, d, padding_idx=SpmTokenizer.PAD)
        self.pos = nn.Embedding(max_len, d)
        layer = nn.TransformerEncoderLayer(d, heads, ff, dropout, activation="gelu", batch_first=True)
        self.encoder = nn.TransformerEncoder(layer, layers, enable_nested_tensor=False)

    def forward(self, texts: list[str]) -> torch.Tensor:
        ids, mask = self.tokenizer(texts, self.max_len)
        pos = torch.arange(ids.shape[1]).unsqueeze(0)
        h = self.encoder(self.emb(ids) + self.pos(pos), src_key_padding_mask=~mask)
        return _mean_pool(h, mask)


def build_encoders(cfg: dict, train_texts: list[str] | None = None,
                   spm_proto: bytes | None = None) -> tuple[nn.Module, nn.Module]:
    """Return (encoder_a, encoder_b). They are the same object when shared."""
    enc = cfg["encoder"]
    kind = enc["kind"]
    if kind == "pretrained":
        p = enc["pretrained"]
        mk = lambda max_len: PretrainedEncoder(  # noqa: E731
            p["path"], max_len, p.get("text_prefix", ""), p.get("freeze", "all"),
            int(p.get("unfreeze_top_layers", 0)))
        share = bool(p.get("share_encoders", True))
        if share:
            # One backbone; max_len is per call, so use the longer field's.
            e = mk(max(enc["max_len_a"], enc["max_len_b"]))
            return e, e
        return mk(enc["max_len_a"]), mk(enc["max_len_b"])
    if kind == "scratch":
        s = enc["scratch"]
        if spm_proto is not None:
            tok = SpmTokenizer(spm_proto)
        elif train_texts is not None:
            tok = SpmTokenizer.train(train_texts, int(s["vocab_size"]))
        else:
            raise ValueError("scratch encoder needs training texts or a saved tokenizer")
        mk = lambda max_len: ScratchEncoder(  # noqa: E731
            tok, max_len, s["d"], s["layers"], s["heads"], s["ff"], s.get("dropout", 0.1))
        if bool(s.get("share_encoders", False)):
            e = mk(max(enc["max_len_a"], enc["max_len_b"]))
            return e, e
        return mk(enc["max_len_a"]), mk(enc["max_len_b"])
    raise ValueError(f"unknown encoder.kind {kind!r}")
