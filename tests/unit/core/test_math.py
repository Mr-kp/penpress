"""Unit tests for Mathematical Formula Handwriting Layout Engine (P4-1).

Tests:
1. 100.0% compilation across all 125 benchmark equations in `tests/fixtures/equations.jsonl`.
2. Throughput benchmark >= 20 equations/second.
3. Sub/superscript relative scale verification (65-75% of parent baseline font size).
4. Negative test: Malformed or unparseable LaTeX raises explicit LaTeXParseError without crash.
5. Stretchy brackets and wobbly rules verification.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import pytest

from penpress.core.math_engine import LaTeXParseError, MathEngine, MathRenderResult
from penpress.core.math_symbols import generate_stretchy_bracket


@pytest.fixture
def math_engine() -> MathEngine:
    return MathEngine()


def test_stretchy_brackets() -> None:
    for b_type in ("(", ")", "[", "]", "{", "}", "|"):
        strokes = generate_stretchy_bracket(b_type, x=10.0, y_bottom=5.0, height_mm=12.0)
        assert len(strokes) >= 1
        assert all(len(s.points) >= 2 for s in strokes)


def test_malformed_latex_raises_latex_parse_error(math_engine: MathEngine) -> None:
    malformed_inputs = [
        r"\frac{1}{",
        r"\sqrt[",
        r"\int_{0}^{",
        r"{unclosed",
        r"unclosed]",
    ]
    for bad in malformed_inputs:
        with pytest.raises(LaTeXParseError):
            math_engine.render_equation_to_strokes(bad)


def test_relative_subscript_superscript_scale(math_engine: MathEngine) -> None:
    # Expression with clear superscript and subscript
    eq = r"E = mc^2 + x_i"
    res = math_engine.render_equation_to_strokes(eq, target_height_mm=10.0)

    assert isinstance(res, MathRenderResult)
    assert len(res.strokes) > 0
    # Relative script scale must fall into standard typographic sub/superscript range (65-75%)
    assert 0.65 <= res.relative_script_scale <= 0.75, (
        f"Relative script scale {res.relative_script_scale:.3f} outside expected 65-75% range"
    )


def test_all_125_fixture_equations_compilation_and_throughput(math_engine: MathEngine) -> None:
    fixture_path = Path("tests/fixtures/equations.jsonl")
    assert fixture_path.exists(), f"Fixture file not found: {fixture_path}"

    with fixture_path.open("r", encoding="utf-8") as f:
        items = [json.loads(line) for line in f if line.strip()]

    assert len(items) == 125, f"Expected 125 equations, got {len(items)}"

    # Benchmark batch layout + stroke compilation
    latex_strings = [item["latex"] for item in items]

    t0 = time.perf_counter()
    batch_layout = math_engine.layout_latex_batch(latex_strings)
    assert len(batch_layout) == 125

    results: list[MathRenderResult] = []
    for item, layout in zip(items, batch_layout, strict=True):
        res = math_engine.render_equation_to_strokes(
            item["latex"],
            layout_data=layout,
        )
        assert len(res.strokes) > 0, f"No strokes generated for equation {item['id']}: {item['latex']}"
        assert res.bounds.width > 0.0
        assert res.bounds.height > 0.0
        results.append(res)

    elapsed = time.perf_counter() - t0
    throughput = len(items) / elapsed

    print(f"\nP4-1 Math Compilation: 125/125 passed in {elapsed:.3f}s ({throughput:.1f} eq/s)")

    # Acceptance requirement: 100.0% success across all 125 equations
    assert len(results) == 125
    # Acceptance requirement: Throughput >= 20 equations/second
    assert throughput >= 20.0, f"Throughput {throughput:.1f} eq/s is below required 20.0 eq/s"


def test_matrix_and_fraction_structures(math_engine: MathEngine) -> None:
    matrix_eq = r"\begin{pmatrix} a & b \\ c & d \end{pmatrix}"
    res = math_engine.render_equation_to_strokes(matrix_eq)
    assert res.symbol_count >= 4
    assert len(res.strokes) >= 4
    assert res.bounds.width > 5.0
