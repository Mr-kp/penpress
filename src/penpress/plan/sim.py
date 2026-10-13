"""Virtual Marlin 3D-printer firmware simulator and toolpath renderer."""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import TextIO

from PIL import Image, ImageDraw

from penpress.core.primitives import CoreGeometryError
from penpress.plan.profile import MachineProfile


class MarlinErrorCode(StrEnum):
    """Machine error and violation codes emitted by Marlin simulator."""

    ERR_OUT_OF_BOUNDS = "ERR_OUT_OF_BOUNDS"
    ERR_Z_BELOW_MIN = "ERR_Z_BELOW_MIN"
    ERR_HEATER_COMMAND = "ERR_HEATER_COMMAND"
    ERR_UNKNOWN_COMMAND = "ERR_UNKNOWN_COMMAND"
    ERR_CHECKSUM_MISMATCH = "ERR_CHECKSUM_MISMATCH"
    ERR_LINE_NUMBER_OUT_OF_ORDER = "ERR_LINE_NUMBER_OUT_OF_ORDER"


class MarlinSimulatorError(CoreGeometryError):
    """Exception raised on fatal simulator errors or violations."""

    def __init__(self, code: MarlinErrorCode, message: str) -> None:
        super().__init__(f"[{code.value}] {message}")
        self.code = code
        self.message = message


@dataclass(frozen=True, slots=True)
class MoveSegment:
    """An executed motion segment in 3D machine space.

    Attributes:
        start_x: Initial X coordinate in mm.
        start_y: Initial Y coordinate in mm.
        start_z: Initial Z coordinate in mm.
        end_x: Final X coordinate in mm.
        end_y: Final Y coordinate in mm.
        end_z: Final Z coordinate in mm.
        feedrate_mm_min: Modal travel or feed rate in mm/min.
        pen_contact: True if pen is in writing contact with surface.
        command: G0 (rapid) or G1 (linear move).
        duration_s: Computed trapezoidal travel time in seconds.
    """

    start_x: float
    start_y: float
    start_z: float
    end_x: float
    end_y: float
    end_z: float
    feedrate_mm_min: float
    pen_contact: bool
    command: str
    duration_s: float


@dataclass
class SimulatorState:
    """Live kinematic state of the virtual Marlin machine."""

    x: float = 0.0
    y: float = 0.0
    z: float = 3.5  # Safe default clearance height (z_lift)
    feedrate_mm_min: float = 6000.0
    absolute_mode: bool = True  # G90 = True, G91 = False
    millimeter_mode: bool = True  # G21 = True, G20 = False
    is_homed: bool = False
    steppers_enabled: bool = True
    fan_speed: int = 0
    extruder_temp: float = 0.0
    bed_temp: float = 0.0
    last_line_number: int = 0
    total_time_seconds: float = 0.0


def compute_trapezoid_time(distance_mm: float, v_feedrate_mm_s: float, acceleration_mm_s2: float) -> float:
    """Compute move duration with a symmetric trapezoidal (or triangular) velocity profile.

    Assumes start velocity v_start = 0 and end velocity v_end = 0.
    Maximum feedrate is capped at v_feedrate_mm_s.

    Args:
        distance_mm: Euclidean distance travelled in mm.
        v_feedrate_mm_s: Target maximum velocity in mm/s.
        acceleration_mm_s2: Constant axis acceleration in mm/s^2.

    Returns:
        Duration in seconds.
    """
    if distance_mm <= 1e-9:
        return 0.0
    if acceleration_mm_s2 <= 1e-9:
        return distance_mm / max(v_feedrate_mm_s, 1e-6)

    # Distance required to accelerate from 0 to v and back to 0:
    # d_crit = 2 * (v^2 / (2 * a)) = v^2 / a
    d_crit = (v_feedrate_mm_s**2) / acceleration_mm_s2

    if distance_mm >= d_crit:
        # Full trapezoid: ramp up to v, cruise at v, ramp down to 0
        t_ramp = v_feedrate_mm_s / acceleration_mm_s2
        d_cruise = distance_mm - d_crit
        t_cruise = d_cruise / v_feedrate_mm_s
        return 2.0 * t_ramp + t_cruise
    else:
        # Triangular profile: peak velocity v_peak < v_target
        # distance = v_peak^2 / a  =>  v_peak = sqrt(distance * a)
        v_peak = math.sqrt(distance_mm * acceleration_mm_s2)
        return 2.0 * (v_peak / acceleration_mm_s2)


class MarlinSimulator:
    """Virtual Marlin 3D-printer firmware emulator for pen plotters."""

    def __init__(
        self,
        profile: MachineProfile,
        strict_safety: bool = True,
        acceleration_mm_s2: float = 500.0,
    ) -> None:
        self.profile = profile
        self.strict_safety = strict_safety
        self.acceleration_mm_s2 = acceleration_mm_s2

        self.state = SimulatorState(z=self.profile.z_lift_mm)
        self.segments: list[MoveSegment] = []
        self.violations: list[tuple[MarlinErrorCode, str]] = []

        # Known allowed commands and regex
        self._gcode_param_re = re.compile(r"([A-Z])([-+]?[0-9]*\.?[0-9]+)")

    def reset(self) -> None:
        """Reset simulator state to cold boot defaults."""
        self.state = SimulatorState(z=self.profile.z_lift_mm)
        self.segments.clear()
        self.violations.clear()

    def execute_line(self, raw_line: str) -> str:
        """Execute a single line of serial G-code input and return Marlin serial response."""
        line = raw_line.strip()

        # Handle comments only
        if not line or line.startswith(";"):
            return "ok\n"

        # Check line number & checksum protocol (e.g. N123 G0 X10*45)
        parsed_cmd = line
        expected_line_num: int | None = None

        if line.startswith("N") and " " in line:
            # Format: N<num> <content>*<checksum> or N<num> <content>
            match_cs = re.match(r"^N(\d+)\s+(.*?)(?:\*(\d+))?$", line)
            if match_cs:
                expected_line_num = int(match_cs.group(1))
                payload_cmd = match_cs.group(2)
                cs_str = match_cs.group(3)

                if cs_str is not None:
                    expected_cs = int(cs_str)
                    calc_cs = 0
                    full_payload = f"N{expected_line_num} {payload_cmd}"
                    for ch in full_payload:
                        calc_cs ^= ord(ch)

                    if calc_cs != expected_cs:
                        err_msg = (
                            f"Checksum mismatch: computed {calc_cs}, "
                            f"received {expected_cs} on line {expected_line_num}"
                        )
                        self.violations.append((MarlinErrorCode.ERR_CHECKSUM_MISMATCH, err_msg))
                        resend_n = self.state.last_line_number + 1
                        return (
                            f"Error:checksum mismatch, Last Line: {self.state.last_line_number}\n"
                            f"Resend: {resend_n}\nok\n"
                        )

                if self.state.last_line_number > 0 and expected_line_num != self.state.last_line_number + 1:
                    err_msg = (
                        f"Line number out of order: received {expected_line_num}, "
                        f"expected {self.state.last_line_number + 1}"
                    )
                    self.violations.append((MarlinErrorCode.ERR_LINE_NUMBER_OUT_OF_ORDER, err_msg))
                    resend_n = self.state.last_line_number + 1
                    return (
                        f"Error:Line Number is not Last Line Number+1, "
                        f"Last Line: {self.state.last_line_number}\n"
                        f"Resend: {resend_n}\nok\n"
                    )

                parsed_cmd = payload_cmd
                self.state.last_line_number = expected_line_num

        # Strip trailing comments from payload
        if ";" in parsed_cmd:
            parsed_cmd = parsed_cmd.split(";", 1)[0].strip()

        if not parsed_cmd:
            return "ok\n"

        # Parse command tokens (e.g. G0 X10 Y20 F3000)
        tokens = parsed_cmd.split()
        cmd = tokens[0].upper()
        params: dict[str, float] = {}

        for part in tokens[1:]:
            m = self._gcode_param_re.match(part.upper())
            if m:
                params[m.group(1)] = float(m.group(2))

        # Process command
        try:
            self._dispatch_command(cmd, params)
        except MarlinSimulatorError as ex:
            self.violations.append((ex.code, ex.message))
            if self.strict_safety:
                raise
            return f"!! {ex.code.value}: {ex.message}\nok\n"

        return "ok\n"

    def _dispatch_command(self, cmd: str, params: dict[str, float]) -> None:
        """Dispatch parsed G-code command and mutate machine state."""
        if cmd in ("M104", "M109", "M140", "M190"):
            self._handle_heater(cmd, params)
        elif cmd in ("G90", "G91", "G20", "G21"):
            self._handle_mode(cmd)
        elif cmd == "G28":
            self.state.x = 0.0
            self.state.y = 0.0
            self.state.z = 0.0
            self.state.is_homed = True
        elif cmd in ("M106", "M107", "M84", "M18", "M17", "M114"):
            self._handle_aux(cmd, params)
        elif cmd in ("G0", "G1"):
            self._handle_motion(cmd, params)
        else:
            raise MarlinSimulatorError(
                MarlinErrorCode.ERR_UNKNOWN_COMMAND,
                f"Unknown or unsupported Marlin command: {cmd}",
            )

    def _handle_heater(self, cmd: str, params: dict[str, float]) -> None:
        """Handle heater off commands or reject positive temperatures."""
        temp_target = params.get("S", 0.0)
        if temp_target > 0.0:
            raise MarlinSimulatorError(
                MarlinErrorCode.ERR_HEATER_COMMAND,
                f"Heater activation command {cmd} S{temp_target} forbidden in pen plotter mode",
            )
        if cmd in ("M104", "M109"):
            self.state.extruder_temp = temp_target
        else:
            self.state.bed_temp = temp_target

    def _handle_mode(self, cmd: str) -> None:
        """Handle coordinate and unit mode selections."""
        if cmd == "G90":
            self.state.absolute_mode = True
        elif cmd == "G91":
            self.state.absolute_mode = False
        elif cmd == "G20":
            self.state.millimeter_mode = False
        elif cmd == "G21":
            self.state.millimeter_mode = True

    def _handle_aux(self, cmd: str, params: dict[str, float]) -> None:
        """Handle auxiliary machine commands."""
        if cmd == "M107":
            self.state.fan_speed = 0
        elif cmd == "M106":
            self.state.fan_speed = int(params.get("S", 255.0))
        elif cmd in {"M84", "M18"}:
            self.state.steppers_enabled = False
        elif cmd == "M17":
            self.state.steppers_enabled = True

    def _handle_motion(self, cmd: str, params: dict[str, float]) -> None:
        """Handle G0/G1 motion commands, check boundaries, and record segments."""
        if "F" in params:
            self.state.feedrate_mm_min = params["F"]

        target_x = self.state.x
        target_y = self.state.y
        target_z = self.state.z

        if self.state.absolute_mode:
            if "X" in params:
                target_x = params["X"]
            if "Y" in params:
                target_y = params["Y"]
            if "Z" in params:
                target_z = params["Z"]
        else:
            if "X" in params:
                target_x += params["X"]
            if "Y" in params:
                target_y += params["Y"]
            if "Z" in params:
                target_z += params["Z"]

        if not self.state.millimeter_mode:
            target_x *= 25.4
            target_y *= 25.4
            target_z *= 25.4

        if target_z < self.profile.z_write_min_mm - 1e-4:
            raise MarlinSimulatorError(
                MarlinErrorCode.ERR_Z_BELOW_MIN,
                f"Target Z {target_z:.3f} mm is below safety floor {self.profile.z_write_min_mm:.3f} mm",
            )

        if not (-1e-4 <= target_x <= self.profile.bed_width_mm + 1e-4):
            raise MarlinSimulatorError(
                MarlinErrorCode.ERR_OUT_OF_BOUNDS,
                f"Target X {target_x:.3f} mm outside bed limits [0.0..{self.profile.bed_width_mm:.1f}]",
            )
        if not (-1e-4 <= target_y <= self.profile.bed_height_mm + 1e-4):
            raise MarlinSimulatorError(
                MarlinErrorCode.ERR_OUT_OF_BOUNDS,
                f"Target Y {target_y:.3f} mm outside bed limits [0.0..{self.profile.bed_height_mm:.1f}]",
            )

        dx = target_x - self.state.x
        dy = target_y - self.state.y
        dz = target_z - self.state.z
        distance_3d = math.sqrt(dx * dx + dy * dy + dz * dz)

        v_feed_mm_s = self.state.feedrate_mm_min / 60.0
        move_duration = compute_trapezoid_time(distance_3d, v_feed_mm_s, self.acceleration_mm_s2)

        pen_contact = (
            target_z <= self.profile.z_write_mm + 1e-4 and self.state.z <= self.profile.z_write_mm + 1e-4
        )

        segment = MoveSegment(
            start_x=self.state.x,
            start_y=self.state.y,
            start_z=self.state.z,
            end_x=target_x,
            end_y=target_y,
            end_z=target_z,
            feedrate_mm_min=self.state.feedrate_mm_min,
            pen_contact=pen_contact,
            command=cmd,
            duration_s=move_duration,
        )
        self.segments.append(segment)

        self.state.x = target_x
        self.state.y = target_y
        self.state.z = target_z
        self.state.total_time_seconds += move_duration

    def execute_stream(self, stream: TextIO | list[str] | str) -> list[str]:
        """Execute multiple lines of G-code and collect serial responses."""
        lines: list[str]
        if isinstance(stream, str):
            lines = stream.splitlines()
        elif isinstance(stream, list):
            lines = stream
        else:
            lines = stream.readlines()

        responses: list[str] = []
        for line in lines:
            resp = self.execute_line(line)
            responses.append(resp)
        return responses

    def render_to_image(
        self,
        width_px: int = 940,
        height_px: int = 940,
        bg_color: tuple[int, int, int] = (13, 14, 18),
        bed_border_color: tuple[int, int, int] = (33, 38, 56),
        travel_color: tuple[int, int, int] = (100, 100, 120),
        draw_color: tuple[int, int, int] = (248, 250, 252),
    ) -> Image.Image:
        """Render executed machine toolpaths to a Pillow raster image.

        Bed origin (0, 0) is at bottom-left in machine space.
        Y is flipped to match standard screen coordinates (0 at top).
        """
        bed_w = self.profile.bed_width_mm
        bed_h = self.profile.bed_height_mm

        scale_x = width_px / bed_w
        scale_y = height_px / bed_h
        scale = min(scale_x, scale_y)

        pad_x = (width_px - (bed_w * scale)) / 2.0
        pad_y = (height_px - (bed_h * scale)) / 2.0

        img = Image.new("RGB", (width_px, height_px), color=bg_color)
        draw = ImageDraw.Draw(img)

        bx0 = pad_x
        by0 = pad_y
        bx1 = pad_x + bed_w * scale
        by1 = pad_y + bed_h * scale
        draw.rectangle([bx0, by0, bx1, by1], outline=bed_border_color, width=2)

        def to_img(x: float, y: float) -> tuple[float, float]:
            ix = pad_x + x * scale
            iy = pad_y + (bed_h - y) * scale
            return ix, iy

        # Draw rapid travel moves
        for seg in self.segments:
            if not seg.pen_contact:
                p0 = to_img(seg.start_x, seg.start_y)
                p1 = to_img(seg.end_x, seg.end_y)
                if abs(p0[0] - p1[0]) > 0.1 or abs(p0[1] - p1[1]) > 0.1:
                    draw.line([p0, p1], fill=travel_color, width=1)

        # Draw writing strokes
        for seg in self.segments:
            if seg.pen_contact:
                p0 = to_img(seg.start_x, seg.start_y)
                p1 = to_img(seg.end_x, seg.end_y)
                if abs(p0[0] - p1[0]) > 0.1 or abs(p0[1] - p1[1]) > 0.1:
                    draw.line([p0, p1], fill=draw_color, width=2)

        return img

    def save_image(self, path: Path | str, **kwargs: float | int | tuple[int, int, int]) -> None:
        """Save rendered toolpath image to disk."""
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        img = self.render_to_image(**kwargs)  # type: ignore[arg-type]
        img.save(target)

    def render_to_svg(self) -> str:
        """Render executed machine toolpaths to SVG format."""
        bed_w = self.profile.bed_width_mm
        bed_h = self.profile.bed_height_mm

        svg_lines: list[str] = [
            f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {bed_w:.1f} {bed_h:.1f}" '
            f'width="{bed_w:.1f}mm" height="{bed_h:.1f}mm">',
            f'  <rect x="0" y="0" width="{bed_w:.1f}" height="{bed_h:.1f}" '
            'fill="#0d0e12" stroke="#212638" stroke-width="0.5"/>',
            "  <!-- Rapid Travel Paths -->",
            '  <g stroke="#646478" stroke-width="0.2" stroke-dasharray="1,1">',
        ]

        for seg in self.segments:
            if not seg.pen_contact:
                y0 = bed_h - seg.start_y
                y1 = bed_h - seg.end_y
                svg_lines.append(
                    f'    <line x1="{seg.start_x:.3f}" y1="{y0:.3f}" x2="{seg.end_x:.3f}" y2="{y1:.3f}"/>'
                )

        svg_lines.append("  </g>")
        svg_lines.append("  <!-- Pen Writing Strokes -->")
        svg_lines.append('  <g stroke="#f8fafc" stroke-width="0.4" stroke-linecap="round">')

        for seg in self.segments:
            if seg.pen_contact:
                y0 = bed_h - seg.start_y
                y1 = bed_h - seg.end_y
                svg_lines.append(
                    f'    <line x1="{seg.start_x:.3f}" y1="{y0:.3f}" x2="{seg.end_x:.3f}" y2="{y1:.3f}"/>'
                )

        svg_lines.append("  </g>")
        svg_lines.append("</svg>")
        return "\n".join(svg_lines)
