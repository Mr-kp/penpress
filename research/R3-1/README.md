# Research Spike R3-1: Vision Calibration and Paper Detection Prototype

Runnable vision prototypes and benchmarks for camera-assisted setup, paper corner detection, bed homography calibration, and binder clip obstacle keepouts.

---

## 1. Quickstart & CLI Commands

```bash
# 1. Detect paper quadrilateral in frame
PYTHONPATH=research/R3-1 uv run python research/R3-1/vision/cli.py detect-paper tests/fixtures/bed_scene_topdown_bright.png

# 2. Detect metallic binder clips and keepouts
PYTHONPATH=research/R3-1 uv run python research/R3-1/vision/cli.py detect-clips tests/fixtures/bed_scene_topdown_bright.png

# 3. Calibrate homography matrix mapping pixels to physical bed mm
PYTHONPATH=research/R3-1 uv run python research/R3-1/vision/cli.py calibrate-homography tests/fixtures/bed_scene_topdown_bright.png

# 4. Find pen nozzle offset from photographed crosshair
PYTHONPATH=research/R3-1 uv run python research/R3-1/vision/cli.py find-pen-offset tests/fixtures/bed_scene_topdown_bright.png

# 5. Verify post-plot ink presence
PYTHONPATH=research/R3-1 uv run python research/R3-1/vision/cli.py verify-plot tests/fixtures/bed_scene_topdown_bright.png

# 6. Run full benchmark suite across >= 300 synthetic scenes
PYTHONPATH=research/R3-1 uv run python research/R3-1/benchmark.py
```

Outputs and metrics are saved to `docs/evidence/R3-1/`:
- `vision_benchmark_results.csv`: Per-condition benchmark numbers.
- `vision_calibration_overlay.png`: Visual alignment verification image.

---

## 2. Architecture & Modules

- `vision/`:
  - `engine.py`: Core computer vision algorithms (paper quad detection, RANSAC homography, clip isolation, glare rejection).
  - `cli.py`: Unified command line interface emitting versioned JSON results with confidence scores and diagnostic codes.
- `tests/`:
  - `test_vision.py`: Comprehensive test suite verifying sub-millimeter precision and 0% false accept rate on negative fixtures.
- `benchmark.py`: Benchmark suite evaluating >= 300 scenes across lighting and pose variations.
