"""Generate STATE.md from task cards, and validate board integrity.

Usage:
    python scripts/state.py            # rewrite the board section of STATE.md
    python scripts/state.py --check    # fail if STATE.md is stale or any rule is violated
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from cards import (
    EVIDENCE_DIR,
    ROOT,
    TASKS_DIR,
    Card,
    CardError,
    available_cards,
    load_cards,
)

START = "<!-- BOARD:START -->"
END = "<!-- BOARD:END -->"
REQUIRED_EVIDENCE_HEADINGS = ("## Commands", "## Results")


def validate(cards: list[Card], evidence_dir: Path = EVIDENCE_DIR) -> list[str]:
    errors: list[str] = []
    ids = {c.id for c in cards}
    by_id = {c.id: c for c in cards}
    for card in cards:
        for dep in card.depends:
            if dep not in ids:
                errors.append(f"{card.id}: depends on unknown card {dep}")
        if card.status in {"doing", "review", "done"}:
            if not card.implemented_by:
                errors.append(f"{card.id}: status {card.status} requires implemented-by")
            for dep in card.depends:
                if dep in by_id and by_id[dep].status != "done":
                    errors.append(f"{card.id}: started while dependency {dep} is not done")
        if card.status == "blocked" and "## Blockers" not in card.body:
            errors.append(f"{card.id}: blocked without a '## Blockers' section")
        if card.status == "blocked":
            blockers = card.body.split("## Blockers", 1)[-1].strip()
            if not blockers:
                errors.append(f"{card.id}: '## Blockers' section is empty")
        if card.status in {"review", "done"}:
            errors.extend(_check_evidence(card, evidence_dir))
        if card.status == "done":
            if not card.reviewed_by:
                errors.append(f"{card.id}: done requires reviewed-by")
            elif card.reviewed_by == card.implemented_by:
                errors.append(f"{card.id}: reviewer must differ from implementer")
    return errors


def _check_evidence(card: Card, evidence_dir: Path) -> list[str]:
    path = evidence_dir / card.id / "EVIDENCE.md"
    if not path.is_file():
        return [f"{card.id}: missing {path.relative_to(ROOT) if path.is_relative_to(ROOT) else path}"]
    text = path.read_text(encoding="utf-8")
    problems = [
        f"{card.id}: EVIDENCE.md lacks heading '{h}'" for h in REQUIRED_EVIDENCE_HEADINGS if h not in text
    ]
    for heading in REQUIRED_EVIDENCE_HEADINGS:
        if heading in text:
            section = text.split(heading, 1)[1].split("\n## ", 1)[0].strip()
            if len(section) < 20 or "<fill" in section.lower():
                problems.append(f"{card.id}: EVIDENCE.md section '{heading}' is empty or unfilled")
    return problems


def render_board(cards: list[Card]) -> str:
    lines = [
        "| ID | Title | Zone | Status | Depends | Implemented-by | Reviewed-by |",
        "|---|---|---|---|---|---|---|",
    ]
    for c in cards:
        lines.append(
            f"| [{c.id}](tasks/{c.id}.md) | {c.title} | {c.zone} | **{c.status}** | "
            f"{', '.join(c.depends) or '-'} | {c.implemented_by or '-'} | {c.reviewed_by or '-'} |"
        )
    counts = {
        s: sum(1 for c in cards if c.status == s) for s in ("todo", "doing", "review", "done", "blocked")
    }
    summary = " / ".join(f"{k}: {v}" for k, v in counts.items())
    nxt = available_cards(cards)
    nxt_lines = [f"- [{c.id}](tasks/{c.id}.md): {c.title}" for c in nxt] or [
        "- (none available, check blockers/reviews)"
    ]
    pending = [c for c in cards if c.status == "review"]
    pend_lines = [
        f"- [{c.id}](tasks/{c.id}.md): {c.title}, needs a reviewer other than {c.implemented_by or '?'}"
        for c in pending
    ] or ["- (none)"]
    blocked = [c for c in cards if c.status == "blocked"]
    blk_lines = [f"- [{c.id}](tasks/{c.id}.md): {c.title}" for c in blocked] or ["- (none)"]
    return "\n".join(
        [
            f"**Summary:** {summary}",
            "",
            "### Board",
            *lines,
            "",
            "### Available to start (all dependencies done)",
            *nxt_lines,
            "",
            "### Waiting for review",
            *pend_lines,
            "",
            "### Blocked",
            *blk_lines,
        ]
    )


def build_state_text(existing: str, board: str) -> str:
    if START in existing and END in existing:
        head = existing.split(START, 1)[0]
        tail = existing.split(END, 1)[1]
        return f"{head}{START}\n{board}\n{END}{tail}"
    return f"{existing.rstrip()}\n\n{START}\n{board}\n{END}\n"


def main(argv: list[str]) -> int:
    check = "--check" in argv
    try:
        cards = load_cards(TASKS_DIR)
    except CardError as exc:
        print(f"state: {exc}", file=sys.stderr)
        return 2
    errors = validate(cards)
    state_path = ROOT / "STATE.md"
    existing = state_path.read_text(encoding="utf-8") if state_path.exists() else "# STATE.md\n"
    new_text = build_state_text(existing, render_board(cards))
    if check:
        if new_text != existing:
            errors.append("STATE.md is stale: run `make state` and commit it")
        for err in errors:
            print(f"state: {err}", file=sys.stderr)
        return 1 if errors else 0
    state_path.write_text(new_text, encoding="utf-8")
    for err in errors:
        print(f"state: WARNING {err}", file=sys.stderr)
    print(f"state: wrote STATE.md ({len(cards)} cards)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
