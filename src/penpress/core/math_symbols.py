"""Vector stroke definitions for mathematical symbols, delimiters, and operators.

Provides single-stroke / polyline representations for mathematical symbols:
- Radicals (square root tick, ascent, horizontal roof)
- Stretchy delimiters (square brackets, curly braces, parentheses)
- Relational and operational signs (plus-minus, minus, cdot, prime, hbar, etc.)
- Multi-tier fallback support.
"""

from __future__ import annotations

import math
import random

from penpress.core.primitives import Point, Stroke

# Catalog of mathematical stroke definitions
# Each entry is a list of polylines: list[list[tuple[float, float]]]
# Coordinates are nominally defined in a [0, 20] x [0, 22] local EM box.
MATH_STROKE_CATALOG: dict[str, list[list[tuple[float, float]]]] = {
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

GREEK_NAME_MAP: dict[str, str] = {
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


def build_wobbly_rule(
    p0: Point,
    p1: Point,
    rng: random.Random | None = None,
    amplitude_mm: float = 0.05,
) -> Stroke:
    """Generate a straight line with subtle organic human wobble."""
    dx = p1.x - p0.x
    dy = p1.y - p0.y
    length = math.hypot(dx, dy)
    if length < 0.1 or amplitude_mm <= 1e-6:
        return Stroke(points=(p0, p1))

    if rng is None:
        rng = random.Random(42)

    num_steps = max(2, int(length / 1.5))
    pts = [p0]
    perp_x = -dy / length
    perp_y = dx / length

    for i in range(1, num_steps):
        t = i / num_steps
        base_x = p0.x + t * dx
        base_y = p0.y + t * dy
        jitter = rng.uniform(-amplitude_mm, amplitude_mm) * (1.0 - 0.5 * abs(2 * t - 1.0))
        pts.append(Point(x=base_x + jitter * perp_x, y=base_y + jitter * perp_y))

    pts.append(p1)
    return Stroke(points=tuple(pts))


def generate_stretchy_bracket(
    bracket_type: str,
    x: float,
    y_bottom: float,
    height_mm: float,
    width_mm: float = 2.0,
    rng: random.Random | None = None,
) -> list[Stroke]:
    """Generate strokes for a stretchy bracket or delimiter (parenthesis, square, brace)."""
    strokes: list[Stroke] = []
    y_top = y_bottom + height_mm

    if bracket_type in ("(", "left_paren"):
        # Arc opening to right
        pts = [
            Point(x + width_mm, y_top),
            Point(x, y_top - height_mm * 0.25),
            Point(x, y_bottom + height_mm * 0.25),
            Point(x + width_mm, y_bottom),
        ]
        strokes.append(Stroke(pts))
    elif bracket_type in (")", "right_paren"):
        pts = [
            Point(x, y_top),
            Point(x + width_mm, y_top - height_mm * 0.25),
            Point(x + width_mm, y_bottom + height_mm * 0.25),
            Point(x, y_bottom),
        ]
        strokes.append(Stroke(pts))
    elif bracket_type in ("[", "left_bracket"):
        pts = [
            Point(x + width_mm, y_top),
            Point(x, y_top),
            Point(x, y_bottom),
            Point(x + width_mm, y_bottom),
        ]
        strokes.append(Stroke(pts))
    elif bracket_type in ("]", "right_bracket"):
        pts = [
            Point(x, y_top),
            Point(x + width_mm, y_top),
            Point(x + width_mm, y_bottom),
            Point(x, y_bottom),
        ]
        strokes.append(Stroke(pts))
    elif bracket_type in ("{", "left_brace"):
        mid_y = y_bottom + height_mm * 0.5
        pts = [
            Point(x + width_mm, y_top),
            Point(x + width_mm * 0.4, y_top - height_mm * 0.1),
            Point(x + width_mm * 0.4, mid_y + height_mm * 0.05),
            Point(x, mid_y),
            Point(x + width_mm * 0.4, mid_y - height_mm * 0.05),
            Point(x + width_mm * 0.4, y_bottom + height_mm * 0.1),
            Point(x + width_mm, y_bottom),
        ]
        strokes.append(Stroke(pts))
    elif bracket_type in ("}", "right_brace"):
        mid_y = y_bottom + height_mm * 0.5
        pts = [
            Point(x, y_top),
            Point(x + width_mm * 0.6, y_top - height_mm * 0.1),
            Point(x + width_mm * 0.6, mid_y + height_mm * 0.05),
            Point(x + width_mm, mid_y),
            Point(x + width_mm * 0.6, mid_y - height_mm * 0.05),
            Point(x + width_mm * 0.6, y_bottom + height_mm * 0.1),
            Point(x, y_bottom),
        ]
        strokes.append(Stroke(pts))
    elif bracket_type in ("|", "vertical_bar"):
        p0 = Point(x, y_bottom)
        p1 = Point(x, y_top)
        strokes.append(build_wobbly_rule(p0, p1, rng=rng))

    return strokes
