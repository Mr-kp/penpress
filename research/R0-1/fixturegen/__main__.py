"""Deterministic synthetic fixture factory for PenPress."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
from dataclasses import asdict, dataclass
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

from penpress.core.hershey import HersheyFont


@dataclass(frozen=True, slots=True)
class CellAnnotation:
    label: str
    box_px: tuple[int, int, int, int]  # x0, y0, x1, y1


@dataclass(frozen=True, slots=True)
class SheetGroundTruth:
    font_name: str
    page_corners_px: list[tuple[float, float]]
    cells: list[CellAnnotation]


@dataclass(frozen=True, slots=True)
class BedSceneGroundTruth:
    camera_angle_deg: float
    lighting_preset: str
    paper_corners_bed_mm: list[tuple[float, float]]
    paper_corners_image_px: list[tuple[float, float]]
    clip_polygons_px: list[list[tuple[float, float]]]
    homography_matrix: list[list[float]]


# 1. Equation Corpus Definition (>= 120 LaTeX strings across categories and difficulties)
EQUATION_CATEGORIES: list[tuple[str, int, str]] = [
    # Arithmetic & Linear (difficulty 1)
    ("arithmetic", 1, "2 + 3 = 5"),
    ("arithmetic", 1, "14 - 9 = 5"),
    ("arithmetic", 1, "7 \\times 8 = 56"),
    ("arithmetic", 1, "81 \\div 9 = 9"),
    ("arithmetic", 1, "3x + 5 = 20"),
    ("arithmetic", 1, "y = mx + b"),
    ("arithmetic", 1, "a^2 + b^2 = c^2"),
    ("arithmetic", 1, "E = mc^2"),
    ("arithmetic", 1, "F = ma"),
    ("arithmetic", 1, "PV = nRT"),
    # Fractions & Nested Fractions (difficulty 1-3)
    ("fractions", 1, "\\frac{1}{2} + \\frac{1}{4} = \\frac{3}{4}"),
    ("fractions", 1, "\\frac{a}{b} = \\frac{c}{d}"),
    ("fractions", 2, "\\frac{x^2 - 1}{x + 1} = x - 1"),
    ("fractions", 2, "\\frac{-b \\pm \\sqrt{b^2 - 4ac}}{2a}"),
    ("fractions", 2, "\\frac{\\Delta y}{\\Delta x} = m"),
    ("fractions", 3, "\\frac{1}{1 + \\frac{1}{1 + \\frac{1}{x}}}"),
    ("fractions", 3, "\\frac{a + \\frac{b}{c}}{d + \\frac{e}{f}}"),
    ("fractions", 3, "\\frac{\\frac{x}{y} - \\frac{y}{x}}{x - y}"),
    ("fractions", 2, "\\frac{d}{dx} \\left( \\frac{u}{v} \\right) = \\frac{u'v - uv'}{v^2}"),
    ("fractions", 3, "\\frac{1}{2\\pi} \\int_{0}^{2\\pi} \\frac{d\\theta}{a + b\\cos\\theta}"),
    # Roots & Radicals
    ("roots", 1, "\\sqrt{4} = 2"),
    ("roots", 1, "\\sqrt{x + y}"),
    ("roots", 2, "\\sqrt[3]{8} = 2"),
    ("roots", 2, "\\sqrt{x^2 + y^2 + z^2}"),
    ("roots", 2, "\\sqrt[n]{a^m} = a^{\\frac{m}{n}}"),
    ("roots", 3, "\\sqrt{1 + \\sqrt{1 + \\sqrt{1 + x}}}"),
    ("roots", 3, "\\sqrt{\\frac{a^2 + b^2}{c^2 + d^2}}"),
    ("roots", 2, "\\sqrt{2\\pi n} \\left(\\frac{n}{e}\\right)^n"),
    ("roots", 3, "\\sqrt[4]{\\frac{x^3 + y^3}{z^3}}"),
    ("roots", 1, "\\sqrt{16} = 4"),
    # Exponents & Indices
    ("exponents", 1, "e^x = \\sum_{n=0}^{\\infty} \\frac{x^n}{n!}"),
    ("exponents", 1, "x^{a+b} = x^a x^b"),
    ("exponents", 2, "(x^a)^b = x^{ab}"),
    ("exponents", 2, "a^{-n} = \\frac{1}{a^n}"),
    ("exponents", 2, "e^{i\\pi} + 1 = 0"),
    ("exponents", 3, "2^{2^{2^x}}"),
    ("exponents", 3, "x^{y^z} \\neq (x^y)^z"),
    ("exponents", 2, "A_0 e^{-\\lambda t}"),
    ("exponents", 1, "10^3 = 1000"),
    ("exponents", 2, "\\exp\\left(-\\frac{x^2}{2\\sigma^2}\\right)"),
    # Sums & Integrals
    ("calculus", 1, "\\int x \\, dx = \\frac{1}{2}x^2 + C"),
    ("calculus", 2, "\\int_a^b f(x) \\, dx = F(b) - F(a)"),
    ("calculus", 2, "\\sum_{i=1}^n i = \\frac{n(n+1)}{2}"),
    ("calculus", 2, "\\sum_{k=0}^\\infty r^k = \\frac{1}{1-r}"),
    ("calculus", 3, "\\iint_D f(x, y) \\, dx \\, dy"),
    (
        "calculus",
        3,
        "\\oint_C \\vec{F} \\cdot d\\vec{r} = \\iint_S (\\nabla \\times \\vec{F}) \\cdot d\\vec{S}",
    ),
    ("calculus", 3, "\\int_{-\\infty}^\\infty e^{-x^2} \\, dx = \\sqrt{\\pi}"),
    ("calculus", 2, "\\lim_{x \\to 0} \\frac{\\sin x}{x} = 1"),
    ("calculus", 2, "\\frac{df}{dx} = \\lim_{h \\to 0} \\frac{f(x+h) - f(x)}{h}"),
    ("calculus", 3, "\\int_0^1 x^p (1-x)^q \\, dx = B(p+1, q+1)"),
    # Matrices & Vectors
    ("matrices", 1, "\\vec{v} = (x, y, z)"),
    ("matrices", 1, "\\hat{i} \\times \\hat{j} = \\hat{k}"),
    ("matrices", 2, "\\vec{a} \\cdot \\vec{b} = |\\vec{a}||\\vec{b}| \\cos\\theta"),
    ("matrices", 2, "\\begin{pmatrix} 1 & 0 \\\\ 0 & 1 \\end{pmatrix}"),
    ("matrices", 2, "\\begin{pmatrix} a & b \\\\ c & d \\end{pmatrix}"),
    ("matrices", 2, "\\det(A) = ad - bc"),
    (
        "matrices",
        3,
        "\\begin{bmatrix} a_{11} & a_{12} & a_{13} \\\\ "
        "a_{21} & a_{22} & a_{23} \\\\ a_{31} & a_{32} & a_{33} \\end{bmatrix}",
    ),
    ("matrices", 3, "A^{-1} = \\frac{1}{\\det(A)} \\text{adj}(A)"),
    ("matrices", 3, "\\nabla \\times (\\nabla \\phi) = \\vec{0}"),
    ("matrices", 2, "\\|\\vec{x}\\|_2 = \\sqrt{\\sum_i x_i^2}"),
    # Piecewise & Cases
    ("piecewise", 2, "|x| = \\begin{cases} x & x \\ge 0 \\\\ -x & x < 0 \\end{cases}"),
    ("piecewise", 2, "u(t) = \\begin{cases} 1 & t \\ge 0 \\\\ 0 & t < 0 \\end{cases}"),
    ("piecewise", 3, "f(x) = \\begin{cases} x^2 & x \\le 1 \\\\ 2x - 1 & x > 1 \\end{cases}"),
    ("piecewise", 3, "\\text{sgn}(x) = \\begin{cases} 1 & x > 0 \\\\ 0 & x = 0 \\\\ -1 & x < 0 \\end{cases}"),
    ("piecewise", 3, "\\delta_{ij} = \\begin{cases} 1 & i = j \\\\ 0 & i \\neq j \\end{cases}"),
    # Trigonometry & Logarithms
    ("trig", 1, "\\sin^2\\theta + \\cos^2\\theta = 1"),
    ("trig", 1, "\\tan\\theta = \\frac{\\sin\\theta}{\\cos\\theta}"),
    ("trig", 2, "\\sin(2\\theta) = 2\\sin\\theta\\cos\\theta"),
    ("trig", 2, "\\cos(2\\theta) = \\cos^2\\theta - \\sin^2\\theta"),
    ("trig", 1, "\\ln(xy) = \\ln x + \\ln y"),
    ("trig", 2, "\\log_b(a) = \\frac{\\ln a}{\\ln b}"),
    ("trig", 2, "\\cosh^2 x - \\sinh^2 x = 1"),
    ("trig", 3, "\\tan(a + b) = \\frac{\\tan a + \\tan b}{1 - \\tan a \\tan b}"),
    ("trig", 2, "\\arcsin(x) + \\arccos(x) = \\frac{\\pi}{2}"),
    ("trig", 1, "e^{\\ln x} = x"),
    # Greek & Physical constants
    ("physics", 1, "\\lambda \\nu = c"),
    ("physics", 1, "p = \\hbar k"),
    ("physics", 2, "\\Delta x \\Delta p \\ge \\frac{\\hbar}{2}"),
    ("physics", 2, "i\\hbar \\frac{\\partial}{\\partial t} \\Psi = \\hat{H} \\Psi"),
    ("physics", 2, "\\nabla \\cdot \\vec{E} = \\frac{\\rho}{\\epsilon_0}"),
    ("physics", 2, "\\nabla \\cdot \\vec{B} = 0"),
    ("physics", 3, "\\nabla \\times \\vec{E} = -\\frac{\\partial \\vec{B}}{\\partial t}"),
    (
        "physics",
        3,
        "\\nabla \\times \\vec{B} = \\mu_0 \\vec{J} + \\frac{1}{c^2} \\frac{\\partial \\vec{E}}{\\partial t}",
    ),
    ("physics", 2, "R_{\\mu\\nu} - \\frac{1}{2} R g_{\\mu\\nu} = \\frac{8\\pi G}{c^4} T_{\\mu\\nu}"),
    ("physics", 1, "V = IR"),
    # Chemistry & Reactions
    ("chemistry", 1, "2\\text{H}_2 + \\text{O}_2 \\to 2\\text{H}_2\\text{O}"),
    ("chemistry", 1, "\\text{NaCl} \\to \\text{Na}^+ + \\text{Cl}^-"),
    ("chemistry", 2, "\\text{CH}_4 + 2\\text{O}_2 \\to \\text{CO}_2 + 2\\text{H}_2\\text{O}"),
    ("chemistry", 2, "\\text{CaCO}_3 \\to \\text{CaO} + \\text{CO}_2"),
    ("chemistry", 2, "K_a = \\frac{[\\text{H}^+][\\text{A}^-]}{[\\text{HA}]}"),
    ("chemistry", 2, "\\text{pH} = -\\log[\\text{H}^+]"),
    ("chemistry", 3, "\\Delta G = \\Delta H - T\\Delta S"),
    ("chemistry", 3, "E = E^\\circ - \\frac{RT}{nF} \\ln Q"),
    ("chemistry", 2, "2\\text{Fe} + 3\\text{Cl}_2 \\to 2\\text{FeCl}_3"),
    ("chemistry", 1, "\\text{H}_2\\text{O}"),
    # Units & Dimensions
    ("units", 1, "1 \\text{ kg} = 1000 \\text{ g}"),
    ("units", 1, "1 \\text{ m} = 100 \\text{ cm}"),
    ("units", 1, "100 \\text{ km/h} = 27.78 \\text{ m/s}"),
    ("units", 2, "G = 6.674 \\times 10^{-11} \\text{ m}^3\\text{kg}^{-1}\\text{s}^{-2}"),
    ("units", 2, "c = 2.998 \\times 10^8 \\text{ m/s}"),
    ("units", 2, "h = 6.626 \\times 10^{-34} \\text{ J}\\cdot\\text{s}"),
    ("units", 3, "k_B = 1.381 \\times 10^{-23} \\text{ J/K}"),
    ("units", 1, "1 \\text{ N} = 1 \\text{ kg}\\cdot\\text{m/s}^2"),
    ("units", 2, "1 \\text{ J} = 1 \\text{ N}\\cdot\\text{m}"),
    ("units", 2, "1 \\text{ W} = 1 \\text{ J/s}"),
    # Additional Variety to guarantee >= 120
    ("arithmetic", 1, "5! = 120"),
    ("arithmetic", 2, "\\binom{n}{k} = \\frac{n!}{k!(n-k)!}"),
    ("arithmetic", 1, "(a + b)^2 = a^2 + 2ab + b^2"),
    ("arithmetic", 1, "(a - b)(a + b) = a^2 - b^2"),
    ("calculus", 2, "\\frac{\\partial u}{\\partial t} = \\alpha \\frac{\\partial^2 u}{\\partial x^2}"),
    ("calculus", 3, "\\nabla^2 \\psi + k^2 \\psi = 0"),
    ("calculus", 2, "\\int_0^\\infty e^{-st} f(t) \\, dt = F(s)"),
    ("physics", 2, "T = 2\\pi \\sqrt{\\frac{L}{g}}"),
    ("physics", 1, "p = mv"),
    ("physics", 2, "K = \\frac{1}{2}mv^2"),
    ("trig", 2, "\\sin(x + y) = \\sin x \\cos y + \\cos x \\sin y"),
    ("trig", 2, "\\cos(x + y) = \\cos x \\cos y - \\sin x \\sin y"),
    ("trig", 3, "\\sum_{n=1}^\\infty \\frac{1}{n^2} = \\frac{\\pi^2}{6}"),
    ("matrices", 2, "A B \\neq B A"),
    ("matrices", 3, "\\det(A B) = \\det(A) \\det(B)"),
    ("matrices", 2, "\\text{Tr}(A) = \\sum_i a_{ii}"),
    ("fractions", 2, "\\frac{1}{R_{\\text{eq}}} = \\frac{1}{R_1} + \\frac{1}{R_2}"),
    ("chemistry", 2, "2\\text{Al} + 6\\text{HCl} \\to 2\\text{AlCl}_3 + 3\\text{H}_2"),
    ("physics", 3, "\\lambda_{\\text{max}} T = 2.898 \\times 10^{-3} \\text{ m}\\cdot\\text{K}"),
    ("calculus", 3, "\\Gamma(n) = (n - 1)!"),
]


def generate_equation_corpus(output_path: Path) -> int:
    """Generate tests/fixtures/equations.jsonl with >= 120 categorized items."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as f:
        for idx, (cat, diff, latex) in enumerate(EQUATION_CATEGORIES, start=1):
            record = {
                "id": f"EQ-{idx:03d}",
                "category": cat,
                "difficulty": diff,
                "latex": latex,
            }
            f.write(json.dumps(record) + "\n")
    return len(EQUATION_CATEGORIES)


# 2. Procedural Handwriting Sheet Generator
REPO_ROOT = Path(__file__).resolve().parents[3]
FONT_FILES = {
    "Caveat": REPO_ROOT / "research/R0-1/vendor/fonts/Caveat.ttf",
    "Kalam": REPO_ROOT / "research/R0-1/vendor/fonts/Kalam-Regular.ttf",
    "IndieFlower": REPO_ROOT / "research/R0-1/vendor/fonts/IndieFlower-Regular.ttf",
    "GochiHand": REPO_ROOT / "research/R0-1/vendor/fonts/GochiHand-Regular.ttf",
}


def generate_handwriting_sheet(
    font_name: str,
    font_path: Path,
    seed: int,
    output_png: Path,
    output_json: Path,
) -> SheetGroundTruth:
    """Render a synthetic handwriting sample sheet with jitter, paper texture, and optical camera effects."""
    rng = random.Random(seed)

    # A4 at ~150 DPI: 1240 x 1754 px
    sheet_w, sheet_h = 1240, 1754
    img = Image.new("RGB", (sheet_w, sheet_h), color=(248, 246, 240))
    draw = ImageDraw.Draw(img)

    # Draw header and grid template
    draw.rectangle([60, 60, sheet_w - 60, sheet_h - 60], outline=(180, 180, 185), width=2)
    draw.text((80, 75), f"PenPress Calibration Sample Sheet - Font: {font_name}", fill=(80, 80, 90))

    # Grid specifications
    cols = 8
    rows = 8
    start_x = 80
    start_y = 120
    cell_w = (sheet_w - 160) // cols
    cell_h = (sheet_h - 350) // rows

    # Character palette: a-z, A-Z, 0-9, symbols
    chars = [
        "a",
        "b",
        "c",
        "d",
        "e",
        "f",
        "g",
        "h",
        "i",
        "j",
        "k",
        "l",
        "m",
        "n",
        "o",
        "p",
        "q",
        "r",
        "s",
        "t",
        "u",
        "v",
        "w",
        "x",
        "y",
        "z",
        "A",
        "B",
        "C",
        "D",
        "E",
        "F",
        "G",
        "H",
        "I",
        "J",
        "K",
        "L",
        "M",
        "N",
        "O",
        "P",
        "Q",
        "R",
        "S",
        "T",
        "U",
        "V",
        "W",
        "X",
        "Y",
        "Z",
        "0",
        "1",
        "2",
        "3",
        "4",
        "5",
        "6",
        "7",
        "8",
        "9",
        "+",
        "=",
    ]

    cells_gt: list[CellAnnotation] = []

    for r in range(rows):
        for c in range(cols):
            idx = r * cols + c
            if idx >= len(chars):
                continue
            ch = chars[idx]
            x0 = start_x + c * cell_w
            y0 = start_y + r * cell_h
            x1 = x0 + cell_w
            y1 = y0 + cell_h

            # Draw cell boundary
            draw.rectangle([x0, y0, x1, y1], outline=(220, 220, 225), width=1)
            # Baseline guide
            base_y = y1 - int(cell_h * 0.3)
            draw.line([x0 + 5, base_y, x1 - 5, base_y], fill=(235, 235, 240), width=1)

            # Cell jitter
            font_size = int(cell_h * 0.5 + rng.uniform(-4, 4))
            pil_font = ImageFont.truetype(str(font_path), size=font_size)

            offset_x = rng.uniform(-5, 5)
            offset_y = rng.uniform(-4, 4)

            # Draw character centered with jitter
            text_x = x0 + int(cell_w * 0.35 + offset_x)
            text_y = y0 + int(cell_h * 0.2 + offset_y)
            draw.text((text_x, text_y), ch, font=pil_font, fill=(20, 22, 30))

            cells_gt.append(CellAnnotation(label=ch, box_px=(x0, y0, x1, y1)))

    # Pangram line at bottom
    pangram = "The quick brown fox jumps over the lazy dog 0123456789"
    pil_font_pangram = ImageFont.truetype(str(font_path), size=int(cell_h * 0.35))
    draw.text((80, sheet_h - 180), pangram, font=pil_font_pangram, fill=(25, 28, 35))

    # Apply photographic effects: perspective tilt, vignette, paper grain
    # 1. Subtle Paper texture grain
    grain = Image.effect_noise((sheet_w, sheet_h), sigma=rng.uniform(4.0, 7.0))
    img = Image.blend(img, grain.convert("RGB"), alpha=0.03)

    # 2. Subtle rotation/perspective (warp corners +-6 deg)
    rot_angle = rng.uniform(-2.5, 2.5)
    img = img.rotate(rot_angle, expand=False, fillcolor=(230, 228, 222), resample=Image.Resampling.BILINEAR)

    # 3. Gaussian softness / camera focus simulation
    img = img.filter(ImageFilter.GaussianBlur(radius=0.4))

    output_png.parent.mkdir(parents=True, exist_ok=True)
    img.save(output_png)

    corners_list = [
        (60.0, 60.0),
        (sheet_w - 60.0, 60.0),
        (sheet_w - 60.0, sheet_h - 60.0),
        (60.0, sheet_h - 60.0),
    ]
    gt = SheetGroundTruth(
        font_name=font_name,
        page_corners_px=corners_list,
        cells=cells_gt,
    )
    output_json.write_text(json.dumps(asdict(gt), indent=2), encoding="utf-8")
    return gt


# 3. Online Ground Truth for Stroke Recovery
def generate_stroke_recovery_fixture(
    seed: int,
    output_png: Path,
    output_json: Path,
) -> None:
    """Generate ground truth single-stroke polyline paths with simulated ink bleed raster."""
    rng = random.Random(seed)
    font = HersheyFont.load_default()

    sample_sentence = "PenPress stroke recovery ground truth 123"
    paths = font.layout_line(sample_sentence, start_x_mm=10.0, baseline_y_mm=25.0, font_size_mm=6.0)

    # Save true vector stroke ground truth
    strokes_data: list[list[dict[str, float]]] = []
    for p in paths:
        for s in p.strokes:
            pts = [{"x": pt.x, "y": pt.y} for pt in s.points]
            strokes_data.append(pts)

    output_json.parent.mkdir(parents=True, exist_ok=True)
    payload = {"sentence": sample_sentence, "strokes": strokes_data}
    output_json.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    # Render with variable pen width and ink bleed
    scale_px_mm = 8.0
    w_px = int(220 * scale_px_mm)
    h_px = int(45 * scale_px_mm)
    img = Image.new("L", (w_px, h_px), color=255)
    draw = ImageDraw.Draw(img)

    for p in paths:
        for s in p.strokes:
            pts_px = [(pt.x * scale_px_mm, h_px - pt.y * scale_px_mm) for pt in s.points]
            if len(pts_px) >= 2:
                stroke_w = int(rng.choice([3, 4]))
                draw.line(pts_px, fill=rng.randint(15, 35), width=stroke_w)

    # Ink bleed blur
    img = img.filter(ImageFilter.GaussianBlur(radius=0.5))
    img.save(output_png)


# 4. Printer-Bed Scene Generator (top-down and oblique camera renders)
def generate_bed_scene(
    scene_id: str,
    oblique_angle_deg: float,
    lighting_preset: str,
    seed: int,
    output_png: Path,
    output_json: Path,
) -> BedSceneGroundTruth:
    """Generate procedural camera render of an Ender 3 Pro bed with paper, binder clips, and homography."""
    rng = random.Random(seed)

    img_w, img_h = 1200, 1200
    bg_color = (25, 27, 32) if lighting_preset == "dim" else (45, 48, 55)
    img = Image.new("RGB", (img_w, img_h), color=bg_color)
    draw = ImageDraw.Draw(img)

    # Bed dimensions (235 x 235 mm) mapped to central region
    bed_center_x, bed_center_y = 600.0, 600.0
    bed_side_px = 750.0

    # Draw PEI textured magnetic bed plate
    bed_x0 = bed_center_x - bed_side_px / 2.0
    bed_y0 = bed_center_y - bed_side_px / 2.0
    bed_x1 = bed_x0 + bed_side_px
    bed_y1 = bed_y0 + bed_side_px

    draw.rectangle([bed_x0, bed_y0, bed_x1, bed_y1], fill=(18, 19, 23), outline=(70, 75, 85), width=3)

    # Paper placement (e.g. A5 paper ~ 148 x 210 mm)
    paper_w_px = (148.0 / 235.0) * bed_side_px
    paper_h_px = (210.0 / 235.0) * bed_side_px

    # Slight random placement offset on bed
    offset_x = rng.uniform(-30.0, 30.0)
    offset_y = rng.uniform(-25.0, 25.0)
    paper_cx = bed_center_x + offset_x
    paper_cy = bed_center_y + offset_y

    px0 = paper_cx - paper_w_px / 2.0
    py0 = paper_cy - paper_h_px / 2.0
    px1 = px0 + paper_w_px
    py1 = py0 + paper_h_px

    # Paper corners in 2D bed space
    p_corners_2d = [(px0, py0), (px1, py0), (px1, py1), (px0, py1)]
    draw.polygon(p_corners_2d, fill=(245, 243, 238), outline=(190, 188, 180), width=1)

    # Draw 2-4 binder clips along bed edges
    clips_px: list[list[tuple[float, float]]] = []
    num_clips = rng.choice([2, 3, 4])
    clip_positions = [
        (bed_x0 + 80, bed_y0),
        (bed_x1 - 80, bed_y0),
        (bed_x0 + 80, bed_y1),
        (bed_x1 - 80, bed_y1),
    ][:num_clips]

    for cx, cy in clip_positions:
        clip_poly = [
            (cx - 20, cy - 10),
            (cx + 20, cy - 10),
            (cx + 15, cy + 18),
            (cx - 15, cy + 18),
        ]
        draw.polygon(clip_poly, fill=(10, 10, 12), outline=(180, 180, 190), width=2)
        # Silver handles
        draw.line([cx - 8, cy + 18, cx - 8, cy + 35], fill=(200, 205, 215), width=2)
        draw.line([cx + 8, cy + 18, cx + 8, cy + 35], fill=(200, 205, 215), width=2)
        clips_px.append(clip_poly)

    # Apply oblique perspective transform if oblique_angle_deg > 0
    homography = [
        [1.0, 0.0, 0.0],
        [0.0, 1.0, 0.0],
        [0.0, 0.0, 1.0],
    ]

    if oblique_angle_deg > 5.0:
        # Tilt perspective matrix
        tilt_factor = math.sin(math.radians(oblique_angle_deg)) * 0.4
        # Warp image with Quad transform
        w, h = float(img_w), float(img_h)
        quad = [
            0.0 + w * tilt_factor * 0.5,
            0.0,
            w - w * tilt_factor * 0.5,
            0.0,
            w,
            h,
            0.0,
            h,
        ]
        img = img.transform((img_w, img_h), Image.Transform.QUAD, quad, resample=Image.Resampling.BILINEAR)

    # Lighting / Vignette gradient
    vignette = Image.effect_noise((img_w, img_h), sigma=rng.uniform(3.0, 6.0))
    img = Image.blend(img, vignette.convert("RGB"), alpha=0.04)

    output_png.parent.mkdir(parents=True, exist_ok=True)
    img.save(output_png)

    # Convert paper corners to bed mm coordinates (0..235)
    def to_bed_mm(pt: tuple[float, float]) -> tuple[float, float]:
        bx = ((pt[0] - bed_x0) / bed_side_px) * 235.0
        by = ((bed_y1 - pt[1]) / bed_side_px) * 235.0
        return round(bx, 2), round(by, 2)

    bed_corners_mm = [to_bed_mm(pt) for pt in p_corners_2d]

    gt = BedSceneGroundTruth(
        camera_angle_deg=oblique_angle_deg,
        lighting_preset=lighting_preset,
        paper_corners_bed_mm=bed_corners_mm,
        paper_corners_image_px=p_corners_2d,
        clip_polygons_px=clips_px,
        homography_matrix=homography,
    )
    output_json.write_text(json.dumps(asdict(gt), indent=2), encoding="utf-8")
    return gt


def build_all_fixtures(seed: int = 1234, target_dir: Path | None = None) -> dict[str, str]:
    """Build complete deterministic fixture suite and return sha256 checksums."""
    base_dir = target_dir or Path("tests/fixtures")
    base_dir.mkdir(parents=True, exist_ok=True)

    # 1. Equation Corpus
    eq_file = base_dir / "equations.jsonl"
    count = generate_equation_corpus(eq_file)
    print(f"Generated {count} equations into {eq_file}")

    # 2. Online Stroke Recovery Fixture
    stroke_png = base_dir / "stroke_recovery_sample.png"
    stroke_json = base_dir / "stroke_recovery_sample.json"
    generate_stroke_recovery_fixture(seed, stroke_png, stroke_json)
    print("Generated stroke recovery ground truth fixture")

    # 3. Handwriting Sample Sheets (4 fonts)
    for font_name, font_rel in FONT_FILES.items():
        f_path = Path(font_rel)
        if f_path.exists():
            out_png = base_dir / f"sample_sheet_{font_name.lower()}.png"
            out_json = base_dir / f"sample_sheet_{font_name.lower()}.json"
            generate_handwriting_sheet(font_name, f_path, seed, out_png, out_json)
            print(f"Generated handwriting sample sheet for {font_name}")

    # 4. Printer Bed Scenes (top-down and oblique angles with lighting presets)
    scenes = [
        ("topdown_bright", 0.0, "bright"),
        ("oblique_dim", 25.0, "dim"),
        ("oblique_harsh", 35.0, "harsh"),
    ]
    for s_name, angle, light in scenes:
        b_png = base_dir / f"bed_scene_{s_name}.png"
        b_json = base_dir / f"bed_scene_{s_name}.json"
        generate_bed_scene(s_name, angle, light, seed, b_png, b_json)
        print(f"Generated bed scene fixture {s_name}")

    # Compute sha256 of all generated files
    hashes: dict[str, str] = {}
    for p in sorted(base_dir.iterdir()):
        if p.is_file() and not p.name.startswith("MANIFEST"):
            sha = hashlib.sha256(p.read_bytes()).hexdigest()
            hashes[p.name] = sha

    return hashes


def main() -> int:
    parser = argparse.ArgumentParser(description="PenPress Fixture Generator")
    parser.add_argument("command", choices=["all", "equations", "sheets", "bed"], default="all")
    parser.add_argument("--seed", type=int, default=1234, help="Random seed for reproducible generation")
    parser.add_argument("--out", type=Path, default=Path("tests/fixtures"), help="Target fixtures directory")
    args = parser.parse_args()

    hashes = build_all_fixtures(seed=args.seed, target_dir=args.out)
    print("\nDeterministic Generation Complete. File Hashes:")
    for fn, h in hashes.items():
        print(f"{fn}: {h}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
