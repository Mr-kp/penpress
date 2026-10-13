"""Persistent execution state and disconnect recovery engine (P7-1).

Saves real-time job progress to a local state file (`.print_state.json`).
Enables stroke-level resume after power interruptions, serial disconnects,
or computer sleep without tearing paper or repeating already-drawn strokes.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class PrintJobSnapshot:
    """Snapshot of a print job in progress."""

    job_id: str
    source_filename: str
    total_strokes: int
    last_completed_stroke_id: int
    last_line_number: int
    toolhead_x_mm: float
    toolhead_y_mm: float
    toolhead_z_mm: float
    is_paused: bool
    timestamp_iso: str


class HardwareRecoveryEngine:
    """Manages persistence and safe resumption of interrupted plot jobs."""

    def __init__(self, state_file_path: Path | str | None = None) -> None:
        if state_file_path is None:
            self.state_file = Path(".print_state.json")
        else:
            self.state_file = Path(state_file_path)

    def save_checkpoint(self, snapshot: PrintJobSnapshot) -> None:
        """Persist snapshot atomically to state file."""
        data = asdict(snapshot)
        tmp_file = self.state_file.with_suffix(".tmp")
        tmp_file.write_text(json.dumps(data, indent=2), encoding="utf-8")
        tmp_file.replace(self.state_file)

    def load_checkpoint(self) -> PrintJobSnapshot | None:
        """Load active checkpoint if it exists and is valid."""
        if not self.state_file.exists():
            return None

        try:
            raw = self.state_file.read_text(encoding="utf-8")
            data = json.loads(raw)
            return PrintJobSnapshot(
                job_id=str(data["job_id"]),
                source_filename=str(data["source_filename"]),
                total_strokes=int(data["total_strokes"]),
                last_completed_stroke_id=int(data["last_completed_stroke_id"]),
                last_line_number=int(data["last_line_number"]),
                toolhead_x_mm=float(data["toolhead_x_mm"]),
                toolhead_y_mm=float(data["toolhead_y_mm"]),
                toolhead_z_mm=float(data["toolhead_z_mm"]),
                is_paused=bool(data["is_paused"]),
                timestamp_iso=str(data["timestamp_iso"]),
            )
        except Exception:
            return None

    def clear_checkpoint(self) -> None:
        """Remove state file after clean job completion."""
        if self.state_file.exists():
            self.state_file.unlink()

    def generate_resume_preamble(
        self,
        snapshot: PrintJobSnapshot,
        safe_z_lift_mm: float = 5.0,
        feedrate_mm_min: float = 3000.0,
    ) -> list[str]:
        """Generate safe Marlin G-code preamble to resume job without colliding with paper."""
        return [
            "; --- PenPress Crash / Disconnect Recovery Preamble ---",
            f"; Resuming job {snapshot.job_id} after stroke {snapshot.last_completed_stroke_id}",
            "G21 ; Millimeters",
            "G90 ; Absolute coordinates",
            f"G0 Z{safe_z_lift_mm:.2f} F1200 ; Safe vertical clearance lift",
            "G28 X Y ; Re-home XY axes to restore spatial calibration",
            f"G0 Z{safe_z_lift_mm:.2f} F1200 ; Ensure pen remains raised",
            f"G0 X{snapshot.toolhead_x_mm:.2f} Y{snapshot.toolhead_y_mm:.2f} F{feedrate_mm_min:.0f}",
        ]
