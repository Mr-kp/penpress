# Evidence: P0-1

Implemented-by: antigravity-orchestrator
Date: 2026-10-13

## Commands
```
uv sync --python 3.12
uv run ruff check . ; uv run ruff format . ; uv run mypy
uv run pytest -q --cov=src/penpress --cov-fail-under=85
uv run penpress --version
```

## Results
- ruff: All checks passed. mypy --strict: no issues in 9 source files.
- pytest: 33 passed; coverage of src/penpress 88.24% (required 85%).
- The gate genuinely failed first on 17 lint errors and one failing test (mock regex), both fixed; this shows the gate has teeth.
- Not yet verified: clean-clone run on a second machine (done by CI in P0-3).

## Acceptance checklist
- gate passes locally: PASS (see P0-3 for CI)
- `penpress --version`: PASS (unit tested)
- briefing/state/journal/evidence-new make targets: PASS (state, journal, evidence-new were used to create these files)

## Deviations
Cards P0-2/P0-3 have no dependency on P0-1 (bootstrap exception) so the board is valid before anything is `done`.

## Reviewer notes

## Local CI run (2026-10-13)
Clean clone (`git clone . .ci-local`), `uv sync --python 3.12`, `GATE_BASE=HEAD~1 uv run python scripts/gate.py`: all 7 steps passed, 33 tests, coverage 88.24%, `penpress --version` printed `penpress 0.0.1`. Linux only: macOS and Windows jobs have not run (GitHub billing block).
