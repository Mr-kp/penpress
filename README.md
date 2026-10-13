# PenPress

Write assignments in **your own handwriting** with an Ender 3 Pro and a pen. Drop in a PDF or Markdown/LaTeX; get a page of natural handwriting with equations and figures, calibrated against your actual paper, optionally by webcam or phone.

> **Status: pre-alpha (research + foundations).** Nothing prints yet. Live progress: [STATE.md](STATE.md). Product contract: [BRIEF.md](BRIEF.md).

## Director quick start (read this first)

You are the **Director**. You dispatch and verify; you do not implement. Full protocol: [DIRECTOR.md](DIRECTOR.md).

```bash
uv sync --python 3.12            # one-time setup (install uv first: pip install uv)
make briefing                    # board, in-progress, reviews waiting, next cards, last journal lines
uv run python scripts/gate.py    # must pass before you trust anything
```

**Dispatch order right now**

1. Review P0-1 and P0-2 (they are in `review`): dispatch a reviewer using the reviewer prompt in DIRECTOR.md. P0-3 is blocked on GitHub Actions billing (user must fix; local CI = `scripts/gate.py` on a clean clone passes).
2. Once P0-1/P0-2 are `done` and the user accepts local gate as CI substitute (or billing is fixed and P0-3 is done), dispatch in parallel, max 3, disjoint zones:
   - **R0-1** fixtures (strong model), **R5-1** physical limits (strong model), **P1-1** core types (cheap model).
3. After R0-1 is done: **R1-1** cloning, **R3-1** vision, **R4-1** ingest. **R2-1** equations can start anytime after P0-3.
4. After all R cards + P1-5 are done: **X-1** expansion, then **ask the user to approve** before any P2+ card.

**Rules the Director enforces**: workers stop at `review`; reviewers are different agents; reject on red flags in DIRECTOR.md; never lower a threshold without an ADR and the user's OK; research claims must come from `gh api`/primary sources (a search once invented a repo).

**Known facts to pass on**: HandwritingAgent repo is 404 (paper only); `sjvasquez/handwriting-synthesis` and PLTR V2 have no licence; MathWriting dataset licence unverified; dev box is 2 vCPU / 3 GB / no GPU (training goes to Colab, see [docs/developer/compute.md](docs/developer/compute.md)); no printer or camera is available to agents, so everything is verified against simulators and synthetic images.

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

# Render text to G-code, simulate Marlin execution, and generate toolpath renders
uv run penpress render-text input.txt --profile ender3pro --out out/
```

Example real execution output:
```text
Rendered input.txt to out/
Pages: 1
Strokes: 1262
Total Pen Lifts: 1262
Estimated Time: 1271.0s
G-code: out/input.gcode
Simulator Image: out/input.png
Simulator SVG: out/input.svg
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
