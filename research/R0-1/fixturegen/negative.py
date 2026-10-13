"""Deterministic negative fixture generator for PenPress calibration and vision testing."""

from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image, ImageDraw


def generate_negative_fixtures(output_dir: Path) -> list[str]:
    """Generate deliberate negative test fixtures: missing corner, paper out of frame, glare cover, blank."""
    output_dir.mkdir(parents=True, exist_ok=True)
    generated: list[str] = []

    # 1. Blank page (zero ink)
    blank_path = output_dir / "negative_blank_page.png"
    img_blank = Image.new("RGB", (1240, 1754), color=(248, 246, 240))
    img_blank.save(blank_path)
    generated.append(blank_path.name)

    # 2. Sheet with missing/torn corner
    torn_path = output_dir / "negative_missing_corner.png"
    img_torn = Image.new("RGB", (1240, 1754), color=(30, 32, 38))  # Dark table background
    draw_torn = ImageDraw.Draw(img_torn)
    # Sheet polygon with top-right corner truncated (torn off)
    torn_poly = [
        (80, 80),
        (1000, 80),  # Tear starts at x=1000 instead of 1160
        (1160, 240),  # Tear ends at y=240 instead of 80
        (1160, 1674),
        (80, 1674),
    ]
    draw_torn.polygon(torn_poly, fill=(245, 243, 238), outline=(200, 198, 190), width=1)
    img_torn.save(torn_path)
    generated.append(torn_path.name)

    # 3. Paper out of frame (only bottom-left visible)
    oof_path = output_dir / "negative_paper_out_of_frame.png"
    img_oof = Image.new("RGB", (1200, 1200), color=(25, 27, 32))
    draw_oof = ImageDraw.Draw(img_oof)
    # Sheet shifted far off screen
    draw_oof.rectangle([-300, -200, 400, 500], fill=(245, 243, 238))
    img_oof.save(oof_path)
    generated.append(oof_path.name)

    # 4. Glare covering corner
    glare_path = output_dir / "negative_glare_corner.png"
    img_glare = Image.new("RGB", (1200, 1200), color=(40, 42, 48))
    draw_glare = ImageDraw.Draw(img_glare)
    draw_glare.rectangle([300, 300, 900, 900], fill=(245, 243, 238))
    # Harsh saturated white specular reflection ellipse over top-left corner
    draw_glare.ellipse([240, 240, 480, 480], fill=(255, 255, 255))
    img_glare.save(glare_path)
    generated.append(glare_path.name)

    return generated


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=Path("tests/fixtures"))
    args = parser.parse_args()
    files = generate_negative_fixtures(args.out)
    print(f"Generated {len(files)} negative fixtures into {args.out}")
