from __future__ import annotations

import math
from pathlib import Path
from typing import TextIO

from penpress.core.primitives import CoreGeometryError, Page, Point, Stroke
from penpress.plan.profile import MachineProfile


class GcodeOutOfBoundsError(CoreGeometryError):
    """Raised when coordinates exceed the printable bed area and clamping is disabled."""


class GcodeCompiler:
    """Compiles vector stroke pages into Marlin-compatible G-code."""

    def __init__(
        self,
        profile: MachineProfile,
        paper_origin_x_mm: float = 0.0,
        paper_origin_y_mm: float = 0.0,
        paper_rotation_deg: float = 0.0,
        clamp_to_bed: bool = False,
        emit_line_numbers: bool = False,
    ) -> None:
        self.profile = profile
        self.paper_origin_x_mm = paper_origin_x_mm
        self.paper_origin_y_mm = paper_origin_y_mm
        self.paper_rotation_deg = paper_rotation_deg
        self.clamp_to_bed = clamp_to_bed
        self.emit_line_numbers = emit_line_numbers

        # Precompute rotation radians
        self._rad = math.radians(paper_rotation_deg)
        self._cos = math.cos(self._rad)
        self._sin = math.sin(self._rad)

    def _page_to_machine(self, pt: Point) -> tuple[float, float]:
        """Convert page point in mm to machine bed coordinates in mm."""
        # 1. Rotate around paper origin
        rx = pt.x * self._cos - pt.y * self._sin
        ry = pt.x * self._sin + pt.y * self._cos

        # 2. Translate by paper origin + toolhead pen offset
        mx = rx + self.paper_origin_x_mm + self.profile.offset_x_mm
        my = ry + self.paper_origin_y_mm + self.profile.offset_y_mm

        # 3. Check bounds or clamp
        min_x = self.profile.usable_min_x
        max_x = self.profile.usable_max_x
        min_y = self.profile.usable_min_y
        max_y = self.profile.usable_max_y

        if self.clamp_to_bed:
            mx = max(min_x, min(max_x, mx))
            my = max(min_y, min(max_y, my))
        elif not (min_x - 1e-4 <= mx <= max_x + 1e-4 and min_y - 1e-4 <= my <= max_y + 1e-4):
            raise GcodeOutOfBoundsError(
                f"Point ({pt.x:.2f}, {pt.y:.2f}) maps to machine coords ({mx:.2f}, {my:.2f}) "
                f"which exceeds printable envelope [X: {min_x}..{max_x}, Y: {min_y}..{max_y}]."
            )

        return mx, my

    def compile(self, page: Page) -> str:
        """Compile a Page of strokes into a G-code string."""
        lines: list[str] = []
        line_num = 1

        def emit(cmd: str) -> None:
            nonlocal line_num
            if self.emit_line_numbers:
                checksum = 0
                payload = f"N{line_num} {cmd}"
                for ch in payload:
                    checksum ^= ord(ch)
                lines.append(f"{payload}*{checksum}")
                line_num += 1
            else:
                lines.append(cmd)

        # 1. Preamble & Safety Pre-flight
        lines.append("; --- PenPress Marlin G-code Output ---")
        lines.append(f"; Machine: {self.profile.name}")
        lines.append(f"; Page: {page.width_mm:.1f} x {page.height_mm:.1f} mm")

        # Disable heaters immediately (zero heat policy)
        if self.profile.disable_heaters:
            emit("M104 S0 ; Extruder heater off")
            emit("M140 S0 ; Bed heater off")

        # Disable part cooling fans
        if self.profile.disable_fans:
            emit("M107 ; Fan off")

        # Set units to millimetres and absolute positioning
        emit("G21 ; Units in millimetres")
        emit("G90 ; Absolute coordinates")

        # Crucial safety: Lift Z before any XY travel to avoid dragging pen across bed
        if self.profile.lift_z_first:
            emit(f"G0 Z{self.profile.z_lift_mm:.2f} F{self.profile.z_lift_feedrate_mm_min:.0f} ; Safe Z lift")

        # Home sequence
        if self.profile.home_xy_first:
            emit("G28 ; Home axes")
            # Re-ensure Z is raised after homing
            z_f = self.profile.z_lift_feedrate_mm_min
            emit(f"G0 Z{self.profile.z_lift_mm:.2f} F{z_f:.0f} ; Restore clearance Z")

        # 2. Iterate paths and strokes
        # Collect all strokes across paths
        all_strokes: list[Stroke] = []
        for path in page.paths:
            all_strokes.extend(path.strokes)

        total_segments = sum(len(s.points) - 1 for s in all_strokes)
        lines.append(f"; Total strokes: {len(all_strokes)}, total segments: {total_segments}")

        for s_idx, stroke in enumerate(all_strokes):
            pts = stroke.points
            if len(pts) < 2:
                continue

            # First point: rapid travel with pen UP
            start_mx, start_my = self._page_to_machine(pts[0])
            emit(
                f"G0 X{start_mx:.3f} Y{start_my:.3f} F{self.profile.travel_feedrate_mm_min:.0f} "
                f"; Move to stroke {s_idx + 1} start"
            )

            # Drop pen to write height
            emit(f"G1 Z{self.profile.z_write_mm:.2f} F{self.profile.z_drop_feedrate_mm_min:.0f} ; Pen down")

            # Draw stroke segments
            for pt in pts[1:]:
                mx, my = self._page_to_machine(pt)
                emit(f"G1 X{mx:.3f} Y{my:.3f} F{self.profile.draw_feedrate_mm_min:.0f}")

            # Lift pen UP before any subsequent travel
            emit(f"G0 Z{self.profile.z_lift_mm:.2f} F{self.profile.z_lift_feedrate_mm_min:.0f} ; Pen up")

        # 3. Postamble
        lines.append("; --- End of Print ---")
        # Final safe clearance lift
        park_z = self.profile.z_lift_mm + 10.0
        emit(f"G0 Z{park_z:.2f} F{self.profile.z_lift_feedrate_mm_min:.0f} ; Final park lift")
        # Park toolhead near home
        park_x = self.profile.usable_min_x
        park_y = self.profile.usable_max_y
        travel_f = self.profile.travel_feedrate_mm_min
        emit(f"G0 X{park_x:.1f} Y{park_y:.1f} F{travel_f:.0f} ; Present paper")

        if self.profile.disable_steppers_on_finish:
            emit("M84 ; Disable steppers")

        return "\n".join(lines) + "\n"

    def compile_to_file(self, page: Page, output_file: TextIO | Path | str) -> None:
        """Compile page and write directly to file."""
        gcode_text = self.compile(page)
        if isinstance(output_file, (str, Path)):
            p = Path(output_file)
            p.write_text(gcode_text, encoding="utf-8")
        else:
            output_file.write(gcode_text)
