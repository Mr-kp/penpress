"""Data models and block schema for PenPress Document Ingest.

A document is represented as an ordered sequence of blocks across pages.
Each block has a type, bounding box, reading order index, content, and optional metadata.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class BlockType(StrEnum):
    TITLE = "title"
    HEADING = "heading"
    PARAGRAPH = "paragraph"
    LIST_ITEM = "list_item"
    EQUATION = "equation"
    TABLE = "table"
    FIGURE_VECTOR = "figure_vector"
    FIGURE_RASTER = "figure_raster"
    PLACEHOLDER = "placeholder"


@dataclass(frozen=True)
class BoundingBox:
    x0: float
    y0: float
    x1: float
    y1: float

    @property
    def width(self) -> float:
        return max(0.0, self.x1 - self.x0)

    @property
    def height(self) -> float:
        return max(0.0, self.y1 - self.y0)

    @property
    def area(self) -> float:
        return self.width * self.height

    def intersects(self, other: BoundingBox) -> bool:
        return not (self.x1 <= other.x0 or self.x0 >= other.x1 or self.y1 <= other.y0 or self.y0 >= other.y1)

    def union(self, other: BoundingBox) -> BoundingBox:
        return BoundingBox(
            x0=min(self.x0, other.x0),
            y0=min(self.y0, other.y0),
            x1=max(self.x1, other.x1),
            y1=max(self.y1, other.y1),
        )

    def to_dict(self) -> dict[str, float]:
        return {
            "x0": round(self.x0, 2),
            "y0": round(self.y0, 2),
            "x1": round(self.x1, 2),
            "y1": round(self.y1, 2),
        }


@dataclass
class DocumentBlock:
    block_id: str
    block_type: BlockType
    page_idx: int
    reading_order: int
    bbox: BoundingBox
    text: str = ""
    latex: str = ""
    confidence: float = 1.0
    vector_paths: list[list[tuple[float, float]]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        d = {
            "block_id": self.block_id,
            "block_type": self.block_type.value,
            "page_idx": self.page_idx,
            "reading_order": self.reading_order,
            "bbox": self.bbox.to_dict(),
            "text": self.text,
            "latex": self.latex,
            "confidence": round(self.confidence, 4),
            "metadata": self.metadata,
        }
        if self.vector_paths:
            d["vector_paths_count"] = len(self.vector_paths)
            d["vector_points_total"] = sum(len(p) for p in self.vector_paths)
        return d


@dataclass
class IngestedPage:
    page_idx: int
    width_pt: float
    height_pt: float
    blocks: list[DocumentBlock] = field(default_factory=list)
    is_scanned: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "page_idx": self.page_idx,
            "width_pt": round(self.width_pt, 2),
            "height_pt": round(self.height_pt, 2),
            "is_scanned": self.is_scanned,
            "blocks": [b.to_dict() for b in self.blocks],
        }


@dataclass
class IngestedDocument:
    doc_id: str
    source_filename: str
    page_count: int
    pages: list[IngestedPage] = field(default_factory=list)
    extraction_duration_s: float = 0.0
    status: str = "ok"
    warnings: list[str] = field(default_factory=list)

    @property
    def total_blocks(self) -> int:
        return sum(len(p.blocks) for p in self.pages)

    def to_dict(self) -> dict[str, Any]:
        return {
            "doc_id": self.doc_id,
            "source_filename": self.source_filename,
            "page_count": self.page_count,
            "total_blocks": self.total_blocks,
            "extraction_duration_s": round(self.extraction_duration_s, 3),
            "status": self.status,
            "warnings": self.warnings,
            "pages": [p.to_dict() for p in self.pages],
        }
