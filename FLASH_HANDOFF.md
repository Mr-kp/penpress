# FLASH REMEDIATION HANDOFF: Real End-to-End Integration & Craft UI Overhaul (P10-1 .. P10-3)

**READ THIS FIRST**: The previous run marked 27 cards `done`, and the underlying Python domain engines (`ingest`, `layout`, `synth`, `core/math_engine`, `plan`, `vision`, `machine`, `profile`) are genuinely well-built and tested in isolation. **HOWEVER, the user-facing entrypoints (Web Studio UI, FastAPI server, and CLI) are currently disconnected facades, and the Web UI looks like generic "vibecoded slop".**

If a real user opens `http://100.121.213.19:8080` or runs `./dist/penpress`, the product **fails** both the `BRIEF.md` contract ("Drop in any assignment (PDF, Markdown, LaTeX)...") and the **Rule 6 Minimalist Design & Visual Polish Standard**.

Do **not** stop until every single item below is fixed, visually inspected via `view_file`, verified by an independent reviewer agent, committed, pushed, and 100% green on all 3 OS CI runners.

---

## PRIORITY 1 (CRITICAL): Why the Current UI Looks Like "Vibecoded Slop" & How to Fix It

Inspecting `docs/screenshots/ui/01..05.png` reveals every hallmark of low-effort AI template slop:
1. **Giant Empty Black Void Cards**: Look at `01_document_studio.png`, `02_profile_studio.png`, `03_calibration_wizard.png`, and `04_plot_monitor.png`—60% to 75% of every card is dead, unstyled `#090a0d` black space with a tiny postage-stamp element floating in the middle.
2. **Screaming `#2563eb` Default Bootstrap Blue Buttons & Neon Cyan/Red Circles**: Violates Rule 6 ("Zero Kindergarten Candy Colors").
3. **Fake CSS "Ruled Sheet" with Unparsed LaTeX Text (`\frac{d^2x}...`)**: Instead of rendering the actual physical A5/A4 paper canvas with real vector pen strokes, it uses a tiny 320x440 HTML `<div>` with `repeating-linear-gradient` and raw unparsed text.
4. **Disconnected 2x2 Metric Boxes Floating in Empty Space**: In `02_profile_studio.png` and `04_plot_monitor.png`, 4–6 oversized boxes sit at the top of a massive empty card with zero visual hierarchy, zero sparklines/bars, zero stroke history, and zero density.
5. **110-Line Static `app.js` with Zero `fetch()` Calls**: None of the buttons work, the handwriting canvas is a static `ctx.arc()` circle, and the Plot Monitor is a 5-line `Math.sin()` wave.

### Mandatory Design System & Layout Architecture (Linear / Raycast / Teenage Engineering Precision)
Before editing `web/index.html` and `web/static/style.css`, invoke the **`modern-web-guidance`** skill and apply these exact industrial design specifications:

- **1. Precision CAD / Desktop Studio Layout (Zero Dead Void)**:
  - Structure the app like **Linear, Figma, or Bambu Studio / PrusaSlicer**:
    - **Top Command Header / Toolbar (44px height)**: Compact breadcrumb + active document title, paper preset selector (`A5 148×210mm` / `A4 210×297mm`), handwriting profile selector, quick stats pill (`1,262 strokes · 148.2m · ~3m 21s`), and primary action buttons.
    - **Left Navigation Rail (200px width)**: Clean SVG vector icons (lucide-style 1.5px stroke SVG icons—**zero emojis**) for each workspace, keyboard shortcut hints (`⌘1`..`⌘5`), and a compact hardware telemetry footer showing live serial port, bed size, and Z-heights.
    - **Full-Bleed Split Workspaces**: Every card must fill its container with purposeful content:
      - Canvases must use **responsive high-DPI scaling (`devicePixelRatio`)** with a subtle precision coordinate ruler (mm ticks along top/left edges), zoom/pan status bar at the bottom (`100% · X: 148.0 mm · Y: 210.0 mm · Grid: 7.0 mm`), and layer toggles (`[x] Ink Strokes`, `[x] Rapid Travel`, `[x] Ruled Lines`, `[x] Clip Keepouts`).
- **2. Refined Obsidian & Graphite Surface Hierarchy**:
  - App background: `#0b0c0e`
  - Elevated panel / sidebar: `#111318`
  - Interactive surface / card: `#151821` with `1px solid rgba(255, 255, 255, 0.07)` border and subtle top highlight `inset 0 1px 0 rgba(255, 255, 255, 0.04)`.
  - Primary button: Refined high-contrast neutral/metallic (`#f8fafc` background with `#0b0c0e` text, or subtle `#1e2433` surface with `#38bdf8` 1px border glow)—**ban the cheap `#2563eb` Bootstrap blue block**.
  - Typography: Inter / system sans-serif with `font-feature-settings: "cv02", "cv03", "cv04", "cv11"`, `tabular-nums` on all coordinates and metrics, tight tracking (`-0.02em` on headings), and uppercase `11px` (`letter-spacing: 0.06em`, `#64748b`) section micro-headers.
- **3. Workspace-Specific Design Requirements**:
  - **View 1 — Document Studio**:
    - **Left Pane**: Tabbed or split source control—**Dropzone for PDF / Markdown upload** (styled with dashed border, SVG document icon, file size limit badge) + **Live Markdown/LaTeX Editor** with line numbers, syntax-styled toolbar (Insert Equation, Insert Heading, Load Sample Physics/Calculus Assignment), and document block outline tree (showing parsed `TITLE`, `HEADING`, `PARAGRAPH`, `EQUATION`, `FIGURE_VECTOR` badges from the backend).
    - **Right Pane**: **True Vector Paper Sheet Viewport** (HTML5 `<canvas>` or `<svg>` scaled to exact A5/A4 aspect ratio filling the viewport) with mm rulers, subtle paper grain/shadow, 7mm ruled lines (`#cbd5e1`), pink margin line, red hatched binder-clip keepout zones in the corners, and **actual vector handwriting & MathJax strokes** rendered from `POST /api/document/compose`. Include page pagination controls (`< Page 1 of 2 >`), layer visibility pills, and `Export .gcode` / `Send to Plotter` buttons.
  - **View 2 — Profile Studio**:
    - **Left Pane**: Interactive **62-Character Glyph Bank Matrix** (`A–Z`, `a–z`, `0–9`, punctuation) showing which glyphs have captured variants (with mini stroke indicators) + **Interactive Stylus Capture Pad** (`#handwriting-canvas`) with baseline/cap-height/x-height guide rails, live pointer drawing (`pointerdown`/`move`/`up`), velocity/pressure readout, and `Download Printable A4 Calibration Sheet (PDF)` button.
    - **Right Pane**: Dense **Profile Telemetry & Humanizer Tuning Panel**—progress bar for 62-char bank completeness, real metrics from `/api/profile/glyph`, interactive sliders for Organic Humanizer parameters (`Baseline Wander mm`, `Slant Drift °`, `Spacing Jitter mm`, `Micro-Wobble`), and a **Live Sentence Preview Strip** showing how the current profile + humanizer settings render a sample sentence in real time.
  - **View 3 — Calibration Wizard**:
    - **Left Pane**: High-precision **235×235 mm Ender 3 Pro Bed CAD View** with 10mm coordinate grid, origin `(0,0)` axes indicator, interactive toolhead crosshair `(X, Y, Z)`, detected/configured A5 paper quad, and 5mm-buffered binder clip keepout polygons.
    - **Right Pane**: Step-by-step **4-Stage Tactile Jog & Camera Homography Control Deck**—includes an interactive XY directional jog pad (`+Y`, `-Y`, `-X`, `+X`, `Home G28`, step sizes `0.1mm` / `1mm` / `10mm`) and Z-height micro-stepper (`+0.05mm`, `-0.05mm`), live corner coordinate table (`TL`, `TR`, `BL`, `BR`, computed skew angle `°`, `Z-touch`, `Z-write`, `Z-lift`), and camera auto-detect trigger (`POST /api/calibration/camera`).
  - **View 4 — Plot Monitor**:
    - **Left Pane**: Full-viewport **Kinematic Toolpath Visualizer** rendering the actual compiled G-code segments from the composed document (rapid air travels in dashed `rgba(148, 163, 184, 0.25)`, pen-down writing strokes in `#38bdf8` / `#f8fafc`, active toolhead position marker), plus an **Interactive Timeline Scrubber Bar** (`0% ────●──── 100%`, Play/Pause simulation playback, speed multiplier `1x / 5x / 20x`, stroke counter).
    - **Right Pane**: **Telemetry & G-code Stream Inspector**—6 compact tabular-num metric cards + **Live G-code Command Log** (showing numbered checksum lines `N104 G1 X45.220 Y182.100 F3600 *71` with `ok` acknowledgments) + **CUPS Spool Queue Panel** (listing jobs from `GET /api/jobs` with a `Plot Job` action).
  - **View 5 — Settings**:
    - Structured two-column **Hardware & Safety Configuration** with categorized sections (`Machine Envelope & Kinematics`, `Pen Z-Axis & Spring Compliance`, `Serial Link & Checksum Protocol`, `Privacy & Zero-Egress Verification Status`), inline unit badges (`mm`, `mm/min`, `baud`), safety range hints, and a working `Save Configuration` action (`POST /api/settings`) with toast confirmation.

---

## PRIORITY 2: Backend & CLI Gaps That Must Be Fixed

### 1. CLI (`src/penpress/__main__.py`) Only Supports `.txt` via P1 Hershey Pipeline
- `penpress` only has `render-text` (which uses the Phase 1 `TextRenderer` on `.txt` files) and `serve`.
- Add `penpress render <file>` supporting `.pdf`, `.md`, and `.txt` inputs through the full production pipeline (`DocumentIngestEngine` -> `PageComposer` -> `OrganicHumanizer` + `MathEngine` -> `ToolpathOptimizer` -> `GcodeCompiler` -> `MarlinSimulator`).
- Fix running `penpress` with no arguments so it prints help instead of `"penpress: no commands available yet. See STATE.md for progress."`.

### 2. API Server (`src/penpress/api/server.py`) Missing Core Endpoints & Stroke Payloads
- Enhance `POST /api/document/compose` so it runs the full pipeline and returns: page dimensions, structured block summary, actual page stroke polylines (for canvas/SVG rendering), compiled G-code string, simulator segments (with `pen_contact` flags), and telemetry (stroke count, pen lifts, travel distance, estimated duration).
- Add `POST /api/document/upload` for `.pdf` and `.md` files (with 50 MB size limit and filename sanitization).
- Add Profile Studio endpoints (`POST /api/profile/glyph`, `GET /api/profile/sample-sheet.pdf`).
- Add Camera Calibration endpoint (`POST /api/calibration/camera`) and Settings update endpoint (`POST /api/settings`).

### 3. Standalone Binary & MathJax Packaging (`src/penpress/core/math_engine.py` & `scripts/package.py`)
- `MATHJAX_LAYOUT_SCRIPT` in [`src/penpress/core/math_engine.py`](file:///root/antigravity/handwriting-print/src/penpress/core/math_engine.py#L29-L31) must check `getattr(sys, "_MEIPASS", None)` and fallback cleanly when run from the standalone binary.
- In [`src/penpress/ingest/markdown_parser.py`](file:///root/antigravity/handwriting-print/src/penpress/ingest/markdown_parser.py#L102-L111), set `h = 35.0` before line 106 so single-line `$$...$$` equations at the top of a document do not raise `UnboundLocalError`.

---

## Execution Plan (Cards P10-1, P10-2, P10-3)

1. **`tasks/P10-1.md`**: Unified CLI pipeline (`penpress render` for `.pdf`, `.md`, `.txt`), fix `markdown_parser.py` single-line `$$` bug, and standalone MathJax bundling/fallback.
2. **`tasks/P10-2.md`**: Complete Interactive Web Studio UI Overhaul & REST API Wiring (Linear/Raycast/CAD craft design, zero empty black voids, zero Bootstrap blue slop, real vector handwriting/math preview, interactive glyph pad + 62-char bank + humanizer sliders, interactive jog pad + bed CAD view, real G-code toolpath scrubber + live G-code stream inspector).
3. **`tasks/P10-3.md`**: Final End-to-End Verification, Tick `docs/developer/checklists.md`, Rebuild Standalone Binary, Re-capture & Critically Inspect Real Screenshots via `view_file`, Independent Review, and Green CI across Linux, macOS, and Windows.

### How to Execute
1. Run `make briefing`.
2. Complete **P10-1**, **P10-2**, and **P10-3** in order (following the Loop in `AGENTS.md`).
3. When doing **P10-2**, read the **`modern-web-guidance`** skill first, then after capturing screenshots with `scripts/capture_screenshots.py`, **open all 5 screenshots with `view_file`** and verify they look like a world-class desktop engineering tool (Linear / Bambu Studio / Raycast aesthetic) with zero dead space and real vector handwriting/math strokes.
4. Use `invoke_subagent` with an independent reviewer agent (`auditor-p10`) to verify and mark each card `done`.
5. Ensure `uv run python scripts/gate.py` passes, push to `main`, and watch `gh run list` / `gh run watch` until all 3 OS runners are 100% green (`✓`).
