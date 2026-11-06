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
    "sam.pdf": "https://arxiv.org/pdf/2304.02643",
    "depth_anything.pdf": "https://arxiv.org/pdf/2401.10891",
    "vggt.pdf": "https://arxiv.org/pdf/2503.11651",
    "grounding_dino.pdf": "https://arxiv.org/pdf/2303.05499",
    "nerf.pdf": "https://arxiv.org/pdf/2003.08934",
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
