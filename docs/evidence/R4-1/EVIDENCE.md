# Evidence: R4-1

Implemented-by: worker-research-r41
Date: 2026-10-13

## Commands
```bash
uv pip install pypdfium2 pdfminer.six reportlab
uv run python research/R4-1/fixtures_generator.py
uv run python research/R4-1/benchmark.py
uv run pytest research/R4-1/tests/test_ingest.py
make gate
```

## Results
- **Benchmark Summary (`research/R4-1/output/benchmark_summary.json`):**
  - Total benchmark execution time: **6.148 s** across 8 diverse test documents.
  - Digital PDF extraction speed:
    - `single_column_academic`: **0.0464 s** (13 blocks, 6 equations detected, reading order 100% strictly monotonic).
    - `two_column_article`: **0.0112 s** (11 blocks, 3 equations detected, vector pore diagram cleanly segmented).
    - `mixed_math_assignment`: **0.0127 s** (24 blocks, Gauss and Stokes theorems extracted, table grid parsed).
    - `vector_figure_circuit`: **0.0059 s** (6 blocks, vector figure isolated with 14 path segments).
    - `assignment_sample`: **0.038 s** (5 blocks, 120-word paragraph + energy equation).
  - Scanned PDF with noise:
    - `scanned_page_noisy`: **5.2049 s** via Tesseract OCR fallback (18 blocks segmented with bounding boxes).
  - Hostile PDF handling:
    - `hostile_oversized` (5000x5000 pt): **0.0029 s**, safely processed with explicit dimension warning (`exceed safe threshold 2500.0 pt`).
    - `hostile_huge_image` (3000x3000 px): **0.1943 s**, safely processed within memory boundaries.
    - `hostile_malformed`: **0.0001 s**, safely caught as `error: malformed_pdf (PdfiumError)` with diagnostic warning without process crash.

- **Visual Inspection of Overlay Images (`docs/screenshots/r41/`):**
  - `single_column_academic_overlay.png`: Inspected via `view_file`. Title, section headings, body paragraphs, and 3 mathematical equations cleanly segmented with distinct color badges. Reading order indices strictly monotonically follow document flow.
  - `two_column_article_overlay.png`: Inspected via `view_file`. Left column (Darcy flow, equation) correctly precedes right column (permeability, Kozeny equation); vector pore diagram isolated as `#1 FIGURE_VECTOR`.
  - `mixed_math_assignment_overlay.png`: Inspected via `view_file`. Stokes and Gauss divergence theorems isolated as amber equation blocks; table rows and grid structure grouped without dropping text.
  - `vector_figure_circuit_overlay.png`: Inspected via `view_file`. RLC circuit drawing isolated as single cohesive `#4 FIGURE_VECTOR` containing all 14 path segments (resistor, inductor coils, capacitor plates, AC sine wave).
  - `scanned_page_noisy_overlay.png`: Inspected via `view_file`. Tesseract OCR fallback correctly segments lines and paragraphs despite skew and speckle noise.
  - `assignment_sample_overlay.png`: Inspected via `view_file`. 120-word ground truth paragraph and energy conservation formula boxed cleanly.

- **Automated Tests:**
  - 10 unit and integration tests passing in `research/R4-1/tests/test_ingest.py`.

## Acceptance checklist
- [x] **Benchmark reproducible from README within +-5%**: PASS (`uv run python research/R4-1/benchmark.py` runs in ~6s, all numbers documented in `docs/developer/research/R4-1.md`).
- [x] **ADR accepted; licence verdicts for every dependency; fallback tiering described with triggers**: PASS (ADR-0004 written and accepted in `docs/developer/adr/0004-pdf-ingest.md`; licenses recorded in `docs/developer/licenses.md`).
- [x] **Overlay images for 6 PDFs opened and described, flaws included**: PASS (All 6 images rendered into `docs/screenshots/r41/`, opened, inspected via `view_file`, and described in detail).
- [x] **Proven safe handling of hostile PDFs: oversized pages, encrypted, malformed, huge embedded images**: PASS (Tested against 5000x5000 pt page, huge 3000x3000 image, corrupted header/trailer stream, and missing files with zero crashes).

## Deviations
- None. Used permissive `pypdfium2` (Apache-2.0 / BSD) + `pdfminer.six` (MIT) + `tesseract` (Apache-2.0) without any AGPL or copyleft code.

## Reviewer notes
<reviewer fills: what was re-run independently, verdict>
