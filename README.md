# PenPress

Write assignments in **your own handwriting** with an Ender 3 Pro and a pen. Drop in a PDF or Markdown/LaTeX; get a page of natural handwriting with equations and figures, calibrated against your actual paper, optionally by webcam or phone.

> **Status: pre-alpha (research + foundations).** Nothing prints yet. Live progress: [STATE.md](STATE.md). Product contract: [BRIEF.md](BRIEF.md).

## How this repo is run (for humans and agents)

This project is built by AI agents with no memory between sessions. The repo itself is the memory.

| File | Purpose |
|---|---|
| [AGENTS.md](AGENTS.md) | Binding rules and the work loop |
| [BRIEF.md](BRIEF.md) | What we are building and the unknowns to resolve |
| [STATE.md](STATE.md) | Live board, generated from task cards |
| [tasks/](tasks/) | One card per unit of work, with numeric acceptance criteria |
| [JOURNAL.md](JOURNAL.md) | Append-only log of decisions and progress |
| [docs/developer/](docs/developer/) | ADRs, research, licences, compute plan, checklists |

Start any session with:

```bash
make briefing
```

## Quickstart (developers)

```bash
uv sync                              # Python 3.11+ environment
uv run python scripts/gate.py        # lint, types, anti-toy scan, board check, docs check, tests + coverage
uv run penpress --version
```

Quality gates (`scripts/gate.py`): ruff (lint + format), mypy `--strict`, `forbid.py` (no stubs/TODOs/mocks in `src/`, no skipped or vacuous tests), `state.py --check` (board integrity, evidence and independent reviewer required for `done`), `docs_check.py` (code changes need a CHANGELOG entry), pytest with coverage >= 85%.

## Architecture (target)

```
 Markdown/LaTeX or PDF -> Ingest -> Document model -> Layout (ruled page, A5/A4)
 Handwriting profile (cloned from your sample) -> Synthesis (text + math) -> Humanizer
 -> Path planner -> G-code compiler (Marlin, Ender 3 Pro) -> Sender (USB serial) -> printer
                                    \-> Simulator (virtual Marlin + renderer)
 Calibration: manual wizard | webcam | phone camera  -> paper origin, skew, keep-out, pen offset
```

Details and decisions: [docs/developer/architecture.md](docs/developer/architecture.md), ADRs in `docs/developer/adr/`.

## Safety and privacy

- No firmware changes, no kernel drivers, no root.
- Local-first: zero network egress by default; cloud features are opt-in plugins.
- Servers bind to loopback or a private Tailscale address only.
- Crash-safe G-code (heaters off, Z lifted) and resumable plots.

## Licence

MIT. Third-party components and their licences: [docs/developer/licenses.md](docs/developer/licenses.md).
