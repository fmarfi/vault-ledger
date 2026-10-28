"""DragoNet-style two-field, two-head categorizer (spec 6.4.3).

    Field A (name)    -> encoder_a -> pool -> proj -> hA (d)
    Field B (context) -> encoder_b -> pool -> proj -> hB (d)
    numeric features  -> Linear -> GELU            -> hN (d/2)
    fusion: concat[hA, hB, hA*hB, |hA-hB|, hN] -> Linear -> GELU -> Dropout -> z (d)
    macro head: Linear(z)
    micro head: Linear(concat[z, softmax(macro logits)])

Reference: Busson et al., "Two-headed DragoNet", arXiv:2312.07730. Layer sizes
and the fusion operator here are this project's choices, not the paper's.
The encoders are pluggable (see encoders.py); with a frozen pretrained
encoder only the projection, fusion and heads are trained.
"""
from __future__ import annotations

import torch
from torch import nn


class DragoNet(nn.Module):
    def __init__(self, encoder_a: nn.Module, encoder_b: nn.Module, n_numeric: int,
                 n_macro: int, n_micro: int, d: int = 128, dropout: float = 0.1,
                 use_field_a: bool = True, use_field_b: bool = True):
        super().__init__()
        if not (use_field_a or use_field_b):
            raise ValueError("at least one text field must be used")
        self.encoder_a = encoder_a
        self.encoder_b = encoder_b
        self.shared = encoder_a is encoder_b
        self.use_a, self.use_b = use_field_a, use_field_b
        self.proj_a = nn.Linear(encoder_a.out_dim, d)
        self.proj_b = nn.Linear(encoder_b.out_dim, d)
        self.numeric = nn.Sequential(nn.Linear(n_numeric, d // 2), nn.GELU())
        self.fusion = nn.Sequential(nn.Linear(4 * d + d // 2, d), nn.GELU(), nn.Dropout(dropout))
        self.head_macro = nn.Linear(d, n_macro)
        self.head_micro = nn.Linear(d + n_macro, n_micro)

    # -- encoding -----------------------------------------------------------
    def encode_a(self, texts: list[str]) -> torch.Tensor:
        return self.encoder_a(texts)

    def encode_b(self, texts: list[str]) -> torch.Tensor:
        return self.encoder_b(texts)

    @property
    def encoders_frozen(self) -> bool:
        return bool(getattr(self.encoder_a, "frozen", False) and getattr(self.encoder_b, "frozen", False))

    # -- from pooled encoder outputs (lets training cache frozen encodings) ---
    def forward_pooled(self, pooled_a: torch.Tensor, pooled_b: torch.Tensor,
                       numeric: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        ha = self.proj_a(pooled_a)
        hb = self.proj_b(pooled_b)
        # Ablations (spec 8.3): a switched-off field contributes nothing.
        if not self.use_a:
            ha = torch.zeros_like(ha)
        if not self.use_b:
            hb = torch.zeros_like(hb)
        h = torch.cat([ha, hb, ha * hb, (ha - hb).abs(), self.numeric(numeric)], dim=-1)
        z = self.fusion(h)
        logits_macro = self.head_macro(z)
        logits_micro = self.head_micro(torch.cat([z, logits_macro.softmax(-1)], dim=-1))
        return logits_macro, logits_micro

    def forward(self, texts_a: list[str], texts_b: list[str],
                numeric: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        return self.forward_pooled(self.encode_a(texts_a), self.encode_b(texts_b), numeric)

    # -- saving ---------------------------------------------------------------
    def saveable_state_dict(self) -> dict[str, torch.Tensor]:
        """Everything except frozen pretrained weights (those ship as the encoder folder)."""
        frozen_names = set()
        for prefix, enc in (("encoder_a.", self.encoder_a), ("encoder_b.", self.encoder_b)):
            if getattr(enc, "is_pretrained", False):
                for name, p in enc.named_parameters():
                    if not p.requires_grad:
                        frozen_names.add(prefix + name)
                for name, _ in enc.named_buffers():
                    frozen_names.add(prefix + name)
        return {k: v for k, v in self.state_dict().items() if k not in frozen_names}

    def count_parameters(self) -> dict[str, int]:
        seen: set[int] = set()
        total = trainable = 0
        for p in self.parameters():
            if id(p) in seen:
                continue
            seen.add(id(p))
            total += p.numel()
            trainable += p.numel() if p.requires_grad else 0
        return {"total": total, "trainable": trainable}
