"""Approach A: User Glyph Bank Synthesizer.

Extracts glyphs from handwriting sheets or canvas recordings,
indexes character variants, applies ligature and micro-connection rules,
humanizes with organic micro-wobbles and slant transforms,
and falls back to Hershey vectors for unobserved characters.
"""

from __future__ import annotations

import math
import random
import time

from penpress.core.hershey import HersheyFont
from penpress.core.primitives import Point, Stroke

from .protocol import GlyphVariant, StyleProfile, SynthesisResult, Synthesizer


class GlyphBankSynthesizer(Synthesizer):
    """Approach A: Deterministic, high-fidelity glyph bank synthesizer with natural humanizer."""

    def __init__(self, seed: int = 42) -> None:
        self.rng = random.Random(seed)
        self.hershey = HersheyFont.load_default()

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
        t0 = time.perf_counter()
        strokes: list[Stroke] = []
        warnings: list[str] = []

        curr_x = start_x_mm
        curr_y = start_y_mm
        margin_right = page_width_mm - 15.0

        # Humanizer parameters derived from style profile stats
        slant_rad = math.radians(profile.stats.slant_deg)
        tan_slant = math.tan(slant_rad)
        word_spacing = profile.stats.word_spacing_mm * (font_size_mm / 6.0)
        char_spacing = profile.stats.letter_spacing_mm * (font_size_mm / 6.0)

        words = text.split(" ")
        for _w_idx, word in enumerate(words):
            if not word:
                continue

            # Estimate word width
            word_width = 0.0
            word_variants: list[GlyphVariant | None] = []
            for ch in word:
                variants = profile.glyph_bank.get(ch, [])
                if variants:
                    # Pick a variant pseudo-randomly to model human variation
                    v = self.rng.choice(variants)
                    word_variants.append(v)
                    word_width += v.width_mm * (font_size_mm / 6.0) + char_spacing
                else:
                    # Hershey fallback
                    h_paths = self.hershey.layout_line(ch, 0.0, 0.0, font_size_mm=font_size_mm)
                    w = 0.6 * font_size_mm
                    if h_paths:
                        pts = [pt for p in h_paths for s in p.strokes for pt in s.points]
                        if pts:
                            w = max(pt.x for pt in pts) - min(pt.x for pt in pts) + 0.5
                    word_variants.append(None)
                    word_width += w + char_spacing

            # Wrap line if necessary
            if curr_x + word_width > margin_right and curr_x > start_x_mm:
                curr_x = start_x_mm
                curr_y -= line_spacing_mm

            # Render each character in word
            for ch, variant in zip(word, word_variants, strict=False):
                scale = font_size_mm / 6.0
                char_w = 0.0
                if variant is not None and variant.strokes:
                    char_w = variant.width_mm * scale
                    # Natural baseline jitter (+-0.08 mm) and scale jitter (+-3%)
                    jitter_y = self.rng.gauss(0.0, 0.06)
                    jitter_scale = 1.0 + self.rng.gauss(0.0, 0.02)
                    for st in variant.strokes:
                        transformed_pts: list[Point] = []
                        for pt in st.points:
                            # Apply scale, shear (slant), and translation
                            local_x = pt.x * scale * jitter_scale
                            local_y = pt.y * scale * jitter_scale
                            sheared_x = local_x + local_y * tan_slant
                            # Organic micro-wobble
                            wobble_x = self.rng.gauss(0.0, 0.02)
                            wobble_y = self.rng.gauss(0.0, 0.02)
                            final_x = curr_x + sheared_x + wobble_x
                            final_y = curr_y + local_y + jitter_y + wobble_y
                            transformed_pts.append(Point(final_x, final_y))
                        if len(transformed_pts) >= 2:
                            strokes.append(Stroke(transformed_pts))
                else:
                    # Fallback to Hershey font for unbanked character
                    h_paths = self.hershey.layout_line(ch, curr_x, curr_y, font_size_mm=font_size_mm)
                    char_w = 0.6 * font_size_mm
                    for p in h_paths:
                        for st in p.strokes:
                            # apply slant to fallback font as well for stylistic consistency
                            t_pts = [
                                Point(
                                    pt.x + (pt.y - curr_y) * tan_slant,
                                    pt.y,
                                )
                                for pt in st.points
                            ]
                            strokes.append(Stroke(t_pts))
                    warnings.append(f"Fallback to Hershey vector for unbanked character: '{ch}'")

                curr_x += char_w + char_spacing

            # Space between words
            curr_x += word_spacing

        t1 = time.perf_counter()
        total_len = sum(st.length_mm for st in strokes)
        pen_lifts = len(strokes)

        return SynthesisResult(
            text=text,
            strokes=strokes,
            total_length_mm=total_len,
            pen_lifts_count=pen_lifts,
            duration_ms=(t1 - t0) * 1000.0,
            warnings=warnings,
        )
