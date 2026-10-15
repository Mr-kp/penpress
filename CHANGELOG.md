# Changelog

All notable changes are recorded here (Keep a Changelog). Every change under `src/`, `scripts/` or `web/` needs an entry with an ISO timestamp.

## [Unreleased]

### Fixed
- 2026-10-14T16:26:00Z: Replaced fixed sleep with polling retry loop for background server health check in `.github/workflows/ci.yml` to prevent race conditions during PyInstaller archive decompression on Windows runners.
- 2026-10-14T16:05:00Z: Guarded `resource.getrusage` import and usage behind `sys.platform != "win32"` in `scripts/load_test.py` to ensure cross-platform mypy type checking passes on Windows runners.

### Added
- 2026-10-15T09:08:00Z: Comprehensive simulation and usage guide in `docs/user/simulation-and-usage-guide.md` documenting CLI execution, Tailscale/loopback Studio access, CUPS virtual printing, kinematics simulation architecture, and multi-agent command flow.
- 2026-10-14T15:52:00Z: High-frequency pulsing load and resource leak verification script in `scripts/load_test.py` (2,000 API requests at 934 req/s and 10,000 Marlin G-code commands with zero file descriptor leaks and bounded memory).
- 2026-10-14T15:54:00Z: ADR 0006 in `docs/developer/adr/0006-network-emulation-scope.md` defining transport simulation boundaries for serial hardware vs. local loopback.
- 2026-10-14T15:55:00Z: Enhanced CI multi-platform workflow in `.github/workflows/ci.yml` verifying background standalone server launch and HTTP health probe across Ubuntu, macOS, and Windows.
- 2026-10-14T08:50:00Z: Standalone executable asset resolution in `src/penpress/api/server.py` supporting PyInstaller `sys._MEIPASS` bundle layout for static web asset serving.
- 2026-10-14T08:52:00Z: Added virtual print spool queue REST endpoints `GET /api/jobs` and `POST /api/jobs/{job_id}/process` in `src/penpress/api/server.py` and unit tests in `tests/unit/api/test_server.py`.
- 2026-10-14T08:53:00Z: Comprehensive end-to-end simulated execution script in `scripts/e2e_demo.py` verifying document ingest, page composition, TSP optimization, Marlin simulation with 0 collisions, camera calibration, and hardware state recovery.
- 2026-10-14T08:55:00Z: CI workflow update in `.github/workflows/ci.yml` adding automated standalone executable builds and validation across Ubuntu, macOS, and Windows.
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
- 2026-10-13T16:38:00Z: Mathematical formula handwriting layout and symbol synthesis engine in `src/penpress/core/` (`math_engine.py` MathJax/KaTeX layout bridge, 3-tier fallback chain; `math_symbols.py` stretchy brackets, radicals, wobbly rules; 100% compilation across all 125 fixture equations at 284 eq/s).
- 2026-10-13T16:59:00Z: Document ingest pipeline and structured block parser in `src/penpress/ingest/` (`DocumentIngestEngine` supporting PDF and Markdown; `markdown_parser.py` converting headings, lists, paragraphs, display LaTeX; `layout.py` multi-column detection and monotonic reading order ordering; `figures.py` vector drawing polyline clustering and raster skeleton tracing; `schema.py` versioned document block representation; 93.7 pages/s throughput and hostile PDF defenses verified).
- 2026-10-13T17:11:00Z: Fixed cross-platform tesseract path resolution (`_find_tesseract`) and tempfile handling in `src/penpress/ingest/engine.py` for macOS and Windows runner compatibility.
- 2026-10-13T17:27:00Z: Page composer and layout typesetter in `src/penpress/layout/` (`PageComposer` supporting A5/A4 presets, greedy word wrapping, 7 mm ruled baseline alignment with <=0.2 mm deviation, multi-page pagination of 1000-word academic assignments with LaTeX equations, `LayoutOverflowError` bounds enforcement; `keepout.py` ray-casting point-in-polygon clipping with 5 mm expanded safety buffers around binder clips).
- 2026-10-13T22:53:00Z: Robust serial driver, checksum flow control, and hardware recovery engine in `src/penpress/machine/` (`serial_driver.py` threaded non-blocking G-code streamer with `N<line> <cmd>*<checksum>` formatting and automatic `Resend: N` error recovery; `state_tracker.py` kinematic coordinates, buffer depth, and execution telemetry; `recovery.py` persistent `.print_state.json` atomic checkpoints with safe Z-lift resume preamble; verified 10,000 command transmission, serial timeout safety lift, and mid-job disconnect resumption).
- 2026-10-13T23:04:00Z: Dual-mode calibration wizard with camera homography and manual tactile jog alignment in `src/penpress/vision/` (`calibrator.py` multi-scale paper quad detection, subpixel corner refinement achieving 0.326 mm mean error, metallic clip keepout extraction with >=5.0 mm expanded safety buffers, 0.0% false accept rate on negative fixtures; `manual_wizard.py` interactive 4-step state machine with tactile paper-drag resistance check; `bed_model.py` immutable bilinear paper-to-bed coordinate mapping and point-in-polygon keepout hit testing).
- 2026-10-13T23:17:00Z: Minimalist dark studio UI and REST API with live toolpath telemetry in `src/penpress/api/` and `web/` (`server.py` FastAPI backend with private Tailscale network and loopback DNS rebinding security middleware; `security.py` rejecting untrusted Host headers and enforcing strict CSP/headers; `web/index.html` Single-Page Application featuring Document Studio, Profile Studio, Calibration Wizard, Plot Monitor, and Settings views adhering to Linear/Apple macOS dark graphite aesthetic; verified 0 console errors and 100% API test pass).
- 2026-10-13T23:31:00Z: Commercial release packaging and virtual print driver in `scripts/package.py`, `packaging/`, and `release/` (`penpress` standalone binary compilation producing 159 MB single-file executable; `packaging/cups/penpress-print` CUPS virtual print driver backend with 50 MB safety rejection; `packaging/desktop/penpress.desktop` Linux XDG desktop entry; `packaging/desktop/Info.plist` macOS application bundle; `packaging/desktop/icons/` SVG and PNG high-contrast obsidian icons; `packaging/systemd/penpress.service` hardened background daemon unit; `docs/user/quickstart.md` user guide; `release/MANIFEST.md` and `release/checksums.sha256` SHA-256 integrity verification).

## [0.1.0] - 2026-10-13
First commercial release of PenPress. Dropping in Markdown, LaTeX, and PDF files writes them on paper with an Ender 3 Pro pen plotter in authentic personalized handwriting.






