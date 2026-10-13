"""Append a timestamped line to JOURNAL.md, and scaffold evidence files.

Usage:
    python scripts/journal.py "message" [CARD]
    python scripts/journal.py --evidence-new CARD
"""

from __future__ import annotations

import datetime as dt
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

EVIDENCE_TEMPLATE = """# Evidence: {card}

Implemented-by: <fill: your agent name>
Date: {date}

## Commands
<fill: every command you ran for acceptance, verbatim, one per line in a code block>

## Results
<fill: real output, numbers vs thresholds, paths to generated artifacts (images, G-code, CSV).
Open every image you reference and describe what you actually saw.>

## Acceptance checklist
<fill: copy each Acceptance line from the card and mark it PASS/FAIL with the proof>

## Deviations
<fill: anything you did differently from the card and why (or 'none')>

## Reviewer notes
<reviewer fills: what was re-run independently, verdict>
"""


def add_entry(message: str, card: str = "-", journal: Path | None = None, agent: str | None = None) -> str:
    journal = journal or ROOT / "JOURNAL.md"
    who = agent or os.environ.get("AGENT_NAME", "agent")
    stamp = dt.datetime.now(dt.UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    line = f"- {stamp} [{who}] [{card}] {message.strip()}"
    if not journal.exists():
        journal.write_text("# JOURNAL.md (append-only; newest at bottom)\n\n", encoding="utf-8")
    with journal.open("a", encoding="utf-8") as handle:
        handle.write(line + "\n")
    return line


def new_evidence(card: str, evidence_root: Path | None = None) -> Path:
    evidence_root = evidence_root or ROOT / "docs" / "evidence"
    target = evidence_root / card / "EVIDENCE.md"
    if target.exists():
        return target
    target.parent.mkdir(parents=True, exist_ok=True)
    date = dt.datetime.now(dt.UTC).strftime("%Y-%m-%d")
    target.write_text(EVIDENCE_TEMPLATE.format(card=card, date=date), encoding="utf-8")
    return target


def main(argv: list[str]) -> int:
    if len(argv) >= 2 and argv[0] == "--evidence-new":
        print(f"created {new_evidence(argv[1])}")
        return 0
    if not argv:
        print(__doc__, file=sys.stderr)
        return 2
    print(add_entry(argv[0], argv[1] if len(argv) > 1 else "-"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
