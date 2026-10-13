"""Hypothesis property tests, golden tests, throughput benchmark, and negative tests for GcodeCompiler."""

from __future__ import annotations

import re
import time
from pathlib import Path

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from penpress.core.primitives import Page, Point, Stroke
from penpress.core.primitives import Path as CorePath
from penpress.plan import (
    GcodeCompiler,
    GcodeOutOfBoundsError,
    MachineProfile,
    MachineProfileError,
)

# Test profile with well-defined dimensions
test_profile = MachineProfile(
    name="Test Plotter",
    bed_width_mm=220.0,
    bed_height_mm=220.0,
    margin_left_mm=10.0,
    margin_right_mm=10.0,
    margin_bottom_mm=10.0,
    margin_top_mm=10.0,
    z_lift_mm=3.0,
    z_write_mm=0.5,
    z_write_min_mm=0.1,
)

# Hypothesis generator for pages that fit within the usable envelope [0..180 mm]
safe_points = st.builds(
    Point,
    x=st.floats(min_value=0.0, max_value=180.0),
    y=st.floats(min_value=0.0, max_value=180.0),
)
safe_strokes = st.lists(safe_points, min_size=2, max_size=10).map(Stroke)
safe_paths = st.lists(safe_strokes, min_size=1, max_size=4).map(CorePath)
safe_pages = st.builds(
    Page,
    width_mm=st.just(190.0),
    height_mm=st.just(190.0),
    paths=st.lists(safe_paths, min_size=1, max_size=3),
)


# --- 1. Hypothesis Property Tests ---


@settings(max_examples=50, deadline=None)
@given(page=safe_pages)
def test_compiler_hypothesis_safety_properties(page: Page) -> None:
    compiler = GcodeCompiler(
        profile=test_profile,
        paper_origin_x_mm=10.0,
        paper_origin_y_mm=10.0,
        clamp_to_bed=False,
    )
    gcode = compiler.compile(page)
    lines = [line.strip() for line in gcode.splitlines() if line.strip() and not line.startswith(";")]

    # Property 1: No heater-on or fan-on commands ever emitted
    for line in lines:
        assert not re.search(r"M104\s+S[1-9]", line), f"Found heater command: {line}"
        assert not re.search(r"M140\s+S[1-9]", line), f"Found bed heater command: {line}"
        assert not re.search(r"M106\b", line), f"Found fan-on command: {line}"

    # Property 2: First motion command must be a Z-lift
    motion_cmds = [line for line in lines if line.startswith("G0") or line.startswith("G1")]
    assert len(motion_cmds) > 0
    assert "Z" in motion_cmds[0]
    assert "X" not in motion_cmds[0] and "Y" not in motion_cmds[0]

    # Property 3: Coordinate bounds and Z safety
    # Track machine state
    curr_z = 0.0
    pen_down = False

    for line in motion_cmds:
        # Check Z coordinate
        z_match = re.search(r"Z([0-9.-]+)", line)
        if z_match:
            curr_z = float(z_match.group(1))
            assert curr_z >= test_profile.z_write_min_mm, (
                f"Z {curr_z} dropped below safety floor {test_profile.z_write_min_mm}"
            )
            if curr_z <= test_profile.z_write_mm + 1e-4:
                pen_down = True
            elif curr_z >= test_profile.z_lift_mm - 1e-4:
                pen_down = False

        # Check XY coordinates
        x_match = re.search(r"X([0-9.-]+)", line)
        y_match = re.search(r"Y([0-9.-]+)", line)

        if x_match:
            x_val = float(x_match.group(1))
            assert test_profile.usable_min_x - 1e-4 <= x_val <= test_profile.usable_max_x + 1e-4, (
                f"X {x_val} out of bounds"
            )
        if y_match:
            y_val = float(y_match.group(1))
            assert test_profile.usable_min_y - 1e-4 <= y_val <= test_profile.usable_max_y + 1e-4, (
                f"Y {y_val} out of bounds"
            )

        # Property 4: Rapid travel (G0) with XY movement must NOT occur while pen is down
        if line.startswith("G0") and (x_match or y_match):
            assert not pen_down, f"Rapid travel G0 executed while pen was down (Z={curr_z}): {line}"


# --- 2. Negative Tests ---


def test_compiler_out_of_bounds_rejection() -> None:
    # Page with point at (300, 300) exceeds 220mm bed
    stroke = Stroke([Point(0.0, 0.0), Point(300.0, 300.0)])
    page = Page(400.0, 400.0, [CorePath([stroke])])

    compiler = GcodeCompiler(profile=test_profile, clamp_to_bed=False)
    with pytest.raises(GcodeOutOfBoundsError, match="exceeds printable envelope"):
        compiler.compile(page)

    # With clamping enabled, it should succeed
    compiler_clamped = GcodeCompiler(profile=test_profile, clamp_to_bed=True)
    gcode = compiler_clamped.compile(page)
    assert "G1 X210.000 Y210.000" in gcode


def test_invalid_machine_profiles_rejected() -> None:
    # Negative bed dimensions
    with pytest.raises(MachineProfileError, match="bed_width_mm must be positive"):
        MachineProfile(bed_width_mm=-200.0)

    # Margins exceed bed
    with pytest.raises(MachineProfileError, match="Margins exceed bed width"):
        MachineProfile(bed_width_mm=100.0, margin_left_mm=60.0, margin_right_mm=60.0)

    # z_lift <= z_write
    with pytest.raises(MachineProfileError, match=r"z_lift_mm .* must be strictly greater"):
        MachineProfile(z_lift_mm=0.5, z_write_mm=0.5)

    # z_write < safety minimum
    with pytest.raises(MachineProfileError, match="cannot be less than safety floor"):
        MachineProfile(z_write_mm=0.05, z_write_min_mm=0.1)


# --- 3. Golden G-code Tests on 3 Fixed Pages ---


def test_golden_pages_reproducibility(tmp_path: Path) -> None:
    # Page 1: Single line
    s1 = Stroke([Point(10.0, 10.0), Point(50.0, 10.0)])
    page1 = Page(148.0, 210.0, [CorePath([s1], label="line")])

    # Page 2: Square box
    box_pts = [
        Point(20.0, 20.0),
        Point(60.0, 20.0),
        Point(60.0, 60.0),
        Point(20.0, 60.0),
        Point(20.0, 20.0),
    ]
    s2 = Stroke(box_pts)
    page2 = Page(148.0, 210.0, [CorePath([s2], label="box")])

    # Page 3: Two separate strokes (lifting in between)
    s3_a = Stroke([Point(10.0, 10.0), Point(20.0, 20.0)])
    s3_b = Stroke([Point(30.0, 30.0), Point(40.0, 40.0)])
    page3 = Page(148.0, 210.0, [CorePath([s3_a, s3_b], label="diag")])

    compiler = GcodeCompiler(profile=test_profile, paper_origin_x_mm=15.0, paper_origin_y_mm=15.0)

    gcode1 = compiler.compile(page1)
    gcode2 = compiler.compile(page2)
    gcode3 = compiler.compile(page3)

    golden_dir = Path("tests/golden/gcode")
    golden_dir.mkdir(parents=True, exist_ok=True)

    f1 = golden_dir / "golden_page1.gcode"
    f2 = golden_dir / "golden_page2.gcode"
    f3 = golden_dir / "golden_page3.gcode"

    if not f1.exists():
        f1.write_text(gcode1, encoding="utf-8")
        f2.write_text(gcode2, encoding="utf-8")
        f3.write_text(gcode3, encoding="utf-8")

    assert gcode1 == f1.read_text(encoding="utf-8")
    assert gcode2 == f2.read_text(encoding="utf-8")
    assert gcode3 == f3.read_text(encoding="utf-8")


# --- 4. Throughput Benchmark (>= 20k segments/s) ---


def test_compiler_throughput_benchmark() -> None:
    # Build 25,000 segments
    pts = [Point(float(i % 100), float((i // 100) % 100)) for i in range(25001)]
    stroke = Stroke(pts)
    page = Page(148.0, 210.0, [CorePath([stroke])])

    compiler = GcodeCompiler(profile=test_profile, clamp_to_bed=True)

    t0 = time.perf_counter()
    gcode = compiler.compile(page)
    elapsed = time.perf_counter() - t0

    segments = len(pts) - 1
    throughput = segments / elapsed

    print(f"\nThroughput: {throughput:,.0f} segments/sec ({segments} segments in {elapsed:.4f}s)")
    assert throughput >= 20000.0, f"Throughput {throughput:,.0f} segments/s below 20,000 threshold"
    assert len(gcode) > 0


def test_toml_profile_loader() -> None:
    profile = MachineProfile.from_toml_file("machine-profiles/ender3pro.toml")
    assert profile.name == "Ender 3 Pro (Pen Plotter)"
    assert profile.bed_width_mm == 235.0
    assert profile.bed_height_mm == 235.0
    assert profile.z_lift_mm == 3.5
    assert profile.z_write_mm == 0.5
    assert profile.usable_width_mm == 215.0


def test_emit_line_numbers_and_checksums() -> None:
    s = Stroke([Point(10.0, 10.0), Point(20.0, 20.0)])
    page = Page(100.0, 100.0, [CorePath([s])])
    compiler = GcodeCompiler(profile=test_profile, emit_line_numbers=True)
    gcode = compiler.compile(page)

    numbered_lines = [line for line in gcode.splitlines() if line.startswith("N")]
    assert len(numbered_lines) > 5
    for line in numbered_lines:
        assert "*" in line, f"Line missing checksum: {line}"
        cmd_part, cs_part = line.split("*", 1)
        expected_cs = 0
        for ch in cmd_part:
            expected_cs ^= ord(ch)
        assert int(cs_part) == expected_cs, f"Checksum invalid on: {line}"
