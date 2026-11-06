"""Generate contact sheets for the expanded paper-figure study."""

from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from pptdraw.fonts import font_path  # noqa: E402

FONT = font_path()
TITLE = ImageFont.truetype(FONT, 25)
SMALL = ImageFont.truetype(FONT, 20)
HEAD = ImageFont.truetype(FONT, 38)

ITEMS = [
    ("SAM", "ICCV 2023 · Fig. 4", "crops/sam.png", "architecture"),
    ("Depth Anything", "CVPR 2024 · Fig. 2", "crops/depth_anything.png", "architecture"),
    ("VGGT", "CVPR 2025 · Fig. 2", "crops/vggt.png", "architecture"),
    ("Grounding DINO", "ECCV 2024 · Fig. 3", "crops/grounding_dino.png", "zoom-in"),
    ("NeRF", "CVPR 2020 · Fig. 2", "crops/nerf.png", "3d"),
    ("4D Gaussian Splatting", "CVPR 2024 · Fig. 1", "crops/4dgs_concept.png", "3d"),
    ("HQ-SAM", "NeurIPS 2023 · Fig. 3", "crops/hq_sam.png", "two-stage"),
    ("Diffusion Models Beat GANs", "NeurIPS 2021 · Fig. 1", "crops/diffusion_beat_gans_grid.png", "result grid"),
    ("LoRA", "ICLR 2022 · Fig. 1", "crops/lora.png", "concept"),
    ("DreamFusion", "ICLR 2023 · Fig. 3", "crops/dreamfusion.png", "3d"),
    ("BLIP-2", "ICML 2023 · Fig. 1", "crops/blip2.png", "two-stage"),
    ("Consistency Models", "ICML 2023 · Fig. 1", "crops/consistency_models.png", "concept"),
    ("SOIT", "AAAI 2022 · Fig. 2", "crops/soit.png", "architecture"),
    ("EOV-Seg", "AAAI 2025 · Fig. 4", "crops/eov_seg.png", "zoom-in"),
    ("3D Gaussian Splatting", "SIGGRAPH 2023 · Fig. 2", "crops/3dgs.png", "architecture"),
    ("Instant NGP", "SIGGRAPH 2022 · Fig. 3", "crops/instant_ngp.png", "steps"),
]


def fit(im: Image.Image, width: int, height: int) -> Image.Image:
    return ImageOps.pad(im, (width, height), color="white", method=Image.LANCZOS)


def make_gallery(path: Path, items: list[tuple], cols: int, thumb_w: int, thumb_h: int, title: str):
    pad = 28
    label_h = 58
    cell_w = thumb_w
    cell_h = thumb_h + label_h
    rows = (len(items) + cols - 1) // cols
    W = pad * 2 + cols * cell_w + (cols - 1) * pad
    H = 88 + pad + rows * cell_h + (rows - 1) * pad + pad
    sheet = Image.new("RGB", (W, H), "white")
    d = ImageDraw.Draw(sheet)
    d.text((pad, 24), title, font=HEAD, fill=(24, 30, 38))
    for i, (name, venue, rel, tag) in enumerate(items):
        row, col = divmod(i, cols)
        x = pad + col * (cell_w + pad)
        y = 88 + pad + row * (cell_h + pad)
        im = Image.open(ROOT / "research" / rel).convert("RGB")
        im = fit(im, thumb_w, thumb_h)
        sheet.paste(im, (x, y))
        d.rectangle((x, y, x + thumb_w, y + thumb_h), outline=(220, 226, 232), width=2)
        d.text((x, y + thumb_h + 8), name, font=TITLE, fill=(24, 30, 38))
        d.text((x, y + thumb_h + 36), venue, font=SMALL, fill=(100, 110, 120))
        tag_w = d.textlength(tag, font=SMALL) + 14
        d.rounded_rectangle(
            (x + thumb_w - tag_w, y + 6, x + thumb_w - 6, y + 30),
            radius=6,
            fill=(238, 244, 250),
        )
        d.text((x + thumb_w - tag_w + 7, y + 9), tag, font=SMALL, fill=(60, 90, 120))
    sheet.save(path, optimize=True)
    print(path, sheet.size)


def main() -> None:
    arch = [i for i in ITEMS if i[3] in ("architecture", "two-stage", "zoom-in", "steps")]
    concepts = [i for i in ITEMS if i[3] in ("concept", "3d", "result grid", "zoom-in")]
    make_gallery(ROOT / "research/figure_gallery_all.png", ITEMS, 4, 360, 230, "16 paper figures across CVPR / AAAI / NeurIPS / ICLR / ICML / SIGGRAPH")
    make_gallery(ROOT / "research/figure_gallery_architecture.png", arch, 2, 980, 430, "Architecture, two-stage, zoom-in and step-by-step figures")
    make_gallery(ROOT / "research/figure_gallery_concepts.png", concepts, 2, 980, 430, "Concept, 3D and result-grid figures")


if __name__ == "__main__":
    main()
