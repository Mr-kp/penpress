"""Document ingestion and structured block parsing package."""

from __future__ import annotations

from penpress.ingest.engine import DocumentIngestEngine, IngestError
from penpress.ingest.markdown_parser import MarkdownParser
from penpress.ingest.schema import (
    BlockType,
    BoundingBox,
    DocumentBlock,
    IngestedDocument,
    IngestedPage,
)

__all__ = [
    "BlockType",
    "BoundingBox",
    "DocumentBlock",
    "DocumentIngestEngine",
    "IngestError",
    "IngestedDocument",
    "IngestedPage",
    "MarkdownParser",
]
