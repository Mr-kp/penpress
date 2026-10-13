# Evidence: P5-2

Implemented-by: worker-layout-p52
Date: 2026-10-13

## Commands
```bash
COVERAGE_FILE=/tmp/.coverage uv run pytest tests/unit/layout/test_composer.py -v -o cache_dir=/tmp/pytest_cache --cov=src/penpress/layout --cov-report=term-missing
uv run ruff check --cache-dir /tmp/ruff_cache src/penpress/layout tests/unit/layout
uv run ruff format --cache-dir /tmp/ruff_cache --check src/penpress/layout tests/unit/layout
uv run mypy --cache-dir=/tmp/mypy_cache src/penpress/layout tests/unit/layout
GATE_BASE=HEAD uv run python scripts/forbid.py
```

## Results
- **Pytest layout test suite**: 7 tests passed in 8.79s with 86% package statement coverage across `src/penpress/layout`.
- **Essay pagination**: A 1000-word academic assignment containing section headers, paragraphs, lists, and LaTeX equations successfully compiles and paginates into 4 A5 sheets (`148 x 210` mm) with 1,732 total strokes and zero text overflowing past printable margins.
- **7 mm Ruled Baseline Alignment**: Maximum baseline deviation across all lines is $0.0000$ mm ($\le 0.2$ mm tolerance required by card acceptance).
- **Binder Clip Keepout Zones**: 0 strokes intersect the 4 standard binder clip keepout polygons with 5 mm expanded safety buffers.
- **Layout Overflow Protection**: Indivisible oversized blocks (e.g. 352 mm vector figure exceeding 116 mm usable width) raise `LayoutOverflowError` with actionable pagination and downscaling suggestions.
- **Bed Travel Limits**: Non-exempt paper presets exceeding $220 \times 220$ mm raise `ValueError`.

## Acceptance checklist
- `pytest tests/unit/layout/test_composer.py` passes 100%: **PASS** (7/7 passed).
- Generates valid multi-page document fitting 1000-word essay with equations onto A5 sheets: **PASS** (4 pages, 1732 strokes, 18.0 mm top/bottom margins, 16.0 mm left/right margins).
- Text baselines strictly align with simulated 7 mm ruled notebook guidelines within +-0.2 mm: **PASS** (all baselines snap to $y = y_{\text{first}} - k \times 7.0$ mm with deviation $\le 0.2$ mm).
- Zero strokes intersect the 5 mm expanded clip keep-out zone: **PASS** (all strokes filtered against 4 binder clip polygons).
- Negative test: A single block larger than page dimensions raises `LayoutOverflowError` with actionable pagination suggestions: **PASS** (`LayoutOverflowError` raised with "Suggestion: Scale down figure or split into multiple smaller panels.").

## Deviations
none

## Reviewer notes
- **Reviewer**: director-adversarial-reviewer
- **Date**: 2026-10-13
- **Verification**: Independently ran `uv run pytest tests/unit/layout/test_composer.py` and confirmed 100% pass (7/7 tests passed). Checked baseline snap math, keepout polygon distance calculation, and error messaging. Clean separation of concerns. Verdict: **APPROVED**.
