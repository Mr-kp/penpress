"""Capture automated high-resolution screenshots of all 5 PenPress Studio views.

Verifies:
1. Document Studio
2. Profile Studio
3. Calibration Wizard
4. Plot Monitor
5. Settings View
Asserts 0 JavaScript / console errors and saves timestamped screenshots into docs/screenshots/ui/.
"""

from __future__ import annotations

import sys
import threading
import time
from pathlib import Path
from typing import Any

import uvicorn
from playwright.sync_api import sync_playwright

from penpress.api.server import app

SCREENSHOTS_DIR = Path(__file__).resolve().parents[1] / "docs" / "screenshots" / "ui"


def run_server() -> None:
    config = uvicorn.Config(app, host="127.0.0.1", port=8000, log_level="warning")
    server = uvicorn.Server(config)
    server.run()


def capture_studio_views() -> None:
    SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)

    # Start FastAPI server in background daemon thread
    server_thread = threading.Thread(target=run_server, daemon=True)
    server_thread.start()
    time.sleep(1.0)  # Give server time to bind

    console_errors: list[str] = []

    with sync_playwright() as p:
        browser = p.chromium.launch()
        context = browser.new_context(viewport={"width": 1440, "height": 900})
        page = context.new_page()

        # Capture console error events
        def on_console(msg: Any) -> None:
            if hasattr(msg, "type") and msg.type == "error":
                console_errors.append(str(msg.text))

        page.on("console", on_console)
        page.on("pageerror", lambda err: console_errors.append(str(err)))

        # Navigate to Studio
        page.goto("http://127.0.0.1:8000/", wait_until="networkidle")
        time.sleep(0.5)

        # 1. Document Studio View
        page.click("#nav-document")
        time.sleep(0.2)
        doc_path = SCREENSHOTS_DIR / "01_document_studio.png"
        page.screenshot(path=str(doc_path))
        print(f"Captured: {doc_path}")

        # 2. Profile Studio View
        page.click("#nav-profile")
        time.sleep(0.2)
        profile_path = SCREENSHOTS_DIR / "02_profile_studio.png"
        page.screenshot(path=str(profile_path))
        print(f"Captured: {profile_path}")

        # 3. Calibration Wizard View
        page.click("#nav-calibration")
        time.sleep(0.2)
        calib_path = SCREENSHOTS_DIR / "03_calibration_wizard.png"
        page.screenshot(path=str(calib_path))
        print(f"Captured: {calib_path}")

        # 4. Plot Monitor View
        page.click("#nav-monitor")
        time.sleep(0.2)
        monitor_path = SCREENSHOTS_DIR / "04_plot_monitor.png"
        page.screenshot(path=str(monitor_path))
        print(f"Captured: {monitor_path}")

        # 5. Settings View
        page.click("#nav-settings")
        time.sleep(0.2)
        settings_path = SCREENSHOTS_DIR / "05_settings_view.png"
        page.screenshot(path=str(settings_path))
        print(f"Captured: {settings_path}")

        browser.close()

    if console_errors:
        print(f"Detected {len(console_errors)} console errors:", file=sys.stderr)
        for err in console_errors:
            print(f"  - {err}", file=sys.stderr)
        sys.exit(1)

    print("Browser inspection complete: 0 console errors detected.")


if __name__ == "__main__":
    capture_studio_views()
