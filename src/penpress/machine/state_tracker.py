"""Live machine state tracking for Marlin serial communications (P7-1).

Tracks real-time machine 3D coordinates, buffer occupancy, homing status,
current layer/stroke execution progress, and transmission telemetry.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import StrEnum

from penpress.core.primitives import Point


class MachineConnectionState(StrEnum):
    DISCONNECTED = "DISCONNECTED"
    CONNECTING = "CONNECTING"
    IDLE = "IDLE"
    PRINTING = "PRINTING"
    PAUSED = "PAUSED"
    ERROR = "ERROR"


@dataclass
class MachineStateTracker:
    """Tracks state and telemetry of the physical or virtual 3D printer."""

    status: MachineConnectionState = MachineConnectionState.DISCONNECTED
    port: str = ""
    baudrate: int = 115200

    # Kinematic position
    pos_x_mm: float = 0.0
    pos_y_mm: float = 0.0
    pos_z_mm: float = 3.5
    feedrate_mm_min: float = 6000.0
    is_homed: bool = False

    # Execution telemetry
    current_stroke_id: int = 0
    total_strokes: int = 0
    current_line_number: int = 0
    lines_sent: int = 0
    lines_acknowledged: int = 0
    resend_count: int = 0
    error_count: int = 0

    # Planning queue depth
    buffer_depth: int = 0
    max_buffer_depth: int = 16

    # Warning and error history
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def current_position(self) -> Point:
        return Point(self.pos_x_mm, self.pos_y_mm)

    @property
    def progress_pct(self) -> float:
        if self.total_strokes <= 0:
            return 0.0
        return min(100.0, max(0.0, 100.0 * self.current_stroke_id / self.total_strokes))

    def update_position(
        self,
        x: float | None = None,
        y: float | None = None,
        z: float | None = None,
        feedrate: float | None = None,
    ) -> None:
        if x is not None and math.isfinite(x):
            self.pos_x_mm = x
        if y is not None and math.isfinite(y):
            self.pos_y_mm = y
        if z is not None and math.isfinite(z):
            self.pos_z_mm = z
        if feedrate is not None and math.isfinite(feedrate):
            self.feedrate_mm_min = feedrate

    def record_warning(self, msg: str) -> None:
        self.warnings.append(msg)

    def record_error(self, msg: str) -> None:
        self.errors.append(msg)
        self.error_count += 1
