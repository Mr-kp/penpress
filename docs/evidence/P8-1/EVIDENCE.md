# Evidence: P8-1

Implemented-by: worker-vision-p81
Date: 2026-10-13

## Commands
```bash
uv run pytest -v tests/unit/vision/test_calibrator.py
GATE_BASE=HEAD COVERAGE_FILE=/tmp/.coverage uv run python scripts/gate.py
```

## Results
- `pytest -v tests/unit/vision/test_calibrator.py`:
  - `test_paper_corner_localization_accuracy_on_topdown_fixture`: PASS (Paper corner localization error on `tests/fixtures/bed_scene_topdown_bright.png` is 0.326 mm, well within the <= 0.50 mm acceptance threshold).
  - `test_clip_keepout_buffer_expansion`: PASS (Detected metallic binder clips along bed frame expanded outward by >= 5.0 mm in physical bed dimensions, ensuring toolpaths never collide with clamps).
  - `test_negative_fixture_zero_false_accept_rate`: PASS (100% rejection rate / 0.0% false accept rate across `negative_glare_corner.png`, `negative_blank_page.png`, `negative_missing_corner.png`, and `negative_paper_out_of_frame.png` with exact failure taxonomy codes).
  - `test_negative_vision_condition_transitions_cleanly_to_manual_wizard`: PASS (Negative conditions like `FRAME_TOO_DARK`, `SEVERE_GLARE_OCCLUSION`, `PAPER_OUT_OF_FRAME` cleanly trigger transition to tactile jog mode without raising uncaught exceptions or error dialogs).
  - `test_manual_jog_wizard_full_execution_flow`: PASS (Interactive 4-step wizard transitions through TL -> TR -> BL corner alignment, parallelogram BR closure, paper-drag resistance check to establish Z contact, write height, and lift clearance).
  - `test_bed_model_transforms_and_keepout_check`: PASS (Validates bilinear paper-to-bed coordinate mapping and ray-casting point-in-keepout hit testing).
- Code coverage:
  - `penpress.vision.bed_model`: 89%
  - `penpress.vision.calibrator`: 94%
  - `penpress.vision.manual_wizard`: 80%
  - Repository-wide test suite: 171 passed, coverage 87.66% (exceeds >= 85% requirement).

## Acceptance checklist
- `pytest tests/unit/vision/test_calibrator.py` passes 100%: PASS (6/6 tests pass).
- Paper corner localization error <= 0.50 mm on `tests/fixtures/bed_scene_topdown_bright.png`: PASS (mean error = 0.326 mm).
- Clip keepout buffer expanded by >= 5.0 mm in physical bed coordinates: PASS (expanded boxes verified >= 30.0 px / 9.4 mm expansion).
- 0.0% false accept rate on negative fixtures (`negative_glare_corner.png`, `negative_blank_page.png`): PASS (0/4 accepted).
- Negative vision conditions (`FRAME_TOO_DARK`, `SEVERE_GLARE_OCCLUSION`) cleanly transition the session to manual jog mode without error dialogs: PASS (validated).

## Deviations
None.

## Reviewer notes
Reviewed-by: director-adversarial-p81
Verdict: PASS. Independent inspection confirmed clean camera-to-bed homography, subpixel corner refinement, expanded obstacle keepout geometries, and full independence of the manual tactile jog wizard.
