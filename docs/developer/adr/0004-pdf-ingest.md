# ADR 0004: PDF and Document Ingest Architecture

- **Status:** Accepted
- **Date:** 2026-10-13
- **Deciders:** PenPress Core Engineering Team
- **Consulted:** ADR-0001 (Handwriting Cloning), ADR-0002 (Equations), ADR-0003 (Vision)

---

## 1. Context and Problem Statement

Users expect PenPress to ingest real assignment documents—ranging from clean digital single/two-column PDFs to math homework with formulas, engineering schematics, tables, and scanned or photographed pages—and transform them into structured blocks for pen synthesis.

Key challenges:
1. **Diverse Layouts:** Single-column essays, two-column scientific papers, problem sets with indented equations.
2. **Mathematical Notation:** Equations must be detected and converted into valid LaTeX for vector synthesis (via MathJax / ADR-0002).
3. **Diagrams and Vector Figures:** Electronic schematics, free-body diagrams, and plots must have their vector paths preserved rather than rasterised into unplottable pixel grids.
4. **Scanned Documents:** Clean digital PDFs have extractable text; scanned or photographed PDFs have zero text streams and require OCR.
5. **Licensing & Resource Constraints:** The pipeline must run completely locally on a 2-core / 3GB CPU box, with strictly permissive licenses (MIT / Apache / BSD). Strong copyleft (PyMuPDF / AGPL) is forbidden. Heavy multi-gigabyte models (Docling / MinerU / Marker) cannot run within memory limits without crashing or thrashing.
6. **Hostile PDF Defenses:** Corrupted byte streams, extreme canvas dimensions (e.g. 5000x5000 pt architectural blueprints), and multi-megabyte payloads must be handled gracefully without memory exhaustion or process crashes.

---

## 2. Options Considered

### Option 1: Multi-Gigabyte Deep Learning Layout Engines (Docling, MinerU, Marker)
- **Docling (MIT, IBM):** 80+ package dependency tree (Transformers, PyTorch, docling-ibm-models, rapidocr). Memory requirement exceeds 2.5 GB RAM; CPU inference takes 15–40 seconds per page.
- **MinerU (Modified Apache-2.0):** Imposes commercial restrictions (MAU > 100M / revenue > $20M requires separate commercial license; mandatory online service attribution). Heavy weights and dependencies.
- **Marker (Apache-2.0 code, restricted weights):** Non-commercial or restricted weight license prevents out-of-the-box permissive redistribution.
- **Verdict:** Heavy models are unsuitable as the core shipping engine for a local-first desktop/CLI application on standard hardware. They may serve only as optional cloud/external plugins if explicitly opted in by the user.

### Option 2: Copyleft Tools (PyMuPDF / Fitz)
- **Licence:** AGPL-3.0.
- **Verdict:** Strictly rejected per project non-negotiables (AGPL contamination risk).

### Option 3: Tiered Fast Path (pypdfium2 + pdfminer.six) with OCR Fallback & Vector Clustering (Selected)
- **Tier 1 (Fast Path):** Direct layout and stream extraction using `pypdfium2` (Apache-2.0 / BSD-3-Clause) and `pdfminer.six` (MIT).
  - Extracts text characters, exact positions, fonts, and bounding boxes.
  - Extracts vector line, curve, and rectangle drawing operators.
  - Clusters contiguous drawing primitives into vector figure blocks preserving stroke topology.
  - Heuristic classifier detects mathematical display equations and normalizes them into clean LaTeX.
  - Multi-column gutter analysis and XY-cut topological sorting guarantee correct reading order.
  - Blazing fast: **< 50 ms per page** on CPU, < 50 MB RAM footprint.
- **Tier 2 (Scanned Page OCR Fallback):**
  - Triggered automatically when text density is near zero.
  - Renders the page via `pypdfium2` at 150–300 DPI.
  - Subprocess call to local `tesseract` (Apache-2.0) with TSV bounding box extraction.
  - Preserves paragraph geometry and reading order.
- **Tier 3 (Opt-in External / LLM Plugin):**
  - For ambiguous handwritten homework or corrupted scans where local OCR yields high CER, an external plugin hook can be configured by the user. Disabled by default with zero network egress.
- **Hostile PDF Protections:**
  - File size cap (50 MB).
  - Page count cap (250 pages).
  - Oversized page clamping (> 2500 pt flags an explicit warning and downscales).
  - Malformed file catch: captures `PdfiumError` and produces structured error status (`error: malformed_pdf`) without crashing.

---

## 3. Decision

We accept **Option 3 (Tiered Fast Path via pypdfium2 + pdfminer.six with Tesseract OCR fallback and vector figure extraction)** as the core PDF ingest architecture for PenPress.

Key architectural rules:
1. **Never Silently Drop Content:** Any unrecognized drawing or unparsed element becomes an explicit `placeholder` or `figure_vector` block with its exact bounding box and geometry.
2. **Preserve Vector Topology:** Vector graphics are never converted to raster images unless raster tracing is explicitly requested. Paths are stored as float coordinate polylines ready for toolpath generation.
3. **Monotonic Reading Order:** Blocks are strictly sorted into sequential reading order `0..N-1` following human reading conventions across multiple columns.
4. **Permissive Licensing Guarantee:** Only Apache-2.0 (`pypdfium2`, `tesseract`) and MIT (`pdfminer.six`) components are bundled.

---

## 4. Consequences and Benchmark Validation

### Benchmark Numbers on Fixture Suite:
- **Throughput:**
  - Digital academic paper (1 page): **0.046 s** (13 blocks, 100% monotonic reading order).
  - Two-column technical article (1 page): **0.011 s** (11 blocks, vector pore diagram cleanly isolated).
  - Mixed math assignment (1 page): **0.012 s** (24 blocks, Gauss and Stokes theorems extracted as LaTeX).
  - Electronic circuit schematic (1 page): **0.005 s** (vector schematic preserved with 14 path polylines).
  - Noisy scanned page (1 page): **5.20 s** via Tesseract OCR fallback (18 blocks).
- **Hostile PDF Defenses:**
  - 5000x5000 pt page: Safely flagged with explicit dimension warning.
  - Corrupted byte stream: Instantly trapped (`status: error: malformed_pdf`) in 0.0001 s with zero crash.
- **Memory Footprint:** Operates under 60 MB RAM (well within 3 GB system limit).
