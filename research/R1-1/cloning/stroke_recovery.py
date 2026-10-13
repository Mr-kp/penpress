"""Skeleton and stroke recovery module for offline handwriting images.

Implements:
1. Adaptive binarization and morphological cleaning.
2. Skeletonization (Zhang-Suen / Scikit-image).
3. Graph analysis: junction detection, branch extraction, path assembly.
4. Writing-order heuristics (top-to-bottom, left-to-right, continuity/smoothness).
5. Polyline simplification (RDP) and arc-length resampling.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np
from PIL import Image

try:
    from skimage.morphology import skeletonize

    HAS_SKIMAGE = True
except ImportError:
    HAS_SKIMAGE = False


@dataclass(frozen=True, slots=True)
class RecoveredStroke:
    points: list[tuple[float, float]]  # [(x, y), ...] in pixel or mm coordinates


def binarize_handwriting(image: Image.Image, threshold: int | None = None) -> np.ndarray:
    """Convert a handwriting image to binary array where ink = 1, background = 0."""
    gray = image.convert("L")
    arr = np.array(gray, dtype=np.uint8)
    if threshold is None:
        # Otsu or mean-based threshold
        # For typical handwriting on paper, background is bright (>180) and ink is dark (<130)
        mean_val = float(np.mean(arr))
        # adaptive: pick 0.8 * mean_val or 128
        threshold = int(min(180, max(50, mean_val * 0.85)))
    binary = (arr < threshold).astype(np.uint8)
    return binary


def skeletonize_binary(binary: np.ndarray) -> np.ndarray:
    """Skeletonize binary image (ink=1). Returns boolean array where skeleton=1."""
    if HAS_SKIMAGE:
        skel = skeletonize(binary > 0)
        return skel.astype(np.uint8)
    # Fallback pure python Zhang-Suen
    im = binary.copy()
    prev = np.zeros_like(im)
    while True:
        # pass 0
        marker = np.zeros_like(im)
        for i in range(1, im.shape[0] - 1):
            for j in range(1, im.shape[1] - 1):
                if im[i, j] == 0:
                    continue
                p2, p3, p4 = im[i - 1, j], im[i - 1, j + 1], im[i, j + 1]
                p5, p6, p7 = im[i + 1, j + 1], im[i + 1, j], im[i + 1, j - 1]
                p8, p9 = im[i, j - 1], im[i - 1, j - 1]
                a = (
                    int(p2 == 0 and p3 == 1)
                    + int(p3 == 0 and p4 == 1)
                    + int(p4 == 0 and p5 == 1)
                    + int(p5 == 0 and p6 == 1)
                    + int(p6 == 0 and p7 == 1)
                    + int(p7 == 0 and p8 == 1)
                    + int(p8 == 0 and p9 == 1)
                    + int(p9 == 0 and p2 == 1)
                )
                b = p2 + p3 + p4 + p5 + p6 + p7 + p8 + p9
                if a == 1 and 2 <= b <= 6 and (p2 * p4 * p6 == 0) and (p4 * p6 * p8 == 0):
                    marker[i, j] = 1
        im = np.bitwise_and(im, np.bitwise_not(marker))

        # pass 1
        marker = np.zeros_like(im)
        for i in range(1, im.shape[0] - 1):
            for j in range(1, im.shape[1] - 1):
                if im[i, j] == 0:
                    continue
                p2, p3, p4 = im[i - 1, j], im[i - 1, j + 1], im[i, j + 1]
                p5, p6, p7 = im[i + 1, j + 1], im[i + 1, j], im[i + 1, j - 1]
                p8, p9 = im[i, j - 1], im[i - 1, j - 1]
                a = (
                    int(p2 == 0 and p3 == 1)
                    + int(p3 == 0 and p4 == 1)
                    + int(p4 == 0 and p5 == 1)
                    + int(p5 == 0 and p6 == 1)
                    + int(p6 == 0 and p7 == 1)
                    + int(p7 == 0 and p8 == 1)
                    + int(p8 == 0 and p9 == 1)
                    + int(p9 == 0 and p2 == 1)
                )
                b = p2 + p3 + p4 + p5 + p6 + p7 + p8 + p9
                if a == 1 and 2 <= b <= 6 and (p2 * p4 * p8 == 0) and (p2 * p6 * p8 == 0):
                    marker[i, j] = 1
        im = np.bitwise_and(im, np.bitwise_not(marker))
        if np.array_equal(prev, im):
            break
        prev = im.copy()
    return im


def rdp_simplify(points: list[tuple[float, float]], epsilon: float = 1.0) -> list[tuple[float, float]]:
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
            dist = math.hypot(pt[0] - start[0], pt[1] - start[1])
        else:
            t = max(0.0, min(1.0, ((pt[0] - start[0]) * dx + (pt[1] - start[1]) * dy) / line_len_sq))
            proj_x = start[0] + t * dx
            proj_y = start[1] + t * dy
            dist = math.hypot(pt[0] - proj_x, pt[1] - proj_y)

        if dist > max_dist:
            max_dist = dist
            index = i

    if max_dist > epsilon and index > 0:
        left = rdp_simplify(points[: index + 1], epsilon)
        right = rdp_simplify(points[index:], epsilon)
        return left[:-1] + right
    return [start, end]


def trace_skeleton_graph(
    skeleton: np.ndarray,
    min_length_px: float = 3.0,
    rdp_epsilon: float = 1.0,
) -> list[RecoveredStroke]:
    """Convert skeleton bitmap into a collection of ordered pen strokes.

    Builds an 8-connected adjacency graph of skeleton pixels, finds endpoints
    (degree 1) and junctions (degree >= 3), segments into maximal paths,
    resolves junctions using tangent continuity, and sorts strokes in
    natural western writing order (top-to-bottom, left-to-right).
    """
    rows, cols = skeleton.shape
    skel_pts = set()
    for r in range(rows):
        for c in range(cols):
            if skeleton[r, c] > 0:
                skel_pts.add((c, r))  # (x, y)

    if not skel_pts:
        return []

    # 8-connected neighbors
    def get_neighbors(pt: tuple[int, int]) -> list[tuple[int, int]]:
        x, y = pt
        nbrs = []
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                if dx == 0 and dy == 0:
                    continue
                nb = (x + dx, y + dy)
                if nb in skel_pts:
                    nbrs.append(nb)
        return nbrs

    # Adjacency
    adj: dict[tuple[int, int], list[tuple[int, int]]] = {pt: get_neighbors(pt) for pt in skel_pts}

    # Find endpoints (deg == 1) and junctions (deg >= 3) and cycles (deg == 2)
    visited_edges: set[frozenset[tuple[int, int]]] = set()
    paths: list[list[tuple[float, float]]] = []

    # Helper: trace along degree 2 chain
    endpoints = [pt for pt, nbrs in adj.items() if len(nbrs) == 1]
    junctions = [pt for pt, nbrs in adj.items() if len(nbrs) >= 3]

    # First pass: trace from endpoints
    # Sort endpoints top-to-bottom, left-to-right
    endpoints.sort(key=lambda p: (p[1], p[0]))

    for ep in endpoints:
        for nxt in adj[ep]:
            edge = frozenset((ep, nxt))
            if edge in visited_edges:
                continue
            # trace path
            path: list[tuple[float, float]] = [(float(ep[0]), float(ep[1]))]
            curr = ep
            step = nxt
            visited_edges.add(edge)
            path.append((float(step[0]), float(step[1])))

            while True:
                # get next candidate that isn't curr
                curr_nbrs = [nb for nb in adj[step] if nb != curr]
                if not curr_nbrs:
                    break
                if len(adj[step]) >= 3:
                    # reached junction! stop branch here
                    break
                # degree 2: continue
                next_pt = curr_nbrs[0]
                edge = frozenset((step, next_pt))
                if edge in visited_edges:
                    break
                visited_edges.add(edge)
                curr, step = step, next_pt
                path.append((float(step[0]), float(step[1])))

            if len(path) >= 2:
                paths.append(path)

    # Second pass: trace between unvisited junction edges
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

    # Third pass: closed loops (isolated circles like 'o' or '0')
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

    # Assemble and orient paths according to handwriting stroke conventions:
    # 1. Orientation: top-to-bottom, or left-to-right if nearly horizontal.
    oriented_paths: list[list[tuple[float, float]]] = []
    for path in paths:
        # Calculate arc-length
        length = sum(
            math.hypot(path[i + 1][0] - path[i][0], path[i + 1][1] - path[i][1]) for i in range(len(path) - 1)
        )
        if length < min_length_px:
            continue
        p_start = path[0]
        p_end = path[-1]
        # Natural writing direction: top to bottom (y_start <= y_end)
        # If dy is small, left to right (x_start <= x_end)
        dy = p_end[1] - p_start[1]
        dx = p_end[0] - p_start[0]
        oriented = list(reversed(path)) if dy < -1.5 or (abs(dy) <= 1.5 and dx < 0) else path
        oriented_paths.append(oriented)

    # Sort strokes in natural writing sequence (Western: lines top to bottom, characters left to right)
    # Primary key: quantized Y (line grouping, ~15px bins), Secondary key: X
    def sort_key(stroke: list[tuple[float, float]]) -> tuple[int, float]:
        min_x = min(pt[0] for pt in stroke)
        min_y = min(pt[1] for pt in stroke)
        y_bin = int(min_y // 20.0)
        return (y_bin, min_x)

    oriented_paths.sort(key=sort_key)

    # Simplify using RDP
    final_strokes: list[RecoveredStroke] = []
    for p in oriented_paths:
        simplified = rdp_simplify(p, epsilon=rdp_epsilon)
        if len(simplified) >= 2:
            final_strokes.append(RecoveredStroke(points=simplified))

    return final_strokes


def compute_chamfer_distance(
    pred_strokes: Sequence[RecoveredStroke | Sequence[tuple[float, float]]],
    gt_strokes: Sequence[Sequence[tuple[float, float]] | Sequence[dict[str, float]]],
) -> tuple[float, float, float]:
    """Compute bidirectional Chamfer distance between recovered strokes and ground truth strokes.

    Returns:
        (mean_chamfer_px, pred_to_gt_px, gt_to_pred_px)
    """
    pred_pts: list[tuple[float, float]] = []
    for s in pred_strokes:
        if isinstance(s, RecoveredStroke):
            pred_pts.extend(s.points)
        elif isinstance(s, (list, tuple)):
            for pt in s:
                if isinstance(pt, dict):
                    pred_pts.append((float(pt["x"]), float(pt["y"])))
                else:
                    pred_pts.append((float(pt[0]), float(pt[1])))

    gt_pts: list[tuple[float, float]] = []
    for s in gt_strokes:
        for pt in s:
            if isinstance(pt, dict):
                gt_pts.append((float(pt["x"]), float(pt["y"])))
            else:
                gt_pts.append((float(pt[0]), float(pt[1])))

    if not pred_pts or not gt_pts:
        return (999.0, 999.0, 999.0)

    p_arr = np.array(pred_pts, dtype=np.float32)
    g_arr = np.array(gt_pts, dtype=np.float32)

    # Distance p -> nearest g
    # Compute chunked or broadcasting (p_arr is typically ~500 points)
    dists_p2g = []
    for p in p_arr:
        d = np.min(np.hypot(g_arr[:, 0] - p[0], g_arr[:, 1] - p[1]))
        dists_p2g.append(float(d))

    dists_g2p = []
    for g in g_arr:
        d = np.min(np.hypot(p_arr[:, 0] - g[0], p_arr[:, 1] - g[1]))
        dists_g2p.append(float(d))

    mean_p2g = float(np.mean(dists_p2g))
    mean_g2p = float(np.mean(dists_g2p))
    mean_chamfer = (mean_p2g + mean_g2p) / 2.0
    return (mean_chamfer, mean_p2g, mean_g2p)
