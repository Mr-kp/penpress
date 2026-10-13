"""Unit tests validating ground truth consistency and integrity of synthetic fixtures."""

from __future__ import annotations

import json
from pathlib import Path

from PIL import Image


def test_equations_corpus_integrity() -> None:
    """Verify equations corpus contains at least 120 valid categorized equations."""
    eq_file = Path("tests/fixtures/equations.jsonl")
    assert eq_file.exists(), f"Missing {eq_file}"

    lines = [line.strip() for line in eq_file.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len(lines) >= 120, f"Expected >= 120 equations, got {len(lines)}"

    categories: set[str] = set()
    difficulties: set[int] = set()
    for line in lines:
        data = json.loads(line)
        assert "id" in data
        assert "category" in data
        assert "difficulty" in data
        assert "latex" in data
        categories.add(data["category"])
        difficulties.add(data["difficulty"])
        assert len(data["latex"]) > 0

    assert len(categories) >= 6, f"Expected at least 6 categories, got {len(categories)}"
    assert {1, 2, 3}.issubset(difficulties)


def test_sample_sheets_ground_truth_consistency() -> None:
    """Verify sample sheets contain valid cell annotations and ink inside bounding boxes."""
    sheet_pngs = sorted(Path("tests/fixtures").glob("sample_sheet_*.png"))
    assert len(sheet_pngs) >= 4, f"Expected at least 4 sample sheet fonts, found {len(sheet_pngs)}"

    for png_p in sheet_pngs:
        json_p = png_p.with_suffix(".json")
        assert json_p.exists(), f"Missing ground truth JSON {json_p}"

        gt_data = json.loads(json_p.read_text(encoding="utf-8"))
        assert "cells" in gt_data
        cells = gt_data["cells"]
        assert len(cells) >= 50

        # Open image and verify ink exists inside cell bounding boxes
        with Image.open(png_p) as img:
            gray = img.convert("L")
            # Sample first 5 cells
            for cell in cells[:5]:
                x0, y0, x1, y1 = cell["box_px"]
                crop = gray.crop((x0, y0, x1, y1))
                min_pixel, _max_pixel = crop.getextrema()
                # If dark ink is drawn on light paper, min_pixel will be distinctly lower than 200
                assert min_pixel < 120, f"Cell '{cell['label']}' in {png_p.name} does not contain dark ink"


def test_bed_scenes_ground_truth_corners() -> None:
    """Verify bed scene ground truth corners are located within image dimensions."""
    scene_pngs = sorted(Path("tests/fixtures").glob("bed_scene_*.png"))
    assert len(scene_pngs) >= 3, f"Expected at least 3 bed scenes, found {len(scene_pngs)}"

    for png_p in scene_pngs:
        json_p = png_p.with_suffix(".json")
        assert json_p.exists(), f"Missing scene JSON {json_p}"

        gt_data = json.loads(json_p.read_text(encoding="utf-8"))
        assert "paper_corners_bed_mm" in gt_data
        assert "paper_corners_image_px" in gt_data
        corners_mm = gt_data["paper_corners_bed_mm"]
        corners_px = gt_data["paper_corners_image_px"]

        assert len(corners_mm) == 4
        assert len(corners_px) == 4

        # Validate corners are within bed limits [0..235 mm]
        for bx, by in corners_mm:
            assert 0.0 <= bx <= 235.0, f"Bed mm corner ({bx}, {by}) outside [0..235]"
            assert 0.0 <= by <= 235.0, f"Bed mm corner ({bx}, {by}) outside [0..235]"

        # Validate corners are inside image resolution
        with Image.open(png_p) as img:
            w, h = img.size
            for px, py in corners_px:
                assert 0.0 <= px <= w
                assert 0.0 <= py <= h


def test_negative_fixtures_exist() -> None:
    """Verify all 4 required negative fixtures exist."""
    fixtures_dir = Path("tests/fixtures")
    assert (fixtures_dir / "negative_blank_page.png").exists()
    assert (fixtures_dir / "negative_missing_corner.png").exists()
    assert (fixtures_dir / "negative_paper_out_of_frame.png").exists()
    assert (fixtures_dir / "negative_glare_corner.png").exists()
