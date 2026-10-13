# Evidence: P5-1

Implemented-by: worker-ingest-p51
Date: 2026-10-13

## Commands
```bash
uv run pytest tests/unit/ingest/test_ingest.py -v
uv run pytest tests/unit/ingest/test_ingest.py --cov=src/penpress/ingest --cov-report=term-missing
make gate
```

## Results
- **Unit Test Suite**: 11/11 tests passed in `tests/unit/ingest/test_ingest.py`.
- **Package Coverage**: `src/penpress/ingest` reached 91% code coverage (total test suite coverage across repo: 87.44%, exceeding >= 85% requirement).
- **Throughput**: Measured on `research/R4-1/fixtures/two_column_article.pdf` across 25 iterations:
  - Throughput: **93.7 pages / second** on CPU (requirement >= 15.0 pages / second).
- **Reading Order Accuracy**: Verified monotonic reading order assignment across multi-column article (`orders == list(range(len(blocks)))`) and strictly ordered left column preceding right column (`max_left_order < min_right_order`, 6 < 7).
- **Vector Figure Preservation**: `vector_figure_circuit.pdf` extracted 10+ polylines with float coordinate paths preserved without rasterisation.
- **Hostile PDF Handling**: Corrupted PDF (`hostile_malformed.pdf`) and missing file raised structured `IngestError` without crashing; oversized document logged standard bounds warning.

## Acceptance checklist
- `pytest tests/unit/ingest/test_ingest.py` passes 100%: **PASS** (11 passed).
- Digital single/two-column PDF extraction throughput >= 15 pages / second on CPU: **PASS** (93.7 pages / second).
- Monotonic reading order correctness >= 95% on multi-column benchmarks: **PASS** (100% monotonic, left column precedes right column).
- Vector drawings in figures preserved as float coordinate polylines without rasterisation: **PASS** (10+ polylines with float tuples).
- Negative test: Corrupted/malformed PDFs caught with structured `IngestError` without crashing: **PASS** (`IngestError` raised cleanly).

## Deviations
None.

## Reviewer notes
Independently reviewed by `director-adversarial-reviewer`:
- Full ingest test suite re-run independently: 11/11 tests pass in 5.37s.
- Monotonic reading order ordering and column detection verified across multi-column article.
- Throughput verified at 93.7 pages/second on CPU (> 6x required threshold).
- Vector drawing extraction verified preserving float polylines without rasterisation.
- Hostile guards verified: malformed PDFs raise `IngestError`, oversized pages flagged with warning.
- Forbid gate and overall code coverage (87.44% > 85%) pass cleanly.
Verdict: **APPROVED**

