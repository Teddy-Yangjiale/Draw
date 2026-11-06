"""Build the three 16-figure overview sheets (CVPR/ICCV/ECCV, AI venues, SIGGRAPH/3D)."""

from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from pptdraw.fonts import font_path  # noqa: E402

FONT = font_path()
HEAD = ImageFont.truetype(FONT, 40)
TITLE = ImageFont.truetype(FONT, 22)
SMALL = ImageFont.truetype(FONT, 18)
NOTE = ImageFont.truetype(FONT, 19)

SHEETS = {
    "research/sheet_cvpr_iccv_eccv_16.png": (
        "CVPR / ICCV / ECCV · 16 figures",
        "视觉三大主会：架构、两阶段、3D 与结果图混排",
        [
            ("SAM", "ICCV 2023 · Fig. 4", "crops/sam.png", "pipeline"),
            ("Depth Anything", "CVPR 2024 · Fig. 2", "crops/depth_anything.png", "pipeline"),
            ("VGGT", "CVPR 2025 · Fig. 2", "crops/vggt.png", "pipeline"),
            ("Grounding DINO", "ECCV 2024 · Fig. 3", "crops/grounding_dino.png", "zoom-in"),
            ("NeRF", "CVPR 2020 · Fig. 2", "crops/nerf.png", "3D"),
            ("4D Gaussian Splatting", "CVPR 2024 · Fig. 2", "crops/4dgs_pipeline.png", "3D"),
            ("Mask2Former", "CVPR 2022 · Fig. 2", "crops/new_mask2former.png", "architecture"),
            ("GLIP", "CVPR 2022 · Fig. 2", "crops/new_glip.png", "architecture"),
            ("ControlNet", "ICCV 2023 · Fig. 2", "crops/new_controlnet.png", "two-stage"),
            ("Latent Diffusion", "CVPR 2022 · Fig. 3", "crops/new_ldm.png", "architecture"),
            ("Mip-NeRF 360", "CVPR 2022 · Fig. 3", "crops/new_mipnerf360.png", "architecture"),
            ("NeRF-W", "CVPR 2021 · Fig. 3", "crops/new_nerfw.png", "architecture"),
            ("Zero-1-to-3", "ICCV 2023 · Fig. 3", "crops/new_zero123.png", "3D"),
            ("Plenoxels", "CVPR 2022 · Fig. 2", "crops/new_plenoxels.png", "3D"),
            ("Mip-Splatting", "CVPR 2024 · Fig. 1", "crops/new_mipsplatting.png", "concept"),
            ("GaussianEditor", "CVPR 2024 · Fig. 1", "crops/new_gaussianeditor.png", "result"),
        ],
    ),
    "research/sheet_aaai_neurips_iclr_icml_16.png": (
        "AAAI / NeurIPS / ICLR / ICML · 16 figures",
        "AI 顶会：表征学习、两阶段 VLM、扩散/一致性、推理与结果",
        [
            ("HQ-SAM", "NeurIPS 2023 · Fig. 3", "crops/hq_sam.png", "two-stage"),
            ("BLIP-2", "ICML 2023 · Fig. 1", "crops/blip2.png", "two-stage"),
            ("Consistency Models", "ICML 2023 · Fig. 1", "crops/consistency_models.png", "concept"),
            ("LoRA", "ICLR 2022 · Fig. 1", "crops/lora.png", "concept"),
            ("DreamFusion", "ICLR 2023 · Fig. 3", "crops/dreamfusion.png", "3D"),
            ("SOIT", "AAAI 2022 · Fig. 2", "crops/soit.png", "architecture"),
            ("EOV-Seg", "AAAI 2025 · Fig. 4", "crops/eov_seg.png", "zoom-in"),
            ("Diffusion Models Beat GANs", "NeurIPS 2021 · Fig. 1", "crops/diffusion_beat_gans_grid.png", "result"),
            ("DINO", "ICLR 2023 · Fig. 2", "crops/new_dino.png", "architecture"),
            ("SAM 2", "ICLR 2025 · Fig. 1", "crops/new_sam2.png", "overview"),
            ("ViLT", "ICML 2021 · Fig. 3", "crops/new_vilt.png", "architecture"),
            ("BEiT-3", "ICML 2023 · Fig. 2", "crops/new_beit3.png", "architecture"),
            ("Flamingo", "NeurIPS 2022 · Fig. 3", "crops/new_flamingo.png", "two-stage"),
            ("DreamGaussian", "ICLR 2024 · Fig. 2", "crops/new_dreamgaussian.png", "3D"),
            ("Point-E", "NeurIPS 2022 · Fig. 1", "crops/new_pointe.png", "3D"),
            ("Imagen", "NeurIPS 2022 · Fig. 1", "crops/new_imagen.png", "result"),
        ],
    ),
    "research/sheet_siggraph_3d_16.png": (
        "SIGGRAPH · 3D · graphics & qualitative · 16 figures",
        "3D/渲染/Gaussian/NeRF 与结果图：PPT 只画外层，主体用渲染图",
        [
            ("3D Gaussian Splatting", "SIGGRAPH 2023 · Fig. 2", "crops/3dgs.png", "3D"),
            ("Instant NGP", "SIGGRAPH 2022 · Fig. 3", "crops/instant_ngp.png", "steps"),
            ("NeRF", "CVPR 2020 · Fig. 2", "crops/nerf.png", "3D"),
            ("4D Gaussian Splatting", "CVPR 2024 · Fig. 1", "crops/4dgs_concept.png", "3D"),
            ("DreamFusion", "ICLR 2023 · Fig. 3", "crops/dreamfusion.png", "3D"),
            ("Latent Diffusion", "CVPR 2022 · Fig. 3", "crops/new_ldm.png", "3D"),
            ("Mip-NeRF 360", "CVPR 2022 · Fig. 3", "crops/new_mipnerf360.png", "3D"),
            ("NeRF-W", "CVPR 2021 · Fig. 3", "crops/new_nerfw.png", "3D"),
            ("DreamGaussian", "ICLR 2024 · Fig. 2", "crops/new_dreamgaussian.png", "3D"),
            ("Zero-1-to-3", "ICCV 2023 · Fig. 3", "crops/new_zero123.png", "3D"),
            ("Point-E", "NeurIPS 2022 · Fig. 1", "crops/new_pointe.png", "3D"),
            ("Plenoxels", "CVPR 2022 · Fig. 2", "crops/new_plenoxels.png", "3D"),
            ("Mip-Splatting", "CVPR 2024 · Fig. 1", "crops/new_mipsplatting.png", "concept"),
            ("GaussianEditor", "CVPR 2024 · Fig. 1", "crops/new_gaussianeditor.png", "result"),
            ("Diffusion Models Beat GANs", "NeurIPS 2021 · Fig. 1", "crops/diffusion_beat_gans_grid.png", "result"),
            ("Depth Anything", "CVPR 2024 · Fig. 2", "crops/depth_anything.png", "result"),
        ],
    ),
}


def fit(im: Image.Image, width: int, height: int) -> Image.Image:
    return ImageOps.pad(im, (width, height), color="white", method=Image.LANCZOS)


def make(path: Path, title: str, subtitle: str, items: list[tuple]):
    cols, rows = 4, 4
    thumb_w, thumb_h = 440, 300
    gap = 24
    pad = 34
    label_h = 64
    cell_w, cell_h = thumb_w, thumb_h + label_h
    W = pad * 2 + cols * cell_w + (cols - 1) * gap
    H = 110 + pad + rows * cell_h + (rows - 1) * gap + 90
    sheet = Image.new("RGB", (W, H), "white")
    d = ImageDraw.Draw(sheet)
    d.text((pad, 26), title, font=HEAD, fill=(24, 30, 38))
    d.text((pad, 74), subtitle, font=NOTE, fill=(95, 106, 116))
    for i, (name, venue, rel, tag) in enumerate(items):
        row, col = divmod(i, cols)
        x = pad + col * (cell_w + gap)
        y = 120 + row * (cell_h + gap)
        im = Image.open(ROOT / "research" / rel).convert("RGB")
        im = fit(im, thumb_w, thumb_h)
        sheet.paste(im, (x, y))
        d.rectangle((x, y, x + thumb_w, y + thumb_h), outline=(218, 225, 232), width=2)
        d.text((x, y + thumb_h + 8), name, font=TITLE, fill=(24, 30, 38))
        d.text((x, y + thumb_h + 35), venue, font=SMALL, fill=(100, 110, 120))
        tag_w = d.textlength(tag, font=SMALL) + 14
        d.rounded_rectangle(
            (x + thumb_w - tag_w, y + 6, x + thumb_w - 6, y + 30),
            radius=6,
            fill=(238, 244, 250),
        )
        d.text((x + thumb_w - tag_w + 7, y + 9), tag, font=SMALL, fill=(60, 90, 120))
    d.text(
        (pad, H - 54),
        "Screenshots for figure-drawing research; see research/figure_analysis.md and docs/figure_playbook.md",
        font=NOTE,
        fill=(120, 128, 136),
    )
    sheet.save(path, optimize=True)
    print(path, sheet.size)


def main() -> None:
    for path, (title, subtitle, items) in SHEETS.items():
        assert len(items) == 16, (path, len(items))
        make(ROOT / path, title, subtitle, items)


if __name__ == "__main__":
    main()
