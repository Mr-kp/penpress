# HANDOFF: where to continue (written 2026-10-14)

## The bar (non-negotiable)
The user wants the **fully polished, simulated-execution, 100% verified deliverable**. "Gate green" is not "done".
Done = every Acceptance line of every card is demonstrably true, evidence is real, and a **different** agent
(or the user) has independently re-run it. Do not self-approve. Do not write reviewer notes for a review that did not happen.

Start: `make briefing`, read `AGENTS.md`, then work the list below **top to bottom**. Each item is independently useful,
so stopping after any item still leaves the repo better.

## Priority list (most important first)

### 1. Undo the fake review on P9-2 (honesty fix, 5 min)
- `tasks/P9-2.md`: set `status: review`, clear `reviewed-by:`.
- `docs/evidence/P9-2/EVIDENCE.md`: delete the "Verified by independent reviewer director-adversarial-p92" text under
  `## Reviewer notes`; leave it for the real reviewer. Fix the checklist lines marked PASS that are not (see items 2-4).
- `make state`, journal the correction (`make journal MSG="P9-2 reset to review: prior review was self-written" CARD=P9-2`).
- Also audit other cards: confirm each `reviewed-by` was a real separate agent run, not set by the implementer.

### 2. Real cross-platform binaries (acceptance: Linux + macOS + Windows)
- Only a Linux ELF was built (`dist/penpress`). Add a CI job (new workflow `.github/workflows/package.yml`, matrix
  ubuntu/macos/windows) that runs `uv run python scripts/package.py --release` and smoke-tests the output:
  `penpress --version` prints `penpress 0.1.0`, and `penpress render-text tests/fixtures/p1_5_text_120words.txt --out out`
  exits 0 and creates `.gcode`.
- Upload the three binaries as artifacts; generate per-OS `checksums.sha256` from the CI-built files.
- macOS: wrap in a `.app` using `packaging/desktop/Info.plist`, and add a real `.icns` (generate from `penpress.png`).
- `scripts/package.py` needs `pip install pyinstaller` as a dev dependency (add to `pyproject.toml` dependency-groups; record in
  `docs/developer/licenses.md` first: PyInstaller is GPL-2.0 with a bootloader exception, so confirm it is acceptable and record the decision).

### 3. Prove `penpress serve` actually runs
- Only `serve --help` was ever run. Write a test that starts the server on `127.0.0.1` (ephemeral port), requests
  `/api/health`, checks `version == __version__`, and shuts it down. Also a negative test: request with `Host: evil.example.com`
  returns 403.
- Raise `src/penpress/__main__.py` coverage (currently 34%): test `_handle_serve` (monkeypatch `run_server`), `_handle_render_text`
  error path, and the no-args path.
- Run the **standalone binary** with `serve` and curl `/api/health` and `/` (web assets must load from the bundle: check
  `WEB_DIR` in `src/penpress/api/server.py`; it uses `parents[3] / "web"`, which will not resolve inside a PyInstaller bundle. Use
  `sys._MEIPASS` fallback.) This is a likely real bug.

### 4. Make the CUPS driver actually enqueue
- `packaging/cups/penpress-print` only writes files to `~/.penpress/spool/`; nothing consumes them. Either:
  a) add a spool watcher / `POST /api/jobs` ingest endpoint in `src/penpress/api/` that picks up spooled PDFs and feeds
     `DocumentIngestEngine` (preferred, matches the acceptance line), with tests, or
  b) change the card's acceptance wording to "spools" via an ADR. Do not silently shrink scope (AGENTS.md section 3).
- Add a test with a real minimal PDF (use `reportlab`, already a dependency), not a fake byte string.
- Make the oversize test stream through stdin, not only a file argument. Note `penpress-print` has no `.py` extension, so ruff/mypy
  do not scan it; consider moving the logic into `src/penpress/` with a thin wrapper.

### 5. Release manifest integrity
- Replace the weak "non-empty" check in `tests/unit/packaging/test_packaging.py` with a test that recomputes SHA-256 of listed
  artifacts and compares. Decide whether `release/` is committed (checksums only) or CI-generated and attached to a GitHub Release.
- Tag `v0.1.0` and create a GitHub Release with the three binaries only after items 2-4 pass.

### 6. Polish and docs
- `docs/user/quickstart.md`: screenshot links use `/docs/screenshots/...` (absolute, broken). Use relative paths
  (`../screenshots/ui/01_document_studio.png`). Re-open the images with `view_file` to confirm they exist.
- README: add CLI flags (`serve --host --port`), packaging instructions, CUPS install, version 0.1.0 badge.
- `docs/developer/checklists.md`: tick only with evidence. Add developer docs for packaging in `docs/developer/`.
- Zone hygiene: P9-2 is `zone: meta` but touched `src/`, `tests/`, `scripts/`. Either note it in the card or split into follow-up cards.

### 7. Security and hygiene
- 13 Dependabot alerts (11 high, 2 moderate) on `Mr-kp/penpress`: `gh api repos/Mr-kp/penpress/dependabot/alerts`, triage, bump deps
  (`uv lock --upgrade-package ...`), rerun the gate.
- `.print_state.json` gets written to the repo root by tests; add it to `.gitignore` and make tests use `tmp_path`. Also ignore `dist/`, `build/`, `*.spec`.
- Confirm `serve` never binds `0.0.0.0` (default is 127.0.0.1; add a test that rejects `--host 0.0.0.0` or warns).

### 8. The "simulated execution, 100% verified" end-to-end proof (the real finish line)
The BRIEF "not a toy" test: a reviewer with no context can install, calibrate against the simulator, import a real
multi-page PDF with equations, preview the page, and get G-code the simulated printer executes within bounds, with OCR
reading back at the card thresholds. Build `scripts/e2e_demo.py` that does exactly this against the **standalone binary**:
1. `serve` + REST: upload a multi-page PDF fixture (R0-1 fixtures), compose pages, compile G-code.
2. Run G-code through the Marlin simulator (`src/penpress/plan/sim.py`): assert zero bounds violations, heaters off, pen lifts balanced.
3. Run calibration against a synthetic bed image (`research/R0-1` fixtures) and the manual-wizard fallback.
4. OCR the rendered output (Tesseract) and assert CER thresholds from the cards.
5. Stream via `serial_driver` against a virtual serial pair (`pty`) with injected `Resend:` errors and a mid-job disconnect, then resume.
6. Capture timestamped screenshots (Playwright, `scripts/capture_screenshots.py`) into `docs/screenshots/`, open each with `view_file`, confirm 0 console errors.
Save the full transcript under `docs/evidence/E2E/EVIDENCE.md`. Add a card `P9-3` for this and have a different agent review it.

## Known facts (do not re-learn)
- Env: `uv run ...`, Python 3.12. Sandbox is read-only for some writes: use `BypassSandbox` for `make journal`, git, uv.
- Gate: `GATE_BASE=HEAD COVERAGE_FILE=/tmp/.coverage uv run python scripts/gate.py` (coverage floor 85%, currently 87.5%).
- Windows CI differs from Linux: pass `{**os.environ, ...}` to subprocesses (home dir), watch path separators, and keep PyInstaller `--add-data` separator `;`.
- Ruff has `PLC0415` (no local imports) and `PLR0911` (max 6 returns); mypy is strict; `forbid.py` bans the words mock/fake/placeholder/dummy/TODO in `src/`.
- Every `git push` must be followed with `gh run list` then `gh run watch <id>` until all three OS jobs are green (rule 5).
- Latest good CI: run `38485811056` on `b92f620`. `HEAD` is `b92f620` on `main`.
- CHANGELOG.md needs an ISO-timestamped entry for any change under `src/`, `scripts/`, `web/`.

## Definition of finished
All of: items 1-8 done; `make gate` green; CI green on three OSes **including** the packaging job; GitHub Release `v0.1.0` with three
verified binaries; E2E evidence reviewed by someone other than the implementer; `STATE.md` regenerated and honest.
