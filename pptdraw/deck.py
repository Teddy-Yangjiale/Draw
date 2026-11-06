"""Create a blank, paper-sized figure deck."""

from __future__ import annotations

from pathlib import Path

from pptx import Presentation
from pptx.util import Inches

from . import pptxutil as pu

PRESETS = {
    "double": (7.16, 3.2),   # IEEE / CVPR double-column text width
    "single": (3.5, 2.4),    # single-column
    "cvpr": (7.16, 2.6),
    "wide": (10.0, 4.0),
    "slide": (13.333, 7.5),
}


def parse_size(value: str) -> tuple[float, float]:
    try:
        width, height = value.lower().split("x")
        return float(width), float(height)
    except Exception as exc:
        raise ValueError("size must look like 7.16x3.2 (inches)") from exc


def new_deck(
    path: str | Path,
    *,
    size: tuple[float, float] = PRESETS["double"],
    title: str = "Paper figure",
) -> Path:
    if size[0] <= 0 or size[1] <= 0:
        raise ValueError("slide size must be positive")
    prs = Presentation()
    prs.slide_width = Inches(size[0])
    prs.slide_height = Inches(size[1])
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    pu.set_background(slide, "FFFFFF")
    prs.core_properties.title = title
    prs.core_properties.author = "pptdraw"
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    prs.save(str(out))
    return out
