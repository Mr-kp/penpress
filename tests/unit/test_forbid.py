from __future__ import annotations

from pathlib import Path

import forbid
import pytest


def _write(tmp_path: Path, name: str, text: str) -> Path:
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    return path


def rules(tmp_path: Path, name: str, text: str, kind: str = "src") -> set[str]:
    path = _write(tmp_path, name, text)
    return {v.rule for v in forbid.scan_file(path, kind, root=tmp_path)}


def test_clean_code_passes(tmp_path: Path) -> None:
    assert rules(tmp_path, "ok.py", "def add(a: int, b: int) -> int:\n    return a + b\n") == set()


@pytest.mark.parametrize(
    ("snippet", "rule"),
    [
        ("# TODO: later\nx = 1\n", "unfinished-marker"),
        ("def f():\n    raise NotImplementedError\n", "not-implemented"),
        ("def f():\n    pass\n", "empty-function"),
        ("def f():\n    ...\n", "empty-function"),
        ('def f():\n    """doc only"""\n', "empty-function"),
        ("x = 'placeholder'\n", "placeholder-word"),
        ("def make_mock_page():\n    return 1\n", "mock-in-src"),
        ("# import os\nx = 1\n", "commented-out-code"),
    ],
)
def test_src_violations_detected(tmp_path: Path, snippet: str, rule: str) -> None:
    assert rule in rules(tmp_path, "bad.py", snippet)


def test_protocol_and_abstract_methods_are_exempt(tmp_path: Path) -> None:
    code = (
        "from abc import ABC, abstractmethod\n"
        "from typing import Protocol\n"
        "class P(Protocol):\n    def run(self) -> None: ...\n"
        "class A(ABC):\n    @abstractmethod\n    def go(self) -> None:\n        ...\n"
    )
    assert rules(tmp_path, "proto.py", code) == set()


def test_allow_marker_suppresses(tmp_path: Path) -> None:
    assert rules(tmp_path, "allow.py", "x = 'placeholder'  # forbid: allow\n") == set()


@pytest.mark.parametrize(
    "snippet",
    [
        "import pytest\n@pytest.mark.skip\ndef test_a():\n    assert 1\n",  # forbid: allow
        "import pytest\n@pytest.mark.xfail\ndef test_a():\n    assert 1\n",  # forbid: allow
        "def test_a():\n    assert True\n",  # forbid: allow
    ],
)
def test_weakened_tests_detected(tmp_path: Path, snippet: str) -> None:
    assert rules(tmp_path, "test_x.py", snippet, kind="tests")


def test_scan_walks_directories(tmp_path: Path) -> None:
    src = tmp_path / "src"
    src.mkdir()
    (src / "a.py").write_text("# FIXME\n", encoding="utf-8")
    vendor = src / "vendor"
    vendor.mkdir()
    (vendor / "b.py").write_text("# FIXME\n", encoding="utf-8")
    found = forbid.scan([src], root=tmp_path)
    assert len(found) == 1
    assert found[0].rule == "unfinished-marker"


def test_main_exit_codes(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    src = tmp_path / "src"
    src.mkdir()
    (src / "ok.py").write_text("x = 1\n", encoding="utf-8")
    assert forbid.main([str(src)]) == 0
    (src / "bad.py").write_text("# TODO\n", encoding="utf-8")
    assert forbid.main([str(src)]) == 1
    assert "unfinished-marker" in capsys.readouterr().err
