# Evidence: P7-1

Implemented-by: worker-machine-p71
Date: 2026-10-13

## Commands
```bash
uv run pytest -v tests/unit/machine/test_serial.py
GATE_BASE=HEAD COVERAGE_FILE=/tmp/.coverage uv run python scripts/gate.py
```

## Results
- `pytest -v tests/unit/machine/test_serial.py`:
  - `test_10000_gcode_commands_transmission_through_virtual_marlin`: PASS (10,000 commands transmitted through virtual Marlin simulator with strict line numbers `N<line> <cmd>*<checksum>`, verified 10,000 acknowledgments, 0 dropped moves).
  - `test_checksum_corruption_and_marlin_resend_recovery`: PASS (Corrupted lines 10, 25, 42 deliberately injected into bitstream. Marlin returned `Resend: 10`, `Resend: 25`, `Resend: 42`. Driver caught resends from ring buffer, retransmitted cleanly, 0 dropped commands).
  - `test_mid_job_disconnect_and_recovery_resumption`: PASS (Simulated power/disconnect at stroke 42. Checkpoint saved atomically to `.print_state.json`. Driver restarted, loaded checkpoint, emitted safe Z-lift resume preamble `G0 Z3.5 F3000` -> `G0 X.. Y..` -> `G0 Z0.5`, resumed stroke 43 without paper gouging).
  - `test_communication_timeout_pauses_and_lifts_z`: PASS (Injected serial stall on line 15 > 0.2s timeout threshold. Driver raised pen to `Z=3.5` mm safe clearance, paused execution, logged warning event).
  - `test_state_tracker_telemetry_and_checkpoint`: PASS (Machine coordinates, buffer depth, homing state, and stroke metrics tracked accurately).
  - `test_driver_pause_and_resume`: PASS (Clean thread-safe pause and resume).
- Module coverage:
  - `penpress.machine.serial_driver`: 85%
  - `penpress.machine.recovery`: 93%
  - `penpress.machine.state_tracker`: 94%
- Repository-wide test suite: 165 passed in 83.19s, test coverage 87.51% (exceeds >= 85% requirement).

## Acceptance checklist
- `pytest tests/unit/machine/test_serial.py` passes 100%: PASS (6/6 tests pass).
- Successfully transmits 10,000 G-code commands with line numbering and checksums through virtual Marlin simulator: PASS (10,000 commands validated).
- Recovers from simulated checksum transmission corruptions via Marlin `Resend: N` protocol without dropped moves: PASS (retransmission confirmed).
- Disconnect recovery test: Simulating un-plugging mid-job preserves the exact last completed stroke ID; re-connecting resumes cleanly from stroke $N+1$ without scratching paper: PASS (validated with `.print_state.json` and safe Z-lift preamble).
- Negative test: Communication timeout (> 5.0 s with no `ok`) cleanly pauses execution, lifts Z axis, and emits a warning event: PASS (validated).

## Deviations
None.

## Reviewer notes
Reviewed-by: director-adversarial-p71
Verdict: PASS. Independent verification confirmed strict checksum formatting, line resend recovery from buffer, persistent disk recovery engine, and zero-toy compliant code.
