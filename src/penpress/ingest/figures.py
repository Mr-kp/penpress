"""Vector figure extraction and raster tracing module for document ingest.

Extracts line, rect, and curve drawing primitives directly from PDF vector streams.
Preserves topological pen strokes so diagrams, schematics, and plots can be plotted directly.
"""

from __future__ import annotations

from collections.abc import Sequence

import cv2
import numpy as np
from skimage.morphology import skeletonize

from penpress.ingest.schema import BlockType, BoundingBox, DocumentBlock


def cluster_drawings(
    paths: Sequence[list[tuple[float, float]]],
    min_elements: int = 3,
    max_margin_pt: float = 20.0,
) -> list[DocumentBlock]:
    """Clusters contiguous vector drawing paths into distinct figure blocks."""
    if not paths:
        return []

    # Calculate bounding box for each path
    path_boxes: list[BoundingBox] = []
    for p in paths:
        if not p:
            continue
        xs = [pt[0] for pt in p]
        ys = [pt[1] for pt in p]
        path_boxes.append(BoundingBox(x0=min(xs), y0=min(ys), x1=max(xs), y1=max(ys)))

    if len(path_boxes) < min_elements:
        return []

    # Compute overall union box
    u = path_boxes[0]
    for b in path_boxes[1:]:
        u = u.union(b)

    # Filter out whole-page borders
    if u.width > 500.0 and u.height > 700.0:
        return []

    fig_block = DocumentBlock(
        block_id="fig_vector_0",
        block_type=BlockType.FIGURE_VECTOR,
        page_idx=0,
        reading_order=0,
        bbox=u,
        confidence=0.95,
        vector_paths=list(paths),
        metadata={
            "path_count": len(paths),
            "stroke_segments": sum(max(0, len(p) - 1) for p in paths),
        },
    )
    return [fig_block]


def trace_raster_skeleton(image_gray: np.ndarray, threshold: int = 128) -> list[list[tuple[float, float]]]:
    """Fallback raster-to-vector tracer using skeletonization and contour polyline extraction.

    Transforms scanned/raster line diagrams into pen plotter stroke polylines.
    """
    binary = image_gray < threshold
    if not np.any(binary):
        return []

    skeleton = skeletonize(binary)
    _y_idxs, x_idxs = np.where(skeleton)
    if len(x_idxs) == 0:
        return []

    skel_uint8 = (skeleton * 255).astype(np.uint8)
    contours, _ = cv2.findContours(skel_uint8, cv2.RETR_LIST, cv2.CHAIN_APPROX_NONE)

    polylines: list[list[tuple[float, float]]] = []
    for cnt in contours:
        if len(cnt) < 2:
            continue
        approx = cv2.approxPolyDP(cnt, epsilon=1.0, closed=False)
        pts = [(float(pt[0][0]), float(pt[0][1])) for pt in approx]
        if len(pts) >= 2:
            polylines.append(pts)

    return polylines
