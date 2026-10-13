"""Docs-sync gate: source changes must come with a CHANGELOG entry.

Usage: python scripts/docs_check.py [BASE_REF]   (default: env GATE_BASE or HEAD~1)
Behaviour change in src/ (or scripts/, web/) requires CHANGELOG.md in the same range.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WATCHED = ("src/", "web/", "scripts/")


def changed_files(base: str) -> list[str] | None:
    git_bin = shutil.which("git") or "git"
    try:
        probe = subprocess.run(
            [git_bin, "rev-parse", "--verify", "--quiet", base],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        if probe.returncode != 0:
            return None
        result = subprocess.run(
            [git_bin, "diff", "--name-only", f"{base}...HEAD"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            return None
        return [line.strip() for line in result.stdout.splitlines() if line.strip()]
    except FileNotFoundError:
        return None


def evaluate(files: list[str]) -> list[str]:
    touched = [f for f in files if f.startswith(WATCHED)]
    if touched and "CHANGELOG.md" not in files:
        return [
            "code changed (" + ", ".join(touched[:5]) + ") but CHANGELOG.md was not updated in this range"
        ]
    return []


def main(argv: list[str]) -> int:
    base = argv[0] if argv else os.environ.get("GATE_BASE", "HEAD~1")
    files = changed_files(base)
    if files is None:
        print(f"docs_check: base '{base}' unavailable, skipping")
        return 0
    errors = evaluate(files)
    for err in errors:
        print(f"docs_check: {err}", file=sys.stderr)
    if not errors:
        print("docs_check: ok")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
