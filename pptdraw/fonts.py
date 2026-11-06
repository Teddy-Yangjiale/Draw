"""Cross-platform font discovery.

Measurement needs a font file that covers Latin + CJK.  The PPTX itself keeps
using editable font names, which PowerPoint/WPS can substitute on the target
machine.  Users can override everything with environment variables.
"""

from __future__ import annotations

import os
import platform
from functools import lru_cache
from pathlib import Path


def _candidates() -> list[str]:
    env = os.environ.get("PPT_DRAW_FONT")
    system = platform.system()
    candidates = [env] if env else []
    if system == "Darwin":
        candidates += [
            "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
            "/Library/Fonts/Arial Unicode.ttf",
            "/System/Library/Fonts/Hiragino Sans GB.ttc",
            "/System/Library/Fonts/STHeiti Light.ttc",
            "/System/Library/Fonts/Supplemental/Arial.ttf",
        ]
    elif system == "Windows":
        candidates += [
            r"C:\Windows\Fonts\arialuni.ttf",
            r"C:\Windows\Fonts\msyh.ttc",
            r"C:\Windows\Fonts\msyhbd.ttc",
            r"C:\Windows\Fonts\simhei.ttf",
            r"C:\Windows\Fonts\arial.ttf",
        ]
    else:
        candidates += [
            "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
            "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
            "/usr/share/fonts/opentype/noto/NotoSerifCJK-Regular.ttc",
            "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
            "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        ]
    # Last-resort paths that appear on some minimal Linux images.
    candidates += [
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        "/usr/share/fonts/TTF/DejaVuSans.ttf",
    ]
    return [c for c in candidates if c]


@lru_cache(maxsize=1)
def font_path() -> str:
    """Return a Unicode-capable measurement font file, or raise."""
    for candidate in _candidates():
        if candidate and Path(candidate).exists():
            return candidate
    raise RuntimeError(
        "No measurement font found. Set PPT_DRAW_FONT to a Unicode .ttf/.ttc file "
        "(for example Noto Sans CJK, Arial Unicode, or Microsoft YaHei)."
    )


def latin_font() -> str:
    return os.environ.get("PPT_DRAW_PPT_FONT", "Arial")


def ea_font() -> str:
    override = os.environ.get("PPT_DRAW_EA_FONT")
    if override:
        return override
    system = platform.system()
    if system == "Windows":
        # Arial Unicode MS ships with Office; Microsoft YaHei is present on
        # virtually every Windows install and is the safer CJK fallback.
        if Path(r"C:\Windows\Fonts\arialuni.ttf").exists():
            return "Arial Unicode MS"
        return "Microsoft YaHei"
    if system == "Linux":
        if Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc").exists() or Path(
            "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc"
        ).exists():
            return "Noto Sans CJK SC"
    return "Arial Unicode MS"


def describe() -> dict:
    system = platform.system()
    found = []
    for candidate in _candidates():
        if Path(candidate).exists():
            found.append(candidate)
            if len(found) >= 4:
                break
    return {
        "system": system,
        "measurement": next((c for c in _candidates() if Path(c).exists()), None),
        "candidates_found": found,
        "pptx_latin": latin_font(),
        "pptx_east_asian": ea_font(),
    }
