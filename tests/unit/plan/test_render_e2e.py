"""Unit and integration tests for P1-5 end-to-end pipeline."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from penpress.plan.profile import MachineProfile
from penpress.plan.render import (
    LayoutOverflowError,
    RenderResult,
    TextRenderer,
    execute_render_pipeline,
)


def levenshtein_distance(s1: str, s2: str) -> int:
    """Compute standard Levenshtein edit distance."""
    if len(s1) < len(s2):
        return levenshtein_distance(s2, s1)
    if len(s2) == 0:
        return len(s1)
    prev = list(range(len(s2) + 1))
    for i, c1 in enumerate(s1):
        curr = [i + 1]
        for j, c2 in enumerate(s2):
            insertions = prev[j + 1] + 1
            deletions = curr[j] + 1
            substitutions = prev[j] + (c1 != c2)
            curr.append(min(insertions, deletions, substitutions))
        prev = curr
    return prev[-1]


def test_e2e_120_word_text_ocr_cer(tmp_path: Path) -> None:
    """Test full 120-word text render to G-code, simulation, and Tesseract OCR round trip with CER <= 8%."""
    fixture_path = Path("tests/fixtures/p1_5_text_120words.txt")
    assert fixture_path.exists(), f"Missing fixture {fixture_path}"

    target_text = fixture_path.read_text(encoding="utf-8").strip()
    words = target_text.split()
    assert len(words) >= 120, f"Expected at least 120 words, got {len(words)}"

    out_dir = tmp_path / "e2e_render"
    result = execute_render_pipeline(
        text_file=fixture_path,
        output_dir=out_dir,
        profile_name="ender3pro",
        ocr_mode=True,
    )

    assert isinstance(result, RenderResult)
    assert result.page_count == 1
    assert result.total_strokes > 1000
    assert result.total_pen_lifts > 1000
    assert result.estimated_duration_s > 0.0
    assert result.gcode_path.exists()
    assert result.sim_image_path.exists()
    assert result.sim_svg_path.exists()

    # Run Tesseract OCR on the simulator's rendered PNG
    ocr_cmd = ["tesseract", str(result.sim_image_path), "stdout", "--psm", "6"]
    proc = subprocess.run(ocr_cmd, capture_output=True, text=True, check=False)
    assert proc.returncode == 0, f"Tesseract failed: {proc.stderr}"

    ocr_output = proc.stdout.strip()

    # Normalize whitespace for comparison
    target_norm = " ".join(words)
    ocr_norm = " ".join(ocr_output.split())

    edit_dist = levenshtein_distance(target_norm, ocr_norm)
    cer = (edit_dist / len(target_norm)) * 100.0

    print(f"P1-5 OCR CER: {cer:.2f}% (edit distance: {edit_dist}, target len: {len(target_norm)})")
    assert cer <= 8.0, f"Character Error Rate {cer:.2f}% exceeded 8.0% threshold"


def test_oversize_text_rejection_and_pagination() -> None:
    """Test oversize text raises LayoutOverflowError without paginate and succeeds with paginate."""
    profile = MachineProfile()
    renderer_no_paginate = TextRenderer(profile, paginate=False)

    # 50 lines of text will definitely exceed a single 235mm bed
    long_lines = [f"This is line number {i} of an oversized document for testing." for i in range(50)]
    long_text = "\n".join(long_lines)

    # 1. Should raise LayoutOverflowError when paginate is False
    with pytest.raises(LayoutOverflowError) as exc_info:
        renderer_no_paginate.layout_text(long_text)
    assert "Text exceeded single page boundary" in str(exc_info.value)

    # 2. Should paginate cleanly into multiple pages when paginate is True
    renderer_paginate = TextRenderer(profile, paginate=True)
    pages = renderer_paginate.layout_text(long_text)
    assert len(pages) > 1, f"Expected multiple pages, got {len(pages)}"


def test_narrow_page_raises_layout_error() -> None:
    """Test that a page width smaller than horizontal margins raises LayoutOverflowError."""
    profile = MachineProfile()
    renderer = TextRenderer(profile, margin_x_mm=50.0)

    with pytest.raises(LayoutOverflowError, match="too narrow for horizontal margin"):
        renderer.layout_text("Hello", page_width_mm=80.0)
