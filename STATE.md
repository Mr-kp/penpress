# STATE.md

Generated from `tasks/*.md` by `make state`. **Do not edit the board by hand**; change the card, then regenerate. CI fails if this file is stale.

Phase flow: P0 (governance) -> R0..R5 research + P1 core (parallel) -> X-1 expansion -> P2..P9.

<!-- BOARD:START -->
**Summary:** todo: 10 / doing: 0 / review: 1 / done: 16 / blocked: 0

### Board
| ID | Title | Zone | Status | Depends | Implemented-by | Reviewed-by |
|---|---|---|---|---|---|---|
| [P0-1](tasks/P0-1.md) | Repository, tooling, package skeleton | meta | **done** | - | antigravity-orchestrator | director-adversarial-review |
| [P0-2](tasks/P0-2.md) | Governance docs: AGENTS, BRIEF, tasks, STATE, JOURNAL, licences, compute, ADR, checklists | meta | **done** | - | antigravity-orchestrator | director-adversarial-review |
| [P0-3](tasks/P0-3.md) | CI green on Linux, macOS, Windows | meta | **done** | - | antigravity-orchestrator | director-adversarial-review |
| [P0-4](tasks/P0-4.md) | Dossier review: independent verification of landscape and licence claims | research | **done** | P0-1, P0-2 | auditor-dossier | director-adversarial-review |
| [P1-1](tasks/P1-1.md) | Core types: Stroke, Path, Page, units, transforms | core | **done** | P0-3 | worker-core-p1 | director-adversarial-review |
| [P1-2](tasks/P1-2.md) | Single-stroke fallback font (public domain Hershey) with Greek and math coverage | core | **done** | P1-1 | worker-core-font | director-adversarial-review |
| [P1-3](tasks/P1-3.md) | Machine profile and G-code compiler (Marlin, Ender 3 Pro) | plan | **done** | P1-1 | worker-plan-gcode | director-adversarial-review |
| [P1-4](tasks/P1-4.md) | Marlin simulator and toolpath renderer | plan | **done** | P1-3 | worker-plan-sim | director-adversarial-review |
| [P1-5](tasks/P1-5.md) | First end-to-end: text to strokes to G-code to simulator image to OCR | plan | **done** | P1-2, P1-4 | worker-plan-e2e | director-adversarial-review |
| [P2-1](tasks/P2-1.md) | Handwriting profile generator and sample sheet ingestion engine | profile | **review** | X-1, R1-1, P1-1 | worker-profile-p21 | - |
| [P2-2](tasks/P2-2.md) | Interactive canvas and tablet stroke capture studio with local-first quality scoring | profile | **todo** | X-1, P2-1 | - | - |
| [P3-1](tasks/P3-1.md) | Organic humanizer engine with multi-scale jitter, baseline wander, and slant drift | profile | **todo** | X-1, P2-1, P1-2 | - | - |
| [P4-1](tasks/P4-1.md) | Mathematical formula handwriting layout and symbol synthesis engine | core | **todo** | X-1, R2-1, P1-1, P1-2 | - | - |
| [P5-1](tasks/P5-1.md) | Document ingest pipeline and structured block parser | ingest | **todo** | X-1, R4-1, P1-1 | - | - |
| [P5-2](tasks/P5-2.md) | Page composer and layout typesetter for ruled and blank stationery | ingest | **todo** | X-1, P5-1, R5-1, P3-1 | - | - |
| [P6-1](tasks/P6-1.md) | Path optimization, traveling salesperson sort, and bed mesh Z-compensation | plan | **todo** | X-1, P1-3, P5-2 | - | - |
| [P7-1](tasks/P7-1.md) | Robust serial driver, line checksum protocol, and hardware recovery engine | plan | **todo** | X-1, P1-3, P1-4 | - | - |
| [P8-1](tasks/P8-1.md) | Dual-mode calibration wizard with camera homography and manual tactile jog alignment | vision | **todo** | X-1, R3-1, P7-1 | - | - |
| [P9-1](tasks/P9-1.md) | Minimalist dark studio UI and REST API with live toolpath telemetry | api | **todo** | X-1, P2-2, P5-2, P6-1, P7-1, P8-1 | - | - |
| [P9-2](tasks/P9-2.md) | Cross-platform packaging, virtual print driver, and commercial release v0.1.0 | meta | **todo** | X-1, P9-1 | - | - |
| [R0-1](tasks/R0-1.md) | Synthetic fixture factory (handwriting sheets, bed photos, equations, PDFs) | research | **done** | P0-3 | worker-research-r01 | director-adversarial-review |
| [R1-1](tasks/R1-1.md) | Handwriting cloning research spike (photo or canvas sample to plottable strokes) | research | **done** | R0-1 | worker-research-r11 | director-adversarial-review |
| [R2-1](tasks/R2-1.md) | Equations in the user's handwriting (research spike) | research | **done** | P0-3 | worker-research-r21 | director-adversarial-review |
| [R3-1](tasks/R3-1.md) | Camera calibration, paper and border detection (simulated + real images) | research | **done** | R0-1 | worker-research-r31 | director-adversarial-review |
| [R4-1](tasks/R4-1.md) | PDF and document ingest (any PDF to structured blocks with LaTeX and figures) | research | **done** | R0-1 | worker-research-r41 | director-adversarial-review |
| [R5-1](tasks/R5-1.md) | Physical limits of the Ender 3 Pro pen plotter (kinematics, Z-touch, paper fit, hardware test protocol) | research | **done** | P0-3 | worker-research-r51 | director-adversarial-review |
| [X-1](tasks/X-1.md) | Expansion: turn research ADRs into concrete implementation cards for P2-P9 | meta | **done** | R1-1, R2-1, R3-1, R4-1, R5-1, P1-5 | chief-system-architect | director-adversarial-review |

### Available to start (all dependencies done)
- [P4-1](tasks/P4-1.md): Mathematical formula handwriting layout and symbol synthesis engine
- [P5-1](tasks/P5-1.md): Document ingest pipeline and structured block parser
- [P7-1](tasks/P7-1.md): Robust serial driver, line checksum protocol, and hardware recovery engine

### Waiting for review
- [P2-1](tasks/P2-1.md): Handwriting profile generator and sample sheet ingestion engine, needs a reviewer other than worker-profile-p21

### Blocked
- (none)
<!-- BOARD:END -->
