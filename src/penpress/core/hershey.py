"""Hershey single-stroke fallback font loader and text layout engine.

Provides full coverage for:
- ASCII printable characters (32..126)
- Greek alphabet (uppercase and lowercase)
- Essential mathematical symbols (+, -, =, <, >, <=, >=, !=, approx, times, div,
  partial, nabla, infty, sum, prod, int, sqrt, arrows, superscript/subscript digits).
"""

from __future__ import annotations

import json
import re
from collections.abc import Sequence
from dataclasses import dataclass
from importlib import resources
from typing import Any

from penpress.core.primitives import CoreGeometryError, Path, Point, Stroke

HERSHEY_DATA_FILENAME = "hersheytext.min.json"
EXPECTED_HERSHEY_SHA256 = "73709473c12b3ea48b29a8167ef4f84ea7340cfa3f44e65fc0194690edf41ceb"


class MissingGlyphError(CoreGeometryError):
    """Raised when a requested character has no representation in the font catalog."""


@dataclass(frozen=True, slots=True)
class Glyph:
    """A single stroke glyph with drawing paths and horizontal advance metrics.

    Attributes:
        char: The character string represented by this glyph.
        advance_width_units: Relative advance width before scaling.
        strokes: Tuple of Strokes normalized with (0,0) at character origin and baseline at y=0.
    """

    char: str
    advance_width_units: float
    strokes: tuple[Stroke, ...]


def _parse_svg_path_to_strokes(path_d: str) -> list[Stroke]:
    """Parse SVG path data (M x,y and L x,y commands) into a list of Strokes."""
    strokes: list[Stroke] = []
    current_pts: list[Point] = []

    norm = re.sub(r"([a-zA-Z])", r" \1 ", path_d)
    tokens = norm.replace(",", " ").split()
    idx = 0
    cmd = ""

    while idx < len(tokens):
        token = tokens[idx]
        if token in ("M", "L", "m", "l"):
            cmd = token.upper()
            idx += 1
            continue

        # Coordinate pair
        try:
            x = float(token)
            y = float(tokens[idx + 1])
            idx += 2
        except (IndexError, ValueError) as exc:
            raise CoreGeometryError(f"Malformed coordinate token in path '{path_d}': {exc}") from exc

        # In Hershey font coordinates, baseline is around Y=15..22, ascending to Y=1..-3.
        # We invert/normalize so Y=0 is baseline and upward is positive or standard Cartesian:
        # Here we place Y=0 at Hershey baseline Y=22 (so baseline is y=0, top of cap is around y=21).
        norm_x = x
        norm_y = 22.0 - y

        if cmd == "M":
            if len(current_pts) >= 2:
                strokes.append(Stroke(current_pts))
            current_pts = [Point(norm_x, norm_y)]
            cmd = "L"  # subsequent pairs are implicit line-to
        elif cmd == "L":
            current_pts.append(Point(norm_x, norm_y))

    if len(current_pts) >= 2:
        strokes.append(Stroke(current_pts))

    return strokes


# Mathematical symbol custom single-stroke definitions (normalized on 22-unit baseline scale)
MATH_SYMBOL_STROKES: dict[str, tuple[float, list[list[tuple[float, float]]]]] = {
    # char -> (advance_units, list of polylines [[(x,y), ...], ...])
    # Baseline is y=0. Capital height ~21 units, lowercase/x-height ~14 units.
    "<=": (
        16.0,
        [
            [(13.0, 16.0), (3.0, 11.0), (13.0, 6.0)],
            [(3.0, 2.0), (13.0, 2.0)],
        ],
    ),
    ">=": (
        16.0,
        [
            [(3.0, 16.0), (13.0, 11.0), (3.0, 6.0)],
            [(3.0, 2.0), (13.0, 2.0)],
        ],
    ),
    "!=": (
        16.0,
        [
            [(3.0, 12.0), (13.0, 12.0)],
            [(3.0, 6.0), (13.0, 6.0)],
            [(12.0, 17.0), (4.0, 1.0)],
        ],
    ),
    "approx": (
        16.0,
        [
            [(3.0, 13.0), (6.0, 15.0), (10.0, 13.0), (13.0, 15.0)],
            [(3.0, 7.0), (6.0, 9.0), (10.0, 7.0), (13.0, 9.0)],
        ],
    ),
    "times": (
        14.0,
        [
            [(3.0, 4.0), (11.0, 14.0)],
            [(3.0, 14.0), (11.0, 4.0)],
        ],
    ),
    "div": (
        16.0,
        [
            [(3.0, 9.0), (13.0, 9.0)],
            [(8.0, 14.0), (8.0, 15.0)],
            [(8.0, 3.0), (8.0, 4.0)],
        ],
    ),
    "partial": (
        14.0,
        [
            [
                (10.0, 16.0),
                (7.0, 18.0),
                (4.0, 16.0),
                (4.0, 12.0),
                (11.0, 7.0),
                (11.0, 3.0),
                (8.0, 0.0),
                (5.0, 1.0),
            ],
            [(4.0, 6.0), (4.0, 0.0), (11.0, 0.0)],
        ],
    ),
    "nabla": (
        16.0,
        [
            [(3.0, 18.0), (13.0, 18.0), (8.0, 0.0), (3.0, 18.0)],
        ],
    ),
    "infty": (
        20.0,
        [
            [
                (5.0, 9.0),
                (3.0, 12.0),
                (3.0, 6.0),
                (10.0, 12.0),
                (17.0, 6.0),
                (17.0, 12.0),
                (10.0, 6.0),
                (5.0, 9.0),
            ]
        ],
    ),
    "sum": (
        16.0,
        [
            [(14.0, 20.0), (2.0, 20.0), (8.0, 10.0), (2.0, 0.0), (14.0, 0.0)],
        ],
    ),
    "prod": (
        16.0,
        [
            [(2.0, 20.0), (14.0, 20.0)],
            [(4.0, 20.0), (4.0, 0.0)],
            [(12.0, 20.0), (12.0, 0.0)],
        ],
    ),
    "int": (
        12.0,
        [
            [
                (10.0, 22.0),
                (8.0, 24.0),
                (5.0, 24.0),
                (5.0, 18.0),
                (5.0, 4.0),
                (5.0, -2.0),
                (2.0, -2.0),
                (0.0, 0.0),
            ],
        ],
    ),
    "sqrt": (
        16.0,
        [
            [(1.0, 6.0), (3.0, 4.0), (6.0, 22.0), (15.0, 22.0)],
        ],
    ),
    "->": (
        18.0,
        [
            [(2.0, 9.0), (16.0, 9.0)],
            [(11.0, 14.0), (16.0, 9.0), (11.0, 4.0)],
        ],
    ),
    "<-": (
        18.0,
        [
            [(2.0, 9.0), (16.0, 9.0)],
            [(7.0, 14.0), (2.0, 9.0), (7.0, 4.0)],
        ],
    ),
    "<->": (
        20.0,
        [
            [(2.0, 9.0), (18.0, 9.0)],
            [(6.0, 13.0), (2.0, 9.0), (6.0, 5.0)],
            [(14.0, 13.0), (18.0, 9.0), (14.0, 5.0)],
        ],
    ),
    "uparrow": (
        12.0,
        [
            [(6.0, 0.0), (6.0, 20.0)],
            [(2.0, 15.0), (6.0, 20.0), (10.0, 15.0)],
        ],
    ),
    "downarrow": (
        12.0,
        [
            [(6.0, 20.0), (6.0, 0.0)],
            [(2.0, 5.0), (6.0, 0.0), (10.0, 5.0)],
        ],
    ),
}

# Greek mapping to Latin character positions in the Hershey Greek alphabet:
GREEK_ALPHABET_MAP: dict[str, str] = {
    # Uppercase
    "Α": "A",
    "Alpha": "A",
    "Β": "B",
    "Beta": "B",
    "Γ": "G",
    "Gamma": "G",
    "Δ": "D",
    "Delta": "D",
    "Ε": "E",
    "Epsilon": "E",
    "Ζ": "Z",
    "Zeta": "Z",
    "Η": "H",
    "Eta": "H",
    "Θ": "Q",
    "Theta": "Q",
    "Ι": "I",
    "Iota": "I",
    "Κ": "K",
    "Kappa": "K",
    "Λ": "L",
    "Lambda": "L",
    "Μ": "M",
    "Mu": "M",
    "Ν": "N",
    "Nu": "N",
    "Ξ": "C",
    "Xi": "C",
    "Ο": "O",
    "Omicron": "O",
    "Π": "P",
    "Pi": "P",
    "Ρ": "R",
    "Rho": "R",
    "Σ": "S",
    "Sigma": "S",
    "Τ": "T",
    "Tau": "T",
    "Υ": "U",
    "Upsilon": "U",
    "Φ": "F",
    "Phi": "F",
    "Χ": "X",
    "Chi": "X",
    "Ψ": "Y",
    "Psi": "Y",
    "Ω": "W",
    "Omega": "W",
    # Lowercase
    "α": "a",
    "alpha": "a",
    "β": "b",
    "beta": "b",
    "γ": "g",
    "gamma": "g",
    "δ": "d",
    "delta": "d",
    "ε": "e",
    "epsilon": "e",
    "ζ": "z",
    "zeta": "z",
    "η": "h",
    "eta": "h",
    "θ": "q",
    "theta": "q",
    "ι": "i",
    "iota": "i",
    "κ": "k",
    "kappa": "k",
    "λ": "l",
    "lambda": "l",
    "μ": "m",
    "mu": "m",
    "ν": "n",
    "nu": "n",
    "ξ": "c",
    "xi": "c",
    "ο": "o",
    "omicron": "o",
    "π": "p",
    "pi": "p",
    "ρ": "r",
    "rho": "r",
    "σ": "s",
    "sigma": "s",
    "τ": "t",
    "tau": "t",
    "υ": "u",
    "upsilon": "u",
    "φ": "f",
    "phi": "f",
    "χ": "x",
    "chi": "x",
    "ψ": "y",
    "psi": "y",
    "ω": "w",
    "omega": "w",
}

# Subscript and superscript unicode mappings
SUPERSCRIPT_DIGITS: dict[str, str] = {
    "⁰": "0",
    "¹": "1",
    "²": "2",
    "³": "3",
    "⁴": "4",
    "⁵": "5",
    "⁶": "6",
    "⁷": "7",
    "⁸": "8",
    "⁹": "9",
    "⁺": "+",
    "⁻": "-",
    "⁼": "=",
}
SUBSCRIPT_DIGITS: dict[str, str] = {
    "₀": "0",
    "₁": "1",
    "₂": "2",
    "₃": "3",
    "₄": "4",
    "₅": "5",
    "₆": "6",
    "₇": "7",
    "₈": "8",
    "₉": "9",
    "₊": "+",
    "₋": "-",
    "₌": "=",
}


class HersheyFont:
    """Hershey single-stroke vector font catalog and layout generator."""

    def __init__(self, raw_data: dict[str, Any]) -> None:
        self._raw = raw_data
        self._latin = raw_data["futural"]["chars"]
        self._greek = raw_data["greek"]["chars"]
        self._glyphs: dict[str, Glyph] = {}
        self._build_glyph_catalog()

    @classmethod
    def load_default(cls) -> HersheyFont:
        """Load the default Hershey single-stroke font dataset from package resources."""
        data_res = resources.files("penpress.core.data").joinpath(HERSHEY_DATA_FILENAME)
        with data_res.open("r", encoding="utf-8") as f:
            data = json.load(f)
        return cls(data)

    def _build_glyph_catalog(self) -> None:
        """Populate the glyph catalog for ASCII, Greek, and Math."""
        # 1. ASCII Space
        self._glyphs[" "] = Glyph(char=" ", advance_width_units=12.0, strokes=())

        # 2. ASCII Printable (33 to 126)
        for code in range(33, 127):
            ch = chr(code)
            idx = code - 33
            if idx < len(self._latin):
                item = self._latin[idx]
                adv = float(item.get("o", 10)) * 2.0  # scale advance to match width
                d = item.get("d", "")
                strokes = _parse_svg_path_to_strokes(d)
                self._glyphs[ch] = Glyph(char=ch, advance_width_units=adv, strokes=tuple(strokes))

        # 3. Greek Alphabet
        for greek_char, latin_key in GREEK_ALPHABET_MAP.items():
            if len(latin_key) == 1:
                idx = ord(latin_key) - 33
                if 0 <= idx < len(self._greek):
                    item = self._greek[idx]
                    adv = float(item.get("o", 10)) * 2.0
                    d = item.get("d", "")
                    strokes = _parse_svg_path_to_strokes(d)
                    self._glyphs[greek_char] = Glyph(
                        char=greek_char, advance_width_units=adv, strokes=tuple(strokes)
                    )

        # 4. Custom Mathematical Symbols
        for sym, (adv, polylines) in MATH_SYMBOL_STROKES.items():
            strokes_list: list[Stroke] = []
            for poly in polylines:
                pts = [Point(pt[0], pt[1]) for pt in poly]
                if len(pts) >= 2:
                    strokes_list.append(Stroke(pts))
            self._glyphs[sym] = Glyph(char=sym, advance_width_units=adv, strokes=tuple(strokes_list))

        # Aliases for math symbols
        aliases = {
            "≤": "<=",
            "≥": ">=",
            "≠": "!=",
            "≈": "approx",
            "×": "times",
            "÷": "div",
            "∂": "partial",
            "∇": "nabla",
            "∞": "infty",
            "∑": "sum",
            "∏": "prod",
            "∫": "int",
            "√": "sqrt",
            "→": "->",
            "←": "<-",
            "↔": "<->",
            "↑": "uparrow",
            "↓": "downarrow",
        }
        for alias, target in aliases.items():
            if target in self._glyphs:
                target_g = self._glyphs[target]
                self._glyphs[alias] = Glyph(
                    char=alias,
                    advance_width_units=target_g.advance_width_units,
                    strokes=target_g.strokes,
                )

        # 5. Superscripts and Subscripts
        scale_sub_super = 0.65
        for sup_ch, base_ch in SUPERSCRIPT_DIGITS.items():
            if base_ch in self._glyphs:
                base_g = self._glyphs[base_ch]
                # Scale and translate up by 10 units
                scaled_strokes = []
                for s in base_g.strokes:
                    scaled_pts = [
                        Point(p.x * scale_sub_super, p.y * scale_sub_super + 10.0) for p in s.points
                    ]
                    scaled_strokes.append(Stroke(scaled_pts))
                self._glyphs[sup_ch] = Glyph(
                    char=sup_ch,
                    advance_width_units=base_g.advance_width_units * scale_sub_super,
                    strokes=tuple(scaled_strokes),
                )

        for sub_ch, base_ch in SUBSCRIPT_DIGITS.items():
            if base_ch in self._glyphs:
                base_g = self._glyphs[base_ch]
                # Scale and translate down by 4 units
                scaled_strokes = []
                for s in base_g.strokes:
                    scaled_pts = [Point(p.x * scale_sub_super, p.y * scale_sub_super - 4.0) for p in s.points]
                    scaled_strokes.append(Stroke(scaled_pts))
                self._glyphs[sub_ch] = Glyph(
                    char=sub_ch,
                    advance_width_units=base_g.advance_width_units * scale_sub_super,
                    strokes=tuple(scaled_strokes),
                )

    def get_glyph(self, char: str) -> Glyph:
        """Retrieve the Glyph for a given character or raise MissingGlyphError."""
        if char in self._glyphs:
            return self._glyphs[char]
        raise MissingGlyphError(f"MissingGlyph: Character '{char}' (U+{ord(char):04X}) not supported in font")

    def has_glyph(self, char: str) -> bool:
        """Check if character exists in font catalog."""
        return char in self._glyphs

    def layout_line(
        self,
        text: str,
        start_x_mm: float = 0.0,
        baseline_y_mm: float = 0.0,
        font_size_mm: float = 4.0,
        letter_spacing_mm: float = 0.2,
    ) -> list[Path]:
        """Layout a single line of text into mm-coordinate Paths.

        Args:
            text: Input string.
            start_x_mm: Starting X position of baseline in mm.
            baseline_y_mm: Baseline Y position in mm.
            font_size_mm: Height of capital letter in mm (nominally 21 font units).
            letter_spacing_mm: Extra spacing between characters in mm.

        Returns:
            List of Paths representing each character.
        """
        if font_size_mm <= 0.0:
            raise CoreGeometryError(f"font_size_mm must be positive, got {font_size_mm}")

        # Nominal cap height in Hershey units is ~21.0
        scale = font_size_mm / 21.0
        paths: list[Path] = []
        curr_x = start_x_mm

        for ch in text:
            glyph = self.get_glyph(ch)
            if glyph.strokes:
                char_strokes: list[Stroke] = []
                for s in glyph.strokes:
                    transformed_pts = [
                        Point(
                            curr_x + p.x * scale,
                            baseline_y_mm + p.y * scale,
                        )
                        for p in s.points
                    ]
                    char_strokes.append(Stroke(transformed_pts))
                paths.append(Path(char_strokes, label=ch))
            curr_x += glyph.advance_width_units * scale + letter_spacing_mm

        return paths

    def check_coverage(self, characters: Sequence[str]) -> tuple[float, list[str]]:
        """Compute coverage percentage and list missing glyphs."""
        missing = [ch for ch in characters if not self.has_glyph(ch)]
        total = len(characters)
        if total == 0:
            return 100.0, []
        coverage = ((total - len(missing)) / total) * 100.0
        return coverage, missing
