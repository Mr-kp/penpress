"""Unit and property-based tests for penpress.core."""

from __future__ import annotations

import json
import math

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from penpress.core import (
    CURRENT_SCHEMA_VERSION,
    BoundingBox,
    CoreGeometryError,
    Page,
    Path,
    Point,
    Stroke,
    Transform2D,
    get_schema,
    page_from_json,
    page_to_json,
    resample_points,
    simplify_rdp,
)

# Strategies
finite_floats = st.floats(
    min_value=-1000.0,
    max_value=1000.0,
    allow_nan=False,
    allow_infinity=False,
)
positive_floats = st.floats(
    min_value=0.1,
    max_value=1000.0,
    allow_nan=False,
    allow_infinity=False,
)
point_strategy = st.builds(
    Point,
    x=finite_floats,
    y=finite_floats,
    pressure=st.one_of(st.none(), st.floats(min_value=0.0, max_value=1.0)),
    time_offset=st.one_of(st.none(), st.floats(min_value=0.0, max_value=100.0)),
)
stroke_strategy = st.lists(point_strategy, min_size=2, max_size=20).map(Stroke)
path_strategy = st.builds(
    Path,
    strokes=st.lists(stroke_strategy, min_size=1, max_size=5),
    label=st.one_of(st.none(), st.text(min_size=1, max_size=10)),
)
page_strategy = st.builds(
    Page,
    width_mm=st.floats(min_value=50.0, max_value=500.0),
    height_mm=st.floats(min_value=50.0, max_value=500.0),
    paths=st.lists(path_strategy, min_size=0, max_size=5),
)


# --- 1. Point Tests & Negative Checks ---


def test_point_valid() -> None:
    pt = Point(10.5, 20.2, pressure=0.8, time_offset=1.5)
    assert pt.x == 10.5
    assert pt.y == 20.2
    assert pt.pressure == 0.8
    assert pt.time_offset == 1.5
    d = pt.to_dict()
    assert d == {"x": 10.5, "y": 20.2, "p": 0.8, "t": 1.5}
    pt2 = Point.from_dict(d)
    assert pt == pt2


@pytest.mark.parametrize(
    "x, y, p, t",
    [
        (float("nan"), 10.0, None, None),
        (10.0, float("nan"), None, None),
        (float("inf"), 10.0, None, None),
        (10.0, float("-inf"), None, None),
        (10.0, 10.0, -0.1, None),
        (10.0, 10.0, 1.1, None),
        (10.0, 10.0, None, -0.5),
        (10.0, 10.0, float("nan"), None),
        (10.0, 10.0, None, float("inf")),
    ],
)
def test_point_invalid_coordinates(x: float, y: float, p: float | None, t: float | None) -> None:
    with pytest.raises(CoreGeometryError):
        Point(x=x, y=y, pressure=p, time_offset=t)


def test_point_from_dict_invalid() -> None:
    with pytest.raises(CoreGeometryError):
        Point.from_dict({"x": 1.0})  # type: ignore[arg-type]
    with pytest.raises(CoreGeometryError):
        Point.from_dict("invalid")  # type: ignore[arg-type]


# --- 2. BoundingBox Tests ---


def test_bounding_box_valid() -> None:
    bb = BoundingBox(10.0, 20.0, 50.0, 80.0)
    assert bb.width == 40.0
    assert bb.height == 60.0
    assert bb.contains_point(Point(25.0, 50.0))
    assert not bb.contains_point(Point(5.0, 50.0))
    d = bb.to_dict()
    assert BoundingBox.from_dict(d) == bb


def test_bounding_box_invalid() -> None:
    with pytest.raises(CoreGeometryError):
        BoundingBox(50.0, 20.0, 10.0, 80.0)  # min_x > max_x
    with pytest.raises(CoreGeometryError):
        BoundingBox(10.0, 90.0, 50.0, 80.0)  # min_y > max_y
    with pytest.raises(CoreGeometryError):
        BoundingBox.from_dict("not_a_dict")  # type: ignore[arg-type]


# --- 3. Transform2D Property Tests ---


@given(
    t1_tx=finite_floats,
    t1_ty=finite_floats,
    t1_angle=st.floats(min_value=-math.pi, max_value=math.pi),
    t2_tx=finite_floats,
    t2_ty=finite_floats,
    t2_angle=st.floats(min_value=-math.pi, max_value=math.pi),
    pt=point_strategy,
)
def test_transform_composition_property(
    t1_tx: float,
    t1_ty: float,
    t1_angle: float,
    t2_tx: float,
    t2_ty: float,
    t2_angle: float,
    pt: Point,
) -> None:
    t1 = Transform2D.translation(t1_tx, t1_ty).compose(Transform2D.rotation(t1_angle))
    t2 = Transform2D.translation(t2_tx, t2_ty).compose(Transform2D.rotation(t2_angle))
    composed = t2.compose(t1)

    pt_stepwise = t2.apply(t1.apply(pt))
    pt_composed = composed.apply(pt)

    assert math.isclose(pt_stepwise.x, pt_composed.x, abs_tol=1e-7)
    assert math.isclose(pt_stepwise.y, pt_composed.y, abs_tol=1e-7)


@given(
    scale_x=st.floats(min_value=0.1, max_value=10.0),
    scale_y=st.floats(min_value=0.1, max_value=10.0),
    tx=finite_floats,
    ty=finite_floats,
    angle=st.floats(min_value=-math.pi, max_value=math.pi),
    pt=point_strategy,
)
def test_transform_inverse_roundtrip(
    scale_x: float,
    scale_y: float,
    tx: float,
    ty: float,
    angle: float,
    pt: Point,
) -> None:
    t = (
        Transform2D.translation(tx, ty)
        .compose(Transform2D.rotation(angle))
        .compose(Transform2D.scale(scale_x, scale_y))
    )
    t_inv = t.inverse()

    pt_transformed = t.apply(pt)
    pt_restored = t_inv.apply(pt_transformed)

    assert math.isclose(pt.x, pt_restored.x, abs_tol=1e-6)
    assert math.isclose(pt.y, pt_restored.y, abs_tol=1e-6)


def test_transform_singular_invert() -> None:
    singular = Transform2D(1.0, 0.0, 1.0, 0.0, 0.0, 0.0)  # det = 0
    with pytest.raises(CoreGeometryError, match="Cannot invert singular transform"):
        singular.inverse()


def test_transform_from_dict_and_to_dict() -> None:
    t = Transform2D(1.5, 0.2, -0.3, 2.0, 10.0, -5.0)
    d = t.to_dict()
    t_reconstructed = Transform2D.from_dict(d)
    assert t == t_reconstructed
    with pytest.raises(CoreGeometryError):
        Transform2D.from_dict("invalid")  # type: ignore[arg-type]


# --- 4. Stroke & Bounds Properties ---


@given(stroke=stroke_strategy)
def test_stroke_bounds_contain_all_points(stroke: Stroke) -> None:
    bb = stroke.bounds
    for pt in stroke.points:
        assert bb.contains_point(pt, tolerance=1e-9)


def test_stroke_empty_or_single_point_rejected() -> None:
    with pytest.raises(CoreGeometryError, match="Stroke requires at least 2 points"):
        Stroke([])
    with pytest.raises(CoreGeometryError, match="Stroke requires at least 2 points"):
        Stroke([Point(0.0, 0.0)])


# --- 5. Ramer-Douglas-Peucker Simplification Tests ---


def test_rdp_collinear_simplification() -> None:
    # 5 points strictly along a straight line y = 2x
    pts = [Point(float(i), float(2 * i)) for i in range(5)]
    simplified = simplify_rdp(pts, epsilon=0.01)
    assert len(simplified) == 2
    assert simplified[0] == pts[0]
    assert simplified[-1] == pts[-1]


@given(
    stroke=stroke_strategy,
    epsilon=st.floats(min_value=0.01, max_value=10.0),
)
def test_rdp_deviation_property(stroke: Stroke, epsilon: float) -> None:
    simplified = stroke.simplify(epsilon=epsilon)
    assert len(simplified.points) >= 2
    assert simplified.points[0] == stroke.points[0]
    assert simplified.points[-1] == stroke.points[-1]


def test_rdp_invalid_epsilon() -> None:
    pts = [Point(0.0, 0.0), Point(1.0, 1.0)]
    with pytest.raises(CoreGeometryError):
        simplify_rdp(pts, epsilon=-0.1)


# --- 6. Resampling Arc-Length & Endpoints Tests ---


@given(
    stroke=stroke_strategy,
    step_mm=st.floats(min_value=0.5, max_value=5.0),
)
def test_resample_endpoints_and_length_property(stroke: Stroke, step_mm: float) -> None:
    resampled = stroke.resample(step_mm=step_mm)
    assert len(resampled.points) >= 2
    # Endpoints exact match
    assert math.isclose(resampled.points[0].x, stroke.points[0].x, abs_tol=1e-9)
    assert math.isclose(resampled.points[0].y, stroke.points[0].y, abs_tol=1e-9)
    assert math.isclose(resampled.points[-1].x, stroke.points[-1].x, abs_tol=1e-9)
    assert math.isclose(resampled.points[-1].y, stroke.points[-1].y, abs_tol=1e-9)

    orig_len = stroke.length_mm
    resampled_len = resampled.length_mm
    if orig_len > 1e-4:
        # Arc length should be preserved within 0.5%
        assert math.isclose(orig_len, resampled_len, rel_tol=0.005)


def test_resample_invalid_step() -> None:
    pts = [Point(0.0, 0.0), Point(1.0, 1.0)]
    with pytest.raises(CoreGeometryError):
        resample_points(pts, step_mm=-1.0)
    with pytest.raises(CoreGeometryError):
        resample_points(pts, step_mm=0.0)


# --- 7. Path and Page Tests ---


def test_path_empty_strokes_rejected() -> None:
    with pytest.raises(CoreGeometryError, match="Path requires at least 1 Stroke"):
        Path([])


def test_path_transform_and_bounds() -> None:
    s1 = Stroke([Point(0.0, 0.0), Point(10.0, 10.0)])
    s2 = Stroke([Point(20.0, 20.0), Point(30.0, 30.0)])
    p = Path([s1, s2], label="test_glyph")
    assert p.bounds == BoundingBox(0.0, 0.0, 30.0, 30.0)
    assert p.label == "test_glyph"

    transformed = p.transform(Transform2D.translation(5.0, 5.0))
    assert transformed.bounds == BoundingBox(5.0, 5.0, 35.0, 35.0)
    assert transformed.label == "test_glyph"


def test_page_bounds_empty() -> None:
    page = Page(148.0, 210.0, [])
    assert page.bounds is None
    assert page.total_length_mm == 0.0


def test_page_invalid_dimensions() -> None:
    with pytest.raises(CoreGeometryError):
        Page(-100.0, 210.0, [])
    with pytest.raises(CoreGeometryError):
        Page(148.0, 0.0, [])


# --- 8. JSON Serialization & Round-Trip on 1000 Pages ---


@settings(max_examples=1000, deadline=None)
@given(page=page_strategy)
def test_json_roundtrip_identity_1000_pages(page: Page) -> None:
    json_str = page_to_json(page)
    deserialized = page_from_json(json_str)

    assert deserialized.schema_version == page.schema_version
    assert math.isclose(deserialized.width_mm, page.width_mm, abs_tol=1e-7)
    assert math.isclose(deserialized.height_mm, page.height_mm, abs_tol=1e-7)
    assert len(deserialized.paths) == len(page.paths)

    for p_orig, p_deser in zip(page.paths, deserialized.paths, strict=True):
        assert p_orig.label == p_deser.label
        assert len(p_orig.strokes) == len(p_deser.strokes)
        for s_orig, s_deser in zip(p_orig.strokes, p_deser.strokes, strict=True):
            assert len(s_orig.points) == len(s_deser.points)
            for pt_o, pt_d in zip(s_orig.points, s_deser.points, strict=True):
                assert math.isclose(pt_o.x, pt_d.x, abs_tol=1e-7)
                assert math.isclose(pt_o.y, pt_d.y, abs_tol=1e-7)
                if pt_o.pressure is not None:
                    assert pt_d.pressure is not None
                    assert math.isclose(pt_o.pressure, pt_d.pressure, abs_tol=1e-7)
                else:
                    assert pt_d.pressure is None


def test_json_schema_version_mismatch_negative() -> None:
    page = Page(148.0, 210.0, [])
    d = page.to_dict()
    d["schema_version"] = 999

    with pytest.raises(CoreGeometryError, match="Unsupported schema_version 999"):
        page_from_json(json.dumps(d))


def test_json_malformed_negative() -> None:
    with pytest.raises(CoreGeometryError, match="Malformed JSON"):
        page_from_json("{broken json")

    with pytest.raises(CoreGeometryError, match="Expected top-level JSON object"):
        page_from_json("[1, 2, 3]")


def test_schema_structure() -> None:
    schema = get_schema()
    assert schema["type"] == "object"
    assert "schema_version" in schema["required"]
    assert schema["properties"]["schema_version"]["const"] == CURRENT_SCHEMA_VERSION
