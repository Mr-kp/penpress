"""Approach B: Graves RNN Handwriting Synthesizer.

Runs the PyTorch Graves LSTM-MDN neural synthesis architecture on CPU.
Generates organic cursive handwriting from text strings.
Translates neural stroke delta sequences into physical plotter mm paths.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import torch

# Ensure vendor package is in pythonpath
VENDOR_DIR = Path(__file__).resolve().parents[1] / "vendor" / "pytorch-handwriting-synthesis-toolkit"
if str(VENDOR_DIR) not in sys.path:
    sys.path.insert(0, str(VENDOR_DIR))

from handwriting_synthesis.sampling import (  # noqa: E402
    HandwritingSynthesizer as VendorSynthesizer,
)

from penpress.core.primitives import Point, Stroke  # noqa: E402

from .protocol import StyleProfile, SynthesisResult, Synthesizer  # noqa: E402


class GravesRNNSynthesizer(Synthesizer):
    """Approach B: Graves LSTM-MDN autoregressive neural handwriting synthesizer."""

    def __init__(
        self,
        checkpoint_dir: str | Path | None = None,
        bias: float = 1.2,
        device_str: str = "cpu",
    ) -> None:
        self.device = torch.device(device_str)
        if checkpoint_dir is None:
            checkpoint_dir = VENDOR_DIR / "checkpoints" / "Epoch_56"
        self.checkpoint_dir = Path(checkpoint_dir)
        self.bias = bias
        self.model_loaded = False
        self._load_model()

    def _load_model(self) -> None:
        if self.checkpoint_dir.exists():
            self.vendor_synth = VendorSynthesizer.load(str(self.checkpoint_dir), self.device, bias=self.bias)
            self.model_loaded = True

    def synthesize(
        self,
        text: str,
        profile: StyleProfile,
        font_size_mm: float = 6.0,
        start_x_mm: float = 15.0,
        start_y_mm: float = 200.0,
        line_spacing_mm: float = 8.0,
        page_width_mm: float = 148.0,
    ) -> SynthesisResult:
        t0 = time.perf_counter()
        strokes: list[Stroke] = []
        warnings: list[str] = []

        if not self.model_loaded:
            warnings.append("Graves model weights not found; returning empty strokes")
            return SynthesisResult(
                text=text,
                strokes=[],
                total_length_mm=0.0,
                pen_lifts_count=0,
                duration_ms=0.0,
                warnings=warnings,
            )

        # Split text into lines or words to fit page width
        # The neural model operates best on 5-8 words per inference call
        words = text.split(" ")
        lines: list[str] = []
        curr_line: list[str] = []
        # Rough estimate: ~7 chars per 10 mm
        max_chars_per_line = int((page_width_mm - 30.0) / 2.0)

        for w in words:
            candidate = " ".join([*curr_line, w])
            if len(candidate) > max_chars_per_line and curr_line:
                lines.append(" ".join(curr_line))
                curr_line = [w]
            else:
                curr_line.append(w)
        if curr_line:
            lines.append(" ".join(curr_line))

        curr_y = start_y_mm

        for line_text in lines:
            c = self.vendor_synth._encode_text(line_text)
            # Sample trajectory
            sampled = self.vendor_synth.model.sample_means(
                context=c, steps=self.vendor_synth.num_steps, stochastic=True
            )
            sampled = sampled.cpu()
            sampled = self.vendor_synth._undo_normalization(sampled).detach().numpy()

            # sampled array has rows: [dx, dy, p_end]
            # Convert neural deltas into points
            curr_stroke_pts: list[Point] = []
            # Scale factor: neural model typical height is ~40 units. Scale to font_size_mm
            scale = font_size_mm / 30.0

            x = start_x_mm
            y = curr_y

            for row in sampled:
                dx, dy, eos = float(row[0]), float(row[1]), float(row[2])
                x += dx * scale
                # neural model y goes downwards; our physical coordinate y goes upwards
                y -= dy * scale

                curr_stroke_pts.append(Point(x, y))

                # If eos > 0.5, pen lifts
                if eos > 0.5:
                    if len(curr_stroke_pts) >= 2:
                        strokes.append(Stroke(curr_stroke_pts))
                    curr_stroke_pts = []

            if len(curr_stroke_pts) >= 2:
                strokes.append(Stroke(curr_stroke_pts))

            curr_y -= line_spacing_mm

        t1 = time.perf_counter()
        total_len = sum(st.length_mm for st in strokes)
        pen_lifts = len(strokes)

        return SynthesisResult(
            text=text,
            strokes=strokes,
            total_length_mm=total_len,
            pen_lifts_count=pen_lifts,
            duration_ms=(t1 - t0) * 1000.0,
            warnings=warnings,
        )
