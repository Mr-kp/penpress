"""Fixture generator for R4-1 PDF Ingest benchmark.

Generates:
1. single_column_academic.pdf (headings, paragraphs, lists, equations)
2. two_column_article.pdf (two-column layout with figures and equations)
3. mixed_math_assignment.pdf (equations, tables, problem sets)
4. vector_figure_circuit.pdf (vector lines, rects, curves, labels)
5. scanned_page_noisy.pdf (rasterised page with scan skew and noise)
6. hostile_oversized.pdf (extreme 5000x5000 pt page)
7. hostile_huge_image.pdf (very large embedded image)
8. hostile_malformed.pdf (corrupted PDF header/trailer byte sequences)
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pypdfium2 as pdfium
from PIL import Image, ImageDraw
from reportlab.lib.colors import HexColor, black
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.pdfgen import canvas
from reportlab.platypus import (
    HRFlowable,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


def generate_single_column_academic(out_path: Path) -> dict:
    doc = SimpleDocTemplate(
        str(out_path),
        pagesize=letter,
        leftMargin=54,
        rightMargin=54,
        topMargin=54,
        bottomMargin=54,
    )
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "DocTitle",
        parent=styles["Title"],
        fontSize=20,
        leading=24,
        spaceAfter=12,
        textColor=HexColor("#111827"),
    )
    h1_style = ParagraphStyle(
        "Heading1",
        parent=styles["Heading1"],
        fontSize=14,
        leading=18,
        spaceBefore=14,
        spaceAfter=6,
        textColor=HexColor("#1f2937"),
    )
    body_style = ParagraphStyle(
        "Body",
        parent=styles["Normal"],
        fontSize=10,
        leading=14,
        spaceAfter=8,
        textColor=HexColor("#374151"),
    )
    code_style = ParagraphStyle(
        "CodeMath",
        parent=styles["Code"],
        fontSize=10,
        leading=13,
        leftIndent=20,
        spaceBefore=4,
        spaceAfter=8,
        textColor=HexColor("#000000"),
    )

    story = []

    # Title
    story.append(Paragraph("Harmonic Oscillations in Coupled Pendulums", title_style))
    story.append(Paragraph("PenPress Benchmark Series &bull; Assignment 1", body_style))
    story.append(HRFlowable(width="100%", thickness=1, color=HexColor("#d1d5db"), spaceAfter=14))

    # Section 1
    story.append(Paragraph("1. Theoretical Foundation", h1_style))
    p1_text = (
        "Consider two identical pendulums of mass m and length l suspended from a rigid horizontal beam. "
        "The pendulums are coupled by a linear spring of spring constant k attached at distance d "
        "below the pivot points. In the small-angle approximation, the equations of motion decouple into "
        "symmetric and antisymmetric normal modes."
    )
    story.append(Paragraph(p1_text, body_style))

    # Equation 1
    eq1_latex = r"\ddot{\theta}_1 + \omega_0^2 \theta_1 + \kappa (\theta_1 - \theta_2) = 0"
    story.append(Paragraph(f"<b>Equation 1:</b> $${eq1_latex}$$", code_style))

    eq2_latex = r"\ddot{\theta}_2 + \omega_0^2 \theta_2 - \kappa (\theta_1 - \theta_2) = 0"
    story.append(Paragraph(f"<b>Equation 2:</b> $${eq2_latex}$$", code_style))

    # Section 2
    story.append(Paragraph("2. Normal Mode Frequencies", h1_style))
    p2_text = (
        "By taking the sum and difference of the coordinates, we define the in-phase coordinate "
        "eta = theta_1 + theta_2 and the out-of-phase coordinate zeta = theta_1 - theta_2. "
        "The eigenfrequencies of the normal modes are given by:"
    )
    story.append(Paragraph(p2_text, body_style))

    eq3_latex = r"\omega_1 = \sqrt{\frac{g}{l}}, \quad \omega_2 = \sqrt{\frac{g}{l} + \frac{2kd^2}{ml^2}}"
    story.append(Paragraph(f"<b>Equation 3:</b> $${eq3_latex}$$", code_style))

    # Section 3: List
    story.append(Paragraph("3. Experimental Procedure", h1_style))
    list_items = [
        "1. Displace both pendulums by identical angle theta_0 = 5 deg in same direction and record T_1.",
        "2. Displace both pendulums by opposite angles theta_1 = -theta_2 = 5 deg and record period T_2.",
        "3. Release pendulum 1 from theta_0 with pendulum 2 at rest, measuring beat frequency omega_b.",
    ]
    for item in list_items:
        story.append(Paragraph(item, body_style))

    doc.build(story)

    return {
        "doc_id": "single_column_academic",
        "file": str(out_path.name),
        "expected_blocks": 9,
        "expected_equations": [
            eq1_latex,
            eq2_latex,
            eq3_latex,
        ],
        "has_columns": False,
        "is_scan": False,
    }


def generate_two_column_article(out_path: Path) -> dict:
    # Use direct canvas drawing for an accurate 2-column layout with vector figure and math
    c = canvas.Canvas(str(out_path), pagesize=letter)
    width, height = letter

    # Title Banner (Full width)
    c.setFont("Helvetica-Bold", 18)
    c.drawString(54, height - 60, "Microfluidic Transport in Porous Media")
    c.setFont("Helvetica", 10)
    c.setFillColor(HexColor("#4b5563"))
    c.drawString(54, height - 76, "Department of Mechanical Engineering • Fluid Dynamics Review")
    c.setStrokeColor(HexColor("#d1d5db"))
    c.setLineWidth(1)
    c.line(54, height - 86, width - 54, height - 86)

    # Column 1 (Left: x=54 to x=280)
    col1_x = 54
    y = height - 110
    c.setFillColor(black)
    c.setFont("Helvetica-Bold", 12)
    c.drawString(col1_x, y, "1. Darcy Flow Regime")
    y -= 16

    c.setFont("Helvetica", 9)
    lines_col1 = [
        "Flow through a packed porous bed satisfies Darcy's law",
        "when the Reynolds number based on mean grain diameter",
        "remains well below unity (Re < 1). The macroscopic superficial",
        "velocity vector q depends on hydraulic permeability kappa",
        "and dynamic fluid viscosity mu:",
    ]
    for line in lines_col1:
        c.drawString(col1_x, y, line)
        y -= 13

    y -= 6
    # Equation in Col 1
    c.setFont("Courier-Bold", 9)
    eq_darcy = r"\vec{q} = -\frac{\kappa}{\mu} \nabla p"
    c.drawString(col1_x + 20, y, f"$$ {eq_darcy} $$")
    y -= 20

    c.setFont("Helvetica", 9)
    lines_col1_b = [
        "In the presence of gravitational acceleration g along the vertical",
        "axis, the pressure gradient is augmented by hydrostatic head:",
    ]
    for line in lines_col1_b:
        c.drawString(col1_x, y, line)
        y -= 13

    y -= 6
    eq_gravity = r"\vec{q} = -\frac{\kappa}{\mu} (\nabla p - \rho \vec{g})"
    c.setFont("Courier-Bold", 9)
    c.drawString(col1_x + 10, y, f"$$ {eq_gravity} $$")
    y -= 22

    # Column 2 (Right: x=330 to width-54)
    col2_x = 330
    y2 = height - 110
    c.setFont("Helvetica-Bold", 12)
    c.setFillColor(black)
    c.drawString(col2_x, y2, "2. Permeability Characterization")
    y2 -= 16

    c.setFont("Helvetica", 9)
    lines_col2 = [
        "The Kozeny-Carman empirical equation estimates permeability",
        "from bed porosity phi and specific surface area per unit volume S_v:",
    ]
    for line in lines_col2:
        c.drawString(col2_x, y2, line)
        y2 -= 13

    y2 -= 6
    eq_kozeny = r"\kappa = \frac{\phi^3}{c_0 S_v^2 (1 - \phi)^2}"
    c.setFont("Courier-Bold", 9)
    c.drawString(col2_x + 10, y2, f"$$ {eq_kozeny} $$")
    y2 -= 24

    # Vector diagram in column 2
    c.setStrokeColor(HexColor("#1e293b"))
    c.setLineWidth(1.5)
    # Box for diagram
    c.rect(col2_x, y2 - 70, 220, 65, fill=0)
    # Pore channel vectors
    c.line(col2_x + 20, y2 - 40, col2_x + 80, y2 - 40)
    c.line(col2_x + 80, y2 - 40, col2_x + 120, y2 - 20)
    c.line(col2_x + 120, y2 - 20, col2_x + 180, y2 - 20)
    c.circle(col2_x + 60, y2 - 25, 8, stroke=1, fill=0)
    c.circle(col2_x + 140, y2 - 45, 12, stroke=1, fill=0)
    c.setFont("Helvetica-Oblique", 8)
    c.drawString(col2_x + 25, y2 - 80, "Figure 1: Tortuous pore network model.")

    c.showPage()
    c.save()

    return {
        "doc_id": "two_column_article",
        "file": str(out_path.name),
        "expected_columns": 2,
        "expected_equations": [eq_darcy, eq_gravity, eq_kozeny],
        "has_vector_figure": True,
        "is_scan": False,
    }


def generate_mixed_math_assignment(out_path: Path) -> dict:
    doc = SimpleDocTemplate(
        str(out_path),
        pagesize=letter,
        leftMargin=54,
        rightMargin=54,
        topMargin=54,
        bottomMargin=54,
    )
    styles = getSampleStyleSheet()

    story = []
    story.append(Paragraph("Calculus III: Multivariable Integration & Stokes' Theorem", styles["Title"]))
    story.append(Spacer(1, 10))

    story.append(Paragraph("Problem 1: Flux through a Paraboloid", styles["Heading2"]))
    story.append(
        Paragraph(
            "Compute the outward flux of the vector field F through the surface S bounded by the paraboloid.",
            styles["Normal"],
        )
    )

    eq1 = r"\iint_S \mathbf{F} \cdot d\mathbf{S} = \iiint_V (\nabla \cdot \mathbf{F}) \, dV"
    story.append(Spacer(1, 4))
    story.append(Paragraph(f"<b>Gauss Divergence Theorem:</b> $${eq1}$$", styles["Code"]))
    story.append(Spacer(1, 8))

    story.append(Paragraph("Problem 2: Circulation along Closed Path", styles["Heading2"]))
    eq2 = r"\oint_C \mathbf{F} \cdot d\mathbf{r} = \iint_S (\nabla \times \mathbf{F}) \cdot d\mathbf{S}"
    story.append(Paragraph(f"<b>Stokes' Theorem:</b> $${eq2}$$", styles["Code"]))
    story.append(Spacer(1, 8))

    # Table of vector field coordinates
    story.append(Paragraph("Table 1: Test Vector Fields and Boundary Curves", styles["Heading3"]))
    table_data = [
        ["Field Index", "Vector Field F(x, y, z)", "Boundary Condition", "Domain"],
        ["Field A", "F = (y, -x, z^2)", "C: x^2 + y^2 = 1, z = 0", "Unit disk in xy-plane"],
        ["Field B", "F = (2z, 3x, 5y)", "S: x^2 + y^2 + z^2 = 4, z >= 0", "Upper hemisphere"],
        ["Field C", "F = (e^y, e^z, e^x)", "Tetrahedron at origin", "x+y+z <= 1, x,y,z >= 0"],
    ]
    t = Table(table_data, colWidths=[80, 160, 150, 114])
    t.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), HexColor("#f3f4f6")),
                ("TEXTCOLOR", (0, 0), (-1, -1), HexColor("#1f2937")),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ("GRID", (0, 0), (-1, -1), 0.5, HexColor("#d1d5db")),
            ]
        )
    )
    story.append(t)

    doc.build(story)

    return {
        "doc_id": "mixed_math_assignment",
        "file": str(out_path.name),
        "expected_equations": [eq1, eq2],
        "has_table": True,
        "is_scan": False,
    }


def generate_vector_figure_circuit(out_path: Path) -> dict:
    c = canvas.Canvas(str(out_path), pagesize=letter)
    _width, height = letter

    c.setFont("Helvetica-Bold", 16)
    c.drawString(54, height - 54, "RLC Resonant Circuit Schematic")

    c.setFont("Helvetica", 10)
    c.drawString(54, height - 72, "Vector stroke preservation benchmark for electronic schematic extraction.")

    # Circuit schematic drawn in vector primitives
    ox, oy = 100, height - 300
    c.setLineWidth(2.0)
    c.setStrokeColor(HexColor("#111827"))

    # Outer loop rectangle wire
    c.rect(ox, oy, 400, 180, fill=0)

    # AC Source on left wire: circle + sine wave
    src_x, src_y = ox, oy + 90
    c.setFillColor(HexColor("#ffffff"))
    c.circle(src_x, src_y, 16, stroke=1, fill=1)
    # Sine wave symbol inside AC source
    c.setLineWidth(1.5)
    c.line(src_x - 8, src_y, src_x - 4, src_y + 6)
    c.line(src_x - 4, src_y + 6, src_x + 4, src_y - 6)
    c.line(src_x + 4, src_y - 6, src_x + 8, src_y)

    # Resistor on top wire: zig-zag
    rx = ox + 100
    ry = oy + 180
    c.setFillColor(HexColor("#ffffff"))
    c.rect(rx, ry - 6, 60, 12, stroke=1, fill=1)
    c.setFont("Helvetica-Bold", 10)
    c.setFillColor(black)
    c.drawString(rx + 15, ry + 10, "R = 50 Ohm")

    # Inductor on top wire: semicircles
    lx = ox + 220
    ly = oy + 180
    c.arc(lx, ly - 8, lx + 20, ly + 8, 0, 180)
    c.arc(lx + 15, ly - 8, lx + 35, ly + 8, 0, 180)
    c.arc(lx + 30, ly - 8, lx + 50, ly + 8, 0, 180)
    c.drawString(lx + 10, ly + 12, "L = 2.5 mH")

    # Capacitor on top wire: parallel plates
    cx = ox + 320
    cy = oy + 180
    c.setFillColor(HexColor("#ffffff"))
    c.rect(cx - 5, cy - 15, 30, 30, stroke=0, fill=1)
    c.line(cx, cy - 12, cx, cy + 12)
    c.line(cx + 8, cy - 12, cx + 8, cy + 12)
    c.line(cx - 10, cy, cx, cy)
    c.line(cx + 8, cy, cx + 18, cy)
    c.drawString(cx - 4, cy + 16, "C = 100 nF")

    # Caption
    c.setFont("Helvetica-Oblique", 9)
    c.drawString(ox, oy - 25, "Figure 2: Series RLC resonant filter circuit topology.")

    c.showPage()
    c.save()

    return {
        "doc_id": "vector_figure_circuit",
        "file": str(out_path.name),
        "has_vector_figure": True,
        "is_scan": False,
    }


def generate_scanned_page_noisy(out_path: Path, clean_pdf_path: Path) -> dict:
    """Renders the clean academic PDF to image, adds skew, speckle noise, and saves as raster scanned PDF."""
    pdf = pdfium.PdfDocument(str(clean_pdf_path))
    page = pdf[0]
    bitmap = page.render(scale=2.0)
    pil_image = bitmap.to_pil()

    # Apply slight rotation/skew (0.8 degrees)
    rotated = pil_image.rotate(0.8, resample=Image.Resampling.BICUBIC, expand=False, fillcolor="white")

    # Add Gaussian noise / speckle
    arr = np.array(rotated).astype(np.float32)
    noise = np.random.normal(0, 12, arr.shape)
    noisy_arr = np.clip(arr + noise, 0, 255).astype(np.uint8)
    noisy_img = Image.fromarray(noisy_arr)

    # Save as scanned PDF
    noisy_img.save(str(out_path), "PDF", resolution=150.0)

    return {
        "doc_id": "scanned_page_noisy",
        "file": str(out_path.name),
        "is_scan": True,
    }


def generate_hostile_pdfs(fixture_dir: Path) -> list[dict]:
    results = []

    # 1. Oversized page (5000 x 5000 pt)
    over_path = fixture_dir / "hostile_oversized.pdf"
    c_over = canvas.Canvas(str(over_path), pagesize=(5000, 5000))
    c_over.setFont("Helvetica", 48)
    c_over.drawString(500, 4500, "Oversized Architectural Blueprint (Extreme Dimensions)")
    c_over.rect(100, 100, 4800, 4800)
    c_over.showPage()
    c_over.save()
    results.append({"doc_id": "hostile_oversized", "file": str(over_path.name), "is_hostile": True})

    # 2. Huge embedded image (3000 x 3000 px)
    huge_img_pdf = fixture_dir / "hostile_huge_image.pdf"
    img_temp = fixture_dir / "temp_huge.png"
    big_img = Image.new("RGB", (3000, 3000), color=(240, 240, 240))
    d = ImageDraw.Draw(big_img)
    d.line([(0, 0), (3000, 3000)], fill=(20, 20, 20), width=10)
    big_img.save(str(img_temp), "PNG")

    c_img = canvas.Canvas(str(huge_img_pdf), pagesize=letter)
    c_img.drawImage(str(img_temp), 54, 54, width=500, height=500)
    c_img.showPage()
    c_img.save()
    if img_temp.exists():
        img_temp.unlink()
    results.append({"doc_id": "hostile_huge_image", "file": str(huge_img_pdf.name), "is_hostile": True})

    # 3. Corrupted / Malformed PDF byte stream
    malformed_pdf = fixture_dir / "hostile_malformed.pdf"
    corrupt_bytes = (
        b"%PDF-1.4\n%Malformed binary payload without valid xref table\n"
        b"<< /Type /Catalog /Pages 2 0 R >>\n%%EOF"
    )
    with malformed_pdf.open("wb") as f:
        f.write(corrupt_bytes)
    results.append({"doc_id": "hostile_malformed", "file": str(malformed_pdf.name), "is_hostile": True})

    return results


def generate_all_fixtures(output_dir: Path) -> dict:
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest = {}

    p1 = output_dir / "single_column_academic.pdf"
    manifest["single_column_academic"] = generate_single_column_academic(p1)

    p2 = output_dir / "two_column_article.pdf"
    manifest["two_column_article"] = generate_two_column_article(p2)

    p3 = output_dir / "mixed_math_assignment.pdf"
    manifest["mixed_math_assignment"] = generate_mixed_math_assignment(p3)

    p4 = output_dir / "vector_figure_circuit.pdf"
    manifest["vector_figure_circuit"] = generate_vector_figure_circuit(p4)

    p5 = output_dir / "scanned_page_noisy.pdf"
    manifest["scanned_page_noisy"] = generate_scanned_page_noisy(p5, p1)

    hostiles = generate_hostile_pdfs(output_dir)
    for h in hostiles:
        manifest[h["doc_id"]] = h

    manifest_file = output_dir / "manifest.json"
    manifest_file.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


if __name__ == "__main__":
    out = Path("research/R4-1/fixtures")
    gen_manifest = generate_all_fixtures(out)
    print(f"Generated {len(gen_manifest)} fixtures in {out}")
