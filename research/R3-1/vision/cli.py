"""CLI interface for vision calibration and detection (R3-1).

Provides commands:
- detect-paper <image_path>
- detect-clips <image_path>
- calibrate-homography <image_path>
- find-pen-offset <image_path>
- verify-plot <image_path>

Every command emits structured JSON with confidence and failure reason.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import cv2
import numpy as np
from vision.engine import (
    DetectionResult,
    compute_bed_homography,
    detect_clips_and_obstacles,
    detect_paper_quad,
)


def cmd_detect_paper(image_path: Path) -> DetectionResult:
    img = cv2.imread(str(image_path))
    if img is None:
        return DetectionResult(valid=False, confidence=0.0, failure_reason="IMAGE_READ_FAILED")

    quad, conf, reason = detect_paper_quad(img)
    if quad is None:
        return DetectionResult(valid=False, confidence=conf, failure_reason=reason)

    corners = [(float(pt[0]), float(pt[1])) for pt in quad]
    return DetectionResult(valid=True, confidence=conf, paper_corners_px=corners)


def cmd_detect_clips(image_path: Path) -> DetectionResult:
    img = cv2.imread(str(image_path))
    if img is None:
        return DetectionResult(valid=False, confidence=0.0, failure_reason="IMAGE_READ_FAILED")

    quad, conf, _ = detect_paper_quad(img)
    clips = detect_clips_and_obstacles(img, quad)
    return DetectionResult(
        valid=len(clips) > 0,
        confidence=conf if quad is not None else 0.5,
        keepout_polygons_px=clips,
    )


def cmd_calibrate_homography(image_path: Path) -> DetectionResult:
    img = cv2.imread(str(image_path))
    if img is None:
        return DetectionResult(valid=False, confidence=0.0, failure_reason="IMAGE_READ_FAILED")

    quad, conf, reason = detect_paper_quad(img)
    if quad is None:
        return DetectionResult(valid=False, confidence=conf, failure_reason=reason)

    H, h_conf = compute_bed_homography(quad)
    corners_px = [(float(pt[0]), float(pt[1])) for pt in quad]
    # Standard nominal A5 corners in bed space
    corners_bed = [(0.0, 210.0), (148.0, 210.0), (148.0, 0.0), (0.0, 0.0)]

    return DetectionResult(
        valid=True,
        confidence=conf * h_conf,
        paper_corners_px=corners_px,
        paper_corners_bed_mm=corners_bed,
        homography_matrix=H.tolist(),
    )


def cmd_find_pen_offset(image_path: Path) -> DetectionResult:
    """Find pen offset (dx, dy) in mm from a photographed test dot/crosshair."""
    img = cv2.imread(str(image_path))
    if img is None:
        return DetectionResult(valid=False, confidence=0.0, failure_reason="IMAGE_READ_FAILED")

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    # Find smallest dark mark near center of frame
    h, w = gray.shape
    center_roi = gray[int(h * 0.3) : int(h * 0.7), int(w * 0.3) : int(w * 0.7)]
    _min_val, _, min_loc, _ = cv2.minMaxLoc(center_roi)

    # Offset from frame optical center in pixels
    dot_x = int(w * 0.3) + min_loc[0]
    dot_y = int(h * 0.3) + min_loc[1]

    # Convert to nominal physical mm offset (using nominal scale ~ 3.2 px/mm)
    dx_mm = (dot_x - (w / 2.0)) / 3.2
    dy_mm = (dot_y - (h / 2.0)) / 3.2

    return DetectionResult(
        valid=True,
        confidence=0.95,
        pen_offset_mm=(round(dx_mm, 2), round(dy_mm, 2)),
    )


def cmd_verify_plot(image_path: Path) -> DetectionResult:
    """Verify presence of plotted ink lines on paper post-plot."""
    img = cv2.imread(str(image_path))
    if img is None:
        return DetectionResult(valid=False, confidence=0.0, failure_reason="IMAGE_READ_FAILED")

    quad, conf, reason = detect_paper_quad(img)
    if quad is None:
        return DetectionResult(valid=False, confidence=conf, failure_reason=reason)

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    mask = np.zeros(gray.shape, dtype=np.uint8)
    cv2.fillPoly(mask, [quad.astype(np.int32)], 255)

    # Check ink density inside paper
    paper_pixels = gray[mask > 0]
    ink_pixels = np.sum(paper_pixels < 100)
    ink_ratio = ink_pixels / max(1, paper_pixels.size)

    return DetectionResult(
        valid=ink_ratio > 0.005,
        confidence=conf,
        failure_reason="NO_INK_DETECTED" if ink_ratio <= 0.005 else None,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="PenPress Vision Calibration and Detection CLI")
    subparsers = parser.add_subparsers(dest="subcommand", required=True)

    for cmd_name in [
        "detect-paper",
        "detect-clips",
        "calibrate-homography",
        "find-pen-offset",
        "verify-plot",
    ]:
        sub = subparsers.add_parser(cmd_name)
        sub.add_argument("image_path", type=Path, help="Path to image file")

    args = parser.parse_args()

    handlers = {
        "detect-paper": cmd_detect_paper,
        "detect-clips": cmd_detect_clips,
        "calibrate-homography": cmd_calibrate_homography,
        "find-pen-offset": cmd_find_pen_offset,
        "verify-plot": cmd_verify_plot,
    }

    res = handlers[args.subcommand](args.image_path)
    print(res.to_json())


if __name__ == "__main__":
    main()
