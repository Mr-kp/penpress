"""Markdown and mixed LaTeX document parser for PenPress.

Parses Markdown documents into structured blocks:
- Headings (# Title, ## Section, ### Subsection)
- Paragraphs with bold (**text**), italics, and inline formulas
- Display equations ($$ ... $$)
- Bullet and numbered lists
- Tables
"""

from __future__ import annotations

import re

from penpress.ingest.schema import (
    BlockType,
    BoundingBox,
    DocumentBlock,
    IngestedDocument,
    IngestedPage,
)


class MarkdownParser:
    """Parses Markdown+LaTeX documents into IngestedDocument block trees."""

    def __init__(self, page_width_pt: float = 420.0, page_height_pt: float = 595.0) -> None:
        self.page_width_pt = page_width_pt  # Standard A5 width in points (148 mm ~ 420 pt)
        self.page_height_pt = page_height_pt  # Standard A5 height in points (210 mm ~ 595 pt)

    def parse_markdown(self, markdown_text: str, doc_id: str = "doc_md") -> IngestedDocument:
        lines = markdown_text.splitlines()
        blocks: list[DocumentBlock] = []
        reading_order = 0

        # State machine for block parsing
        in_display_math = False
        math_accumulator: list[str] = []
        para_accumulator: list[str] = []

        # Nominal cursor in points
        cursor_y = self.page_height_pt - 40.0
        line_height_pt = 16.0

        def flush_paragraph() -> None:
            nonlocal reading_order, cursor_y
            if not para_accumulator:
                return
            p_text = " ".join(s.strip() for s in para_accumulator if s.strip())
            para_accumulator.clear()
            if not p_text:
                return

            h = max(20.0, (len(p_text) // 60 + 1) * line_height_pt)
            bbox = BoundingBox(x0=40.0, y0=cursor_y - h, x1=self.page_width_pt - 40.0, y1=cursor_y)
            cursor_y -= h + 10.0

            blocks.append(
                DocumentBlock(
                    block_id=f"b_{reading_order}",
                    block_type=BlockType.PARAGRAPH,
                    page_idx=0,
                    reading_order=reading_order,
                    bbox=bbox,
                    text=p_text,
                    confidence=1.0,
                )
            )
            reading_order += 1

        for line in lines:
            stripped = line.strip()

            # 1. Multi-line display math delimiter
            if stripped.startswith("$$"):
                if in_display_math:
                    # Closing $$
                    math_content = "\n".join(math_accumulator).strip()
                    math_accumulator.clear()
                    in_display_math = False

                    h = 35.0
                    bbox = BoundingBox(x0=40.0, y0=cursor_y - h, x1=self.page_width_pt - 40.0, y1=cursor_y)
                    cursor_y -= h + 10.0

                    blocks.append(
                        DocumentBlock(
                            block_id=f"b_{reading_order}",
                            block_type=BlockType.EQUATION,
                            page_idx=0,
                            reading_order=reading_order,
                            bbox=bbox,
                            text=math_content,
                            latex=math_content,
                            confidence=1.0,
                        )
                    )
                    reading_order += 1
                    continue
                else:
                    # Check for single-line $$ formula $$
                    m_single = re.match(r"^\$\$(.+?)\$\$$", stripped)
                    if m_single:
                        flush_paragraph()
                        eq_content = m_single.group(1).strip()
                        h = 35.0
                        bbox = BoundingBox(
                            x0=40.0,
                            y0=cursor_y - h,
                            x1=self.page_width_pt - 40.0,
                            y1=cursor_y,
                        )
                        cursor_y -= h + 10.0

                        blocks.append(
                            DocumentBlock(
                                block_id=f"b_{reading_order}",
                                block_type=BlockType.EQUATION,
                                page_idx=0,
                                reading_order=reading_order,
                                bbox=bbox,
                                text=eq_content,
                                latex=eq_content,
                                confidence=1.0,
                            )
                        )
                        reading_order += 1
                        continue
                    else:
                        flush_paragraph()
                        in_display_math = True
                        rest = stripped[2:].strip()
                        if rest:
                            math_accumulator.append(rest)
                        continue

            if in_display_math:
                math_accumulator.append(stripped)
                continue

            # Empty line ends paragraph
            if not stripped:
                flush_paragraph()
                continue

            # 2. Headings (# Title, ## Section, ### Subsection)
            if stripped.startswith("#"):
                flush_paragraph()
                heading_level = len(stripped) - len(stripped.lstrip("#"))
                heading_text = stripped.lstrip("#").strip()

                b_type = BlockType.TITLE if heading_level == 1 else BlockType.HEADING
                h = 28.0 if heading_level == 1 else 22.0
                bbox = BoundingBox(x0=40.0, y0=cursor_y - h, x1=self.page_width_pt - 40.0, y1=cursor_y)
                cursor_y -= h + 10.0

                blocks.append(
                    DocumentBlock(
                        block_id=f"b_{reading_order}",
                        block_type=b_type,
                        page_idx=0,
                        reading_order=reading_order,
                        bbox=bbox,
                        text=heading_text,
                        confidence=1.0,
                        metadata={"level": heading_level},
                    )
                )
                reading_order += 1
                continue

            # 3. Bullet lists (- item or * item)
            if re.match(r"^[-*]\s+", stripped):
                flush_paragraph()
                item_text = re.sub(r"^[-*]\s+", "", stripped)
                h = 16.0
                bbox = BoundingBox(x0=55.0, y0=cursor_y - h, x1=self.page_width_pt - 40.0, y1=cursor_y)
                cursor_y -= h + 4.0

                blocks.append(
                    DocumentBlock(
                        block_id=f"b_{reading_order}",
                        block_type=BlockType.LIST_ITEM,
                        page_idx=0,
                        reading_order=reading_order,
                        bbox=bbox,
                        text=item_text,
                        confidence=1.0,
                    )
                )
                reading_order += 1
                continue

            # Normal line accumulated into current paragraph
            para_accumulator.append(stripped)

        # Flush any trailing paragraph or math
        flush_paragraph()
        if math_accumulator:
            math_content = "\n".join(math_accumulator).strip()
            h = 35.0
            bbox = BoundingBox(x0=40.0, y0=cursor_y - h, x1=self.page_width_pt - 40.0, y1=cursor_y)
            blocks.append(
                DocumentBlock(
                    block_id=f"b_{reading_order}",
                    block_type=BlockType.EQUATION,
                    page_idx=0,
                    reading_order=reading_order,
                    bbox=bbox,
                    text=math_content,
                    latex=math_content,
                    confidence=1.0,
                )
            )

        page = IngestedPage(
            page_idx=0,
            width_pt=self.page_width_pt,
            height_pt=self.page_height_pt,
            blocks=blocks,
            is_scanned=False,
        )

        return IngestedDocument(
            doc_id=doc_id,
            source_filename=f"{doc_id}.md",
            page_count=1,
            pages=[page],
            status="ok",
        )
