"""Build a CVPR-style demo figure and a small round-trip edit.

The demo is intentionally similar to the visual grammar found in the reference
papers: one horizontal pipeline, pastel native modules, a dashed repeat block,
attached arrows, photographic inputs/outputs, and a skip connection.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw
from pptx import Presentation
from pptx.util import Inches

from . import pptxutil as pu
from .deck import PRESETS, new_deck
from .ops import apply_ops


def _gradient(size, top, bottom) -> Image.Image:
    w, h = size
    arr = np.zeros((h, w, 3), dtype=np.uint8)
    top = np.array(top, dtype=float)
    bottom = np.array(bottom, dtype=float)
    for y in range(h):
        t = y / max(1, h - 1)
        arr[y, :, :] = (top * (1 - t) + bottom * t).astype(np.uint8)
    return Image.fromarray(arr, "RGB")


def _make_input(path: Path) -> None:
    scale = 2
    w, h = 800 * scale, 500 * scale
    im = _gradient((w, h), (174, 205, 231), (242, 246, 250))
    d = ImageDraw.Draw(im)
    # ground
    d.polygon([(0, int(h * 0.62)), (w, int(h * 0.55)), (w, h), (0, h)], fill=(205, 192, 171))
    d.line(
        [(0, int(h * 0.62)), (w, int(h * 0.56))],
        fill=(150, 140, 125),
        width=3 * scale,
    )
    # building block
    x0, x1 = int(w * 0.31), int(w * 0.68)
    y0, y1 = int(h * 0.20), int(h * 0.66)
    d.rectangle((x0, y0, x1, y1), fill=(218, 206, 190), outline=(120, 112, 100), width=2 * scale)
    d.rectangle((x0 - 10 * scale, y0 - 12 * scale, x1 + 10 * scale, y0 + 8 * scale), fill=(160, 154, 145))
    # windows
    cols, rows = 4, 5
    for r in range(rows):
        for c in range(cols):
            wx0 = x0 + int((c + 0.22) * (x1 - x0) / cols)
            wx1 = x0 + int((c + 0.78) * (x1 - x0) / cols)
            wy0 = y0 + int((r + 0.22) * (y1 - y0) / rows) + 20 * scale
            wy1 = y0 + int((r + 0.78) * (y1 - y0) / rows) + 20 * scale
            d.rectangle((wx0, wy0, wx1, wy1), fill=(92, 116, 138), outline=(70, 82, 96), width=scale)
    # door
    d.rectangle((int(w * 0.47), int(h * 0.53), int(w * 0.53), int(h * 0.66)), fill=(111, 92, 73))
    # trees
    for cx, cy, r in [(110, 370, 55), (150, 350, 45), (690, 360, 65)]:
        d.ellipse(
            ((cx - r) * scale, (cy - r) * scale, (cx + r) * scale, (cy + r) * scale),
            fill=(122, 148, 113),
        )
        d.rectangle(
            ((cx - 6) * scale, (cy + r - 8) * scale, (cx + 6) * scale, (cy + r + 45) * scale),
            fill=(120, 96, 76),
        )
    im = im.resize((800, 500), Image.LANCZOS)
    im.save(path)


def _make_depth(path: Path) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    w, h = 800, 500
    yy, xx = np.mgrid[0:h, 0:w]
    depth = 0.08 + 0.9 * (yy / h) ** 1.4
    facade = (xx > w * 0.30) & (xx < w * 0.70) & (yy > h * 0.18) & (yy < h * 0.66)
    depth[facade] = 0.18 + 0.25 * ((xx[facade] - w * 0.30) / (w * 0.40))
    depth += 0.03 * np.sin(xx / 33.0) * np.sin(yy / 41.0)
    fig = plt.figure(figsize=(8, 5), dpi=100)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.imshow(depth, cmap="magma", origin="upper")
    ax.axis("off")
    fig.savefig(path, dpi=100, facecolor="white")
    plt.close(fig)


def _make_points(path: Path) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    rng = np.random.default_rng(4)
    fig = plt.figure(figsize=(8, 5), dpi=100)
    ax = fig.add_subplot(111, projection="3d")
    fig.patch.set_facecolor("#FBFAF7")
    ax.set_facecolor("#FBFAF7")

    # ground plane
    n = 9000
    x = rng.uniform(-1.4, 1.4, n)
    y = rng.uniform(-1.0, 1.0, n)
    z = np.zeros(n) + rng.normal(0, 0.01, n)
    ax.scatter(x, y, z, c="#8FA3B0", s=0.8, alpha=0.55, linewidths=0)

    # front facade
    n = 8000
    wx = rng.uniform(-0.5, 0.5, n)
    wz = rng.uniform(0, 1.1, n)
    wy = np.full(n, -0.6) + rng.normal(0, 0.008, n)
    ax.scatter(wx, wy, wz, c=wz, cmap="viridis", s=1.4, linewidths=0)

    # side wall
    n = 5000
    sy = rng.uniform(-0.6, 0.2, n)
    sz = rng.uniform(0, 1.1, n)
    sx = np.full(n, 0.5) + rng.normal(0, 0.008, n)
    ax.scatter(sx, sy, sz, c=sz, cmap="viridis", s=1.4, linewidths=0)

    # roof
    n = 3000
    rx = rng.uniform(-0.5, 0.5, n)
    ry = rng.uniform(-0.6, 0.2, n)
    rz = np.full(n, 1.1) + rng.normal(0, 0.008, n)
    ax.scatter(rx, ry, rz, c="#2A788E", s=1.2, linewidths=0)

    ax.view_init(elev=20, azim=-68)
    ax.set_box_aspect((1.5, 1.0, 0.9))
    ax.set_axis_off()
    fig.savefig(
        path,
        dpi=100,
        facecolor="#FBFAF7",
        bbox_inches="tight",
        pad_inches=0.02,
    )
    plt.close(fig)

    # Trim the generous 3D axes margins so the thumbnail is legible at 0.7 in.
    image = Image.open(path).convert("RGB")
    arr = np.asarray(image).astype(int)
    bg = np.array([251, 250, 247])
    mask = np.abs(arr - bg).max(axis=2) > 8
    if mask.any():
        ys, xs = np.where(mask)
        pad = 8
        box = (
            max(0, int(xs.min()) - pad),
            max(0, int(ys.min()) - pad),
            min(image.width, int(xs.max()) + pad),
            min(image.height, int(ys.max()) + pad),
        )
        image.crop(box).save(path)


def ensure_assets(directory: str | Path) -> dict[str, str]:
    out = Path(directory)
    out.mkdir(parents=True, exist_ok=True)
    paths = {
        "input": out / "synthetic_input.png",
        "depth": out / "synthetic_depth.png",
        "points": out / "synthetic_points.png",
    }
    if not paths["input"].exists():
        _make_input(paths["input"])
    if not paths["depth"].exists():
        _make_depth(paths["depth"])
    if not paths["points"].exists():
        _make_points(paths["points"])
    return {k: str(v.resolve()) for k, v in paths.items()}


def demo_ops(assets: dict[str, str]) -> dict:
    shapes = [
        {
            "op": "add_text",
            "name": "fig.panel",
            "text": "(a) Overall architecture",
            "x": 0.20,
            "y": 0.08,
            "w": 2.6,
            "h": 0.24,
            "font_size": 9.0,
            "text_color": "5B6773",
            "bold": True,
            "align": "left",
            "anchor": "top",
        },
        {
            "op": "add_picture",
            "name": "fig.input",
            "path": assets["input"],
            "x": 0.20,
            "y": 0.84,
            "w": 0.94,
            "h": 0.60,
        },
        {
            "op": "add_text",
            "name": "fig.label.input",
            "text": "Input views",
            "x": 0.14,
            "y": 1.50,
            "w": 1.06,
            "h": 0.18,
            "font_size": 8.5,
            "text_color": "5B6773",
            "align": "center",
            "anchor": "top",
        },
        {
            "op": "add_shape",
            "name": "fig.encoder",
            "shape": "roundRect",
            "x": 1.38,
            "y": 0.90,
            "w": 1.18,
            "h": 0.58,
            "text": "Image\nEncoder",
            "style": "green",
            "font_size": 10.0,
        },
        # Attention stack (placed first, container is sent behind).
        {
            "op": "add_shape",
            "name": "fig.attn.frame",
            "shape": "roundRect",
            "x": 3.02,
            "y": 0.96,
            "w": 1.40,
            "h": 0.34,
            "text": "Frame-wise Attention",
            "style": "blue",
            "font_size": 9.0,
            "radius": 0.06,
        },
        {
            "op": "add_shape",
            "name": "fig.attn.global",
            "shape": "roundRect",
            "x": 3.02,
            "y": 1.38,
            "w": 1.40,
            "h": 0.34,
            "text": "Global Attention",
            "style": "blue",
            "font_size": 9.0,
            "radius": 0.06,
        },
        {
            "op": "add_container",
            "name": "fig.attention",
            "around": ["fig.attn.frame", "fig.attn.global"],
            "label": "Attention Block   × L",
            "padding": 0.12,
            "top_pad": 0.26,
            "style": "container",
        },
        {
            "op": "add_shape",
            "name": "fig.decoder",
            "shape": "roundRect",
            "x": 4.78,
            "y": 0.90,
            "w": 1.12,
            "h": 0.58,
            "text": "Task\nDecoder",
            "style": "orange",
            "font_size": 10.0,
        },
        {
            "op": "add_picture",
            "name": "fig.output.depth",
            "path": assets["depth"],
            "x": 6.16,
            "y": 0.70,
            "w": 0.72,
            "h": 0.48,
        },
        {
            "op": "add_text",
            "name": "fig.label.depth",
            "text": "Depth",
            "x": 6.05,
            "y": 1.18,
            "w": 0.94,
            "h": 0.15,
            "font_size": 8.0,
            "text_color": "5B6773",
            "align": "center",
            "anchor": "top",
        },
        {
            "op": "add_picture",
            "name": "fig.output.points",
            "path": assets["points"],
            "x": 6.16,
            "y": 1.42,
            "w": 0.72,
            "h": 0.48,
        },
        {
            "op": "add_text",
            "name": "fig.label.points",
            "text": "Point map",
            "x": 6.05,
            "y": 1.90,
            "w": 0.94,
            "h": 0.15,
            "font_size": 8.0,
            "text_color": "5B6773",
            "align": "center",
            "anchor": "top",
        },
        # Arrows (attached to the named shapes, so they follow human edits).
        {
            "op": "add_connector",
            "name": "fig.edge.input--encoder",
            "from": "fig.input",
            "to": "fig.encoder",
            "from_side": "right",
            "to_side": "left",
            "arrow": "end",
        },
        {
            "op": "add_connector",
            "name": "fig.edge.encoder--attention",
            "from": "fig.encoder",
            "to": "fig.attention",
            "from_side": "right",
            "to_side": "left",
            "arrow": "end",
        },
        {
            "op": "add_connector",
            "name": "fig.edge.attention--decoder",
            "from": "fig.attention",
            "to": "fig.decoder",
            "from_side": "right",
            "to_side": "left",
            "arrow": "end",
        },
        {
            "op": "add_connector",
            "name": "fig.edge.decoder--depth",
            "from": "fig.decoder",
            "to": "fig.output.depth",
            "from_side": "right",
            "to_side": "left",
            "arrow": "end",
        },
        {
            "op": "add_connector",
            "name": "fig.edge.decoder--points",
            "from": "fig.decoder",
            "to": "fig.output.points",
            "from_side": "right",
            "to_side": "left",
            "arrow": "end",
        },
        {
            "op": "add_detour",
            "name": "fig.edge.skip",
            "from": "fig.encoder",
            "to": "fig.decoder",
            "side": "bottom",
            "offset": 0.76,
            "dash": "dash",
            "arrow": "end",
            "label": "skip connection",
        },
        {"op": "normalize_z"},
    ]
    return {"slide": 1, "ops": shapes}


def build_demo(path: str | Path, asset_dir: str | Path = "out/assets") -> dict:
    assets = ensure_assets(asset_dir)
    deck = new_deck(path, size=PRESETS["cvpr"], title="CVPR-style demo")
    report = apply_ops(deck, demo_ops(assets), backup=False)
    report["assets"] = assets
    return report


def edit_ops() -> dict:
    """A small, realistic AI edit on the existing deck.

    It changes copy, adds a badge and a new prompt-token branch.  Nothing is
    regenerated from scratch, which is the point of the round-trip design.
    """
    return {
        "slide": 1,
        "ops": [
            {
                "op": "set_text",
                "name": "fig.encoder",
                "text": "Visual Encoder\n(ViT-B)",
                "font_size": 9.5,
            },
            {
                "op": "set_text",
                "name": "fig.decoder",
                "text": "Multi-Task\nDecoder",
                "font_size": 9.5,
            },
            {
                "op": "set_style",
                "name": "fig.decoder",
                "style": "accent",
            },
            {
                "op": "add_text",
                "name": "fig.badge.frozen",
                "text": "frozen",
                "x": 1.48,
                "y": 0.68,
                "w": 0.55,
                "h": 0.20,
                "font_size": 8.0,
                "text_color": "C05243",
                "align": "center",
                "anchor": "middle",
            },
            # A new camera-token branch above the attention block.
            {
                "op": "add_shape",
                "name": "fig.token.1",
                "shape": "roundRect",
                "x": 3.42,
                "y": 0.22,
                "w": 0.13,
                "h": 0.13,
                "style": "orange",
                "radius": 0.02,
            },
            {
                "op": "add_shape",
                "name": "fig.token.2",
                "shape": "roundRect",
                "x": 3.62,
                "y": 0.22,
                "w": 0.13,
                "h": 0.13,
                "style": "orange",
                "radius": 0.02,
            },
            {
                "op": "add_shape",
                "name": "fig.token.3",
                "shape": "roundRect",
                "x": 3.82,
                "y": 0.22,
                "w": 0.13,
                "h": 0.13,
                "style": "orange",
                "radius": 0.02,
            },
            {
                "op": "add_text",
                "name": "fig.label.tokens",
                "text": "camera tokens",
                "x": 3.12,
                "y": 0.04,
                "w": 1.15,
                "h": 0.16,
                "font_size": 8.0,
                "text_color": "5B6773",
                "align": "center",
                "anchor": "top",
            },
            {
                "op": "add_connector",
                "name": "fig.edge.tokens--attention",
                "from": "fig.token.2",
                "to": "fig.attention",
                "from_side": "bottom",
                "to_side": "top",
                "arrow": "end",
                "dash": "dash",
                "line_width": 0.9,
            },
            {"op": "normalize_z"},
        ],
    }


def simulate_human_edit(src: str | Path, dst: str | Path) -> dict:
    """Stand-in for the human moving a box in WPS.

    Reads the real file, makes a human-like change (text + position), and saves.
    The next ``inspect`` sees it exactly as it would see a WPS save.
    """
    src = Path(src).resolve()
    dst = Path(dst).resolve()
    prs = Presentation(str(src))
    slide = prs.slides[0]
    for info in pu.iter_shapes(slide):
        if info.name == "fig.decoder":
            info.shape.left = Inches(info.x - 0.12)
            info.shape.top = Inches(info.y + 0.18)
            pu.set_text(
                info.shape,
                "Shared\nDecoder",
                size=9.5,
                color=pu.text_color(info.shape) or "4D2A18",
                bold=False,
                align="center",
                anchor="middle",
            )
            break
    pu.reflow_all(slide)
    dst.parent.mkdir(parents=True, exist_ok=True)
    prs.save(str(dst))
    return {"input": str(src), "output": str(dst)}
