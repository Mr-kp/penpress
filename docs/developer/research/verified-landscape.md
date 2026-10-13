# Verified research landscape (2026-10-12)

Method: every row below was checked with `gh api repos/OWNER/REPO` or by fetching the primary source on the date above. Search-engine summaries were treated as leads only. **Re-verify before depending on anything; repos change.**

## Corrections to earlier claims

| Claim | Reality |
|---|---|
| `Jaykef/HandwritingAgent` repo available | **HTTP 404.** The paper exists (arXiv:2606.18788) and footnotes that URL, but the code is not public. It drives Gemini 3.1 Pro to draw SVG strokes on a grid, so it is cloud-based and not a model we can run. |
| `Gang-Dai/SDT` | 404. The real repo is `dailenson/SDT`. |
| `loicgasser/vpype-gcode` | 404. Find the real vpype G-code writer plugin (agents: verify; vpype itself has a built-in `gwrite` with profiles in recent versions). |
| `maddinkunze/handcode` is reusable | License is a custom "Other" license + `LICENSE_NOTE`. Read both before reusing any code. It wraps MIT `vickianand/handwriting-synthesis` and unlicensed `sjvasquez/handwriting-synthesis`. |

## Handwriting synthesis (R1)

| Repo | License | Stars | Last push | Output type | Notes |
|---|---|---|---|---|---|
| `dailenson/SDT` (CVPR 2023) | MIT | 1.4k | 2025-06 | **online strokes** | Style-disentangled Transformer. Datasets: Chinese, Japanese, English (Drive links in README). Weights in README. Plotter-native output. Verify English quality and that style can be taken from our own samples. |
| `dailenson/One-DM` (ECCV 2024) | MIT | 571 | 2025-10 | raster image | One-shot diffusion. Needs skeleton and stroke-order recovery to plot. |
| `koninik/DiffusionPen` (ECCV 2024) | MIT | 108 | 2024-10 | raster image | Few-shot latent diffusion, IAM. |
| `X-rayLaser/pytorch-handwriting-synthesis-toolkit` | MIT | 120 | 2024-01 | online strokes | Graves RNN (LSTM+MDN+attention), trainable, style priming. |
| `vickianand/handwriting-synthesis` | MIT | 6 | 2019-04 | online strokes | PyTorch Graves port (used by handcode). Verified active fork. |
| `sjvasquez/handwriting-synthesis` | **none (all rights reserved)** | 4.8k | 2024-01 | online strokes | Study the architecture; **do not copy code or ship its weights** without permission. |
| `reshamgaire/HandFonted` | MIT | 49 | 2026-05 | vector glyphs | Single image to font: segmentation, classification, skeletonize, RDP. Useful reference for the glyph-bank path. |
| `MengLi-l1/StrokeExtraction` | none | 41 | 2023-11 | stroke order from raster | Research code, no license: reference only. |

Data needed for training/fine-tuning online models: IAM-OnDB (registration, research license), CASIA-OLHWDB (research). **Check dataset licenses** before any weight is redistributed; product may need to train on user data or permissive data only.

## Stroke recovery from images (R1/R3)

| Repo | License | Notes |
|---|---|---|
| `LingDong-/skeleton-tracing` | MIT | Raster to polylines, no outline step. Python/JS/C++ ports. |
| scikit-image `skeletonize` (BSD) + `skan` (BSD) | permissive | Graph analysis of skeletons (branches, junctions). |

## Equations (R2)

| Resource | License | Notes |
|---|---|---|
| Google MathWriting (in `google-research/google-research` under `mathwriting/`) | **Dataset: CC BY-NC-SA 4.0; Code: Apache-2.0** | Online handwritten math, InkML (verified 2026-10-13). Non-commercial license strictly restricts distribution; evaluation only. |
| CROHME / CROHME 2023 | research | Online math InkML benchmark. |
| `lukas-blecher/LaTeX-OCR` (pix2tex) | MIT | Image to LaTeX; use for round-trip checking. |
| `breezedeus/pix2text` | MIT | Text + math OCR. |
| KaTeX (MIT) / MathJax (Apache-2.0) | permissive | Layout of LaTeX (boxes, positions); run via Node. |

## PDF ingest (R4)

| Resource | License | Notes |
|---|---|---|
| `DS4SD/docling` | MIT | Structured PDF conversion. Primary candidate. |
| `datalab-to/marker` | code Apache-2.0, **weights restricted** (OpenRAIL-M, startup/revenue limits) | Opt-in only. |
| `opendatalab/MinerU` | NOASSERTION / see LICENSE.md | Read LICENSE.md; historically AGPL. |
| `PaddlePaddle/PaddleOCR` | Apache-2.0 | OCR. |
| pdfminer.six (MIT), pypdfium2 (Apache/BSD) | permissive | Vector path extraction for figures. PyMuPDF is AGPL: avoid or isolate. |

## Plotting / machine (R5, P1)

| Resource | License | Notes |
|---|---|---|
| `abey79/vpype` | MIT | Path optimisation (linemerge, linesort, linesimplify). |
| `AndrewSink/pltr_toolhead` (PLTR V2) | **none** | Spring-loaded Ender 3 Pro pen mount (STL). Print for personal use; **do not redistribute**. Consider designing our own mount (separate card). |
| `LingDong-/skeleton-tracing`, `opencv-python` (MIT wrapper, Apache OpenCV) | permissive | Vision. |

## Compute reality

Dev VPS: 2 vCPU, 3 GB RAM, no GPU, 73 GB disk, Python 3.14 (ML wheels often lag; target Python 3.11/3.12 via `uv`). Training and heavy inference: Colab (MCP) or user machine.
