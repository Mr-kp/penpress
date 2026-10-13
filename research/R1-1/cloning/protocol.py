"""Common Synthesizer Protocol and Benchmark Contracts for PenPress.

Defines:
- Synthesizer protocol: profile + text -> list of strokes in mm with pen-up gaps
- SynthesisResult: strokes, timing stats, metrics, warnings
- StyleProfile: extracted or loaded user handwriting style metadata
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable

from penpress.core.primitives import Stroke


@dataclass(frozen=True, slots=True)
class StyleStats:
    slant_deg: float = 0.0
    x_height_ratio: float = 0.5  # x_height / cap_height
    stroke_curvature_mean: float = 0.0
    letter_spacing_mm: float = 1.0
    word_spacing_mm: float = 3.5
    line_spacing_mm: float = 7.0


@dataclass(frozen=True, slots=True)
class GlyphVariant:
    char: str
    strokes: list[Stroke]  # list of Stroke objects normalized to unit height or mm
    width_mm: float
    height_mm: float


@dataclass(frozen=True, slots=True)
class StyleProfile:
    source_name: str
    stats: StyleStats
    glyph_bank: dict[str, list[GlyphVariant]] = field(default_factory=dict)
    neural_primer_prompt: str | None = None


@dataclass(frozen=True, slots=True)
class SynthesisResult:
    text: str
    strokes: list[Stroke]  # Final physical plotter strokes in mm
    total_length_mm: float
    pen_lifts_count: int
    duration_ms: float
    cer_tesseract: float | None = None
    warnings: list[str] = field(default_factory=list)


@runtime_checkable
class Synthesizer(Protocol):
    """Protocol for handwriting synthesis backends."""

    def synthesize(
        self,
        text: str,
        profile: StyleProfile,
        font_size_mm: float = 6.0,
        start_x_mm: float = 15.0,
        start_y_mm: float = 200.0,
        line_spacing_mm: float = 8.0,
        page_width_mm: float = 148.0,
    ) -> SynthesisResult:
        """Synthesize plottable vector strokes for arbitrary text conditioned on profile."""
        ...
