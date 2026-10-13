# STATE.md

Generated from `tasks/*.md` by `make state`. **Do not edit the board by hand**; change the card, then regenerate. CI fails if this file is stale.

Phase flow: P0 (governance) -> R0..R5 research + P1 core (parallel) -> X-1 expansion -> P2..P9.

<!-- BOARD:START -->
**Summary:** todo: 4 / doing: 0 / review: 0 / done: 12 / blocked: 0

### Board
| ID | Title | Zone | Status | Depends | Implemented-by | Reviewed-by |
|---|---|---|---|---|---|---|
| [P0-1](tasks/P0-1.md) | Repository, tooling, package skeleton | meta | **done** | - | antigravity-orchestrator | director-adversarial-review |
| [P0-2](tasks/P0-2.md) | Governance docs: AGENTS, BRIEF, tasks, STATE, JOURNAL, licences, compute, ADR, checklists | meta | **done** | - | antigravity-orchestrator | director-adversarial-review |
| [P0-3](tasks/P0-3.md) | CI green on Linux, macOS, Windows | meta | **done** | - | antigravity-orchestrator | director-adversarial-review |
| [P0-4](tasks/P0-4.md) | Dossier review: independent verification of landscape and licence claims | research | **todo** | P0-1, P0-2 | - | - |
| [P1-1](tasks/P1-1.md) | Core types: Stroke, Path, Page, units, transforms | core | **done** | P0-3 | worker-core-p1 | director-adversarial-review |
| [P1-2](tasks/P1-2.md) | Single-stroke fallback font (public domain Hershey) with Greek and math coverage | core | **done** | P1-1 | worker-core-font | director-adversarial-review |
| [P1-3](tasks/P1-3.md) | Machine profile and G-code compiler (Marlin, Ender 3 Pro) | plan | **done** | P1-1 | worker-plan-gcode | director-adversarial-review |
| [P1-4](tasks/P1-4.md) | Marlin simulator and toolpath renderer | plan | **done** | P1-3 | worker-plan-sim | director-adversarial-review |
| [P1-5](tasks/P1-5.md) | First end-to-end: text to strokes to G-code to simulator image to OCR | plan | **done** | P1-2, P1-4 | worker-plan-e2e | director-adversarial-review |
| [R0-1](tasks/R0-1.md) | Synthetic fixture factory (handwriting sheets, bed photos, equations, PDFs) | research | **done** | P0-3 | worker-research-r01 | director-adversarial-review |
| [R1-1](tasks/R1-1.md) | Handwriting cloning research spike (photo or canvas sample to plottable strokes) | research | **done** | R0-1 | worker-research-r11 | director-adversarial-review |
| [R2-1](tasks/R2-1.md) | Equations in the user's handwriting (research spike) | research | **done** | P0-3 | worker-research-r21 | director-adversarial-review |
| [R3-1](tasks/R3-1.md) | Camera calibration, paper and border detection (simulated + real images) | research | **todo** | R0-1 | - | - |
| [R4-1](tasks/R4-1.md) | PDF and document ingest (any PDF to structured blocks with LaTeX and figures) | research | **todo** | R0-1 | - | - |
| [R5-1](tasks/R5-1.md) | Physical limits of the Ender 3 Pro pen plotter (kinematics, Z-touch, paper fit, hardware test protocol) | research | **done** | P0-3 | worker-research-r51 | director-adversarial-review |
| [X-1](tasks/X-1.md) | Expansion: turn research ADRs into concrete implementation cards for P2-P9 | meta | **todo** | R1-1, R2-1, R3-1, R4-1, R5-1, P1-5 | - | - |

### Available to start (all dependencies done)
- [P0-4](tasks/P0-4.md): Dossier review: independent verification of landscape and licence claims
- [R3-1](tasks/R3-1.md): Camera calibration, paper and border detection (simulated + real images)
- [R4-1](tasks/R4-1.md): PDF and document ingest (any PDF to structured blocks with LaTeX and figures)

### Waiting for review
- (none)

### Blocked
- (none)
<!-- BOARD:END -->
