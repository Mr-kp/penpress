"""Session briefing for agents with no memory. Prints what to read and do next.

Usage: python scripts/briefing.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from cards import ROOT, CardError, available_cards, load_cards


def non_negotiables(agents_text: str) -> list[str]:
    section = agents_text.split("## 1. Non-negotiables", 1)
    if len(section) < 2:
        return []
    body = section[1].split("\n## ", 1)[0]
    return [re.sub(r"\s+", " ", m).strip() for m in re.findall(r"^\d+\.\s+(.*)$", body, re.M)]


def journal_tail(path: Path, count: int = 8) -> list[str]:
    if not path.exists():
        return []
    entries = [line for line in path.read_text(encoding="utf-8").splitlines() if line.startswith("- ")]
    return entries[-count:]


def main() -> int:
    try:
        cards = load_cards()
    except CardError as exc:
        print(f"briefing: board is malformed: {exc}", file=sys.stderr)
        return 2
    print("=" * 72)
    print("PENPRESS SESSION BRIEFING: you have no memory; the repo is your memory")
    print("=" * 72)
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    print("\nRULES (full text in AGENTS.md; read it if you have not this session):")
    for rule in non_negotiables(agents):
        print(f"  - {rule[:150]}")
    doing = [c for c in cards if c.status == "doing"]
    print("\nIN PROGRESS (resume one of these before starting anything new):")
    for c in doing or []:
        print(f"  * {c.id} {c.title} (by {c.implemented_by or '?'})")
    if not doing:
        print("  (none)")
    review = [c for c in cards if c.status == "review"]
    print("\nWAITING FOR REVIEW (review these if you did not implement them):")
    for c in review:
        print(f"  * {c.id} {c.title} (implemented by {c.implemented_by or '?'})")
    if not review:
        print("  (none)")
    print("\nAVAILABLE TO START:")
    for c in available_cards(cards):
        print(f"  * {c.id} {c.title}  [zone: {c.zone}]")
    if not available_cards(cards):
        print("  (none)")
    blocked = [c for c in cards if c.status == "blocked"]
    if blocked:
        print("\nBLOCKED:")
        for c in blocked:
            print(f"  * {c.id} {c.title}")
    print("\nLAST JOURNAL ENTRIES:")
    for line in journal_tail(ROOT / "JOURNAL.md") or ["  (empty)"]:
        print(f"  {line}")
    print("\nNEXT STEPS: open tasks/<ID>.md, read Acceptance + Anti-shortcut, then work.")
    print("Re-read the Acceptance section every ~10 tool calls. Run `make gate` before every commit.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
