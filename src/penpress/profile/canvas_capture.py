"""Canvas and tablet online stroke capture engine.

Ingests pointer event streams (PointerEvent / touch / stylus events with x, y, pressure,
timestamps, and optional tilt), tracks instantaneous velocities, applies scale calibration
to millimetres, and constructs clean multi-stroke Stroke structures.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

from penpress.core.primitives import Point, Stroke
from penpress.profile.models import HandwritingProfile


class CanvasCaptureError(ValueError):
    """Raised when incoming canvas event data is malformed or invalid."""


@dataclass(frozen=True, slots=True)
class RawPointerEvent:
    """A single raw pointer event from a web canvas or digital digitizer.

    Attributes:
        x: X coordinate in screen/canvas pixels or arbitrary units.
        y: Y coordinate in screen/canvas pixels or arbitrary units.
        time_ms: Timestamp in milliseconds (relative or epoch).
        pressure: Contact pressure in range [0.0, 1.0], or None.
        tilt_x: Stylus tilt angle along X axis in degrees [-90, 90], or None.
        tilt_y: Stylus tilt angle along Y axis in degrees [-90, 90], or None.
    """

    x: float
    y: float
    time_ms: float
    pressure: float | None = None
    tilt_x: float | None = None
    tilt_y: float | None = None

    def __post_init__(self) -> None:
        if not math.isfinite(self.x) or not math.isfinite(self.y):
            raise CanvasCaptureError(f"Pointer coordinates must be finite, got x={self.x}, y={self.y}")
        if not math.isfinite(self.time_ms) or self.time_ms < 0.0:
            raise CanvasCaptureError(f"Timestamp time_ms must be non-negative, got {self.time_ms}")
        if self.pressure is not None and (
            not math.isfinite(self.pressure) or not (0.0 <= self.pressure <= 1.0)
        ):
            raise CanvasCaptureError(f"Pressure must be finite in range [0.0, 1.0], got {self.pressure}")
        if self.tilt_x is not None and (not math.isfinite(self.tilt_x) or abs(self.tilt_x) > 90.0):
            raise CanvasCaptureError(f"tilt_x must be in range [-90, 90], got {self.tilt_x}")
        if self.tilt_y is not None and (not math.isfinite(self.tilt_y) or abs(self.tilt_y) > 90.0):
            raise CanvasCaptureError(f"tilt_y must be in range [-90, 90], got {self.tilt_y}")

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RawPointerEvent:
        if not isinstance(data, dict):
            raise CanvasCaptureError(f"Expected dict for pointer event, got {type(data).__name__}")
        for key in ("x", "y", "time_ms"):
            if key not in data:
                raise CanvasCaptureError(f"Pointer event dict missing required key '{key}'")

        p = float(data["pressure"]) if "pressure" in data and data["pressure"] is not None else None
        tx = float(data["tilt_x"]) if "tilt_x" in data and data["tilt_x"] is not None else None
        ty = float(data["tilt_y"]) if "tilt_y" in data and data["tilt_y"] is not None else None

        return cls(
            x=float(data["x"]),
            y=float(data["y"]),
            time_ms=float(data["time_ms"]),
            pressure=p,
            tilt_x=tx,
            tilt_y=ty,
        )


@dataclass(frozen=True, slots=True)
class KinematicPoint:
    """A point enriched with kinematic physical properties in millimetres and seconds.

    Attributes:
        point: Geometric Point primitive in mm.
        vx_mm_s: Instantaneous horizontal velocity in mm/s.
        vy_mm_s: Instantaneous vertical velocity in mm/s.
        speed_mm_s: Magnitude of velocity in mm/s.
    """

    point: Point
    vx_mm_s: float
    vy_mm_s: float
    speed_mm_s: float


class CanvasStrokeSession:
    """Normalizes raw online stroke streams into calibrated physical Strokes.

    Parameters:
        scale_mm_per_unit: Conversion factor from canvas units (pixels) to millimetres.
            Default is 0.264583 mm/px (~96 DPI).
        invert_y: Whether canvas Y (downwards positive) should be flipped so upwards is positive.
            Default True, matching standard Cartesian/G-code document space.
        min_points_per_stroke: Minimum point count to accept a stroke (default 2).
    """

    def __init__(
        self,
        scale_mm_per_unit: float = 0.264583,
        invert_y: bool = True,
        min_points_per_stroke: int = 2,
    ) -> None:
        if scale_mm_per_unit <= 0.0 or not math.isfinite(scale_mm_per_unit):
            raise CanvasCaptureError(
                f"scale_mm_per_unit must be positive finite number, got {scale_mm_per_unit}"
            )
        if min_points_per_stroke < 2:
            raise CanvasCaptureError(f"min_points_per_stroke must be >= 2, got {min_points_per_stroke}")

        self.scale_mm_per_unit = scale_mm_per_unit
        self.invert_y = invert_y
        self.min_points_per_stroke = min_points_per_stroke

    def process_raw_stroke(
        self,
        raw_events: list[RawPointerEvent] | list[dict[str, Any]],
    ) -> tuple[Stroke, list[KinematicPoint]]:
        """Convert a sequence of raw pointer events representing one pen-down motion into a Stroke.

        Args:
            raw_events: List of RawPointerEvent objects or raw dicts.

        Returns:
            Tuple of (Stroke, list of KinematicPoints).
        """
        if not raw_events:
            raise CanvasCaptureError("Cannot process empty stroke event list")

        events: list[RawPointerEvent] = []
        for item in raw_events:
            if isinstance(item, RawPointerEvent):
                events.append(item)
            elif isinstance(item, dict):
                events.append(RawPointerEvent.from_dict(item))
            else:
                raise CanvasCaptureError(f"Invalid event item type: {type(item).__name__}")

        if len(events) < self.min_points_per_stroke:
            raise CanvasCaptureError(
                f"Stroke requires at least {self.min_points_per_stroke} points, got {len(events)}"
            )

        # Baseline start time
        t0_ms = events[0].time_ms

        points: list[Point] = []
        kinematics: list[KinematicPoint] = []

        for i, ev in enumerate(events):
            x_mm = ev.x * self.scale_mm_per_unit
            y_mm = (-ev.y if self.invert_y else ev.y) * self.scale_mm_per_unit
            t_sec = max(0.0, (ev.time_ms - t0_ms) / 1000.0)

            # Default pressure to 0.5 if not provided by device
            press = ev.pressure if ev.pressure is not None else 0.5

            pt = Point(x=x_mm, y=y_mm, pressure=press, time_offset=t_sec)
            points.append(pt)

            # Velocity computation using central differences or one-sided at boundaries
            if len(events) == 1:
                vx = vy = speed = 0.0
            elif i == 0:
                dt = (events[1].time_ms - ev.time_ms) / 1000.0
                if dt > 1e-6:
                    vx = (events[1].x - ev.x) * self.scale_mm_per_unit / dt
                    vy = (
                        (
                            (-events[1].y if self.invert_y else events[1].y)
                            - (-ev.y if self.invert_y else ev.y)
                        )
                        * self.scale_mm_per_unit
                        / dt
                    )
                    speed = math.hypot(vx, vy)
                else:
                    vx = vy = speed = 0.0
            elif i == len(events) - 1:
                dt = (ev.time_ms - events[i - 1].time_ms) / 1000.0
                if dt > 1e-6:
                    vx = (ev.x - events[i - 1].x) * self.scale_mm_per_unit / dt
                    vy = (
                        (
                            (-ev.y if self.invert_y else ev.y)
                            - (-events[i - 1].y if self.invert_y else events[i - 1].y)
                        )
                        * self.scale_mm_per_unit
                        / dt
                    )
                    speed = math.hypot(vx, vy)
                else:
                    vx = vy = speed = 0.0
            else:
                dt = (events[i + 1].time_ms - events[i - 1].time_ms) / 1000.0
                if dt > 1e-6:
                    vx = (events[i + 1].x - events[i - 1].x) * self.scale_mm_per_unit / dt
                    vy = (
                        (
                            (-events[i + 1].y if self.invert_y else events[i + 1].y)
                            - (-events[i - 1].y if self.invert_y else events[i - 1].y)
                        )
                        * self.scale_mm_per_unit
                        / dt
                    )
                    speed = math.hypot(vx, vy)
                else:
                    vx = vy = speed = 0.0

            kinematics.append(KinematicPoint(point=pt, vx_mm_s=vx, vy_mm_s=vy, speed_mm_s=speed))

        stroke = Stroke(points)
        return stroke, kinematics

    def process_glyph_drawing(
        self,
        stroke_list: list[list[RawPointerEvent]] | list[list[dict[str, Any]]],
        normalize_origin: bool = True,
    ) -> list[Stroke]:
        """Convert a collection of separate strokes forming a single multi-stroke glyph.

        Preserves individual strokes distinctly (does not flatten them).
        If normalize_origin is True, translates the glyph bounding box so min_x = 0 and min_y = 0.
        """
        if not stroke_list:
            raise CanvasCaptureError("Cannot process glyph with 0 strokes")

        strokes: list[Stroke] = []
        for raw_s in stroke_list:
            st, _ = self.process_raw_stroke(raw_s)
            strokes.append(st)

        if not normalize_origin:
            return strokes

        # Find global bounds across all strokes
        min_x = min(min(p.x for p in s.points) for s in strokes)
        min_y = min(min(p.y for p in s.points) for s in strokes)

        normalized: list[Stroke] = []
        for s in strokes:
            pts: list[Point] = []
            for p in s.points:
                pts.append(
                    Point(
                        x=p.x - min_x,
                        y=p.y - min_y,
                        pressure=p.pressure,
                        time_offset=p.time_offset,
                    )
                )
            normalized.append(Stroke(pts))

        return normalized


def populate_profile_from_canvas_bank(
    profile_id: str,
    user_name: str,
    glyph_bank_data: dict[str, list[list[list[dict[str, Any]]]]],
    scale_mm_per_unit: float = 0.264583,
) -> HandwritingProfile:
    """Construct a full HandwritingProfile from a dictionary of online canvas captured glyphs.

    Args:
        profile_id: Profile identifier.
        user_name: Human readable name.
        glyph_bank_data: Mapping from character -> list of variants, where each variant
            is a list of raw strokes (list of pointer dicts).
        scale_mm_per_unit: Canvas to mm scaling factor.

    Returns:
        Populated HandwritingProfile instance.
    """
    session = CanvasStrokeSession(scale_mm_per_unit=scale_mm_per_unit)
    profile = HandwritingProfile(
        profile_id=profile_id,
        user_name=user_name,
        created_at="2026-10-13T00:00:00Z",
    )

    for char, variants in glyph_bank_data.items():
        for raw_variant in variants:
            processed_strokes = session.process_glyph_drawing(raw_variant, normalize_origin=True)
            profile.add_glyph_variant(char, processed_strokes)

    return profile
