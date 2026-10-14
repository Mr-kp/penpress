"""Run every quality gate in order. Exit non-zero on the first failure.

Usage: python scripts/gate.py [--fast]    (--fast skips pytest coverage threshold)
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

# Ensure cache/coverage files use /tmp in sandbox or read-only workspaces
os.environ.setdefault("COVERAGE_FILE", "/tmp/.coverage")
os.environ.setdefault("RUFF_CACHE_DIR", "/tmp/.ruff_cache")

ROOT = Path(__file__).resolve().parent.parent
PY = sys.executable
COVERAGE_MIN = "85"

STEPS: list[tuple[str, list[str]]] = [
    ("ruff lint", [PY, "-m", "ruff", "check", "--no-cache", "."]),
    ("ruff format", [PY, "-m", "ruff", "format", "--check", "--no-cache", "."]),
    ("mypy", [PY, "-m", "mypy", "--cache-dir=/tmp/.mypy_cache", "src/penpress", "scripts"]),
    ("forbid", [PY, "scripts/forbid.py"]),
    ("board", [PY, "scripts/state.py", "--check"]),
    ("docs", [PY, "scripts/docs_check.py"]),
    (
        "pytest",
        [
            PY,
            "-m",
            "pytest",
            "-q",
            "-o",
            "cache_dir=/tmp/.pytest_cache",
            "--cov=src/penpress",
            f"--cov-fail-under={COVERAGE_MIN}",
            "--cov-report=term-missing:skip-covered",
        ],
    ),
]


def run(fast: bool = False) -> int:
    for name, step_cmd in STEPS:
        cmd = [PY, "-m", "pytest", "-q"] if fast and name == "pytest" else step_cmd
        print(f"\n=== gate: {name} ===", flush=True)
        result = subprocess.run(cmd, cwd=ROOT, check=False)
        if result.returncode != 0:
            print(f"\nGATE FAILED at step '{name}'. Fix it; do not commit or claim done.", file=sys.stderr)
            return result.returncode
    print("\nGATE PASSED (all steps)")
    return 0


if __name__ == "__main__":
    raise SystemExit(run(fast="--fast" in sys.argv[1:]))
