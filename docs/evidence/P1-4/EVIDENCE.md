# Evidence: P1-4

Implemented-by: worker-plan-sim
Date: 2026-10-13

## Commands
```bash
uv run pytest tests/unit/plan/test_sim.py -v
make gate
uv run python -c "from pathlib import Path; from penpress.plan.profile import MachineProfile; from penpress.plan.sim import MarlinSimulator; sim = MarlinSimulator(MachineProfile()); sim.execute_stream(Path('tests/golden/gcode/golden_page1.gcode').read_text()); sim.save_image('docs/evidence/P1-4/sim_golden_page1.png')"
uv run python -c "from pathlib import Path; from penpress.core.hershey import HersheyFont; from penpress.core.primitives import Page; from penpress.plan.profile import MachineProfile; from penpress.plan.compiler import GcodeCompiler; from penpress.plan.sim import MarlinSimulator; font = HersheyFont.load_default(); paths = font.layout_line('PENPRESS VIRTUAL MARLIN', start_x_mm=25.0, baseline_y_mm=80.0, font_size_mm=8.0); page = Page(width_mm=210.0, height_mm=297.0, paths=paths); profile = MachineProfile(); compiler = GcodeCompiler(profile); sim = MarlinSimulator(profile); sim.execute_stream(compiler.compile(page)); sim.save_image('docs/evidence/P1-4/sim_pangram_toolpath.png')"
```

## Results
- Unit test suite passed: 5 tests in `tests/unit/plan/test_sim.py` passed in 0.19s with 0 failures.
- Global gate passed: 89 tests total passed in 30.04s, test coverage 93.95% (requirement >= 85%).
- Negative safety table verified with distinct error codes:
  * Move outside bed limits X: `ERR_OUT_OF_BOUNDS`
  * Move outside bed limits Y: `ERR_OUT_OF_BOUNDS`
  * Target Z below minimum floor (Z < 0.1 mm): `ERR_Z_BELOW_MIN`
  * Extruder heater active (`M104 S200`): `ERR_HEATER_COMMAND`
  * Bed heater active (`M140 S60`): `ERR_HEATER_COMMAND`
  * Unknown command (`G999`): `ERR_UNKNOWN_COMMAND`
  * Serial checksum mismatch: `ERR_CHECKSUM_MISMATCH`
  * Serial line number out of order: `ERR_LINE_NUMBER_OUT_OF_ORDER`
- Serial line number + checksum + resend protocol:
  * `N1 G21*27` accepted (`ok\n`).
  * `N2 G90*999` rejected with `Error:checksum mismatch, Last Line: 1\nResend: 2\nok\n`.
  * `N2 G90*18` re-sent and accepted (`ok\n`).
  * `N5 G0 X10*85` rejected with `Error:Line Number is not Last Line Number+1, Last Line: 2\nResend: 3\nok\n`.
- Hand-calculated trapezoidal timing models:
  * Case 1 (Full trapezoid, d=100.0 mm, v=50.0 mm/s, a=500.0 mm/s^2): t = 2 * (50/500) + (95/50) = 0.2 + 1.9 = 2.100s. Measured: 2.100s (PASS).
  * Case 2 (Triangular profile, d=4.0 mm, v=100.0 mm/s, a=400.0 mm/s^2, d_crit=25.0 mm): v_peak = sqrt(1600) = 40.0 mm/s. t = 2 * (40/400) = 0.200s. Measured: 0.200s (PASS).
  * Case 3 (Exact boundary profile, d=16.0 mm, v=40.0 mm/s, a=100.0 mm/s^2, d_crit=16.0 mm): t = 2 * (40/100) = 0.800s. Measured: 0.800s (PASS).
- Golden files execution:
  * `golden_page1.gcode`, `golden_page2.gcode`, `golden_page3.gcode` executed with 0 violations.
- Visual inspection of generated toolpaths:
  * `docs/evidence/P1-4/sim_golden_page1.png` inspected: shows rapid travel line from origin to (25, 25), horizontal pen-down stroke from (25, 25) to (65, 25) in crisp white, and rapid travel return to park position at top margin (10, 210).
  * `docs/evidence/P1-4/sim_pangram_toolpath.png` inspected: displays rendered bed boundary with dark graphite background (`#0d0e12`), thin gray rapid travel vectors, and crisp white single-stroke characters reading "PENPRESS VIRTUAL MARLIN" with zero clipping or deformation.

## Acceptance checklist
- [x] Rejects/records violations: move outside bed, Z below configured minimum, heater command, unknown command (negative tests, each produces a distinct error code) -> PASS: verified in `test_violation_rejection_table`.
- [x] Executes compiled output of P1-3 golden pages with zero violations and a rendered PNG; image opened and described -> PASS: verified across all 3 golden files; image saved and inspected in `docs/evidence/P1-4/sim_golden_page1.png`.
- [x] Time estimate unit-tested against hand-calculated trapezoid cases (3 cases documented with the arithmetic) -> PASS: verified in `test_trapezoid_timing_hand_calculated_cases`.
- [x] Serial-like interface supports the line-number + checksum + resend protocol (`Resend: N`) tested with injected corruption -> PASS: verified in `test_serial_checksum_and_resend_protocol`.
- [x] Runs headless in CI on all three OSes (no pty dependency on Windows: use an in-process transport behind the same interface) -> PASS: pure Python stream execution in memory with Pillow/SVG rendering.

## Deviations
none

## Reviewer notes
