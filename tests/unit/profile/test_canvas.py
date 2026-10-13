"""Unit tests for Interactive Canvas and Tablet Stroke Capture Studio (P2-2).

Verifies online pointer event ingestion, multi-stroke character preservation,
completeness and quality gating, negative scribble rejection, and zero-egress network isolation.
"""

from __future__ import annotations

import math
import socket
from collections.abc import Generator
from contextlib import contextmanager

import pytest

from penpress.core.primitives import Point, Stroke
from penpress.profile.canvas_capture import (
    CanvasCaptureError,
    CanvasStrokeSession,
    RawPointerEvent,
    populate_profile_from_canvas_bank,
)
from penpress.profile.models import HandwritingProfile
from penpress.profile.quality import (
    STANDARD_ALPHANUMERIC,
    QualityThresholdError,
    audit_profile_quality,
    compute_stroke_smoothness,
    evaluate_glyph_quality,
)


@contextmanager
def network_egress_guard() -> Generator[None, None, None]:
    """Audit guard asserting zero outbound network calls occur during code execution."""
    orig_connect = socket.socket.connect

    def blocked_connect(*args: object, **kwargs: object) -> None:
        raise AssertionError("Network egress attempted: socket.connect was invoked!")

    socket.socket.connect = blocked_connect  # type: ignore[assignment]
    try:
        yield
    finally:
        socket.socket.connect = orig_connect  # type: ignore[assignment]


def test_canvas_single_stroke_normalization() -> None:
    session = CanvasStrokeSession(scale_mm_per_unit=0.2, invert_y=True)

    raw_events = [
        {"x": 10.0, "y": 20.0, "time_ms": 100.0, "pressure": 0.4},
        {"x": 15.0, "y": 25.0, "time_ms": 150.0, "pressure": 0.6},
        {"x": 20.0, "y": 30.0, "time_ms": 200.0, "pressure": 0.8},
    ]

    stroke, kinematics = session.process_raw_stroke(raw_events)

    assert isinstance(stroke, Stroke)
    assert len(stroke.points) == 3
    # Coordinates in mm: x = 10 * 0.2 = 2.0 mm, y = -20 * 0.2 = -4.0 mm
    assert pytest.approx(stroke.points[0].x) == 2.0
    assert pytest.approx(stroke.points[0].y) == -4.0
    assert pytest.approx(stroke.points[0].pressure) == 0.4
    assert pytest.approx(stroke.points[0].time_offset) == 0.0

    # Timestamp offset at last point: (200 - 100) ms = 0.1 s
    assert pytest.approx(stroke.points[2].time_offset) == 0.1

    # Kinematics velocity check
    assert len(kinematics) == 3
    assert kinematics[1].speed_mm_s > 0.0


def test_canvas_multi_stroke_character_separation() -> None:
    session = CanvasStrokeSession(scale_mm_per_unit=0.1, invert_y=True)

    # Multi-stroke 'E': 4 strokes (1 vertical spine + 3 horizontal bars)
    spine = [
        {"x": 0.0, "y": 0.0, "time_ms": 0.0, "pressure": 0.5},
        {"x": 0.0, "y": 50.0, "time_ms": 100.0, "pressure": 0.5},
    ]
    top_bar = [
        {"x": 0.0, "y": 0.0, "time_ms": 150.0, "pressure": 0.5},
        {"x": 30.0, "y": 0.0, "time_ms": 200.0, "pressure": 0.5},
    ]
    mid_bar = [
        {"x": 0.0, "y": 25.0, "time_ms": 250.0, "pressure": 0.5},
        {"x": 20.0, "y": 25.0, "time_ms": 300.0, "pressure": 0.5},
    ]
    bot_bar = [
        {"x": 0.0, "y": 50.0, "time_ms": 350.0, "pressure": 0.5},
        {"x": 30.0, "y": 50.0, "time_ms": 400.0, "pressure": 0.5},
    ]

    strokes = session.process_glyph_drawing([spine, top_bar, mid_bar, bot_bar], normalize_origin=True)

    # Must preserve exactly 4 separate strokes without flattening
    assert len(strokes) == 4
    for st in strokes:
        assert isinstance(st, Stroke)
        assert len(st.points) >= 2

    # Origin normalized: min_x should be 0.0, min_y should be 0.0
    all_x = [p.x for s in strokes for p in s.points]
    all_y = [p.y for s in strokes for p in s.points]
    assert pytest.approx(min(all_x)) == 0.0
    assert pytest.approx(min(all_y)) == 0.0


def test_multi_stroke_character_t_and_i() -> None:
    session = CanvasStrokeSession()

    # 'i': stem + dot (dot represented as small 2-point tap)
    stem = [
        {"x": 10.0, "y": 20.0, "time_ms": 0.0},
        {"x": 10.0, "y": 40.0, "time_ms": 50.0},
    ]
    dot = [
        {"x": 10.0, "y": 10.0, "time_ms": 100.0},
        {"x": 10.1, "y": 10.1, "time_ms": 110.0},
    ]

    strokes_i = session.process_glyph_drawing([stem, dot])
    assert len(strokes_i) == 2


def test_completeness_score_100_percent() -> None:
    # Build complete profile with all A-Z, a-z, 0-9
    profile = HandwritingProfile(
        profile_id="complete_user",
        user_name="Bob",
        created_at="2026-10-13T00:00:00Z",
    )

    # Build smooth stroke arc (e.g. circle/semicircle arc)
    arc_pts = [Point(2.0 + 2.0 * math.cos(i * 0.3), 2.0 + 2.0 * math.sin(i * 0.3)) for i in range(10)]
    for c in STANDARD_ALPHANUMERIC:
        # Create a valid stroke variant for each
        s = Stroke(arc_pts)
        profile.add_glyph_variant(c, [s])

    report = audit_profile_quality(profile, min_alphanumeric_completeness=100.0)

    assert report.alphanumeric_completeness == 100.0
    assert len(report.missing_alphanumeric) == 0
    assert report.total_unique_glyphs == len(STANDARD_ALPHANUMERIC)
    assert report.passed is True


def test_quality_gating_rejects_empty_and_micro_scribbles() -> None:
    # Negative test: profile with degenerate micro scribble
    profile = HandwritingProfile(profile_id="bad_user", user_name="Eve", created_at="2026-10-13T00:00:00Z")

    # Degenerate scribble of microscopic length (< 0.05 mm)
    micro_stroke = Stroke([Point(0.0, 0.0), Point(0.01, 0.01)])
    profile.add_glyph_variant("A", [micro_stroke])

    score = evaluate_glyph_quality("A", profile.get_glyph_variants("A"))
    assert score.is_valid is False
    assert any("below threshold" in r or "degenerate" in r for r in score.failure_reasons)

    # audit_profile_quality with strict_raise must raise QualityThresholdError
    with pytest.raises(QualityThresholdError) as exc_info:
        audit_profile_quality(profile, strict_raise=True)
    assert "failed quality gating" in str(exc_info.value)


def test_empty_stroke_error() -> None:
    session = CanvasStrokeSession()
    with pytest.raises(CanvasCaptureError):
        session.process_raw_stroke([])


def test_invalid_raw_pointer_event() -> None:
    with pytest.raises(CanvasCaptureError):
        RawPointerEvent(x=float("nan"), y=10.0, time_ms=0.0)

    with pytest.raises(CanvasCaptureError):
        RawPointerEvent(x=10.0, y=10.0, time_ms=-5.0)

    with pytest.raises(CanvasCaptureError):
        RawPointerEvent(x=10.0, y=10.0, time_ms=0.0, pressure=1.5)


def test_zero_egress_during_profile_creation_and_audit() -> None:
    with network_egress_guard():
        raw_bank = {
            "A": [
                [
                    [
                        {"x": 0.0, "y": 0.0, "time_ms": 0.0, "pressure": 0.5},
                        {"x": 10.0, "y": 30.0, "time_ms": 50.0, "pressure": 0.6},
                    ],
                    [
                        {"x": 10.0, "y": 30.0, "time_ms": 60.0, "pressure": 0.6},
                        {"x": 20.0, "y": 0.0, "time_ms": 100.0, "pressure": 0.5},
                    ],
                ]
            ]
        }
        profile = populate_profile_from_canvas_bank(
            profile_id="offline_user",
            user_name="Offline User",
            glyph_bank_data=raw_bank,
        )
        assert profile.total_glyphs == 1
        assert "A" in profile.glyph_bank

        report = audit_profile_quality(profile, min_alphanumeric_completeness=1.0)
        assert report.total_unique_glyphs == 1


def test_smoothness_scoring_metric() -> None:
    # Smooth line
    smooth_stroke = Stroke([Point(float(i), float(i)) for i in range(10)])
    smooth_val = compute_stroke_smoothness(smooth_stroke)
    assert pytest.approx(smooth_val, rel=1e-3) == 1.0

    # Highly erratic zig-zag
    zigzag_pts = []
    for i in range(20):
        y = 5.0 if i % 2 == 1 else -5.0
        zigzag_pts.append(Point(float(i), y))
    zigzag_stroke = Stroke(zigzag_pts)
    zigzag_val = compute_stroke_smoothness(zigzag_stroke)
    assert zigzag_val < 0.3
