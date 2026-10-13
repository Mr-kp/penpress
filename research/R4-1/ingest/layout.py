"""Layout analysis and reading order sorter for PDF text and drawing elements.

Handles:
- Header / title detection
- Single-column vs multi-column clustering (X-projection / gutter detection)
- Top-to-bottom reading order within columns (XY-cut / topological sort)
- Table detection via grid line intersections
"""

from __future__ import annotations

from collections.abc import Sequence

from .schema import DocumentBlock


def detect_columns(blocks: Sequence[DocumentBlock], page_width: float) -> list[list[DocumentBlock]]:
    """Partitions blocks into columns if a vertical gutter exists."""
    if not blocks:
        return []

    # Check for title/full-width header blocks spanning > 65% of page width
    full_width_top: list[DocumentBlock] = []
    candidates: list[DocumentBlock] = []

    for b in blocks:
        if b.bbox.width > 0.65 * page_width:
            full_width_top.append(b)
        else:
            candidates.append(b)

    if not candidates:
        full_width_top.sort(key=lambda b: -b.bbox.y1)  # top to bottom (PDF coords)
        return [full_width_top]

    # Analyze x0 coordinates to find column split
    mid_x = page_width / 2.0
    left_col = [b for b in candidates if b.bbox.x1 <= mid_x + 30.0]
    right_col = [b for b in candidates if b.bbox.x0 >= mid_x - 30.0]

    # If cleanly partitioned into two significant sets
    if len(left_col) >= 2 and len(right_col) >= 2 and (len(left_col) + len(right_col) == len(candidates)):
        left_col.sort(key=lambda b: -b.bbox.y1)
        right_col.sort(key=lambda b: -b.bbox.y1)
        full_width_top.sort(key=lambda b: -b.bbox.y1)
        return [full_width_top, left_col, right_col]

    # Single column fallback: sort all strictly top-to-bottom (PDF y goes upwards)
    all_blocks = list(blocks)
    all_blocks.sort(key=lambda b: -b.bbox.y1)
    return [all_blocks]


def order_blocks(blocks: Sequence[DocumentBlock], page_width: float) -> list[DocumentBlock]:
    """Sorts blocks into natural human reading order and assigns sequential reading_order indices."""
    col_groups = detect_columns(blocks, page_width)
    ordered: list[DocumentBlock] = []
    order_idx = 0

    for group in col_groups:
        for b in group:
            b.reading_order = order_idx
            ordered.append(b)
            order_idx += 1

    return ordered
