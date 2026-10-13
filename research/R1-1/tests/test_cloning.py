import json
import sys
from pathlib import Path

from PIL import Image

REPO_ROOT = Path(__file__).resolve().parents[3]
R1_ROOT = REPO_ROOT / "research/R1-1"
if str(R1_ROOT) not in sys.path:
    sys.path.insert(0, str(R1_ROOT))

from cloning.approach_a_bank import GlyphBankSynthesizer  # noqa: E402
from cloning.profile_builder import build_profile_from_sheet  # noqa: E402
from cloning.protocol import StyleProfile, StyleStats  # noqa: E402
from cloning.stroke_recovery import (  # noqa: E402
    binarize_handwriting,
    compute_chamfer_distance,
    skeletonize_binary,
    trace_skeleton_graph,
)


def test_stroke_recovery_on_synthetic_fixture() -> None:
    """Verify stroke recovery achieves <= 2.5 px Chamfer distance against ground truth."""
    gt_path = REPO_ROOT / "tests/fixtures/stroke_recovery_sample.json"
    img_path = REPO_ROOT / "tests/fixtures/stroke_recovery_sample.png"

    gt_data = json.loads(gt_path.read_text(encoding="utf-8"))
    img = Image.open(img_path)

    binary = binarize_handwriting(img)
    skel = skeletonize_binary(binary)
    pred_strokes = trace_skeleton_graph(skel, min_length_px=3.0, rdp_epsilon=0.8)

    assert len(pred_strokes) > 0

    # Convert GT mm to image px (8.0 px/mm, Y inverted from 360 px)
    gt_strokes_px = [
        [{"x": pt["x"] * 8.0, "y": 360.0 - pt["y"] * 8.0} for pt in s] for s in gt_data["strokes"]
    ]

    chamfer, _p2g, _g2p = compute_chamfer_distance(pred_strokes, gt_strokes_px)
    assert chamfer <= 2.5, f"Expected Chamfer distance <= 2.5 px, got {chamfer:.2f} px"


def test_profile_builder_extracts_all_cells() -> None:
    """Verify profile builder successfully parses Caveat sample sheet."""
    sheet_png = REPO_ROOT / "tests/fixtures/sample_sheet_caveat.png"
    sheet_json = REPO_ROOT / "tests/fixtures/sample_sheet_caveat.json"

    profile = build_profile_from_sheet(sheet_png, sheet_json, source_name="Caveat")

    assert len(profile.glyph_bank) == 64
    assert "a" in profile.glyph_bank
    assert "Z" in profile.glyph_bank
    assert "9" in profile.glyph_bank


def test_glyph_bank_synthesis_legibility_and_bounds() -> None:
    """Verify Approach A synthesizes valid plotter strokes with zero NaNs."""
    profile = StyleProfile(
        source_name="TestMinimal",
        stats=StyleStats(slant_deg=0.0, letter_spacing_mm=1.0, word_spacing_mm=3.0),
        glyph_bank={},
    )
    synth = GlyphBankSynthesizer(seed=42)
    res = synth.synthesize("Hello PenPress 123", profile, font_size_mm=5.0)

    assert len(res.strokes) > 0
    assert res.total_length_mm > 0.0
    assert res.pen_lifts_count == len(res.strokes)

    # Check for valid coordinates
    for st in res.strokes:
        for pt in st.points:
            assert not (pt.x != pt.x or pt.y != pt.y)  # No NaNs
            assert 0.0 <= pt.x <= 200.0
            assert 0.0 <= pt.y <= 250.0
