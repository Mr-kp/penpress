"""Unit tests for MarlinSimulator, trapezoidal timing, safety violations, and toolpath rendering."""

from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image

from penpress.plan.profile import MachineProfile
from penpress.plan.sim import (
    MarlinErrorCode,
    MarlinSimulator,
    MarlinSimulatorError,
    compute_trapezoid_time,
)


@pytest.fixture
def standard_profile() -> MachineProfile:
    return MachineProfile(
        name="Test Ender 3 Pro",
        bed_width_mm=235.0,
        bed_height_mm=235.0,
        margin_left_mm=10.0,
        margin_right_mm=10.0,
        margin_bottom_mm=10.0,
        margin_top_mm=10.0,
        z_lift_mm=3.5,
        z_write_mm=0.5,
        z_write_min_mm=0.1,
        travel_feedrate_mm_min=6000.0,
        draw_feedrate_mm_min=2400.0,
        z_lift_feedrate_mm_min=1200.0,
        z_drop_feedrate_mm_min=800.0,
    )


def test_trapezoid_timing_hand_calculated_cases() -> None:
    """Validate trapezoidal timing against 3 mathematically hand-calculated test cases.

    Case 1: Full Trapezoid (Distance exceeds d_crit).
      - distance = 100.0 mm
      - feedrate = 3000 mm/min => v = 50.0 mm/s
      - accel a = 500.0 mm/s^2
      - d_crit = v^2 / a = 2500 / 500 = 5.0 mm.
      - Since d = 100 mm >= 5 mm:
        * t_ramp = v / a = 50 / 500 = 0.1 s.
        * d_cruise = 100 - 5 = 95.0 mm.
        * t_cruise = 95 / 50 = 1.9 s.
        * Total time = 2 * t_ramp + t_cruise = 0.2 + 1.9 = 2.100 s.

    Case 2: Triangular Profile (Distance less than d_crit, target velocity not reached).
      - distance = 4.0 mm
      - feedrate = 6000 mm/min => v_target = 100.0 mm/s
      - accel a = 400.0 mm/s^2
      - d_crit = 100^2 / 400 = 10000 / 400 = 25.0 mm.
      - Since d = 4.0 mm < 25.0 mm:
        * Peak velocity v_peak = sqrt(distance * a) = sqrt(4.0 * 400) = sqrt(1600) = 40.0 mm/s.
        * Time = 2 * (v_peak / a) = 2 * (40 / 400) = 2 * 0.1 = 0.200 s.

    Case 3: Exact Boundary Profile (Distance exactly equal to d_crit).
      - distance = 16.0 mm
      - feedrate = 2400 mm/min => v = 40.0 mm/s
      - accel a = 100.0 mm/s^2
      - d_crit = 40^2 / 100 = 1600 / 100 = 16.0 mm.
      - Cruise distance = 0 mm.
      * Total time = 2 * (v / a) = 2 * (40 / 100) = 0.800 s.
    """
    # Case 1: Full Trapezoid
    t1 = compute_trapezoid_time(distance_mm=100.0, v_feedrate_mm_s=50.0, acceleration_mm_s2=500.0)
    assert pytest.approx(t1, rel=1e-5) == 2.100

    # Case 2: Triangular Profile
    t2 = compute_trapezoid_time(distance_mm=4.0, v_feedrate_mm_s=100.0, acceleration_mm_s2=400.0)
    assert pytest.approx(t2, rel=1e-5) == 0.200

    # Case 3: Exact Boundary
    t3 = compute_trapezoid_time(distance_mm=16.0, v_feedrate_mm_s=40.0, acceleration_mm_s2=100.0)
    assert pytest.approx(t3, rel=1e-5) == 0.800

    # Edge cases
    assert compute_trapezoid_time(0.0, 50.0, 500.0) == 0.0
    assert pytest.approx(compute_trapezoid_time(10.0, 50.0, 0.0), rel=1e-5) == 0.2


def test_violation_rejection_table(standard_profile: MachineProfile) -> None:
    """Verify distinct error codes for all negative safety violation cases."""
    sim = MarlinSimulator(standard_profile, strict_safety=True)

    # 1. Out of bounds X (negative)
    with pytest.raises(MarlinSimulatorError) as exc_info:
        sim.execute_line("G0 X-5.0 Y10.0")
    assert exc_info.value.code == MarlinErrorCode.ERR_OUT_OF_BOUNDS

    # 2. Out of bounds X (greater than bed width)
    with pytest.raises(MarlinSimulatorError) as exc_info:
        sim.execute_line("G0 X250.0 Y10.0")
    assert exc_info.value.code == MarlinErrorCode.ERR_OUT_OF_BOUNDS

    # 3. Out of bounds Y
    with pytest.raises(MarlinSimulatorError) as exc_info:
        sim.execute_line("G0 X10.0 Y300.0")
    assert exc_info.value.code == MarlinErrorCode.ERR_OUT_OF_BOUNDS

    # 4. Z below safety floor (z_write_min is 0.1 mm)
    with pytest.raises(MarlinSimulatorError) as exc_info:
        sim.execute_line("G1 Z0.05 F500")
    assert exc_info.value.code == MarlinErrorCode.ERR_Z_BELOW_MIN

    # 5. Heater command (extruder heater active)
    with pytest.raises(MarlinSimulatorError) as exc_info:
        sim.execute_line("M104 S200")
    assert exc_info.value.code == MarlinErrorCode.ERR_HEATER_COMMAND

    # 6. Bed heater active
    with pytest.raises(MarlinSimulatorError) as exc_info:
        sim.execute_line("M140 S60")
    assert exc_info.value.code == MarlinErrorCode.ERR_HEATER_COMMAND

    # 7. Unknown G-code command
    with pytest.raises(MarlinSimulatorError) as exc_info:
        sim.execute_line("G999 X10")
    assert exc_info.value.code == MarlinErrorCode.ERR_UNKNOWN_COMMAND


def test_serial_checksum_and_resend_protocol(standard_profile: MachineProfile) -> None:
    """Test line-number, XOR checksum calculation, and resend protocol on corruption."""
    sim = MarlinSimulator(standard_profile, strict_safety=False)

    # Valid line with checksum: N1 G21*27
    resp = sim.execute_line("N1 G21*27")
    assert resp == "ok\n"
    assert sim.state.millimeter_mode is True
    assert sim.state.last_line_number == 1

    # Injected corrupted checksum: N2 G90*999 (wrong checksum, should be 18)
    resp_err = sim.execute_line("N2 G90*999")
    assert "checksum mismatch" in resp_err
    assert "Resend: 2" in resp_err
    expected_violation = (
        MarlinErrorCode.ERR_CHECKSUM_MISMATCH,
        "Checksum mismatch: computed 18, received 999 on line 2",
    )
    assert expected_violation in sim.violations

    # Re-send line 2 with valid checksum (18)
    resp_fixed = sim.execute_line("N2 G90*18")
    assert resp_fixed == "ok\n"
    assert sim.state.last_line_number == 2

    # Out of order line: received N5 when N3 was expected (checksum is 85)
    resp_ooo = sim.execute_line("N5 G0 X10*85")
    assert "Line Number is not Last Line Number+1" in resp_ooo
    assert "Resend: 3" in resp_ooo


def test_execute_golden_pages_zero_violations(standard_profile: MachineProfile, tmp_path: Path) -> None:
    """Execute compiled output of all P1-3 golden pages with zero violations and produce PNG."""
    golden_dir = Path("tests/golden/gcode")
    golden_files = sorted(golden_dir.glob("*.gcode"))
    assert len(golden_files) == 3, f"Expected 3 golden files, found {len(golden_files)}"

    for g_path in golden_files:
        sim = MarlinSimulator(standard_profile, strict_safety=True)
        gcode_content = g_path.read_text(encoding="utf-8")
        responses = sim.execute_stream(gcode_content)

        assert len(responses) > 0
        assert len(sim.violations) == 0, f"Violations found in {g_path.name}: {sim.violations}"
        assert sim.state.total_time_seconds > 0.0
        assert len(sim.segments) > 0

        # Verify segments have pen contact
        draw_segments = [s for s in sim.segments if s.pen_contact]
        assert len(draw_segments) >= 1

        # Render PNG and SVG
        png_out = tmp_path / f"{g_path.stem}.png"
        svg_out = tmp_path / f"{g_path.stem}.svg"
        sim.save_image(png_out)
        svg_text = sim.render_to_svg()
        svg_out.write_text(svg_text, encoding="utf-8")

        assert png_out.exists()
        img = Image.open(png_out)
        assert img.size == (940, 940)
        assert "<svg" in svg_text


def test_simulator_state_mutation(standard_profile: MachineProfile) -> None:
    """Assert every accepted command updates simulator state as expected."""
    sim = MarlinSimulator(standard_profile, strict_safety=True)

    # Cold boot state (z starts at safe clearance lift height)
    assert sim.state.x == 0.0
    assert sim.state.y == 0.0
    assert sim.state.z == standard_profile.z_lift_mm
    assert not sim.state.is_homed

    # Safe preamble commands
    sim.execute_line("M104 S0")
    assert sim.state.extruder_temp == 0.0
    sim.execute_line("M140 S0")
    assert sim.state.bed_temp == 0.0
    sim.execute_line("M107")
    assert sim.state.fan_speed == 0
    sim.execute_line("M106 S128")
    assert sim.state.fan_speed == 128

    sim.execute_line("G28")
    assert sim.state.is_homed is True

    # Move with feedrate
    sim.execute_line("G0 Z3.5 F1200")
    assert sim.state.z == 3.5
    assert sim.state.feedrate_mm_min == 1200.0

    sim.execute_line("G0 X20.0 Y30.0 F6000")
    assert sim.state.x == 20.0
    assert sim.state.y == 30.0
    assert sim.state.feedrate_mm_min == 6000.0

    # Relative move mode
    sim.execute_line("G91")
    assert not sim.state.absolute_mode
    sim.execute_line("G0 X5.0 Y-10.0")
    assert sim.state.x == 25.0
    assert sim.state.y == 20.0

    # Restore absolute mode
    sim.execute_line("G90")
    assert sim.state.absolute_mode

    # Disable steppers
    sim.execute_line("M84")
    assert not sim.state.steppers_enabled
    sim.execute_line("M17")
    assert sim.state.steppers_enabled
