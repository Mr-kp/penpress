"""Additional targeted unit tests to achieve >= 95% coverage on penpress.core."""

from __future__ import annotations

import pytest

from penpress.core import (
    BoundingBox,
    CoreGeometryError,
    Page,
    Path,
    Point,
    Stroke,
    Transform2D,
    resample_points,
)


def test_bounding_box_nan_and_inf() -> None:
    with pytest.raises(CoreGeometryError, match="BoundingBox coordinates must be finite"):
        BoundingBox(float("nan"), 0.0, 10.0, 10.0)
    with pytest.raises(CoreGeometryError, match="BoundingBox coordinates must be finite"):
        BoundingBox(0.0, float("inf"), 10.0, 10.0)


def test_transform_nan_and_identity() -> None:
    with pytest.raises(CoreGeometryError, match="Transform2D parameters must be finite"):
        Transform2D(float("nan"), 0.0, 0.0, 1.0, 0.0, 0.0)
    ident = Transform2D.identity()
    pt = Point(12.3, 45.6)
    pt_ident = ident.apply(pt)
    assert pt_ident.x == pt.x
    assert pt_ident.y == pt.y


def test_resample_points_single_or_empty() -> None:
    assert resample_points([], 1.0) == []
    p = Point(1.0, 1.0)
    assert resample_points([p], 1.0) == [p]


def test_stroke_from_dict_errors() -> None:
    with pytest.raises(CoreGeometryError, match="Stroke data must be a dict"):
        Stroke.from_dict("invalid")  # type: ignore[arg-type]
    with pytest.raises(CoreGeometryError, match="Stroke dict missing 'pts' list"):
        Stroke.from_dict({"pts": "not-a-list"})  # type: ignore[arg-type]


def test_path_from_dict_and_simplify() -> None:
    s = Stroke([Point(0.0, 0.0), Point(5.0, 0.0), Point(10.0, 0.0)])
    p = Path([s], label="test")
    p_simplified = p.simplify(0.1)
    assert len(p_simplified.strokes[0].points) == 2
    assert p_simplified.label == "test"

    with pytest.raises(CoreGeometryError, match="Path data must be a dict"):
        Path.from_dict("invalid")  # type: ignore[arg-type]
    with pytest.raises(CoreGeometryError, match="Path dict missing 'strokes' list"):
        Path.from_dict({"strokes": "not-a-list"})  # type: ignore[arg-type]
    with pytest.raises(CoreGeometryError, match="Path 'label' must be a string"):
        Path.from_dict({"strokes": [s.to_dict()], "label": 123})  # type: ignore[arg-type]


def test_page_bounds_non_empty_and_transform() -> None:
    s = Stroke([Point(10.0, 10.0), Point(20.0, 20.0)])
    path = Path([s])
    page = Page(148.0, 210.0, [path])
    bounds = page.bounds
    assert bounds is not None
    assert bounds.min_x == 10.0
    assert bounds.min_y == 10.0
    assert bounds.max_x == 20.0
    assert bounds.max_y == 20.0

    page_t = page.transform(Transform2D.translation(5.0, 5.0))
    assert page_t.bounds is not None
    assert page_t.bounds.min_x == 15.0
    assert page_t.bounds.max_x == 25.0


def test_page_from_dict_validation_errors() -> None:
    with pytest.raises(CoreGeometryError, match="Page data must be a dict"):
        Page.from_dict("invalid")  # type: ignore[arg-type]
    with pytest.raises(CoreGeometryError, match="missing required 'schema_version'"):
        Page.from_dict({"width_mm": 100.0, "height_mm": 100.0})
    with pytest.raises(CoreGeometryError, match="Page dict missing 'width_mm' or 'height_mm'"):
        Page.from_dict({"schema_version": 1, "width_mm": 100.0})
    with pytest.raises(CoreGeometryError, match="Page 'paths' must be a list"):
        Page.from_dict({"schema_version": 1, "width_mm": 100.0, "height_mm": 100.0, "paths": "invalid"})
