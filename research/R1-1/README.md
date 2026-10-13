# Research Spike R1-1: Handwriting Cloning Research Prototype

Runnable research prototypes and benchmarks for turning user handwriting samples (photos or canvas recordings) into plottable vector strokes for arbitrary text.

---

## 1. Quickstart & Benchmark Reproduction

To reproduce the benchmark results on the hold-out test sentences:

```bash
# 1. Run the full benchmark suite across Approaches A, B, and C
uv run python research/R1-1/benchmark.py

# 2. Inspect generated CSV results
cat docs/evidence/R1-1/cloning_benchmark_results.csv
```

Outputs are generated in `docs/evidence/R1-1/`:
- `cloning_benchmark_results.csv`: Benchmark metrics (CER, speed, path length, pen lifts).
- `Approach_A_GlyphBank_contact_page.png`: Full 30-sentence rendered page of Approach A.
- `Approach_B_GravesRNN_page.png`: Rendered page of Approach B.
- `Approach_C_Hybrid_page.png`: Rendered page of Approach C.

---

## 2. Directory Structure

- `cloning/`:
  - `protocol.py`: Common `Synthesizer` protocol and dataclasses (`StyleProfile`, `GlyphVariant`, `SynthesisResult`).
  - `stroke_recovery.py`: Offline-to-online vectorization (adaptive binarization, skeletonization, graph-based writing order sorting, RDP simplification).
  - `profile_builder.py`: Extracts and normalizes glyph banks and style statistics from sample sheets.
  - `approach_a_bank.py`: Deterministic User Glyph Bank Synthesizer with organic humanizer.
  - `approach_b_graves.py`: Neural Graves LSTM-MDN Synthesizer running on CPU.
  - `approach_c_hybrid.py`: Hybrid Confidence-Gated Synthesizer.
- `vendor/`:
  - `skeleton-tracing/`: Algorithmic skeleton tracing (MIT).
  - `pytorch-handwriting-synthesis-toolkit/`: Graves LSTM PyTorch model & checkpoint (MIT).
- `benchmark.py`: 30-sentence benchmark script with Tesseract OCR evaluation.
