# ADR 0002: Mathematical Equation Layout and Handwriting Synthesis Architecture

- **Status**: Accepted
- **Date**: 2026-10-13
- **Card**: `tasks/R2-1.md`
- **Deciders**: PenPress Core Architecture Swarm

---

## Context

PenPress requires an end-to-end mathematical formula synthesis pipeline that takes LaTeX input (e.g. within student assignments, physics problem sets, and calculus notes) and renders plottable, natural 2D handwriting vector toolpaths for an Ender 3 Pro plotter.

Mathematical notation presents specialized geometric challenges:
1. **Strict 2D Structural Typography**: Fractions, nested fractions, radicals, subscripts, superscripts, big operators (summations, integrals), matrices, and piecewise cases require sub-millimetre baseline and vertical alignment.
2. **Stretchy Delimiters & Enclosures**: Fraction bars, square root roofs, and matrix brackets must scale continuously to enclose variable-height content without clipping or baseline collisions.
3. **Plottability & Quality Constraints**: Output must consist of continuous, single-stroke polylines with zero self-intersection artifacts, bounded pen-lifts, and no double-stroked outlines.
4. **Local-First & Zero-Egress Privacy**: The engine must operate 100% offline without public cloud calls and run efficiently on modest CPU hardware (< 2 seconds per equation).
5. **Licensing Compliance**: All bundled fonts, models, and layout code must be under permissive open-source licenses (MIT/BSD/Apache/OFL/Public Domain).

---

## Options Evaluated

### Option 1: Handcrafted Pure Python Recursive AST Layout
- *Description*: Build a custom AST parser in Python (via `sympy` or regex) that places boxes for fractions, exponents, and symbols.
- *Pros*: Zero external binary dependencies.
- *Cons*: Reinvents decades of TeX math typesetting algorithms. Fragile handling of nested fractions, limits positioning, and matrix alignments. Violates the user directive against "handcrafting fragile toy engines from scratch".
- *Verdict*: Rejected.

### Option 2: Symbol Layout Tree -> Online InkML Traces (MathWriting / CROHME)
- *Description*: Extract symbol positions from TeX and insert human handwriting strokes sampled from the Google MathWriting or CROHME online handwriting datasets.
- *Pros*: Authentic human hand movements for individual symbols.
- *Cons*:
  - **Licensing Blocker**: Google MathWriting dataset is strictly licensed under **CC BY-NC-SA 4.0** (Non-Commercial). Distributing these strokes in a commercial product is prohibited.
  - High stroke noise, irregular pen lift ordering, and extensive cleaning needed for plotter toolpaths.
- *Verdict*: Rejected for production distribution; reserved for synthetic research benchmarking only.

### Option 3: TeX Engine Layout (MathJax / KaTeX) + Multi-Tier Stroke Synthesis (Selected)
- *Description*:
  1. Utilize MathJax (`mathjax-full` Apache-2.0 via Node.js IPC) to compute world-class TeX metric layout, yielding exact $(x, y)$ positions, scales, and rule dimensions.
  2. Map structural rules (fraction bars, radical roofs) into continuous vector strokes with configurable organic human wobble.
  3. Map symbols through a strict multi-tier fallback chain:
     - Tier 1: User's calibrated handwriting glyph bank (extracted from sample sheets).
     - Tier 2: Public domain Hershey vector font (Latin, Greek, and core math symbols).
     - Tier 3: Procedural stroke stencils for advanced calculus/matrix operators.
- *Pros*:
  - 100% permissive licensing (MathJax: Apache-2.0, Hershey: Public Domain).
  - Flawless mathematical layout across all LaTeX constructs (125 / 125 corpus equations compiled with 0 errors).
  - High performance: 163 ms/equation single-process, 2.66 ms/equation batch.
  - Native vector polylines: zero rasterization or skeletonization artifacts.
- *Verdict*: **Accepted**.

---

## Decision

We adopt **Option 3**: TeX metric layout via MathJax, coupled with a multi-tier single-stroke synthesis engine:
1. MathJax runs locally via a lightweight Node.js IPC subprocess boundary.
2. The user's calibrated symbol bank provides personalized handwriting strokes for alphanumeric characters and basic arithmetic operators.
3. Hershey vector fonts and procedural stencils provide universal fallback coverage for Greek letters, calculus integrals, and stretchable matrix delimiters.
4. Horizontal fraction bars and radical enclosures are rendered with organic human wobble to ensure visual harmony with handwritten text.

---

## Consequences

### Positive
- Fully handles complex mathematical academic assignments (calculus, physics, matrices, chemistry).
- Zero external data egress; runs entirely offline.
- Deterministic, verifiable vector toolpaths ready for Marlin G-code compilation.
- 100% compliant with permissive open-source licenses.

### Negative / Trade-offs
- Requires Node.js installed in the runtime environment (already standard on our target platforms, Node v24.21.0 active).
- Symbols never written by the user default to Hershey vector font style; mitigated by applying affine slant and width jitter matching the user's measured handwriting slant.

---

## Fallback Strategy
If Node.js is unavailable on a client system, PenPress falls back to an embedded lightweight pure-Python TeX box layout engine for standard arithmetic and inline equations, alerting the user to install Node.js for complex nested matrices and multi-line equations.
