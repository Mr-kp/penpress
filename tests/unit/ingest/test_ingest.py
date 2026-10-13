"""Unit tests for Document Ingest Pipeline and Structured Block Parser (P5-1).

Tests:
1. Digital single/two-column PDF extraction throughput >= 15 pages / second on CPU.
2. Monotonic reading order correctness >= 95% on multi-column benchmarks.
3. Vector drawings in figures preserved as float coordinate polylines without rasterisation.
4. Markdown parser converts headings, lists, paragraphs, and display math.
5. Hostile and corrupted files raise structured IngestError without crashing.
"""

from __future__ import annotations

import time
from pathlib import Path

import numpy as np
import pytest

from penpress.ingest.engine import DocumentIngestEngine, IngestError
from penpress.ingest.figures import cluster_drawings, trace_raster_skeleton
from penpress.ingest.markdown_parser import MarkdownParser
from penpress.ingest.schema import BlockType, BoundingBox, DocumentBlock


@pytest.fixture
def fixtures_dir() -> Path:
    return Path("research/R4-1/fixtures")


@pytest.fixture
def engine() -> DocumentIngestEngine:
    return DocumentIngestEngine()


def test_markdown_parser_structured_blocks() -> None:
    md_text = """# Physics Assignment

## Harmonic Oscillations
A simple pendulum exhibits harmonic motion for small angular displacements.

$$
\\frac{d^2\\theta}{dt^2} + \\frac{g}{L} \\sin\\theta = 0
$$

Key observations:
- Period depends on length L
- Amplitude remains constant without damping
"""
    parser = MarkdownParser()
    doc = parser.parse_markdown(md_text, doc_id="test_assignment")

    assert doc.status == "ok"
    assert doc.page_count == 1
    p0 = doc.pages[0]
    assert len(p0.blocks) >= 6

    # Verify block types
    types = [b.block_type for b in p0.blocks]
    assert BlockType.TITLE in types
    assert BlockType.HEADING in types
    assert BlockType.PARAGRAPH in types
    assert BlockType.EQUATION in types
    assert BlockType.LIST_ITEM in types

    eq_block = next(b for b in p0.blocks if b.block_type == BlockType.EQUATION)
    assert r"\frac{d^2\theta}{dt^2}" in eq_block.latex


def test_single_column_academic_ingest(engine: DocumentIngestEngine, fixtures_dir: Path) -> None:
    pdf_path = fixtures_dir / "single_column_academic.pdf"
    doc = engine.ingest_pdf(pdf_path)

    assert doc.status == "ok"
    assert doc.page_count == 1
    p0 = doc.pages[0]
    assert len(p0.blocks) >= 8

    # Title check
    titles = [b for b in p0.blocks if b.block_type == BlockType.TITLE]
    assert len(titles) >= 1
    assert "Harmonic Oscillations" in titles[0].text


def test_two_column_reading_order_and_throughput(engine: DocumentIngestEngine, fixtures_dir: Path) -> None:
    pdf_path = fixtures_dir / "two_column_article.pdf"

    # Measure throughput across repeated runs
    t0 = time.perf_counter()
    iterations = 25
    for _ in range(iterations):
        doc = engine.ingest_pdf(pdf_path)
    elapsed = time.perf_counter() - t0

    throughput = iterations / elapsed
    print(f"\nPDF Extraction throughput: {throughput:.1f} pages / sec")
    assert throughput >= 15.0, f"Throughput {throughput:.1f} pages/sec is below required 15.0"

    p0 = doc.pages[0]

    # Check reading order correctness: monotonic indices 0..N-1
    orders = [b.reading_order for b in p0.blocks]
    assert orders == list(range(len(p0.blocks)))

    # Monotonic top-to-bottom reading order check within columns
    # Split into left and right column by X midpoint
    mid_x = p0.width_pt / 2.0
    left_col = [b for b in p0.blocks if b.bbox.x1 <= mid_x + 30.0 and b.block_type != BlockType.TITLE]
    right_col = [b for b in p0.blocks if b.bbox.x0 >= mid_x - 30.0 and b.block_type != BlockType.TITLE]

    # Verify left column precedes right column in reading order
    if left_col and right_col:
        max_left_order = max(b.reading_order for b in left_col)
        min_right_order = min(b.reading_order for b in right_col)
        assert min_right_order > max_left_order, "Left column must be read before right column"


def test_vector_figure_polyline_preservation(engine: DocumentIngestEngine, fixtures_dir: Path) -> None:
    pdf_path = fixtures_dir / "vector_figure_circuit.pdf"
    doc = engine.ingest_pdf(pdf_path)

    assert doc.status == "ok"
    p0 = doc.pages[0]

    fig = next(b for b in p0.blocks if b.block_type == BlockType.FIGURE_VECTOR)
    assert len(fig.vector_paths) >= 10
    # Verify polylines contain float coordinates without rasterisation
    for path in fig.vector_paths:
        assert len(path) >= 2
        for pt in path:
            assert isinstance(pt[0], float) and isinstance(pt[1], float)


def test_hostile_malformed_and_missing_files_raise_ingest_error(
    engine: DocumentIngestEngine,
    fixtures_dir: Path,
    tmp_path: Path,
) -> None:
    malformed_pdf = fixtures_dir / "hostile_malformed.pdf"
    with pytest.raises(IngestError):
        engine.ingest_pdf(malformed_pdf)

    missing_pdf = fixtures_dir / "nonexistent_file.pdf"
    with pytest.raises(IngestError):
        engine.ingest_pdf(missing_pdf)

    # Unsupported format
    fake_txt = tmp_path / "dummy.unknown"
    fake_txt.write_text("dummy", encoding="utf-8")
    with pytest.raises(IngestError):
        engine.ingest_document(fake_txt)


def test_schema_serialization_and_bounding_box() -> None:
    b1 = BoundingBox(x0=10.0, y0=20.0, x1=50.0, y1=60.0)
    assert b1.width == 40.0
    assert b1.height == 40.0
    assert b1.area == 1600.0

    b2 = BoundingBox(x0=30.0, y0=40.0, x1=80.0, y1=90.0)
    assert b1.intersects(b2) is True
    assert b1.intersects(BoundingBox(100.0, 100.0, 120.0, 120.0)) is False

    u = b1.union(b2)
    assert u.x0 == 10.0 and u.y0 == 20.0 and u.x1 == 80.0 and u.y1 == 90.0

    block = DocumentBlock(
        block_id="b0",
        block_type=BlockType.PARAGRAPH,
        page_idx=0,
        reading_order=0,
        bbox=b1,
        text="Sample text",
        latex="",
        confidence=0.99,
        vector_paths=[[(10.0, 20.0), (30.0, 40.0)]],
    )
    d = block.to_dict()
    assert d["block_id"] == "b0"
    assert d["block_type"] == "paragraph"
    assert len(d["vector_paths"]) == 1

    restored = DocumentBlock.from_dict(d)
    assert restored.block_id == block.block_id
    assert restored.bbox == block.bbox


def test_figures_raster_skeleton_tracer() -> None:
    # Empty paths or small elements
    assert cluster_drawings([]) == []
    assert cluster_drawings([[(0.0, 0.0), (1.0, 1.0)]]) == []

    # Raster diagram tracing
    img = np.ones((50, 50), dtype=np.uint8) * 255
    # Draw horizontal black line
    img[25, 10:40] = 0

    polylines = trace_raster_skeleton(img, threshold=128)
    assert len(polylines) >= 1
    assert len(polylines[0]) >= 2

    # Blank image returns empty
    blank = np.ones((50, 50), dtype=np.uint8) * 255
    assert trace_raster_skeleton(blank) == []


def test_ingest_document_pdf_and_markdown_paths(
    engine: DocumentIngestEngine, fixtures_dir: Path, tmp_path: Path
) -> None:
    # 1. Ingest document with markdown file path
    md_file = tmp_path / "sample.md"
    md_file.write_text("# Chapter 1\n\nIntroductory remarks.\n\n$$E = mc^2$$\n", encoding="utf-8")
    doc_md = engine.ingest_document(md_file)
    assert doc_md.status == "ok"
    assert doc_md.page_count == 1
    assert doc_md.total_blocks >= 3

    # 2. Ingest document with PDF file path
    pdf_file = fixtures_dir / "single_column_academic.pdf"
    doc_pdf = engine.ingest_document(pdf_file)
    assert doc_pdf.status == "ok"
    assert doc_pdf.page_count == 1

    # 3. Nonexistent file raises IngestError
    with pytest.raises(IngestError):
        engine.ingest_document(tmp_path / "ghost.pdf")


def test_markdown_parser_edge_cases() -> None:
    parser = MarkdownParser(page_width_pt=500.0, page_height_pt=700.0)
    raw = """### Section 1.1

A paragraph with **bold** and *italic* text.

Another paragraph immediately following.

$$
\\int_0^\\infty e^{-x^2} dx = \\frac{\\sqrt{\\pi}}{2}
$$

* First bullet
* Second bullet
"""
    doc = parser.parse_markdown(raw)
    p0 = doc.pages[0]
    types = [b.block_type for b in p0.blocks]
    assert BlockType.HEADING in types
    assert BlockType.PARAGRAPH in types
    assert BlockType.EQUATION in types
    assert BlockType.LIST_ITEM in types


def test_scanned_page_fallback(engine: DocumentIngestEngine, fixtures_dir: Path) -> None:
    pdf_path = fixtures_dir / "scanned_page_noisy.pdf"
    doc = engine.ingest_pdf(pdf_path)

    assert doc.status == "ok"
    assert doc.pages[0].is_scanned is True
    assert doc.total_blocks >= 10
    all_text = " ".join(b.text for b in doc.pages[0].blocks)
    assert "Oscillations" in all_text or "Pendulum" in all_text or "Harmonic" in all_text


def test_hostile_oversized_handling(engine: DocumentIngestEngine, fixtures_dir: Path) -> None:
    pdf_path = fixtures_dir / "hostile_oversized.pdf"
    doc = engine.ingest_pdf(pdf_path)

    assert doc.status == "ok"
    assert len(doc.warnings) >= 1
    assert "exceed standard bounds" in doc.warnings[0]
