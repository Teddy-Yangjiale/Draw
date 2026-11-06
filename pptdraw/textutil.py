"""Text measurement and wrapping without PowerPoint.

PowerPoint itself is the final renderer, but the layout/lint layer needs to know
whether a label fits.  We use a Unicode font so mixed Chinese/English figures are
measured with the same metrics the preview will roughly use.
"""

from __future__ import annotations

import re
from functools import lru_cache

from PIL import ImageFont

from .fonts import font_path

SCALE = 8  # measure at 8x to reduce hinting noise
_CJK = re.compile(
    r"[\u1100-\u11ff\u2e80-\u9fff\uac00-\ud7af\uf900-\ufaff\uff00-\uffef]"
)


@lru_cache(maxsize=256)
def _font(size_px: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(font_path(), size_px)


def _is_cjk(ch: str) -> bool:
    return bool(_CJK.match(ch))


def _tokens(text: str) -> list[str]:
    """Split a paragraph into breakable units.

    CJK characters break individually; Latin words stay together; spaces are
    preserved as their own tokens.
    """
    out: list[str] = []
    buf = ""
    for ch in text:
        if ch == " " or _is_cjk(ch):
            if buf:
                out.append(buf)
                buf = ""
            out.append(ch)
        else:
            buf += ch
    if buf:
        out.append(buf)
    return out


def wrap_text(text: str, font_size: float, max_width: float) -> list[str]:
    """Greedy wrap. ``max_width`` is in inches, ``font_size`` in points."""
    if max_width <= 0:
        return [text]
    font = _font(max(1, round(font_size * SCALE)))
    max_px = max_width * 72 * SCALE
    lines: list[str] = []

    for paragraph in str(text).split("\n"):
        if paragraph == "":
            lines.append("")
            continue
        current = ""
        for token in _tokens(paragraph):
            if token == " ":
                if current and not current.endswith(" "):
                    current += " "
                continue
            candidate = current + token
            if font.getlength(candidate) <= max_px:
                current = candidate
                continue

            if current.strip():
                lines.append(current.rstrip())
            current = ""

            if font.getlength(token) > max_px:
                # A single very long word: hard-break it by character.
                for ch in token:
                    if font.getlength(current + ch) <= max_px or not current:
                        current += ch
                    else:
                        lines.append(current)
                        current = ch
            else:
                current = token

        if current.strip():
            lines.append(current.rstrip())
        elif paragraph == "":
            lines.append("")

    return lines or [""]


def line_height(font_size: float) -> float:
    """Approximate PowerPoint single-spaced line height, in inches."""
    font = _font(max(1, round(font_size * SCALE)))
    ascent, descent = font.getmetrics()
    return (ascent + descent) / (72 * SCALE)


def text_width(text: str, font_size: float) -> float:
    font = _font(max(1, round(font_size * SCALE)))
    widest = 0.0
    for line in str(text).split("\n"):
        widest = max(widest, font.getlength(line) / (72 * SCALE))
    return widest


def block_size(
    text: str, font_size: float, max_width: float
) -> tuple[float, float, list[str]]:
    """Return (width, height, wrapped_lines) for a text block in inches."""
    lines = wrap_text(text, font_size, max_width)
    width = max((text_width(line, font_size) for line in lines), default=0.0)
    height = max(1, len(lines)) * line_height(font_size)
    return width, height, lines


def auto_box(
    text: str,
    font_size: float,
    min_width: float = 0.8,
    max_width: float = 1.9,
    pad_x: float = 0.16,
    pad_y: float = 0.14,
    min_height: float = 0.42,
) -> tuple[float, float]:
    """Suggest a box size for a module label."""
    natural_w = text_width(text, font_size)
    inner_w = min(max_width, max(min_width, natural_w + 0.02))
    _, height, _ = block_size(text, font_size, inner_w - pad_x)
    width = max(min_width, min(max_width, natural_w + pad_x))
    return round(width, 3), round(max(min_height, height + pad_y), 3)
