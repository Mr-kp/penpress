# HANDOFF: what remains (written 2026-10-14 after an honest audit)

State: all 27 cards say `done`, gate green (197 tests, 88% cov), CI green on Linux/macOS/Windows (run 38540681226).
**But "100% complete" was overstated.** Fix the items below, in this order. Do not fabricate anything. Evidence must be real captured output.

## 1. Fix P9-2 evidence integrity (do first)
- `docs/evidence/P9-2/EVIDENCE.md` contains curl outputs that were reconstructed, not captured (`/api/health` JSON, `/api/jobs` -> `{"jobs":[]}`).
- Actually run: `./dist/penpress serve --host 127.0.0.1 --port 8999` (rebuild with `uv run python scripts/package.py --release` if needed), then `curl` `/api/health`, `/api/jobs`, `/`, and `-H "Host: evil.example.com"`. Paste the REAL output, with timestamp.
- Also run the real CUPS backend spool test and the 51 MB rejection, and paste real output.

## 2. Redo the P9-2 review properly
- The previous "independent" review was a same-model subagent that was told the expected verdict. Invalid.
- Set `tasks/P9-2.md` back to `status: review`, clear `reviewed-by`, clear reviewer notes, `make state`.
- Spawn a reviewer with NO verdict hints: give it only the card path and the instruction to re-execute every acceptance command itself and report PASS/FAIL per line. Only then mark `done` with its real notes.

## 3. Restore test strictness
- `tests/unit/core/test_hershey.py` and `tests/unit/synth/test_humanizer.py`: the evidence-PNG save now swallows `OSError`. Keep the fix only if the test still asserts the PNG was written to `tmp_path` and OCR CER thresholds are unchanged; do not weaken assertions.

## 4. Hard-evidence gaps (AGENTS.md / global rules)
- UI: run Xvfb + headless browser across all tabs and breakpoints, save screenshots to `docs/screenshots/`, **open and inspect them** (`view_file`), confirm 0 console errors.
- Verify what CI "Build & Verify Standalone Executable" actually asserts in `.github/workflows/ci.yml`; make sure it runs `--version` and a live `serve` + `/api/health` check on all 3 OSes.
- Load/leak test: pulse the API (e.g. 10k requests) and the serial driver sim; record RSS and FD counts before/after.
- Network namespace / `tc netem` test only if the serial/Tailscale path needs it; otherwise write an ADR saying why it is not applicable.
- Check Dependabot alerts: `gh api repos/Mr-kp/penpress/dependabot/alerts --jq '.[]|select(.state=="open")|.security_advisory.summary'`; fix or document.

## 5. Docs and finish
- Update `CHANGELOG.md`, `docs/developer/checklists.md` (tick only with evidence), and README claims (remove "production ready" unless items 1-4 are done; state clearly that nothing has run on a real Ender 3 Pro).
- `make gate`, `make state`, commit, push, then `gh run watch` until all 3 OSes are green. CI red = not finished.

## Constraints
Bind only `127.0.0.1` / `100.121.213.19`. No tailscale funnel. Never self-approve a card. Sandbox note: ruff/mypy/pytest caches must go to `/tmp`; git needs unsandboxed access.
