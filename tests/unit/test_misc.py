from __future__ import annotations

from pathlib import Path

import docs_check
import journal
import pytest

from penpress import __main__ as cli


def test_cli_version(capsys: pytest.CaptureFixture[str]) -> None:
    assert cli.main(["--version"]) == 0
    assert capsys.readouterr().out.startswith("penpress ")


def test_cli_without_args_is_an_error(capsys: pytest.CaptureFixture[str]) -> None:
    assert cli.main([]) == 2
    assert "no commands" in capsys.readouterr().err


def test_docs_check_requires_changelog() -> None:
    assert docs_check.evaluate(["src/penpress/x.py"]) != []
    assert docs_check.evaluate(["src/penpress/x.py", "CHANGELOG.md"]) == []
    assert docs_check.evaluate(["docs/a.md"]) == []
    assert docs_check.evaluate(["scripts/gate.py"]) != []


def test_journal_appends_lines(tmp_path: Path) -> None:
    target = tmp_path / "JOURNAL.md"
    journal.add_entry("first", "P1-1", journal=target, agent="a")
    journal.add_entry("second", journal=target, agent="b")
    lines = [ln for ln in target.read_text(encoding="utf-8").splitlines() if ln.startswith("- ")]
    assert len(lines) == 2
    assert "[a] [P1-1] first" in lines[0]
    assert "[b] [-] second" in lines[1]


def test_evidence_scaffold_is_idempotent(tmp_path: Path) -> None:
    first = journal.new_evidence("P1-1", tmp_path)
    first.write_text("custom", encoding="utf-8")
    second = journal.new_evidence("P1-1", tmp_path)
    assert second.read_text(encoding="utf-8") == "custom"
