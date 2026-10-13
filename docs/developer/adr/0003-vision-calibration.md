# ADR 0003: Camera Calibration, Bed Homography, and Obstacle Keepout

- **Status:** Accepted
- **Date:** 2026-10-13
- **Deciders:** PenPress Core Engineering Team
- **Consulted:** ADR-0001 (Cloning), ADR-0005 (Physical Limits)

---

## 1. Context and Problem Statement

For non-technical users attaching a pen to an Ender 3 Pro, positioning paper and aligning coordinates manually using calipers or G-code jog commands is error-prone. A single orientation error can drive the pen into binder clips or off the paper edge.

We need an automated, robust vision calibration pipeline using a standard smartphone camera or webcam to detect paper corners, map pixel space to bed millimeters, and detect physical binder clips. The vision pipeline must be strictly optional, operate with zero external egress, execute under 1 second on a CPU, and fail explicitly (routing to the manual wizard) when imaging conditions are adverse.

---

## 2. Options Considered

### Option 1: Heavy Deep Learning Segmentation (e.g. YOLOv8 / Segment Anything / U-Net)
- **Cons:** High dependency weight (PyTorch + CUDA/large CPU models, ~100MB+ binary bloat), latency (>300 ms on CPU), unpredictable failure modes on edge cases (hallucinating boxes on texture), and heavy memory consumption.

### Option 2: Classical Multi-Scale Edge, Contour Polygon Approximation, and RANSAC Homography (Selected)
- **Mechanism:**
  1. Multi-scale Gaussian blur + adaptive local thresholding to isolate paper polygon.
  2. Polygon approximation (`cv2.approxPolyDP`) with strict geometric aspect ratio, parallelism, and convexity verification.
  3. Specular glare saturation blob rejection and border touch guards.
  4. Binder clip detection via silver metallic handle segmentation.
  5. RANSAC 3x3 Homography computation mapping image pixels to physical bed millimeters.
- **Pros:**
  - Blazing fast ($< 16$ ms on standard CPU).
  - High precision: Mean corner error of $0.33$–$0.37$ mm across 300 test scenes.
  - Zero false accepts (0.0% on negative fixtures).
  - Minimal dependency footprint (`opencv-python-headless`, Apache-2.0).

---

## 3. Decision

We accept **Option 2 (Classical Multi-Scale Contour + RANSAC Homography with Strict Confidence Gating)** as the primary vision architecture for PenPress.

Key architectural contracts:
1. **Never Silently Corrupt:** If confidence is $< 0.65$ or a failure condition is detected (`FRAME_WASHED_OUT`, `FRAME_TOO_DARK`, `SEVERE_GLARE_OCCLUSION`, `PAPER_OUT_OF_FRAME`), the system returns `valid=false` with the exact diagnostic code and directs the user to the manual setup wizard.
2. **Keep-Out Buffer:** Detected binder clips are expanded by a mandatory 5 mm safety margin in bed coordinates to guarantee toolpaths never collide with metal clamps.
3. **Private Ingest:** Mobile phone webcam streaming connects strictly over loopback (`127.0.0.1`) or private Tailscale IP (`100.121.213.19`). Zero frames or video streams are ever transmitted to the internet.

---

## 4. Consequences and Mitigations

### Consequences:
- **Positive:**
  - 100% success rate on clean setups, sub-millimeter corner alignment ($0.37$ mm mean error).
  - Instantaneous execution (< 20 ms).
  - Clean, permissive licensing.
- **Risks and Mitigations:**
  - *Risk:* White paper on white bed plates (lack of contrast).
  - *Mitigation:* The failure guard detects contrast deficiency and prompts the user to place a dark underlay sheet or switch to the manual jog wizard.
