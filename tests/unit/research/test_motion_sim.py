"""Unit tests for R5-1 motion simulator and hardware schema validator."""

from __future__ import annotations

import json
from pathlib import Path

from motion_sim import (
    AdvancedMarlinMotionSimulator,
    compute_junction_speed,
    plan_trapezoid_block,
)


def test_junction_speed_collinear() -> None:
    # 0 deg turn -> no speed reduction
    v1 = (1.0, 0.0, 0.0)
    v2 = (1.0, 0.0, 0.0)
    speed = compute_junction_speed(v1, v2, 0.02, 500.0, 40.0)
    assert speed == 40.0


def test_junction_speed_reversal() -> None:
    # 180 deg reversal -> must stop completely
    v1 = (1.0, 0.0, 0.0)
    v2 = (-1.0, 0.0, 0.0)
    speed = compute_junction_speed(v1, v2, 0.02, 500.0, 40.0)
    assert speed == 0.0


def test_junction_speed_corner() -> None:
    # 90 deg corner
    v1 = (1.0, 0.0, 0.0)
    v2 = (0.0, 1.0, 0.0)
    speed = compute_junction_speed(v1, v2, 0.02, 500.0, 40.0)
    assert 4.5 < speed < 5.5


def test_trapezoid_block_planning() -> None:
    # Long move reaching cruising speed
    v_peak, duration = plan_trapezoid_block(
        distance_mm=100.0,
        v_entry_mm_s=0.0,
        v_exit_mm_s=0.0,
        v_nominal_mm_s=50.0,
        acceleration_mm_s2=500.0,
    )
    assert v_peak == 50.0
    # Accel time: 50/500 = 0.1s, d_accel = 2.5mm
    # Decel time: 50/500 = 0.1s, d_decel = 2.5mm
    # Cruise d = 95mm, time = 95/50 = 1.9s
    # Total time = 2.1s
    assert abs(duration - 2.1) < 1e-3


def test_simulator_multi_segment_trajectory() -> None:
    sim = AdvancedMarlinMotionSimulator()
    coords = [
        (0.0, 0.0, 0.0, 2400.0),
        (50.0, 0.0, 0.0, 2400.0),
        (50.0, 50.0, 0.0, 2400.0),
        (0.0, 50.0, 0.0, 2400.0),
        (0.0, 0.0, 0.0, 2400.0),
    ]
    t = sim.simulate_path_time(coords)
    assert t > 0.0
    # Total distance 200 mm, max speed 40 mm/s -> time > 5.0 s
    assert t > 5.0


def test_hardware_schema_validation() -> None:
    schema_file = Path("research/R5-1/hardware_schema.json")
    assert schema_file.exists()
    schema = json.loads(schema_file.read_text(encoding="utf-8"))
    assert schema["title"] == "PenPress Hardware Results"
    assert "bed_usable_width_mm" in schema["properties"]
    assert "z_contact_nominal_mm" in schema["properties"]
