# JOURNAL.md (append-only; newest at bottom)

Add entries with: `make journal MSG="what/why" CARD=<ID>`. One line per meaningful step or decision. If your context resets, read the tail of this file.

- 2026-10-12T18:55:00Z [antigravity-orchestrator] [P0-1] Created repo skeleton, uv project, gate tooling, tests.
- 2026-10-12T18:55:00Z [antigravity-orchestrator] [P0-2] Verified research via gh api: HandwritingAgent repo 404; sjvasquez unlicensed; handcode custom licence; SDT/One-DM/DiffusionPen/toolkit/skeleton-tracing/vpype MIT; docling MIT; marker weights restricted. Recorded in docs/developer/research/verified-landscape.md.
- 2026-10-12T18:55:00Z [antigravity-orchestrator] [P0-2] Decision: research cards R0..R5 run before implementation of P2-P9; X-1 expands roadmap from ADRs. User decisions: local-first, Python+FastAPI, PDF+Markdown inputs, webcam optional, agents must resolve the honest limits.
- 2026-10-13T09:33:47Z [agent] [P0-3] CI blocked by GitHub billing, not code; local gate green; P0-3 blocked
- 2026-10-13T09:35:09Z [agent] [P0-3] Local CI on clean clone passed (Linux). README director quick start added.
- 2026-10-13T09:45:17Z [agent] [P0-3] P0-1, P0-2, P0-3 reviewed by director; all 3 green, CI verified across 3 platforms. Unlocked Phase 1 and Research track.
- 2026-10-13T09:45:40Z [agent] [P1-1] Claimed P1-1 (core stroke types, transforms, RDP, serialization) by worker-core-p1
- 2026-10-13T09:52:20Z [agent] [P1-1] P1-1 completed: core types implemented, 1000-page hypothesis test green, gate passed with 98% coverage. Card moved to review.
- 2026-10-13T09:56:02Z [agent] [P1-1] P1-1 reviewed by director-adversarial-review: mutation tests passed, coverage 98.5%, CI 100% green. P1-1 marked done. Unlocked P1-2 and P1-3.
- 2026-10-13T09:56:20Z [agent] [P1-2] Claimed P1-2 (single-stroke fallback font: Hershey loader, Greek/math coverage, line layout, OCR CER validation) by worker-core-font
- 2026-10-13T10:02:35Z [agent] [P1-2] P1-2 completed: Hershey single-stroke loader, Greek/math symbols, layout engine, OCR CER 0.00% verified. Card moved to review.
- 2026-10-13T10:12:13Z [agent] [P1-2] P1-2 reviewed by director-adversarial-review: mutation test passed, Tesseract CER 0.00% verified, visual inspection passed, CI 100% green. P1-2 marked done.
- 2026-10-13T10:15:07Z [agent] [P1-3] Claimed P1-3 (machine profile loader, Marlin G-code compiler, safety preambles, Hypothesis property tests, golden tests) by worker-plan-gcode
- 2026-10-13T10:19:04Z [agent] [P1-3] P1-3 completed: Marlin G-code compiler implemented with safety preambles, Hypothesis property tests, golden tests, throughput >1M segments/s. Card moved to review.
- 2026-10-13T10:22:41Z [agent] [P1-3] P1-3 reviewed by director-adversarial-review: mutation test passed, golden files matched, throughput 1.08M seg/s, CI 100% green. P1-3 marked done. Unlocked P1-4.
- 2026-10-13T10:24:07Z [agent] [P1-4] Starting P1-4: Virtual Marlin simulator and toolpath renderer design and implementation
- 2026-10-13T10:29:48Z [agent] [P1-4] P1-4 completed: Virtual Marlin simulator, trapezoidal timing, serial resend protocol, and toolpath renderer implemented. Evidence recorded and card moved to review.
- 2026-10-13T10:33:10Z [agent] [P1-4] P1-4 reviewed and marked done by director-adversarial-review. CI 100% green across all platforms. Unlocked P1-5.
