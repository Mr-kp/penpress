"""Sample sheet image ingestion, perspective rectification, and cell extraction.

Takes a photo or scan of a filled handwriting sample sheet:
1. Detects fiducial alignment corners.
2. Rectifies perspective distortion to canonical coordinate space.
3. Segments and crops cell bounding boxes.
4. Recovers stroke polylines using thinning, graph tracing, and RDP simplification.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import cv2
import numpy as np
from skimage.morphology import skeletonize

from penpress.core.primitives import Point, Stroke
from penpress.profile.models import HandwritingProfile, StyleMetrics
from penpress.profile.sheet_gen import DEFAULT_CHARS


class SheetAlignmentError(Exception):
    """Raised when fiducials cannot be localized or the sheet is corrupted/misaligned."""


def find_fiducial_markers(img_gray: np.ndarray) -> np.ndarray:
    """Finds the 4 corner alignment markers in the captured sheet."""
    h, w = img_gray.shape

    # Check for empty / low-contrast or blank images (e.g. solid white or solid black)
    std_dev = float(np.std(img_gray))
    if std_dev < 10.0:
        raise SheetAlignmentError("Image has insufficient contrast or is blank.")

    # Adaptive thresholding to find solid black marker squares
    thresh = cv2.adaptiveThreshold(
        img_gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 25, 8
    )

    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    marker_centers = []
    min_area = (w * h) * 0.00005
    max_area = (w * h) * 0.01

    for cnt in contours:
        area = cv2.contourArea(cnt)
        if min_area < area < max_area:
            peri = cv2.arcLength(cnt, True)
            approx = cv2.approxPolyDP(cnt, 0.04 * peri, True)
            if len(approx) == 4:
                # Check aspect ratio
                _bx, _by, bw, bh = cv2.boundingRect(approx)
                aspect = float(bw) / bh
                if 0.75 <= aspect <= 1.35:
                    m = cv2.moments(cnt)
                    if m["m00"] > 0:
                        cx = m["m10"] / m["m00"]
                        cy = m["m01"] / m["m00"]
                        marker_centers.append((cx, cy))

    # If 4 markers found near corners
    if len(marker_centers) >= 4:
        # Sort into TL, TR, BR, BL
        pts = np.array(marker_centers, dtype=np.float32)
        s = pts.sum(axis=1)
        diff = np.diff(pts, axis=1)

        tl = pts[np.argmin(s)]
        br = pts[np.argmax(s)]
        tr = pts[np.argmin(diff)]
        bl = pts[np.argmax(diff)]
        return np.array([tl, tr, br, bl], dtype=np.float32)

    # Fallback to document outer boundaries if fiducials are plain corner borders
    blurred = cv2.GaussianBlur(img_gray, (5, 5), 0)
    thresh_doc = cv2.adaptiveThreshold(
        blurred, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 21, 10
    )
    cnts, _ = cv2.findContours(255 - thresh_doc, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if cnts:
        c_largest = max(cnts, key=cv2.contourArea)
        if cv2.contourArea(c_largest) > (0.2 * w * h):
            peri = cv2.arcLength(c_largest, True)
            approx = cv2.approxPolyDP(c_largest, 0.02 * peri, True)
            if len(approx) == 4:
                pts = approx.reshape(4, 2).astype(np.float32)
                s = pts.sum(axis=1)
                diff = np.diff(pts, axis=1)
                return np.array(
                    [
                        pts[np.argmin(s)],
                        pts[np.argmin(diff)],
                        pts[np.argmax(s)],
                        pts[np.argmax(diff)],
                    ],
                    dtype=np.float32,
                )

    # Check for document edges / corners via Canny
    edges = cv2.Canny(blurred, 50, 150)
    edge_pts = np.argwhere(edges > 0)
    if len(edge_pts) < 100:
        raise SheetAlignmentError("Unable to locate alignment fiducials or page corners on sheet.")

    # Use standard full page margin fallback if document spans image with sufficient contrast
    if w >= 800 and h >= 800:
        return np.array(
            [
                [60.0, 60.0],
                [float(w - 60), 60.0],
                [float(w - 60), float(h - 60)],
                [60.0, float(h - 60)],
            ],
            dtype=np.float32,
        )

    raise SheetAlignmentError("Unable to locate alignment fiducials or page corners on sheet.")


def rectify_sheet(
    img: np.ndarray,
    target_width: int = 1600,
    target_height: int = 2200,
) -> tuple[np.ndarray, np.ndarray]:
    """Warp sheet to canonical fronto-parallel orientation."""
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if len(img.shape) == 3 else img

    corners = find_fiducial_markers(gray)

    dst_pts = np.array(
        [
            [0, 0],
            [target_width - 1, 0],
            [target_width - 1, target_height - 1],
            [0, target_height - 1],
        ],
        dtype=np.float32,
    )

    H = cv2.getPerspectiveTransform(corners, dst_pts)
    warped = cv2.warpPerspective(img, H, (target_width, target_height))
    return warped, H


def rdp_simplify(points: list[tuple[float, float]], epsilon: float = 0.8) -> list[tuple[float, float]]:
    """Ramer-Douglas-Peucker polyline simplification."""
    if len(points) < 3:
        return points

    start = points[0]
    end = points[-1]
    dx = end[0] - start[0]
    dy = end[1] - start[1]
    line_len_sq = dx * dx + dy * dy

    max_dist = -1.0
    index = -1

    for i in range(1, len(points) - 1):
        pt = points[i]
        if line_len_sq == 0:
            dist = float(np.hypot(pt[0] - start[0], pt[1] - start[1]))
        else:
            t = max(0.0, min(1.0, ((pt[0] - start[0]) * dx + (pt[1] - start[1]) * dy) / line_len_sq))
            proj_x = start[0] + t * dx
            proj_y = start[1] + t * dy
            dist = float(np.hypot(pt[0] - proj_x, pt[1] - proj_y))

        if dist > max_dist:
            max_dist = dist
            index = i

    if max_dist > epsilon and index > 0:
        left = rdp_simplify(points[: index + 1], epsilon)
        right = rdp_simplify(points[index:], epsilon)
        return left[:-1] + right
    return [start, end]


def trace_cell_strokes(
    cell_crop: np.ndarray,
    scale_mm_per_px: float = 0.1,
    min_stroke_length: int = 3,
    rdp_epsilon: float = 0.8,
) -> list[Stroke]:
    """Extracts stroke polyline primitives from a cropped cell image via skeleton graph."""
    gray = cv2.cvtColor(cell_crop, cv2.COLOR_BGR2GRAY) if len(cell_crop.shape) == 3 else cell_crop

    # Adaptive / Otsu binarization
    mean_val = float(np.mean(gray))
    thresh_val = int(min(180, max(50, mean_val * 0.85)))
    binary = (gray < thresh_val).astype(np.uint8)

    if not np.any(binary):
        return []

    # Skeletonize to single-pixel centerlines
    skel_bool = skeletonize(binary > 0)  # type: ignore[no-untyped-call]
    rows, cols = skel_bool.shape

    skel_pts: set[tuple[int, int]] = set()
    for r in range(rows):
        for c in range(cols):
            if skel_bool[r, c]:
                skel_pts.add((c, r))

    if not skel_pts:
        return []

    # Build 8-connected adjacency
    adj: dict[tuple[int, int], list[tuple[int, int]]] = {}
    for x, y in skel_pts:
        nbrs = []
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                if dx == 0 and dy == 0:
                    continue
                nb = (x + dx, y + dy)
                if nb in skel_pts:
                    nbrs.append(nb)
        adj[(x, y)] = nbrs

    visited_edges: set[frozenset[tuple[int, int]]] = set()
    paths: list[list[tuple[float, float]]] = []

    endpoints = [pt for pt, nbrs in adj.items() if len(nbrs) == 1]
    junctions = [pt for pt, nbrs in adj.items() if len(nbrs) >= 3]

    endpoints.sort(key=lambda p: (p[1], p[0]))

    # Pass 1: trace from endpoints
    for ep in endpoints:
        for nxt in adj[ep]:
            edge = frozenset((ep, nxt))
            if edge in visited_edges:
                continue
            path: list[tuple[float, float]] = [(float(ep[0]), float(ep[1]))]
            curr = ep
            step = nxt
            visited_edges.add(edge)
            path.append((float(step[0]), float(step[1])))

            while True:
                curr_nbrs = [nb for nb in adj[step] if nb != curr]
                if not curr_nbrs:
                    break
                if len(adj[step]) >= 3:
                    break
                next_pt = curr_nbrs[0]
                edge = frozenset((step, next_pt))
                if edge in visited_edges:
                    break
                visited_edges.add(edge)
                curr, step = step, next_pt
                path.append((float(step[0]), float(step[1])))

            if len(path) >= 2:
                paths.append(path)

    # Pass 2: unvisited junction edges
    for junc in junctions:
        for nxt in adj[junc]:
            edge = frozenset((junc, nxt))
            if edge in visited_edges:
                continue
            path = [(float(junc[0]), float(junc[1])), (float(nxt[0]), float(nxt[1]))]
            visited_edges.add(edge)
            curr = junc
            step = nxt
            while True:
                if len(adj[step]) >= 3:
                    break
                curr_nbrs = [nb for nb in adj[step] if nb != curr]
                if not curr_nbrs:
                    break
                next_pt = curr_nbrs[0]
                edge = frozenset((step, next_pt))
                if edge in visited_edges:
                    break
                visited_edges.add(edge)
                curr, step = step, next_pt
                path.append((float(step[0]), float(step[1])))
            if len(path) >= 2:
                paths.append(path)

    # Pass 3: closed loops
    remaining = [pt for pt in skel_pts if any(frozenset((pt, nb)) not in visited_edges for nb in adj[pt])]
    for pt in remaining:
        for nxt in adj[pt]:
            edge = frozenset((pt, nxt))
            if edge in visited_edges:
                continue
            path = [(float(pt[0]), float(pt[1])), (float(nxt[0]), float(nxt[1]))]
            visited_edges.add(edge)
            curr = pt
            step = nxt
            while True:
                curr_nbrs = [nb for nb in adj[step] if nb != curr]
                if not curr_nbrs:
                    break
                next_pt = curr_nbrs[0]
                edge = frozenset((step, next_pt))
                if edge in visited_edges:
                    break
                visited_edges.add(edge)
                curr, step = step, next_pt
                path.append((float(step[0]), float(step[1])))
                if step == pt:
                    break
            if len(path) >= 2:
                paths.append(path)

    # Filter by minimum length and orient
    oriented_paths: list[list[tuple[float, float]]] = []
    for path in paths:
        length = sum(
            float(np.hypot(path[i + 1][0] - path[i][0], path[i + 1][1] - path[i][1]))
            for i in range(len(path) - 1)
        )
        if length < min_stroke_length:
            continue
        p_start = path[0]
        p_end = path[-1]
        delta_y = float(p_end[1] - p_start[1])
        delta_x = float(p_end[0] - p_start[0])
        oriented = list(reversed(path)) if delta_y < -1.5 or (abs(delta_y) <= 1.5 and delta_x < 0) else path
        oriented_paths.append(oriented)

    # Sort strokes top-to-bottom, left-to-right
    def sort_key(stroke: list[tuple[float, float]]) -> tuple[int, float]:
        min_x = min(pt[0] for pt in stroke)
        min_y = min(pt[1] for pt in stroke)
        y_bin = int(min_y // 20.0)
        return (y_bin, min_x)

    oriented_paths.sort(key=sort_key)

    strokes: list[Stroke] = []
    for p in oriented_paths:
        simplified = rdp_simplify(p, epsilon=rdp_epsilon)
        if len(simplified) >= 2:
            pts = [Point(x=pt[0] * scale_mm_per_px, y=pt[1] * scale_mm_per_px) for pt in simplified]
            strokes.append(Stroke(points=pts))

    return strokes


class SampleSheetIngestEngine:
    def __init__(self, target_width: int = 1600, target_height: int = 2200) -> None:
        self.target_width = target_width
        self.target_height = target_height

    def ingest_sheet(
        self,
        image_path: str | Path,
        template_meta: dict[str, Any] | None = None,
    ) -> HandwritingProfile:
        path = Path(image_path)
        if not path.exists():
            raise FileNotFoundError(f"Sample sheet not found: {path}")

        img = cv2.imread(str(path))
        if img is None:
            raise SheetAlignmentError(f"Corrupted or invalid image file: {path}")

        # Check if accompanying JSON metadata exists if template_meta is not supplied
        if template_meta is None:
            meta_path = path.with_suffix(".json")
            if meta_path.exists():
                try:
                    template_meta = json.loads(meta_path.read_text(encoding="utf-8"))
                except Exception:
                    template_meta = None

        profile = HandwritingProfile(
            profile_id=path.stem,
            user_name="Sample User",
            created_at=str(path.stat().st_mtime_ns),
            metrics=StyleMetrics(
                slant_deg=0.0,
                baseline_jitter_mm=0.06,
                spacing_jitter_mm=0.15,
                stroke_width_mean_mm=0.4,
            ),
        )

        # If metadata has specific cells defined, use them directly
        if template_meta and "cells" in template_meta:
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            for cell_info in template_meta["cells"]:
                label = cell_info["label"]
                bx0, by0, bx1, by1 = cell_info["box_px"]
                # crop with margin
                h_crop, w_crop = gray.shape
                pad_x = int(0.08 * (bx1 - bx0))
                pad_y = int(0.08 * (by1 - by0))
                cy0 = max(0, by0 + pad_y)
                cy1 = min(h_crop, by1 - pad_y)
                cx0 = max(0, bx0 + pad_x)
                cx1 = min(w_crop, bx1 - pad_x)
                cell_crop = gray[cy0:cy1, cx0:cx1]
                strokes = trace_cell_strokes(cell_crop)
                if strokes:
                    profile.add_glyph_variant(label, strokes)
            return profile

        # Otherwise rectify image and segment regular grid
        warped, _ = rectify_sheet(img, self.target_width, self.target_height)

        # Segment grid cells
        margin_x = 0.06 * self.target_width
        margin_y_top = 0.08 * self.target_height
        margin_y_bottom = 0.05 * self.target_height

        cols = 8
        rows = 9
        cell_w = (self.target_width - 2 * margin_x) / cols
        cell_h = (self.target_height - margin_y_top - margin_y_bottom) / rows

        char_idx = 0

        for r in range(rows):
            for c in range(cols):
                if char_idx >= len(DEFAULT_CHARS):
                    break
                char = DEFAULT_CHARS[char_idx]

                x0 = int(margin_x + c * cell_w)
                y0 = int(margin_y_top + r * cell_h)
                x1 = int(x0 + cell_w)
                y1 = int(y0 + cell_h)

                pad_x = int(0.12 * cell_w)
                pad_y = int(0.15 * cell_h)
                cell_crop = warped[y0 + pad_y : y1 - pad_y, x0 + pad_x : x1 - pad_x]

                strokes = trace_cell_strokes(cell_crop)
                if strokes:
                    profile.add_glyph_variant(char, strokes)

                char_idx += 1

        return profile
