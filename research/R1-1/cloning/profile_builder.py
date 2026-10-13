"""Profile builder for extracting user StyleProfiles from sample sheets or canvas traces.

Takes sample sheet images + cell annotations (from R0-1) or phone/tablet canvas JSON,
runs stroke recovery, segments glyphs, computes slant/x-height/spacing statistics,
and constructs a multi-variant StyleProfile.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
from PIL import Image

from penpress.core.primitives import Point, Stroke

from .protocol import GlyphVariant, StyleProfile, StyleStats
from .stroke_recovery import binarize_handwriting, skeletonize_binary, trace_skeleton_graph


def build_profile_from_sheet(
    sheet_png: Path | str,
    sheet_json: Path | str,
    source_name: str = "SampleSheet",
) -> StyleProfile:
    """Build a StyleProfile by extracting and vectorizing glyph cells from a sample sheet."""
    sheet_img = Image.open(sheet_png)
    meta = json.loads(Path(sheet_json).read_text(encoding="utf-8"))

    glyph_bank: dict[str, list[GlyphVariant]] = {}
    slants: list[float] = []

    # Process each annotated cell
    for cell in meta.get("cells", []):
        label = cell["label"]
        x0, y0, x1, y1 = cell["box_px"]
        # Add padding
        pad = 4
        crop_box = (
            max(0, x0 + pad),
            max(0, y0 + pad),
            min(sheet_img.width, x1 - pad),
            min(sheet_img.height, y1 - pad),
        )
        cell_crop = sheet_img.crop(crop_box)

        binary = binarize_handwriting(cell_crop)
        if np.sum(binary) < 10:
            continue

        skel = skeletonize_binary(binary)
        recovered = trace_skeleton_graph(skel, min_length_px=3.0, rdp_epsilon=0.8)

        if not recovered:
            continue

        # Convert recovered pixel strokes into normalized local glyph strokes (in mm)
        # Target nominal cap height: ~4.0 mm, x-height ~2.5 mm
        # In crop coordinates:
        cell_h_px = crop_box[3] - crop_box[1]
        scale_mm_per_px = 6.0 / max(1.0, float(cell_h_px))

        # Center and normalize strokes
        pts_all = [pt for st in recovered for pt in st.points]
        min_x = min(pt[0] for pt in pts_all)
        max_x = max(pt[0] for pt in pts_all)
        min_y = min(pt[1] for pt in pts_all)
        max_y = max(pt[1] for pt in pts_all)

        glyph_strokes: list[Stroke] = []
        for st in recovered:
            pts: list[Point] = []
            for pt in st.points:
                # Local mm coordinates with baseline at y=0, bottom upwards
                gx = (pt[0] - min_x) * scale_mm_per_px
                # Invert Y so up is positive
                gy = (max_y - pt[1]) * scale_mm_per_px
                pts.append(Point(gx, gy))
            if len(pts) >= 2:
                glyph_strokes.append(Stroke(pts))

        width_mm = (max_x - min_x) * scale_mm_per_px + 0.5
        height_mm = (max_y - min_y) * scale_mm_per_px

        # Measure stroke angle for slant
        for st in glyph_strokes:
            p0 = st.points[0]
            p1 = st.points[-1]
            dy = p1.y - p0.y
            dx = p1.x - p0.x
            if abs(dy) > 1.0:
                angle_deg = math.degrees(math.atan2(dx, dy))
                if abs(angle_deg) < 45.0:
                    slants.append(angle_deg)

        variant = GlyphVariant(
            char=label,
            strokes=glyph_strokes,
            width_mm=max(1.0, width_mm),
            height_mm=max(1.0, height_mm),
        )
        if label not in glyph_bank:
            glyph_bank[label] = []
        glyph_bank[label].append(variant)

    mean_slant = float(np.mean(slants)) if slants else 0.0

    stats = StyleStats(
        slant_deg=mean_slant,
        x_height_ratio=0.55,
        stroke_curvature_mean=0.0,
        letter_spacing_mm=0.8,
        word_spacing_mm=3.2,
        line_spacing_mm=8.0,
    )

    return StyleProfile(
        source_name=source_name,
        stats=stats,
        glyph_bank=glyph_bank,
    )
