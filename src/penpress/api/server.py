"""FastAPI server and REST API for PenPress Studio."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from penpress import __version__
from penpress.api.security import PrivateHostValidationMiddleware
from penpress.ingest.engine import DocumentIngestEngine
from penpress.layout.composer import A4_PRESET, A5_PRESET, PageComposer
from penpress.machine.recovery import HardwareRecoveryEngine
from penpress.machine.state_tracker import MachineConnectionState, MachineStateTracker
from penpress.plan.profile import MachineProfile
from penpress.vision.calibrator import CameraCalibrator
from penpress.vision.manual_wizard import ManualJogWizard

WEB_DIR = Path(__file__).resolve().parents[3] / "web"

app = FastAPI(
    title="PenPress Studio API",
    version=__version__,
    docs_url="/api/docs",
    redoc_url=None,
)

# Enforce Private Tailscale / Loopback Host Header Security
app.add_middleware(PrivateHostValidationMiddleware)

# State Singletons
state_tracker = MachineStateTracker()
recovery_engine = HardwareRecoveryEngine()
manual_wizard = ManualJogWizard()
camera_calibrator = CameraCalibrator()
page_composer = PageComposer()
machine_profile = MachineProfile()


class DocumentRenderRequest(BaseModel):
    markdown_text: str = Field(..., description="Markdown document text including LaTeX equations")
    profile_name: str = Field("default", description="Handwriting profile identifier")
    paper_format: str = Field("A5", description="Paper size: A5 or A4")


class ManualJogStepRequest(BaseModel):
    x: float = Field(..., description="X coordinate in mm")
    y: float = Field(..., description="Y coordinate in mm")


class ZTouchRequest(BaseModel):
    z_touch: float = Field(..., description="Measured Z touch height in mm")


class MachineControlRequest(BaseModel):
    action: str = Field(..., description="pause | resume | cancel | emergency_stop")


@app.get("/api/health")
def get_health() -> dict[str, Any]:
    """Health check and telemetry status."""
    return {
        "status": "healthy",
        "version": __version__,
        "machine_status": state_tracker.status.value,
        "is_homed": state_tracker.is_homed,
        "pos": {
            "x": state_tracker.pos_x_mm,
            "y": state_tracker.pos_y_mm,
            "z": state_tracker.pos_z_mm,
        },
        "lines_sent": state_tracker.lines_sent,
        "lines_acknowledged": state_tracker.lines_acknowledged,
    }


@app.get("/api/telemetry")
def get_telemetry() -> dict[str, Any]:
    """Real-time printing telemetry."""
    return {
        "status": state_tracker.status.value,
        "port": state_tracker.port,
        "baudrate": state_tracker.baudrate,
        "pos_x_mm": state_tracker.pos_x_mm,
        "pos_y_mm": state_tracker.pos_y_mm,
        "pos_z_mm": state_tracker.pos_z_mm,
        "feedrate_mm_min": state_tracker.feedrate_mm_min,
        "is_homed": state_tracker.is_homed,
        "current_stroke_id": state_tracker.current_stroke_id,
        "total_strokes": state_tracker.total_strokes,
        "progress_percent": round(state_tracker.progress_pct, 1),
        "buffer_depth": state_tracker.buffer_depth,
        "errors": state_tracker.errors[-5:],
        "warnings": state_tracker.warnings[-5:],
    }


@app.post("/api/machine/control")
def control_machine(req: MachineControlRequest) -> dict[str, str]:
    """Machine pause, resume, cancel control."""
    if req.action == "pause":
        state_tracker.status = MachineConnectionState.PAUSED
        return {"action": "pause", "status": state_tracker.status.value}
    elif req.action == "resume":
        state_tracker.status = MachineConnectionState.PRINTING
        return {"action": "resume", "status": state_tracker.status.value}
    elif req.action in ("cancel", "emergency_stop"):
        state_tracker.status = MachineConnectionState.IDLE
        return {"action": req.action, "status": state_tracker.status.value}
    raise HTTPException(status_code=400, detail=f"Unknown action: {req.action}")


@app.post("/api/document/compose")
def compose_document(req: DocumentRenderRequest) -> dict[str, Any]:
    """Parse Markdown and generate composed pages."""
    try:
        engine = DocumentIngestEngine()
        ingested_doc = engine.md_parser.parse_markdown(req.markdown_text, doc_id="preview")
        composer = PageComposer(paper=A5_PRESET if req.paper_format == "A5" else A4_PRESET)
        res = composer.compose_document(ingested_doc)
        total_strokes = sum(sum(len(p.strokes) for p in page.paths) for page in res.pages)
        return {
            "success": True,
            "page_count": len(res.pages),
            "total_strokes": total_strokes,
            "pages": [
                {
                    "page_number": idx + 1,
                    "stroke_count": sum(len(p.strokes) for p in page.paths),
                    "width_mm": page.width_mm,
                    "height_mm": page.height_mm,
                }
                for idx, page in enumerate(res.pages)
            ],
        }
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/calibration/manual/start")
def start_manual_calibration() -> dict[str, Any]:
    """Start manual tactile jog wizard."""
    prompt = manual_wizard.start()
    return {"step": manual_wizard.current_step.value, "prompt": prompt}


@app.post("/api/calibration/manual/corner-1")
def record_corner_1(req: ManualJogStepRequest) -> dict[str, Any]:
    """Record Corner 1 (Top-Left)."""
    try:
        prompt = manual_wizard.record_corner_1_tl(req.x, req.y)
        return {"step": manual_wizard.current_step.value, "prompt": prompt}
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/calibration/manual/corner-2")
def record_corner_2(req: ManualJogStepRequest) -> dict[str, Any]:
    """Record Corner 2 (Top-Right)."""
    try:
        prompt = manual_wizard.record_corner_2_tr(req.x, req.y)
        return {"step": manual_wizard.current_step.value, "prompt": prompt}
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/calibration/manual/corner-3")
def record_corner_3(req: ManualJogStepRequest) -> dict[str, Any]:
    """Record Corner 3 (Bottom-Left) and compute Bottom-Right."""
    try:
        prompt = manual_wizard.record_corner_3_bl(req.x, req.y)
        return {"step": manual_wizard.current_step.value, "prompt": prompt}
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/calibration/manual/z-touch")
def record_z_touch(req: ZTouchRequest) -> dict[str, Any]:
    """Record Z contact height from paper drag test."""
    try:
        prompt = manual_wizard.record_z_touch_paper_drag(req.z_touch)
        placement = manual_wizard.get_placement()
        return {
            "step": manual_wizard.current_step.value,
            "prompt": prompt,
            "z_touch_mm": manual_wizard.z_touch_mm,
            "z_write_mm": manual_wizard.z_write_mm,
            "z_lift_mm": manual_wizard.z_lift_mm,
            "paper_width_mm": round(placement.width_mm, 2),
            "paper_height_mm": round(placement.height_mm, 2),
        }
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/settings")
def get_settings() -> dict[str, Any]:
    """Get machine profile and safety configuration."""
    return {
        "bed_size_x_mm": machine_profile.bed_width_mm,
        "bed_size_y_mm": machine_profile.bed_height_mm,
        "max_feedrate_xy_mm_min": machine_profile.travel_feedrate_mm_min,
        "z_write_mm": machine_profile.z_write_mm,
        "z_lift_mm": machine_profile.z_lift_mm,
        "z_write_min_mm": machine_profile.z_write_min_mm,
    }


# Mount Static Frontend Files
if (WEB_DIR / "static").exists():
    app.mount("/static", StaticFiles(directory=str(WEB_DIR / "static")), name="static")


@app.get("/")
def get_index() -> HTMLResponse:
    """Serve PenPress Studio unified single-page application."""
    index_file = WEB_DIR / "index.html"
    if index_file.exists():
        return HTMLResponse(content=index_file.read_text(encoding="utf-8"))
    return HTMLResponse("<h1>PenPress Studio</h1><p>Frontend loading...</p>")


def run_server(host: str = "127.0.0.1", port: int = 8080) -> None:
    """Launch the PenPress Studio web server and API daemon."""
    uvicorn.run(app, host=host, port=port, log_level="info")
