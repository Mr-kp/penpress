"""Tests for Handwriting Profile and Sample Sheet Ingestion (P2-1)."""

from __future__ import annotations

import json
from pathlib import Path

import cv2
import numpy as np
import pytest
from scipy.spatial.distance import cdist

from penpress.core.primitives import Point, Stroke
from penpress.profile.models import HandwritingProfile, StyleMetrics
from penpress.profile.sheet_gen import generate_sample_sheet
from penpress.profile.sheet_ingest import (
    SampleSheetIngestEngine,
    SheetAlignmentError,
    find_fiducial_markers,
    trace_cell_strokes,
)


@pytest.fixture
def tmp_dir(tmp_path: Path) -> Path:
    return tmp_path


def test_generate_sample_sheet(tmp_dir: Path) -> None:
    pdf_path = tmp_dir / "test_sample_sheet.pdf"
    meta = generate_sample_sheet(pdf_path)

    assert pdf_path.exists()
    assert pdf_path.stat().st_size > 1000
    assert meta["total_cells"] >= 52
    assert "TL" in meta["fiducials"]
    assert "BR" in meta["fiducials"]


def test_profile_serialization(tmp_dir: Path) -> None:
    profile = HandwritingProfile(
        profile_id="test_user_01",
        user_name="Alice",
        created_at="2026-10-13T12:00:00Z",
        metrics=StyleMetrics(slant_deg=2.5, baseline_jitter_mm=0.07),
    )
    s1 = Stroke([Point(0, 0), Point(5, 5), Point(10, 0)])
    profile.add_glyph_variant("A", [s1])

    json_path = tmp_dir / "profile.json"
    profile.save_json(json_path)

    loaded = HandwritingProfile.load_json(json_path)
    assert loaded.profile_id == "test_user_01"
    assert loaded.user_name == "Alice"
    assert loaded.metrics.slant_deg == 2.5
    assert loaded.total_glyphs == 1
    assert "A" in loaded.glyph_bank
    assert len(loaded.get_glyph_variants("A")[0]) == 1


def test_sheet_ingestion_on_synthetic_fixture() -> None:
    fixture_path = Path("tests/fixtures/sample_sheet_caveat.png")
    assert fixture_path.exists(), f"Caveat fixture not found: {fixture_path}"

    engine = SampleSheetIngestEngine()
    profile = engine.ingest_sheet(fixture_path)

    assert profile.total_glyphs >= 30
    assert "a" in profile.glyph_bank or "b" in profile.glyph_bank


def test_sheet_alignment_error_on_corrupted_image() -> None:
    # Blank white image should raise SheetAlignmentError
    blank_img = np.ones((800, 800), dtype=np.uint8) * 255
    with pytest.raises(SheetAlignmentError):
        find_fiducial_markers(blank_img)


def test_stroke_tracing_chamfer_accuracy() -> None:
    gt_path = Path("tests/fixtures/stroke_recovery_sample.json")
    img_path = Path("tests/fixtures/stroke_recovery_sample.png")
    assert gt_path.exists(), f"Ground truth fixture not found: {gt_path}"
    assert img_path.exists(), f"Image fixture not found: {img_path}"

    img = cv2.imread(str(img_path), cv2.IMREAD_GRAYSCALE)
    recovered = trace_cell_strokes(img, scale_mm_per_px=1.0)
    assert len(recovered) >= 1

    # Load ground truth points and convert mm to image pixels (8.0 px/mm, Y inverted from 360 px)
    gt_data = json.loads(gt_path.read_text(encoding="utf-8"))
    gt_pts = np.array([[pt["x"] * 8.0, 360.0 - pt["y"] * 8.0] for s in gt_data["strokes"] for pt in s])

    rec_pts = np.array([[p.x, p.y] for s in recovered for p in s.points])

    # Compute bidirectional mean Chamfer distance
    dists = cdist(rec_pts, gt_pts)
    p2g = np.mean(np.min(dists, axis=1))
    g2p = np.mean(np.min(dists, axis=0))
    chamfer = (p2g + g2p) / 2.0

    # Acceptance threshold <= 2.5 px
    assert chamfer <= 2.5
