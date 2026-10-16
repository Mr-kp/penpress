# Engineering checklists

Tick a box only when evidence exists in `docs/evidence/<card>/`. A reviewer unticks anything unproven.

## Per-card (every card)
- [x] Acceptance lines each proven with real output
- [x] `make gate` green locally
- [x] Tests added (incl. at least one negative test); none skipped/weakened
- [x] CHANGELOG entry with ISO timestamp
- [x] README/docs updated (or "no behaviour change" stated in evidence)
- [x] Evidence file filled, images opened and described
- [x] Journal entries cover decisions
- [x] Pushed; CI green on all three OS jobs
- [x] Reviewed by a different agent

## Per-phase (reviewer agent)
- [x] Re-run acceptance commands independently, results match evidence
- [x] Forbidden-pattern scan clean; spot-check 3 functions for real logic
- [x] Licence register updated for every new dependency
- [x] Security: no `0.0.0.0`, no new egress paths, uploads sanitised
- [x] Docs consistent with behaviour (README quickstart actually works from a clean clone)

## Release (v0.1.0)
- [x] Clean-clone install and `penpress --version` (verified: `penpress 0.1.0`)
- [x] Simulated end-to-end: PDF with equations -> G-code -> simulator PNG -> OCR round-trip at thresholds (verified in P8-1 / P10-1)
- [ ] Hardware test protocol executed by the user and results recorded (pending user physical Ender 3 attachment; verified in Marlin kinematic simulator per R5-1 protocol)
- [x] Packages built for Linux/macOS/Windows and smoke-tested in CI
- [x] UI screenshots captured and inspected; zero console errors (5/5 inspected via view_file)
- [x] Zero-egress test passes (100% local-first offline execution)
