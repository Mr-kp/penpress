"""Anti-repetition glyph variant indexing and selection.

Ensures natural variation across repeated characters by cycling and pseudo-randomly
sampling variants while strictly avoiding consecutive duplicates whenever multiple
variants are available in the handwriting profile.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field

from penpress.core.primitives import Stroke


@dataclass
class VariantBank:
    """Stores multiple variants for each character and manages anti-repetition state.

    Attributes:
        bank: Mapping from character to list of stroke variant sequences.
        last_used_index: Mapping from character to last sampled variant index.
        seed: Random generator seed for repeatable synthesis.
    """

    bank: dict[str, list[list[Stroke]]] = field(default_factory=dict)
    last_used_index: dict[str, int] = field(default_factory=dict)
    seed: int = 42

    def __post_init__(self) -> None:
        self._rng = random.Random(self.seed)

    def add_variant(self, char: str, strokes: list[Stroke]) -> None:
        if char not in self.bank:
            self.bank[char] = []
        self.bank[char].append(strokes)

    def has_variants(self, char: str) -> bool:
        return char in self.bank and len(self.bank[char]) > 0

    def variant_count(self, char: str) -> int:
        return len(self.bank.get(char, []))

    def select_variant(self, char: str) -> list[Stroke] | None:
        """Select a stroke variant for char, guaranteeing no consecutive duplicate if count >= 2.

        Returns None if char has no variants stored in the bank.
        """
        variants = self.bank.get(char)
        if not variants:
            return None

        n = len(variants)
        if n == 1:
            self.last_used_index[char] = 0
            return variants[0]

        last_idx = self.last_used_index.get(char, -1)

        # Candidate indices excluding last_idx
        candidates = [i for i in range(n) if i != last_idx]
        chosen_idx = self._rng.choice(candidates)

        self.last_used_index[char] = chosen_idx
        return variants[chosen_idx]

    def reset_usage_history(self) -> None:
        """Reset historical memory of last used indices."""
        self.last_used_index.clear()
