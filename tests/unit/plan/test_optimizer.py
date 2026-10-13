"""Unit tests for path optimization, traveling salesperson sort, and bed mesh Z-compensation (P6-1).

Tests:
1. Non-drawing pen-up travel distance reduction >= 35% on synthetic document patterns.
2. Stroke reversal chooses shortest jump between end-of-stroke-A and start/end-of-stroke-B.
3. Bed mesh compensation computes interpolated Z within +-0.01 mm of analytical plane.
4. Negative test: Zero-length strokes or NaN coordinates raise InvalidGeometryError.
5. Collinear stroke merger reduces pen-down/pen-up cycles on contiguous lines.
"""

from __future__ import annotations

import pytest

from penpress.core.primitives import CoreGeometryError, Page, Point, Stroke
from penpress.core.primitives import Path as CorePath
from penpress.plan.merger import InvalidGeometryError, merge_collinear_strokes
from penpress.plan.mesh_comp import BedMeshCompensator, BedMeshGrid, MeshInterpolationError
from penpress.plan.optimizer import ToolpathOptimizer


def test_travel_distance_reduction_ge_35_percent() -> None:
    # Construct document layout with scattered lines across multiple paragraphs (large back-and-forth jumps)
    # Naive order: jumps between distant columns/lines
    strokes: list[Stroke] = []
    # Grid of short strokes ordered in worst-case interlaced column order
    for col in range(5):
        for row in range(10):
            # Interlaced jump: alternate between top and bottom
            y = row * 15.0 if col % 2 == 0 else (9 - row) * 15.0
            x = col * 30.0
            strokes.append(Stroke([Point(x, y), Point(x + 20.0, y)]))

    # Scramble stroke order to simulate unoptimized block fragments
    naive_strokes: list[Stroke] = []
    # Interleave early strokes with late strokes
    for i in range(len(strokes) // 2):
        naive_strokes.append(strokes[i])
        naive_strokes.append(strokes[-(i + 1)])

    optimizer = ToolpathOptimizer(allow_stroke_flip=True, merge_collinear=True)
    optimized_strokes, stats = optimizer.optimize_strokes(naive_strokes)

    assert len(optimized_strokes) == len(naive_strokes)
    assert stats.distance_reduction_pct >= 35.0, (
        f"Expected travel reduction >= 35%, got {stats.distance_reduction_pct:.1f}% "
        f"(before: {stats.travel_distance_before_mm:.1f} mm, after: {stats.travel_distance_after_mm:.1f} mm)"
    )


def test_stroke_reversal_chooses_shortest_jump() -> None:
    # Stroke A: (0, 0) -> (10, 0)
    # Stroke B: (10, 2) -> (0, 2) (starts at x=10, right near A's end)
    # Stroke C: (0, 4) -> (10, 4)
    sA = Stroke([Point(0.0, 0.0), Point(10.0, 0.0)])
    # In naive orientation, sB ends at (0, 2), but if we consider a stroke going from (0, 2) to (10, 2),
    # jumping to its end (10, 2) is distance 2.0 mm, while jumping to its start (0, 2) is distance ~10.2 mm.
    sB_inverted = Stroke([Point(0.0, 2.0), Point(10.0, 2.0)])

    optimizer = ToolpathOptimizer(allow_stroke_flip=True, merge_collinear=False, max_2opt_iterations=0)
    optimized, stats = optimizer.optimize_strokes([sA, sB_inverted])

    assert len(optimized) == 2
    # The second stroke should be flipped so its starting point is (10, 2), minimizing jump from (10, 0)
    assert optimized[1].points[0].x == 10.0
    assert optimized[1].points[0].y == 2.0
    assert stats.reversed_stroke_count >= 1


def test_bed_mesh_compensation_analytical_plane() -> None:
    # Define an analytical plane: z = 0.5 + 0.002 * x - 0.003 * y
    slope_x = 0.002
    slope_y = -0.003
    z_origin = 0.5

    mesh = BedMeshGrid.from_analytical_plane(
        x_min=0.0,
        x_max=200.0,
        y_min=0.0,
        y_max=200.0,
        x_count=5,
        y_count=5,
        slope_x=slope_x,
        slope_y=slope_y,
        z_origin=z_origin,
    )
    compensator = BedMeshCompensator(mesh)

    # Test arbitrary test coordinates inside mesh
    test_coords = [
        (25.4, 38.7),
        (100.0, 100.0),
        (173.2, 84.1),
        (5.0, 195.0),
    ]

    for x, y in test_coords:
        nominal_z = 0.2
        expected_z = nominal_z + (z_origin + slope_x * x + slope_y * y)
        actual_z = compensator.compute_compensated_z(x, y, nominal_z)
        assert abs(actual_z - expected_z) <= 0.01, (
            f"At ({x}, {y}): expected Z {expected_z:.4f}, got {actual_z:.4f} (error > 0.01 mm)"
        )


def test_negative_zero_length_stroke_raises_invalid_geometry_error() -> None:
    # Stroke with coincident points has 0 length
    with pytest.raises(InvalidGeometryError, match="zero length"):
        s = Stroke([Point(10.0, 10.0), Point(10.0, 10.0)])
        optimizer = ToolpathOptimizer()
        optimizer.optimize_strokes([s])


def test_negative_nan_coordinate_raises_geometry_error() -> None:
    # Point with NaN raises CoreGeometryError or InvalidGeometryError during creation/validation
    with pytest.raises(CoreGeometryError, match="finite numbers"):
        Point(float("nan"), 10.0)


def test_collinear_stroke_merger() -> None:
    # Two collinear segments: (0, 0) -> (5, 0) and (5.05, 0) -> (10, 0) (gap 0.05 mm < 0.15 mm)
    s1 = Stroke([Point(0.0, 0.0), Point(5.0, 0.0)])
    s2 = Stroke([Point(5.05, 0.0), Point(10.0, 0.0)])
    # Non-collinear stroke far away
    s3 = Stroke([Point(20.0, 20.0), Point(30.0, 20.0)])

    merged = merge_collinear_strokes([s1, s2, s3], distance_tolerance_mm=0.15)
    assert len(merged) == 2
    # First stroke merged into a single stroke from 0 to 10
    assert merged[0].points[0].x == 0.0
    assert merged[0].points[-1].x == 10.0
    assert merged[1].points[0].x == 20.0


def test_page_optimization_wrapper() -> None:
    s1 = Stroke([Point(0.0, 0.0), Point(10.0, 0.0)])
    s2 = Stroke([Point(10.1, 0.0), Point(20.0, 0.0)])
    page = Page(width_mm=148.0, height_mm=210.0, paths=[CorePath([s1, s2])])

    optimizer = ToolpathOptimizer(allow_stroke_flip=True, merge_collinear=True)
    opt_page, stats = optimizer.optimize_page(page)

    assert opt_page.width_mm == 148.0
    assert opt_page.height_mm == 210.0
    assert len(opt_page.paths) == 1
    assert stats.stroke_count_after == 1  # merged into 1 continuous stroke


def test_bed_mesh_edge_cases_and_compensator() -> None:
    # Invalid grid size
    with pytest.raises(MeshInterpolationError, match="at least 2x2"):
        BedMeshGrid(x_min_mm=0.0, x_max_mm=10.0, y_min_mm=0.0, y_max_mm=10.0, x_count=1, y_count=2)

    # Invalid bounds
    with pytest.raises(MeshInterpolationError, match="Invalid mesh bounds"):
        BedMeshGrid(
            x_min_mm=10.0,
            x_max_mm=0.0,
            y_min_mm=0.0,
            y_max_mm=10.0,
            x_count=2,
            y_count=2,
            z_values=(0.0, 0.0, 0.0, 0.0),
        )

    # Size mismatch
    with pytest.raises(MeshInterpolationError, match="Expected 4 Z mesh values"):
        BedMeshGrid(
            x_min_mm=0.0,
            x_max_mm=10.0,
            y_min_mm=0.0,
            y_max_mm=10.0,
            x_count=2,
            y_count=2,
            z_values=(0.0, 0.0),
        )

    # Non-finite Z
    with pytest.raises(MeshInterpolationError, match="must be finite"):
        BedMeshGrid(
            x_min_mm=0.0,
            x_max_mm=10.0,
            y_min_mm=0.0,
            y_max_mm=10.0,
            x_count=2,
            y_count=2,
            z_values=(0.0, float("nan"), 0.0, 0.0),
        )

    grid = BedMeshGrid(
        x_min_mm=0.0,
        x_max_mm=100.0,
        y_min_mm=0.0,
        y_max_mm=100.0,
        x_count=2,
        y_count=2,
        z_values=(0.1, 0.2, 0.3, 0.4),
    )
    # Out of bounds with clamp_boundary=False
    with pytest.raises(MeshInterpolationError, match="outside mesh boundaries"):
        grid.interpolate_z(-10.0, 50.0, clamp_boundary=False)

    # Out of bounds with clamp_boundary=True
    z_clamped = grid.interpolate_z(-10.0, 0.0, clamp_boundary=True)
    assert abs(z_clamped - 0.1) < 1e-4

    # Compensate stroke
    comp = BedMeshCompensator(grid)
    stroke = Stroke([Point(0.0, 0.0), Point(100.0, 100.0)])
    z_pts = comp.compensate_stroke(stroke, base_z_mm=0.5)
    assert len(z_pts) == 2
    assert abs(z_pts[0][1] - 0.6) < 1e-4
    assert abs(z_pts[1][1] - 0.9) < 1e-4


def test_optimizer_empty_and_single_stroke() -> None:
    optimizer = ToolpathOptimizer()
    strokes_empty, stats_empty = optimizer.optimize_strokes([])
    assert len(strokes_empty) == 0
    assert stats_empty.travel_distance_before_mm == 0.0

    s = Stroke([Point(0.0, 0.0), Point(10.0, 10.0)])
    strokes_single, _stats_single = optimizer.optimize_strokes([s])
    assert len(strokes_single) == 1
