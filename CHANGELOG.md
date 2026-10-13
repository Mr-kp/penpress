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
- 2026-10-13T11:33:00Z: Physical limits and kinematics simulation for Ender 3 Pro pen plotter in `research/R5-1/` (trapezoid velocity planning, junction deviation cornering math, hardware test protocol in `docs/user/hardware-test-protocol.md`, JSON schema validator, and ADR-0005 accepted).
- 2026-10-13T12:00:00Z: Handwriting cloning research spike in `research/R1-1/` (stroke recovery achieved 1.90 px Chamfer distance on ground truth, 3-way synthesis benchmark across 30 hold-out sentences, ADR-0001 accepted establishing User Glyph Bank with Organic Humanizer as primary standard, and 2-tier canvas/sheet capture UX proposal).
- 2026-10-13T14:40:00Z: Camera calibration, paper detection, and obstacle keepout spike in `research/R3-1/` (paper quad corner error 0.33-0.37 mm across 300 scenes, 0% false accept rate on negative fixtures, clip handle segmentation, ADR-0003 accepted).
- 2026-10-13T15:38:00Z: Handwriting profile generator and sample sheet ingestion engine in `src/penpress/profile/` (`HandwritingProfile` versioned schema, `sheet_gen.py` ArUco calibration PDF generator, `sheet_ingest.py` perspective rectification, skeleton graph centerline tracing with RDP simplification achieving 1.903 px Chamfer distance, and unit test suite).
- 2026-10-13T15:44:00Z: Declared runtime profile dependencies (`opencv-python-headless`, `scikit-image`, `scipy`, `reportlab`, `numpy`) and added typed context override for `sheet_ingest.py`.
- 2026-10-13T15:58:00Z: Added resilient git executable path resolution with `shutil.which` in `scripts/docs_check.py` for cross-platform Windows runner compatibility.
- 2026-10-13T16:18:00Z: Interactive canvas and tablet stroke capture studio with local-first quality scoring in `src/penpress/profile/` (`canvas_capture.py` online pointer event normalization, velocity tracking, multi-stroke character preservation; `quality.py` completeness gating across 62 standard alphanumerics, stroke smoothness scoring, micro-scribble rejection; 0-egress network isolation verified).
- 2026-10-13T16:28:00Z: Organic humanizer engine with multi-scale jitter, baseline wander, and slant drift in `src/penpress/synth/` (`humanizer.py` sinusoidal baseline wander, Perlin micro-wobble, word-level slant drift; `variant.py` anti-repetition variant sampling; `dynamics.py` curvature-dependent feedrate modulation and bold multi-pass toolpaths; 0.00% OCR CER verified).




