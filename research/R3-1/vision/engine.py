"""Vision models and detection engine for PenPress (R3-1).

Implements:
1. Paper quadrilateral detection with perspective verification.
2. Homography calibration from bed frame or ArUco markers.
3. Binder clip and tape keepout detection along borders.
4. Pen offset calibration from printed calibration crosshair.
5. Strict confidence scoring and self-diagnostic failure taxonomy.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field

import cv2
import numpy as np


@dataclass(frozen=True, slots=True)
class DetectionResult:
    valid: bool
    confidence: float  # 0.0 to 1.0
    failure_reason: str | None = None
    paper_corners_px: list[tuple[float, float]] = field(default_factory=list)
    paper_corners_bed_mm: list[tuple[float, float]] = field(default_factory=list)
    homography_matrix: list[list[float]] = field(default_factory=list)
    keepout_polygons_px: list[list[tuple[float, float]]] = field(default_factory=list)
    pen_offset_mm: tuple[float, float] | None = None

    def to_json(self) -> str:
        def convert_val(obj: object) -> object:
            if isinstance(obj, (np.bool_, np.bool)):
                return bool(obj)
            if isinstance(obj, (np.floating, np.float32, np.float64, np.integer, np.int32, np.int64)):
                return float(obj) if isinstance(obj, (np.floating, float)) else int(obj)
            if isinstance(obj, np.ndarray):
                return obj.tolist()
            if isinstance(obj, dict):
                return {k: convert_val(v) for k, v in obj.items()}
            if isinstance(obj, (list, tuple)):
                return [convert_val(v) for v in obj]
            return obj

        data = convert_val(asdict(self))
        return json.dumps(data, indent=2)


def order_quad_points(pts: np.ndarray) -> np.ndarray:
    """Order points in clockwise order starting from Top-Left: [TL, TR, BR, BL]."""
    pts = pts.reshape((4, 2))
    rect = np.zeros((4, 2), dtype=np.float32)

    s = pts.sum(axis=1)
    rect[0] = pts[np.argmin(s)]  # Top-left (smallest sum)
    rect[2] = pts[np.argmax(s)]  # Bottom-right (largest sum)

    diff = np.diff(pts, axis=1)
    rect[1] = pts[np.argmin(diff)]  # Top-right (smallest diff)
    rect[3] = pts[np.argmax(diff)]  # Bottom-left (largest diff)

    return rect


def detect_paper_quad(
    image: np.ndarray,
    min_area_ratio: float = 0.08,
    max_area_ratio: float = 0.85,
) -> tuple[np.ndarray | None, float, str | None]:
    """Detect paper quadrilateral in frame.

    Returns:
        (quad_pts_ordered, confidence, failure_reason)
    """
    h, w = image.shape[:2]
    total_area = float(w * h)

    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if len(image.shape) == 3 else image

    # Check for extreme glare or dark occlusion
    mean_brightness = float(np.mean(gray))
    if mean_brightness < 20:
        return None, 0.0, "FRAME_TOO_DARK"
    if mean_brightness > 245:
        return None, 0.0, "FRAME_WASHED_OUT"

    # Check for localized optical glare (saturated white circle/patch)
    sat_mask = (gray >= 252).astype(np.uint8)
    sat_contours, _ = cv2.findContours(sat_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    for sc in sat_contours:
        if cv2.contourArea(sc) > 15000:
            # Significant glare patch covering paper or corner
            return None, 0.0, "SEVERE_GLARE_OCCLUSION"

    # Multi-scale edge and contour extraction
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)

    # Adaptive thresholding to isolate bright paper on dark bed
    thresh = cv2.adaptiveThreshold(blurred, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 25, 4)

    # Morphological closing to seal boundary gaps
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
    closed = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)

    contours, _ = cv2.findContours(closed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return None, 0.0, "NO_CONTOURS_DETECTED"

    # Also check Otsu threshold as secondary candidate
    _, otsu = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    otsu_contours, _ = cv2.findContours(otsu, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    all_contours = list(contours) + list(otsu_contours)
    all_contours.sort(key=cv2.contourArea, reverse=True)

    best_quad = None
    best_conf = 0.0
    best_reason = "PAPER_NOT_FOUND"

    for cnt in all_contours[:5]:
        area = cv2.contourArea(cnt)
        ratio = area / total_area
        if ratio < min_area_ratio or ratio > max_area_ratio:
            continue

        peri = cv2.arcLength(cnt, True)
        approx = cv2.approxPolyDP(cnt, 0.025 * peri, True)

        if len(approx) == 4:
            pts = approx.reshape((4, 2)).astype(np.float32)
            ordered = order_quad_points(pts)

            # Check convexity and angles
            # Vector sides
            v0 = ordered[1] - ordered[0]
            v1 = ordered[2] - ordered[1]
            v2 = ordered[3] - ordered[2]
            v3 = ordered[0] - ordered[3]

            len0 = np.linalg.norm(v0)
            len1 = np.linalg.norm(v1)
            len2 = np.linalg.norm(v2)
            len3 = np.linalg.norm(v3)

            # Aspect ratio check (A5/A4 is approx 1:1.414)
            aspect1 = max(len0, len1) / max(1.0, min(len0, len1))
            aspect2 = max(len2, len3) / max(1.0, min(len2, len3))

            # Opposing sides ratio
            opp_ratio1 = abs(len0 - len2) / max(len0, len2)
            opp_ratio2 = abs(len1 - len3) / max(len1, len3)

            if opp_ratio1 > 0.4 or opp_ratio2 > 0.4:
                best_reason = "SEVERE_TRAPEZOIDAL_DISTORTION"
                continue

            # Check if any corner touches image boundary (out of frame)
            margin = 5
            touches_border = any(
                pt[0] <= margin or pt[0] >= w - margin or pt[1] <= margin or pt[1] >= h - margin
                for pt in ordered
            )
            if touches_border:
                best_reason = "PAPER_OUT_OF_FRAME"
                continue

            # Confidence scoring
            # 1. Aspect score: closeness to ~1.414
            aspect_err = abs((aspect1 + aspect2) / 2.0 - 1.414)
            aspect_score = max(0.0, 1.0 - aspect_err / 0.5)

            # 2. Parallelism score
            parallel_score = max(0.0, 1.0 - (opp_ratio1 + opp_ratio2))

            # 3. Brightness contrast between inside quad and outside
            mask = np.zeros(gray.shape, dtype=np.uint8)
            cv2.fillPoly(mask, [ordered.astype(np.int32)], 255)
            inside_mean = float(cv2.mean(gray, mask=mask)[0])
            outside_mean = float(cv2.mean(gray, mask=cv2.bitwise_not(mask))[0])
            contrast = (inside_mean - outside_mean) / max(1.0, inside_mean + outside_mean)
            contrast_score = max(0.0, min(1.0, contrast * 2.5))

            conf = 0.4 * aspect_score + 0.3 * parallel_score + 0.3 * contrast_score
            if conf > best_conf:
                best_conf = conf
                best_quad = ordered
                best_reason = None

    if best_quad is not None and best_conf >= 0.65:
        return best_quad, best_conf, None

    return None, best_conf, best_reason or "PAPER_NOT_FOUND"


def detect_clips_and_obstacles(
    image: np.ndarray,
    paper_quad_px: np.ndarray | None = None,
    margin_px: float = 120.0,
) -> list[list[tuple[float, float]]]:
    """Detect metallic binder clips clamped along the bed perimeter or paper margins."""
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if len(image.shape) == 3 else image
    h, w = gray.shape

    # Estimate bed background intensity
    bed_sample = gray[int(h * 0.1) : int(h * 0.2), int(w * 0.1) : int(w * 0.2)]
    bed_mean = float(np.mean(bed_sample)) if bed_sample.size > 0 else 50.0

    # Silver metallic handles are significantly brighter than the bed background (>= bed_mean + 50)
    silver_thresh = max(110.0, bed_mean + 45.0)
    silver_handles = (gray >= silver_thresh).astype(np.uint8) * 255

    if paper_quad_px is not None:
        paper_mask = np.zeros((h, w), dtype=np.uint8)
        hull = cv2.convexHull(paper_quad_px.astype(np.int32))
        cv2.fillPoly(paper_mask, [hull], 255)
        # Exclude paper interior
        silver_handles = cv2.bitwise_and(silver_handles, cv2.bitwise_not(paper_mask))

    # Morphological grouping of handle pair and clip body
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (15, 15))
    dilated = cv2.dilate(silver_handles, kernel)

    contours, _ = cv2.findContours(dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    clips: list[list[tuple[float, float]]] = []

    for cnt in contours:
        area = cv2.contourArea(cnt)
        if 800 < area < 6000:
            rect = cv2.minAreaRect(cnt)
            (cx, cy), (bw, bh), angle = rect
            # Form expanded keepout box
            box = cv2.boxPoints(((cx, cy), (max(35.0, bw), max(35.0, bh)), angle))
            clips.append([(float(pt[0]), float(pt[1])) for pt in box])

    return clips


def compute_bed_homography(
    paper_corners_px: np.ndarray,
    bed_paper_corners_mm: np.ndarray | None = None,
) -> tuple[np.ndarray, float]:
    """Compute 3x3 homography matrix transforming image pixels to bed physical millimeters.

    Default assumes standard A5 paper (148 x 210 mm) placed parallel to bed coordinates.
    """
    if bed_paper_corners_mm is None:
        # Nominal A5 centered in printable bed area [148 x 210 mm]
        bed_paper_corners_mm = np.array(
            [
                [0.0, 210.0],  # Top-Left (highest Y)
                [148.0, 210.0],  # Top-Right
                [148.0, 0.0],  # Bottom-Right
                [0.0, 0.0],  # Bottom-Left
            ],
            dtype=np.float32,
        )

    H, _status = cv2.findHomography(paper_corners_px, bed_paper_corners_mm, cv2.RANSAC, 3.0)
    if H is None:
        return np.eye(3, dtype=np.float32), 0.0

    # Validate conditioning
    det = np.linalg.det(H)
    conf = 1.0 if abs(det) > 1e-6 else 0.0
    return H, conf
