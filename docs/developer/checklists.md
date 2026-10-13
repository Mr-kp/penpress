# Engineering checklists

Tick a box only when evidence exists in `docs/evidence/<card>/`. A reviewer unticks anything unproven.

## Per-card (every card)
- [ ] Acceptance lines each proven with real output
- [ ] `make gate` green locally
- [ ] Tests added (incl. at least one negative test); none skipped/weakened
- [ ] CHANGELOG entry with ISO timestamp
- [ ] README/docs updated (or "no behaviour change" stated in evidence)
- [ ] Evidence file filled, images opened and described
- [ ] Journal entries cover decisions
- [ ] Pushed; CI green on all three OS jobs
- [ ] Reviewed by a different agent

## Per-phase (reviewer agent)
- [ ] Re-run acceptance commands independently, results match evidence
- [ ] Forbidden-pattern scan clean; spot-check 3 functions for real logic
- [ ] Licence register updated for every new dependency
- [ ] Security: no `0.0.0.0`, no new egress paths, uploads sanitised
- [ ] Docs consistent with behaviour (README quickstart actually works from a clean clone)

## Release (v0.1.0)
- [ ] Clean-clone install and `penpress --version`
- [ ] Simulated end-to-end: PDF with equations -> G-code -> simulator PNG -> OCR round-trip at thresholds
- [ ] Hardware test protocol executed by the user and results recorded
- [ ] Packages built for Linux/macOS/Windows and smoke-tested in CI
- [ ] UI screenshots captured and inspected; zero console errors
- [ ] Zero-egress test passes
