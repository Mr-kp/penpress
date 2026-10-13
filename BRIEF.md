# BRIEF.md: PenPress Product Contract

**One sentence:** Drop in any assignment (PDF, Markdown, LaTeX) and an Ender 3 Pro with a pen writes it on paper in the user's own handwriting, including equations and diagrams, with setup and calibration that a non-expert can complete.

## Must-haves (acceptance of the product, not of a card)

1. **Input:** Markdown+LaTeX and PDF (any PDF is converted to a structured document: headings, paragraphs, lists, tables, equations, figures).
2. **Handwriting clone:** from a photo/scan of a sample sheet (and optionally a phone/tablet canvas capture), produces strokes that are readable, look like the user's hand, and are not visibly repetitive.
3. **Equations:** LaTeX equations rendered as natural handwritten math (fractions, roots, integrals, scripts, matrices, Greek).
4. **Figures:** vector figures and traced images become pen strokes, optionally with a hand-drawn wobble.
5. **Page layout:** titles, margins, ruled-paper alignment, pagination, A5 natively, A4 via two passes on the 220 mm bed.
6. **Machine:** safe Marlin G-code for Ender 3 Pro, pen-up/down with spring-mount, heaters/fans off, bounds-checked, resumable, streamed over USB serial or exported.
7. **Calibration:** manual wizard always available; camera mode (USB webcam or phone) is optional and detects paper, borders, clips, skew and pen offset. Failure falls back to the manual wizard with a reason.
8. **Simulation:** everything hardware-facing is verified against a software Marlin and synthetic camera images before it ever touches a printer.
9. **App:** local web UI + desktop wrapper, installable packages for Linux/macOS/Windows.

## Hard constraints

- Local-first, zero egress by default. Cloud plugins are opt-in.
- Permissive licenses only in the shipped product (see `docs/developer/licenses.md`).
- Listeners bind to loopback or the Tailscale IP only.
- No firmware flashing, no kernel drivers, no root. Crash = nothing destructive; resumable.

## Honest limits agents must resolve (not assume)

| Unknown | Research card |
|---|---|
| Best way to clone handwriting from a photo (and what quality is achievable) | R1 |
| Equations in the user's style (symbol bank vs generative vs stroke font) | R2 |
| Robust paper/border/clip detection and calibration by camera, tested on simulated + real images | R3 |
| PDF to structured document with equations and figures, locally | R4 |
| Physical limits: Z-touch, pen lift cost, paper fit, mount flex, human hardware test protocol | R5 |

## Definition of "not a toy"

A reviewer who has never seen this repo can: install it, calibrate against the simulator, import a real multi-page PDF with equations, preview the page, and get G-code that the simulated printer executes within bounds, whose rendered output an OCR reads back at the thresholds in `tasks/`.
