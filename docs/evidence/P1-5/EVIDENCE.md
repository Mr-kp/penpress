# Evidence: P1-5

Implemented-by: worker-plan-e2e
Date: 2026-10-13

## Commands
```bash
uv run penpress render-text tests/fixtures/p1_5_text_120words.txt --profile ender3pro --out out/p1_5_test/ --ocr-mode
uv run pytest tests/unit/plan/test_render_e2e.py -v
tesseract docs/evidence/P1-5/sim_e2e_120words_ocr.png stdout --psm 6
make gate
```

## Results
- CLI invocation transcript:
  ```text
  Rendered p1_5_text_120words.txt to out/p1_5_test
  Pages: 1
  Strokes: 1262
  Total Pen Lifts: 1262
  Estimated Time: 1271.0s
  G-code: out/p1_5_test/p1_5_text_120words.gcode
  Simulator Image: out/p1_5_test/p1_5_text_120words.png
  Simulator SVG: out/p1_5_test/p1_5_text_120words.svg
  ```
- Word count: 121 words input text (`tests/fixtures/p1_5_text_120words.txt`).
- Simulator reports: 0 violations, 1,262 strokes, 1,262 pen lifts, estimated time 1,271.0s.
- Tesseract OCR round-trip verification on simulated G-code render:
  * Normalized input length: 868 characters.
  * Normalized OCR length: 868 characters.
  * Levenshtein edit distance: 1 (single character difference in em-dash hyphen rendering).
  * Character Error Rate (CER): **0.12%** (Threshold required: $\le 8.0\%$).
- Negative test & oversize handling:
  * Oversized text raises explicit `LayoutOverflowError`: `"Text exceeded single page boundary (reached Y=... mm < ... mm). Enable paginate=True to flow into multi-page document."`
  * When `paginate=True` is provided, document cleanly divides into multiple sequential pages.
  * Verified in `test_oversize_text_rejection_and_pagination`.
- Visual Artifacts Inspected:
  * `docs/evidence/P1-5/sim_e2e_120words_ocr.png`: High-contrast black glyphs on pure white background, perfectly legible, zero clipping, aligned margins.
  * `docs/evidence/P1-5/sim_e2e_120words_dark.png`: Linear/macOS dark graphite background (`#0d0e12`), subtle gray rapid travel vectors, crisp white single-stroke text.

## OCR Output vs Input Diff
```text
--- Input Text (868 chars normalized)
+++ OCR Output (868 chars normalized)
@@ -1,7 +1,7 @@
 PenPress is an autonomous system built to print academic
 assignments, notes, and technical reports in natural
 handwriting using an Ender 3 Pro pen plotter. The software
 translates digital text or equations into continuous vector
 strokes with single line fonts. Our compiler schedules rapid
 travel moves with positive vertical clearance, eliminates all
 hotend and heatbed commands, and outputs standard dialect
-G-code for Marlin firmware. Before any physical motor moves,
+G—code for Marlin firmware. Before any physical motor moves,
 the virtual simulator executes the trajectory step by step,
 tracking machine coordinates, enforcing bed boundaries, and
 calculating trapezoidal velocity profiles. Finally, an optical
 recognition model reads the simulated toolpath render to verify
 that every single sentence is crisp, legible, and authentic. This
 closed loop pipeline guarantees reliable output on paper without
 human intervention.
```

## Acceptance checklist
- [x] CLI command exists and is documented in README with real output -> PASS: `penpress render-text` documented and verified.
- [x] Input: a 120-word text. OCR round-trip CER <= 8% on the simulator's rendered PNG -> PASS: 121 words, CER = 0.12% (edit distance 1 out of 868 chars).
- [x] Simulator reports 0 violations; total pen lifts and estimated time printed -> PASS: 0 violations, 1,262 pen lifts, 1,271.0s time.
- [x] A deliberately oversize text returns a clear error or paginates (documented choice, tested) -> PASS: `LayoutOverflowError` on single-page, multi-page when `--paginate` enabled.
- [x] CI runs this e2e on all three OSes (Tesseract install step added in CI) -> PASS: verified across Ubuntu, macOS, and Windows matrix.

## Deviations
none

## Reviewer notes
