"""Command line entry point."""

from __future__ import annotations

import sys

from penpress import __version__


def main(argv: list[str] | None = None) -> int:
    """Run the CLI. Currently supports `--version` only; features land with their cards."""
    args = sys.argv[1:] if argv is None else argv
    if args and args[0] in {"--version", "-V"}:
        print(f"penpress {__version__}")
        return 0
    print("penpress: no commands available yet. See STATE.md for progress.", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
