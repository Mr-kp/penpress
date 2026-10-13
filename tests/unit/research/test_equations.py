"""Unit tests for R2-1 equation handwriting synthesis engine."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from eqengine.engine import EquationEngine

from penpress.core.primitives import BoundingBox


@pytest.fixture(scope="module")
def engine() -> EquationEngine:
    return EquationEngine()


def test_equation_engine_basic_arithmetic(engine: EquationEngine) -> None:
    res = engine.render_equation_to_strokes("2 + 3 = 5")
    assert res.latex == "2 + 3 = 5"
    assert len(res.strokes) > 0
    assert res.symbol_count == 5  # 2, +, 3, =, 5
    assert res.rule_count == 0
    assert res.fallback_count == 0
    assert isinstance(res.bounds, BoundingBox)
    assert res.bounds.min_x < res.bounds.max_x
    assert res.bounds.min_y < res.bounds.max_y


def test_equation_engine_fraction_structure(engine: EquationEngine) -> None:
    res = engine.render_equation_to_strokes(r"\frac{a}{b}")
    assert res.symbol_count == 2  # a, b
    assert res.rule_count == 1  # fraction bar
    assert res.fallback_count == 0
    # Numerator must be above fraction bar, denominator below
    all_pts = [p for s in res.strokes for p in s.points]
    assert len(all_pts) >= 4


def test_equation_engine_quadratic_formula(engine: EquationEngine) -> None:
    res = engine.render_equation_to_strokes(r"x = \frac{-b \pm \sqrt{b^2 - 4ac}}{2a}")
    assert res.symbol_count >= 10
    assert res.rule_count >= 2  # fraction bar + radical roof
    assert res.fallback_count == 0
    assert len(res.strokes) >= 15


def test_equation_engine_matrix_and_piecewise(engine: EquationEngine) -> None:
    res = engine.render_equation_to_strokes(r"\begin{pmatrix} 1 & 0 \\ 0 & 1 \end{pmatrix}")
    assert res.symbol_count >= 4
    cases_latex = r"|x| = \begin{cases} x & x \ge 0 \\ -x & x < 0 \end{cases}"
    res_cases = engine.render_equation_to_strokes(cases_latex)
    assert res_cases.symbol_count >= 10
    assert res_cases.fallback_count == 0


def test_all_corpus_equations_render_successfully(engine: EquationEngine) -> None:
    eq_file = Path("tests/fixtures/equations.jsonl")
    assert eq_file.exists()

    with open(eq_file, encoding="utf-8") as f:
        equations = [json.loads(line) for line in f if line.strip()]

    assert len(equations) >= 120

    success_count = 0
    for eq in equations:
        res = engine.render_equation_to_strokes(eq["latex"])
        assert len(res.strokes) > 0
        assert res.symbol_count > 0
        assert res.fallback_count == 0
        success_count += 1

    assert success_count == len(equations)
