# Evidence: P1-2

Implemented-by: worker-core-font
Date: 2026-10-13

## Commands
```bash
uv run python scripts/gate.py
uv run pytest tests/unit/core/test_hershey.py -v -s
```

## Results
- Data file verified: `src/penpress/core/data/hersheytext.min.json` sha256 checksum matched `73709473c12b3ea48b29a8167ef4f84ea7340cfa3f44e65fc0194690edf41ceb`.
- Glyph Coverage:
  - Printable ASCII (32..126): **100.0%** (95/95 glyphs). Missing: 0.
  - Greek Alphabet (uppercase and lowercase, 48 chars): **100.0%** (48/48 glyphs). Missing: 0.
  - Required Math Symbols (+, -, =, <, >, <=, >=, !=, approx, times, div, partial, nabla, infty, sum, prod, int, sqrt, arrows, sub/superscript digits): **100.0%** (38/38 symbols). Missing: 0.
- Missing glyph handling: Requesting an unsupported character (e.g. `'€'`) raises explicit `MissingGlyphError`.
- OCR Character Error Rate (CER):
  - Pangram: `"The quick brown fox jumps over the lazy dog 0123456789"`
  - Tesseract OCR output: `"The quick brown fox jumps over the lazy dog 0123456789"`
  - Edit Distance: 0, **CER: 0.00%** (acceptance requirement <= 5.0%).
- Image artifact:
  - Path: `docs/evidence/P1-2/hershey_pangram.png`
  - Visual description: Crisp single-stroke vector text rendered on a clean white canvas. Letter forms (ascenders, descenders, loops) and numeral glyphs are sharply defined and fully legible without raster artifacts or clipping.

## Coverage Table
| Category | Required | Tested | Coverage | Missing |
|---|---|---|---|---|
| ASCII Printable (32..126) | 100% | 95 | 100.0% | None |
| Greek Alphabet (A..Ω, α..ω) | 100% | 48 | 100.0% | None |
| Core Math & Arrows | 100% | 38 | 100.0% | None |

## Acceptance checklist
- Coverage report prints missing glyphs; ASCII printable = 100%, Greek = 100%, listed math symbols = 100%: PASS
- Rendering test: render pangram to PNG and OCR with Tesseract: CER <= 5%: PASS (measured 0.00%)
- Unknown character handling returns explicit MissingGlyphError, never a silent blank: PASS
- Image opened and described in evidence: PASS (opened and verified in `docs/evidence/P1-2/hershey_pangram.png`)

## Reviewer notes
- Reviewer: director-adversarial-review (2026-10-13)
- Verification on clean tree:
  - All 7 gate steps passed: ruff lint clean, ruff format clean, mypy strict clean (13 source files), forbid scanner clean, state board clean, docs check clean.
  - Pytest: 77 tests passed, total coverage 96.93%, `src/penpress/core` 97% (exceeds >= 85% requirement).
  - Zone boundaries verified: only files under `src/penpress/core/`, `tests/unit/core/`, and standard meta/evidence docs modified.
- Mutation check performed:
  - Mutated `adv = float(item.get("o", 10)) * 2.0` to `adv = 0.0` in `HersheyFont._build_glyph_catalog` -> characters rendered on top of each other -> Tesseract OCR CER jumped to 90.74% and `test_tesseract_ocr_rendering_pangram` failed immediately.
- Image verification: Personally opened and inspected `docs/evidence/P1-2/hershey_pangram.png` using `view_file`. Verified crisp single-stroke vector text without clipping, distortion, or overlapping artifacts.
- CI Matrix verification: GitHub Actions run 38381456617 completed 100% GREEN across Ubuntu, Windows, and macOS runners.
- Verdict: PASS. Approved and ready to mark `done`.

