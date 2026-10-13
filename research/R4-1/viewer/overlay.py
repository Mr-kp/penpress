"""Overlay visualizer for document ingest inspection.

Renders high-resolution page bitmaps and overlays color-coded bounding boxes and
labels for detected blocks (Headings, Paragraphs, Equations, Figures, Tables).
Uses minimalist dark theme / Linear aesthetics.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pypdfium2 as pdfium
from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ingest.schema import BlockType, IngestedDocument

# Modern minimalist color palette for block categories
BLOCK_COLORS = {
    BlockType.TITLE: (99, 102, 241, 180),  # Indigo
    BlockType.HEADING: (59, 130, 246, 180),  # Blue
    BlockType.PARAGRAPH: (16, 185, 129, 140),  # Emerald
    BlockType.LIST_ITEM: (20, 184, 166, 140),  # Teal
    BlockType.EQUATION: (245, 158, 11, 200),  # Amber / Gold
    BlockType.TABLE: (168, 85, 247, 180),  # Purple
    BlockType.FIGURE_VECTOR: (236, 72, 153, 200),  # Pink
    BlockType.FIGURE_RASTER: (244, 63, 94, 200),  # Rose
    BlockType.PLACEHOLDER: (107, 114, 128, 180),  # Gray
}


def render_overlay(
    pdf_path: Path,
    doc: IngestedDocument,
    page_idx: int,
    output_png: Path,
    scale: float = 2.0,
) -> None:
    """Renders page overlay with color-coded bounding boxes and badges."""
    pdf = pdfium.PdfDocument(str(pdf_path))
    if page_idx >= len(pdf):
        return

    page = pdf[page_idx]
    _page_w_pt, page_h_pt = page.get_size()
    bitmap = page.render(scale=scale)
    base_img = bitmap.to_pil().convert("RGBA")

    # Create transparent overlay surface
    overlay = Image.new("RGBA", base_img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    # Find blocks for this page
    if page_idx < len(doc.pages):
        page_doc = doc.pages[page_idx]
        for b in page_doc.blocks:
            color = BLOCK_COLORS.get(b.block_type, (100, 100, 100, 150))

            # Map PDF coordinates (origin at bottom-left) to Image pixel coordinates (origin top-left)
            px0 = b.bbox.x0 * scale
            py0 = (page_h_pt - b.bbox.y1) * scale
            px1 = b.bbox.x1 * scale
            py1 = (page_h_pt - b.bbox.y0) * scale

            # Draw subtle semi-transparent filled box
            tint_bg = (color[0], color[1], color[2], 30)
            draw.rectangle([px0, py0, px1, py1], fill=tint_bg, outline=color, width=2)

            # Draw block badge label at top-left
            label = f"#{b.reading_order} {b.block_type.value.upper()}"
            badge_w = len(label) * 7 + 10
            draw.rectangle([px0, py0 - 16, px0 + badge_w, py0], fill=color)
            draw.text((px0 + 5, py0 - 14), label, fill=(255, 255, 255, 255))

    # Composite overlay onto base image
    composite = Image.alpha_composite(base_img, overlay).convert("RGB")
    output_png.parent.mkdir(parents=True, exist_ok=True)
    composite.save(str(output_png), "PNG")
