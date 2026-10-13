# Changelog

All notable changes are recorded here (Keep a Changelog). Every change under `src/`, `scripts/` or `web/` needs an entry with an ISO timestamp.

## [Unreleased]

### Added
- 2026-10-12T18:55:00Z: Repository bootstrap: uv project, package skeleton, `penpress --version`.
- 2026-10-12T18:55:00Z: Agent governance: `AGENTS.md`, `BRIEF.md`, task cards (`tasks/`), generated board (`STATE.md`), append-only `JOURNAL.md`.
- 2026-10-12T18:55:00Z: Tooling: `scripts/gate.py`, `forbid.py` (anti-toy scanner), `state.py` (board integrity + evidence + independent-review enforcement), `docs_check.py`, `briefing.py`, `journal.py`; Makefile entry points; tests for all of it.
- 2026-10-12T18:55:00Z: CI workflow (Linux, macOS, Windows) running the full gate.
- 2026-10-12T18:55:00Z: Research dossier with verified repos and licences, licence register, compute strategy, ADR template, checklists.
- 2026-10-12T18:55:00Z: Task cards: R0-1 fixtures, R1-1 handwriting cloning, R2-1 equations, R3-1 vision/calibration, R4-1 PDF ingest, R5-1 physical limits, P1-1..P1-5 core vertical slice, X-1 expansion gate.
- 2026-10-13T09:34:00Z: DIRECTOR.md (skeptical director protocol with worker/reviewer prompts).
- 2026-10-13T09:36:00Z: README Director quick start (dispatch order, rules, known facts).
- 2026-10-13T09:52:00Z: Core stroke geometry primitives in `src/penpress/core/` (immutable `Point`, `BoundingBox`, `Transform2D`, `Stroke`, `Path`, `Page`, RDP simplification, uniform polyline arc-length resampling, versioned JSON serialization and schema).
- 2026-10-13T10:02:00Z: Single-stroke typography engine in `src/penpress/core/hershey.py` (Hershey public domain vector font loader, ASCII/Greek/Math coverage, text line layout, Tesseract OCR verification).
- 2026-10-13T10:18:00Z: Machine profile validation and Marlin G-code compiler in `src/penpress/plan/` (zero-heat safety enforcement, Z-lift preambles, out-of-bounds guards, line checksums, >1M seg/s throughput).
- 2026-10-13T10:30:00Z: Virtual Marlin firmware simulator in `src/penpress/plan/sim.py` (kinematic state tracking, safety floor/boundary violation rejection with distinct error codes, hand-calculated trapezoidal timing verification, serial line-number + checksum resend protocol, and dark graphite toolpath raster/SVG renderer).
- 2026-10-13T10:42:00Z: First end-to-end vertical slice in `src/penpress/plan/render.py` and `penpress render-text` CLI subcommand (text to single-stroke paths, G-code compilation, virtual simulation, and closed-loop Tesseract OCR verification with 0.12% CER on 120-word text).
- 2026-10-13T11:00:00Z: Deterministic synthetic fixture factory in `research/R0-1/fixturegen/` (125 LaTeX equations across categories, Hershey vector stroke-recovery ground truth, 4 OFL handwriting sample sheets with optical noise, 3 Ender-3 bed scenes with homography matrices, and 4 negative vision edge cases; verified byte-identical SHA256 across runs).
- 2026-10-13T11:15:00Z: Mathematical equation handwriting synthesis engine in `research/R2-1/` (TeX layout via MathJax, multi-tier stroke synthesis from user bank/Hershey/wobbly rules, 100% compilation across all 125 corpus equations, ADR-0002 accepted, MathWriting CC BY-NC-SA 4.0 license restriction verified).

