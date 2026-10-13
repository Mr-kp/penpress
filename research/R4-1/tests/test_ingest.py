"""Tests for R4-1 PDF Ingest Pipeline."""

from __future__ import annotations

from pathlib import Path

import pytest
from ingest.engine import DocumentIngestEngine
from ingest.equations import clean_latex
from ingest.schema import BlockType, BoundingBox


@pytest.fixture
def fixtures_dir() -> Path:
    return Path("research/R4-1/fixtures")


@pytest.fixture
def engine() -> DocumentIngestEngine:
    return DocumentIngestEngine()


def test_single_column_academic_ingest(engine: DocumentIngestEngine, fixtures_dir: Path) -> None:
    pdf_path = fixtures_dir / "single_column_academic.pdf"
    doc = engine.ingest_pdf(pdf_path)

    assert doc.status == "ok"
    assert doc.page_count == 1
    assert doc.total_blocks >= 8

    # Check title block
    p0 = doc.pages[0]
    titles = [b for b in p0.blocks if b.block_type == BlockType.TITLE]
    assert len(titles) >= 1
    assert "Harmonic Oscillations" in titles[0].text

    # Check equations
    equations = [b for b in p0.blocks if b.block_type == BlockType.EQUATION]
    assert len(equations) >= 3
    eq_texts = " ".join(b.latex for b in equations)
    assert "omega" in eq_texts or "theta" in eq_texts


def test_two_column_article_layout(engine: DocumentIngestEngine, fixtures_dir: Path) -> None:
    pdf_path = fixtures_dir / "two_column_article.pdf"
    doc = engine.ingest_pdf(pdf_path)

    assert doc.status == "ok"
    p0 = doc.pages[0]

    # Verify vector figure detected
    figs = [b for b in p0.blocks if b.block_type == BlockType.FIGURE_VECTOR]
    assert len(figs) == 1
    assert len(figs[0].vector_paths) >= 5

    # Check reading order indices are strictly sequential 0..N-1
    orders = [b.reading_order for b in p0.blocks]
    assert orders == list(range(len(p0.blocks)))


def test_mixed_math_assignment(engine: DocumentIngestEngine, fixtures_dir: Path) -> None:
    pdf_path = fixtures_dir / "mixed_math_assignment.pdf"
    doc = engine.ingest_pdf(pdf_path)

    assert doc.status == "ok"
    p0 = doc.pages[0]
    assert any("Stokes" in b.text or "Gauss" in b.text for b in p0.blocks)

    # Table grid detected
    table_figs = [b for b in p0.blocks if b.block_type == BlockType.FIGURE_VECTOR]
    assert len(table_figs) >= 1


def test_vector_figure_circuit(engine: DocumentIngestEngine, fixtures_dir: Path) -> None:
    pdf_path = fixtures_dir / "vector_figure_circuit.pdf"
    doc = engine.ingest_pdf(pdf_path)

    assert doc.status == "ok"
    p0 = doc.pages[0]
    fig = next(b for b in p0.blocks if b.block_type == BlockType.FIGURE_VECTOR)
    assert len(fig.vector_paths) >= 10


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
    assert "exceed safe threshold" in doc.warnings[0]


def test_hostile_malformed_handling(engine: DocumentIngestEngine, fixtures_dir: Path) -> None:
    pdf_path = fixtures_dir / "hostile_malformed.pdf"
    doc = engine.ingest_pdf(pdf_path)

    assert "malformed_pdf" in doc.status
    assert len(doc.warnings) >= 1


def test_hostile_missing_file(engine: DocumentIngestEngine) -> None:
    doc = engine.ingest_pdf("nonexistent_file_xyz.pdf")
    assert doc.status == "error: file_not_found"


def test_clean_latex_utilities() -> None:
    raw = "$$\\frac{a}{b} = c$$"
    assert clean_latex(raw) == "\\frac{a}{b} = c"

    labeled = "Equation 1: $$\\int x dx$$"
    assert clean_latex(labeled) == "\\int x dx"


def test_bounding_box_geometry() -> None:
    b1 = BoundingBox(0, 0, 10, 10)
    b2 = BoundingBox(5, 5, 15, 15)
    b3 = BoundingBox(20, 20, 30, 30)

    assert b1.intersects(b2) is True
    assert b1.intersects(b3) is False

    union_b = b1.union(b3)
    assert union_b.x0 == 0
    assert union_b.y0 == 0
    assert union_b.x1 == 30
    assert union_b.y1 == 30
