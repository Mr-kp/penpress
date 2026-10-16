"""Unit and security tests for FastAPI server and REST endpoints (P9-1).

Tests:
1. Rejection of untrusted / public Host headers (HTTP 403 Forbidden).
2. Acceptance of private loopback (127.0.0.1, localhost) and
   Tailscale CGNAT hostnames (*.ts.net, 100.121.213.19).
3. Defensive security headers (X-Frame-Options, X-Content-Type-Options, CSP, Referrer-Policy).
4. Health telemetry endpoint returns machine status and coordinates.
5. Telemetry polling endpoint returns buffer depth, progress, and kinematic coordinates.
6. Machine control endpoint handles pause, resume, and cancel actions.
7. Document composition endpoint processes Markdown text into composed pages.
8. Manual calibration endpoints advance state machine through corner alignment.
9. Static frontend assets and index HTML are served properly.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from penpress import __version__
from penpress.api.server import app

client = TestClient(app)


def test_private_host_validation_rejection_of_untrusted_public_hosts() -> None:
    untrusted_hosts = [
        "87.106.42.187",
        "87.106.42.187:8000",
        "evil-attacker.com",
        "malicious.org:8080",
        "192.168.1.100",
    ]

    for host in untrusted_hosts:
        response = client.get("/api/health", headers={"Host": host})
        assert response.status_code == 403
        data = response.json()
        assert "Forbidden" in data["error"]
        assert "Rule 1" in data["detail"]


def test_private_host_validation_acceptance_of_tailscale_and_loopback() -> None:
    allowed_hosts = [
        "127.0.0.1",
        "127.0.0.1:8000",
        "localhost",
        "localhost:5173",
        "100.121.213.19",
        "100.121.213.19:8000",
        "ubuntu.tailscale.ts.net",
        "my-laptop.ts.net:8080",
        "ubuntu",
    ]

    for host in allowed_hosts:
        response = client.get("/api/health", headers={"Host": host})
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"


def test_defensive_security_headers_present() -> None:
    response = client.get("/api/health", headers={"Host": "127.0.0.1"})
    assert response.status_code == 200

    headers = response.headers
    assert headers["x-content-type-options"] == "nosniff"
    assert headers["x-frame-options"] == "DENY"
    assert headers["referrer-policy"] == "no-referrer"
    assert "default-src 'self'" in headers["content-security-policy"]


def test_telemetry_and_health_endpoints() -> None:
    resp_health = client.get("/api/health", headers={"Host": "localhost"})
    assert resp_health.status_code == 200
    health_data = resp_health.json()
    assert health_data["version"] == __version__
    assert "pos" in health_data

    resp_tel = client.get("/api/telemetry", headers={"Host": "localhost"})
    assert resp_tel.status_code == 200
    tel_data = resp_tel.json()
    assert "feedrate_mm_min" in tel_data
    assert "buffer_depth" in tel_data
    assert "progress_percent" in tel_data


def test_machine_control_actions() -> None:
    # Pause
    resp_pause = client.post(
        "/api/machine/control",
        json={"action": "pause"},
        headers={"Host": "localhost"},
    )
    assert resp_pause.status_code == 200
    assert resp_pause.json()["status"] == "PAUSED"

    # Resume
    resp_resume = client.post(
        "/api/machine/control",
        json={"action": "resume"},
        headers={"Host": "localhost"},
    )
    assert resp_resume.status_code == 200
    assert resp_resume.json()["status"] == "PRINTING"

    # Cancel
    resp_cancel = client.post(
        "/api/machine/control",
        json={"action": "cancel"},
        headers={"Host": "localhost"},
    )
    assert resp_cancel.status_code == 200
    assert resp_cancel.json()["status"] == "IDLE"


def test_document_composition_endpoint() -> None:
    req_payload = {
        "markdown_text": "# Physics\n\nLinear momentum is conserved in isolated systems.",
        "profile_name": "default",
        "paper_format": "A5",
    }
    resp = client.post(
        "/api/document/compose",
        json=req_payload,
        headers={"Host": "localhost"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert data["page_count"] >= 1
    assert data["total_strokes"] > 0


def test_manual_calibration_wizard_flow() -> None:
    # Start
    resp_start = client.post("/api/calibration/manual/start", headers={"Host": "localhost"})
    assert resp_start.status_code == 200
    assert resp_start.json()["step"] == "JOG_CORNER_1_TL"

    # Corner 1 TL
    resp_c1 = client.post(
        "/api/calibration/manual/corner-1",
        json={"x": 43.5, "y": 222.5},
        headers={"Host": "localhost"},
    )
    assert resp_c1.status_code == 200
    assert resp_c1.json()["step"] == "JOG_CORNER_2_TR"

    # Corner 2 TR
    resp_c2 = client.post(
        "/api/calibration/manual/corner-2",
        json={"x": 191.5, "y": 222.5},
        headers={"Host": "localhost"},
    )
    assert resp_c2.status_code == 200
    assert resp_c2.json()["step"] == "JOG_CORNER_3_BL"

    # Corner 3 BL
    resp_c3 = client.post(
        "/api/calibration/manual/corner-3",
        json={"x": 43.5, "y": 12.5},
        headers={"Host": "localhost"},
    )
    assert resp_c3.status_code == 200
    assert resp_c3.json()["step"] == "Z_TOUCH_PAPER_DRAG"

    # Z Touch
    resp_z = client.post(
        "/api/calibration/manual/z-touch",
        json={"z_touch": 0.85},
        headers={"Host": "localhost"},
    )
    assert resp_z.status_code == 200
    data_z = resp_z.json()
    assert data_z["step"] == "COMPLETED"
    assert data_z["z_write_mm"] == 0.45
    assert data_z["z_lift_mm"] == 3.85
    assert data_z["paper_width_mm"] == 148.0


def test_index_and_settings_endpoints() -> None:
    resp_index = client.get("/", headers={"Host": "localhost"})
    assert resp_index.status_code == 200
    assert "PenPress Studio" in resp_index.text

    resp_settings = client.get("/api/settings", headers={"Host": "localhost"})
    assert resp_settings.status_code == 200
    settings = resp_settings.json()
    assert settings["bed_size_x_mm"] == 235.0
    assert settings["bed_size_y_mm"] == 235.0


def test_spool_jobs_endpoints(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Test listing and ingesting CUPS spooled jobs."""
    monkeypatch.setenv("PENPRESS_SPOOL_DIR", str(tmp_path))

    # Empty initially
    resp_empty = client.get("/api/jobs", headers={"Host": "localhost"})
    assert resp_empty.status_code == 200
    assert resp_empty.json()["count"] == 0

    # Create synthetic job
    meta_file = tmp_path / "101_assignment.meta"
    data_file = tmp_path / "101_assignment.dat"
    meta_file.write_text("job_id=101\ntitle=assignment\nuser=alice\nstatus=enqueued\n", encoding="utf-8")
    data_file.write_bytes(b"%PDF-1.4\n...")

    # Now listed
    resp_listed = client.get("/api/jobs", headers={"Host": "localhost"})
    assert resp_listed.status_code == 200
    assert resp_listed.json()["count"] == 1
    assert resp_listed.json()["jobs"][0]["job_id"] == "101"

    # Process job
    resp_proc = client.post("/api/jobs/101/process", headers={"Host": "localhost"})
    assert resp_proc.status_code == 200
    assert resp_proc.json()["status"] == "ready"
    assert resp_proc.json()["size_bytes"] == len(b"%PDF-1.4\n...")

    # Not found negative test
    resp_404 = client.post("/api/jobs/999/process", headers={"Host": "localhost"})
    assert resp_404.status_code == 404


def test_document_upload_endpoint() -> None:
    md_content = b"# Calculus\n\n$$\\int_0^1 x dx = \\frac{1}{2}$$\n"
    files = {"file": ("calc.md", md_content, "text/markdown")}
    resp = client.post("/api/document/upload", files=files, headers={"Host": "localhost"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert data["page_count"] >= 1
    assert data["total_strokes"] > 0
    assert "gcode" in data
    assert "sim_segments" in data
    assert "telemetry" in data


def test_document_upload_negative_oversize() -> None:
    fake_huge = b"A" * (50 * 1024 * 1024 + 10)
    files = {"file": ("huge.pdf", fake_huge, "application/pdf")}
    resp = client.post("/api/document/upload", files=files, headers={"Host": "localhost"})
    assert resp.status_code == 413
    assert "exceeds" in resp.json()["detail"]


def test_document_upload_negative_bad_format() -> None:
    files = {"file": ("malicious.exe", b"\x4d\x5a", "application/octet-stream")}
    resp = client.post("/api/document/upload", files=files, headers={"Host": "localhost"})
    assert resp.status_code == 400
    assert "Unsupported" in resp.json()["detail"]


def test_profile_glyph_and_sample_sheet() -> None:
    # 1. Add glyph
    glyph_payload = {
        "char": "A",
        "strokes": [
            [[10.0, 5.0], [15.0, 25.0]],
            [[15.0, 25.0], [20.0, 5.0]],
            [[12.0, 15.0], [18.0, 15.0]],
        ],
    }
    resp = client.post("/api/profile/glyph", json=glyph_payload, headers={"Host": "localhost"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert data["char"] == "A"
    assert "glyph_quality" in data
    assert "profile_report" in data
    assert "A" in data["captured_glyphs"]

    # 2. Get sample sheet PDF
    resp_pdf = client.get("/api/profile/sample-sheet.pdf", headers={"Host": "localhost"})
    assert resp_pdf.status_code == 200
    assert resp_pdf.headers["content-type"] == "application/pdf"
    assert resp_pdf.content.startswith(b"%PDF")


def test_camera_calibration_endpoint() -> None:
    resp = client.post("/api/calibration/camera", headers={"Host": "localhost"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["valid"] is True
    assert len(data["paper_corners"]) == 4
    assert len(data["clip_keepouts"]) > 0


def test_update_settings_endpoint() -> None:
    update_payload = {
        "bed_size_x_mm": 220.0,
        "bed_size_y_mm": 220.0,
        "max_feedrate_xy_mm_min": 7500.0,
        "z_write_mm": 0.4,
        "z_lift_mm": 4.0,
        "z_write_min_mm": 0.1,
    }
    resp = client.post("/api/settings", json=update_payload, headers={"Host": "localhost"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert data["settings"]["max_feedrate_xy_mm_min"] == 7500.0
    assert data["settings"]["z_write_mm"] == 0.4
