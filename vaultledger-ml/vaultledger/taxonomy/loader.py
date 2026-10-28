"""Load and validate the two-level reference taxonomy (macro -> micro).

The model's label space is the *trainable* part only: SUSPENSE/uncategorized
is never predicted by the network; abstention puts rows there later (ML-M9).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import yaml

DEFAULT_PATH = Path(__file__).with_name("reference_taxonomy.yaml")
DIRECTIONS = ("IN", "OUT", "BOTH")


class TaxonomyError(ValueError):
    pass


@dataclass(frozen=True)
class Micro:
    name: str
    macro: str
    allowed_direction: str
    trainable: bool = True


@dataclass
class Taxonomy:
    version: str
    micros: dict[str, Micro]
    # Trainable label space, in a fixed order.
    macro_names: list[str] = field(default_factory=list)
    micro_names: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        trainable = [m for m in self.micros.values() if m.trainable]
        self.micro_names = [m.name for m in trainable]
        seen: list[str] = []
        for m in trainable:
            if m.macro not in seen:
                seen.append(m.macro)
        self.macro_names = seen
        self.macro_index = {n: i for i, n in enumerate(self.macro_names)}
        self.micro_index = {n: i for i, n in enumerate(self.micro_names)}
        # parent[j] = macro index of micro j
        self.parent = np.array([self.macro_index[self.micros[n].macro] for n in self.micro_names])
        # child[i, j] = micro j is a child of macro i
        self.child = np.zeros((len(self.macro_names), len(self.micro_names)), dtype=bool)
        self.child[self.parent, np.arange(len(self.micro_names))] = True

    @property
    def n_macro(self) -> int:
        return len(self.macro_names)

    @property
    def n_micro(self) -> int:
        return len(self.micro_names)

    def direction_ok(self, direction: str) -> np.ndarray:
        """Boolean vector over trainable micros: allowed for this direction."""
        if direction not in ("IN", "OUT"):
            raise TaxonomyError(f"transaction direction must be IN or OUT, got {direction!r}")
        return np.array(
            [self.micros[n].allowed_direction in (direction, "BOTH") for n in self.micro_names]
        )

    def macro_of(self, micro: str) -> str:
        return self.micros[micro].macro


def load_taxonomy(path: str | Path | None = None) -> Taxonomy:
    path = Path(path) if path else DEFAULT_PATH
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or "taxonomy_version" not in raw or "macros" not in raw:
        raise TaxonomyError(f"{path}: needs 'taxonomy_version' and 'macros'")
    micros: dict[str, Micro] = {}
    for macro, children in raw["macros"].items():
        if not children:
            raise TaxonomyError(f"macro {macro} has no micro categories")
        for name, spec in children.items():
            if name in micros:
                raise TaxonomyError(
                    f"micro {name!r} appears under both {micros[name].macro} and {macro}"
                )
            spec = spec or {}
            direction = spec.get("allowed_direction")
            if direction not in DIRECTIONS:
                raise TaxonomyError(f"micro {name!r}: allowed_direction must be one of {DIRECTIONS}")
            micros[name] = Micro(name, macro, direction, bool(spec.get("trainable", True)))
    tax = Taxonomy(version=str(raw["taxonomy_version"]), micros=micros)
    tax.path = str(path)
    if tax.n_micro == 0:
        raise TaxonomyError("no trainable micro categories")
    return tax
