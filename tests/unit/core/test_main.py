"""Unit tests for penpress CLI entry point and subcommands."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from penpress import __version__
from penpress.__main__ import build_parser, main


def test_cli_version(capsys: pytest.CaptureFixture[str]) -> None:
    """Test --version and -V output."""
    assert main(["--version"]) == 0
    captured = capsys.readouterr()
    assert f"penpress {__version__}" in captured.out

    assert main(["-V"]) == 0
    captured = capsys.readouterr()
    assert f"penpress {__version__}" in captured.out


def test_cli_no_args(capsys: pytest.CaptureFixture[str]) -> None:
    """Test calling CLI with no arguments prints usage help and returns code 2."""
    assert main([]) == 2
    captured = capsys.readouterr()
    assert "usage: penpress" in captured.err


def test_cli_unknown_subcommand(capsys: pytest.CaptureFixture[str]) -> None:
    """Test calling CLI with unknown subcommand."""
    with pytest.raises(SystemExit):
        main(["unknown-cmd"])


def test_cli_serve_subcommand(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test serve subcommand dispatches to run_server."""
    called: dict[str, Any] = {}

    def fake_run_server(host: str, port: int) -> None:
        called["host"] = host
        called["port"] = port

    monkeypatch.setattr("penpress.__main__.run_server", fake_run_server)
    exit_code = main(["serve", "--host", "127.0.0.1", "--port", "9090"])
    assert exit_code == 0
    assert called["host"] == "127.0.0.1"
    assert called["port"] == 9090


def test_cli_serve_subcommand_failure(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Test serve subcommand handles runtime errors gracefully."""

    def fail_run_server(host: str, port: int) -> None:
        raise RuntimeError("Port in use")

    monkeypatch.setattr("penpress.__main__.run_server", fail_run_server)
    exit_code = main(["serve"])
    assert exit_code == 1
    captured = capsys.readouterr()
    assert "Error starting server" in captured.err


def test_cli_render_text_subcommand(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Test render-text subcommand execution."""
    sample_txt = tmp_path / "doc.txt"
    sample_txt.write_text("Hello PenPress", encoding="utf-8")
    out_dir = tmp_path / "out"

    called: dict[str, Any] = {}

    def fake_execute(**kwargs: Any) -> None:
        called.update(kwargs)

    monkeypatch.setattr("penpress.__main__.execute_render_pipeline", fake_execute)

    exit_code = main(["render-text", str(sample_txt), "--out", str(out_dir), "--font-size", "4.0"])
    assert exit_code == 0
    assert called["text_file"] == sample_txt
    assert called["output_dir"] == out_dir
    assert called["font_size_mm"] == 4.0


def test_cli_render_text_failure(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    """Test render-text handles exceptions cleanly."""

    def fail_execute(**kwargs: Any) -> None:
        raise ValueError("Invalid file format")

    monkeypatch.setattr("penpress.__main__.execute_render_pipeline", fail_execute)

    exit_code = main(["render-text", "nonexistent.txt"])
    assert exit_code == 1
    captured = capsys.readouterr()
    assert "Error: Invalid file format" in captured.err


def test_cli_parser_help() -> None:
    """Test build_parser constructs subcommands properly."""
    parser = build_parser()
    assert parser.prog == "penpress"
