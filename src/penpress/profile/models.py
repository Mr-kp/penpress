"""Handwriting profile data models and serialization.

A handwriting profile stores user metadata, style statistics, and a glyph bank
mapping unicode characters to one or more Stroke sequences (variants).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from penpress.core.primitives import Stroke


@dataclass(frozen=True)
class StyleMetrics:
    slant_deg: float = 0.0
    baseline_jitter_mm: float = 0.06
    spacing_jitter_mm: float = 0.15
    stroke_width_mean_mm: float = 0.4
    x_height_mm: float = 3.5
    ascent_mm: float = 2.0
    descent_mm: float = 1.5

    def to_dict(self) -> dict[str, float]:
        return {
            "slant_deg": round(self.slant_deg, 2),
            "baseline_jitter_mm": round(self.baseline_jitter_mm, 4),
            "spacing_jitter_mm": round(self.spacing_jitter_mm, 4),
            "stroke_width_mean_mm": round(self.stroke_width_mean_mm, 3),
            "x_height_mm": round(self.x_height_mm, 2),
            "ascent_mm": round(self.ascent_mm, 2),
            "descent_mm": round(self.descent_mm, 2),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> StyleMetrics:
        return cls(
            slant_deg=float(data.get("slant_deg", 0.0)),
            baseline_jitter_mm=float(data.get("baseline_jitter_mm", 0.06)),
            spacing_jitter_mm=float(data.get("spacing_jitter_mm", 0.15)),
            stroke_width_mean_mm=float(data.get("stroke_width_mean_mm", 0.4)),
            x_height_mm=float(data.get("x_height_mm", 3.5)),
            ascent_mm=float(data.get("ascent_mm", 2.0)),
            descent_mm=float(data.get("descent_mm", 1.5)),
        )


@dataclass
class HandwritingProfile:
    profile_id: str
    user_name: str
    created_at: str
    schema_version: str = "1.0.0"
    metrics: StyleMetrics = field(default_factory=StyleMetrics)
    glyph_bank: dict[str, list[list[Stroke]]] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def add_glyph_variant(self, char: str, strokes: list[Stroke]) -> None:
        if char not in self.glyph_bank:
            self.glyph_bank[char] = []
        self.glyph_bank[char].append(strokes)

    def get_glyph_variants(self, char: str) -> list[list[Stroke]]:
        return self.glyph_bank.get(char, [])

    @property
    def total_glyphs(self) -> int:
        return len(self.glyph_bank)

    @property
    def total_variants(self) -> int:
        return sum(len(variants) for variants in self.glyph_bank.values())

    def to_dict(self) -> dict[str, Any]:
        serialized_bank: dict[str, list[list[dict[str, Any]]]] = {}
        for char, variant_list in self.glyph_bank.items():
            serialized_bank[char] = []
            for strokes in variant_list:
                serialized_bank[char].append([s.to_dict() for s in strokes])

        return {
            "profile_id": self.profile_id,
            "user_name": self.user_name,
            "created_at": self.created_at,
            "schema_version": self.schema_version,
            "metrics": self.metrics.to_dict(),
            "total_glyphs": self.total_glyphs,
            "total_variants": self.total_variants,
            "metadata": self.metadata,
            "glyph_bank": serialized_bank,
        }

    def save_json(self, path: str | Path) -> None:
        out_path = Path(path)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(self.to_dict(), indent=2), encoding="utf-8")

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> HandwritingProfile:
        metrics = StyleMetrics.from_dict(data.get("metrics", {}))
        bank: dict[str, list[list[Stroke]]] = {}

        raw_bank = data.get("glyph_bank", {})
        for char, raw_variants in raw_bank.items():
            bank[char] = []
            for raw_strokes in raw_variants:
                strokes: list[Stroke] = []
                for s_dict in raw_strokes:
                    strokes.append(Stroke.from_dict(s_dict))
                bank[char].append(strokes)

        return cls(
            profile_id=str(data.get("profile_id", "default")),
            user_name=str(data.get("user_name", "Anonymous")),
            created_at=str(data.get("created_at", "")),
            schema_version=str(data.get("schema_version", "1.0.0")),
            metrics=metrics,
            glyph_bank=bank,
            metadata=dict(data.get("metadata", {})),
        )

    @classmethod
    def load_json(cls, path: str | Path) -> HandwritingProfile:
        in_path = Path(path)
        data = json.loads(in_path.read_text(encoding="utf-8"))
        return cls.from_dict(data)
