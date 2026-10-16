"""End-to-end rendering pipeline: text to Hershey strokes to Marlin G-code to simulator image."""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import TextIO

from penpress.core.hershey import HersheyFont
from penpress.core.math_engine import MathEngine
from penpress.core.primitives import CoreGeometryError, Page
from penpress.core.primitives import Path as CorePath
from penpress.ingest.engine import DocumentIngestEngine
from penpress.layout.composer import A4_PRESET, A5_PRESET, PageComposer
from penpress.plan.compiler import GcodeCompiler
from penpress.plan.optimizer import ToolpathOptimizer
from penpress.plan.profile import MachineProfile
from penpress.plan.sim import MarlinSimulator
from penpress.synth.humanizer import OrganicHumanizer


class LayoutOverflowError(CoreGeometryError):
    """Raised when text exceeds the printable page area."""


@dataclass(frozen=True, slots=True)
class RenderResult:
    """Telemetry and output data resulting from an end-to-end text render.

    Attributes:
        page_count: Number of pages generated.
        total_strokes: Total number of discrete continuous pen strokes.
        total_pen_lifts: Number of times pen was lifted up.
        estimated_duration_s: Estimated execution time in seconds.
        gcode_path: Path to the generated G-code output file.
        sim_image_path: Path to the rendered simulator PNG image.
        sim_svg_path: Path to the rendered simulator SVG file.
    """

    page_count: int
    total_strokes: int
    total_pen_lifts: int
    estimated_duration_s: float
    gcode_path: Path
    sim_image_path: Path
    sim_svg_path: Path


class TextRenderer:
    """Renders formatted text onto vector pages, compiles G-code, and simulates execution."""

    def __init__(
        self,
        profile: MachineProfile,
        font: HersheyFont | None = None,
        font_size_mm: float = 3.5,
        line_height_mm: float = 8.5,
        margin_x_mm: float = 25.0,
        margin_top_mm: float = 40.0,
        margin_bottom_mm: float = 20.0,
        letter_spacing_mm: float = 0.2,
        paginate: bool = False,
    ) -> None:
        self.profile = profile
        self.font = font or HersheyFont.load_default()
        self.font_size_mm = font_size_mm
        self.line_height_mm = line_height_mm
        self.margin_x_mm = margin_x_mm
        self.margin_top_mm = margin_top_mm
        self.margin_bottom_mm = margin_bottom_mm
        self.letter_spacing_mm = letter_spacing_mm
        self.paginate = paginate

    def _measure_text_width_mm(self, text: str) -> float:
        """Measure the horizontal length of a text string in mm."""
        scale = self.font_size_mm / 21.0
        width = 0.0
        for ch in text:
            glyph = self.font.get_glyph(ch)
            width += glyph.advance_width_units * scale + self.letter_spacing_mm
        return width

    def _wrap_text_into_lines(self, text: str, max_width_mm: float) -> list[str]:
        """Wrap paragraph text into lines fitting within max_width_mm."""
        paragraphs = text.splitlines()
        result_lines: list[str] = []

        for p in paragraphs:
            clean_p = p.strip()
            if not clean_p:
                result_lines.append("")
                continue

            words = clean_p.split()
            current_line: list[str] = []
            for word in words:
                candidate = " ".join([*current_line, word])
                if self._measure_text_width_mm(candidate) <= max_width_mm:
                    current_line.append(word)
                else:
                    if current_line:
                        result_lines.append(" ".join(current_line))
                    current_line = [word]
            if current_line:
                result_lines.append(" ".join(current_line))

        return result_lines

    def layout_text(
        self,
        text: str,
        page_width_mm: float | None = None,
        page_height_mm: float | None = None,
    ) -> list[Page]:
        """Layout wrapped lines across one or more pages.

        Raises LayoutOverflowError if text exceeds single page and paginate is False.
        """
        p_width = page_width_mm if page_width_mm is not None else self.profile.bed_width_mm
        p_height = page_height_mm if page_height_mm is not None else self.profile.bed_height_mm

        # Calculate printable box
        usable_width = p_width - (2.0 * self.margin_x_mm)
        if usable_width <= 0.0:
            raise LayoutOverflowError(
                f"Page width {p_width} mm too narrow for horizontal margin {self.margin_x_mm} mm"
            )

        lines = self._wrap_text_into_lines(text, usable_width)

        # Baseline Y starts near the top and decreases towards bottom
        start_y = p_height - self.margin_top_mm
        min_allowed_y = self.margin_bottom_mm

        pages: list[Page] = []
        current_page_paths: list[CorePath] = []
        curr_y = start_y

        for line_str in lines:
            if curr_y < min_allowed_y:
                if not self.paginate:
                    msg = (
                        f"Text exceeded single page boundary (reached Y={curr_y:.1f} mm < "
                        f"{min_allowed_y:.1f} mm). Enable paginate=True to flow into multi-page document."
                    )
                    raise LayoutOverflowError(msg)
                # Paginate into next page
                pages.append(Page(width_mm=p_width, height_mm=p_height, paths=current_page_paths))
                current_page_paths = []
                curr_y = start_y

            if line_str:
                line_paths = self.font.layout_line(
                    line_str,
                    start_x_mm=self.margin_x_mm,
                    baseline_y_mm=curr_y,
                    font_size_mm=self.font_size_mm,
                    letter_spacing_mm=self.letter_spacing_mm,
                )
                current_page_paths.extend(line_paths)

            curr_y -= self.line_height_mm

        if current_page_paths or not pages:
            pages.append(Page(width_mm=p_width, height_mm=p_height, paths=current_page_paths))

        return pages

    def render_to_dir(
        self,
        text: str,
        output_dir: Path | str,
        base_name: str = "output",
        page_width_mm: float | None = None,
        page_height_mm: float | None = None,
        ocr_mode: bool = False,
    ) -> RenderResult:
        """Execute end-to-end pipeline: text -> Page -> G-code -> Simulation -> Render."""
        out_path = Path(output_dir)
        out_path.mkdir(parents=True, exist_ok=True)

        pages = self.layout_text(text, page_width_mm=page_width_mm, page_height_mm=page_height_mm)
        first_page = pages[0]

        compiler = GcodeCompiler(self.profile)
        gcode_content = compiler.compile(first_page)

        gcode_file = out_path / f"{base_name}.gcode"
        gcode_file.write_text(gcode_content, encoding="utf-8")

        sim = MarlinSimulator(self.profile, strict_safety=True)
        sim.execute_stream(gcode_content)

        png_file = out_path / f"{base_name}.png"
        svg_file = out_path / f"{base_name}.svg"

        if ocr_mode:
            # White background, dark black text, hide rapid travel lines for OCR
            img = sim.render_to_image(
                width_px=1880,
                height_px=1880,
                bg_color=(255, 255, 255),
                bed_border_color=(255, 255, 255),
                travel_color=(255, 255, 255),
                draw_color=(0, 0, 0),
            )
            img.save(png_file)
        else:
            sim.save_image(png_file)

        svg_text = sim.render_to_svg()
        svg_file.write_text(svg_text, encoding="utf-8")

        # Calculate stroke metrics
        all_strokes = [s for p in first_page.paths for s in p.strokes]
        total_lifts = len(all_strokes)

        return RenderResult(
            page_count=len(pages),
            total_strokes=len(all_strokes),
            total_pen_lifts=total_lifts,
            estimated_duration_s=sim.state.total_time_seconds,
            gcode_path=gcode_file,
            sim_image_path=png_file,
            sim_svg_path=svg_file,
        )


def execute_render_pipeline(
    text_file: Path | str,
    output_dir: Path | str,
    profile_path: Path | str | None = None,
    profile_name: str = "ender3pro",
    font_size_mm: float = 3.5,
    line_height_mm: float = 8.5,
    paginate: bool = False,
    ocr_mode: bool = False,
    out_stream: TextIO | None = None,
) -> RenderResult:
    """Entry point for CLI render-text command."""
    in_file = Path(text_file)
    if not in_file.exists():
        raise FileNotFoundError(f"Input file not found: {in_file}")

    content = in_file.read_text(encoding="utf-8")

    # Load machine profile
    if profile_path is not None:
        profile = MachineProfile.from_toml_file(profile_path)
    else:
        # Search in known machine profiles location
        standard_path = Path("machine-profiles") / f"{profile_name}.toml"
        profile = MachineProfile.from_toml_file(standard_path) if standard_path.exists() else MachineProfile()

    renderer = TextRenderer(
        profile=profile,
        font_size_mm=font_size_mm,
        line_height_mm=line_height_mm,
        paginate=paginate,
    )

    base = in_file.stem
    result = renderer.render_to_dir(
        text=content,
        output_dir=output_dir,
        base_name=base,
        ocr_mode=ocr_mode,
    )

    if out_stream is not None:
        out_stream.write(f"Rendered {in_file.name} to {output_dir}\n")
        out_stream.write(f"Pages: {result.page_count}\n")
        out_stream.write(f"Strokes: {result.total_strokes}\n")
        out_stream.write(f"Total Pen Lifts: {result.total_pen_lifts}\n")
        out_stream.write(f"Estimated Time: {result.estimated_duration_s:.1f}s\n")
        out_stream.write(f"G-code: {result.gcode_path}\n")
        out_stream.write(f"Simulator Image: {result.sim_image_path}\n")
        out_stream.write(f"Simulator SVG: {result.sim_svg_path}\n")

    return result


@dataclass(frozen=True, slots=True)
class DocumentPageArtifacts:
    """Artifact paths and kinematics telemetry for an individual rendered page."""

    page_num: int
    gcode_path: Path
    sim_image_path: Path
    sim_svg_path: Path
    stroke_count: int
    draw_distance_mm: float
    travel_distance_mm: float
    duration_s: float


@dataclass(frozen=True, slots=True)
class DocumentRenderResult:
    """Complete summary and page artifacts for an end-to-end document render."""

    input_file: Path
    paper: str
    page_count: int
    total_strokes: int
    total_pen_lifts: int
    total_draw_distance_mm: float
    total_travel_distance_mm: float
    estimated_duration_s: float
    artifacts: tuple[DocumentPageArtifacts, ...]
    summary_json_path: Path


def execute_document_pipeline(
    file_path: Path | str,
    output_dir: Path | str,
    paper: str = "A5",
    profile_path: Path | str | None = None,
    profile_name: str = "ender3pro",
    optimize: bool = True,
    humanizer: OrganicHumanizer | None = None,
    out_stream: TextIO | None = None,
) -> DocumentRenderResult:
    """Execute full production rendering pipeline for PDF, Markdown, or text assignments.

    Runs: DocumentIngestEngine -> PageComposer -> ToolpathOptimizer -> GcodeCompiler -> MarlinSimulator.
    """
    in_file = Path(file_path)
    if not in_file.exists():
        raise FileNotFoundError(f"Input file not found: {in_file}")

    valid_exts = {".pdf", ".md", ".markdown", ".txt"}
    if in_file.suffix.lower() not in valid_exts:
        raise ValueError(
            f"Unsupported document format: {in_file.suffix}. Expected one of {sorted(valid_exts)}"
        )

    # 1. Ingest
    ingest_engine = DocumentIngestEngine()
    if in_file.suffix.lower() == ".txt":
        text_content = in_file.read_text(encoding="utf-8")
        doc = ingest_engine.md_parser.parse_markdown(text_content, doc_id=in_file.stem)
    else:
        doc = ingest_engine.ingest_document(in_file)

    # 2. Page Composition
    paper_preset = A5_PRESET if paper.strip().upper() == "A5" else A4_PRESET
    math_engine = MathEngine()
    composer = PageComposer(
        paper=paper_preset,
        humanizer=humanizer,
        math_engine=math_engine,
        autoscale_figures=True,
    )
    layout_res = composer.compose_document(doc)
    pages = list(layout_res.pages)
    if not pages:
        pages = [Page(width_mm=paper_preset.width_mm, height_mm=paper_preset.height_mm, paths=())]

    # 3. Path Optimization
    if optimize:
        optimizer = ToolpathOptimizer()
        pages = [optimizer.optimize_page(p)[0] for p in pages]

    # 4. Load Machine Profile
    if profile_path is not None:
        profile = MachineProfile.from_toml_file(profile_path)
    else:
        standard_path = Path("machine-profiles") / f"{profile_name}.toml"
        profile = MachineProfile.from_toml_file(standard_path) if standard_path.exists() else MachineProfile()

    # 5. Compile and Simulate
    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    compiler = GcodeCompiler(profile=profile, emit_line_numbers=True)

    artifacts_list: list[DocumentPageArtifacts] = []
    total_strokes = 0
    total_lifts = 0
    total_draw = 0.0
    total_travel = 0.0
    total_duration = 0.0

    for idx, page in enumerate(pages):
        page_num = idx + 1
        page_suffix = f"_p{page_num}" if len(pages) > 1 else ""
        base = f"{in_file.stem}{page_suffix}"
        gcode_file = out_path / f"{base}.gcode"
        png_file = out_path / f"{base}.png"
        svg_file = out_path / f"{base}.svg"

        gcode_str = compiler.compile(page)
        gcode_file.write_text(gcode_str, encoding="utf-8")

        sim = MarlinSimulator(profile=profile, strict_safety=True)
        gcode_commands = [line.strip() for line in gcode_str.splitlines() if line.strip()]
        sim.execute_stream(gcode_commands)

        sim.save_image(png_file)
        svg_str = sim.render_to_svg()
        svg_file.write_text(svg_str, encoding="utf-8")

        page_strokes = sum(len(p.strokes) for p in page.paths)
        page_draw = sum(s.length_mm for p in page.paths for s in p.strokes)
        page_travel = sum(
            math.hypot(s.end_x - s.start_x, s.end_y - s.start_y) for s in sim.segments if not s.pen_contact
        )
        page_time = sim.state.total_time_seconds

        total_strokes += page_strokes
        total_lifts += page_strokes
        total_draw += page_draw
        total_travel += page_travel
        total_duration += page_time

        artifacts_list.append(
            DocumentPageArtifacts(
                page_num=page_num,
                gcode_path=gcode_file,
                sim_image_path=png_file,
                sim_svg_path=svg_file,
                stroke_count=page_strokes,
                draw_distance_mm=round(page_draw, 2),
                travel_distance_mm=round(page_travel, 2),
                duration_s=round(page_time, 2),
            )
        )

    summary_file = out_path / f"{in_file.stem}_summary.json"
    summary_dict = {
        "input_file": str(in_file),
        "paper": paper,
        "page_count": len(pages),
        "total_strokes": total_strokes,
        "total_pen_lifts": total_lifts,
        "total_draw_distance_mm": round(total_draw, 2),
        "total_travel_distance_mm": round(total_travel, 2),
        "estimated_duration_s": round(total_duration, 2),
        "artifacts": [
            {
                "page_num": art.page_num,
                "gcode": str(art.gcode_path),
                "png": str(art.sim_image_path),
                "svg": str(art.sim_svg_path),
                "stroke_count": art.stroke_count,
                "duration_s": art.duration_s,
            }
            for art in artifacts_list
        ],
    }
    summary_file.write_text(json.dumps(summary_dict, indent=2), encoding="utf-8")

    result = DocumentRenderResult(
        input_file=in_file,
        paper=paper,
        page_count=len(pages),
        total_strokes=total_strokes,
        total_pen_lifts=total_lifts,
        total_draw_distance_mm=round(total_draw, 2),
        total_travel_distance_mm=round(total_travel, 2),
        estimated_duration_s=round(total_duration, 2),
        artifacts=tuple(artifacts_list),
        summary_json_path=summary_file,
    )

    if out_stream is not None:
        out_stream.write(f"Rendered {in_file.name} ({paper}) to {output_dir}\n")
        out_stream.write(f"Pages: {result.page_count}\n")
        out_stream.write(f"Strokes: {result.total_strokes}\n")
        out_stream.write(f"Total Pen Lifts: {result.total_pen_lifts}\n")
        out_stream.write(f"Draw Distance: {result.total_draw_distance_mm:.1f} mm\n")
        out_stream.write(f"Travel Distance: {result.total_travel_distance_mm:.1f} mm\n")
        out_stream.write(f"Estimated Duration: {result.estimated_duration_s:.1f}s\n")
        out_stream.write(f"Summary JSON: {result.summary_json_path}\n")
        for art in result.artifacts:
            out_stream.write(
                f"  Page {art.page_num}: {art.gcode_path.name}, "
                f"{art.sim_image_path.name}, {art.sim_svg_path.name}\n"
            )

    return result
