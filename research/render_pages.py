"""Render the reference pages used for the figure analysis (optional).

Requires PyMuPDF:  python -m pip install pymupdf
"""

from __future__ import annotations

import sys
from pathlib import Path

import pymupdf

PAGES = {
    "sam": [5, 16],
    "depth_anything": [1, 3, 4, 5],
    "vggt": [1, 3],
    "grounding_dino": [1, 2, 3, 5],
    "nerf": [1, 2, 3, 5],
    "4dgs": [2, 4],
    "hq_sam": [4],
    "diffusion_beat_gans": [1],
    "lora": [1],
    "dreamfusion": [5],
    "blip2": [1],
    "consistency_models": [1],
    "soit": [3],
    "eov_seg": [4],
    "3dgs": [5],
    "instant_ngp": [4],
    "dino": [6],
    "mask2former": [3],
    "glip": [2],
    "controlnet": [3],
    "latent_diffusion": [4, 5],
    "mipnerf360": [1, 4],
    "nerfw": [1, 3],
    "zero123": [3],
    "plenoxels": [1, 3],
    "mipsplatting": [1],
    "gaussianeditor": [1, 4],
    "sam2": [2],
    "vilt": [4],
    "beit3": [3],
    "flamingo": [4],
    "imagen": [2],
    "dreamgaussian": [1, 4],
    "pointe": [2],
}


def main() -> int:
    base = Path(__file__).resolve().parent
    pdf_dir = base / "papers"
    out_dir = base / "pages"
    out_dir.mkdir(exist_ok=True)
    for name, pages in PAGES.items():
        pdf = pdf_dir / f"{name}.pdf"
        if not pdf.exists():
            print(f"skip {name}: run research/download_papers.py first")
            continue
        doc = pymupdf.open(pdf)
        for page_no in pages:
            if page_no < 1 or page_no > doc.page_count:
                continue
            pix = doc[page_no - 1].get_pixmap(dpi=180, alpha=False)
            target = out_dir / f"{name}_p{page_no}.png"
            pix.save(target)
            print(target)
    return 0


if __name__ == "__main__":
    sys.exit(main())
