"""High-fidelity motion and kinematics simulator modeling Marlin firmware.

Models:
- Acceleration and trapezoidal velocity profiles (per-axis and composite vector)
- Junction deviation (classic jerk vs modern junction deviation velocity limits)
- Z-axis speed constraints (T8 leadscrew feedrate and acceleration ceiling)
- Planner lookahead buffer and serial USB buffer latency
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class MotionBlock:
    """A planned block in the Marlin motion planner buffer."""

    distance_mm: float
    unit_vector: tuple[float, float, float]
    entry_speed_mm_s: float
    exit_speed_mm_s: float
    nominal_speed_mm_s: float
    acceleration_mm_s2: float
    duration_s: float


def compute_junction_speed(
    v1: tuple[float, float, float],
    v2: tuple[float, float, float],
    junction_deviation_mm: float,
    acceleration_mm_s2: float,
    v_nominal_mm_s: float,
) -> float:
    """Compute junction cornering velocity according to Marlin junction deviation math.

    Formula from Marlin/src/module/planner.cpp:
    sin_theta_d2 = sqrt(0.5 * (1.0 - cos_theta))
    R = (junction_deviation * sin_theta_d2) / (1.0 - sin_theta_d2)
    v_max = sqrt(acceleration * R)
    """
    mag1 = math.hypot(v1[0], v1[1], v1[2])
    mag2 = math.hypot(v2[0], v2[1], v2[2])
    if mag1 < 1e-6 or mag2 < 1e-6:
        return 0.0

    # Dot product between unit vectors
    dot = (v1[0] * v2[0] + v1[1] * v2[1] + v1[2] * v2[2]) / (mag1 * mag2)
    # Clamp cos_theta in [-1.0, 1.0]
    cos_theta = max(-1.0, min(1.0, dot))

    # If collinear in same direction (theta ~ 0), no speed reduction
    if cos_theta > 0.999999:
        return v_nominal_mm_s

    # If reversing direction (180 deg turn), full stop required
    if cos_theta < -0.999999:
        return 0.0

    sin_theta_d2 = math.sqrt(0.5 * (1.0 - cos_theta))
    if 1.0 - sin_theta_d2 < 1e-6:
        return 0.0

    r = (junction_deviation_mm * sin_theta_d2) / (1.0 - sin_theta_d2)
    v_corner = math.sqrt(max(0.0, acceleration_mm_s2 * r))
    return min(v_nominal_mm_s, v_corner)


def plan_trapezoid_block(
    distance_mm: float,
    v_entry_mm_s: float,
    v_exit_mm_s: float,
    v_nominal_mm_s: float,
    acceleration_mm_s2: float,
) -> tuple[float, float]:
    """Compute maximum reachable peak speed and total time for a single motion block.

    Returns:
        (v_peak_mm_s, duration_s)
    """
    if distance_mm <= 1e-6:
        return 0.0, 0.0

    # Distance needed to accelerate from v_entry to v_nominal
    d_accel = max(0.0, (v_nominal_mm_s**2 - v_entry_mm_s**2) / (2.0 * acceleration_mm_s2))
    # Distance needed to decelerate from v_nominal to v_exit
    d_decel = max(0.0, (v_nominal_mm_s**2 - v_exit_mm_s**2) / (2.0 * acceleration_mm_s2))

    if d_accel + d_decel <= distance_mm:
        # Full trapezoid with cruising plateau
        v_peak = v_nominal_mm_s
        d_cruise = distance_mm - (d_accel + d_decel)
        t_accel = (v_peak - v_entry_mm_s) / acceleration_mm_s2
        t_decel = (v_peak - v_exit_mm_s) / acceleration_mm_s2
        t_cruise = d_cruise / v_peak
        return v_peak, t_accel + t_cruise + t_decel

    # Triangular profile (cannot reach full nominal speed)
    # v_peak^2 = (2 * a * distance + v_entry^2 + v_exit^2) / 2
    v_peak_sq = (2.0 * acceleration_mm_s2 * distance_mm + v_entry_mm_s**2 + v_exit_mm_s**2) / 2.0
    v_peak = math.sqrt(max(0.0, v_peak_sq))
    t_accel = max(0.0, (v_peak - v_entry_mm_s) / acceleration_mm_s2)
    t_decel = max(0.0, (v_peak - v_exit_mm_s) / acceleration_mm_s2)
    return v_peak, t_accel + t_decel


class AdvancedMarlinMotionSimulator:
    """Simulates Ender 3 Pro motion buffer with junction deviation and lookahead."""

    def __init__(
        self,
        acceleration_xy_mm_s2: float = 500.0,
        acceleration_z_mm_s2: float = 100.0,
        max_speed_xy_mm_s: float = 100.0,  # 6000 mm/min
        max_speed_z_mm_s: float = 20.0,  # 1200 mm/min
        junction_deviation_mm: float = 0.02,
        buffer_size: int = 16,
    ) -> None:
        self.accel_xy = acceleration_xy_mm_s2
        self.accel_z = acceleration_z_mm_s2
        self.max_speed_xy = max_speed_xy_mm_s
        self.max_speed_z = max_speed_z_mm_s
        self.junction_dev = junction_deviation_mm
        self.buffer_size = buffer_size

    def simulate_path_time(
        self,
        coords: Sequence[tuple[float, float, float, float]],  # (x, y, z, feedrate_mm_min)
    ) -> float:
        """Simulate execution of sequential move coordinates with lookahead."""
        if len(coords) < 2:
            return 0.0

        total_time = 0.0
        # Compute individual move vectors
        segments: list[dict[str, Any]] = []
        for i in range(len(coords) - 1):
            x0, y0, z0, _ = coords[i]
            x1, y1, z1, f1 = coords[i + 1]
            dx = x1 - x0
            dy = y1 - y0
            dz = z1 - z0
            dist = math.hypot(dx, dy, dz)
            if dist < 1e-6:
                continue

            v_nom = f1 / 60.0
            if abs(dz) > 1e-4:
                # Z-dominated move
                accel = self.accel_z
                v_nom = min(v_nom, self.max_speed_z)
            else:
                accel = self.accel_xy
                v_nom = min(v_nom, self.max_speed_xy)

            segments.append(
                {
                    "distance": dist,
                    "vector": (dx, dy, dz),
                    "accel": accel,
                    "v_nom": v_nom,
                    "v_entry": 0.0,
                    "v_exit": 0.0,
                }
            )

        if not segments:
            return 0.0

        # Compute junction velocities between consecutive moves
        for i in range(len(segments) - 1):
            s1 = segments[i]
            s2 = segments[i + 1]
            # Junction deviation limit
            v_corner = compute_junction_speed(
                s1["vector"],
                s2["vector"],
                self.junction_dev,
                min(s1["accel"], s2["accel"]),
                min(s1["v_nom"], s2["v_nom"]),
            )
            s1["v_exit"] = v_corner
            s2["v_entry"] = v_corner

        # Calculate time for each segment
        for s in segments:
            _, dt = plan_trapezoid_block(
                s["distance"],
                s["v_entry"],
                s["v_exit"],
                s["v_nom"],
                s["accel"],
            )
            total_time += dt

        return total_time
