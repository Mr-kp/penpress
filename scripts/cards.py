"""Shared card parsing for the task board tooling (stdlib only)."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TASKS_DIR = ROOT / "tasks"
EVIDENCE_DIR = ROOT / "docs" / "evidence"
STATUSES = ("todo", "doing", "review", "done", "blocked")
_ID_RE = re.compile(r"^[A-Z]+[0-9]*-[0-9]+$")


@dataclass
class Card:
    path: Path
    id: str
    title: str
    phase: str
    zone: str
    status: str
    depends: list[str] = field(default_factory=list)
    implemented_by: str = ""
    reviewed_by: str = ""
    body: str = ""


class CardError(ValueError):
    """Raised when a card file is malformed."""


def parse_card(path: Path) -> Card:
    text = path.read_text(encoding="utf-8")
    match = re.match(r"^---\n(.*?)\n---\n(.*)$", text, re.DOTALL)
    if not match:
        raise CardError(f"{path.name}: missing front matter")
    meta: dict[str, str] = {}
    for line in match.group(1).splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        key, sep, value = line.partition(":")
        if not sep:
            raise CardError(f"{path.name}: bad front matter line {line!r}")
        meta[key.strip()] = value.split("#", 1)[0].strip()
    for required in ("id", "title", "phase", "zone", "status"):
        if not meta.get(required):
            raise CardError(f"{path.name}: front matter missing '{required}'")
    if not _ID_RE.match(meta["id"]):
        raise CardError(f"{path.name}: invalid id {meta['id']!r}")
    if meta["id"] != path.stem:
        raise CardError(f"{path.name}: id {meta['id']} must equal file name")
    if meta["status"] not in STATUSES:
        raise CardError(f"{path.name}: status must be one of {STATUSES}")
    depends = [d.strip() for d in meta.get("depends", "").split(",") if d.strip()]
    return Card(
        path=path,
        id=meta["id"],
        title=meta["title"],
        phase=meta["phase"],
        zone=meta["zone"],
        status=meta["status"],
        depends=depends,
        implemented_by=meta.get("implemented-by", ""),
        reviewed_by=meta.get("reviewed-by", ""),
        body=match.group(2),
    )


def load_cards(tasks_dir: Path = TASKS_DIR) -> list[Card]:
    cards = [
        parse_card(p) for p in sorted(tasks_dir.glob("*.md")) if p.name not in {"README.md", "ROADMAP.md"}
    ]
    return sorted(cards, key=lambda c: _sort_key(c.id))


def _sort_key(card_id: str) -> tuple[str, int, int]:
    prefix, _, num = card_id.partition("-")
    letters = re.match(r"[A-Z]+", prefix)
    digits = re.search(r"[0-9]+", prefix)
    return (
        letters.group(0) if letters else prefix,
        int(digits.group(0)) if digits else 0,
        int(num) if num.isdigit() else 0,
    )


def available_cards(cards: list[Card]) -> list[Card]:
    done = {c.id for c in cards if c.status == "done"}
    return [c for c in cards if c.status == "todo" and all(d in done for d in c.depends)]
