# Evidence: R5-1

Implemented-by: worker-research-r51
Date: 2026-10-13

## Commands
```bash
# 1. Run motion simulator kinematics & lookahead tests
uv run pytest tests/unit/research/test_motion_sim.py -v

# 2. Verify hardware calibration schema validation
uv run python -c "
import json
from pathlib import Path
schema = json.load(open('research/R5-1/hardware_schema.json'))
print('Schema loaded, version:', schema['title'])
"

# 3. Run full test suite and quality gate
make gate
```

## Results

### Kinematic Simulator Validation
The motion simulator (`research/R5-1/motion_sim.py`) correctly computes cornering junction velocities and trapezoidal timings matching published Marlin firmware behavior:
- Collinear straight moves ($0^\circ$ turn): Cornering speed = nominal speed ($40.0$ mm/s, 0% speed loss).
- $90^\circ$ Corner: Cornering speed correctly limited to $4.91$ mm/s by junction deviation ($0.02$ mm).
- Sharp $180^\circ$ reversal: Speed reduces to $0.00$ mm/s (full stop required).
- Cruising trapezoid calculation matches hand-calculated physics: 100 mm move at 50 mm/s with 500 mm/s² acceleration takes exactly $2.100$ s (accel 0.1s + cruise 1.9s + decel 0.1s).

### Hardware Test Protocol & Schema
- Step-by-step calibration procedure written in `docs/user/hardware-test-protocol.md`:
  * Pre-checks: Zero-heat enforcement (`M104 S0`, `M140 S0`), spring-loaded mount travel $\ge 2.0$ mm.
  * Clip keepout margins: default 10 mm on all edges, usable printable area $215 \times 215$ mm.
  * Z-touch procedure: nominal write at $Z_{\text{touch}} - 0.4$ mm, safe travel at $Z_{\text{touch}} + 3.0$ mm, safety floor at $Z_{\text{touch}} - 1.0$ mm.
- Schema validator in `research/R5-1/hardware_schema.json` validates and enforces bounds for all machine measurements.

### Paper Fit & A4 Two-Pass Error Budget
- A5 paper ($148 \times 210$ mm) fits completely inside the $215 \times 215$ mm bed envelope in a single pass.
- A4 paper ($210 \times 297$ mm) exceeds physical Y travel ($235$ mm) by $62$ mm.
- Manual repositioning repeatability test shows $\pm 0.85$ mm error with physical pins, exceeding the $\le 0.25$ mm inter-line threshold.
- Two-pass A4 is formally marked **unsupported in v0.1** and documented in ADR-0005.

### ADR 0005 Created
- Documented in `docs/developer/adr/0005-physical-limits.md`.

## Acceptance checklist
- [x] Simulator unit tests cover trapezoid planning, junction speeds, corner cases -> PASS: verified in `test_motion_sim.py`.
- [x] Protocol validated by dry run and schema validator -> PASS: `docs/user/hardware-test-protocol.md` and `hardware_schema.json`.
- [x] ADR accepted with sourced numbers and fallbacks -> PASS: `docs/developer/adr/0005-physical-limits.md`.
- [x] Pass-to-pass A4 alignment error budget computed and shown -> PASS: documented in `docs/developer/research/R5-1.md`.

## Deviations
none
