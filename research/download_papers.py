"""Download the five reference PDFs used in research/figure_analysis.md.

The PDFs are intentionally not committed to git (they are ~42 MB).  The cropped
figures and the analysis sheet are committed, so a fresh clone can read the
analysis without downloading anything.
"""

from __future__ import annotations

import sys
import urllib.request
from pathlib import Path

PAPERS = {
    # CVPR / ICCV / ECCV
    "sam.pdf": "https://arxiv.org/pdf/2304.02643",
    "depth_anything.pdf": "https://arxiv.org/pdf/2401.10891",
    "vggt.pdf": "https://arxiv.org/pdf/2503.11651",
    "grounding_dino.pdf": "https://arxiv.org/pdf/2303.05499",
    "nerf.pdf": "https://arxiv.org/pdf/2003.08934",
    "4dgs.pdf": "https://arxiv.org/pdf/2310.10642",
    # NeurIPS
    "hq_sam.pdf": "https://arxiv.org/pdf/2306.01567",
    "diffusion_beat_gans.pdf": "https://arxiv.org/pdf/2105.05233",
    # ICLR
    "lora.pdf": "https://arxiv.org/pdf/2106.09685",
    "dreamfusion.pdf": "https://arxiv.org/pdf/2209.14988",
    # ICML
    "blip2.pdf": "https://arxiv.org/pdf/2301.12597",
    "consistency_models.pdf": "https://arxiv.org/pdf/2303.01469",
    # AAAI
    "soit.pdf": "https://arxiv.org/pdf/2112.11037",
    "eov_seg.pdf": "https://arxiv.org/pdf/2412.08628",
    # SIGGRAPH
    "3dgs.pdf": "https://arxiv.org/pdf/2308.04079",
    "instant_ngp.pdf": "https://arxiv.org/pdf/2201.05989",
    # Second expansion: CVPR / ICCV / ECCV
    "dino.pdf": "https://arxiv.org/pdf/2203.03605",
    "mask2former.pdf": "https://arxiv.org/pdf/2112.01527",
    "glip.pdf": "https://arxiv.org/pdf/2112.03857",
    "controlnet.pdf": "https://arxiv.org/pdf/2302.05543",
    "latent_diffusion.pdf": "https://arxiv.org/pdf/2112.10752",
    "mipnerf360.pdf": "https://arxiv.org/pdf/2111.12077",
    "nerfw.pdf": "https://arxiv.org/pdf/2008.02268",
    "zero123.pdf": "https://arxiv.org/pdf/2303.11328",
    "plenoxels.pdf": "https://arxiv.org/pdf/2112.05131",
    "mipsplatting.pdf": "https://arxiv.org/pdf/2311.16493",
    "gaussianeditor.pdf": "https://arxiv.org/pdf/2311.14521",
    # Second expansion: AAAI / NeurIPS / ICLR / ICML / SIGGRAPH-adjacent
    "sam2.pdf": "https://arxiv.org/pdf/2408.00714",
    "vilt.pdf": "https://arxiv.org/pdf/2102.03334",
    "beit3.pdf": "https://arxiv.org/pdf/2208.10442",
    "flamingo.pdf": "https://arxiv.org/pdf/2204.14198",
    "imagen.pdf": "https://arxiv.org/pdf/2205.11487",
    "dreamgaussian.pdf": "https://arxiv.org/pdf/2309.16653",
    "pointe.pdf": "https://arxiv.org/pdf/2212.08751",
}


def main() -> int:
    out = Path(__file__).resolve().parent / "papers"
    out.mkdir(parents=True, exist_ok=True)
    for name, url in PAPERS.items():
        target = out / name
        if target.exists() and target.stat().st_size > 100_000:
            print(f"skip {name} (already exists)")
            continue
        print(f"download {name} ...")
        request = urllib.request.Request(
            url,
            headers={"User-Agent": "pptdraw-research/0.1 (academic figure analysis)"},
        )
        with urllib.request.urlopen(request, timeout=120) as response:
            target.write_bytes(response.read())
        print(f"  {target} ({target.stat().st_size / 1e6:.1f} MB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
