# Architecture (target, pending ADRs)

Decisions are made by research cards and recorded as ADRs in `adr/`. Until ADRs 0001-0005 are accepted, module names below are provisional.

```mermaid
flowchart TD
  A[Markdown / LaTeX / PDF] --> B[ingest]
  B --> C[Document model]
  C --> D[layout: ruled page, margins, pagination]
  P[profile: cloned handwriting] --> E[synth: text and math strokes]
  C --> E
  D --> E
  E --> F[humanizer]
  F --> G[plan: merge, order, simplify]
  G --> H[plan: G-code compiler]
  H --> I[machine: serial sender]
  H --> J[machine: Marlin simulator]
  K[vision: calibration] --> D
  K --> H
  I --> L[(Ender 3 Pro)]
```

## Module zones

| Module | Responsibility | Zone |
|---|---|---|
| `core` | Stroke/Path/Page types, transforms, serialisation | core |
| `profile`, `synth` | Handwriting cloning, text and math stroke synthesis, humanizer | profile |
| `ingest`, `layout` | Documents in, pages out | ingest |
| `plan`, `machine` | Optimisation, G-code, sender, simulator | plan |
| `vision` | Paper/border detection, calibration | vision |
| `api`, `web` | Local FastAPI server and UI | api |

## Cross-cutting design rules

- Units are millimetres everywhere internally; conversion happens at the machine boundary.
- All inter-module data are typed, versioned, JSON-serialisable (`schema_version`).
- Heavy engines (OCR, PDF converters, TeX layout) are isolated behind subprocess or loopback boundaries with timeouts, memory limits and clear errors.
- Every plugin that can touch the network is off by default and covered by a zero-egress test.
- Failure never produces silent wrong output: low confidence or missing data yields an explicit error/warning, with a documented fallback.
