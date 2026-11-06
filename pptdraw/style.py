"""Paper-friendly style presets.

Derived from the visual grammar of CVPR/ICCV/ECCV architecture figures:
low-saturation fills, one shade darker for the outline, dark text, no shadows.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Style:
    fill: str | None
    line: str | None
    text: str
    dash: str = "solid"
    bold: bool = False
    line_width: float = 1.0


STYLES: dict[str, Style] = {
    # Neutral module: very common in pipeline figures.
    "plain": Style("#FFFFFF", "#3F4B57", "#1E2833"),
    "neutral": Style("#F2F0EC", "#B8B1A6", "#2B2B2B"),
    # A small, restrained palette. Fill/line pairs are deliberately related.
    "blue": Style("#DCEBF7", "#5B8DB8", "#1E3A52"),
    "primary": Style("#DCEBF7", "#5B8DB8", "#1E3A52"),
    "green": Style("#DFF0E4", "#6A9E7A", "#1F3D2A"),
    "success": Style("#DFF0E4", "#6A9E7A", "#1F3D2A"),
    "orange": Style("#FBE7D8", "#C98A62", "#4D2A18"),
    "accent": Style("#FBE7D8", "#C98A62", "#4D2A18"),
    "purple": Style("#ECE4F4", "#8E76B0", "#372849"),
    "yellow": Style("#F7EFC9", "#C2A64B", "#463A12"),
    "warning": Style("#F7EFC9", "#C2A64B", "#463A12"),
    "gray": Style("#F4F5F6", "#AAB2BA", "#3B4652"),
    "muted": Style("#F4F5F6", "#AAB2BA", "#3B4652"),
    "dark": Style("#3A4654", "#3A4654", "#FFFFFF"),
    # Semantic roles.
    "note": Style("#FFFDF5", "#C2AC73", "#4A3D1A", dash="dash"),
    "container": Style("#FBFCFD", "#C9D2DA", "#66727E", dash="dash"),
    "text": Style(None, None, "#1E2833"),
    "loss": Style(None, None, "#C05243"),
}

DASHES = {"solid": None, "dash": "dash", "dot": "sysDot", "dashdot": "dashDot"}


def get_style(name: str | None) -> Style:
    key = name or "plain"
    try:
        return STYLES[key]
    except KeyError as exc:
        raise ValueError(
            f"unknown style {key!r}; choose from {', '.join(sorted(STYLES))}"
        ) from exc


# A compact, colorblind-safe rotation for multi-branch figures.
SERIES = ["blue", "green", "orange", "purple", "yellow", "gray"]
