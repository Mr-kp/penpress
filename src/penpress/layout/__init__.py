"""Layout and document composer package for PenPress."""

from penpress.layout.composer import (
    A4_PRESET,
    A5_PRESET,
    ComposerResult,
    LayoutOverflowError,
    Margins,
    PageComposer,
    PaperPreset,
    RuledGridConfig,
)
from penpress.layout.keepout import (
    KeepoutPolygon,
    create_standard_a5_clip_keepouts,
)

__all__ = [
    "A4_PRESET",
    "A5_PRESET",
    "ComposerResult",
    "KeepoutPolygon",
    "LayoutOverflowError",
    "Margins",
    "PageComposer",
    "PaperPreset",
    "RuledGridConfig",
    "create_standard_a5_clip_keepouts",
]
