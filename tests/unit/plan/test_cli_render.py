"""Unit tests for unified CLI render pipeline (P10-1).

Tests:
1. penpress render on multi-page PDF with math and figures.
2. penpress render on Markdown file starting with single-line display math.
3. penpress render on plain text file.
4. Negative tests: missing file, unsupported file extension.
5. penpress with no arguments prints usage help.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from penpress.__main__ import main as cli_main


def test_cli_render_pdf_mixed_math(tmp_path: Path) -> None:
    pdf_path = Path("tests/fixtures/pdfs/mixed_math_assignment.pdf")
    assert pdf_path.is_file(), f"Fixture missing: {pdf_path}"

    out_dir = tmp_path / "pdf_out"
    exit_code = cli_main(["render", str(pdf_path), "--out", str(out_dir), "--paper", "A5"])
    assert exit_code == 0

    summary_file = out_dir / "mixed_math_assignment_summary.json"
    assert summary_file.is_file()

    with summary_file.open("r", encoding="utf-8") as f:
        summary = json.load(f)

    assert summary["page_count"] >= 1
    assert summary["total_strokes"] > 100
    assert summary["total_draw_distance_mm"] > 500.0

    # Verify per-page artifacts
    for art in summary["artifacts"]:
        gcode = Path(art["gcode"])
        png = Path(art["png"])
        svg = Path(art["svg"])
        assert gcode.is_file() and gcode.stat().st_size > 0
        assert png.is_file() and png.stat().st_size > 0
        assert svg.is_file() and svg.stat().st_size > 0


def test_cli_render_markdown_single_line_math(tmp_path: Path) -> None:
    md_file = tmp_path / "assignment.md"
    md_file.write_text(
        "$$\\frac{a}{b} = c$$\n\nCalculate the coefficient when $a=10$ and $b=2$.\n",
        encoding="utf-8",
    )

    out_dir = tmp_path / "md_out"
    exit_code = cli_main(["render", str(md_file), "--out", str(out_dir)])
    assert exit_code == 0

    gcode = out_dir / "assignment.gcode"
    png = out_dir / "assignment.png"
    svg = out_dir / "assignment.svg"
    summary = out_dir / "assignment_summary.json"

    assert gcode.is_file() and gcode.stat().st_size > 0
    assert png.is_file() and png.stat().st_size > 0
    assert svg.is_file() and svg.stat().st_size > 0
    assert summary.is_file()


def test_cli_render_text_file(tmp_path: Path) -> None:
    txt_file = tmp_path / "simple.txt"
    txt_file.write_text("Hello world\nThis is a simple text note.\n", encoding="utf-8")

    out_dir = tmp_path / "txt_out"
    exit_code = cli_main(["render", str(txt_file), "--out", str(out_dir)])
    assert exit_code == 0

    assert (out_dir / "simple.gcode").is_file()
    assert (out_dir / "simple.png").is_file()
    assert (out_dir / "simple.svg").is_file()


def test_cli_render_negative_missing_file(tmp_path: Path) -> None:
    missing_file = tmp_path / "does_not_exist.pdf"
    exit_code = cli_main(["render", str(missing_file), "--out", str(tmp_path / "out")])
    assert exit_code != 0


def test_cli_render_negative_unsupported_extension(tmp_path: Path) -> None:
    bad_file = tmp_path / "binary.unsupported_ext"
    bad_file.write_bytes(b"\x00\x01\x02\x03")
    exit_code = cli_main(["render", str(bad_file), "--out", str(tmp_path / "out")])
    assert exit_code != 0


def test_cli_no_args_prints_help(capsys: pytest.CaptureFixture[str]) -> None:
    exit_code = cli_main([])
    assert exit_code == 2
    assert "usage: penpress" in capsys.readouterr().err
