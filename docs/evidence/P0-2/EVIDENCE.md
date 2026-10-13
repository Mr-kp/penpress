# Evidence: P0-2

Implemented-by: antigravity-orchestrator
Date: 2026-10-13

## Commands
```
gh api repos/OWNER/REPO --jq '[.license.spdx_id,.stargazers_count,.pushed_at]'   # ran for 28 repos
curl -sI https://github.com/Jaykef/HandwritingAgent                              # HTTP/2 404
curl https://export.arxiv.org/api/query?search_query=ti:%22HandwritingAgent%22   # paper exists, 2606.18788
gh api repos/dailenson/SDT/readme | base64 -d | grep -i -E "online|english|dataset"
uv run python scripts/state.py --check
```

## Results
- Verified: One-DM, DiffusionPen, SDT (dailenson), pytorch-handwriting-synthesis-toolkit, skeleton-tracing, vpype, HandFonted, docling, pix2tex, pix2text, LaTeX-OCR are MIT; marker Apache-2.0 code with restricted weights; MinerU NOASSERTION; PaddleOCR Apache-2.0; KaTeX MIT; MathJax Apache-2.0; Caveat font OFL-1.1.
- Corrected: HandwritingAgent repo 404; Gang-Dai/SDT and loicgasser/vpype-gcode 404; sjvasquez and PLTR V2 have no licence; handcode has a custom licence.
- UNVERIFIED and labelled so: MathWriting dataset licence, vickianand/handwriting-synthesis details (MIT, 6 stars, 2019), real vpype gcode plugin repo.
- Governance docs written: AGENTS, BRIEF, DIRECTOR, tasks/README, ROADMAP, 17 cards.

## Acceptance checklist
- Fresh-reviewer cold-start test: NOT YET DONE; requires an independent reviewer agent (see DIRECTOR.md reviewer prompt).
- Every research claim verified or labelled UNVERIFIED: PASS
- state.py --check: see gate output in P0-3

## Deviations
none

## Reviewer notes
