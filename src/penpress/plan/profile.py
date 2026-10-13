"""Machine profile configuration and validation for Marlin pen plotters."""

from __future__ import annotations

import math
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from penpress.core.primitives import CoreGeometryError


class MachineProfileError(CoreGeometryError):
    """Raised when machine profile validation constraints fail."""


@dataclass(frozen=True, slots=True)
class MachineProfile:
    """Hardware and kinematics profile for a Marlin 3D-printer pen plotter.

    Attributes:
        name: Profile display name.
        firmware: Firmware dialect ("marlin").
        bed_width_mm: Total bed width in mm.
        bed_height_mm: Total bed height in mm.
        margin_left_mm: Left margin in mm.
        margin_right_mm: Right margin in mm.
        margin_bottom_mm: Bottom margin in mm.
        margin_top_mm: Top margin in mm.
        offset_x_mm: Toolhead pen offset X in mm.
        offset_y_mm: Toolhead pen offset Y in mm.
        z_lift_mm: Safe travel height above bed in mm.
        z_write_mm: Pen contact height in mm.
        z_write_min_mm: Minimum allowed Z write height safety floor in mm.
        travel_feedrate_mm_min: Rapid XY travel speed in mm/min.
        draw_feedrate_mm_min: Writing XY speed in mm/min.
        z_lift_feedrate_mm_min: Z lift speed in mm/min.
        z_drop_feedrate_mm_min: Z touch/drop speed in mm/min.
        disable_heaters: Whether to emit M104 S0 and M140 S0 in preamble.
        disable_fans: Whether to emit M107 in preamble.
        lift_z_first: Ensure first motion command raises Z before any XY travel.
        home_xy_first: Whether to home axes (G28) in preamble.
        disable_steppers_on_finish: Emit M84 in postamble.
    """

    name: str = "Ender 3 Pro (Pen Plotter)"
    firmware: str = "marlin"
    bed_width_mm: float = 235.0
    bed_height_mm: float = 235.0
    margin_left_mm: float = 10.0
    margin_right_mm: float = 10.0
    margin_bottom_mm: float = 10.0
    margin_top_mm: float = 10.0
    offset_x_mm: float = 0.0
    offset_y_mm: float = 0.0
    z_lift_mm: float = 3.5
    z_write_mm: float = 0.5
    z_write_min_mm: float = 0.1
    travel_feedrate_mm_min: float = 6000.0
    draw_feedrate_mm_min: float = 2400.0
    z_lift_feedrate_mm_min: float = 1200.0
    z_drop_feedrate_mm_min: float = 800.0
    disable_heaters: bool = True
    disable_fans: bool = True
    lift_z_first: bool = True
    home_xy_first: bool = True
    disable_steppers_on_finish: bool = True

    def __post_init__(self) -> None:
        """Validate profile parameters."""
        if not math.isfinite(self.bed_width_mm) or self.bed_width_mm <= 0.0:
            raise MachineProfileError(f"bed_width_mm must be positive finite, got {self.bed_width_mm}")
        if not math.isfinite(self.bed_height_mm) or self.bed_height_mm <= 0.0:
            raise MachineProfileError(f"bed_height_mm must be positive finite, got {self.bed_height_mm}")

        for m_name, m_val in (
            ("margin_left_mm", self.margin_left_mm),
            ("margin_right_mm", self.margin_right_mm),
            ("margin_bottom_mm", self.margin_bottom_mm),
            ("margin_top_mm", self.margin_top_mm),
        ):
            if not math.isfinite(m_val) or m_val < 0.0:
                raise MachineProfileError(f"{m_name} must be non-negative finite, got {m_val}")

        if self.usable_width_mm <= 0.0:
            raise MachineProfileError(f"Margins exceed bed width: usable_width={self.usable_width_mm} <= 0")
        if self.usable_height_mm <= 0.0:
            raise MachineProfileError(
                f"Margins exceed bed height: usable_height={self.usable_height_mm} <= 0"
            )

        if not math.isfinite(self.z_write_min_mm) or self.z_write_min_mm <= 0.0:
            raise MachineProfileError(f"z_write_min_mm must be positive, got {self.z_write_min_mm}")
        if not math.isfinite(self.z_write_mm) or self.z_write_mm < self.z_write_min_mm:
            raise MachineProfileError(
                f"z_write_mm ({self.z_write_mm}) cannot be less than safety floor ({self.z_write_min_mm})"
            )
        if not math.isfinite(self.z_lift_mm) or self.z_lift_mm <= self.z_write_mm:
            raise MachineProfileError(
                f"z_lift_mm ({self.z_lift_mm}) must be strictly greater than z_write_mm ({self.z_write_mm})"
            )

        for feed_name, feed_val in (
            ("travel_feedrate_mm_min", self.travel_feedrate_mm_min),
            ("draw_feedrate_mm_min", self.draw_feedrate_mm_min),
            ("z_lift_feedrate_mm_min", self.z_lift_feedrate_mm_min),
            ("z_drop_feedrate_mm_min", self.z_drop_feedrate_mm_min),
        ):
            if not math.isfinite(feed_val) or feed_val <= 0.0:
                raise MachineProfileError(f"{feed_name} must be positive finite, got {feed_val}")

    @property
    def usable_min_x(self) -> float:
        """Minimum safe X coordinate in mm."""
        return self.margin_left_mm

    @property
    def usable_max_x(self) -> float:
        """Maximum safe X coordinate in mm."""
        return self.bed_width_mm - self.margin_right_mm

    @property
    def usable_min_y(self) -> float:
        """Minimum safe Y coordinate in mm."""
        return self.margin_bottom_mm

    @property
    def usable_max_y(self) -> float:
        """Maximum safe Y coordinate in mm."""
        return self.bed_height_mm - self.margin_top_mm

    @property
    def usable_width_mm(self) -> float:
        """Width of usable printing area in mm."""
        return self.bed_width_mm - self.margin_left_mm - self.margin_right_mm

    @property
    def usable_height_mm(self) -> float:
        """Height of usable printing area in mm."""
        return self.bed_height_mm - self.margin_bottom_mm - self.margin_top_mm

    @classmethod
    def from_toml_file(cls, path: Path | str) -> MachineProfile:
        """Load and validate a MachineProfile from a TOML file."""
        p = Path(path)
        if not p.is_file():
            raise MachineProfileError(f"Profile file not found: {p}")
        try:
            with p.open("rb") as f:
                data = tomllib.load(f)
        except Exception as exc:
            raise MachineProfileError(f"Failed to parse TOML profile {p}: {exc}") from exc

        return cls.from_dict(data)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> MachineProfile:
        """Instantiate MachineProfile from dictionary."""
        machine = data.get("machine", {})
        pen = data.get("pen", {})
        speeds = data.get("speeds", {})
        safety = data.get("safety", {})

        return cls(
            name=str(machine.get("name", "Ender 3 Pro (Pen Plotter)")),
            firmware=str(machine.get("firmware", "marlin")),
            bed_width_mm=float(machine.get("bed_width_mm", 235.0)),
            bed_height_mm=float(machine.get("bed_height_mm", 235.0)),
            margin_left_mm=float(machine.get("margin_left_mm", 10.0)),
            margin_right_mm=float(machine.get("margin_right_mm", 10.0)),
            margin_bottom_mm=float(machine.get("margin_bottom_mm", 10.0)),
            margin_top_mm=float(machine.get("margin_top_mm", 10.0)),
            offset_x_mm=float(pen.get("offset_x_mm", 0.0)),
            offset_y_mm=float(pen.get("offset_y_mm", 0.0)),
            z_lift_mm=float(pen.get("z_lift_mm", 3.5)),
            z_write_mm=float(pen.get("z_write_mm", 0.5)),
            z_write_min_mm=float(pen.get("z_write_min_mm", 0.1)),
            travel_feedrate_mm_min=float(speeds.get("travel_feedrate_mm_min", 6000.0)),
            draw_feedrate_mm_min=float(speeds.get("draw_feedrate_mm_min", 2400.0)),
            z_lift_feedrate_mm_min=float(speeds.get("z_lift_feedrate_mm_min", 1200.0)),
            z_drop_feedrate_mm_min=float(speeds.get("z_drop_feedrate_mm_min", 800.0)),
            disable_heaters=bool(safety.get("disable_heaters", True)),
            disable_fans=bool(safety.get("disable_fans", True)),
            lift_z_first=bool(safety.get("lift_z_first", True)),
            home_xy_first=bool(safety.get("home_xy_first", True)),
            disable_steppers_on_finish=bool(safety.get("disable_steppers_on_finish", True)),
        )
