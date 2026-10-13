"""Physical obstacle and binder clip keepout buffer module for PenPress.

Calculates printable regions, clipping boundaries, and safety clearance zones
around binder clips, tape, and bed hardware edges per ADR-0005.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass

from penpress.core.primitives import BoundingBox, Point, Stroke


@dataclass(frozen=True, slots=True)
class KeepoutPolygon:
    """A 2D polygon representing a hardware obstacle (e.g. binder clip) in mm.

    Attributes:
        points: Vertices of the obstacle polygon in mm.
        name: Identifier (e.g. 'top_clip_left', 'bed_margin').
        buffer_mm: Safety expansion buffer in mm (default 5.0 mm).
    """

    points: tuple[Point, ...]
    name: str = "obstacle"
    buffer_mm: float = 5.0

    def __init__(self, points: Sequence[Point], name: str = "obstacle", buffer_mm: float = 5.0) -> None:
        if len(points) < 3:
            raise ValueError(f"KeepoutPolygon requires at least 3 points, got {len(points)}")
        object.__setattr__(self, "points", tuple(points))
        object.__setattr__(self, "name", name)
        object.__setattr__(self, "buffer_mm", max(0.0, float(buffer_mm)))

    @property
    def bounds(self) -> BoundingBox:
        xs = [p.x for p in self.points]
        ys = [p.y for p in self.points]
        buf = self.buffer_mm
        return BoundingBox(
            min_x=min(xs) - buf,
            min_y=min(ys) - buf,
            max_x=max(xs) + buf,
            max_y=max(ys) + buf,
        )

    def contains_point(self, pt: Point) -> bool:
        """Ray-casting point-in-polygon check with safety expansion buffer."""
        # Fast bounding box check
        b = self.bounds
        if not (b.min_x <= pt.x <= b.max_x and b.min_y <= pt.y <= b.max_y):
            return False

        # If buffer is > 0, check distance to polygon boundary edges
        if self.buffer_mm > 0:
            for i in range(len(self.points)):
                p1 = self.points[i]
                p2 = self.points[(i + 1) % len(self.points)]
                if _point_segment_distance(pt, p1, p2) <= self.buffer_mm:
                    return True

        # Standard ray-casting for interior
        inside = False
        n = len(self.points)
        j = n - 1
        for i in range(n):
            pi = self.points[i]
            pj = self.points[j]
            if ((pi.y > pt.y) != (pj.y > pt.y)) and (
                pt.x < (pj.x - pi.x) * (pt.y - pi.y) / (pj.y - pi.y + 1e-12) + pi.x
            ):
                inside = not inside
            j = i
        return inside

    def intersects_stroke(self, stroke: Stroke) -> bool:
        """Check whether any stroke segment passes inside the keepout zone."""
        # 1. Check points directly
        for p in stroke.points:
            if self.contains_point(p):
                return True

        # 2. Check segment intersections
        for idx in range(len(stroke.points) - 1):
            s1 = stroke.points[idx]
            s2 = stroke.points[idx + 1]
            for i in range(len(self.points)):
                e1 = self.points[i]
                e2 = self.points[(i + 1) % len(self.points)]
                if _segments_intersect(s1, s2, e1, e2):
                    return True
                # Buffer clearance check along segment
                if self.buffer_mm > 0:
                    mid = Point(0.5 * (s1.x + s2.x), 0.5 * (s1.y + s2.y))
                    if self.contains_point(mid):
                        return True
        return False


def _point_segment_distance(p: Point, a: Point, b: Point) -> float:
    """Perpendicular Euclidean distance from point p to line segment ab in mm."""
    ab_x = b.x - a.x
    ab_y = b.y - a.y
    seg_len_sq = ab_x * ab_x + ab_y * ab_y
    if seg_len_sq <= 1e-12:
        return p.distance_to(a)

    t = max(0.0, min(1.0, ((p.x - a.x) * ab_x + (p.y - a.y) * ab_y) / seg_len_sq))
    proj_x = a.x + t * ab_x
    proj_y = a.y + t * ab_y
    return math.hypot(p.x - proj_x, p.y - proj_y)


def _segments_intersect(p1: Point, p2: Point, p3: Point, p4: Point) -> bool:
    """True if line segment p1-p2 intersects line segment p3-p4."""

    def ccw(a: Point, b: Point, c: Point) -> bool:
        return (c.y - a.y) * (b.x - a.x) > (b.y - a.y) * (c.x - a.x)

    return (ccw(p1, p3, p4) != ccw(p2, p3, p4)) and (ccw(p1, p2, p3) != ccw(p1, p2, p4))


def create_standard_a5_clip_keepouts(
    page_width_mm: float = 148.0,
    page_height_mm: float = 210.0,
    clip_width_mm: float = 20.0,
    clip_reach_mm: float = 12.0,
    buffer_mm: float = 5.0,
) -> list[KeepoutPolygon]:
    """Creates standard binder clip keepout polygons positioned along page top and bottom edges."""
    keepouts: list[KeepoutPolygon] = []

    # Top-left binder clip
    top_left = [
        Point(15.0, page_height_mm),
        Point(15.0 + clip_width_mm, page_height_mm),
        Point(15.0 + clip_width_mm, page_height_mm - clip_reach_mm),
        Point(15.0, page_height_mm - clip_reach_mm),
    ]
    keepouts.append(KeepoutPolygon(top_left, name="clip_top_left", buffer_mm=buffer_mm))

    # Top-right binder clip
    top_right = [
        Point(page_width_mm - 15.0 - clip_width_mm, page_height_mm),
        Point(page_width_mm - 15.0, page_height_mm),
        Point(page_width_mm - 15.0, page_height_mm - clip_reach_mm),
        Point(page_width_mm - 15.0 - clip_width_mm, page_height_mm - clip_reach_mm),
    ]
    keepouts.append(KeepoutPolygon(top_right, name="clip_top_right", buffer_mm=buffer_mm))

    # Bottom-left binder clip
    bot_left = [
        Point(15.0, 0.0),
        Point(15.0 + clip_width_mm, 0.0),
        Point(15.0 + clip_width_mm, clip_reach_mm),
        Point(15.0, clip_reach_mm),
    ]
    keepouts.append(KeepoutPolygon(bot_left, name="clip_bot_left", buffer_mm=buffer_mm))

    # Bottom-right binder clip
    bot_right = [
        Point(page_width_mm - 15.0 - clip_width_mm, 0.0),
        Point(page_width_mm - 15.0, 0.0),
        Point(page_width_mm - 15.0, clip_reach_mm),
        Point(page_width_mm - 15.0 - clip_width_mm, clip_reach_mm),
    ]
    keepouts.append(KeepoutPolygon(bot_right, name="clip_bot_right", buffer_mm=buffer_mm))

    return keepouts
