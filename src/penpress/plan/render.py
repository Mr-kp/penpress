"""End-to-end rendering pipeline: text to Hershey strokes to Marlin G-code to simulator image."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TextIO

from penpress.core.hershey import HersheyFont
from penpress.core.primitives import CoreGeometryError, Page
from penpress.core.primitives import Path as CorePath
from penpress.plan.compiler import GcodeCompiler
from penpress.plan.profile import MachineProfile
from penpress.plan.sim import MarlinSimulator


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
