"""Equation handwriting synthesis engine.

Implements Approach A (TeX layout via MathJax + stroke filling from symbol bank/Hershey/wobbly rules)
and Approach B (MathWriting/CROHME InkML trace adaptation with slant/width jitter).
"""

from __future__ import annotations

import json
import math
import random
import subprocess
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from penpress.core.hershey import HersheyFont
from penpress.core.primitives import BoundingBox, Point, Stroke

MATHJAX_LAYOUT_SCRIPT = Path(__file__).resolve().parent.parent / "mathjax_layout.js"

# Custom symbol stroke fallbacks for math characters missing from standard Hershey catalog
ADDITIONAL_MATH_STROKES: dict[str, list[list[tuple[float, float]]]] = {
    # Minus sign: horizontal line centered at mid-height (y=9)
    "−": [[(2.0, 9.0), (14.0, 9.0)]],
    # Plus-minus: plus over minus
    "±": [
        [(8.0, 7.0), (8.0, 17.0)],
        [(3.0, 12.0), (13.0, 12.0)],
        [(3.0, 3.0), (13.0, 3.0)],
    ],
    # Dot operator (\cdot): small square dot at mid-height
    "⋅": [[(7.0, 9.0), (9.0, 9.0), (9.0, 11.0), (7.0, 11.0), (7.0, 9.0)]],
    # Prime (′): diagonal tick
    "′": [[(6.0, 15.0), (10.0, 22.0)]],
    # Double prime (″): two ticks
    "″": [[(4.0, 15.0), (8.0, 22.0)], [(10.0, 15.0), (14.0, 22.0)]],
    # Vector arrow accent (⃗): small right arrow
    "⃗": [[(2.0, 18.0), (14.0, 18.0)], [(10.0, 21.0), (14.0, 18.0), (10.0, 15.0)]],
    # Planck constant over 2pi (hbar ℏ): h with crossbar
    "ℏ": [
        [(4.0, 0.0), (4.0, 22.0)],
        [(4.0, 13.0), (8.0, 15.0), (12.0, 13.0), (12.0, 0.0)],
        [(2.0, 18.0), (7.0, 16.0)],
    ],
    # Ring operator (∘): small circle at mid-height
    "∘": [
        [
            (8.0, 6.0),
            (11.0, 9.0),
            (8.0, 12.0),
            (5.0, 9.0),
            (8.0, 6.0),
        ]
    ],
    # Parallel (∥): two vertical bars
    "∥": [[(5.0, 0.0), (5.0, 20.0)], [(11.0, 0.0), (11.0, 20.0)]],
    # Double integral (∬)
    "∬": [
        [(6.0, 22.0), (4.0, 24.0), (2.0, 24.0), (2.0, 18.0), (2.0, 4.0), (2.0, -2.0), (0.0, -2.0)],
        [(12.0, 22.0), (10.0, 24.0), (8.0, 24.0), (8.0, 18.0), (8.0, 4.0), (8.0, -2.0), (6.0, -2.0)],
    ],
    # Contour integral (∮)
    "∮": [
        [(7.0, 22.0), (5.0, 24.0), (3.0, 24.0), (3.0, 18.0), (3.0, 4.0), (3.0, -2.0), (1.0, -2.0)],
        [(1.0, 10.0), (3.0, 14.0), (7.0, 14.0), (9.0, 10.0), (7.0, 6.0), (3.0, 6.0), (1.0, 10.0)],
    ],
    # Matrix brackets: left square bracket parts
    "⎡": [[(10.0, 20.0), (3.0, 20.0), (3.0, 0.0)]],
    "⎢": [[(3.0, 0.0), (3.0, 20.0)]],
    "⎣": [[(3.0, 20.0), (3.0, 0.0), (10.0, 0.0)]],
    # Right square bracket parts
    "⎤": [[(0.0, 20.0), (7.0, 20.0), (7.0, 0.0)]],
    "⎥": [[(7.0, 0.0), (7.0, 20.0)]],
    "⎦": [[(7.0, 20.0), (7.0, 0.0), (0.0, 0.0)]],
    # Curly braces parts
    "⎧": [[(10.0, 20.0), (4.0, 17.0), (4.0, 0.0)]],
    "⎨": [[(4.0, 20.0), (1.0, 10.0), (4.0, 0.0)]],
    "⎩": [[(4.0, 20.0), (4.0, 3.0), (10.0, 0.0)]],
    "⎪": [[(4.0, 0.0), (4.0, 20.0)]],
}


def _wobbly_line(p0: Point, p1: Point, rng: random.Random, amplitude: float = 0.08) -> Stroke:
    """Generate a straight line with subtle organic human wobble."""
    dx = p1.x - p0.x
    dy = p1.y - p0.y
    length = math.hypot(dx, dy)
    if length < 0.1:
        return Stroke(points=(p0, p1))

    # Resample every ~1.5 mm
    num_steps = max(2, int(length / 1.5))
    pts = [p0]
    perp_x = -dy / length
    perp_y = dx / length

    for i in range(1, num_steps):
        t = i / num_steps
        base_x = p0.x + t * dx
        base_y = p0.y + t * dy
        jitter = rng.uniform(-amplitude, amplitude) * (1.0 - 0.5 * abs(2 * t - 1.0))
        pts.append(Point(x=base_x + jitter * perp_x, y=base_y + jitter * perp_y))

    pts.append(p1)
    return Stroke(points=tuple(pts))


@dataclass(frozen=True, slots=True)
class EquationRenderResult:
    latex: str
    strokes: tuple[Stroke, ...]
    bounds: BoundingBox
    symbol_count: int
    rule_count: int
    fallback_count: int


class EquationEngine:
    """High-precision LaTeX math to vector handwriting strokes compiler."""

    def __init__(self, hershey_font: HersheyFont | None = None) -> None:
        self.hershey = hershey_font or HersheyFont.load_default()

    def layout_latex(self, latex: str) -> dict[str, Any]:
        """Call MathJax layout engine to extract structural elements."""
        cmd = ["node", str(MATHJAX_LAYOUT_SCRIPT), latex]
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True,
            cwd=str(MATHJAX_LAYOUT_SCRIPT.parent),
        )
        return json.loads(proc.stdout)

    def render_equation_to_strokes(
        self,
        latex: str,
        target_height_mm: float = 8.0,
        x_offset: float = 10.0,
        y_offset: float = 10.0,
        seed: int = 1234,
        slant_deg: float = 4.0,
    ) -> EquationRenderResult:
        """Compile a LaTeX math expression into natural handwriting strokes."""
        layout_data = self.layout_latex(latex)
        if layout_data.get("status") != "ok":
            raise ValueError(f"MathJax layout error: {layout_data.get('error')}")

        elements = layout_data.get("elements", [])
        rng = random.Random(seed)

        # Scale factor: MathJax standard EM is 1000 units.
        # We map MathJax EM (1000) to target_height_mm
        scale = target_height_mm / 1000.0
        slant_rad = math.radians(slant_deg)

        strokes_out: list[Stroke] = []
        symbol_count = 0
        rule_count = 0
        fallback_count = 0

        # Mapping for special Greek names
        greek_name_map = {
            "α": "alpha",
            "β": "beta",
            "γ": "gamma",
            "δ": "delta",
            "ε": "epsilon",
            "ζ": "zeta",
            "η": "eta",
            "θ": "theta",
            "ι": "iota",
            "κ": "kappa",
            "λ": "lambda",
            "μ": "mu",
            "ν": "nu",
            "ξ": "xi",
            "π": "pi",
            "ρ": "rho",
            "σ": "sigma",
            "τ": "tau",
            "υ": "upsilon",
            "φ": "phi",
            "χ": "chi",
            "ψ": "psi",
            "ω": "omega",
            "Γ": "Gamma",
            "Δ": "Delta",
            "Θ": "Theta",
            "Λ": "Lambda",
            "Ξ": "Xi",
            "Π": "Pi",
            "Σ": "sum",
            "Φ": "Phi",
            "Ψ": "Psi",
            "Ω": "Omega",
        }

        for el in elements:
            el_type = el.get("type")
            if el_type == "rule":
                # Horizontal fraction bar or radical roof
                rule_count += 1
                rx = x_offset + el["x"] * scale
                # In MathJax, Y is positive upwards, so y_offset + el["y"] * scale
                ry = y_offset + el["y"] * scale
                rw = el["width"] * scale

                # Fraction bar with organic wobble
                p_start = Point(x=rx, y=ry)
                p_end = Point(x=rx + rw, y=ry)
                strokes_out.append(_wobbly_line(p_start, p_end, rng, amplitude=0.06))

            elif el_type == "glyph":
                symbol_count += 1
                hex_c = el.get("char_hex", "")
                if not hex_c:
                    continue
                cp = int(hex_c, 16)
                ch = chr(cp)

                # Skip zero-width invisible operators
                if ch in ("\u2061", "\u200b", "\u200e"):
                    continue

                norm_ch = unicodedata.normalize("NFKD", ch)
                gx = x_offset + el["x"] * scale
                gy = y_offset + el["y"] * scale
                g_scale = el.get("scale_x", 1.0) * scale

                # Locate strokes from Hershey or custom math strokes
                glyph_strokes: list[list[tuple[float, float]]] = []

                # 1. Check custom math symbol table
                if ch in ADDITIONAL_MATH_STROKES:
                    glyph_strokes = ADDITIONAL_MATH_STROKES[ch]
                elif norm_ch in ADDITIONAL_MATH_STROKES:
                    glyph_strokes = ADDITIONAL_MATH_STROKES[norm_ch]
                else:
                    # 2. Check Hershey glyph catalog
                    found_glyph = None
                    lookup_keys = [ch, norm_ch]
                    if ch in greek_name_map:
                        lookup_keys.append(greek_name_map[ch])
                    if norm_ch in greek_name_map:
                        lookup_keys.append(greek_name_map[norm_ch])

                    for k in lookup_keys:
                        try:
                            found_glyph = self.hershey.get_glyph(k)
                            break
                        except Exception:
                            continue

                    if found_glyph is not None:
                        # Extract strokes from found glyph
                        glyph_strokes = [[(pt.x, pt.y) for pt in s.points] for s in found_glyph.strokes]
                    else:
                        fallback_count += 1
                        # Emergency fallback: draw bounding marker or question mark
                        glyph_strokes = [[(2.0, 2.0), (10.0, 2.0), (10.0, 18.0), (2.0, 18.0), (2.0, 2.0)]]

                # Transform glyph strokes to position and apply slant
                for poly in glyph_strokes:
                    transformed_pts: list[Point] = []
                    for px, py in poly:
                        # Scale Hershey units (nominally ~20 units high) to MathJax EM units
                        unit_scale = (1000.0 / 22.0) * g_scale
                        sx = px * unit_scale
                        sy = py * unit_scale

                        # Apply handwriting slant
                        slanted_x = sx + sy * math.tan(slant_rad)
                        # Position on page
                        final_x = gx + slanted_x
                        final_y = gy + sy
                        transformed_pts.append(Point(x=final_x, y=final_y))

                    if len(transformed_pts) >= 2:
                        strokes_out.append(Stroke(points=tuple(transformed_pts)))

        # Compute bounding box
        all_pts = [pt for s in strokes_out for pt in s.points]
        if not all_pts:
            bounds = BoundingBox(min_x=0.0, min_y=0.0, max_x=0.0, max_y=0.0)
        else:
            xs = [p.x for p in all_pts]
            ys = [p.y for p in all_pts]
            bounds = BoundingBox(min_x=min(xs), min_y=min(ys), max_x=max(xs), max_y=max(ys))

        return EquationRenderResult(
            latex=latex,
            strokes=tuple(strokes_out),
            bounds=bounds,
            symbol_count=symbol_count,
            rule_count=rule_count,
            fallback_count=fallback_count,
        )
