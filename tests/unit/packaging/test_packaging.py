"""Unit tests for packaging assets, CUPS virtual print driver, and desktop integrations."""

from __future__ import annotations

import hashlib
import os
import subprocess
import sys
from pathlib import Path

from penpress import __version__

ROOT = Path(__file__).resolve().parents[3]
CUPS_BACKEND = ROOT / "packaging" / "cups" / "penpress-print"
DESKTOP_ENTRY = ROOT / "packaging" / "desktop" / "penpress.desktop"
PLIST_FILE = ROOT / "packaging" / "desktop" / "Info.plist"
SYSTEMD_SERVICE = ROOT / "packaging" / "systemd" / "penpress.service"
RELEASE_MANIFEST = ROOT / "release" / "MANIFEST.md"
CHECKSUM_FILE = ROOT / "release" / "checksums.sha256"


def test_package_version_is_v010() -> None:
    """Verify package version is 0.1.0."""
    assert __version__ == "0.1.0"


def test_cups_discovery_mode() -> None:
    """Verify CUPS backend discovery output when called without arguments."""
    res = subprocess.run(
        [sys.executable, str(CUPS_BACKEND)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert res.returncode == 0
    assert "direct penpress-print" in res.stdout
    assert "PenPress Virtual Plotter" in res.stdout
    assert "Ender3Pro" in res.stdout


def test_cups_spool_job_from_stdin(tmp_path: Path) -> None:
    """Verify print job spooling from standard input stream."""
    sample_pdf_payload = b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog >>\nendobj\n%%EOF\n"
    env = {**os.environ, "PENPRESS_SPOOL_DIR": str(tmp_path)}

    cmd = [
        sys.executable,
        str(CUPS_BACKEND),
        "101",
        "student",
        "Assignment_Math.pdf",
        "1",
        "options=default",
    ]
    res = subprocess.run(
        cmd,
        input=sample_pdf_payload,
        capture_output=True,
        env=env,
        check=False,
    )
    assert res.returncode == 0
    assert "spooled job 101" in res.stderr.decode("utf-8")

    data_file = tmp_path / "101_Assignment_Math.pdf.dat"
    meta_file = tmp_path / "101_Assignment_Math.pdf.meta"

    assert data_file.is_file()
    assert data_file.read_bytes() == sample_pdf_payload
    assert meta_file.is_file()
    meta_text = meta_file.read_text(encoding="utf-8")
    assert "job_id=101" in meta_text
    assert "status=enqueued" in meta_text
    assert f"bytes={len(sample_pdf_payload)}" in meta_text


def test_cups_spool_job_from_file(tmp_path: Path) -> None:
    """Verify print job spooling from input file argument."""
    spool_dir = tmp_path / "spool"
    input_file = tmp_path / "input.ps"
    input_file.write_bytes(b"%!PS-Adobe-3.0\n%%Title: Test Page\nshowpage\n")

    env = {**os.environ, "PENPRESS_SPOOL_DIR": str(spool_dir)}
    cmd = [
        sys.executable,
        str(CUPS_BACKEND),
        "102",
        "student",
        "TestPage",
        "1",
        "options=draft",
        str(input_file),
    ]
    res = subprocess.run(cmd, capture_output=True, env=env, check=False)
    assert res.returncode == 0
    assert "spooled job 102" in res.stderr.decode("utf-8")

    data_file = spool_dir / "102_TestPage.dat"
    assert data_file.is_file()
    assert data_file.read_bytes() == input_file.read_bytes()


def test_cups_rejects_oversized_job(tmp_path: Path) -> None:
    """Negative test: Job stream exceeding 50 MB is rejected with spooler error."""
    spool_dir = tmp_path / "spool"
    env = {**os.environ, "PENPRESS_SPOOL_DIR": str(spool_dir)}

    # Simulate streaming an oversized job directly via stdin
    oversized_file = tmp_path / "large_job.dat"
    # Create sparse file that reports 51 MB
    with oversized_file.open("wb") as f:
        f.seek(51 * 1024 * 1024)
        f.write(b"X")

    cmd = [
        sys.executable,
        str(CUPS_BACKEND),
        "999",
        "student",
        "MassiveBook",
        "1",
        "options=default",
        str(oversized_file),
    ]
    res = subprocess.run(cmd, capture_output=True, env=env, check=False)
    assert res.returncode == 1
    assert "ERROR: Print job exceeds maximum limit of 50 MB" in res.stderr.decode("utf-8")
    assert not (spool_dir / "999_MassiveBook.dat").exists()


def test_desktop_entry_syntax() -> None:
    """Verify Linux XDG desktop entry syntax and fields."""
    assert DESKTOP_ENTRY.is_file()
    content = DESKTOP_ENTRY.read_text(encoding="utf-8")
    assert "[Desktop Entry]" in content
    assert "Name=PenPress" in content
    assert "Exec=penpress serve" in content
    assert "Icon=penpress" in content
    assert "Categories=" in content


def test_macos_plist_syntax() -> None:
    """Verify macOS Info.plist structure and version strings."""
    assert PLIST_FILE.is_file()
    content = PLIST_FILE.read_text(encoding="utf-8")
    assert "<key>CFBundleDisplayName</key>" in content
    assert "<string>PenPress</string>" in content
    assert "<key>CFBundleShortVersionString</key>" in content
    assert "<string>0.1.0</string>" in content


def test_systemd_service_syntax() -> None:
    """Verify systemd service unit structure and security hardening."""
    assert SYSTEMD_SERVICE.is_file()
    content = SYSTEMD_SERVICE.read_text(encoding="utf-8")
    assert "[Unit]" in content
    assert "[Service]" in content
    assert "ExecStart=" in content
    assert "penpress serve" in content
    assert "ProtectSystem=strict" in content
    assert "PrivateTmp=true" in content


def test_release_manifest_and_checksums() -> None:
    """Verify release manifest and sha256 checksums exist and match compiled binary."""
    assert RELEASE_MANIFEST.is_file()
    assert CHECKSUM_FILE.is_file()

    manifest_text = RELEASE_MANIFEST.read_text(encoding="utf-8")
    assert "PenPress Release v0.1.0 Manifest" in manifest_text
    assert "penpress" in manifest_text

    checksums_text = CHECKSUM_FILE.read_text(encoding="utf-8")
    assert len(checksums_text.strip()) > 0

    dist_binary = ROOT / "dist" / "penpress"
    if dist_binary.is_file():
        hasher = hashlib.sha256()
        with dist_binary.open("rb") as f:
            while chunk := f.read(65536):
                hasher.update(chunk)
        expected_digest = hasher.hexdigest()
        assert expected_digest in checksums_text
