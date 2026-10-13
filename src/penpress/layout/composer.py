"""Page composer and layout typesetter for ruled and blank stationery (P5-2).

Fits structured assignment blocks onto physical paper sizes (A5 single-pass per ADR-0005,
A4 indexed/multi-pass). Manages line wraps, paragraph justification, section indentation,
margin constraints, ruled line alignment (grid/lined paper), and obstacle keep-out buffer clipping.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass, field

from penpress.core.math_engine import MathEngine
from penpress.core.primitives import Page, Point, Stroke
from penpress.core.primitives import Path as CorePath
from penpress.ingest.schema import BlockType, DocumentBlock, IngestedDocument
from penpress.layout.keepout import KeepoutPolygon, create_standard_a5_clip_keepouts
from penpress.synth.humanizer import HumanizerParams, OrganicHumanizer

# Physical limits
MAX_BED_TRAVEL_X_MM = 220.0
MAX_BED_TRAVEL_Y_MM = 220.0


class LayoutOverflowError(ValueError):
    """Raised when an indivisible content block exceeds page printable bounds."""


@dataclass(frozen=True, slots=True)
class PaperPreset:
    name: str
    width_mm: float
    height_mm: float


A5_PRESET = PaperPreset(name="A5", width_mm=148.0, height_mm=210.0)
A4_PRESET = PaperPreset(name="A4", width_mm=210.0, height_mm=297.0)


@dataclass(frozen=True, slots=True)
class Margins:
    top_mm: float = 18.0
    bottom_mm: float = 18.0
    left_mm: float = 16.0
    right_mm: float = 16.0


@dataclass(frozen=True, slots=True)
class RuledGridConfig:
    enabled: bool = True
    line_spacing_mm: float = 7.0  # standard 7 mm or 8 mm college ruled
    first_baseline_y_mm: float | None = None
    snap_tolerance_mm: float = 0.2


@dataclass
class ComposerResult:
    pages: list[Page] = field(default_factory=list)
    page_count: int = 0
    total_stroke_count: int = 0
    total_length_mm: float = 0.0
    baseline_y_positions: list[float] = field(default_factory=list)


class PageComposer:
    def __init__(
        self,
        paper: PaperPreset = A5_PRESET,
        margins: Margins | None = None,
        ruled_grid: RuledGridConfig | None = None,
        humanizer: OrganicHumanizer | None = None,
        math_engine: MathEngine | None = None,
        keepouts: Sequence[KeepoutPolygon] | None = None,
    ) -> None:
        self.paper = paper
        self.margins = margins if margins is not None else Margins()
        self.ruled_grid = ruled_grid if ruled_grid is not None else RuledGridConfig()
        self.humanizer = humanizer or OrganicHumanizer(params=HumanizerParams.zero_jitter())
        self.math_engine = math_engine or MathEngine()

        if keepouts is not None:
            self.keepouts = list(keepouts)
        elif paper.name == "A5":
            self.keepouts = create_standard_a5_clip_keepouts(paper.width_mm, paper.height_mm)
        else:
            self.keepouts = []

        # Validate physical limits
        if (
            self.paper.width_mm > MAX_BED_TRAVEL_X_MM or self.paper.height_mm > MAX_BED_TRAVEL_Y_MM
        ) and self.paper.name != "A4":
            raise ValueError(
                f"Paper size {self.paper.width_mm}x{self.paper.height_mm} mm exceeds "
                f"Ender 3 physical bed travel limits ({MAX_BED_TRAVEL_X_MM}x{MAX_BED_TRAVEL_Y_MM} mm)"
            )

        # Usable writing area
        self.usable_min_x = self.margins.left_mm
        self.usable_max_x = self.paper.width_mm - self.margins.right_mm
        self.usable_width = self.usable_max_x - self.usable_min_x

        self.usable_min_y = self.margins.bottom_mm
        self.usable_max_y = self.paper.height_mm - self.margins.top_mm
        self.usable_height = self.usable_max_y - self.usable_min_y

    def calculate_ruled_baselines(self) -> list[float]:
        """Calculates exact notebook ruled guide line Y positions descending from top."""
        if not self.ruled_grid.enabled:
            return []

        spacing = self.ruled_grid.line_spacing_mm
        first_y = (
            self.ruled_grid.first_baseline_y_mm
            if self.ruled_grid.first_baseline_y_mm is not None
            else self.usable_max_y - spacing
        )

        baselines: list[float] = []
        curr_y = first_y
        while curr_y >= self.usable_min_y:
            baselines.append(curr_y)
            curr_y -= spacing
        return baselines

    def snap_to_ruled_baseline(self, target_y: float, baselines: Sequence[float]) -> float:
        """Snaps target Y to the closest ruled baseline if within snap_tolerance_mm."""
        if not baselines or not self.ruled_grid.enabled:
            return target_y

        closest = min(baselines, key=lambda b: abs(b - target_y))
        if abs(closest - target_y) <= self.ruled_grid.snap_tolerance_mm:
            return closest
        return target_y

    def compose_document(self, doc: IngestedDocument) -> ComposerResult:
        """Typesets and paginates structured blocks from an IngestedDocument across sheets."""
        all_blocks: list[DocumentBlock] = []
        for p in doc.pages:
            all_blocks.extend(p.blocks)

        pages: list[Page] = []
        current_page_paths: list[CorePath] = []
        recorded_baselines: list[float] = []

        ruled_baselines = self.calculate_ruled_baselines()
        spacing = self.ruled_grid.line_spacing_mm if self.ruled_grid.enabled else 7.0
        line_height = spacing

        current_baseline_idx = 0

        def current_y() -> float:
            if ruled_baselines and current_baseline_idx < len(ruled_baselines):
                return ruled_baselines[current_baseline_idx]
            return self.usable_max_y - (current_baseline_idx + 1) * line_height

        def flush_page() -> None:
            nonlocal current_page_paths, current_baseline_idx
            if current_page_paths:
                p = Page(
                    width_mm=self.paper.width_mm,
                    height_mm=self.paper.height_mm,
                    paths=current_page_paths,
                )
                pages.append(p)
                current_page_paths = []
            current_baseline_idx = 0

        for block in all_blocks:
            # Check for oversized indivisible block
            if block.block_type == BlockType.FIGURE_VECTOR and block.vector_paths:
                xs = [pt[0] for path in block.vector_paths for pt in path]
                ys = [pt[1] for path in block.vector_paths for pt in path]
                w_mm = (max(xs) - min(xs)) * 0.352778  # pt to mm
                h_mm = (max(ys) - min(ys)) * 0.352778
                if w_mm > self.usable_width or h_mm > self.usable_height:
                    raise LayoutOverflowError(
                        f"Figure block {block.block_id} dimensions ({w_mm:.1f}x{h_mm:.1f} mm) exceed "
                        f"printable area ({self.usable_width:.1f}x{self.usable_height:.1f} mm). "
                        "Suggestion: Scale down figure or split into multiple smaller panels."
                    )

            if block.block_type in (BlockType.TITLE, BlockType.HEADING):
                font_sz = 6.5 if block.block_type == BlockType.TITLE else 5.5
                lines = self._wrap_text(block.text, self.usable_width, font_sz)
                for line in lines:
                    if current_y() < self.usable_min_y:
                        flush_page()

                    y_pos = current_y()
                    y_pos = self.snap_to_ruled_baseline(y_pos, ruled_baselines)
                    strokes = self.humanizer.synthesize_line(
                        line,
                        start_x_mm=self.usable_min_x,
                        base_y_mm=y_pos,
                        font_size_mm=font_sz,
                    )
                    safe_strokes = self._filter_keepout_strokes(strokes)
                    if safe_strokes:
                        current_page_paths.append(CorePath(safe_strokes, label=block.block_id))
                        recorded_baselines.append(y_pos)
                    current_baseline_idx += 1

            elif block.block_type == BlockType.EQUATION:
                latex_code = block.latex or block.text.replace("$$", "").strip()
                try:
                    res = self.math_engine.render_equation_to_strokes(
                        latex_code,
                        target_height_mm=5.0,
                        x_offset=self.usable_min_x + 10.0,
                        y_offset=current_y(),
                    )
                    eq_height = res.bounds.max_y - res.bounds.min_y
                    lines_needed = max(1, math.ceil(eq_height / line_height))

                    if current_y() - eq_height < self.usable_min_y:
                        flush_page()

                    # Re-render at new Y if page was flushed
                    y_pos = current_y()
                    y_pos = self.snap_to_ruled_baseline(y_pos, ruled_baselines)
                    res = self.math_engine.render_equation_to_strokes(
                        latex_code,
                        target_height_mm=5.0,
                        x_offset=self.usable_min_x + 10.0,
                        y_offset=y_pos,
                    )
                    safe_strokes = self._filter_keepout_strokes(list(res.strokes))
                    if safe_strokes:
                        current_page_paths.append(CorePath(safe_strokes, label=f"eq_{block.block_id}"))
                        recorded_baselines.append(y_pos)
                    current_baseline_idx += lines_needed
                except Exception:
                    # Fallback text rendering
                    lines = self._wrap_text(block.text, self.usable_width, 4.5)
                    for line in lines:
                        if current_y() < self.usable_min_y:
                            flush_page()
                        y_pos = current_y()
                        y_pos = self.snap_to_ruled_baseline(y_pos, ruled_baselines)
                        strokes = self.humanizer.synthesize_line(
                            line, self.usable_min_x + 10.0, y_pos, font_size_mm=4.5
                        )
                        safe_strokes = self._filter_keepout_strokes(strokes)
                        if safe_strokes:
                            current_page_paths.append(CorePath(safe_strokes, label=block.block_id))
                            recorded_baselines.append(y_pos)
                        current_baseline_idx += 1

            elif block.block_type in (BlockType.PARAGRAPH, BlockType.LIST_ITEM):
                font_sz = 4.5
                indent = 6.0 if block.block_type == BlockType.LIST_ITEM else 0.0
                is_item = block.block_type == BlockType.LIST_ITEM
                prefix = "- " if is_item and not block.text.startswith("- ") else ""
                full_text = prefix + block.text
                lines = self._wrap_text(full_text, self.usable_width - indent, font_sz)
                for line in lines:
                    if current_y() < self.usable_min_y:
                        flush_page()

                    y_pos = current_y()
                    y_pos = self.snap_to_ruled_baseline(y_pos, ruled_baselines)
                    strokes = self.humanizer.synthesize_line(
                        line,
                        start_x_mm=self.usable_min_x + indent,
                        base_y_mm=y_pos,
                        font_size_mm=font_sz,
                    )
                    safe_strokes = self._filter_keepout_strokes(strokes)
                    if safe_strokes:
                        current_page_paths.append(CorePath(safe_strokes, label=block.block_id))
                        recorded_baselines.append(y_pos)
                    current_baseline_idx += 1

            elif block.block_type == BlockType.FIGURE_VECTOR and block.vector_paths:
                # Convert vector paths to mm and position
                strokes_fig: list[Stroke] = []
                # Find bounds in pt
                xs = [pt[0] for path in block.vector_paths for pt in path]
                ys = [pt[1] for path in block.vector_paths for pt in path]
                min_x_pt, max_x_pt = min(xs), max(xs)
                min_y_pt, max_y_pt = min(ys), max(ys)
                w_mm = (max_x_pt - min_x_pt) * 0.352778
                h_mm = (max_y_pt - min_y_pt) * 0.352778

                scale = 1.0
                if w_mm > self.usable_width:
                    scale = self.usable_width / w_mm

                w_final = w_mm * scale
                h_final = h_mm * scale

                lines_needed = max(1, math.ceil(h_final / line_height))
                if current_y() - h_final < self.usable_min_y:
                    flush_page()

                base_top_y = current_y()
                # Center horizontally
                ox = self.usable_min_x + (self.usable_width - w_final) / 2.0

                for path in block.vector_paths:
                    if len(path) < 2:
                        continue
                    pts = [
                        Point(
                            ox + (pt[0] - min_x_pt) * 0.352778 * scale,
                            base_top_y - (max_y_pt - pt[1]) * 0.352778 * scale,
                        )
                        for pt in path
                    ]
                    strokes_fig.append(Stroke(pts))

                safe_strokes = self._filter_keepout_strokes(strokes_fig)
                if safe_strokes:
                    current_page_paths.append(CorePath(safe_strokes, label=block.block_id))
                current_baseline_idx += lines_needed

        flush_page()

        total_strokes = sum(len(path.strokes) for page in pages for path in page.paths)
        total_len = sum(page.total_length_mm for page in pages)

        return ComposerResult(
            pages=pages,
            page_count=len(pages),
            total_stroke_count=total_strokes,
            total_length_mm=round(total_len, 2),
            baseline_y_positions=recorded_baselines,
        )

    def _wrap_text(self, text: str, max_width_mm: float, font_size_mm: float) -> list[str]:
        """Greedy word wrapping based on character advance width estimation."""
        avg_char_w = font_size_mm * 0.55
        words = text.split(" ")
        lines: list[str] = []
        curr_line: list[str] = []
        curr_w = 0.0

        for w in words:
            word_w = len(w) * avg_char_w + (avg_char_w if curr_line else 0.0)
            if curr_w + word_w > max_width_mm and curr_line:
                lines.append(" ".join(curr_line))
                curr_line = [w]
                curr_w = len(w) * avg_char_w
            else:
                curr_line.append(w)
                curr_w += word_w

        if curr_line:
            lines.append(" ".join(curr_line))
        return lines or [text]

    def _filter_keepout_strokes(self, strokes: Sequence[Stroke]) -> list[Stroke]:
        """Filters out or clips strokes that intersect binder clip keep-out polygons."""
        if not self.keepouts:
            return list(strokes)

        valid_strokes: list[Stroke] = []
        for s in strokes:
            intersects = False
            for ko in self.keepouts:
                if ko.intersects_stroke(s):
                    intersects = True
                    break
            if not intersects:
                valid_strokes.append(s)
        return valid_strokes
