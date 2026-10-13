"""Core geometric and document primitives for PenPress.

Immutable, typed structures for millimetre-coordinate strokes, paths, and pages
with affine transforms, bounding boxes, Ramer-Douglas-Peucker simplification,
arc-length resampling, and versioned JSON serialization.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

CURRENT_SCHEMA_VERSION = 1


class CoreGeometryError(ValueError):
    """Raised when geometric constraints are violated (e.g. NaN/inf coordinates or empty sequences)."""


@dataclass(frozen=True, slots=True)
class Point:
    """A 2D point on a page or bed measured in millimetres.

    Attributes:
        x: X-coordinate in mm.
        y: Y-coordinate in mm.
        pressure: Optional normalized contact pressure [0.0, 1.0].
        time_offset: Optional timestamp offset in seconds from stroke start.
    """

    x: float
    y: float
    pressure: float | None = None
    time_offset: float | None = None

    def __post_init__(self) -> None:
        if not math.isfinite(self.x) or not math.isfinite(self.y):
            raise CoreGeometryError(f"Point coordinates must be finite numbers, got x={self.x}, y={self.y}")
        if self.pressure is not None and (
            not math.isfinite(self.pressure) or not (0.0 <= self.pressure <= 1.0)
        ):
            raise CoreGeometryError(f"Pressure must be finite in range [0.0, 1.0], got {self.pressure}")
        if self.time_offset is not None and (not math.isfinite(self.time_offset) or self.time_offset < 0.0):
            raise CoreGeometryError(f"time_offset must be finite and non-negative, got {self.time_offset}")

    def distance_to(self, other: Point) -> float:
        """Euclidean distance in mm between two points."""
        return math.hypot(self.x - other.x, self.y - other.y)

    def to_dict(self) -> dict[str, Any]:
        """Convert point to dictionary representation."""
        data: dict[str, Any] = {"x": self.x, "y": self.y}
        if self.pressure is not None:
            data["p"] = self.pressure
        if self.time_offset is not None:
            data["t"] = self.time_offset
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Point:
        """Instantiate Point from dictionary."""
        if not isinstance(data, dict):
            raise CoreGeometryError(f"Point data must be a dict, got {type(data).__name__}")
        if "x" not in data or "y" not in data:
            raise CoreGeometryError("Point dict missing required keys 'x' or 'y'")
        x = float(data["x"])
        y = float(data["y"])
        p = float(data["p"]) if "p" in data and data["p"] is not None else None
        t = float(data["t"]) if "t" in data and data["t"] is not None else None
        return cls(x=x, y=y, pressure=p, time_offset=t)


@dataclass(frozen=True, slots=True)
class BoundingBox:
    """Axis-aligned bounding box in millimetres.

    Attributes:
        min_x: Minimum X in mm.
        min_y: Minimum Y in mm.
        max_x: Maximum X in mm.
        max_y: Maximum Y in mm.
    """

    min_x: float
    min_y: float
    max_x: float
    max_y: float

    def __post_init__(self) -> None:
        for val in (self.min_x, self.min_y, self.max_x, self.max_y):
            if not math.isfinite(val):
                raise CoreGeometryError(f"BoundingBox coordinates must be finite, got {self}")
        if self.min_x > self.max_x or self.min_y > self.max_y:
            raise CoreGeometryError(
                f"Invalid BoundingBox bounds: min_x={self.min_x} > max_x={self.max_x} "
                f"or min_y={self.min_y} > max_y={self.max_y}"
            )

    @property
    def width(self) -> float:
        """Width of bounding box in mm."""
        return self.max_x - self.min_x

    @property
    def height(self) -> float:
        """Height of bounding box in mm."""
        return self.max_y - self.min_y

    def contains_point(self, pt: Point, tolerance: float = 1e-9) -> bool:
        """Check whether point lies within bounds (with float tolerance)."""
        return (self.min_x - tolerance <= pt.x <= self.max_x + tolerance) and (
            self.min_y - tolerance <= pt.y <= self.max_y + tolerance
        )

    def to_dict(self) -> dict[str, float]:
        """Convert to dictionary representation."""
        return {
            "min_x": self.min_x,
            "min_y": self.min_y,
            "max_x": self.max_x,
            "max_y": self.max_y,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> BoundingBox:
        """Instantiate BoundingBox from dictionary."""
        if not isinstance(data, dict):
            raise CoreGeometryError("BoundingBox data must be a dict")
        return cls(
            min_x=float(data["min_x"]),
            min_y=float(data["min_y"]),
            max_x=float(data["max_x"]),
            max_y=float(data["max_y"]),
        )


@dataclass(frozen=True, slots=True)
class Transform2D:
    """2D Affine transformation representing [x', y', 1]^T = M * [x, y, 1]^T.

    Matrix layout:
      [ a  c  tx ]
      [ b  d  ty ]
      [ 0  0  1  ]
    """

    a: float = 1.0
    b: float = 0.0
    c: float = 0.0
    d: float = 1.0
    tx: float = 0.0
    ty: float = 0.0

    def __post_init__(self) -> None:
        for val in (self.a, self.b, self.c, self.d, self.tx, self.ty):
            if not math.isfinite(val):
                raise CoreGeometryError(f"Transform2D parameters must be finite, got {self}")

    @classmethod
    def identity(cls) -> Transform2D:
        """Identity transformation."""
        return cls(1.0, 0.0, 0.0, 1.0, 0.0, 0.0)

    @classmethod
    def translation(cls, dx: float, dy: float) -> Transform2D:
        """Translation transformation by dx, dy in mm."""
        return cls(1.0, 0.0, 0.0, 1.0, dx, dy)

    @classmethod
    def scale(cls, sx: float, sy: float) -> Transform2D:
        """Scale transformation by sx, sy."""
        return cls(sx, 0.0, 0.0, sy, 0.0, 0.0)

    @classmethod
    def rotation(cls, angle_radians: float) -> Transform2D:
        """Counter-clockwise rotation by angle in radians."""
        cos_theta = math.cos(angle_radians)
        sin_theta = math.sin(angle_radians)
        return cls(cos_theta, sin_theta, -sin_theta, cos_theta, 0.0, 0.0)

    def determinant(self) -> float:
        """Determinant of the linear component (a * d - b * c)."""
        return self.a * self.d - self.b * self.c

    def compose(self, other: Transform2D) -> Transform2D:
        """Compose self * other such that (self.compose(other)).apply(p) == self.apply(other.apply(p))."""
        return Transform2D(
            a=self.a * other.a + self.c * other.b,
            b=self.b * other.a + self.d * other.b,
            c=self.a * other.c + self.c * other.d,
            d=self.b * other.c + self.d * other.d,
            tx=self.a * other.tx + self.c * other.ty + self.tx,
            ty=self.b * other.tx + self.d * other.ty + self.ty,
        )

    def inverse(self) -> Transform2D:
        """Calculate the inverse transformation matrix."""
        det = self.determinant()
        if abs(det) < 1e-12:
            raise CoreGeometryError(f"Cannot invert singular transform with determinant {det}")
        inv_det = 1.0 / det
        inv_a = self.d * inv_det
        inv_b = -self.b * inv_det
        inv_c = -self.c * inv_det
        inv_d = self.a * inv_det
        inv_tx = -(inv_a * self.tx + inv_c * self.ty)
        inv_ty = -(inv_b * self.tx + inv_d * self.ty)
        return Transform2D(
            a=inv_a,
            b=inv_b,
            c=inv_c,
            d=inv_d,
            tx=inv_tx,
            ty=inv_ty,
        )

    def apply(self, pt: Point) -> Point:
        """Apply transform to a Point."""
        new_x = self.a * pt.x + self.c * pt.y + self.tx
        new_y = self.b * pt.x + self.d * pt.y + self.ty
        return Point(
            x=new_x,
            y=new_y,
            pressure=pt.pressure,
            time_offset=pt.time_offset,
        )

    def to_dict(self) -> dict[str, float]:
        """Convert to dictionary representation."""
        return {
            "a": self.a,
            "b": self.b,
            "c": self.c,
            "d": self.d,
            "tx": self.tx,
            "ty": self.ty,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Transform2D:
        """Instantiate Transform2D from dictionary."""
        if not isinstance(data, dict):
            raise CoreGeometryError("Transform2D data must be a dict")
        return cls(
            a=float(data.get("a", 1.0)),
            b=float(data.get("b", 0.0)),
            c=float(data.get("c", 0.0)),
            d=float(data.get("d", 1.0)),
            tx=float(data.get("tx", 0.0)),
            ty=float(data.get("ty", 0.0)),
        )


def _perpendicular_distance(pt: Point, line_start: Point, line_end: Point) -> float:
    """Perpendicular distance from pt to segment between line_start and line_end."""
    dx = line_end.x - line_start.x
    dy = line_end.y - line_start.y
    line_len_sq = dx * dx + dy * dy
    if line_len_sq < 1e-12:
        return pt.distance_to(line_start)
    # Area of parallelogram divided by base length
    num = abs(dy * pt.x - dx * pt.y + line_end.x * line_start.y - line_end.y * line_start.x)
    return num / math.sqrt(line_len_sq)


def simplify_rdp(points: Sequence[Point], epsilon: float) -> list[Point]:
    """Ramer-Douglas-Peucker simplification on a sequence of Points.

    Args:
        points: Sequence of Points.
        epsilon: Maximum allowed deviation in mm (must be >= 0.0).

    Returns:
        Simplified list of Points containing at least the first and last point.
    """
    if epsilon < 0.0:
        raise CoreGeometryError(f"RDP epsilon must be non-negative, got {epsilon}")
    if len(points) <= 2:
        return list(points)

    max_dist = 0.0
    index = 0
    start = points[0]
    end = points[-1]

    for i in range(1, len(points) - 1):
        dist = _perpendicular_distance(points[i], start, end)
        if dist > max_dist:
            max_dist = dist
            index = i

    if max_dist > epsilon:
        left = simplify_rdp(points[: index + 1], epsilon)
        right = simplify_rdp(points[index:], epsilon)
        return left[:-1] + right
    else:
        return [start, end]


def resample_points(points: Sequence[Point], step_mm: float) -> list[Point]:
    """Resample a sequence of Points along its polyline path at approximately uniform intervals.

    Preserves exact endpoints, intermediate turning points where direction reverses,
    and preserves total path arc-length within 0.5%.

    Args:
        points: Sequence of Points.
        step_mm: Desired step size between consecutive sampled points in mm.

    Returns:
        Resampled list of Points.
    """
    if step_mm <= 0.0 or not math.isfinite(step_mm):
        raise CoreGeometryError(f"step_mm must be a positive finite number, got {step_mm}")
    if len(points) <= 1:
        return list(points)

    total_len = 0.0
    for i in range(1, len(points)):
        total_len += points[i].distance_to(points[i - 1])

    if total_len < 1e-9:
        return [points[0], points[-1]]

    resampled: list[Point] = [points[0]]

    # Resample each segment individually or along the path maintaining intermediate vertices
    for i in range(len(points) - 1):
        p0 = points[i]
        p1 = points[i + 1]
        seg_dist = p0.distance_to(p1)
        if seg_dist < 1e-9:
            continue

        num_subsegs = max(1, math.ceil(seg_dist / step_mm))
        for step_idx in range(1, num_subsegs):
            ratio = step_idx / num_subsegs
            interp_x = p0.x + ratio * (p1.x - p0.x)
            interp_y = p0.y + ratio * (p1.y - p0.y)

            interp_p: float | None = None
            if p0.pressure is not None and p1.pressure is not None:
                interp_p = p0.pressure + ratio * (p1.pressure - p0.pressure)
            elif p0.pressure is not None:
                interp_p = p0.pressure

            interp_t: float | None = None
            if p0.time_offset is not None and p1.time_offset is not None:
                interp_t = p0.time_offset + ratio * (p1.time_offset - p0.time_offset)
            elif p0.time_offset is not None:
                interp_t = p0.time_offset

            resampled.append(Point(x=interp_x, y=interp_y, pressure=interp_p, time_offset=interp_t))

        resampled.append(p1)

    return resampled


@dataclass(frozen=True, slots=True)
class Stroke:
    """A continuous pen-down motion composed of an ordered sequence of points in mm.

    Attributes:
        points: Tuple of Points (must contain at least 2 points for a valid stroke).
    """

    points: tuple[Point, ...]

    def __init__(self, points: Sequence[Point]) -> None:
        if not points or len(points) < 2:
            count = len(points) if points else 0
            raise CoreGeometryError(f"A Stroke requires at least 2 points, got {count}")
        object.__setattr__(self, "points", tuple(points))

    @property
    def bounds(self) -> BoundingBox:
        """Compute the axis-aligned bounding box enclosing all points in mm."""
        xs = [p.x for p in self.points]
        ys = [p.y for p in self.points]
        return BoundingBox(
            min_x=min(xs),
            min_y=min(ys),
            max_x=max(xs),
            max_y=max(ys),
        )

    @property
    def length_mm(self) -> float:
        """Total Euclidean arc-length of the stroke in mm."""
        total = 0.0
        for i in range(1, len(self.points)):
            total += self.points[i].distance_to(self.points[i - 1])
        return total

    def transform(self, t: Transform2D) -> Stroke:
        """Return a new Stroke with transform t applied to all points."""
        return Stroke([t.apply(p) for p in self.points])

    def simplify(self, epsilon: float) -> Stroke:
        """Simplify stroke using Ramer-Douglas-Peucker algorithm."""
        simplified = simplify_rdp(self.points, epsilon)
        if len(simplified) < 2:
            simplified = [self.points[0], self.points[-1]]
        return Stroke(simplified)

    def resample(self, step_mm: float) -> Stroke:
        """Resample stroke at roughly uniform step_mm intervals."""
        return Stroke(resample_points(self.points, step_mm))

    def to_dict(self) -> dict[str, Any]:
        """Convert stroke to dictionary."""
        return {
            "pts": [p.to_dict() for p in self.points],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Stroke:
        """Instantiate Stroke from dictionary."""
        if not isinstance(data, dict):
            raise CoreGeometryError("Stroke data must be a dict")
        pts_raw = data.get("pts")
        if not isinstance(pts_raw, list):
            raise CoreGeometryError("Stroke dict missing 'pts' list")
        pts = [Point.from_dict(p) for p in pts_raw]
        return cls(pts)


@dataclass(frozen=True, slots=True)
class Path:
    """A collection of strokes forming a glyph, symbol, drawing element, or word.

    Attributes:
        strokes: Tuple of Strokes.
        label: Optional semantic label (e.g. character, equation node ID).
    """

    strokes: tuple[Stroke, ...]
    label: str | None = None

    def __init__(self, strokes: Sequence[Stroke], label: str | None = None) -> None:
        if not strokes:
            raise CoreGeometryError("A Path requires at least 1 Stroke")
        object.__setattr__(self, "strokes", tuple(strokes))
        object.__setattr__(self, "label", label)

    @property
    def bounds(self) -> BoundingBox:
        """Compute the axis-aligned bounding box enclosing all strokes."""
        min_x = min(s.bounds.min_x for s in self.strokes)
        min_y = min(s.bounds.min_y for s in self.strokes)
        max_x = max(s.bounds.max_x for s in self.strokes)
        max_y = max(s.bounds.max_y for s in self.strokes)
        return BoundingBox(min_x=min_x, min_y=min_y, max_x=max_x, max_y=max_y)

    @property
    def total_length_mm(self) -> float:
        """Total drawing length of all strokes in mm."""
        return sum(s.length_mm for s in self.strokes)

    def transform(self, t: Transform2D) -> Path:
        """Return a new Path with transform t applied to all strokes."""
        return Path([s.transform(t) for s in self.strokes], label=self.label)

    def simplify(self, epsilon: float) -> Path:
        """Simplify all strokes in the path using RDP."""
        return Path([s.simplify(epsilon) for s in self.strokes], label=self.label)

    def to_dict(self) -> dict[str, Any]:
        """Convert Path to dictionary."""
        data: dict[str, Any] = {
            "strokes": [s.to_dict() for s in self.strokes],
        }
        if self.label is not None:
            data["label"] = self.label
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Path:
        """Instantiate Path from dictionary."""
        if not isinstance(data, dict):
            raise CoreGeometryError("Path data must be a dict")
        strokes_raw = data.get("strokes")
        if not isinstance(strokes_raw, list):
            raise CoreGeometryError("Path dict missing 'strokes' list")
        strokes = [Stroke.from_dict(s) for s in strokes_raw]
        label = data.get("label")
        if label is not None and not isinstance(label, str):
            raise CoreGeometryError("Path 'label' must be a string")
        return cls(strokes, label=label)


@dataclass(frozen=True, slots=True)
class Page:
    """A printable document page with defined physical dimensions and paths in mm.

    Attributes:
        width_mm: Physical width of paper in mm (e.g. 148.0 for A5, 210.0 for A4).
        height_mm: Physical height of paper in mm (e.g. 210.0 for A5, 297.0 for A4).
        paths: Tuple of Paths on this page.
        schema_version: Version of the serialization schema.
    """

    width_mm: float
    height_mm: float
    paths: tuple[Path, ...]
    schema_version: int = CURRENT_SCHEMA_VERSION

    def __init__(
        self,
        width_mm: float,
        height_mm: float,
        paths: Sequence[Path],
        schema_version: int = CURRENT_SCHEMA_VERSION,
    ) -> None:
        if not math.isfinite(width_mm) or width_mm <= 0.0:
            raise CoreGeometryError(f"Page width_mm must be positive finite number, got {width_mm}")
        if not math.isfinite(height_mm) or height_mm <= 0.0:
            raise CoreGeometryError(f"Page height_mm must be positive finite number, got {height_mm}")
        if schema_version != CURRENT_SCHEMA_VERSION:
            raise CoreGeometryError(
                f"Unsupported schema_version {schema_version}; "
                f"current supported version is {CURRENT_SCHEMA_VERSION}"
            )
        object.__setattr__(self, "width_mm", float(width_mm))
        object.__setattr__(self, "height_mm", float(height_mm))
        object.__setattr__(self, "paths", tuple(paths))
        object.__setattr__(self, "schema_version", schema_version)

    @property
    def bounds(self) -> BoundingBox | None:
        """BoundingBox enclosing all paths on the page, or None if page has no paths."""
        if not self.paths:
            return None
        min_x = min(p.bounds.min_x for p in self.paths)
        min_y = min(p.bounds.min_y for p in self.paths)
        max_x = max(p.bounds.max_x for p in self.paths)
        max_y = max(p.bounds.max_y for p in self.paths)
        return BoundingBox(min_x=min_x, min_y=min_y, max_x=max_x, max_y=max_y)

    @property
    def total_length_mm(self) -> float:
        """Total written stroke length on the page in mm."""
        return sum(p.total_length_mm for p in self.paths)

    def transform(self, t: Transform2D) -> Page:
        """Return a new Page with transform t applied to all paths."""
        return Page(
            width_mm=self.width_mm,
            height_mm=self.height_mm,
            paths=[p.transform(t) for p in self.paths],
            schema_version=self.schema_version,
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert page to JSON-serializable dictionary."""
        return {
            "schema_version": self.schema_version,
            "width_mm": self.width_mm,
            "height_mm": self.height_mm,
            "paths": [p.to_dict() for p in self.paths],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Page:
        """Instantiate Page from dictionary, strictly checking schema_version."""
        if not isinstance(data, dict):
            raise CoreGeometryError("Page data must be a dict")
        version = data.get("schema_version")
        if version is None:
            raise CoreGeometryError("Page dict missing required 'schema_version' key")
        if version != CURRENT_SCHEMA_VERSION:
            raise CoreGeometryError(
                f"Unsupported schema_version {version}; current supported version is {CURRENT_SCHEMA_VERSION}"
            )

        if "width_mm" not in data or "height_mm" not in data:
            raise CoreGeometryError("Page dict missing 'width_mm' or 'height_mm'")
        width_mm = float(data["width_mm"])
        height_mm = float(data["height_mm"])

        paths_raw = data.get("paths", [])
        if not isinstance(paths_raw, list):
            raise CoreGeometryError("Page 'paths' must be a list")
        paths = [Path.from_dict(p) for p in paths_raw]
        return cls(
            width_mm=width_mm,
            height_mm=height_mm,
            paths=paths,
            schema_version=int(version),
        )
