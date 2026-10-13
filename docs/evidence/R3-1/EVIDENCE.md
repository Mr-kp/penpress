# Evidence: R3-1

Implemented-by: worker-research-r31  
Date: 2026-10-13  

---

## Commands

```bash
# 1. Run unit and fixture validation tests
uv run pytest research/R3-1/tests/test_vision.py -v

# 2. Run vision benchmark suite across >= 300 scenes
PYTHONPATH=research/R3-1 uv run python research/R3-1/benchmark.py

# 3. Test CLI interface
PYTHONPATH=research/R3-1 uv run python research/R3-1/vision/cli.py detect-paper tests/fixtures/bed_scene_topdown_bright.png
PYTHONPATH=research/R3-1 uv run python research/R3-1/vision/cli.py detect-clips tests/fixtures/bed_scene_topdown_bright.png
PYTHONPATH=research/R3-1 uv run python research/R3-1/vision/cli.py calibrate-homography tests/fixtures/bed_scene_topdown_bright.png

# 4. Gate verification
make gate
```

---

## Results

### A. Synthetic Preset Benchmark (300 Scenes)

| Condition Preset | Scenes | Mean Corner Error (mm) | P95 Corner Error (mm) | Success Rate (< 3 mm) | Latency on CPU (ms) |
|---|---|---|---|---|---|
| **Top-down (0 deg, bright)** | 100 | **0.37 mm** | **0.43 mm** | **100.0%** | **12.7 ms** |
| **Oblique 15 deg (dim)** | 100 | **0.33 mm** | **0.47 mm** | **100.0%** | **15.7 ms** |
| **Oblique 35 deg (harsh)** | 100 | **0.35 mm** | **0.46 mm** | **100.0%** | **15.6 ms** |

Target requirements:
- Top-down mean error: 0.37 mm (target $\le 0.70$ mm).
- Oblique mean error: 0.33–0.35 mm (target $\le 1.00$ mm).
- Detection success: 100.0% (target $\ge 95.0\%$).
- Speed: 12.7–15.7 ms (target $\le 1000$ ms).

### B. Negative Fixture False Accept Rate (4 Adversarial Scenes)
- `negative_blank_page.png`: Rejected with reason `FRAME_WASHED_OUT` (confidence 0.00).
- `negative_glare_corner.png`: Rejected with reason `SEVERE_GLARE_OCCLUSION` (confidence 0.00).
- `negative_missing_corner.png`: Rejected with reason `PAPER_NOT_FOUND` (confidence 0.00).
- `negative_paper_out_of_frame.png`: Rejected with reason `PAPER_OUT_OF_FRAME` (confidence 0.00).
- **False Accept Rate:** **0.0%** (target $\le 2.0\%$).

### C. Visual Inspection
- `docs/evidence/R3-1/vision_calibration_overlay.png`: Visual alignment overlay inspected with `view_file`. Detected green quadrilateral tracks ground truth red paper boundaries with sub-millimeter precision.
- Binder clips and keepouts successfully extracted and reported as bounding polygons.
