"""Tests for Hershey single-stroke fallback font loader and line layout."""

from __future__ import annotations

import hashlib
import subprocess
from importlib import resources
from pathlib import Path

import pytest
from PIL import Image, ImageDraw

from penpress.core import (
    EXPECTED_HERSHEY_SHA256,
    CoreGeometryError,
    HersheyFont,
    MissingGlyphError,
)
from penpress.core.hershey import HERSHEY_DATA_FILENAME


def test_hershey_data_file_checksum() -> None:
    data_res = resources.files("penpress.core.data").joinpath(HERSHEY_DATA_FILENAME)
    data_bytes = data_res.read_bytes().replace(b"\r\n", b"\n")
    computed_sha256 = hashlib.sha256(data_bytes).hexdigest()
    assert computed_sha256 == EXPECTED_HERSHEY_SHA256, (
        f"Checksum mismatch: {computed_sha256} != {EXPECTED_HERSHEY_SHA256}"
    )


def test_hershey_ascii_and_greek_coverage() -> None:
    font = HersheyFont.load_default()

    # 1. Printable ASCII (32..126)
    ascii_chars = [chr(c) for c in range(32, 127)]
    cov_ascii, missing_ascii = font.check_coverage(ascii_chars)
    assert cov_ascii == 100.0, f"Missing ASCII glyphs: {missing_ascii}"

    # 2. Greek alphabet (both uppercase and lowercase)
    greek_chars = [
        "Α",
        "Β",
        "Γ",
        "Δ",
        "Ε",
        "Ζ",
        "Η",
        "Θ",
        "Ι",
        "Κ",
        "Λ",
        "Μ",
        "Ν",
        "Ξ",
        "Ο",
        "Π",
        "Ρ",
        "Σ",
        "Τ",
        "Υ",
        "Φ",
        "Χ",
        "Ψ",
        "Ω",
        "α",
        "β",
        "γ",
        "δ",
        "ε",
        "ζ",
        "η",
        "θ",
        "ι",
        "κ",
        "λ",
        "μ",
        "ν",
        "ξ",
        "ο",
        "π",
        "ρ",
        "σ",
        "τ",
        "υ",
        "φ",
        "χ",
        "ψ",
        "ω",
    ]
    cov_greek, missing_greek = font.check_coverage(greek_chars)
    assert cov_greek == 100.0, f"Missing Greek glyphs: {missing_greek}"

    # 3. Listed Math symbols
    math_symbols = [
        "+",
        "-",
        "=",
        "<",
        ">",
        "<=",
        ">=",
        "!=",
        "approx",
        "times",
        "div",
        "partial",
        "nabla",
        "infty",
        "sum",
        "prod",
        "int",
        "sqrt",
        "->",
        "<-",
        "<->",
        "uparrow",
        "downarrow",
        "⁰",
        "¹",
        "²",
        "³",
        "⁴",
        "⁵",
        "⁶",
        "⁷",
        "⁸",
        "⁹",
        "₀",
        "₁",
        "₂",
        "₃",
        "₄",
        "₅",
        "₆",
        "₇",
        "₈",
        "₉",
    ]
    cov_math, missing_math = font.check_coverage(math_symbols)
    assert cov_math == 100.0, f"Missing Math glyphs: {missing_math}"


def test_missing_glyph_raises_error() -> None:
    font = HersheyFont.load_default()
    with pytest.raises(MissingGlyphError, match="MissingGlyph: Character '€'"):
        font.get_glyph("€")


def test_layout_line_invalid_font_size() -> None:
    font = HersheyFont.load_default()
    with pytest.raises(CoreGeometryError, match="font_size_mm must be positive"):
        font.layout_line("test", font_size_mm=-1.0)


def test_tesseract_ocr_rendering_pangram(tmp_path: Path) -> None:
    font = HersheyFont.load_default()
    test_text = "The quick brown fox jumps over the lazy dog 0123456789"
    paths = font.layout_line(test_text, start_x_mm=10.0, baseline_y_mm=25.0, font_size_mm=8.0)
    assert len(paths) == len([c for c in test_text if c != " "])

    # Render to raster image scaled to canvas
    scale_px_per_mm = 8.0
    img_width = int(400 * scale_px_per_mm)
    img_height = int(50 * scale_px_per_mm)
    img = Image.new("L", (img_width, img_height), color=255)
    draw = ImageDraw.Draw(img)

    for path in paths:
        for stroke in path.strokes:
            pts_px = [(p.x * scale_px_per_mm, img_height - p.y * scale_px_per_mm) for p in stroke.points]
            if len(pts_px) >= 2:
                draw.line(pts_px, fill=0, width=4)

    out_png = tmp_path / "hershey_pangram.png"
    img.save(out_png)
    assert out_png.is_file()
    assert out_png.stat().st_size > 0

    # Also save evidence copy in docs/evidence/P1-2/hershey_pangram.png if writable
    try:
        evidence_dir = Path("docs/evidence/P1-2")
        evidence_dir.mkdir(parents=True, exist_ok=True)
        evidence_png = evidence_dir / "hershey_pangram.png"
        img.save(evidence_png)
    except OSError:
        pass

    # Run Tesseract OCR
    res = subprocess.run(
        ["tesseract", str(out_png), "stdout", "--psm", "7"],
        capture_output=True,
        text=True,
        check=False,
    )
    ocr_result = res.stdout.strip()

    # Levenshtein distance calculation for CER
    def levenshtein(s1: str, s2: str) -> int:
        if len(s1) < len(s2):
            return levenshtein(s2, s1)
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

    edit_dist = levenshtein(test_text, ocr_result)
    cer = (edit_dist / len(test_text)) * 100.0

    print(f"Pangram OCR Result: '{ocr_result}'")
    print(f"Target:             '{test_text}'")
    print(f"Edit Distance: {edit_dist}, CER: {cer:.2f}%")

    assert cer <= 5.0, f"Character Error Rate {cer:.2f}% exceeds threshold of 5.0%"
