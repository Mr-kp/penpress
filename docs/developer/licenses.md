# Dependency & licence register

Rule: record the verdict **before** adding a dependency. Product binaries may only include permissive licences. A repo without a licence file is all-rights-reserved.

| Component | Licence (verified 2026-10-12) | Use | Verdict |
|---|---|---|---|
| Python, FastAPI, uvicorn, Pillow, numpy, scipy | BSD/MIT/HPND | runtime | OK (check at add time) |
| opencv-python | MIT wrapper + Apache-2.0 OpenCV | vision | OK |
| scikit-image, skan | BSD | skeletonize | OK |
| `LingDong-/skeleton-tracing` | MIT | stroke tracing | OK (attribute in NOTICE if code is copied) |
| `abey79/vpype` | MIT | path optimisation | OK |
| `dailenson/SDT`, `One-DM`, `DiffusionPen` | MIT code | R1 candidates | Code OK. **Weights/dataset licences must be checked per file** |
| `X-rayLaser/pytorch-handwriting-synthesis-toolkit` | MIT | R1 candidate | OK |
| `sjvasquez/handwriting-synthesis` | none | study only | **Do not copy or ship** |
| `maddinkunze/handcode` | custom ("Other") | study only | **Read LICENSE + LICENSE_NOTE before any reuse** |
| `AndrewSink/pltr_toolhead` | none | personal print | **Do not redistribute STL** |
| `docling` | MIT | PDF ingest | OK |
| `marker` | Apache-2.0 code, restricted weights | PDF ingest opt-in | Opt-in plugin only |
| `MinerU` | see LICENSE.md (historically AGPL) | PDF ingest | Subprocess-only if at all; read licence first |
| PyMuPDF | AGPL | PDF | **Avoid** (use pypdfium2 / pdfminer.six) |
| pix2tex (LaTeX-OCR), pix2text | MIT | math round-trip checks | OK |
| KaTeX / MathJax | MIT / Apache-2.0 | LaTeX layout | OK (Node subprocess) |
| Tesseract | Apache-2.0 | OCR round-trip | OK (subprocess) |
| MathWriting dataset | **UNVERIFIED** | R2 | Verify before use; likely evaluation-only |
| Blender | GPL | synthetic rendering tool | Subprocess tool only; rendered images are fine |

Agents: append rows as you add dependencies. Include licence URL and date checked.
