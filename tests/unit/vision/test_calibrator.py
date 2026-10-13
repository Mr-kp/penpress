"""Unit tests for dual-mode calibration wizard, camera homography, and manual jog (P8-1).

Tests:
1. Paper corner localization accuracy <= 0.50 mm on topdown bright fixture.
2. Clip keepout buffer expanded by >= 5.0 mm in physical bed coordinates.
3. 0.0% false accept rate on negative fixtures (glare, washed out, missing corner, out of frame).
4. Negative vision conditions transition cleanly to manual jog mode without error dialogs.
5. Manual jog wizard state machine complete 4-step execution and PaperBedPlacement generation.
6. Bed coordinate model transforms and point-in-keepout hit testing.
"""

from __future__ import annotations

import json
from pathlib import Path

import cv2
import numpy as np
import pytest

from penpress.core.primitives import Point
from penpress.vision.bed_model import PaperBedPlacement
from penpress.vision.calibrator import (
    CameraCalibrator,
    detect_clips_and_expand_keepout,
    detect_paper_quadrilateral,
)
from penpress.vision.manual_wizard import ManualJogWizard, WizardStep

REPO_ROOT = Path(__file__).resolve().parents[3]


def test_paper_corner_localization_accuracy_on_topdown_fixture() -> None:
    img_path = REPO_ROOT / "tests/fixtures/bed_scene_topdown_bright.png"
    gt_path = REPO_ROOT / "tests/fixtures/bed_scene_topdown_bright.json"

    assert img_path.exists()
    assert gt_path.exists()

    img = cv2.imread(str(img_path))
    assert img is not None
    gt = json.loads(gt_path.read_text(encoding="utf-8"))

    calibrator = CameraCalibrator()
    res = calibrator.calibrate(img)

    assert res.valid is True
    assert res.confidence >= 0.85
    assert res.placement is not None

    gt_pts = np.array(gt["paper_corners_image_px"], dtype=np.float32)
    det_pts = np.array(res.paper_corners_px, dtype=np.float32)

    scale_px_per_mm = float(np.linalg.norm(gt_pts[1] - gt_pts[0])) / 148.0
    err_px = np.linalg.norm(det_pts - gt_pts, axis=1)
    err_mm = err_px / scale_px_per_mm
    mean_err_mm = float(np.mean(err_mm))

    # Acceptance requirement: <= 0.50 mm
    assert mean_err_mm <= 0.50, f"Expected mean corner error <= 0.50 mm, got {mean_err_mm:.3f} mm"


def test_clip_keepout_buffer_expansion() -> None:
    img_path = REPO_ROOT / "tests/fixtures/bed_scene_topdown_bright.png"
    img = cv2.imread(str(img_path))
    assert img is not None

    quad, _, _ = detect_paper_quadrilateral(img)
    assert quad is not None

    raw_clips, exp_clips = detect_clips_and_expand_keepout(
        image=img,
        paper_quad_px=quad,
        buffer_mm=5.0,
        px_per_mm=3.19,
    )

    assert len(raw_clips) >= 2
    assert len(exp_clips) == len(raw_clips)

    # Verify each expanded clip is strictly larger than the raw clip by at least 5 mm buffer (15.95 px)
    for raw, exp in zip(raw_clips, exp_clips, strict=False):
        raw_box = np.array(raw)
        exp_box = np.array(exp)

        raw_rect = cv2.minAreaRect(raw_box.astype(np.float32))
        exp_rect = cv2.minAreaRect(exp_box.astype(np.float32))

        (raw_w, raw_h) = raw_rect[1]
        (exp_w, exp_h) = exp_rect[1]

        # Both width and height are expanded by 2 * buffer_px = 31.9 px
        diff_w = max(exp_w, exp_h) - max(raw_w, raw_h)
        diff_h = min(exp_w, exp_h) - min(raw_w, raw_h)

        assert diff_w >= 30.0, f"Expected width expansion >= 30.0 px (2*5mm), got {diff_w:.1f}"
        assert diff_h >= 30.0, f"Expected height expansion >= 30.0 px (2*5mm), got {diff_h:.1f}"


def test_negative_fixture_zero_false_accept_rate() -> None:
    neg_fixtures = [
        ("tests/fixtures/negative_blank_page.png", "FRAME_WASHED_OUT"),
        ("tests/fixtures/negative_glare_corner.png", "SEVERE_GLARE_OCCLUSION"),
        ("tests/fixtures/negative_missing_corner.png", "PAPER_NOT_FOUND"),
        ("tests/fixtures/negative_paper_out_of_frame.png", "PAPER_OUT_OF_FRAME"),
    ]

    calibrator = CameraCalibrator()

    for rel_path, expected_reason in neg_fixtures:
        full_path = REPO_ROOT / rel_path
        img = cv2.imread(str(full_path))
        assert img is not None
        res = calibrator.calibrate(img)

        # Strict 0.0% false accept rate
        assert res.valid is False, f"Negative fixture {rel_path} was falsely accepted!"
        assert res.placement is None
        assert res.confidence < 0.65
        assert res.failure_reason == expected_reason


def test_negative_vision_condition_transitions_cleanly_to_manual_wizard() -> None:
    wizard = ManualJogWizard()
    assert wizard.current_step == WizardStep.INITIAL

    # Test seamless transition from failure conditions without raising exceptions
    failure_reasons = ["FRAME_TOO_DARK", "SEVERE_GLARE_OCCLUSION", "PAPER_OUT_OF_FRAME"]
    for reason in failure_reasons:
        wiz = ManualJogWizard()
        prompt = wiz.transition_from_failed_camera(reason)
        assert wiz.current_step == WizardStep.JOG_CORNER_1_TL
        assert "manual tactile jog alignment" in prompt
        assert len(wiz.history_log) == 1


def test_manual_jog_wizard_full_execution_flow() -> None:
    wizard = ManualJogWizard()

    # Step 1: Start and record TL
    prompt1 = wizard.start()
    assert str(wizard.current_step) == str(WizardStep.JOG_CORNER_1_TL)
    assert "Step 1/4" in prompt1

    # Record TL: (43.5, 222.5) mm
    prompt2 = wizard.record_corner_1_tl(43.5, 222.5)
    assert str(wizard.current_step) == str(WizardStep.JOG_CORNER_2_TR)
    assert "Step 2/4" in prompt2
    assert wizard.p_tl == Point(43.5, 222.5)

    # Record TR: (191.5, 222.5) mm
    prompt3 = wizard.record_corner_2_tr(191.5, 222.5)
    assert str(wizard.current_step) == str(WizardStep.JOG_CORNER_3_BL)
    assert "Step 3/4" in prompt3
    assert wizard.p_tr == Point(191.5, 222.5)

    # Record BL: (43.5, 12.5) mm
    prompt4 = wizard.record_corner_3_bl(43.5, 12.5)
    assert str(wizard.current_step) == str(WizardStep.Z_TOUCH_PAPER_DRAG)
    assert "Step 4/4" in prompt4
    assert wizard.p_bl == Point(43.5, 12.5)
    # Check parallelogram computed BR: (191.5, 12.5)
    assert wizard.p_br == Point(191.5, 12.5)

    # Record Z touch: 0.85 mm
    prompt5 = wizard.record_z_touch_paper_drag(0.85)
    assert str(wizard.current_step) == str(WizardStep.COMPLETED)
    assert "Manual calibration complete!" in prompt5
    assert wizard.z_touch_mm == 0.85
    assert wizard.z_write_mm == 0.45  # 0.85 - 0.4
    assert wizard.z_lift_mm == 3.85  # 0.85 + 3.0

    placement = wizard.get_placement()
    assert placement.source_mode == "manual"
    assert placement.confidence == 1.0
    assert placement.width_mm == pytest.approx(148.0, abs=0.1)
    assert placement.height_mm == pytest.approx(210.0, abs=0.1)


def test_bed_model_transforms_and_keepout_check() -> None:
    placement = PaperBedPlacement(
        corners_bed_mm=(
            Point(43.5, 222.5),  # TL
            Point(191.5, 222.5),  # TR
            Point(191.5, 12.5),  # BR
            Point(43.5, 12.5),  # BL
        ),
        source_mode="manual",
        confidence=1.0,
        keepout_polygons_mm=((Point(10.0, 10.0), Point(30.0, 10.0), Point(30.0, 30.0), Point(10.0, 30.0)),),
    )

    # Check center paper coordinate (74, 105) maps to bed center (117.5, 117.5)
    p_center = placement.paper_to_bed_point(Point(74.0, 105.0))
    assert p_center.x == pytest.approx(117.5, abs=0.1)
    assert p_center.y == pytest.approx(117.5, abs=0.1)

    # Check keepout detection
    assert placement.is_point_in_keepout(Point(20.0, 20.0)) is True
    assert placement.is_point_in_keepout(Point(117.5, 117.5)) is False
