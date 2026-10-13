# Evidence: P1-3

Implemented-by: worker-plan-gcode
Date: 2026-10-13

## Commands
```bash
uv run python scripts/gate.py
uv run pytest tests/unit/plan/test_compiler.py -v -s
```

## Results
- Property testing over randomized pages (Hypothesis):
  - Every coordinate is guaranteed inside the printable bed envelope after offsets.
  - Z coordinate is strictly bounded above the minimum safety floor `z_write_min` (0.10 mm).
  - Rapid XY travel moves (`G0`) are never performed while the pen is in the contact position.
  - Zero heater-on (`M104 S>0`, `M140 S>0`) and fan-on (`M106`) commands are emitted. Heaters (`M104 S0`, `M140 S0`) and fans (`M107`) are disabled in the preamble.
  - The first motion command after program initiation is guaranteed to be a safe Z-lift (`G0 Z...`).
- Negative testing:
  - Compiling content beyond the bed boundary raises explicit `GcodeOutOfBoundsError` when clamping is disabled.
  - Clamping cleanly bounds out-of-range coordinates to the machine's safe margins.
  - Invalid profiles (negative bed dimensions, margins exceeding bed envelope, `z_lift <= z_write`, `z_write < safety floor`) are strictly rejected with `MachineProfileError`.
- Golden G-code reproducibility:
  - 3 fixed test pages (`golden_page1.gcode`, `golden_page2.gcode`, `golden_page3.gcode`) in `tests/golden/gcode/` match byte-for-byte across runs.
- Throughput benchmark:
  - Compiler benchmarked on 25,000 polyline segments in 0.023s:
  - Throughput: **1,088,251 segments/sec** on T0 (vastly exceeding the required >= 20,000 segments/sec threshold).

## Golden Files Excerpt (Page 1)
```gcode
; --- PenPress Marlin G-code Output ---
; Machine: Test Plotter
; Page: 148.0 x 210.0 mm
M104 S0 ; Extruder heater off
M140 S0 ; Bed heater off
M107 ; Fan off
G21 ; Units in millimetres
G90 ; Absolute coordinates
G0 Z3.00 F1200 ; Safe Z lift
G28 ; Home axes
G0 Z3.00 F1200 ; Restore clearance Z
; Total strokes: 1, total segments: 1
G0 X25.000 Y25.000 F6000 ; Move to stroke 1 start
G1 Z0.50 F800 ; Pen down
G1 X65.000 Y25.000 F2400
G0 Z3.00 F1200 ; Pen up
; --- End of Print ---
G0 Z13.00 F1200 ; Final park lift
G0 X10.0 Y210.0 F6000 ; Present paper
M84 ; Disable steppers
```

## Acceptance checklist
- Property tests over random pages: PASS
- Coordinates inside bed after offsets: PASS
- Z never below z_write_min: PASS
- Every pen-down followed by pen-up before travel: PASS
- No heater/fan-on commands emitted: PASS
- First motion command is Z lift: PASS
- Compilation of out-of-bounds content fails unless clamped: PASS
- Invalid profiles rejected: PASS
- Golden G-code tests for 3 fixed pages: PASS
- Compiler throughput >= 20k segments/s: PASS (measured 1,088,251 segments/s)

## Reviewer notes
- Reviewer: director-adversarial-review (2026-10-13)
- Verification on clean tree:
  - All 7 gate steps passed: ruff lint clean, ruff format clean, mypy strict clean (16 source files), forbid scanner clean, state board clean, docs check clean.
  - Pytest: 84 tests passed, total coverage 94.59%, `src/penpress/plan` 88% (meets >= 85% requirement).
  - Zone boundaries verified: only files under `src/penpress/plan/`, `tests/unit/plan/`, `tests/golden/`, `machine-profiles/`, and meta/evidence docs modified.
- Mutation check performed:
  - Mutated `z_write` emission in `GcodeCompiler.compile` to emit `z_write_min - 0.5` -> `test_compiler_hypothesis_safety_properties` caught the hardware floor breach immediately and failed with `AssertionError: Z -0.4 dropped below safety floor 0.1`.
- Throughput verified: 1,088,251 segments/sec on T0 (exceeds >= 20k threshold by >50x).
- CI Matrix verification: GitHub Actions run 38382635756 completed 100% GREEN across Ubuntu, Windows, and macOS runners.
- Verdict: PASS. Approved and ready to mark `done`.

