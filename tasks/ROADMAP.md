# ROADMAP (outline only; concrete cards are written by X-1 after research)

Do **not** implement from this file. It tells the architect what must be covered.

## P2: Profile and cloning
Sample sheet generator (PDF with markers); sheet ingestion (rectify, binarise, segment); stroke recovery; glyph bank / model per ADR 0001; profile manager (versioned, export/import); phone/tablet capture flow; quality report shown to the user; opt-in cloud plugin with zero-egress-when-off test.

## P3: Humanizer
Baseline wander, slant drift, spacing jitter, margin drift, ink-dynamics feedrate modulation, bold via multi-pass; statistical tests on distributions; no repeated-glyph look (variant checks).

## P4: Math
Per ADR 0002: LaTeX layout, symbol bank, fallback chain, stretchy symbols, matrices; round-trip OCR gates.

## P5: Ingest and layout
Markdown+LaTeX parser; PDF ingest per ADR 0004; figure handling (vector and raster tracing, hand-drawn filter); page composer (ruled paper, margins, titles, pagination, A5 and A4 per ADR 0005); keep-out zones from calibration.

## P6: Path planning
Merge/order/flip/simplify with vpype or own implementation (decided by measurement), minimise lifts and travel; Z-compensation by bed mesh.

## P7: Machine control
Serial sender (handshake, buffering, line numbers/checksums, resend), pause/resume/cancel, resume-from-stroke after disconnect, progress, dry-run/hover mode, power-loss notes, emergency-stop UX.

## P8: Calibration
Manual wizard (always works), camera mode per ADR 0003 (paper/borders/clips/skew/offset), phone-as-camera (private HTTPS), plot verification (photo after test pattern), hardware-results import from R5-1 protocol.

## P9: Application and packaging
Web UI (Document Studio, Profile Studio, Calibration, Plot/Monitor, Settings), toolpath preview with scrubber, security hardening (Host headers, upload limits, CSRF), desktop wrapper, installers for Linux/macOS/Windows, optional virtual CUPS printer, user guide, screenshots, release v0.1.0.

## Cross-cutting (every phase)
Docs, changelog, checklists, licence register, zero-egress test, security tests, CI green on three OSes, evidence + independent review.
