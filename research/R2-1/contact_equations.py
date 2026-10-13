"""Contact sheet generator for R2-1 rendered equations.

Generates a multi-panel visual overview of rendered equations across all categories
and difficulty levels adhering to the dark graphite minimalist aesthetic.
"""

from __future__ import annotations

import json
from pathlib import Path

from eqengine.engine import EquationEngine
from PIL import Image, ImageDraw


def generate_equation_contact_sheet(
    equations_file: Path,
    output_path: Path,
    sample_ids: list[str],
) -> None:
    engine = EquationEngine()
    eq_map = {}
    with open(equations_file, encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            d = json.loads(line)
            eq_map[d["id"]] = d

    # Render selected samples
    rendered_items = []
    for sid in sample_ids:
        if sid in eq_map:
            eq = eq_map[sid]
            res = engine.render_equation_to_strokes(
                eq["latex"],
                target_height_mm=6.5,
                x_offset=5.0,
                y_offset=5.0,
                slant_deg=3.5,
            )
            rendered_items.append((eq, res))

    # Grid layout: 4 columns x 6 rows (24 equations)
    cols = 4
    rows = 6
    cell_w, cell_h = 440, 240
    margin = 40
    gap = 20

    sheet_w = margin * 2 + cols * cell_w + (cols - 1) * gap
    sheet_h = margin * 2 + rows * cell_h + (rows - 1) * gap + 50

    # Linear / dark graphite palette
    bg_color = (13, 14, 18)  # #0d0e12
    card_bg = (20, 23, 34)  # #141722
    card_border = (33, 38, 56)  # #212638
    text_primary = (248, 250, 252)  # #f8fafc
    text_muted = (148, 163, 184)  # #94a3b8

    sheet = Image.new("RGB", (sheet_w, sheet_h), color=bg_color)
    draw = ImageDraw.Draw(sheet)

    # Title header
    draw.text(
        (margin, margin - 15),
        "PenPress R2-1: Equation Handwriting Synthesis & Layout Contact Sheet (24 Samples)",
        fill=text_primary,
    )

    scale_px_per_mm = 5.0  # mm to px

    for idx, (eq, res) in enumerate(rendered_items):
        r = idx // cols
        c = idx % cols
        x0 = margin + c * (cell_w + gap)
        y0 = margin + 40 + r * (cell_h + gap)
        x1 = x0 + cell_w
        y1 = y0 + cell_h

        # Draw card container
        draw.rectangle([x0, y0, x1, y1], fill=card_bg, outline=card_border, width=1)

        # Header metadata
        cat_info = f"[{eq['id']}] {eq['category']} (diff: {eq['difficulty']})"
        draw.text((x0 + 12, y0 + 10), cat_info, fill=text_muted)

        # Draw rendered strokes
        # Center equation in the card preview area
        bw = res.bounds.max_x - res.bounds.min_x
        bh = res.bounds.max_y - res.bounds.min_y
        area_w = cell_w - 24
        area_h = cell_h - 60

        fit_scale = min(scale_px_per_mm, area_w / max(bw, 1.0), area_h / max(bh, 1.0))
        center_x = x0 + 12 + (area_w - bw * fit_scale) / 2.0
        center_y = y0 + 35 + (area_h - bh * fit_scale) / 2.0

        for stroke in res.strokes:
            pts = []
            for p in stroke.points:
                px = center_x + (p.x - res.bounds.min_x) * fit_scale
                # Invert Y for screen display
                py = center_y + (res.bounds.max_y - p.y) * fit_scale
                pts.append((px, py))
            if len(pts) >= 2:
                draw.line(pts, fill=text_primary, width=2)

        # Bottom LaTeX label (truncated if long)
        tex_label = eq["latex"]
        if len(tex_label) > 42:
            tex_label = tex_label[:39] + "..."
        draw.text((x0 + 12, y1 - 22), tex_label, fill=(100, 116, 139))

    output_path.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output_path, "PNG")
    print(f"Generated equation contact sheet: {output_path}")


if __name__ == "__main__":
    sample_ids = [
        # Arithmetic & Linear
        "EQ-001",
        "EQ-007",
        "EQ-008",
        "EQ-010",
        # Fractions & Nested
        "EQ-011",
        "EQ-014",
        "EQ-016",
        "EQ-019",
        # Roots & Exponents
        "EQ-021",
        "EQ-024",
        "EQ-028",
        "EQ-030",
        # Calculus & Limits
        "EQ-031",
        "EQ-035",
        "EQ-039",
        "EQ-040",
        # Trigonometry & Logarithms
        "EQ-041",
        "EQ-045",
        "EQ-048",
        "EQ-050",
        # Matrices & Piecewise
        "EQ-051",
        "EQ-054",
        "EQ-060",
        "EQ-061",
    ]
    eq_file = Path("tests/fixtures/equations.jsonl")
    out_img = Path("docs/evidence/R2-1/contact-equations-24.png")
    generate_equation_contact_sheet(eq_file, out_img, sample_ids)
