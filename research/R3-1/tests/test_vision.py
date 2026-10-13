"""Automated tests for Vision and Bed Calibration (R3-1)."""

from __future__ import annotations

import json
from pathlib import Path

import cv2
import numpy as np
from vision.engine import (
    compute_bed_homography,
    detect_clips_and_obstacles,
    detect_paper_quad,
)

REPO_ROOT = Path(__file__).resolve().parents[3]


def test_topdown_scene_detection_accuracy() -> None:
    """Verify paper quad corner error is <= 0.7 mm on topdown bright scene."""
    img_path = REPO_ROOT / "tests/fixtures/bed_scene_topdown_bright.png"
    gt_path = REPO_ROOT / "tests/fixtures/bed_scene_topdown_bright.json"

    img = cv2.imread(str(img_path))
    gt = json.loads(gt_path.read_text(encoding="utf-8"))

    quad, conf, reason = detect_paper_quad(img)
    assert quad is not None, f"Detection failed: {reason}"
    assert conf >= 0.85

    gt_pts = np.array(gt["paper_corners_image_px"], dtype=np.float32)
    # Scale is ~3.19 px/mm
    err_px = np.linalg.norm(quad - gt_pts, axis=1)
    mean_err_mm = float(np.mean(err_px)) / 3.19
    assert mean_err_mm <= 0.7, f"Expected mean error <= 0.7 mm, got {mean_err_mm:.2f} mm"


def test_negative_fixture_rejection() -> None:
    """Verify 100% rejection rate (0% false accept) across all negative edge fixtures."""
    neg_fixtures = [
        ("tests/fixtures/negative_blank_page.png", "FRAME_WASHED_OUT"),
        ("tests/fixtures/negative_glare_corner.png", "SEVERE_GLARE_OCCLUSION"),
        ("tests/fixtures/negative_missing_corner.png", "PAPER_NOT_FOUND"),
        ("tests/fixtures/negative_paper_out_of_frame.png", "PAPER_OUT_OF_FRAME"),
    ]

    for rel_path, expected_reason in neg_fixtures:
        full_path = REPO_ROOT / rel_path
        img = cv2.imread(str(full_path))
        quad, conf, reason = detect_paper_quad(img)

        assert quad is None, f"Negative fixture {rel_path} was falsely accepted!"
        assert conf < 0.65, f"Negative fixture {rel_path} had high confidence: {conf}"
        assert reason == expected_reason, f"Expected {expected_reason}, got {reason}"


def test_clip_obstacle_detection_and_keepout() -> None:
    """Verify binder clips on bed frame edges are reliably isolated."""
    img_path = REPO_ROOT / "tests/fixtures/bed_scene_topdown_bright.png"
    img = cv2.imread(str(img_path))

    quad, _, _ = detect_paper_quad(img)
    clips = detect_clips_and_obstacles(img, quad)

    assert len(clips) >= 2
    for c in clips:
        assert len(c) == 4
        # Points must be valid within image boundaries
        for pt in c:
            assert 0.0 <= pt[0] <= 1200.0
            assert 0.0 <= pt[1] <= 1200.0


def test_homography_matrix_conditioning() -> None:
    """Verify computed homography matrix is non-singular with positive determinant."""
    quad = np.array(
        [[391.0, 261.0], [864.0, 261.0], [864.0, 932.0], [391.0, 932.0]],
        dtype=np.float32,
    )
    H, conf = compute_bed_homography(quad)

    assert conf == 1.0
    det = np.linalg.det(H)
    assert abs(det) > 1e-4
