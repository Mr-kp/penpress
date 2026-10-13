"""Quality assessment and completeness scoring for handwriting profiles.

Audits glyph coverage across standard character sets (uppercase, lowercase, digits, punctuation),
computes stroke smoothness, detects degenerate scribbles/dots, and gates profiles against
minimum quality thresholds before use in document synthesis.
"""

from __future__ import annotations

import math
import string
from dataclasses import dataclass, field
from typing import Any

from penpress.core.primitives import Stroke
from penpress.profile.models import HandwritingProfile

# Standard reference character sets
ASCII_UPPERCASE = tuple(string.ascii_uppercase)
ASCII_LOWERCASE = tuple(string.ascii_lowercase)
ASCII_DIGITS = tuple(string.digits)
ASCII_PUNCTUATION = tuple(".,!?:;\"'-()[]/+=_@#$%&*")
STANDARD_ALPHANUMERIC = ASCII_UPPERCASE + ASCII_LOWERCASE + ASCII_DIGITS


class QualityThresholdError(ValueError):
    """Raised when a handwriting profile or glyph fails minimum quality criteria."""


@dataclass(frozen=True, slots=True)
class GlyphQualityScore:
    """Quality metrics for a single glyph or character entry.

    Attributes:
        char: The character represented.
        variant_count: Number of distinct stroke variations available.
        stroke_count: Average number of strokes per variant.
        total_length_mm: Average arc length in mm.
        smoothness_score: Average stroke smoothness in range [0.0, 1.0] (1.0 = optimal smooth).
        is_valid: Whether the glyph passes minimum geometric validity.
        failure_reasons: Tuple of failure reason descriptions, if any.
    """

    char: str
    variant_count: int
    stroke_count: float
    total_length_mm: float
    smoothness_score: float
    is_valid: bool
    failure_reasons: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ProfileQualityReport:
    """Comprehensive quality evaluation report for a HandwritingProfile.

    Attributes:
        profile_id: Identifier of the evaluated profile.
        total_unique_glyphs: Total unique characters present.
        total_variants: Total variants across all characters.
        alphanumeric_completeness: Percentage of standard A-Z, a-z, 0-9 present [0.0, 100.0].
        punctuation_completeness: Percentage of common punctuation present [0.0, 100.0].
        overall_completeness: Overall completeness percentage [0.0, 100.0].
        mean_smoothness: Average smoothness score across all glyphs [0.0, 1.0].
        missing_alphanumeric: Sorted list of missing alphanumeric characters.
        invalid_glyphs: Tuple of characters that failed quality standards.
        passed: Whether the profile satisfies required deployment criteria.
    """

    profile_id: str
    total_unique_glyphs: int
    total_variants: int
    alphanumeric_completeness: float
    punctuation_completeness: float
    overall_completeness: float
    mean_smoothness: float
    missing_alphanumeric: tuple[str, ...] = field(default_factory=tuple)
    invalid_glyphs: tuple[str, ...] = field(default_factory=tuple)
    passed: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "profile_id": self.profile_id,
            "total_unique_glyphs": self.total_unique_glyphs,
            "total_variants": self.total_variants,
            "alphanumeric_completeness": round(self.alphanumeric_completeness, 2),
            "punctuation_completeness": round(self.punctuation_completeness, 2),
            "overall_completeness": round(self.overall_completeness, 2),
            "mean_smoothness": round(self.mean_smoothness, 4),
            "missing_alphanumeric_count": len(self.missing_alphanumeric),
            "missing_alphanumeric": list(self.missing_alphanumeric),
            "invalid_glyphs": list(self.invalid_glyphs),
            "passed": self.passed,
        }


def compute_stroke_smoothness(stroke: Stroke) -> float:
    """Compute normalized curvature smoothness for a stroke in range [0.0, 1.0].

    Smooth strokes with gradual turning angles score close to 1.0, while erratic
    high-frequency zig-zags score close to 0.0.
    """
    pts = stroke.points
    if len(pts) <= 2:
        return 1.0

    angles: list[float] = []
    for i in range(1, len(pts) - 1):
        p_prev = pts[i - 1]
        p_curr = pts[i]
        p_next = pts[i + 1]

        v1_x = p_curr.x - p_prev.x
        v1_y = p_curr.y - p_prev.y
        v2_x = p_next.x - p_curr.x
        v2_y = p_next.y - p_curr.y

        norm1 = math.hypot(v1_x, v1_y)
        norm2 = math.hypot(v2_x, v2_y)

        if norm1 < 1e-6 or norm2 < 1e-6:
            continue

        dot = (v1_x * v2_x + v1_y * v2_y) / (norm1 * norm2)
        dot = max(-1.0, min(1.0, dot))
        turning_rad = math.acos(dot)
        angles.append(turning_rad)

    if not angles:
        return 1.0

    mean_turning = sum(angles) / len(angles)
    # Map turning angle: 0 rad -> 1.0 smoothness; pi rad -> 0.0 smoothness
    score = max(0.0, min(1.0, 1.0 - (mean_turning / math.pi)))
    return score


def evaluate_glyph_quality(
    char: str,
    variants: list[list[Stroke]],
    min_length_mm: float = 0.5,
    min_aspect_or_extent_mm: float = 0.3,
) -> GlyphQualityScore:
    """Evaluate quality of a specific character's variants in a profile.

    Rejects empty, single-dot, or degenerate microscopic scribbles.
    """
    if not variants:
        return GlyphQualityScore(
            char=char,
            variant_count=0,
            stroke_count=0.0,
            total_length_mm=0.0,
            smoothness_score=0.0,
            is_valid=False,
            failure_reasons=("No variants provided",),
        )

    failures: list[str] = []
    stroke_counts: list[int] = []
    lengths: list[float] = []
    smoothnesses: list[float] = []

    for v_idx, strokes in enumerate(variants):
        if not strokes:
            failures.append(f"Variant {v_idx} has 0 strokes")
            continue

        stroke_counts.append(len(strokes))
        v_len = sum(s.length_mm for s in strokes)
        lengths.append(v_len)

        # Check total length
        # For dot '.' punctuation, allow shorter minimum
        eff_min_len = 0.15 if char in ".,:;·" else min_length_mm
        if v_len < eff_min_len:
            failures.append(
                f"Variant {v_idx} length {v_len:.3f} mm is below threshold {eff_min_len} mm (dot/scribble)"
            )

        # Check bounding box extent
        all_pts = [p for s in strokes for p in s.points]
        min_x = min(p.x for p in all_pts)
        max_x = max(p.x for p in all_pts)
        min_y = min(p.y for p in all_pts)
        max_y = max(p.y for p in all_pts)
        w = max_x - min_x
        h = max_y - min_y

        eff_extent = 0.1 if char in ".,:;·" else min_aspect_or_extent_mm
        if max(w, h) < eff_extent:
            failures.append(f"Variant {v_idx} extent ({w:.3f}x{h:.3f} mm) is degenerate")

        # Smoothness
        for s in strokes:
            smoothnesses.append(compute_stroke_smoothness(s))

    mean_strokes = sum(stroke_counts) / len(stroke_counts) if stroke_counts else 0.0
    mean_length = sum(lengths) / len(lengths) if lengths else 0.0
    mean_smooth = sum(smoothnesses) / len(smoothnesses) if smoothnesses else 0.0
    is_valid = len(failures) == 0

    return GlyphQualityScore(
        char=char,
        variant_count=len(variants),
        stroke_count=mean_strokes,
        total_length_mm=mean_length,
        smoothness_score=mean_smooth,
        is_valid=is_valid,
        failure_reasons=tuple(failures),
    )


def audit_profile_quality(
    profile: HandwritingProfile,
    min_alphanumeric_completeness: float = 90.0,
    min_mean_smoothness: float = 0.60,
    strict_raise: bool = False,
) -> ProfileQualityReport:
    """Audit the complete handwriting profile and compute coverage and quality metrics.

    Args:
        profile: The HandwritingProfile to audit.
        min_alphanumeric_completeness: Minimum percentage of A-Z, a-z, 0-9 required.
        min_mean_smoothness: Minimum average smoothness threshold.
        strict_raise: If True, raises QualityThresholdError when audit fails.

    Returns:
        ProfileQualityReport summarizing completeness, smoothness, and valid status.
    """
    bank = profile.glyph_bank

    # Check alphanumeric completeness
    present_alnum = [c for c in STANDARD_ALPHANUMERIC if c in bank and len(bank[c]) > 0]
    missing_alnum = tuple(c for c in STANDARD_ALPHANUMERIC if c not in bank or len(bank[c]) == 0)
    alnum_pct = (len(present_alnum) / len(STANDARD_ALPHANUMERIC)) * 100.0

    # Check punctuation completeness
    present_punct = [c for c in ASCII_PUNCTUATION if c in bank and len(bank[c]) > 0]
    punct_pct = (len(present_punct) / len(ASCII_PUNCTUATION)) * 100.0 if ASCII_PUNCTUATION else 100.0

    # Evaluate individual glyphs
    glyph_scores: dict[str, GlyphQualityScore] = {}
    invalid_chars: list[str] = []
    smoothness_vals: list[float] = []

    for char, variants in bank.items():
        score = evaluate_glyph_quality(char, variants)
        glyph_scores[char] = score
        if not score.is_valid:
            invalid_chars.append(char)
        else:
            smoothness_vals.append(score.smoothness_score)

    mean_smooth = (sum(smoothness_vals) / len(smoothness_vals)) if smoothness_vals else 0.0

    total_variants = sum(len(v) for v in bank.values())
    total_standard = len(STANDARD_ALPHANUMERIC) + len(ASCII_PUNCTUATION)
    overall_pct = ((len(present_alnum) + len(present_punct)) / total_standard) * 100.0

    passed = (
        alnum_pct >= min_alphanumeric_completeness
        and mean_smooth >= min_mean_smoothness
        and len(invalid_chars) == 0
    )

    report = ProfileQualityReport(
        profile_id=profile.profile_id,
        total_unique_glyphs=len(bank),
        total_variants=total_variants,
        alphanumeric_completeness=alnum_pct,
        punctuation_completeness=punct_pct,
        overall_completeness=overall_pct,
        mean_smoothness=mean_smooth,
        missing_alphanumeric=missing_alnum,
        invalid_glyphs=tuple(sorted(invalid_chars)),
        passed=passed,
    )

    if strict_raise and not passed:
        reasons: list[str] = []
        if alnum_pct < min_alphanumeric_completeness:
            reasons.append(
                f"Alphanumeric completeness {alnum_pct:.1f}% below {min_alphanumeric_completeness:.1f}% min"
            )
        if mean_smooth < min_mean_smoothness:
            reasons.append(f"Mean smoothness {mean_smooth:.3f} below minimum {min_mean_smoothness:.3f}")
        if invalid_chars:
            reasons.append(f"Invalid degenerate glyphs: {', '.join(invalid_chars)}")
        msg = f"Profile {profile.profile_id} failed quality gating: {'; '.join(reasons)}"
        raise QualityThresholdError(msg)

    return report
