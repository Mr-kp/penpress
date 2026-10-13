# tasks/: the work queue

Each card is one file `tasks/<ID>.md`. **Cards are the single source of truth for status**; `STATE.md` is generated from them (`make state`).

## Card format

```
---
id: P1-1
title: Short title
phase: P1
zone: core
status: todo            # todo | doing | review | done | blocked
depends: P0-1, P0-2     # card ids that must be done first (or empty)
implemented-by:         # fill when you start (agent name/session id)
reviewed-by:            # a DIFFERENT agent fills this when approving
---
# P1-1: Title
## Goal
## Inputs / context to read first
## Deliverables
## Acceptance     <- exact commands + numeric thresholds; ALL must hold
## Anti-shortcut  <- the lazy ways to fail this card, explicitly forbidden
## Evidence       <- what must be in docs/evidence/<ID>/EVIDENCE.md
## Blockers
```

Status moves: `todo -> doing` (you start) `-> review` (you finish) `-> done` (reviewer) or back to `doing` (reviewer rejects, with notes in the card). `blocked` needs a Blockers entry.

## Zones (claim zones: do not edit outside yours)

| Zone | Paths |
|---|---|
| `meta` | `AGENTS.md BRIEF.md STATE.md JOURNAL.md CHANGELOG.md README.md tasks/ scripts/ docs/ .github/ Makefile pyproject.toml` |
| `core` | `src/penpress/core/` `tests/unit/core/` |
| `profile` | `src/penpress/profile/` `src/penpress/synth/` + tests |
| `ingest` | `src/penpress/ingest/` `src/penpress/layout/` + tests |
| `plan` | `src/penpress/plan/` `src/penpress/machine/` + tests |
| `vision` | `src/penpress/vision/` + tests |
| `api` | `src/penpress/api/` `web/` + tests |
| `research` | `research/<card-id>/` `notebooks/` `docs/developer/research/` `docs/developer/adr/` |

## Phase gates (an agent may not start a phase early)

| Phase | Starts when | Meaning |
|---|---|---|
| P0 | now | Governance, tooling, CI |
| R | P0 done | Research spikes R1-R5 (parallel). Each ends with an ADR + running prototype |
| P1 | P0 done | Core stroke types, stroke font, G-code compiler, Marlin simulator (needs no research) |
| X | R1-R5 ADRs accepted | **Expansion cards**: an architect expands phases P2-P9 into concrete cards using the ADR numbers |
| P2-P9 | their expansion card is done | Profile/cloning, humanizer, math, ingest/layout, planning, machine, calibration, app, packaging |

Outline of P2-P9 lives in `tasks/ROADMAP.md`. **No implementation card for P2-P9 exists until the matching X card is done.** This is deliberate: research results decide the design.

## Writing good acceptance criteria (for architects)

- Every line is checkable by a command or a number. "Works well" is rejected.
- Include a negative test (what must fail or be rejected).
- Include a fixture path and a threshold.
- State the evidence artifact (image, log, CSV) that a reviewer can open.
