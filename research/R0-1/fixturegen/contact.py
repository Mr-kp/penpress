"""Contact sheet builder for visual inspection of synthetic fixtures."""

from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image, ImageDraw


def build_contact_sheet(
    image_paths: list[Path],
    output_path: Path,
    title: str,
    thumb_w: int = 400,
    thumb_h: int = 400,
    cols: int = 3,
) -> None:
    """Combine a list of images into a single annotated visual contact sheet."""
    rows = (len(image_paths) + cols - 1) // cols
    sheet_w = cols * thumb_w + (cols + 1) * 20
    sheet_h = rows * thumb_h + (rows + 1) * 40 + 50

    sheet = Image.new("RGB", (sheet_w, sheet_h), color=(13, 14, 18))
    draw = ImageDraw.Draw(sheet)

    # Title header
    draw.text((20, 20), title, fill=(248, 250, 252))

    for idx, img_p in enumerate(image_paths):
        c = idx % cols
        r = idx // cols
        x = 20 + c * (thumb_w + 20)
        y = 60 + r * (thumb_h + 40)

        if img_p.exists():
            with Image.open(img_p) as src:
                thumb = src.copy()
                thumb.thumbnail((thumb_w, thumb_h))
                # Paste centered
                px = x + (thumb_w - thumb.width) // 2
                py = y + (thumb_h - thumb.height) // 2
                sheet.paste(thumb, (px, py))
                draw.rectangle([x, y, x + thumb_w, y + thumb_h], outline=(33, 38, 56), width=1)
                draw.text((x + 5, y + thumb_h + 5), img_p.name, fill=(148, 163, 184))

    output_path.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output_path)


def generate_all_contact_sheets(fixtures_dir: Path, out_dir: Path) -> list[Path]:
    """Generate visual contact sheets for each fixture family."""
    out_dir.mkdir(parents=True, exist_ok=True)
    generated: list[Path] = []

    # 1. Handwriting Sheets
    sheet_paths = sorted(fixtures_dir.glob("sample_sheet_*.png"))
    if sheet_paths:
        cs1 = out_dir / "contact-handwriting-sheets.png"
        build_contact_sheet(sheet_paths, cs1, "PenPress R0-1: Synthetic Handwriting Sample Sheets")
        generated.append(cs1)

    # 2. Bed Scenes
    bed_paths = sorted(fixtures_dir.glob("bed_scene_*.png"))
    if bed_paths:
        cs2 = out_dir / "contact-bed-scenes.png"
        build_contact_sheet(bed_paths, cs2, "PenPress R0-1: Printer Bed Scenes & Lighting Presets")
        generated.append(cs2)

    # 3. Negative Fixtures
    neg_paths = sorted(fixtures_dir.glob("negative_*.png"))
    if neg_paths:
        cs3 = out_dir / "contact-negative-fixtures.png"
        build_contact_sheet(neg_paths, cs3, "PenPress R0-1: Negative Vision & Calibration Fixtures")
        generated.append(cs3)

    return generated


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--fixtures", type=Path, default=Path("tests/fixtures"))
    parser.add_argument("--out", type=Path, default=Path("docs/evidence/R0-1"))
    args = parser.parse_args()
    res = generate_all_contact_sheets(args.fixtures, args.out)
    for p in res:
        print(f"Generated contact sheet: {p}")
