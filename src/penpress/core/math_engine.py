"""Mathematical formula handwriting layout and symbol synthesis engine (P4-1).

Compiles LaTeX math expressions into vector handwriting stroke primitives using
MathJax/KaTeX layout trees, 3-tier fallback chain (user profile -> Hershey math glyphs ->
wobbly rules), stretchy delimiters/radicals/fractions, and relative script scaling.
"""

from __future__ import annotations

import json
import math
import random
import shutil
import subprocess
import sys
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from penpress.core.hershey import HersheyFont
from penpress.core.math_symbols import (
    GREEK_NAME_MAP,
    MATH_STROKE_CATALOG,
    build_wobbly_rule,
)
from penpress.core.primitives import BoundingBox, Point, Stroke
from penpress.profile.models import HandwritingProfile


def get_mathjax_script_path() -> Path:
    """Resolve mathjax_layout.js for both dev repository checkout and PyInstaller bundle."""
    base = getattr(sys, "_MEIPASS", None)
    if base:
        p1 = Path(base) / "research" / "R2-1" / "mathjax_layout.js"
        if p1.is_file():
            return p1
        p2 = Path(base) / "mathjax_layout.js"
        if p2.is_file():
            return p2
    return Path(__file__).resolve().parent.parent.parent.parent / "research/R2-1/mathjax_layout.js"


MATHJAX_LAYOUT_SCRIPT = get_mathjax_script_path()


class LaTeXParseError(ValueError):
    """Raised when LaTeX math expression is malformed or cannot be parsed."""


@dataclass(frozen=True, slots=True)
class MathRenderResult:
    """Result of compiling a LaTeX expression into vector handwriting strokes.

    Attributes:
        latex: Source LaTeX string.
        strokes: Tuple of compiled Stroke primitives in mm.
        bounds: Bounding box enclosing the rendered formula in mm.
        symbol_count: Number of glyph symbols rendered.
        rule_count: Number of horizontal rules (fractions/radicals) rendered.
        fallback_count: Number of emergency box fallback symbols rendered.
        relative_script_scale: Subscript/superscript scale ratio relative to parent baseline.
    """

    latex: str
    strokes: tuple[Stroke, ...]
    bounds: BoundingBox
    symbol_count: int
    rule_count: int
    fallback_count: int
    relative_script_scale: float


def validate_latex_syntax(latex: str) -> None:
    """Pre-validate LaTeX syntax to raise explicit LaTeXParseError on obvious syntax truncation."""
    # Fast balance checks for obvious syntax truncation
    open_curly = latex.count("{")
    close_curly = latex.count("}")
    if open_curly != close_curly:
        raise LaTeXParseError(
            f"Unbalanced braces in LaTeX: {open_curly} open '{{' vs {close_curly} close '}}'"
        )

    # Check for unclosed square brackets
    open_square = latex.count("[")
    close_square = latex.count("]")
    if open_square != close_square:
        raise LaTeXParseError(
            f"Unbalanced brackets in LaTeX: {open_square} open '[' vs {close_square} close ']'"
        )


class MathEngine:
    """Compiles LaTeX mathematical formulas into vector handwriting toolpaths."""

    def __init__(
        self,
        hershey_font: HersheyFont | None = None,
        user_profile: HandwritingProfile | None = None,
    ) -> None:
        self.hershey = hershey_font or HersheyFont.load_default()
        self.user_profile = user_profile

    def layout_latex_tree(self, latex: str) -> dict[str, Any]:
        """Call MathJax layout engine to extract structural elements."""
        validate_latex_syntax(latex)

        script_path = get_mathjax_script_path()
        node_bin = shutil.which("node") or shutil.which("node.exe")
        if node_bin and script_path.is_file():
            cmd = [node_bin, str(script_path), latex]
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=False,
                cwd=str(script_path.parent),
            )
            if proc.returncode == 0:
                try:
                    raw_data = json.loads(proc.stdout)
                    if isinstance(raw_data, dict):
                        if raw_data.get("status") == "error":
                            raise LaTeXParseError(f"MathJax error compiling LaTeX: {raw_data.get('error')}")
                        return raw_data
                except LaTeXParseError:
                    raise
                except Exception:
                    pass

        return self._fallback_layout_latex(latex)

    def layout_latex_batch(self, latex_list: list[str]) -> list[dict[str, Any]]:
        """Batch process multiple LaTeX equations in a single persistent Node invocation."""
        for s in latex_list:
            validate_latex_syntax(s)

        script_path = get_mathjax_script_path()
        node_bin = shutil.which("node") or shutil.which("node.exe")
        if node_bin and script_path.is_file():
            payload = "\n".join(json.dumps({"latex": s}) for s in latex_list)
            proc = subprocess.run(
                [node_bin, str(script_path)],
                input=payload,
                text=True,
                capture_output=True,
                check=False,
                cwd=str(script_path.parent),
            )
            if proc.returncode == 0:
                try:
                    batch_data = json.loads(proc.stdout)
                    if isinstance(batch_data, list) and len(batch_data) == len(latex_list):
                        return batch_data
                except Exception:
                    pass

        return [self._fallback_layout_latex(s) for s in latex_list]

    def _fallback_layout_latex(self, latex: str) -> dict[str, Any]:
        """Deterministic vector fallback layout when Node.js/MathJax is unavailable."""
        elements: list[dict[str, Any]] = []
        cursor_x = 0.0

        # Tokenize basic latex: \command, ^, _, {, }, or single character
        tokens: list[str] = []
        i = 0
        while i < len(latex):
            if latex[i].isspace():
                i += 1
                continue
            if latex[i] == "\\":
                j = i + 1
                if j < len(latex) and not latex[j].isalpha():
                    tokens.append(latex[i : j + 1])
                    i = j + 1
                else:
                    while j < len(latex) and latex[j].isalpha():
                        j += 1
                    tokens.append(latex[i:j])
                    i = j
            else:
                tokens.append(latex[i])
                i += 1

        idx = 0
        while idx < len(tokens):
            tok = tokens[idx]
            if tok == r"\frac":
                idx += 1
                num_toks: list[str] = []
                den_toks: list[str] = []
                if idx < len(tokens) and tokens[idx] == "{":
                    idx += 1
                    depth = 1
                    while idx < len(tokens) and depth > 0:
                        if tokens[idx] == "{":
                            depth += 1
                        elif tokens[idx] == "}":
                            depth -= 1
                        if depth > 0:
                            num_toks.append(tokens[idx])
                        idx += 1
                if idx < len(tokens) and tokens[idx] == "{":
                    idx += 1
                    depth = 1
                    while idx < len(tokens) and depth > 0:
                        if tokens[idx] == "{":
                            depth += 1
                        elif tokens[idx] == "}":
                            depth -= 1
                        if depth > 0:
                            den_toks.append(tokens[idx])
                        idx += 1

                num_w = max(len(num_toks) * 450.0, 350.0)
                den_w = max(len(den_toks) * 450.0, 350.0)
                frac_w = max(num_w, den_w) + 120.0

                nx = cursor_x + (frac_w - num_w) / 2.0
                for nt in num_toks:
                    c = nt[1:] if nt.startswith("\\") else nt
                    elements.append(
                        {
                            "type": "glyph",
                            "char_hex": hex(ord(c[0]) if c else ord("x"))[2:],
                            "x": nx,
                            "y": 420.0,
                            "scale_x": 0.80,
                            "scale_y": 0.80,
                        }
                    )
                    nx += 450.0 * 0.80

                dx = cursor_x + (frac_w - den_w) / 2.0
                for dt in den_toks:
                    c = dt[1:] if dt.startswith("\\") else dt
                    elements.append(
                        {
                            "type": "glyph",
                            "char_hex": hex(ord(c[0]) if c else ord("x"))[2:],
                            "x": dx,
                            "y": -320.0,
                            "scale_x": 0.80,
                            "scale_y": 0.80,
                        }
                    )
                    dx += 450.0 * 0.80

                elements.append(
                    {
                        "type": "rule",
                        "x": cursor_x,
                        "y": 140.0,
                        "width": frac_w,
                        "height": 40.0,
                    }
                )
                cursor_x += frac_w + 120.0
                continue
            elif tok == "^":
                idx += 1
                if idx < len(tokens):
                    st = tokens[idx]
                    if st == "{" and idx + 1 < len(tokens):
                        idx += 1
                        st = tokens[idx]
                        if idx + 1 < len(tokens) and tokens[idx + 1] == "}":
                            idx += 1
                    c = st[1:] if st.startswith("\\") else st
                    elements.append(
                        {
                            "type": "glyph",
                            "char_hex": hex(ord(c[0]) if c else ord("x"))[2:],
                            "x": cursor_x,
                            "y": 380.0,
                            "scale_x": 0.70,
                            "scale_y": 0.70,
                        }
                    )
                    cursor_x += 450.0 * 0.70
                idx += 1
                continue
            elif tok == "_":
                idx += 1
                if idx < len(tokens):
                    st = tokens[idx]
                    if st == "{" and idx + 1 < len(tokens):
                        idx += 1
                        st = tokens[idx]
                        if idx + 1 < len(tokens) and tokens[idx + 1] == "}":
                            idx += 1
                    c = st[1:] if st.startswith("\\") else st
                    elements.append(
                        {
                            "type": "glyph",
                            "char_hex": hex(ord(c[0]) if c else ord("x"))[2:],
                            "x": cursor_x,
                            "y": -220.0,
                            "scale_x": 0.70,
                            "scale_y": 0.70,
                        }
                    )
                    cursor_x += 450.0 * 0.70
                idx += 1
                continue
            elif tok in ("{", "}"):
                idx += 1
                continue
            else:
                c = tok[1:] if tok.startswith("\\") else tok
                elements.append(
                    {
                        "type": "glyph",
                        "char_hex": hex(ord(c[0]) if c else ord("?"))[2:],
                        "x": cursor_x,
                        "y": 0.0,
                        "scale_x": 1.0,
                        "scale_y": 1.0,
                    }
                )
                cursor_x += 500.0
                idx += 1

        return {"status": "ok", "elements": elements}

    def render_equation_to_strokes(
        self,
        latex: str,
        target_height_mm: float = 8.0,
        x_offset: float = 10.0,
        y_offset: float = 10.0,
        seed: int = 1234,
        slant_deg: float = 2.0,
        layout_data: dict[str, Any] | None = None,
    ) -> MathRenderResult:
        """Compile a LaTeX math expression into natural handwriting strokes."""
        if layout_data is None:
            layout_data = self.layout_latex_tree(latex)

        if layout_data.get("status") != "ok":
            raise LaTeXParseError(f"MathJax layout error: {layout_data.get('error')}")

        elements = layout_data.get("elements", [])
        rng = random.Random(seed)

        # Scale factor: MathJax standard EM is 1000 units
        scale = target_height_mm / 1000.0
        slant_rad = math.radians(slant_deg)

        strokes_out: list[Stroke] = []
        symbol_count = 0
        rule_count = 0
        fallback_count = 0
        scales_detected: list[float] = []

        for el in elements:
            el_type = el.get("type")
            if el_type == "rule":
                rule_count += 1
                rx = x_offset + el["x"] * scale
                ry = y_offset + el["y"] * scale
                rw = el["width"] * scale

                # Fraction bar or radical roof with subtle organic wobble
                p_start = Point(x=rx, y=ry)
                p_end = Point(x=rx + rw, y=ry)
                strokes_out.append(build_wobbly_rule(p_start, p_end, rng=rng, amplitude_mm=0.04))

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
                elem_scale = abs(el.get("scale_x", 1.0))
                scales_detected.append(elem_scale)
                g_scale = elem_scale * scale

                # Tier 1: Check user handwriting profile bank
                found_user_variant = False
                if self.user_profile is not None:
                    variants = self.user_profile.get_glyph_variants(
                        ch
                    ) or self.user_profile.get_glyph_variants(norm_ch)
                    if variants:
                        chosen_variant = rng.choice(variants)
                        # Scale variant strokes
                        all_v_pts = [p for s in chosen_variant for p in s.points]
                        min_vx = min(p.x for p in all_v_pts)
                        for s in chosen_variant:
                            t_pts: list[Point] = []
                            for pt in s.points:
                                lx = (pt.x - min_vx) * elem_scale
                                ly = pt.y * elem_scale
                                fx = gx + lx + ly * math.tan(slant_rad)
                                fy = gy + ly
                                t_pts.append(Point(fx, fy))
                            if len(t_pts) >= 2:
                                strokes_out.append(Stroke(t_pts))
                        found_user_variant = True

                if found_user_variant:
                    continue

                # Tier 2: Check custom math symbol catalog or Hershey font
                glyph_polys: list[list[tuple[float, float]]] = []

                if ch in MATH_STROKE_CATALOG:
                    glyph_polys = MATH_STROKE_CATALOG[ch]
                elif norm_ch in MATH_STROKE_CATALOG:
                    glyph_polys = MATH_STROKE_CATALOG[norm_ch]
                else:
                    found_hershey = None
                    lookup_keys = [ch, norm_ch]
                    if ch in GREEK_NAME_MAP:
                        lookup_keys.append(GREEK_NAME_MAP[ch])
                    if norm_ch in GREEK_NAME_MAP:
                        lookup_keys.append(GREEK_NAME_MAP[norm_ch])

                    for k in lookup_keys:
                        try:
                            found_hershey = self.hershey.get_glyph(k)
                            break
                        except Exception:
                            continue

                    if found_hershey is not None:
                        glyph_polys = [[(p.x, p.y) for p in s.points] for s in found_hershey.strokes]
                    else:
                        # Tier 3: Emergency fallback box
                        fallback_count += 1
                        glyph_polys = [[(2.0, 2.0), (10.0, 2.0), (10.0, 18.0), (2.0, 18.0), (2.0, 2.0)]]

                # Transform Hershey/Catalog strokes (defined in ~22 unit box) to MathJax EM units
                for poly in glyph_polys:
                    transformed_pts: list[Point] = []
                    for px, py in poly:
                        unit_scale = (1000.0 / 22.0) * g_scale
                        sx = px * unit_scale
                        sy = py * unit_scale
                        slanted_x = sx + sy * math.tan(slant_rad)
                        final_x = gx + slanted_x
                        final_y = gy + sy
                        transformed_pts.append(Point(x=final_x, y=final_y))

                    if len(transformed_pts) >= 2:
                        strokes_out.append(Stroke(points=tuple(transformed_pts)))

        # Relative script scale
        subscript_scales = [s for s in scales_detected if s < 0.95]
        mean_subscript = (sum(subscript_scales) / len(subscript_scales)) if subscript_scales else 0.70

        all_pts = [pt for s in strokes_out for pt in s.points]
        if not all_pts:
            bounds = BoundingBox(min_x=0.0, min_y=0.0, max_x=0.0, max_y=0.0)
        else:
            xs = [p.x for p in all_pts]
            ys = [p.y for p in all_pts]
            bounds = BoundingBox(min_x=min(xs), min_y=min(ys), max_x=max(xs), max_y=max(ys))

        return MathRenderResult(
            latex=latex,
            strokes=tuple(strokes_out),
            bounds=bounds,
            symbol_count=symbol_count,
            rule_count=rule_count,
            fallback_count=fallback_count,
            relative_script_scale=mean_subscript,
        )
