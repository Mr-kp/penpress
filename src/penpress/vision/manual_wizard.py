"""Interactive manual tactile jog calibration state machine."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from penpress.core.primitives import Point
from penpress.vision.bed_model import PaperBedPlacement


class WizardStep(StrEnum):
    INITIAL = "INITIAL"
    JOG_CORNER_1_TL = "JOG_CORNER_1_TL"
    JOG_CORNER_2_TR = "JOG_CORNER_2_TR"
    JOG_CORNER_3_BL = "JOG_CORNER_3_BL"
    Z_TOUCH_PAPER_DRAG = "Z_TOUCH_PAPER_DRAG"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


@dataclass
class ManualJogWizard:
    """State machine guiding the user through manual tactile corner alignment."""

    bed_width_mm: float = 235.0
    bed_height_mm: float = 235.0
    current_step: WizardStep = WizardStep.INITIAL

    # Recorded corner points in bed mm
    p_tl: Point | None = None
    p_tr: Point | None = None
    p_bl: Point | None = None
    p_br: Point | None = None

    # Z calibration measurements
    z_touch_mm: float | None = None
    z_write_mm: float | None = None
    z_lift_mm: float | None = None

    history_log: list[str] = field(default_factory=list)

    def start(self) -> str:
        """Start manual calibration wizard and prompt for Corner 1 (Top-Left)."""
        self.current_step = WizardStep.JOG_CORNER_1_TL
        prompt = (
            "Step 1/4: Jog the pen tip over the Top-Left corner of the paper sheet. "
            "Confirm position when aligned."
        )
        self.history_log.append(f"START -> {self.current_step}: {prompt}")
        return prompt

    def record_corner_1_tl(self, x: float, y: float) -> str:
        """Record Top-Left corner coordinates and advance to Top-Right."""
        if self.current_step != WizardStep.JOG_CORNER_1_TL:
            msg = f"Cannot record Corner 1 in state {self.current_step}"
            raise ValueError(msg)
        self.p_tl = Point(x, y)
        self.current_step = WizardStep.JOG_CORNER_2_TR
        prompt = (
            f"Top-Left corner set at ({x:.2f}, {y:.2f}). "
            "Step 2/4: Jog pen tip over Top-Right corner of the paper sheet."
        )
        self.history_log.append(f"CORNER_1 ({x:.2f}, {y:.2f}) -> {self.current_step}")
        return prompt

    def record_corner_2_tr(self, x: float, y: float) -> str:
        """Record Top-Right corner coordinates and advance to Bottom-Left."""
        if self.current_step != WizardStep.JOG_CORNER_2_TR:
            msg = f"Cannot record Corner 2 in state {self.current_step}"
            raise ValueError(msg)
        self.p_tr = Point(x, y)
        self.current_step = WizardStep.JOG_CORNER_3_BL
        prompt = (
            f"Top-Right corner set at ({x:.2f}, {y:.2f}). "
            "Step 3/4: Jog pen tip over Bottom-Left corner of the paper sheet."
        )
        self.history_log.append(f"CORNER_2 ({x:.2f}, {y:.2f}) -> {self.current_step}")
        return prompt

    def record_corner_3_bl(self, x: float, y: float) -> str:
        """Record Bottom-Left corner, compute Bottom-Right corner, advance to Z drag check."""
        if self.current_step != WizardStep.JOG_CORNER_3_BL:
            msg = f"Cannot record Corner 3 in state {self.current_step}"
            raise ValueError(msg)
        if self.p_tl is None or self.p_tr is None:
            msg = "Missing previous corners before recording Corner 3"
            raise ValueError(msg)

        self.p_bl = Point(x, y)

        # Bottom-Right corner computed via parallelogram closure:
        # p_br = p_tr + (p_bl - p_tl)
        br_x = self.p_tr.x + (self.p_bl.x - self.p_tl.x)
        br_y = self.p_tr.y + (self.p_bl.y - self.p_tl.y)
        self.p_br = Point(br_x, br_y)

        self.current_step = WizardStep.Z_TOUCH_PAPER_DRAG
        prompt = (
            f"Bottom-Left corner set at ({x:.2f}, {y:.2f}). "
            f"Computed Bottom-Right corner at ({br_x:.2f}, {br_y:.2f}). "
            "Step 4/4: Slide a strip of paper under the pen. Slowly lower Z until slight resistance "
            "is felt (paper drag check), then confirm."
        )
        self.history_log.append(f"CORNER_3 ({x:.2f}, {y:.2f}) -> {self.current_step}")
        return prompt

    def record_z_touch_paper_drag(self, z_touch: float) -> str:
        """Record touch height and compute optimal write and lift levels."""
        if self.current_step != WizardStep.Z_TOUCH_PAPER_DRAG:
            msg = f"Cannot record Z touch in state {self.current_step}"
            raise ValueError(msg)

        self.z_touch_mm = z_touch
        # Per hardware protocol: Z_write = Z_touch - 0.4mm (compliance pre-load),
        # Z_lift = Z_touch + 3.0mm
        self.z_write_mm = round(z_touch - 0.4, 3)
        self.z_lift_mm = round(z_touch + 3.0, 3)

        self.current_step = WizardStep.COMPLETED
        prompt = (
            f"Z touch calibrated: contact at Z={z_touch:.2f} mm, "
            f"write height={self.z_write_mm:.2f} mm, lift height={self.z_lift_mm:.2f} mm. "
            "Manual calibration complete!"
        )
        self.history_log.append(f"Z_TOUCH ({z_touch:.2f}) -> {self.current_step}")
        return prompt

    def cancel(self) -> None:
        """Cancel the wizard."""
        self.current_step = WizardStep.CANCELLED
        self.history_log.append("CANCELLED")

    def get_placement(self) -> PaperBedPlacement:
        """Retrieve completed PaperBedPlacement model."""
        if (
            self.current_step != WizardStep.COMPLETED
            or self.p_tl is None
            or self.p_tr is None
            or self.p_br is None
            or self.p_bl is None
        ):
            msg = f"Cannot generate PaperBedPlacement from incomplete wizard state: {self.current_step}"
            raise ValueError(msg)

        return PaperBedPlacement(
            corners_bed_mm=(self.p_tl, self.p_tr, self.p_br, self.p_bl),
            source_mode="manual",
            confidence=1.0,
            bed_width_mm=self.bed_width_mm,
            bed_height_mm=self.bed_height_mm,
        )

    def transition_from_failed_camera(self, failure_reason: str) -> str:
        """Gracefully transition from a failed camera calibration to manual mode."""
        self.current_step = WizardStep.JOG_CORNER_1_TL
        reason_explanation = {
            "FRAME_TOO_DARK": "Camera lighting is too dark to locate paper edges.",
            "FRAME_WASHED_OUT": "Camera image is washed out by excessive glare.",
            "SEVERE_GLARE_OCCLUSION": "Glare reflection occludes paper corners.",
            "PAPER_OUT_OF_FRAME": "Paper boundary extends beyond camera frame.",
            "PAPER_NOT_FOUND": "Could not identify paper sheet boundary in camera frame.",
        }.get(failure_reason, f"Camera detection paused ({failure_reason}).")

        prompt = (
            f"{reason_explanation} Switching seamlessly to manual tactile jog alignment.\n"
            "Step 1/4: Jog the pen tip over the Top-Left corner of the paper sheet."
        )
        self.history_log.append(f"FALLBACK_FROM_CAMERA ({failure_reason}) -> {self.current_step}")
        return prompt
