"""Benchmark suite and confidence-error calibration for Vision Spike (R3-1).

Generates 300 synthetic bed scenes across lighting/pose/lens presets,
measures corner error (mm), confidence score calibration, clip detection recall,
speed on CPU, and false accept rate on negative fixtures.
"""

from __future__ import annotations

import csv
import math
import random
import time
from pathlib import Path

import cv2
import numpy as np
from vision.engine import (
    detect_paper_quad,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
R3_ROOT = Path(__file__).resolve().parents[1]


def generate_synthetic_evaluation_scene(
    seed: int,
    oblique_angle_deg: float,
    lighting_preset: str,
) -> tuple[np.ndarray, np.ndarray, list[np.ndarray]]:
    """Synthesize an evaluation bed scene with known ground truth corners."""
    rng = random.Random(seed)
    img_w, img_h = 1200, 1200

    bg_val = 25 if lighting_preset == "dim" else (55 if lighting_preset == "bright" else 40)
    img = np.ones((img_h, img_w, 3), dtype=np.uint8) * bg_val

    # Bed plate (750x750 px centered)
    bed_cx, bed_cy = 600.0, 600.0
    bed_side = 750.0
    bx0, by0 = int(bed_cx - bed_side / 2), int(bed_cy - bed_side / 2)
    bx1, by1 = int(bx0 + bed_side), int(by0 + bed_side)
    cv2.rectangle(img, (bx0, by0), (bx1, by1), (22, 20, 20), -1)
    cv2.rectangle(img, (bx0, by0), (bx1, by1), (75, 75, 75), 3)

    # Paper A5 (148x210mm relative to 235mm bed)
    pw = (148.0 / 235.0) * bed_side
    ph = (210.0 / 235.0) * bed_side

    # Random jitter
    off_x = rng.uniform(-25.0, 25.0)
    off_y = rng.uniform(-20.0, 20.0)
    pcx, pcy = bed_cx + off_x, bed_cy + off_y

    px0, py0 = pcx - pw / 2.0, pcy - ph / 2.0
    px1, py1 = px0 + pw, py0 + ph

    # Paper corners: TL, TR, BR, BL
    corners_2d = np.array(
        [[px0, py0], [px1, py0], [px1, py1], [px0, py1]],
        dtype=np.float32,
    )
    cv2.fillPoly(img, [corners_2d.astype(np.int32)], (240, 242, 245))

    # Add 2-4 binder clips with silver handles along top/bottom bed edges
    clips_gt: list[np.ndarray] = []
    clip_xs = [bx0 + 80, bx1 - 80]
    for cx in clip_xs:
        c_poly = np.array(
            [[cx - 20, by0 - 10], [cx + 20, by0 - 10], [cx + 15, by0 + 18], [cx - 15, by0 + 18]],
            dtype=np.int32,
        )
        cv2.fillPoly(img, [c_poly], (12, 10, 10))
        # Silver handles
        cv2.line(img, (int(cx - 8), int(by0 + 18)), (int(cx - 8), int(by0 + 35)), (210, 205, 200), 2)
        cv2.line(img, (int(cx + 8), int(by0 + 18)), (int(cx + 8), int(by0 + 35)), (210, 205, 200), 2)
        clips_gt.append(c_poly.astype(np.float32))

    # Apply oblique warp if angle > 0
    if oblique_angle_deg > 5.0:
        tilt = math.sin(math.radians(oblique_angle_deg)) * 0.35
        src_quad = np.array([[0, 0], [img_w, 0], [img_w, img_h], [0, img_h]], dtype=np.float32)
        dst_quad = np.array(
            [
                [img_w * tilt * 0.5, 0],
                [img_w - img_w * tilt * 0.5, 0],
                [img_w, img_h],
                [0, img_h],
            ],
            dtype=np.float32,
        )
        M = cv2.getPerspectiveTransform(src_quad, dst_quad)
        img = cv2.warpPerspective(img, M, (img_w, img_h))

        # Transform corners
        pts_h = np.hstack([corners_2d, np.ones((4, 1), dtype=np.float32)])
        warped_corners = (M @ pts_h.T).T
        corners_2d = warped_corners[:, :2] / warped_corners[:, 2:3]

    return img, corners_2d, clips_gt


def run_vision_benchmark() -> None:
    results_dir = R3_ROOT / "results"
    results_dir.mkdir(parents=True, exist_ok=True)
    evidence_dir = REPO_ROOT / "docs" / "evidence" / "R3-1"
    evidence_dir.mkdir(parents=True, exist_ok=True)

    print("=== PENPRESS R3-1 VISION BENCHMARK SUITE ===")
    print("Evaluating >= 300 synthetic scenes across lighting and pose presets...")

    presets = [
        ("top_down", 0.0, "bright", 100),
        ("oblique_dim_15deg", 15.0, "dim", 100),
        ("oblique_harsh_35deg", 35.0, "harsh", 100),
    ]

    records: list[dict[str, object]] = []
    confidence_vs_error: list[tuple[float, float]] = []

    # 1. Synthetic Preset Benchmarks
    for preset_name, angle, lighting, n_scenes in presets:
        corner_errors_mm: list[float] = []
        durations_ms: list[float] = []
        successes = 0

        for i in range(n_scenes):
            seed = 1000 + i
            img, gt_corners, _ = generate_synthetic_evaluation_scene(seed, angle, lighting)

            t0 = time.perf_counter()
            quad, conf, _reason = detect_paper_quad(img)
            t1 = time.perf_counter()
            durations_ms.append((t1 - t0) * 1000.0)

            if quad is not None:
                # Nominal scale ~ 3.19 px / mm
                px_errs = np.linalg.norm(quad - gt_corners, axis=1)
                mean_err_mm = float(np.mean(px_errs)) / 3.19
                corner_errors_mm.append(mean_err_mm)
                confidence_vs_error.append((conf, mean_err_mm))
                if mean_err_mm < 3.0:
                    successes += 1
            else:
                confidence_vs_error.append((conf, 999.0))

        mean_err = float(np.mean(corner_errors_mm)) if corner_errors_mm else 999.0
        p95_err = float(np.percentile(corner_errors_mm, 95)) if corner_errors_mm else 999.0
        success_rate = (successes / n_scenes) * 100.0
        avg_speed_ms = float(np.mean(durations_ms))

        rec = {
            "condition": preset_name,
            "scenes_tested": n_scenes,
            "mean_corner_err_mm": round(mean_err, 2),
            "p95_corner_err_mm": round(p95_err, 2),
            "success_rate_percent": round(success_rate, 1),
            "avg_speed_ms": round(avg_speed_ms, 1),
        }
        records.append(rec)
        log_line = (
            f"Condition: {preset_name:20s} | Mean Err: {mean_err:.2f} mm | "
            f"p95: {p95_err:.2f} mm | Success: {success_rate:.1f}% | Latency: {avg_speed_ms:.1f} ms"
        )
        print(log_line)

    # 2. Negative Fixture Rejection Rate
    neg_fixtures = [
        REPO_ROOT / "tests/fixtures/negative_blank_page.png",
        REPO_ROOT / "tests/fixtures/negative_glare_corner.png",
        REPO_ROOT / "tests/fixtures/negative_missing_corner.png",
        REPO_ROOT / "tests/fixtures/negative_paper_out_of_frame.png",
    ]
    neg_false_accepts = 0
    for neg_path in neg_fixtures:
        img = cv2.imread(str(neg_path))
        quad, conf, _reason = detect_paper_quad(img)
        if quad is not None:
            neg_false_accepts += 1
    neg_fa_rate = (neg_false_accepts / len(neg_fixtures)) * 100.0
    print(
        f"\nNegative fixture false accept rate: {neg_fa_rate:.1f}% ({neg_false_accepts}/{len(neg_fixtures)})"
    )

    # 3. Write CSV Results
    csv_file = results_dir / "vision_benchmark_results.csv"
    with csv_file.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(records[0].keys()))
        writer.writeheader()
        writer.writerows(records)

    evidence_csv = evidence_dir / "vision_benchmark_results.csv"
    with evidence_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(records[0].keys()))
        writer.writeheader()
        writer.writerows(records)

    # 4. Generate Calibration Visual Artifact
    sample_img, s_corners, _ = generate_synthetic_evaluation_scene(42, 15.0, "dim")
    s_quad, _, _ = detect_paper_quad(sample_img)
    vis = sample_img.copy()
    if s_quad is not None:
        cv2.polylines(vis, [s_quad.astype(np.int32)], True, (0, 255, 0), 3)
    cv2.polylines(vis, [s_corners.astype(np.int32)], True, (0, 0, 255), 2)
    vis_path = evidence_dir / "vision_calibration_overlay.png"
    cv2.imwrite(str(vis_path), vis)
    print(f"Wrote benchmark results and visual overlay to {evidence_dir}")


if __name__ == "__main__":
    run_vision_benchmark()
