from __future__ import annotations

from pathlib import Path

import pytest
import state
from cards import CardError, available_cards, load_cards, parse_card

CARD = """---
id: {id}
title: Example {id}
phase: P9
zone: core
status: {status}
depends: {depends}
implemented-by: {impl}
reviewed-by: {rev}
---
# {id}
## Blockers
{blockers}
"""


def make(
    tmp_path: Path,
    card_id: str,
    *,
    status: str = "todo",
    depends: str = "",
    impl: str = "",
    rev: str = "",
    blockers: str = "",
) -> Path:
    tasks = tmp_path / "tasks"
    tasks.mkdir(exist_ok=True)
    path = tasks / f"{card_id}.md"
    path.write_text(
        CARD.format(id=card_id, status=status, depends=depends, impl=impl, rev=rev, blockers=blockers),
        encoding="utf-8",
    )
    return path


def evidence(tmp_path: Path, card_id: str, body: str | None = None) -> Path:
    path = tmp_path / "docs" / "evidence" / card_id
    path.mkdir(parents=True, exist_ok=True)
    text = body or (
        "# Evidence\n## Commands\n```\nmake gate && pytest tests/unit -q\n```\n"
        "## Results\nAll 42 tests passed, coverage 91 percent, image out/a.png inspected.\n"
    )
    (path / "EVIDENCE.md").write_text(text, encoding="utf-8")
    return tmp_path / "docs" / "evidence"


def test_parse_valid_card(tmp_path: Path) -> None:
    card = parse_card(make(tmp_path, "P9-1", depends="P9-0, P8-2"))
    assert card.depends == ["P9-0", "P8-2"]
    assert card.status == "todo"


@pytest.mark.parametrize(
    "text",
    [
        "no front matter",
        "---\nid: X-1\n---\nbody",
        "---\nid: bad id\ntitle: t\nphase: p\nzone: z\nstatus: todo\n---\n",
    ],
)
def test_parse_rejects_malformed(tmp_path: Path, text: str) -> None:
    path = tmp_path / "X-1.md"
    path.write_text(text, encoding="utf-8")
    with pytest.raises(CardError):
        parse_card(path)


def test_parse_rejects_id_mismatch_and_bad_status(tmp_path: Path) -> None:
    path = make(tmp_path, "P9-1")
    path.rename(path.with_name("P9-2.md"))
    with pytest.raises(CardError, match="must equal file name"):
        parse_card(path.with_name("P9-2.md"))
    bad = make(tmp_path, "P9-3", status="weird")
    with pytest.raises(CardError, match="status"):
        parse_card(bad)


def test_available_respects_dependencies(tmp_path: Path) -> None:
    make(tmp_path, "P9-1", status="done", impl="a", rev="b")
    make(tmp_path, "P9-2", depends="P9-1")
    make(tmp_path, "P9-3", depends="P9-2")
    cards = load_cards(tmp_path / "tasks")
    assert [c.id for c in available_cards(cards)] == ["P9-2"]


def test_done_requires_evidence_and_independent_reviewer(tmp_path: Path) -> None:
    make(tmp_path, "P9-1", status="done", impl="a", rev="a")
    cards = load_cards(tmp_path / "tasks")
    errors = state.validate(cards, tmp_path / "docs" / "evidence")
    assert any("missing" in e for e in errors)
    root = evidence(tmp_path, "P9-1")
    errors = state.validate(cards, root)
    assert any("reviewer must differ" in e for e in errors)
    make(tmp_path, "P9-1", status="done", impl="a", rev="b")
    assert state.validate(load_cards(tmp_path / "tasks"), root) == []


def test_unfilled_evidence_is_rejected(tmp_path: Path) -> None:
    make(tmp_path, "P9-1", status="review", impl="a")
    root = evidence(tmp_path, "P9-1", "## Commands\n<fill: x>\n## Results\n<fill: y>\n")
    errors = state.validate(load_cards(tmp_path / "tasks"), root)
    assert len([e for e in errors if "empty or unfilled" in e]) == 2


def test_cannot_start_before_dependency_done(tmp_path: Path) -> None:
    make(tmp_path, "P9-1")
    make(tmp_path, "P9-2", status="doing", depends="P9-1", impl="a")
    errors = state.validate(load_cards(tmp_path / "tasks"), tmp_path / "docs" / "evidence")
    assert any("dependency P9-1 is not done" in e for e in errors)


def test_blocked_needs_blockers_text(tmp_path: Path) -> None:
    make(tmp_path, "P9-1", status="blocked", impl="a", blockers="")
    errors = state.validate(load_cards(tmp_path / "tasks"), tmp_path / "docs" / "evidence")
    assert any("empty" in e for e in errors)


def test_unknown_dependency_reported(tmp_path: Path) -> None:
    make(tmp_path, "P9-1", depends="Z9-9")
    errors = state.validate(load_cards(tmp_path / "tasks"), tmp_path / "docs" / "evidence")
    assert any("unknown card" in e for e in errors)


def test_render_and_replace_board(tmp_path: Path) -> None:
    make(tmp_path, "P9-1", status="review", impl="agent-a")
    cards = load_cards(tmp_path / "tasks")
    board = state.render_board(cards)
    assert "Waiting for review" in board
    assert "agent-a" in board
    first = state.build_state_text("# STATE\n", board)
    second = state.build_state_text(first, board)
    assert first == second
    assert first.count(state.START) == 1
