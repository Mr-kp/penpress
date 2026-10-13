"""Equation detection, isolation, and LaTeX extraction module for document ingest.

Detects display equations ($$ ... $$ or standalone lines), mathematical symbols,
and extracts clean LaTeX strings for the MathJax vector rendering engine.
"""

from __future__ import annotations

import re

from penpress.ingest.schema import BoundingBox

# Patterns indicating LaTeX mathematical notation
MATH_PATTERNS = [
    re.compile(r"\$\$(.*?)\$\$", re.DOTALL),
    re.compile(r"\\\[(.*?)\\\]", re.DOTALL),
    re.compile(r"\\begin\{(equation|align|gather)\*?\}(.*?)\\end\{\1\*?\}", re.DOTALL),
    re.compile(
        r"\b(sum|int|iint|iiint|oint|nabla|partial|frac|sqrt|alpha|beta|gamma|theta|omega|kappa|mu|rho|phi)\b"
    ),
]

# Common math operators and unicode Greek symbols
MATH_CHARS = set("=+-*/^_{}∫∬∭∮∂∇∑√αβγδεθλμπρστφωΩ")


def is_math_block(text: str, bbox: BoundingBox, page_width: float) -> bool:
    """Heuristic classifier for mathematical equation blocks."""
    stripped = text.strip()
    if not stripped:
        return False

    # Check for explicit LaTeX markers
    if "$$" in stripped or "\\[" in stripped or "\\begin{" in stripped:
        return True

    # Count mathematical symbols
    math_char_count = sum(1 for c in stripped if c in MATH_CHARS or c in "\\_^{}")

    # Standalone centered equation check
    center_dist = abs((bbox.x0 + bbox.x1) / 2.0 - page_width / 2.0)
    is_centered = center_dist < (0.25 * page_width) and bbox.width < (0.85 * page_width)

    if math_char_count >= 3 and (math_char_count / max(1, len(stripped))) > 0.15:
        return True

    has_rel_op = any(op in stripped for op in ("=", "≈", "≤", "≥"))
    return bool(is_centered and has_rel_op and math_char_count >= 2)


def clean_latex(raw_text: str) -> str:
    """Cleans and extracts standardized LaTeX expression from text block."""
    stripped = raw_text.strip()
    # Strip enclosing $$ or \[ \] if present
    m = re.search(r"\$\$(.*?)\$\$", stripped, re.DOTALL)
    if m:
        return m.group(1).strip()

    m_bracket = re.search(r"\\\[(.*?)\\\]", stripped, re.DOTALL)
    if m_bracket:
        return m_bracket.group(1).strip()

    # Clean leading label e.g., "Equation 1:" or "(1)"
    cleaned = re.sub(r"^(Equation\s+\d+:?|\(\d+\))\s*", "", stripped, flags=re.IGNORECASE).strip()
    if cleaned.startswith("$$") and cleaned.endswith("$$"):
        cleaned = cleaned[2:-2].strip()

    return cleaned
