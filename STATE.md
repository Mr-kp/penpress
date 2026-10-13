# STATE.md

Generated from `tasks/*.md` by `make state`. **Do not edit the board by hand**; change the card, then regenerate. CI fails if this file is stale.

Phase flow: P0 (governance) -> R0..R5 research + P1 core (parallel) -> X-1 expansion -> P2..P9.

<!-- BOARD:START -->
**Summary:** todo: 13 / doing: 0 / review: 2 / done: 0 / blocked: 1

### Board
| ID | Title | Zone | Status | Depends | Implemented-by | Reviewed-by |
|---|---|---|---|---|---|---|
| [P0-1](tasks/P0-1.md) | Repository, tooling, package skeleton | meta | **review** | - | antigravity-orchestrator | - |
| [P0-2](tasks/P0-2.md) | Governance docs: AGENTS, BRIEF, tasks, STATE, JOURNAL, licences, compute, ADR, checklists | meta | **review** | - | antigravity-orchestrator | - |
| [P0-3](tasks/P0-3.md) | CI green on Linux, macOS, Windows | meta | **blocked** | - | antigravity-orchestrator | - |
| [P0-4](tasks/P0-4.md) | Dossier review: independent verification of landscape and licence claims | research | **todo** | P0-1, P0-2 | - | - |
| [P1-1](tasks/P1-1.md) | Core types: Stroke, Path, Page, units, transforms | core | **todo** | P0-3 | - | - |
| [P1-2](tasks/P1-2.md) | Single-stroke fallback font (public domain Hershey) with Greek and math coverage | core | **todo** | P1-1 | - | - |
| [P1-3](tasks/P1-3.md) | Machine profile and G-code compiler (Marlin, Ender 3 Pro) | plan | **todo** | P1-1 | - | - |
| [P1-4](tasks/P1-4.md) | Marlin simulator and toolpath renderer | plan | **todo** | P1-3 | - | - |
| [P1-5](tasks/P1-5.md) | First end-to-end: text to strokes to G-code to simulator image to OCR | plan | **todo** | P1-2, P1-4 | - | - |
| [R0-1](tasks/R0-1.md) | Synthetic fixture factory (handwriting sheets, bed photos, equations, PDFs) | research | **todo** | P0-3 | - | - |
| [R1-1](tasks/R1-1.md) | Handwriting cloning research spike (photo or canvas sample to plottable strokes) | research | **todo** | R0-1 | - | - |
| [R2-1](tasks/R2-1.md) | Equations in the user's handwriting (research spike) | research | **todo** | P0-3 | - | - |
| [R3-1](tasks/R3-1.md) | Camera calibration, paper and border detection (simulated + real images) | research | **todo** | R0-1 | - | - |
| [R4-1](tasks/R4-1.md) | PDF and document ingest (any PDF to structured blocks with LaTeX and figures) | research | **todo** | R0-1 | - | - |
| [R5-1](tasks/R5-1.md) | Physical limits of the Ender 3 Pro pen plotter (kinematics, Z-touch, paper fit, hardware test protocol) | research | **todo** | P0-3 | - | - |
| [X-1](tasks/X-1.md) | Expansion: turn research ADRs into concrete implementation cards for P2-P9 | meta | **todo** | R1-1, R2-1, R3-1, R4-1, R5-1, P1-5 | - | - |

### Available to start (all dependencies done)
- (none available, check blockers/reviews)

### Waiting for review
- [P0-1](tasks/P0-1.md): Repository, tooling, package skeleton, needs a reviewer other than antigravity-orchestrator
- [P0-2](tasks/P0-2.md): Governance docs: AGENTS, BRIEF, tasks, STATE, JOURNAL, licences, compute, ADR, checklists, needs a reviewer other than antigravity-orchestrator

### Blocked
- [P0-3](tasks/P0-3.md): CI green on Linux, macOS, Windows
<!-- BOARD:END -->
