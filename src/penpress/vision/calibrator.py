"""Automated vision calibration engine for Ender 3 Pro pen plotter.

Detects paper corners, computes homography, extracts binder clips with expanded safety buffers,
and provides confidence gating with graceful diagnostic fallbacks.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import cv2
import numpy as np

from penpress.core.primitives import Point
from penpress.vision.bed_model import PaperBedPlacement


@dataclass(frozen=True, slots=True)
class VisionCalibrationResult:
    """Result of camera calibration pass."""

    valid: bool
    confidence: float
    failure_reason: str | None = None
    placement: PaperBedPlacement | None = None
    paper_corners_px: tuple[tuple[float, float], ...] = field(default_factory=tuple)
    clip_polygons_px: tuple[tuple[tuple[float, float], ...], ...] = field(default_factory=tuple)
    clip_polygons_bed_mm: tuple[tuple[Point, ...], ...] = field(default_factory=tuple)
    homography_matrix: tuple[tuple[float, ...], ...] = field(default_factory=tuple)


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


def detect_paper_quadrilateral(
    image: np.ndarray,
    min_area_ratio: float = 0.08,
    max_area_ratio: float = 0.85,
) -> tuple[np.ndarray | None, float, str | None]:
    """Detect paper quadrilateral with lighting guards and subpixel refinement."""
    h, w = image.shape[:2]
    total_area = float(w * h)

    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if len(image.shape) == 3 else image

    # Lighting and washed-out checks
    mean_brightness = float(np.mean(gray))
    if mean_brightness < 20:
        return None, 0.0, "FRAME_TOO_DARK"
    if mean_brightness > 245:
        return None, 0.0, "FRAME_WASHED_OUT"

    # Glare patch detection
    sat_mask = (gray >= 252).astype(np.uint8)
    sat_contours, _ = cv2.findContours(sat_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    for sc in sat_contours:
        if cv2.contourArea(sc) > 15000:
            return None, 0.0, "SEVERE_GLARE_OCCLUSION"

    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    thresh = cv2.adaptiveThreshold(blurred, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 25, 4)
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
    closed = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)

    contours, _ = cv2.findContours(closed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return None, 0.0, "NO_CONTOURS_DETECTED"

    _, otsu = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    otsu_contours, _ = cv2.findContours(otsu, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    all_contours = list(contours) + list(otsu_contours)
    all_contours.sort(key=cv2.contourArea, reverse=True)

    best_quad = None
    best_conf = 0.0
    best_reason: str | None = "PAPER_NOT_FOUND"

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

            v0 = ordered[1] - ordered[0]
            v1 = ordered[2] - ordered[1]
            v2 = ordered[3] - ordered[2]
            v3 = ordered[0] - ordered[3]

            len0 = np.linalg.norm(v0)
            len1 = np.linalg.norm(v1)
            len2 = np.linalg.norm(v2)
            len3 = np.linalg.norm(v3)

            aspect1 = max(len0, len1) / max(1.0, min(len0, len1))
            aspect2 = max(len2, len3) / max(1.0, min(len2, len3))

            opp_ratio1 = abs(len0 - len2) / max(len0, len2)
            opp_ratio2 = abs(len1 - len3) / max(len1, len3)

            if opp_ratio1 > 0.4 or opp_ratio2 > 0.4:
                best_reason = "SEVERE_TRAPEZOIDAL_DISTORTION"
                continue

            margin = 5
            touches_border = any(
                pt[0] <= margin or pt[0] >= w - margin or pt[1] <= margin or pt[1] >= h - margin
                for pt in ordered
            )
            if touches_border:
                best_reason = "PAPER_OUT_OF_FRAME"
                continue

            aspect_err = abs((aspect1 + aspect2) / 2.0 - 1.414)
            aspect_score = max(0.0, 1.0 - aspect_err / 0.5)
            parallel_score = max(0.0, 1.0 - (opp_ratio1 + opp_ratio2))

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
        # Refine corners with subpixel accuracy
        criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 0.01)
        refined = cv2.cornerSubPix(gray, best_quad.copy(), (3, 3), (-1, -1), criteria)
        return refined, best_conf, None

    return None, best_conf, best_reason or "PAPER_NOT_FOUND"


def detect_clips_and_expand_keepout(
    image: np.ndarray,
    paper_quad_px: np.ndarray | None = None,
    buffer_mm: float = 5.0,
    px_per_mm: float = 3.19,
) -> tuple[list[list[tuple[float, float]]], list[list[tuple[float, float]]]]:
    """Detect metallic binder clips and return both raw and expanded keepout polygons in pixels.

    buffer_mm expands each clip polygon outward by at least the specified millimeter safety margin.
    """
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if len(image.shape) == 3 else image
    h, w = gray.shape

    bed_sample = gray[int(h * 0.1) : int(h * 0.2), int(w * 0.1) : int(w * 0.2)]
    bed_mean = float(np.mean(bed_sample)) if bed_sample.size > 0 else 50.0

    silver_thresh = max(110.0, bed_mean + 45.0)
    silver_handles = (gray >= silver_thresh).astype(np.uint8) * 255

    if paper_quad_px is not None:
        paper_mask = np.zeros((h, w), dtype=np.uint8)
        hull = cv2.convexHull(paper_quad_px.astype(np.int32))
        cv2.fillPoly(paper_mask, [hull], 255)
        silver_handles = cv2.bitwise_and(silver_handles, cv2.bitwise_not(paper_mask)).astype(np.uint8)

    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (15, 15))
    dilated = cv2.dilate(silver_handles, kernel)

    contours, _ = cv2.findContours(dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    raw_clips: list[list[tuple[float, float]]] = []
    expanded_clips: list[list[tuple[float, float]]] = []

    buffer_px = buffer_mm * px_per_mm

    for cnt in contours:
        area = cv2.contourArea(cnt)
        if 800 < area < 6000:
            rect = cv2.minAreaRect(cnt)
            (cx, cy), (bw, bh), angle = rect

            raw_box = cv2.boxPoints(((cx, cy), (max(35.0, bw), max(35.0, bh)), angle))
            raw_clips.append([(float(pt[0]), float(pt[1])) for pt in raw_box])

            # Expand width and height by 2 * buffer_px
            exp_w = max(35.0, bw) + 2.0 * buffer_px
            exp_h = max(35.0, bh) + 2.0 * buffer_px
            exp_box = cv2.boxPoints(((cx, cy), (exp_w, exp_h), angle))
            expanded_clips.append([(float(pt[0]), float(pt[1])) for pt in exp_box])

    return raw_clips, expanded_clips


class CameraCalibrator:
    """Automated camera-to-bed calibration pipeline."""

    def __init__(
        self,
        nominal_paper_w_mm: float = 148.0,
        nominal_paper_h_mm: float = 210.0,
        clip_buffer_mm: float = 5.0,
        bed_width_mm: float = 235.0,
        bed_height_mm: float = 235.0,
    ) -> None:
        self.nominal_paper_w_mm = nominal_paper_w_mm
        self.nominal_paper_h_mm = nominal_paper_h_mm
        self.clip_buffer_mm = clip_buffer_mm
        self.bed_width_mm = bed_width_mm
        self.bed_height_mm = bed_height_mm

    def calibrate(self, image: np.ndarray) -> VisionCalibrationResult:
        """Run complete vision calibration pipeline on camera image."""
        quad_px, conf, failure_reason = detect_paper_quadrilateral(image)
        if quad_px is None or failure_reason is not None:
            return VisionCalibrationResult(
                valid=False,
                confidence=conf,
                failure_reason=failure_reason,
            )

        # Estimate pixel per mm scale from paper width in pixels
        w_px = float(np.linalg.norm(quad_px[1] - quad_px[0]))
        px_per_mm = w_px / max(1.0, self.nominal_paper_w_mm)

        raw_clips_px, exp_clips_px = detect_clips_and_expand_keepout(
            image=image,
            paper_quad_px=quad_px,
            buffer_mm=self.clip_buffer_mm,
            px_per_mm=px_per_mm,
        )

        # Estimate bed coordinates for the 4 corners:
        # Centered or placed with margin on 235 x 235 mm bed
        # Default nominal target for homography:
        # Top-left is (margin_x, margin_y + nominal_h), etc.
        margin_x = (self.bed_width_mm - self.nominal_paper_w_mm) / 2.0
        margin_y = (self.bed_height_mm - self.nominal_paper_h_mm) / 2.0

        target_corners_bed = np.array(
            [
                [margin_x, margin_y + self.nominal_paper_h_mm],  # TL (highest Y)
                [margin_x + self.nominal_paper_w_mm, margin_y + self.nominal_paper_h_mm],  # TR
                [margin_x + self.nominal_paper_w_mm, margin_y],  # BR (lowest Y)
                [margin_x, margin_y],  # BL
            ],
            dtype=np.float32,
        )

        H, _ = cv2.findHomography(quad_px, target_corners_bed, cv2.RANSAC, 3.0)
        if H is None:
            H = np.eye(3, dtype=np.float32)

        # Transform paper corners to bed mm
        corners_bed_list: list[Point] = []
        for pt in quad_px:
            vec = np.array([pt[0], pt[1], 1.0], dtype=np.float32)
            b = H @ vec
            bx = float(b[0] / b[2])
            by = float(b[1] / b[2])
            corners_bed_list.append(Point(bx, by))

        # Transform expanded clip polygons to bed mm
        clip_polys_bed: list[tuple[Point, ...]] = []
        for poly in exp_clips_px:
            pts_bed: list[Point] = []
            for pt in poly:
                vec = np.array([pt[0], pt[1], 1.0], dtype=np.float32)
                b = H @ vec
                bx = float(b[0] / b[2])
                by = float(b[1] / b[2])
                pts_bed.append(Point(bx, by))
            clip_polys_bed.append(tuple(pts_bed))

        placement = PaperBedPlacement(
            corners_bed_mm=(
                corners_bed_list[0],
                corners_bed_list[1],
                corners_bed_list[2],
                corners_bed_list[3],
            ),
            source_mode="camera",
            confidence=conf,
            bed_width_mm=self.bed_width_mm,
            bed_height_mm=self.bed_height_mm,
            keepout_polygons_mm=tuple(clip_polys_bed),
        )

        h_tuple = tuple(tuple(float(v) for v in row) for row in H)
        quad_tuple = tuple((float(pt[0]), float(pt[1])) for pt in quad_px)
        raw_clips_tuple = tuple(tuple((float(p[0]), float(p[1])) for p in c) for c in raw_clips_px)

        return VisionCalibrationResult(
            valid=True,
            confidence=conf,
            placement=placement,
            paper_corners_px=quad_tuple,
            clip_polygons_px=raw_clips_tuple,
            clip_polygons_bed_mm=tuple(clip_polys_bed),
            homography_matrix=h_tuple,
        )
