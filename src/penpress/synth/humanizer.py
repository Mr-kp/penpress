"""Organic Humanizer Engine for handwriting naturalization.

Transforms rigid digital/Hershey glyphs or user bank strokes into living human handwriting:
- Low-frequency sinusoidal baseline wander across text lines.
- Gaussian micro-jitter on baseline (sigma = 0.06 mm) and character spacing (sigma = 0.15 mm).
- Word-level slant drift and shear transformation (mu = 0, sigma = 2.5 deg).
- Continuous Perlin-style cubic spline micro-wobble along stroke trajectories.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass

from penpress.core.hershey import HersheyFont
from penpress.core.primitives import Point, Stroke
from penpress.profile.models import HandwritingProfile, StyleMetrics
from penpress.synth.variant import VariantBank


@dataclass(frozen=True, slots=True)
class HumanizerParams:
    """Configuration parameters controlling organic handwriting variation.

    Attributes:
        baseline_jitter_sigma_mm: Standard deviation of vertical baseline jitter in mm.
        spacing_jitter_sigma_mm: Standard deviation of horizontal spacing jitter in mm.
        slant_deg_mean: Mean slant angle in degrees.
        slant_deg_sigma: Standard deviation of word-level slant fluctuation in degrees.
        baseline_wander_amplitude_mm: Peak amplitude of sinusoidal wave along line in mm.
        baseline_wander_wavelength_mm: Wavelength of sinusoidal drift in mm.
        wobble_amplitude_mm: Peak amplitude of continuous stroke edge micro-wobble in mm.
        wobble_frequency_mm: Spatial frequency of micro-wobble in cycles/mm.
        scale_jitter_sigma: Multiplicative size variation (sigma = 0.02 -> +-2%).
    """

    baseline_jitter_sigma_mm: float = 0.06
    spacing_jitter_sigma_mm: float = 0.15
    slant_deg_mean: float = 0.0
    slant_deg_sigma: float = 2.5
    baseline_wander_amplitude_mm: float = 0.12
    baseline_wander_wavelength_mm: float = 80.0
    wobble_amplitude_mm: float = 0.025
    wobble_frequency_mm: float = 0.8
    scale_jitter_sigma: float = 0.02

    @classmethod
    def from_style_metrics(cls, metrics: StyleMetrics) -> HumanizerParams:
        return cls(
            baseline_jitter_sigma_mm=metrics.baseline_jitter_mm,
            spacing_jitter_sigma_mm=metrics.spacing_jitter_mm,
            slant_deg_mean=metrics.slant_deg,
        )

    @classmethod
    def zero_jitter(cls) -> HumanizerParams:
        """Zero jitter configuration for strictly deterministic layout testing."""
        return cls(
            baseline_jitter_sigma_mm=0.0,
            spacing_jitter_sigma_mm=0.0,
            slant_deg_mean=0.0,
            slant_deg_sigma=0.0,
            baseline_wander_amplitude_mm=0.0,
            baseline_wander_wavelength_mm=80.0,
            wobble_amplitude_mm=0.0,
            wobble_frequency_mm=0.8,
            scale_jitter_sigma=0.0,
        )


class OrganicHumanizer:
    """Transforms text lines into organic handwriting vector strokes.

    Integrates user glyph bank, anti-repetition variant sampling, Hershey vector fallback,
    and multi-scale human jitter.
    """

    def __init__(
        self,
        profile: HandwritingProfile | None = None,
        params: HumanizerParams | None = None,
        seed: int = 42,
    ) -> None:
        self.rng = random.Random(seed)
        self.hershey = HersheyFont.load_default()

        if profile is not None:
            self.profile = profile
            self.params = (
                params if params is not None else HumanizerParams.from_style_metrics(profile.metrics)
            )
            self.variants = VariantBank(seed=seed)
            for ch, var_list in profile.glyph_bank.items():
                for s_list in var_list:
                    self.variants.add_variant(ch, s_list)
        else:
            self.profile = HandwritingProfile(
                profile_id="default_hershey", user_name="Default", created_at=""
            )
            self.params = params if params is not None else HumanizerParams()
            self.variants = VariantBank(seed=seed)

    def _sample_continuous_wobble(self, x: float, y: float, stroke_t: float) -> tuple[float, float]:
        """Compute smooth Perlin-style micro-wobble offset (dx, dy) in mm."""
        if self.params.wobble_amplitude_mm <= 1e-6:
            return 0.0, 0.0

        # High-order sinusoidal harmonics simulating hand tremor
        w_amp = self.params.wobble_amplitude_mm
        freq = self.params.wobble_frequency_mm * 2.0 * math.pi

        # Combine two non-harmonic spatial frequencies
        dx = w_amp * (0.6 * math.sin(x * freq + stroke_t * 12.0) + 0.4 * math.sin(y * freq * 1.618 + 0.5))
        dy = w_amp * (0.6 * math.cos(y * freq + stroke_t * 12.0) + 0.4 * math.cos(x * freq * 1.618 + 0.8))
        return dx, dy

    def synthesize_line(
        self,
        text: str,
        start_x_mm: float,
        base_y_mm: float,
        font_size_mm: float = 6.0,
    ) -> list[Stroke]:
        """Synthesize vector strokes for a line of text starting at (start_x_mm, base_y_mm)."""
        strokes: list[Stroke] = []
        curr_x = start_x_mm
        char_scale = font_size_mm / 6.0

        words = text.split(" ")
        for w_idx, word in enumerate(words):
            if not word:
                curr_x += 3.0 * char_scale
                continue

            # Word-level slant drift
            word_slant_deg = self.params.slant_deg_mean + (
                self.rng.gauss(0.0, self.params.slant_deg_sigma) if self.params.slant_deg_sigma > 0 else 0.0
            )
            tan_slant = math.tan(math.radians(word_slant_deg))

            for ch in word:
                # Baseline wander (sinusoidal low-frequency wave along page)
                wander_y = 0.0
                if (
                    self.params.baseline_wander_amplitude_mm > 0
                    and self.params.baseline_wander_wavelength_mm > 0
                ):
                    phase = (curr_x / self.params.baseline_wander_wavelength_mm) * 2.0 * math.pi
                    wander_y = self.params.baseline_wander_amplitude_mm * math.sin(phase)

                # High-frequency baseline jitter
                jitter_y = (
                    self.rng.gauss(0.0, self.params.baseline_jitter_sigma_mm)
                    if self.params.baseline_jitter_sigma_mm > 0
                    else 0.0
                )
                effective_y = base_y_mm + wander_y + jitter_y

                # Size variation
                jitter_scale = (
                    1.0 + self.rng.gauss(0.0, self.params.scale_jitter_sigma)
                    if self.params.scale_jitter_sigma > 0
                    else 1.0
                )
                eff_scale = char_scale * jitter_scale

                # Check if character has variants in bank
                variant_strokes = self.variants.select_variant(ch)
                char_w = 0.0

                if variant_strokes is not None:
                    # Transform variant strokes
                    all_pts = [p for s in variant_strokes for p in s.points]
                    min_x = min(p.x for p in all_pts)
                    max_x = max(p.x for p in all_pts)
                    char_w = (max_x - min_x) * eff_scale

                    for s in variant_strokes:
                        t_pts: list[Point] = []
                        total_pts = len(s.points)
                        for p_idx, pt in enumerate(s.points):
                            local_x = (pt.x - min_x) * eff_scale
                            local_y = pt.y * eff_scale
                            sheared_x = local_x + local_y * tan_slant

                            s_time = float(p_idx) / max(1, total_pts - 1)
                            w_x, w_y = self._sample_continuous_wobble(
                                curr_x + sheared_x, effective_y + local_y, s_time
                            )

                            fx = curr_x + sheared_x + w_x
                            fy = effective_y + local_y + w_y
                            t_pts.append(Point(x=fx, y=fy, pressure=pt.pressure, time_offset=pt.time_offset))

                        if len(t_pts) >= 2:
                            strokes.append(Stroke(t_pts))
                else:
                    # Hershey fallback
                    h_scale = (font_size_mm * jitter_scale) / 21.0
                    glyph = self.hershey.get_glyph(ch)
                    char_w = glyph.advance_width_units * h_scale

                    for s in glyph.strokes:
                        t_pts = []
                        total_pts = len(s.points)
                        for p_idx, pt in enumerate(s.points):
                            local_x = pt.x * h_scale
                            local_y = pt.y * h_scale
                            sheared_x = local_x + local_y * tan_slant

                            s_time = float(p_idx) / max(1, total_pts - 1)
                            w_x, w_y = self._sample_continuous_wobble(
                                curr_x + sheared_x, effective_y + local_y, s_time
                            )

                            fx = curr_x + sheared_x + w_x
                            fy = effective_y + local_y + w_y
                            t_pts.append(Point(x=fx, y=fy))
                        if len(t_pts) >= 2:
                            strokes.append(Stroke(t_pts))

                # Advance character spacing with jitter
                spacing_jitter = (
                    self.rng.gauss(0.0, self.params.spacing_jitter_sigma_mm)
                    if self.params.spacing_jitter_sigma_mm > 0
                    else 0.0
                )
                curr_x += char_w + max(0.0, spacing_jitter)

            # Word spacing
            if w_idx < len(words) - 1:
                curr_x += 3.2 * char_scale

        return strokes

    def synthesize_paragraph(
        self,
        paragraph: str,
        start_x_mm: float = 15.0,
        start_y_mm: float = 200.0,
        line_spacing_mm: float = 8.0,
        page_width_mm: float = 148.0,
        font_size_mm: float = 4.0,
    ) -> list[Stroke]:
        """Wrap and synthesize an entire paragraph into multiline strokes."""
        strokes: list[Stroke] = []
        curr_y = start_y_mm
        margin_right = page_width_mm - 15.0

        raw_lines = paragraph.split("\n")
        for raw_line in raw_lines:
            words = raw_line.split(" ")
            curr_line_words: list[str] = []
            curr_line_width = 0.0
            scale = font_size_mm / 6.0

            for w in words:
                w_est = len(w) * (3.0 * scale) + (2.5 * scale)
                if curr_line_width + w_est > (margin_right - start_x_mm) and curr_line_words:
                    # Emit line
                    line_text = " ".join(curr_line_words)
                    strokes.extend(
                        self.synthesize_line(line_text, start_x_mm, curr_y, font_size_mm=font_size_mm)
                    )
                    curr_y -= line_spacing_mm
                    curr_line_words = [w]
                    curr_line_width = w_est
                else:
                    curr_line_words.append(w)
                    curr_line_width += w_est

            if curr_line_words:
                line_text = " ".join(curr_line_words)
                strokes.extend(self.synthesize_line(line_text, start_x_mm, curr_y, font_size_mm=font_size_mm))
                curr_y -= line_spacing_mm

        return strokes
