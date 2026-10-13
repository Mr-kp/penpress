"""Immutable bed coordinate mapping, paper boundaries, and keepouts."""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from penpress.core.primitives import BoundingBox, Point


@dataclass(frozen=True, slots=True)
class PaperBedPlacement:
    """Immutable placement of paper on the physical printer bed.

    Corners are ordered Top-Left, Top-Right, Bottom-Right, Bottom-Left:
    c0 = TL (lowest X, highest Y in standard Cartesian)
    c1 = TR (highest X, highest Y)
    c2 = BR (highest X, lowest Y)
    c3 = BL (lowest X, lowest Y)
    """

    corners_bed_mm: tuple[Point, Point, Point, Point]
    source_mode: str  # "camera" or "manual"
    confidence: float = 1.0
    bed_width_mm: float = 235.0
    bed_height_mm: float = 235.0
    keepout_polygons_mm: tuple[tuple[Point, ...], ...] = field(default_factory=tuple)

    @property
    def top_left(self) -> Point:
        return self.corners_bed_mm[0]

    @property
    def top_right(self) -> Point:
        return self.corners_bed_mm[1]

    @property
    def bottom_right(self) -> Point:
        return self.corners_bed_mm[2]

    @property
    def bottom_left(self) -> Point:
        return self.corners_bed_mm[3]

    @property
    def bounding_box(self) -> BoundingBox:
        xs = [pt.x for pt in self.corners_bed_mm]
        ys = [pt.y for pt in self.corners_bed_mm]
        return BoundingBox(min_x=min(xs), min_y=min(ys), max_x=max(xs), max_y=max(ys))

    @property
    def width_mm(self) -> float:
        # Distance from TL to TR
        return math.hypot(self.top_right.x - self.top_left.x, self.top_right.y - self.top_left.y)

    @property
    def height_mm(self) -> float:
        # Distance from TL to BL
        return math.hypot(self.bottom_left.x - self.top_left.x, self.bottom_left.y - self.top_left.y)

    @property
    def rotation_rad(self) -> float:
        """Angle of the top paper edge relative to horizontal X axis."""
        dx = self.top_right.x - self.top_left.x
        dy = self.top_right.y - self.top_left.y
        return math.atan2(dy, dx)

    def paper_to_bed_point(self, p_paper: Point) -> Point:
        """Transform a point in paper coordinates (origin top-left, x right, y down) to bed mm."""
        w = max(1.0, self.width_mm)
        h = max(1.0, self.height_mm)
        u = p_paper.x / w
        v = p_paper.y / h

        # Bilinear interpolation of quad corners
        tl = self.top_left
        tr = self.top_right
        br = self.bottom_right
        bl = self.bottom_left

        bx = (1.0 - u) * (1.0 - v) * tl.x + u * (1.0 - v) * tr.x + u * v * br.x + (1.0 - u) * v * bl.x
        by = (1.0 - u) * (1.0 - v) * tl.y + u * (1.0 - v) * tr.y + u * v * br.y + (1.0 - u) * v * bl.y
        return Point(bx, by)

    def is_point_in_keepout(self, pt: Point) -> bool:
        """Check if bed point falls inside any registered keepout polygon (e.g. binder clips)."""
        for poly in self.keepout_polygons_mm:
            if len(poly) < 3:
                continue
            # Ray casting algorithm
            inside = False
            n = len(poly)
            p1 = poly[0]
            for i in range(1, n + 1):
                p2 = poly[i % n]
                if (
                    pt.y > min(p1.y, p2.y)
                    and pt.y <= max(p1.y, p2.y)
                    and pt.x <= max(p1.x, p2.x)
                    and p1.y != p2.y
                ):
                    x_inters = (pt.y - p1.y) * (p2.x - p1.x) / (p2.y - p1.y) + p1.x
                    if p1.x == p2.x or pt.x <= x_inters:
                        inside = not inside
                p1 = p2
            if inside:
                return True
        return False
