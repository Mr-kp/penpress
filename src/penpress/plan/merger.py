"""Collinear and tangent stroke endpoint merger (P6-1).

Merges adjacent strokes whose endpoints are within a distance tolerance (<= 0.15 mm)
and whose tangent vectors are substantially collinear (or continuous).
Significantly reduces pen lift/drop cycles for multi-segment continuous lines.
"""

from __future__ import annotations

import math
from collections.abc import Sequence

from penpress.core.primitives import CoreGeometryError, Point, Stroke


class InvalidGeometryError(CoreGeometryError):
    """Raised when stroke geometry is invalid (NaN coordinates, zero-length, or fewer than 2 points)."""


def validate_stroke_geometry(stroke: Stroke) -> None:
    """Validate that stroke contains finite coordinates and non-zero total length."""
    if len(stroke.points) < 2:
        raise InvalidGeometryError(f"Stroke must contain at least 2 points, got {len(stroke.points)}")

    for pt in stroke.points:
        if not math.isfinite(pt.x) or not math.isfinite(pt.y):
            raise InvalidGeometryError(f"Stroke point contains non-finite coordinate: ({pt.x}, {pt.y})")

    if stroke.length_mm <= 1e-7:
        raise InvalidGeometryError(f"Stroke has zero length: {stroke.length_mm} mm")


def merge_collinear_strokes(
    strokes: Sequence[Stroke],
    distance_tolerance_mm: float = 0.15,
    angle_tolerance_deg: float = 30.0,
) -> list[Stroke]:
    """Merge adjacent strokes whose endpoints meet within tolerance.

    Args:
        strokes: Sequence of input strokes.
        distance_tolerance_mm: Maximum endpoint gap in mm to merge (default 0.15 mm).
        angle_tolerance_deg: Maximum angular difference between incoming and outgoing tangent vectors.

    Returns:
        List of merged strokes with reduced pen-lift count.
    """
    for s in strokes:
        validate_stroke_geometry(s)

    if len(strokes) <= 1:
        return list(strokes)

    cos_max = math.cos(math.radians(angle_tolerance_deg))
    merged: list[Stroke] = []
    current_pts: list[Point] = list(strokes[0].points)

    for next_stroke in strokes[1:]:
        next_pts = list(next_stroke.points)

        # Gap between current end and next start
        end_p = current_pts[-1]
        start_p = next_pts[0]
        gap = end_p.distance_to(start_p)

        can_merge = False
        if gap <= distance_tolerance_mm:
            # Check tangent alignment if there are enough points
            if len(current_pts) >= 2 and len(next_pts) >= 2:
                # Tangent of current stroke ending segment
                p_prev = current_pts[-2]
                v1_x = end_p.x - p_prev.x
                v1_y = end_p.y - p_prev.y
                len1 = math.hypot(v1_x, v1_y)

                # Tangent of next stroke starting segment
                p_next = next_pts[1]
                v2_x = p_next.x - start_p.x
                v2_y = p_next.y - start_p.y
                len2 = math.hypot(v2_x, v2_y)

                if len1 > 1e-9 and len2 > 1e-9:
                    dot = (v1_x * v2_x + v1_y * v2_y) / (len1 * len2)
                    if dot >= cos_max:
                        can_merge = True
                else:
                    can_merge = True
            else:
                can_merge = True

        if can_merge:
            # Merge: skip the first point of next_pts if it's virtually coincident
            if gap < 1e-6:
                current_pts.extend(next_pts[1:])
            else:
                current_pts.extend(next_pts)
        else:
            merged.append(Stroke(current_pts))
            current_pts = next_pts

    if current_pts:
        merged.append(Stroke(current_pts))

    return merged
