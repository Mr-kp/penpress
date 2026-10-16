"""FastAPI server and REST API for PenPress Studio."""

from __future__ import annotations

import math
import os
import sys
import tempfile
from pathlib import Path
from typing import Any

import cv2
import uvicorn
from fastapi import FastAPI, File, HTTPException, Response, UploadFile
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from penpress import __version__
from penpress.api.security import PrivateHostValidationMiddleware
from penpress.core.math_engine import MathEngine
from penpress.core.primitives import Page, Point, Stroke
from penpress.ingest.engine import DocumentIngestEngine
from penpress.layout.composer import A4_PRESET, A5_PRESET, PageComposer
from penpress.machine.recovery import HardwareRecoveryEngine
from penpress.machine.state_tracker import MachineConnectionState, MachineStateTracker
from penpress.plan.compiler import GcodeCompiler
from penpress.plan.optimizer import ToolpathOptimizer
from penpress.plan.profile import MachineProfile
from penpress.plan.sim import MarlinSimulator
from penpress.profile.models import HandwritingProfile
from penpress.profile.quality import audit_profile_quality, evaluate_glyph_quality
from penpress.profile.sheet_gen import generate_sample_sheet
from penpress.synth.humanizer import HumanizerParams, OrganicHumanizer
from penpress.vision.calibrator import CameraCalibrator
from penpress.vision.manual_wizard import ManualJogWizard

# Maximum upload size: 50 MB
MAX_UPLOAD_SIZE_BYTES = 50 * 1024 * 1024

# Locate web directory with PyInstaller bundle support
_bundle_dir = getattr(sys, "_MEIPASS", None)
WEB_DIR = Path(_bundle_dir) / "web" if _bundle_dir else Path(__file__).resolve().parents[3] / "web"

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
page_composer = PageComposer(autoscale_figures=True)
machine_profile = MachineProfile()
active_profile = HandwritingProfile(
    profile_id="default",
    user_name="Student",
    created_at="2026-10-16T00:00:00Z",
)


class DocumentRenderRequest(BaseModel):
    markdown_text: str = Field(..., description="Markdown document text including LaTeX equations")
    profile_name: str = Field("default", description="Handwriting profile identifier")
    paper_format: str = Field("A5", description="Paper size: A5 or A4")
    baseline_wander_mm: float = Field(0.06, description="Baseline organic jitter in mm")
    slant_deg: float = Field(0.0, description="Organic slant drift in degrees")
    spacing_jitter_mm: float = Field(0.15, description="Inter-character spacing jitter in mm")
    wobble_mm: float = Field(0.05, description="Micro stroke wobble in mm")
    optimize: bool = Field(True, description="Enable TSP 2-opt path optimization")


class GlyphDrawRequest(BaseModel):
    char: str = Field(..., min_length=1, max_length=5, description="Character symbol, e.g. 'A', 'a', '0'")
    strokes: list[list[list[float]]] = Field(
        ..., description="List of strokes, each a list of [x, y] coordinates in mm"
    )


class SettingsUpdateRequest(BaseModel):
    bed_size_x_mm: float = Field(235.0, ge=100.0, le=500.0)
    bed_size_y_mm: float = Field(235.0, ge=100.0, le=500.0)
    max_feedrate_xy_mm_min: float = Field(6000.0, ge=500.0, le=20000.0)
    z_write_mm: float = Field(0.5, ge=0.01, le=10.0)
    z_lift_mm: float = Field(3.5, ge=0.5, le=20.0)
    z_write_min_mm: float = Field(0.1, ge=0.01, le=5.0)


class ManualJogStepRequest(BaseModel):
    x: float = Field(..., description="X coordinate in mm")
    y: float = Field(..., description="Y coordinate in mm")


class ZTouchRequest(BaseModel):
    z_touch: float = Field(..., description="Measured Z touch height in mm")


class MachineControlRequest(BaseModel):
    action: str = Field(..., description="pause | resume | cancel | emergency_stop")


def _render_ingested_to_payload(
    ingested_doc: Any,
    paper_format: str = "A5",
    baseline_wander_mm: float = 0.06,
    slant_deg: float = 0.0,
    spacing_jitter_mm: float = 0.15,
    wobble_mm: float = 0.05,
    optimize: bool = True,
) -> dict[str, Any]:
    """Execute page composition, path optimization, and Marlin simulation."""
    paper_preset = A5_PRESET if paper_format.upper() == "A5" else A4_PRESET
    humanizer_params = HumanizerParams(
        baseline_jitter_sigma_mm=baseline_wander_mm,
        slant_deg_mean=slant_deg,
        spacing_jitter_sigma_mm=spacing_jitter_mm,
        wobble_amplitude_mm=wobble_mm,
        baseline_wander_amplitude_mm=baseline_wander_mm,
    )
    humanizer = OrganicHumanizer(params=humanizer_params)
    math_engine = MathEngine(user_profile=active_profile)
    composer = PageComposer(
        paper=paper_preset,
        humanizer=humanizer,
        math_engine=math_engine,
        autoscale_figures=True,
    )
    res = composer.compose_document(ingested_doc)
    pages = list(res.pages)
    if not pages:
        pages = [Page(width_mm=paper_preset.width_mm, height_mm=paper_preset.height_mm, paths=())]

    if optimize:
        opt = ToolpathOptimizer()
        pages = [opt.optimize_page(p)[0] for p in pages]

    compiler = GcodeCompiler(profile=machine_profile, emit_line_numbers=True)
    primary_page = pages[0]
    gcode_str = compiler.compile(primary_page)
    gcode_lines = [line.strip() for line in gcode_str.splitlines() if line.strip()]

    sim = MarlinSimulator(profile=machine_profile, strict_safety=True)
    sim.execute_stream(gcode_lines)

    doc_blocks: list[dict[str, Any]] = []
    for p in ingested_doc.pages:
        for b in p.blocks:
            doc_blocks.append(
                {
                    "block_id": b.block_id,
                    "block_type": b.block_type.value,
                    "text": b.text[:120],
                    "latex": b.latex,
                }
            )

    total_strokes = sum(sum(len(path.strokes) for path in page.paths) for page in pages)
    total_draw_mm = sum(sum(s.length_mm for path in page.paths for s in path.strokes) for page in pages)
    total_travel_mm = sum(
        math.hypot(s.end_x - s.start_x, s.end_y - s.start_y) for s in sim.segments if not s.pen_contact
    )

    pages_payload = []
    for idx, page in enumerate(pages):
        page_polys = []
        for path in page.paths:
            for stroke in path.strokes:
                page_polys.append([[round(pt.x, 2), round(pt.y, 2)] for pt in stroke.points])
        pages_payload.append(
            {
                "page_number": idx + 1,
                "stroke_count": sum(len(p.strokes) for p in page.paths),
                "width_mm": page.width_mm,
                "height_mm": page.height_mm,
                "strokes": page_polys,
            }
        )

    sim_segments_payload = [
        {
            "start_x": round(s.start_x, 2),
            "start_y": round(s.start_y, 2),
            "start_z": round(s.start_z, 2),
            "end_x": round(s.end_x, 2),
            "end_y": round(s.end_y, 2),
            "end_z": round(s.end_z, 2),
            "feedrate": s.feedrate_mm_min,
            "pen_contact": s.pen_contact,
            "command": s.command,
            "duration_s": round(s.duration_s, 3),
        }
        for s in sim.segments[:2000]
    ]

    return {
        "success": True,
        "page_count": len(pages),
        "total_strokes": total_strokes,
        "telemetry": {
            "total_strokes": total_strokes,
            "pen_lifts": total_strokes,
            "draw_distance_mm": round(total_draw_mm, 1),
            "travel_distance_mm": round(total_travel_mm, 1),
            "estimated_duration_s": round(sim.state.total_time_seconds, 1),
        },
        "blocks": doc_blocks,
        "pages": pages_payload,
        "gcode": gcode_str,
        "gcode_preview_lines": gcode_lines[:100],
        "sim_segments": sim_segments_payload,
    }


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
    """Parse Markdown and LaTeX into composed pages, toolpaths, and simulation."""
    try:
        engine = DocumentIngestEngine()
        ingested_doc = engine.md_parser.parse_markdown(req.markdown_text, doc_id="preview")
        return _render_ingested_to_payload(
            ingested_doc=ingested_doc,
            paper_format=req.paper_format,
            baseline_wander_mm=req.baseline_wander_mm,
            slant_deg=req.slant_deg,
            spacing_jitter_mm=req.spacing_jitter_mm,
            wobble_mm=req.wobble_mm,
            optimize=req.optimize,
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/document/upload")
async def upload_document(
    file: UploadFile = File(...),  # noqa: B008
    paper_format: str = "A5",
) -> dict[str, Any]:
    """Upload PDF or Markdown assignment file and run full composition pipeline."""
    filename = file.filename or "upload.pdf"
    suffix = Path(filename).suffix.lower()

    if suffix not in (".pdf", ".md", ".markdown", ".txt"):
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported document format: {suffix}. Allowed: .pdf, .md, .txt",
        )

    content = await file.read()
    if len(content) > MAX_UPLOAD_SIZE_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"File size ({len(content)} bytes) exceeds maximum limit ({MAX_UPLOAD_SIZE_BYTES} bytes)",
        )

    # Save to temporary file for ingestion
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tf:
        tmp_file = Path(tf.name)
        tmp_file.write_bytes(content)

    try:
        engine = DocumentIngestEngine()
        if suffix == ".txt":
            text = tmp_file.read_text(encoding="utf-8")
            ingested_doc = engine.md_parser.parse_markdown(text, doc_id=tmp_file.stem)
        else:
            ingested_doc = engine.ingest_document(tmp_file)

        return _render_ingested_to_payload(
            ingested_doc=ingested_doc,
            paper_format=paper_format,
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Error parsing document: {exc}") from exc
    finally:
        if tmp_file.exists():
            tmp_file.unlink()


@app.post("/api/profile/glyph")
def record_profile_glyph(req: GlyphDrawRequest) -> dict[str, Any]:
    """Record online handwriting stroke variant for a character in the active profile bank."""
    if not req.char or not req.strokes:
        raise HTTPException(status_code=400, detail="Character and strokes are required")

    stroke_objs: list[Stroke] = []
    for s_pts in req.strokes:
        if len(s_pts) >= 2:
            pts = [Point(x=float(p[0]), y=float(p[1])) for p in s_pts]
            stroke_objs.append(Stroke(pts))

    if not stroke_objs:
        raise HTTPException(
            status_code=400,
            detail="At least one valid stroke with >= 2 points is required",
        )

    if req.char not in active_profile.glyph_bank:
        active_profile.glyph_bank[req.char] = []
    active_profile.glyph_bank[req.char].append(stroke_objs)

    report = audit_profile_quality(active_profile)
    glyph_score = evaluate_glyph_quality(req.char, active_profile.glyph_bank[req.char])

    return {
        "success": True,
        "char": req.char,
        "glyph_quality": {
            "smoothness_score": round(glyph_score.smoothness_score, 3),
            "is_valid": glyph_score.is_valid,
            "variant_count": glyph_score.variant_count,
        },
        "profile_report": report.to_dict(),
        "captured_glyphs": sorted(active_profile.glyph_bank.keys()),
    }


@app.get("/api/profile/sample-sheet.pdf")
def get_sample_sheet_pdf() -> Response:
    """Generate and return printable A4 handwriting calibration sheet PDF."""
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tf:
        tmp_path = Path(tf.name)

    try:
        generate_sample_sheet(tmp_path)
        pdf_bytes = tmp_path.read_bytes()
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": 'attachment; filename="penpress_calibration_sheet.pdf"'},
        )
    finally:
        if tmp_path.exists():
            tmp_path.unlink()


@app.post("/api/calibration/camera")
def run_camera_calibration() -> dict[str, Any]:
    """Execute camera vision homography detection for paper quad and binder clip keepouts."""
    candidate_fixtures = [
        Path("tests/fixtures/bed_scene_topdown_bright.png"),
        Path("research/R0-1/fixtures/bed_scenes/bed_scene_topdown_bright.png"),
    ]
    scene_file = next((f for f in candidate_fixtures if f.is_file()), None)

    if scene_file is None:
        raise HTTPException(status_code=404, detail="Bed calibration scene fixture not found")

    image = cv2.imread(str(scene_file))
    if image is None:
        raise HTTPException(status_code=500, detail="Failed to load calibration camera frame")

    cal_res = camera_calibrator.calibrate(image)

    paper_corners: list[dict[str, Any]] = []
    skew_angle = 0.0
    w_mm = 148.0
    h_mm = 210.0
    if cal_res.placement is not None:
        p = cal_res.placement
        paper_corners = [
            {"name": "TL", "x": round(p.top_left.x, 2), "y": round(p.top_left.y, 2)},
            {"name": "TR", "x": round(p.top_right.x, 2), "y": round(p.top_right.y, 2)},
            {"name": "BR", "x": round(p.bottom_right.x, 2), "y": round(p.bottom_right.y, 2)},
            {"name": "BL", "x": round(p.bottom_left.x, 2), "y": round(p.bottom_left.y, 2)},
        ]
        skew_angle = round(math.degrees(p.rotation_rad), 2)
        w_mm = round(p.width_mm, 1)
        h_mm = round(p.height_mm, 1)

    clip_keepouts = []
    for poly in cal_res.clip_polygons_bed_mm:
        clip_keepouts.append([[round(p.x, 2), round(p.y, 2)] for p in poly])

    return {
        "valid": bool(cal_res.valid),
        "detection_confidence": round(float(cal_res.confidence), 2),
        "paper_corners": paper_corners,
        "skew_angle_deg": skew_angle,
        "paper_width_mm": w_mm,
        "paper_height_mm": h_mm,
        "clip_keepouts": clip_keepouts,
    }


@app.get("/api/jobs")
def list_spool_jobs() -> dict[str, Any]:
    """List spooled print jobs waiting in the spool directory."""
    spool_override = os.environ.get("PENPRESS_SPOOL_DIR")
    if spool_override:
        spool_dir = Path(spool_override)
    else:
        try:
            spool_dir = Path.home() / ".penpress" / "spool"
        except Exception:
            spool_dir = Path("/tmp") / ".penpress" / "spool"

    jobs: list[dict[str, str]] = []
    if spool_dir.exists():
        for meta_file in sorted(spool_dir.glob("*.meta")):
            job_info: dict[str, str] = {}
            for line in meta_file.read_text(encoding="utf-8").splitlines():
                if "=" in line:
                    k, v = line.split("=", 1)
                    job_info[k.strip()] = v.strip()
            if job_info:
                jobs.append(job_info)

    return {"count": len(jobs), "jobs": jobs}


@app.post("/api/jobs/{job_id}/process")
def process_spool_job(job_id: str) -> dict[str, Any]:
    """Ingest and prepare a spooled print job."""
    spool_override = os.environ.get("PENPRESS_SPOOL_DIR")
    if spool_override:
        spool_dir = Path(spool_override)
    else:
        try:
            spool_dir = Path.home() / ".penpress" / "spool"
        except Exception:
            spool_dir = Path("/tmp") / ".penpress" / "spool"

    matching_meta = list(spool_dir.glob(f"{job_id}_*.meta"))
    if not matching_meta:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found in spool directory")

    meta_file = matching_meta[0]
    data_file = meta_file.with_suffix(".dat")
    if not data_file.exists():
        raise HTTPException(status_code=404, detail=f"Data for job {job_id} not found")

    return {
        "job_id": job_id,
        "status": "ready",
        "data_file": str(data_file),
        "size_bytes": data_file.stat().st_size,
    }


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


@app.post("/api/settings")
def update_settings(req: SettingsUpdateRequest) -> dict[str, Any]:
    """Update machine profile and safety configuration."""
    global machine_profile  # noqa: PLW0603
    machine_profile = MachineProfile(
        bed_width_mm=req.bed_size_x_mm,
        bed_height_mm=req.bed_size_y_mm,
        travel_feedrate_mm_min=req.max_feedrate_xy_mm_min,
        z_write_mm=req.z_write_mm,
        z_lift_mm=req.z_lift_mm,
        z_write_min_mm=req.z_write_min_mm,
    )
    return {
        "success": True,
        "settings": {
            "bed_size_x_mm": machine_profile.bed_width_mm,
            "bed_size_y_mm": machine_profile.bed_height_mm,
            "max_feedrate_xy_mm_min": machine_profile.travel_feedrate_mm_min,
            "z_write_mm": machine_profile.z_write_mm,
            "z_lift_mm": machine_profile.z_lift_mm,
            "z_write_min_mm": machine_profile.z_write_min_mm,
        },
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
