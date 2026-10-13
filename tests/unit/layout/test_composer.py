"""Unit tests for Page Composer and Layout Typesetter (P5-2).

Tests:
1. Multi-page pagination fitting a 1000-word essay with equations onto A5 sheets.
2. Text baselines strictly align with simulated 7 mm ruled notebook guidelines within +-0.2 mm.
3. Zero strokes intersect the 5 mm expanded clip keep-out zone.
4. Block larger than printable bounds raises LayoutOverflowError with actionable suggestions.
5. Physical bed travel limit clamps.
"""

from __future__ import annotations

import pytest

from penpress.core.primitives import Point, Stroke
from penpress.ingest.markdown_parser import MarkdownParser
from penpress.ingest.schema import BlockType, BoundingBox, DocumentBlock, IngestedDocument, IngestedPage
from penpress.layout.composer import (
    A4_PRESET,
    A5_PRESET,
    LayoutOverflowError,
    Margins,
    PageComposer,
    PaperPreset,
    RuledGridConfig,
)
from penpress.layout.keepout import KeepoutPolygon


@pytest.fixture
def a5_composer() -> PageComposer:
    return PageComposer(
        paper=A5_PRESET,
        margins=Margins(top_mm=18.0, bottom_mm=18.0, left_mm=16.0, right_mm=16.0),
        ruled_grid=RuledGridConfig(enabled=True, line_spacing_mm=7.0, snap_tolerance_mm=0.2),
    )


def test_1000_word_essay_multi_page_pagination(a5_composer: PageComposer) -> None:
    # Generate 1000-word academic assignment with sections, paragraphs, and LaTeX equations
    sentence = "The thermodynamics of non-equilibrium systems exhibits spontaneous entropy production. "
    words_para = sentence * 15
    md_text = (
        "# Non-Equilibrium Thermodynamics and Transport Phenomena\n\n"
        "## 1. Introduction and Conservation Laws\n" + words_para + "\n\n"
        "$$\n"
        r"\frac{\partial \rho}{\partial t} + \nabla \cdot (\rho \mathbf{v}) = 0"
        "\n"
        "$$\n\n"
        "## 2. Entropy Production Balance\n" + words_para + "\n\n"
        "$$\n"
        r"\sigma = \sum_{i} J_i X_i \ge 0"
        "\n"
        "$$\n\n"
        "## 3. Onsager Reciprocal Relations\n" + words_para + "\n\n"
        "- Coefficient symmetry implies microscopic reversibility.\n"
        "- Linear response theory holds close to equilibrium.\n"
        "- Fluctuation dissipation theorem connects noise to friction.\n\n"
        "## 4. Discussion and Macroscopic Limits\n" + words_para + "\n"
    )
    parser = MarkdownParser()
    doc = parser.parse_markdown(md_text, doc_id="essay_1000")

    result = a5_composer.compose_document(doc)

    # Must paginate across multiple A5 sheets
    assert result.page_count >= 3, f"Expected >= 3 pages for 1000 words on A5, got {result.page_count}"
    assert len(result.pages) == result.page_count
    assert result.total_stroke_count > 500
    assert result.total_length_mm > 1000.0

    for page_idx, page in enumerate(result.pages):
        assert page.width_mm == 148.0
        assert page.height_mm == 210.0
        assert len(page.paths) > 0, f"Page {page_idx} has no paths"


def test_ruled_notebook_7mm_baseline_alignment(a5_composer: PageComposer) -> None:
    md_text = """# Physics Notes

A simple harmonic oscillator has position given by sinusoidal displacement.
The kinetic and potential energies exchange continuously throughout the cycle.
"""
    parser = MarkdownParser()
    doc = parser.parse_markdown(md_text, doc_id="ruled_test")

    result = a5_composer.compose_document(doc)
    assert len(result.baseline_y_positions) >= 3

    ruled_baselines = a5_composer.calculate_ruled_baselines()
    assert len(ruled_baselines) >= 20

    # Verify every rendered baseline is within +-0.2 mm of a simulated 7 mm ruled notebook line
    for y in result.baseline_y_positions:
        closest_diff = min(abs(y - rb) for rb in ruled_baselines)
        assert closest_diff <= 0.20, f"Baseline at Y={y:.3f} mm deviates by {closest_diff:.3f} mm (> 0.20 mm)"


def test_zero_strokes_intersect_clip_keepout_zone(a5_composer: PageComposer) -> None:
    # Top and bottom clips with 5 mm buffer
    keepouts = a5_composer.keepouts
    assert len(keepouts) >= 4

    md_text = """# Edge Writing Assignment

Line 1 near top edge.
Line 2 near top edge.
"""
    parser = MarkdownParser()
    doc = parser.parse_markdown(md_text, doc_id="clip_test")
    result = a5_composer.compose_document(doc)

    for page in result.pages:
        for path in page.paths:
            for stroke in path.strokes:
                for ko in keepouts:
                    assert ko.intersects_stroke(stroke) is False, (
                        f"Stroke intersects keep-out polygon {ko.name}"
                    )


def test_overflow_indivisible_figure_raises_layout_overflow_error(a5_composer: PageComposer) -> None:
    # Create an excessively large vector figure block (300 x 300 mm > A5 usable width)
    huge_figure = DocumentBlock(
        block_id="huge_fig",
        block_type=BlockType.FIGURE_VECTOR,
        page_idx=0,
        reading_order=0,
        bbox=BoundingBox(0.0, 0.0, 1000.0, 1000.0),
        vector_paths=[
            [(0.0, 0.0), (1000.0, 0.0)],
            [(1000.0, 0.0), (1000.0, 1000.0)],
            [(1000.0, 1000.0), (0.0, 1000.0)],
            [(0.0, 1000.0), (0.0, 0.0)],
        ],
    )
    doc = IngestedDocument(
        doc_id="overflow_test",
        source_filename="overflow.pdf",
        page_count=1,
        pages=[IngestedPage(page_idx=0, width_pt=612.0, height_pt=792.0, blocks=[huge_figure])],
    )

    with pytest.raises(LayoutOverflowError) as exc_info:
        a5_composer.compose_document(doc)

    assert "exceed printable area" in str(exc_info.value)
    assert "Suggestion:" in str(exc_info.value)


def test_physical_bed_limits_and_presets() -> None:
    # A4 preset is supported
    a4_comp = PageComposer(paper=A4_PRESET)
    assert a4_comp.paper.width_mm == 210.0
    assert a4_comp.paper.height_mm == 297.0

    # Custom preset exceeding travel limits without A4 exemption raises ValueError
    oversized = PaperPreset("GIANT", width_mm=300.0, height_mm=300.0)
    with pytest.raises(ValueError, match="exceeds Ender 3 physical bed travel limits"):
        PageComposer(paper=oversized)


def test_keepout_polygon_distance_and_containment() -> None:
    poly = KeepoutPolygon(
        points=[Point(10.0, 10.0), Point(30.0, 10.0), Point(30.0, 30.0), Point(10.0, 30.0)],
        name="test_box",
        buffer_mm=5.0,
    )
    # Inside polygon
    assert poly.contains_point(Point(20.0, 20.0)) is True
    # Inside 5 mm buffer
    assert poly.contains_point(Point(8.0, 20.0)) is True
    # Well outside buffer
    assert poly.contains_point(Point(0.0, 20.0)) is False

    # Stroke crossing buffer
    crossing = Stroke([Point(0.0, 20.0), Point(40.0, 20.0)])
    assert poly.intersects_stroke(crossing) is True

    # Stroke well away
    away = Stroke([Point(0.0, 50.0), Point(40.0, 50.0)])
    assert poly.intersects_stroke(away) is False


def test_composer_vector_figure_and_equation(a5_composer: PageComposer) -> None:
    eq_block = DocumentBlock(
        block_id="eq_1",
        block_type=BlockType.EQUATION,
        page_idx=0,
        reading_order=0,
        bbox=BoundingBox(0.0, 0.0, 50.0, 20.0),
        latex=r"E = mc^2",
        text="E = mc^2",
    )
    fig_block = DocumentBlock(
        block_id="fig_1",
        block_type=BlockType.FIGURE_VECTOR,
        page_idx=0,
        reading_order=1,
        bbox=BoundingBox(0.0, 0.0, 100.0, 50.0),
        vector_paths=[
            [(10.0, 10.0), (50.0, 10.0), (50.0, 30.0), (10.0, 30.0), (10.0, 10.0)],
        ],
    )
    doc = IngestedDocument(
        doc_id="mixed_doc",
        source_filename="mixed.pdf",
        page_count=1,
        pages=[IngestedPage(page_idx=0, width_pt=612.0, height_pt=792.0, blocks=[eq_block, fig_block])],
    )

    sheet_deck = a5_composer.compose_document(doc)
    assert len(sheet_deck.pages) >= 1
    assert any(path.label is not None and "eq_1" in path.label for path in sheet_deck.pages[0].paths)
    assert any(path.label is not None and "fig_1" in path.label for path in sheet_deck.pages[0].paths)
