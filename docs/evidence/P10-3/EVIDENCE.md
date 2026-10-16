# Evidence: P10-3

Implemented-by: worker-release-p103
Date: 2026-10-16

## Commands
```bash
uv run python scripts/package.py --release
./dist/penpress render tests/fixtures/pdfs/mixed_math_assignment.pdf --out /tmp/final_verify
./dist/penpress render /tmp/test_assignment.md --out /tmp/final_verify_md
./dist/penpress --version
uv run python scripts/capture_screenshots.py
make gate
```

## Results
- **Standalone Binary Build (`scripts/package.py --release`)**:
  - Compiles `src/penpress/__main__.py` into single-file executable `dist/penpress` (172,876,760 bytes).
  - Bundles static web assets (`web/`), Hershey glyph databases (`src/penpress/core/data/`), MathJax bridge assets (`research/R2-1/`), and all runtime dependencies (FastAPI, Uvicorn, Multipart, Scipy, OpenCV, ReportLab).
  - Generated release manifest: `release/MANIFEST.md` and `release/checksums.sha256`.

- **Standalone PDF Rendering Verification (`./dist/penpress render`)**:
  - Command: `./dist/penpress render tests/fixtures/pdfs/mixed_math_assignment.pdf --out /tmp/final_verify`
  - Output:
    ```text
    Rendered mixed_math_assignment.pdf (A5) to /tmp/final_verify
    Pages: 2
    Strokes: 814
    Total Pen Lifts: 814
    Draw Distance: 5239.4 mm
    Travel Distance: 3326.7 mm
    Estimated Duration: 859.8s
    Summary JSON: /tmp/final_verify/mixed_math_assignment_summary.json
      Page 1: mixed_math_assignment_p1.gcode, mixed_math_assignment_p1.png, mixed_math_assignment_p1.svg
      Page 2: mixed_math_assignment_p2.gcode, mixed_math_assignment_p2.png, mixed_math_assignment_p2.svg
    ```
  - Exit code: 0. Generated valid Marlin G-code, raster PNG, and vector SVG for both pages.

- **Standalone Markdown + LaTeX Math Rendering Verification**:
  - Input: `/tmp/test_assignment.md` (Harmonic Oscillator with $\frac{d^2x}{dt^2} + 2\gamma \frac{dx}{dt} + \omega_0^2 x = 0$ and $x(t) = A e^{-\gamma t} \cos(\omega_1 t + \phi)$)
  - Output:
    ```text
    Rendered test_assignment.md (A5) to /tmp/final_verify_md
    Pages: 1
    Strokes: 725
    Total Pen Lifts: 725
    Draw Distance: 4069.3 mm
    Travel Distance: 2557.6 mm
    Estimated Duration: 777.4s
    Summary JSON: /tmp/final_verify_md/test_assignment_summary.json
      Page 1: test_assignment.gcode, test_assignment.png, test_assignment.svg
    ```
  - Exit code: 0.

- **Automated Headless Screenshot Capture & 0-Console-Error Verification**:
  - `uv run python scripts/capture_screenshots.py` executed across all 5 views.
  - Result: 0 console errors, 0 page errors, 0 unhandled exceptions.
  - Visually inspected all 5 images via `view_file`:
    - `docs/screenshots/ui/01_document_studio.png`: Dark graphite CAD UI with high-contrast text, 44px top command bar, live telemetry badge (`457 strokes · 8m 08s · 2.51 m ink`), drag-and-drop zone, monospace Markdown editor with LaTeX quick-insert buttons, parsed document block tree, and right paper CAD viewport showing vector handwriting with 7mm ruled notebook lines, 25mm margin line, corner binder-clip keepouts, and true vector MathJax equations. Zero unparsed LaTeX tags, zero empty voids.
    - `docs/screenshots/ui/02_profile_studio.png`: 62-character glyph bank grid (`A–Z`, `a–z`, `0–9`), tactile stylus pad with typographic guide rails, real profile quality metrics (Smoothness: 0.96, Chamfer: 1.88 mm, Baseline Stability: 0.12 mm, Coverage: 100%), organic humanizer parameter sliders, and live synthesized cursive preview canvas ("The quick brown fox jumps over the lazy dog. E = mc²").
    - `docs/screenshots/ui/03_calibration_wizard.png`: 235×235 mm Ender 3 bed CAD canvas with coordinate grid, A5 paper quad, 4 corner binder clip keepouts with 5mm expansion and red hatching, live toolhead crosshair (X: 117.5, Y: 117.5), interactive jog controller (XY/Z, 0.1/1/10mm step sizes), 4-step tactile wizard flow, and calibrated geometry readout table.
    - `docs/screenshots/ui/04_plot_monitor.png`: Kinematic toolpath visualizer with centered bed and paper quad, cyan pen-down strokes, dashed rapid travels, live toolhead crosshair, interactive playback scrubber bar at 45% (`Stroke 562 / 1,248 · 01:30 / 03:18`), 6 tabular telemetry cards, real numbered checksum G-code stream (`N1 M104 S0*...`), and CUPS virtual spool queue. Zero hardcoded sine waves.
    - `docs/screenshots/ui/05_settings_view.png`: Two-column machine & safety configuration cards with unit badges (`mm`, `mm/min`, `baud`), physical envelope parameters, Z-axis spring compression and safety floor protection, serial protocol options, and local-first privacy audit checklist.

- **Checklists Synchronized**:
  - Updated `docs/developer/checklists.md` with proven engineering items checked.

## Acceptance checklist
- `./dist/penpress render tests/fixtures/pdfs/mixed_math_assignment.pdf --out /tmp/final_verify` exits 0 and produces valid G-code and simulator PNG: PASS.
- All 5 screenshots in `docs/screenshots/ui/` show real vector handwriting/math rendering and real toolpaths (verified via `view_file`), with 0 console errors: PASS.
- `uv run python scripts/gate.py` passes 100% (lint, format, mypy, forbid, state, docs, pytest coverage >= 85%): PASS.
- Standalone single-binary packaging succeeds with manifest and checksums: PASS.

## Deviations
- none

## Reviewer notes
- Independently audited and verified by `auditor-p103` on 2026-10-16.
- Standalone single-file binary `./dist/penpress` tested independently on `tests/fixtures/pdfs/mixed_math_assignment.pdf` with `--out /tmp/auditor_verify`:
  - Exit code 0, rendered 2 pages (814 strokes, 5239.4 mm draw, 3326.7 mm travel, 859.8s duration), valid Marlin G-code, PNG, SVG generated.
  - Verified `./dist/penpress --version` reports `penpress 0.1.0`.
- Headless screenshot suite `scripts/capture_screenshots.py` re-run with 0 browser console errors, 0 page errors.
- Visually inspected all 5 images in `docs/screenshots/ui/` via `view_file`:
  - `01_document_studio.png`: Valid dark graphite CAD layout, LaTeX math rendering with vector fractions/roots, 7mm ruled stationery, 25mm margin line, corner keepouts, live telemetry badge.
  - `02_profile_studio.png`: Complete 62-glyph bank, tactile guide rails, live cursive synthesized preview canvas.
  - `03_calibration_wizard.png`: 235x235 Ender 3 bed CAD with A5 sheet quad, 4 binder clip keepouts, toolhead crosshair, jog controls, geometry readout.
  - `04_plot_monitor.png`: Kinematic toolpath visualizer with bed and paper boundaries, cyan pen-down strokes, rapid travels, playback scrubber, telemetry cards, live numbered Marlin checksum stream, CUPS virtual spooler.
  - `05_settings_view.png`: Kinematic parameters, Z-axis spring protection, serial controls, and local-first privacy audit checklist.
  - Verified: Zero empty black voids, zero unparsed LaTeX syntax, zero Bootstrap blue, zero console errors.
- Verified `docs/developer/checklists.md` correctly has proven items ticked and physical hardware execution documented as pending user physical Ender 3 attachment (verified in kinematic simulator per R5-1 protocol).
- Re-ran `make gate`:
  - ruff lint: passed
  - ruff format: passed
  - mypy: clean (55 files)
  - forbid: clean
  - docs_check: ok
  - pytest: 209 passed, 86.27% coverage (>= 85% requirement).
- Verdict: APPROVED. Card P10-3 is complete with no deviations.
