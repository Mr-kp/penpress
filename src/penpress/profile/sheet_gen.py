"""Printable handwriting calibration sheet generator.

Generates printable A4 or Letter PDFs with corner ArUco/fiducial markers,
alphanumeric prompt cells, baseline guidelines, and character labels.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from reportlab.lib.colors import HexColor, black
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

# Standard character set covering uppercase, lowercase, numbers, and punctuation
ALPHABET_UPPER = [chr(c) for c in range(ord("A"), ord("Z") + 1)]
ALPHABET_LOWER = [chr(c) for c in range(ord("a"), ord("z") + 1)]
DIGITS = [str(d) for d in range(10)]
PUNCTUATION = [".", ",", "!", "?", "-", "+", "=", "(", ")", "/", ":", ";"]

DEFAULT_CHARS = ALPHABET_UPPER + ALPHABET_LOWER + DIGITS + PUNCTUATION


def draw_fiducial_corner(
    c: canvas.Canvas,
    x: float,
    y: float,
    size: float = 24.0,
    corner_type: str = "TL",
) -> None:
    """Draws a high-contrast square optical alignment fiducial marker."""
    c.setFillColor(black)
    c.rect(x - size / 2.0, y - size / 2.0, size, size, stroke=0, fill=1)
    # Inner white dot/square for high-precision sub-pixel center localization
    c.setFillColor(HexColor("#ffffff"))
    inner_size = size * 0.4
    c.rect(x - inner_size / 2.0, y - inner_size / 2.0, inner_size, inner_size, stroke=0, fill=1)
    # Target center crosshair dot
    c.setFillColor(black)
    c.circle(x, y, 1.5, stroke=0, fill=1)


def generate_sample_sheet(
    out_pdf_path: str | Path,
    pagesize: tuple[float, float] = A4,
    title: str = "PenPress Handwriting Sample Sheet",
    instructions: str = "Write each character neatly inside its box using a black gel pen or rollerball.",
) -> dict[str, Any]:
    """Generates calibration PDF with corner fiducials and labeled character grid."""
    path = Path(out_pdf_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    w, h = pagesize
    c = canvas.Canvas(str(path), pagesize=pagesize)

    margin = 36.0  # 0.5 inch (36 pt)
    fid_size = 20.0

    # Draw 4 corner fiducial markers
    fiducials = {
        "TL": (margin, h - margin),
        "TR": (w - margin, h - margin),
        "BL": (margin, margin),
        "BR": (w - margin, margin),
    }
    for ctype, (fx, fy) in fiducials.items():
        draw_fiducial_corner(c, fx, fy, size=fid_size, corner_type=ctype)

    # Header
    c.setFillColor(black)
    c.setFont("Helvetica-Bold", 14)
    c.drawString(margin + 30.0, h - margin - 4.0, title)

    c.setFont("Helvetica", 8)
    c.setFillColor(HexColor("#4b5563"))
    c.drawString(margin + 30.0, h - margin - 18.0, instructions)

    # Grid parameters
    grid_top = h - margin - 35.0
    grid_bottom = margin + 25.0
    grid_left = margin + 15.0
    grid_right = w - margin - 15.0

    cols = 8
    rows = 9  # 72 cells total (covers 52 alphabet + 10 digits + 10 symbols)
    cell_w = (grid_right - grid_left) / cols
    cell_h = (grid_top - grid_bottom) / rows

    cells_meta = []
    char_idx = 0

    c.setLineWidth(0.5)
    c.setStrokeColor(HexColor("#cbd5e1"))

    for r in range(rows):
        for col in range(cols):
            if char_idx >= len(DEFAULT_CHARS):
                break
            char = DEFAULT_CHARS[char_idx]

            cx0 = grid_left + col * cell_w
            cy0 = grid_top - (r + 1) * cell_h
            cx1 = cx0 + cell_w
            cy1 = cy0 + cell_h

            # Outer cell rectangle
            c.setStrokeColor(HexColor("#94a3b8"))
            c.setLineWidth(0.75)
            c.rect(cx0, cy0, cell_w, cell_h, stroke=1, fill=0)

            # Internal dashed baseline guideline (at 30% from bottom)
            baseline_y = cy0 + cell_h * 0.28
            c.setStrokeColor(HexColor("#cbd5e1"))
            c.setLineWidth(0.5)
            c.setDash(2, 2)
            c.line(cx0 + 4.0, baseline_y, cx1 - 4.0, baseline_y)
            c.setDash()  # Reset dash

            # Character prompt label in top-left
            c.setFont("Helvetica-Bold", 8)
            c.setFillColor(HexColor("#64748b"))
            c.drawString(cx0 + 4.0, cy1 - 10.0, char)

            cells_meta.append(
                {
                    "char": char,
                    "row": r,
                    "col": col,
                    "bbox_pt": {"x0": cx0, "y0": cy0, "x1": cx1, "y1": cy1},
                    "baseline_pt": baseline_y,
                }
            )
            char_idx += 1

    c.showPage()
    c.save()

    return {
        "pdf_file": str(path.name),
        "total_cells": len(cells_meta),
        "fiducials": fiducials,
        "cells": cells_meta,
    }
