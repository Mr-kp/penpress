"""Load and resource leak verification test.

Verifies:
1. 2,000 pulsing HTTP requests to REST API endpoints without socket/FD leaks.
2. 10,000 serial G-code commands streamed through MarlinSimulator without descriptor leaks.
3. Memory RSS stability before and after pulsing load.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

if sys.platform != "win32":
    import resource

from fastapi.testclient import TestClient

from penpress.api.server import app
from penpress.plan.profile import MachineProfile
from penpress.plan.sim import MarlinSimulator


def get_fd_count() -> int:
    """Return count of open file descriptors in current process."""
    fd_dir = Path("/proc/self/fd")
    if fd_dir.exists():
        return len(list(fd_dir.iterdir()))
    return 0


def get_rss_kb() -> int:
    """Return max RSS in KB."""
    if sys.platform != "win32":
        usage = resource.getrusage(resource.RUSAGE_SELF)
        return int(usage.ru_maxrss)
    return 0


def run_load_test() -> None:
    print("=== PenPress Resource Leak & Load Verification ===")

    # Baseline resource snapshot
    fd_baseline = get_fd_count()
    rss_baseline_kb = get_rss_kb()
    print(f"Baseline: FDs={fd_baseline}, MaxRSS={rss_baseline_kb} KB")

    # 1. Pulse HTTP API (2,000 requests)
    print("Pulsing API with 2,000 requests across /api/health and /api/jobs...")
    start_time = time.perf_counter()
    with TestClient(app) as client:
        for i in range(2000):
            if i % 2 == 0:
                resp = client.get("/api/health", headers={"Host": "localhost"})
            else:
                resp = client.get("/api/jobs", headers={"Host": "localhost"})
            assert resp.status_code == 200

    api_elapsed = time.perf_counter() - start_time
    api_rate = 2000.0 / api_elapsed
    print(f"API load complete: 2,000 requests in {api_elapsed:.2f}s ({api_rate:.1f} req/s)")

    # 2. Pulse Serial Driver & Marlin Kinematic Simulator (10,000 commands)
    print("Streaming 10,000 G-code commands through Marlin kinematic simulator...")
    sim_start = time.perf_counter()
    sim = MarlinSimulator(profile=MachineProfile(), strict_safety=True)
    lines = [f"G1 X{(i % 200)} Y{((i * 3) % 200)} F3600" for i in range(10000)]
    for chunk in [lines[i : i + 500] for i in range(0, len(lines), 500)]:
        sim.execute_stream(chunk)

    sim_elapsed = time.perf_counter() - sim_start
    sim_rate = 10000.0 / sim_elapsed
    print(f"Sim load complete: 10,000 commands in {sim_elapsed:.2f}s ({sim_rate:.1f} cmd/s)")

    # Post-load resource snapshot
    fd_post = get_fd_count()
    rss_post_kb = get_rss_kb()
    fd_delta = fd_post - fd_baseline
    rss_delta_mb = (rss_post_kb - rss_baseline_kb) / 1024.0

    print(
        f"Post-Load: FDs={fd_post} (delta={fd_delta:+d}), "
        f"MaxRSS={rss_post_kb} KB (delta={rss_delta_mb:+.2f} MB)"
    )

    # Verification gates
    assert abs(fd_delta) <= 5, f"File descriptor leak detected: delta={fd_delta}"
    assert rss_delta_mb < 150.0, f"Excessive memory growth: {rss_delta_mb:.2f} MB"
    assert len(sim.violations) == 0, f"Kinematic violations detected: {len(sim.violations)}"

    print("LOAD TEST PASSED: Zero FD leaks, bounded memory, and zero kinematic violations.")


if __name__ == "__main__":
    run_load_test()
