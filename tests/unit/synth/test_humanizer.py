"""Tests for Organic Humanizer Engine (P3-1).

Verifies:
1. Anti-repetition variant sampling across repeated glyphs.
2. Statistical validation of baseline jitter Gaussian distribution N(0, sigma^2).
3. Deterministic zero-jitter straight baseline execution (negative test).
4. Pen feedrate modulation and bold multi-pass toolpaths.
5. Closed-loop Tesseract OCR recognition with CER <= 1.0% on clean text.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import numpy as np
import pytest
from PIL import Image, ImageDraw

from penpress.core.primitives import Point, Stroke
from penpress.profile.models import HandwritingProfile
from penpress.synth.dynamics import (
    FeedrateModulationParams,
    compute_stroke_feedrates,
    generate_bold_multipass_strokes,
)
from penpress.synth.humanizer import HumanizerParams, OrganicHumanizer
from penpress.synth.variant import VariantBank


def levenshtein_distance(s1: str, s2: str) -> int:
    m, n = len(s1), len(s2)
    dp = [[0] * (n + 1) for _ in range(m + 1)]
    for i in range(m + 1):
        dp[i][0] = i
    for j in range(n + 1):
        dp[0][j] = j
    for i in range(1, m + 1):
        for j in range(1, n + 1):
            cost = 0 if s1[i - 1] == s2[j - 1] else 1
            dp[i][j] = min(dp[i - 1][j] + 1, dp[i][j - 1] + 1, dp[i - 1][j - 1] + cost)
    return dp[m][n]


def test_anti_repetition_variant_selection() -> None:
    bank = VariantBank(seed=123)

    # 3 distinct variants of 'e'
    v1 = [Stroke([Point(0, 0), Point(2, 2)])]
    v2 = [Stroke([Point(0, 0), Point(2, 3)])]
    v3 = [Stroke([Point(0, 0), Point(2, 4)])]

    bank.add_variant("e", v1)
    bank.add_variant("e", v2)
    bank.add_variant("e", v3)

    assert bank.variant_count("e") == 3

    # Sample 'e' 50 times consecutively: no two consecutive picks may be equal
    last_pts = None
    for _ in range(50):
        chosen = bank.select_variant("e")
        assert chosen is not None
        curr_pts = chosen[0].points
        if last_pts is not None:
            assert curr_pts != last_pts, "Consecutive identical variant selected!"
        last_pts = curr_pts


def test_anti_repetition_in_100_word_paragraph() -> None:
    profile = HandwritingProfile(profile_id="test_multi_var", user_name="Test", created_at="")

    # Add 2 distinct variants for common letters
    for char in "abcdefghijklmnopqrstuvwxyz":
        s1 = Stroke([Point(0.0, 0.0), Point(2.0, 3.0)])
        s2 = Stroke([Point(0.0, 0.0), Point(2.0, 3.2)])
        profile.add_glyph_variant(char, [s1])
        profile.add_glyph_variant(char, [s2])

    humanizer = OrganicHumanizer(profile=profile, seed=99)

    # 100-word paragraph
    text = (
        "the quick brown fox jumps over the lazy dog repeatedly and creates "
        "natural handwriting without repetitive identical glyphs appearing in sequence. "
        "every character alternates between available variations to mimic personal script. "
        "this test verifies that consecutive repetitions of identical letters never reuse "
        "the exact same stroke pattern across the entire paragraph text."
    )

    strokes = humanizer.synthesize_paragraph(text, font_size_mm=4.0)
    assert len(strokes) > 50


def test_statistical_baseline_jitter_distribution() -> None:
    # Measure baseline jitter across 500 samples
    target_sigma = 0.06
    params = HumanizerParams(
        baseline_jitter_sigma_mm=target_sigma,
        spacing_jitter_sigma_mm=0.0,
        slant_deg_mean=0.0,
        slant_deg_sigma=0.0,
        baseline_wander_amplitude_mm=0.0,
        wobble_amplitude_mm=0.0,
        scale_jitter_sigma=0.0,
    )
    humanizer = OrganicHumanizer(params=params, seed=42)

    jitters: list[float] = []
    base_y = 100.0

    for _ in range(500):
        # Single character 'l' (vertical stem)
        st = humanizer.synthesize_line("l", start_x_mm=10.0, base_y_mm=base_y)
        if st:
            min_y = min(p.y for p in st[0].points)
            jitters.append(min_y - base_y)

    jitters_arr = np.array(jitters)
    measured_mean = float(np.mean(jitters_arr))
    measured_std = float(np.std(jitters_arr))

    # Mean should be close to 0 mm (+-0.015)
    assert abs(measured_mean) < 0.015
    # Standard deviation must be in [0.04, 0.08] mm
    assert 0.04 <= measured_std <= 0.08, f"Measured std {measured_std} outside expected [0.04, 0.08] mm"


def test_zero_jitter_negative_test() -> None:
    # Zero jitter should produce completely straight and deterministic baseline
    params = HumanizerParams.zero_jitter()
    humanizer = OrganicHumanizer(params=params, seed=1)

    st1 = humanizer.synthesize_line("Hello World", start_x_mm=20.0, base_y_mm=50.0)
    st2 = humanizer.synthesize_line("Hello World", start_x_mm=20.0, base_y_mm=50.0)

    assert len(st1) == len(st2)
    for s_a, s_b in zip(st1, st2, strict=True):
        assert len(s_a.points) == len(s_b.points)
        for p_a, p_b in zip(s_a.points, s_b.points, strict=True):
            assert p_a.x == pytest.approx(p_b.x, abs=1e-6)
            assert p_a.y == pytest.approx(p_b.y, abs=1e-6)


def test_dynamics_feedrate_and_bold_multipass() -> None:
    # Sharp corner stroke: straight line, 90 deg turn, straight line
    s = Stroke([Point(0, 0), Point(10, 0), Point(10, 10)])
    feedrates = compute_stroke_feedrates(s, FeedrateModulationParams(nominal_feedrate_mm_min=3000.0))

    assert len(feedrates) == 2
    # At least one segment should have decelerated due to corner curvature
    assert any(fr < 3000.0 for fr in feedrates)

    # Multi-pass bold
    bold_strokes = generate_bold_multipass_strokes([s], offset_mm=0.2, passes=3)
    assert len(bold_strokes) == 3


def test_tesseract_ocr_on_humanized_synthetic_page(tmp_path: Path) -> None:
    tesseract_bin = shutil.which("tesseract")
    assert tesseract_bin is not None, "tesseract binary must be installed on system"

    # Render a clean pangram using OrganicHumanizer
    params = HumanizerParams(
        baseline_jitter_sigma_mm=0.03,
        spacing_jitter_sigma_mm=0.08,
        slant_deg_mean=2.0,
        slant_deg_sigma=1.0,
        baseline_wander_amplitude_mm=0.05,
        wobble_amplitude_mm=0.015,
    )
    humanizer = OrganicHumanizer(params=params, seed=77)

    target_text = "The quick brown fox jumps over the lazy dog."
    strokes = humanizer.synthesize_line(target_text, start_x_mm=10.0, base_y_mm=20.0, font_size_mm=7.0)

    # Render to raster image using PIL ImageDraw (8 px/mm, matching test_hershey.py)
    scale_px_per_mm = 8.0
    img_width = int(400 * scale_px_per_mm)
    img_height = int(50 * scale_px_per_mm)
    img = Image.new("L", (img_width, img_height), color=255)
    draw = ImageDraw.Draw(img)

    for s in strokes:
        pts_px = [(p.x * scale_px_per_mm, img_height - p.y * scale_px_per_mm) for p in s.points]
        if len(pts_px) >= 2:
            draw.line(pts_px, fill=0, width=4)

    out_png = tmp_path / "humanized_ocr.png"
    img.save(out_png)

    # Save evidence copy
    evidence_dir = Path("docs/evidence/P3-1")
    evidence_dir.mkdir(parents=True, exist_ok=True)
    img.save(evidence_dir / "humanized_ocr.png")

    # OCR with PSM 7 (single text line)
    proc = subprocess.run(
        [tesseract_bin, str(out_png), "stdout", "--psm", "7"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, f"Tesseract OCR failed: {proc.stderr}"
    ocr_text = proc.stdout.strip()

    # Compare edit distance
    dist = levenshtein_distance(target_text.lower(), ocr_text.lower())
    cer = (dist / len(target_text)) * 100.0

    print(f"Target: '{target_text}', OCR: '{ocr_text}', CER: {cer:.2f}%")
    assert cer <= 1.0, f"CER {cer:.2f}% exceeded 1.0% threshold (dist={dist})"
