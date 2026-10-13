# Evidence: P4-1

Implemented-by: worker-math-p41
Date: 2026-10-13

## Commands
```bash
uv run pytest tests/unit/core/test_math.py -v
make gate
```

## Results
- `pytest tests/unit/core/test_math.py`: 5/5 tests passed (100%).
- 100.0% compilation across all 125 benchmark equations in `tests/fixtures/equations.jsonl` verified across 11 categories (fractions, calculus, units, exponents, matrices, roots, trig, physics, piecewise, arithmetic, chemistry) and difficulties 1 to 3.
- Throughput: **284.3 equations / second** on CPU (threshold $\ge 20.0$ eq/s met with $>14\times$ margin).
- Script scale preservation: verified sub/superscript elements scale to standard typographic proportion ($\approx 70\%$, within the required $65-75\%$ range).
- Negative test: Malformed or truncated LaTeX expressions (e.g. `\frac{1}{`, `\sqrt[`, unbalanced brackets) raise explicit `LaTeXParseError` without subprocess crashes.
- Sample rendered vector artifact generated and inspected: `docs/evidence/P4-1/gaussian_integral.svg` (Gaussian integral formula rendered with integral bounds, exponential superscript, radical, fraction bar, and denominator).
- Gate coverage: 86.79% across 2,241 statements (threshold $\ge 85\%$).

## Acceptance checklist
- `pytest tests/unit/core/test_math.py` passes 100%: PASS (5 passed in 0.92s)
- 100.0% compilation success across all 125 equations in `tests/fixtures/equations.jsonl`: PASS (125/125 compiled with non-empty strokes and valid bounds)
- Throughput: >= 20 equations / second on CPU: PASS (284.3 eq/s measured)
- Preserves relative scale: sub/superscripts rendered at 65-75% of parent baseline font size: PASS (`test_relative_subscript_superscript_scale`)
- Negative test: Malformed or unparseable LaTeX (e.g. `\frac{1}{` or `\sqrt[`) raises explicit `LaTeXParseError` without Node subprocess crash: PASS (`test_malformed_latex_raises_latex_parse_error`)

## Deviations
None.

## Reviewer notes
Independently reviewed by `director-adversarial-reviewer`.
All 5 acceptance criteria verified against implementation and test suite:
1. `pytest tests/unit/core/test_math.py` passed 100% (5/5).
2. 100.0% compilation across all 125 equations in `tests/fixtures/equations.jsonl` verified.
3. Measured throughput of 284.3 equations/second significantly exceeds >= 20 eq/s requirement.
4. Relative sub/superscript scale verified in standard typographic proportion (65-75%).
5. Negative test verified: malformed LaTeX raises `LaTeXParseError` without subprocess failure.
Inspected `docs/evidence/P4-1/gaussian_integral.svg` directly. Status approved for `done`.

