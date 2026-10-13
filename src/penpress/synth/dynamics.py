"""Ink dynamics and pen feedrate modulation based on curvature and contact pressure.

Models realistic pen-on-paper dynamics:
- Decelerates at sharp corners and high curvature to prevent pen skip and overshoot.
- Accelerates on straight ascenders and descenders.
- Computes multi-pass bold toolpaths (parallel offset passes) for headings and emphasis.
"""

from __future__ import annotations

from dataclasses import dataclass

from penpress.core.primitives import Point, Stroke


@dataclass(frozen=True, slots=True)
class FeedrateModulationParams:
    """Parameters governing curvature-dependent feedrate modulation in mm/min."""

    nominal_feedrate_mm_min: float = 3000.0
    min_feedrate_mm_min: float = 800.0
    max_feedrate_mm_min: float = 4500.0
    curvature_sensitivity: float = 0.60


def compute_local_curvature(p0: Point, p1: Point, p2: Point) -> float:
    """Compute turning curvature (inverse radius of circumscribed circle, 1/mm)."""
    d01 = p0.distance_to(p1)
    d12 = p1.distance_to(p2)
    d02 = p0.distance_to(p2)

    if d01 < 1e-6 or d12 < 1e-6 or d02 < 1e-6:
        return 0.0

    # Cross product area * 2
    area = abs((p1.x - p0.x) * (p2.y - p0.y) - (p1.y - p0.y) * (p2.x - p0.x))
    # Circumcircle radius R = (a * b * c) / (4 * Area)
    # Curvature kappa = 1 / R = (4 * Area) / (a * b * c)
    curvature = (2.0 * area) / (d01 * d12 * d02)
    return curvature


def compute_stroke_feedrates(
    stroke: Stroke,
    params: FeedrateModulationParams | None = None,
) -> list[float]:
    """Compute recommended feedrate (mm/min) for each segment of a stroke.

    Returns a list of length max(1, len(stroke.points) - 1).
    """
    if params is None:
        params = FeedrateModulationParams()
    pts = stroke.points
    if len(pts) < 2:
        return [params.nominal_feedrate_mm_min]

    feedrates: list[float] = []

    for i in range(len(pts) - 1):
        p_curr = pts[i]
        p_next = pts[i + 1]

        # Calculate local curvature around segment
        kappa = 0.0
        if i > 0:
            p_prev = pts[i - 1]
            kappa = max(kappa, compute_local_curvature(p_prev, p_curr, p_next))
        if i + 2 < len(pts):
            p_after = pts[i + 2]
            kappa = max(kappa, compute_local_curvature(p_curr, p_next, p_after))

        # Modulate speed: speed = nominal / (1 + sensitivity * kappa)
        mod_speed = params.nominal_feedrate_mm_min / (1.0 + params.curvature_sensitivity * kappa)
        clamped_speed = max(params.min_feedrate_mm_min, min(params.max_feedrate_mm_min, mod_speed))
        feedrates.append(round(clamped_speed, 1))

    return feedrates


def generate_bold_multipass_strokes(
    strokes: list[Stroke],
    offset_mm: float = 0.18,
    passes: int = 2,
) -> list[Stroke]:
    """Generate multi-pass offset strokes to simulate bold/heavy pen nibs.

    Args:
        strokes: Original stroke list.
        offset_mm: Distance between parallel offset passes in mm.
        passes: Number of parallel passes (e.g. 2 or 3).

    Returns:
        Expanded stroke list containing offset copies.
    """
    if passes <= 1 or offset_mm <= 0.0:
        return list(strokes)

    expanded: list[Stroke] = []

    # Center passes symmetrically around origin
    # e.g. passes = 2 -> [-offset/2, +offset/2]
    # e.g. passes = 3 -> [-offset, 0, +offset]
    shifts: list[float] = []
    if passes == 2:
        shifts = [-offset_mm / 2.0, offset_mm / 2.0]
    elif passes == 3:
        shifts = [-offset_mm, 0.0, offset_mm]
    else:
        half = (passes - 1) * offset_mm / 2.0
        step = passes - 1
        shifts = [-half + i * (2.0 * half / step) for i in range(passes)]

    for shift in shifts:
        for s in strokes:
            pts: list[Point] = []
            for p in s.points:
                # Perpendicular or slight diagonal offset
                pts.append(
                    Point(x=p.x + shift, y=p.y + shift * 0.3, pressure=p.pressure, time_offset=p.time_offset)
                )
            expanded.append(Stroke(pts))

    return expanded
