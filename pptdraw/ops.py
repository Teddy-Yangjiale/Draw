"""The AI-facing editing API.

An AI never edits raw OOXML.  It sends a JSON list of semantic operations, each
one targeting a named PowerPoint shape.  This keeps the file editable by humans
and makes every AI edit auditable and repeatable.
"""

from __future__ import annotations

import os
import shutil
import tempfile
from datetime import datetime
from pathlib import Path

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.util import Inches, Pt

from . import pptxutil as pu
from .style import get_style
from .textutil import block_size, line_height, text_width

IMAGE_EXT = {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".tif", ".tiff", ".webp"}


def _req(op: dict, key: str):
    if key not in op:
        raise ValueError(f"operation {op.get('op')!r} requires {key!r}")
    return op[key]


def _color(value) -> str | None:
    if value is None:
        return None
    value = str(value).lstrip("#").upper()
    if value in ("NONE", "TRANSPARENT", ""):
        return None
    if len(value) == 3:
        value = "".join(ch * 2 for ch in value)
    if len(value) != 6 or any(ch not in "0123456789ABCDEF" for ch in value):
        raise ValueError(f"invalid color {value!r}; use RRGGBB or 'none'")
    return value


def _shape_info(slide, name: str) -> pu.ShapeInfo:
    for info in pu.iter_shapes(slide):
        if info.name == name:
            return info
    raise KeyError(f"no shape named {name!r}")


def _exists(slide, name: str) -> bool:
    try:
        _shape_info(slide, name)
        return True
    except KeyError:
        return False


def _unique_name(slide, name: str) -> None:
    if _exists(slide, name):
        raise ValueError(f"shape name {name!r} already exists; choose a new name")


def _shape_or_raise(slide, name: str):
    return _shape_info(slide, name).shape


def _geom_info(slide, name: str) -> pu.ShapeInfo:
    info = _shape_info(slide, name)
    if info.group:
        raise ValueError(
            f"{name!r} is inside group {info.group!r}; ungroup it in WPS/PowerPoint "
            "before moving or resizing it with pptdraw"
        )
    return info


def _resolved(op: dict) -> dict:
    style = get_style(op.get("style"))
    return {
        "fill": _color(op["fill"]) if "fill" in op else _color(style.fill),
        "line": _color(op["line"]) if "line" in op else _color(style.line),
        "text_color": _color(op.get("text_color", style.text)) or "1E2833",
        "dash": op.get("dash", style.dash),
        "line_width": float(op.get("line_width", style.line_width)),
        "bold": bool(op.get("bold", style.bold)),
        "font_size": float(op.get("font_size", 10.5)),
        "align": op.get("align", "center"),
        "anchor": op.get("anchor", "middle"),
    }


def _apply_box_style(shape, cfg: dict) -> None:
    pu.set_shape_style(
        shape,
        fill=cfg["fill"],
        line=cfg["line"],
        line_width_pt=cfg["line_width"],
        dash=cfg["dash"],
    )
    if getattr(shape, "has_text_frame", False):
        pu.set_text(
            shape,
            shape.text_frame.text,
            size=cfg["font_size"],
            color=cfg["text_color"],
            bold=cfg["bold"],
            align=cfg["align"],
            anchor=cfg["anchor"],
        )


def _write_text(shape, op: dict, cfg: dict, default_anchor: str = "middle") -> None:
    pu.set_text(
        shape,
        str(op.get("text", "")),
        size=float(op.get("font_size", cfg["font_size"])),
        color=_color(op.get("text_color", cfg["text_color"])) or cfg["text_color"],
        bold=bool(op.get("bold", cfg["bold"])),
        italic=bool(op.get("italic", False)),
        align=op.get("align", cfg["align"]),
        anchor=op.get("anchor", default_anchor),
    )


def _add_shape(slide, op: dict) -> str:
    name = op.get("name") or f"fig.shape.{len(slide.shapes) + 1}"
    _unique_name(slide, name)
    kind = op.get("shape", "roundRect")
    text = str(op.get("text", ""))
    cfg = _resolved(op)
    x = float(_req(op, "x"))
    y = float(_req(op, "y"))
    w = op.get("w")
    h = op.get("h")
    if w is None or h is None:
        auto_w, auto_h = block_size(text, cfg["font_size"], 1.55)[0:2]
        auto_w = max(0.8, auto_w + 0.18)
        auto_h = max(0.44, auto_h + 0.14)
        w = w if w is not None else min(auto_w, 1.9)
        h = h if h is not None else auto_h
    shape = pu.add_autoshape(slide, kind, x, y, float(w), float(h))
    shape.name = name
    if kind in ("roundRect", "round", "rounded"):
        try:
            radius = float(op.get("radius", 0.08))
            shape.adjustments[0] = max(0.01, min(0.5, radius / max(min(float(w), float(h)), 0.1)))
        except (AttributeError, IndexError):
            pass
    _apply_box_style(shape, cfg)
    if text:
        _write_text(shape, op, cfg)
    if op.get("z") == "back":
        pu.send_to_back(shape)
    if op.get("alt"):
        pu.set_alt_text(shape, str(op["alt"]))
    return name


def _add_text(slide, op: dict) -> str:
    name = op.get("name") or f"fig.text.{len(slide.shapes) + 1}"
    _unique_name(slide, name)
    size = float(op.get("font_size", 9.0))
    w = op.get("w")
    h = op.get("h")
    text = str(op.get("text", ""))
    if w is None or h is None:
        tw = text_width(text, size)
        _, th, _ = block_size(text, size, max(0.1, tw + 0.02))
        w = w if w is not None else max(0.2, tw + 0.08)
        h = h if h is not None else max(0.18, th + 0.06)
    shape = slide.shapes.add_textbox(
        Inches(float(_req(op, "x"))),
        Inches(float(_req(op, "y"))),
        Inches(float(w)),
        Inches(float(h)),
    )
    shape.name = name
    shape.fill.background()
    shape.line.fill.background()
    pu.set_text(
        shape,
        text,
        size=size,
        color=_color(op.get("text_color", "1E2833")) or "1E2833",
        bold=bool(op.get("bold", False)),
        italic=bool(op.get("italic", False)),
        align=op.get("align", "left"),
        anchor=op.get("anchor", "top"),
        margins=(0.01, 0.01, 0.005, 0.005),
    )
    if op.get("z") == "back":
        pu.send_to_back(shape)
    return name


def _union_bbox(slide, names: list[str]) -> tuple[float, float, float, float]:
    infos = [_shape_info(slide, name) for name in names]
    x = min(i.x for i in infos)
    y = min(i.y for i in infos)
    right = max(i.right for i in infos)
    bottom = max(i.bottom for i in infos)
    return x, y, right, bottom


def _add_container(slide, op: dict) -> str:
    name = op.get("name") or f"fig.container.{len(slide.shapes) + 1}"
    _unique_name(slide, name)
    pad = float(op.get("padding", 0.12))
    label = str(op.get("label", op.get("text", "")))
    top_pad = float(op.get("top_pad", 0.24 if label else 0.0))
    if op.get("around"):
        x0, y0, x1, y1 = _union_bbox(slide, list(op["around"]))
        x, y = x0 - pad, y0 - pad - top_pad
        w, h = (x1 - x0) + 2 * pad, (y1 - y0) + 2 * pad + top_pad
    else:
        x = float(_req(op, "x"))
        y = float(_req(op, "y"))
        w = float(_req(op, "w"))
        h = float(_req(op, "h"))
    style = get_style(op.get("style", "container"))
    fill = _color(op["fill"]) if "fill" in op else _color(style.fill)
    line = _color(op["line"]) if "line" in op else _color(style.line)
    shape = pu.add_autoshape(slide, "roundRect", x, y, w, h)
    shape.name = name
    try:
        shape.adjustments[0] = max(0.02, min(0.2, float(op.get("radius", 0.1)) / max(min(w, h), 0.1)))
    except (AttributeError, IndexError):
        pass
    pu.set_shape_style(
        shape,
        fill=fill,
        line=line,
        line_width_pt=float(op.get("line_width", 1.0)),
        dash=op.get("dash", style.dash),
    )
    pu.set_text(
        shape,
        label,
        size=float(op.get("font_size", 9.0)),
        color=_color(op.get("text_color", style.text)) or style.text,
        bold=bool(op.get("bold", False)),
        align="left",
        anchor="top",
        margins=(0.08, 0.06, 0.045, 0.02),
    )
    pu.set_alt_text(shape, f"pptdraw:container:{name}")
    pu.send_to_back(shape)
    return name


def _sides_for(a: pu.ShapeInfo, b: pu.ShapeInfo) -> tuple[int, int]:
    dx = b.cx - a.cx
    dy = b.cy - a.cy
    if abs(dx) >= abs(dy) * 0.9:
        return (pu.SIDE_INDEX["right"], pu.SIDE_INDEX["left"]) if dx >= 0 else (
            pu.SIDE_INDEX["left"],
            pu.SIDE_INDEX["right"],
        )
    return (pu.SIDE_INDEX["bottom"], pu.SIDE_INDEX["top"]) if dy >= 0 else (
        pu.SIDE_INDEX["top"],
        pu.SIDE_INDEX["bottom"],
    )


def _midpoint_for_label(slide, connector, infos: dict[int, pu.ShapeInfo]) -> tuple[float, float, bool]:
    info = infos.get(connector.shape_id)
    prst = pu._prst(connector) or "line"
    if prst.startswith("bentConnector") or prst.startswith("curvedConnector"):
        if info:
            return info.cx, info.cy, abs(info.w) >= abs(info.h)
    x1, y1, x2, y2 = pu.connector_endpoints(connector, infos)
    return (x1 + x2) / 2, (y1 + y2) / 2, abs(x2 - x1) >= abs(y2 - y1)


def _add_edge_label(slide, connector, name: str, op: dict) -> str | None:
    text = op.get("label")
    if not text:
        return None
    label_name = f"{name}.label"
    _unique_name(slide, label_name)
    size = float(op.get("label_font_size", 8.5))
    color = _color(op.get("label_color", "5B6773")) or "5B6773"
    lines = str(text).split("\n")
    tw = max(text_width(line, size) for line in lines)
    w = max(0.16, tw + 0.1)
    h = max(0.16, len(lines) * line_height(size) + 0.05)
    infos = pu.shape_by_id(slide)
    mx, my, horizontal = _midpoint_for_label(slide, connector, infos)
    offset = float(op.get("label_offset", 0.12))
    x = mx - w / 2
    y = my - h / 2 - offset if horizontal else my - h / 2
    if not horizontal:
        x = mx + offset
    shape = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    shape.name = label_name
    bg = _color(op.get("label_bg", "FFFFFF"))
    if bg:
        shape.fill.solid()
        shape.fill.fore_color.rgb = RGBColor.from_string(bg)
    else:
        shape.fill.background()
    shape.line.fill.background()
    pu.set_text(
        shape,
        str(text),
        size=size,
        color=color,
        bold=bool(op.get("label_bold", False)),
        align="center",
        anchor="middle",
        margins=(0.02, 0.02, 0.005, 0.005),
    )
    pu.set_alt_text(shape, f"pptdraw:edge-label:{name}:{offset}")
    return label_name


def _add_route(slide, op: dict) -> list[str]:
    """A multi-segment open polyline for skip/feedback connections.

    Native elbow connectors route bottom-to-bottom straight across the diagram,
    so special detours are built as 2-4 straight segments.  Each segment remains
    a native, editable line; the last one carries the arrowhead.
    """
    base = op.get("name") or f"fig.route.{len(slide.shapes) + 1}"
    points = [(float(p[0]), float(p[1])) for p in _req(op, "points")]
    if len(points) < 2:
        raise ValueError("add_route needs at least 2 points")
    color = _color(op.get("color", op.get("line", "4B5763"))) or "4B5763"
    width = float(op.get("line_width", 1.0))
    dash = op.get("dash", "solid")
    ends = op.get("arrow", "end")
    made = []
    for index in range(len(points) - 1):
        x1, y1 = points[index]
        x2, y2 = points[index + 1]
        name = base if index == 0 else f"{base}.seg{index + 1}"
        if index == 0:
            name = f"{base}.seg1"
        _unique_name(slide, name)
        connector = pu.add_connector(slide, "straight", x1, y1, x2, y2)
        connector.name = name
        pu.set_shape_style(
            connector,
            fill=None,
            line=color,
            line_width_pt=width,
            dash=dash,
        )
        segment_ends = "none"
        if index == len(points) - 2 and ends in ("end", "both"):
            segment_ends = "end" if ends == "end" else "both"
        elif index == 0 and ends in ("start", "both"):
            segment_ends = "start"
        pu.set_arrow_ends(connector, segment_ends)
        made.append(name)

    label_text = op.get("label")
    if label_text:
        # Put the label above the longest segment.
        seg_index = max(
            range(len(points) - 1),
            key=lambda i: (points[i + 1][0] - points[i][0]) ** 2
            + (points[i + 1][1] - points[i][1]) ** 2,
        )
        x1, y1 = points[seg_index]
        x2, y2 = points[seg_index + 1]
        size = float(op.get("label_font_size", 8.5))
        label_name = f"{base}.label"
        _unique_name(slide, label_name)
        text_w = text_width(str(label_text), size)
        w = max(0.18, text_w + 0.1)
        h = max(0.16, line_height(size) + 0.05)
        mx, my = (x1 + x2) / 2, (y1 + y2) / 2
        offset = float(op.get("label_offset", 0.12))
        shape = slide.shapes.add_textbox(
            Inches(mx - w / 2), Inches(my - h / 2 - offset), Inches(w), Inches(h)
        )
        shape.name = label_name
        bg = _color(op.get("label_bg", "FFFFFF"))
        if bg:
            shape.fill.solid()
            shape.fill.fore_color.rgb = RGBColor.from_string(bg)
        else:
            shape.fill.background()
        shape.line.fill.background()
        pu.set_text(
            shape,
            str(label_text),
            size=size,
            color=_color(op.get("label_color", "5B6773")) or "5B6773",
            bold=bool(op.get("label_bold", False)),
            align="center",
            anchor="middle",
            margins=(0.02, 0.02, 0.005, 0.005),
        )
        made.append(label_name)
    return made


def _add_detour(slide, op: dict) -> list[str]:
    """A U-shaped, attached skip/feedback connection.

    Two native connectors attach the source and target to a nearly invisible
    anchor line.  Moving a module in WPS therefore keeps the detour connected;
    the anchor itself can also be moved to change the route depth.
    """
    name = op.get("name") or f"fig.route.{len(slide.shapes) + 1}"
    a = _shape_info(slide, str(_req(op, "from")))
    b = _shape_info(slide, str(_req(op, "to")))
    side = op.get("side", "bottom")
    offset = float(op.get("offset", 0.35))
    color = _color(op.get("color", op.get("line", "4B5763"))) or "4B5763"
    width = float(op.get("line_width", 1.0))
    dash = op.get("dash", "dash")
    ends = op.get("arrow", "end")
    thickness = 0.0005
    anchor_name = f"{name}.anchor"
    _unique_name(slide, anchor_name)

    if side in ("bottom", "top"):
        if abs(a.cx - b.cx) < 0.1:
            raise ValueError(
                "a top/bottom detour needs the two shapes to differ horizontally; "
                "use side='left' or 'right' instead"
            )
        edge = max(a.bottom, b.bottom) + offset if side == "bottom" else min(a.y, b.y) - offset
        x0, x1 = sorted([a.cx, b.cx])
        if abs(x1 - x0) < 0.03:
            x1 = x0 + 0.03
        anchor = slide.shapes.add_shape(
            MSO_SHAPE.RECTANGLE,
            Inches(x0),
            Inches(edge - thickness / 2),
            Inches(x1 - x0),
            Inches(thickness),
        )
        if side == "bottom":
            begin_site, end_site = 2, 2
        else:
            begin_site, end_site = 0, 0
        near_a = 1 if a.cx <= b.cx else 3
        far_b = 3 if a.cx <= b.cx else 1
        first = pu.add_connector(
            slide, "straight", 0, 0, 0, 0,
            begin_shape=a.shape, begin_idx=begin_site,
            end_shape=anchor, end_idx=near_a,
        )
        second = pu.add_connector(
            slide, "straight", 0, 0, 0, 0,
            begin_shape=anchor, begin_idx=far_b,
            end_shape=b.shape, end_idx=end_site,
        )
        label_above = side == "bottom"
    else:
        if abs(a.cy - b.cy) < 0.1:
            raise ValueError(
                "a left/right detour needs the two shapes to differ vertically; "
                "use side='top' or 'bottom' instead"
            )
        edge = max(a.right, b.right) + offset if side == "right" else min(a.x, b.x) - offset
        y0, y1 = sorted([a.cy, b.cy])
        if abs(y1 - y0) < 0.03:
            y1 = y0 + 0.03
        anchor = slide.shapes.add_shape(
            MSO_SHAPE.RECTANGLE,
            Inches(edge - thickness / 2),
            Inches(y0),
            Inches(thickness),
            Inches(y1 - y0),
        )
        if side == "right":
            begin_site, end_site = 3, 3
        else:
            begin_site, end_site = 1, 1
        near_a = 0 if a.cy <= b.cy else 2
        far_b = 2 if a.cy <= b.cy else 0
        first = pu.add_connector(
            slide, "straight", 0, 0, 0, 0,
            begin_shape=a.shape, begin_idx=begin_site,
            end_shape=anchor, end_idx=near_a,
        )
        second = pu.add_connector(
            slide, "straight", 0, 0, 0, 0,
            begin_shape=anchor, begin_idx=far_b,
            end_shape=b.shape, end_idx=end_site,
        )
        label_above = True

    anchor.name = anchor_name
    anchor.fill.background()
    anchor.line.color.rgb = RGBColor.from_string(color)
    anchor.line.width = Pt(max(0.5, width * 0.5))
    anchor.line.dash_style = pu.DASH_MAP.get(dash, pu.MSO_LINE_DASH_STYLE.SOLID)
    pu.set_alt_text(anchor, f"pptdraw:route-anchor:{name}:{side}")

    made = [anchor_name]
    for index, conn in enumerate((first, second), start=1):
        conn.name = f"{name}.seg{index}"
        pu.set_shape_style(
            conn, fill=None, line=color, line_width_pt=width, dash=dash
        )
        segment_ends = "none"
        if index == 2 and ends in ("end", "both"):
            segment_ends = "end" if ends == "end" else "both"
        elif index == 1 and ends in ("start", "both"):
            segment_ends = "start"
        pu.set_arrow_ends(conn, segment_ends)
        made.append(conn.name)

    text = op.get("label")
    if text:
        size = float(op.get("label_font_size", 8.5))
        tw = text_width(str(text), size)
        w = max(0.18, tw + 0.1)
        h = max(0.16, line_height(size) + 0.05)
        ax, ay = anchor.left / pu.EMU, anchor.top / pu.EMU
        aw, ah = anchor.width / pu.EMU, anchor.height / pu.EMU
        mx, my = ax + aw / 2, ay + ah / 2
        label_name = f"{name}.label"
        _unique_name(slide, label_name)
        if side in ("bottom", "top"):
            y = my - h - 0.03 if label_above else my + 0.03
            x = mx - w / 2
        else:
            x = mx + 0.05 if side == "right" else mx - w - 0.05
            y = my - h / 2
        label_shape = slide.shapes.add_textbox(
            Inches(x), Inches(y), Inches(w), Inches(h)
        )
        label_shape.name = label_name
        bg = _color(op.get("label_bg", "FFFFFF"))
        if bg:
            label_shape.fill.solid()
            label_shape.fill.fore_color.rgb = RGBColor.from_string(bg)
        else:
            label_shape.fill.background()
        label_shape.line.fill.background()
        pu.set_text(
            label_shape,
            str(text),
            size=size,
            color=_color(op.get("label_color", "5B6773")) or "5B6773",
            bold=bool(op.get("label_bold", False)),
            align="center",
            anchor="middle",
            margins=(0.02, 0.02, 0.005, 0.005),
        )
        pu.set_alt_text(
            label_shape, f"pptdraw:detour-label:{name}:{side}:{label_above}"
        )
        made.append(label_name)
    return made


def _add_connector(slide, op: dict) -> str:
    name = op.get("name") or f"fig.edge.{len(slide.shapes) + 1}"
    _unique_name(slide, name)
    start = _req(op, "from")
    end = _req(op, "to")
    route = op.get("route", "straight")
    begin_shape = end_shape = None
    begin_idx = end_idx = None
    x1 = y1 = x2 = y2 = 0.0
    if isinstance(start, str):
        a = _shape_info(slide, start)
        b = _shape_info(slide, end)
        auto_s, auto_e = _sides_for(a, b)
        begin_idx = pu.SIDE_INDEX.get(str(op.get("from_side", "")).lower(), auto_s)
        end_idx = pu.SIDE_INDEX.get(str(op.get("to_side", "")).lower(), auto_e)
        begin_shape, end_shape = a.shape, b.shape
        x1, y1 = pu.site_point(a, begin_idx)
        x2, y2 = pu.site_point(b, end_idx)
    else:
        x1, y1 = float(start[0]), float(start[1])
        x2, y2 = float(end[0]), float(end[1])
    connector = pu.add_connector(
        slide,
        route,
        x1,
        y1,
        x2,
        y2,
        begin_shape=begin_shape,
        begin_idx=begin_idx,
        end_shape=end_shape,
        end_idx=end_idx,
    )
    connector.name = name
    pu.set_shape_style(
        connector,
        fill=None,
        line=_color(op.get("color", op.get("line", "4B5763"))) or "4B5763",
        line_width_pt=float(op.get("line_width", 1.0)),
        dash=op.get("dash", "solid"),
    )
    pu.set_arrow_ends(connector, op.get("arrow", "end"))
    label = _add_edge_label(slide, connector, name, op)
    if label:
        pu.set_alt_text(connector, f"pptdraw:edge:{label}")
    return name


def _image_path(path: str, base_dir: Path) -> Path:
    candidate = Path(path)
    if not candidate.is_absolute():
        candidate = base_dir / candidate
    candidate = candidate.resolve()
    if not candidate.exists():
        raise FileNotFoundError(f"image not found: {candidate}")
    return candidate


def _add_picture(slide, op: dict, base_dir: Path) -> str:
    name = op.get("name") or f"fig.image.{len(slide.shapes) + 1}"
    _unique_name(slide, name)
    path = _image_path(str(_req(op, "path")), base_dir)
    x = float(_req(op, "x"))
    y = float(_req(op, "y"))
    box_w = op.get("w")
    box_h = op.get("h")
    from PIL import Image

    with Image.open(path) as image:
        iw, ih = image.size
    aspect = iw / ih if ih else 1.0
    if box_w is None and box_h is None:
        box_w, box_h = 1.0, 1.0 / aspect
    elif box_w is None:
        box_w = float(box_h) * aspect
    elif box_h is None:
        box_h = float(box_w) / aspect
    box_w, box_h = float(box_w), float(box_h)
    draw_w, draw_h = box_w, box_h
    if draw_w / draw_h > aspect:
        draw_w = draw_h * aspect
    else:
        draw_h = draw_w / aspect
    px = x + (box_w - draw_w) / 2
    py = y + (box_h - draw_h) / 2
    pic = slide.shapes.add_picture(
        str(path), Inches(px), Inches(py), Inches(draw_w), Inches(draw_h)
    )
    pic.name = name
    if op.get("line"):
        pic.line.color.rgb = RGBColor.from_string(_color(op["line"]))
        pic.line.width = Pt(float(op.get("line_width", 0.75)))
    pu.set_alt_text(pic, f"pptdraw:image:{path}")
    return name


def _add_image_grid(slide, op: dict, base_dir: Path) -> list[str]:
    images = list(_req(op, "images"))
    cols = int(_req(op, "cols"))
    x0 = float(_req(op, "x"))
    y0 = float(_req(op, "y"))
    cw = float(_req(op, "cell_w"))
    ch = float(_req(op, "cell_h"))
    gap = float(op.get("gap", 0.08))
    labels = op.get("labels") or []
    label_size = float(op.get("label_size", 8.0))
    label_h = float(op.get("label_h", 0.18)) if labels else 0.0
    prefix = op.get("prefix", "fig.image")
    made = []
    for index, image_path in enumerate(images):
        row, col = divmod(index, cols)
        x = x0 + col * (cw + gap)
        y = y0 + row * (ch + gap)
        name = f"{prefix}.{index + 1}"
        spec = {
            "name": name,
            "path": image_path,
            "x": x,
            "y": y,
            "w": cw,
            "h": max(0.1, ch - label_h),
        }
        made.append(_add_picture(slide, spec, base_dir))
        if labels and index < len(labels):
            _add_text(
                slide,
                {
                    "name": f"fig.label.{prefix.split('.')[-1]}.{index + 1}",
                    "text": labels[index],
                    "x": x,
                    "y": y + ch - label_h + 0.015,
                    "w": cw,
                    "h": max(0.14, label_h - 0.01),
                    "font_size": label_size,
                    "text_color": "5B6773",
                    "align": "center",
                    "anchor": "top",
                },
            )
    return made


def _reposition_edge_labels(slide) -> None:
    infos = pu.shape_by_id(slide)
    for info in pu.iter_shapes(slide):
        alt = pu.alt_text(info.shape) or ""
        if not alt.startswith("pptdraw:edge-label:"):
            continue
        parts = alt.split(":")
        if len(parts) < 4:
            continue
        edge_name = parts[2]
        try:
            offset = float(parts[3])
            connector = _shape_or_raise(slide, edge_name)
        except (KeyError, ValueError):
            continue
        mx, my, horizontal = _midpoint_for_label(slide, connector, infos)
        w = info.w
        h = info.h
        x = mx - w / 2
        y = my - h / 2 - offset if horizontal else my - h / 2
        if not horizontal:
            x = mx + offset
        info.shape.left = Inches(x)
        info.shape.top = Inches(y)
        try:
            connector_alt = pu.alt_text(connector)
            if connector_alt:
                pu.set_alt_text(connector, f"pptdraw:edge:{info.name}")
        except Exception:
            pass


def _reposition_detour_labels(slide) -> None:
    infos = {info.name: info for info in pu.iter_shapes(slide)}
    for info in pu.iter_shapes(slide):
        alt = pu.alt_text(info.shape) or ""
        if not alt.startswith("pptdraw:detour-label:"):
            continue
        parts = alt.split(":")
        if len(parts) < 5:
            continue
        name, side, above = parts[2], parts[3], parts[4] == "True"
        anchor = infos.get(f"{name}.anchor")
        if anchor is None:
            continue
        w, h = info.w, info.h
        mx, my = anchor.cx, anchor.cy
        if side in ("bottom", "top"):
            y = my - h - 0.03 if above else my + 0.03
            x = mx - w / 2
        else:
            x = mx + 0.05 if side == "right" else mx - w - 0.05
            y = my - h / 2
        info.shape.left = Inches(x)
        info.shape.top = Inches(y)


def _detour_base(name: str) -> str | None:
    for suffix in (".anchor", ".label", ".seg1", ".seg2"):
        if name.endswith(suffix):
            return name[: -len(suffix)]
    return None


def _fit_canvas(slide, op: dict) -> None:
    infos = [info for info in pu.iter_shapes(slide) if info.group is None]
    if not infos:
        raise ValueError("fit_canvas needs at least one shape")
    min_x = min(i.x for i in infos)
    min_y = min(i.y for i in infos)
    max_x = max(i.right for i in infos)
    max_y = max(i.bottom for i in infos)
    content_w = max_x - min_x
    content_h = max_y - min_y
    margin = float(op.get("margin", 0.1))
    prs = slide.part.package.presentation_part.presentation
    current_w = prs.slide_width / pu.EMU
    current_h = prs.slide_height / pu.EMU
    keep_width = bool(op.get("keep_width", False))
    keep_height = bool(op.get("keep_height", False))

    if keep_width:
        new_w = max(1.0, current_w)
    else:
        new_w = max(1.0, content_w + 2 * margin)
    if keep_height:
        new_h = max(1.0, current_h)
    else:
        new_h = max(1.0, content_h + 2 * margin)
    dx = (new_w - content_w) / 2 - min_x
    dy = (new_h - content_h) / 2 - min_y

    for info in infos:
        info.shape.left = Inches(info.x + dx)
        info.shape.top = Inches(info.y + dy)
    prs.slide_width = Inches(new_w)
    prs.slide_height = Inches(new_h)
    pu.reflow_all(slide)
    _reposition_edge_labels(slide)
    _reposition_detour_labels(slide)


def _delete(slide, op: dict) -> list[str]:
    name = str(_req(op, "name"))
    target = _shape_or_raise(slide, name)
    target_id = target.shape_id
    names: set[str] = {name, f"{name}.label"}
    base = _detour_base(name)
    if base:
        names.update(
            {
                base,
                f"{base}.anchor",
                f"{base}.label",
                f"{base}.seg1",
                f"{base}.seg2",
            }
        )
    # Cascade: connectors attached to the deleted shape, plus detour groups.
    for info in list(pu.iter_shapes(slide)):
        if info.kind != "connector":
            continue
        c = pu.connector_connections(info.shape)
        if target_id in (c.get("begin_id"), c.get("end_id")):
            names.add(info.name)
            names.add(f"{info.name}.label")
            other_base = _detour_base(info.name)
            if other_base:
                names.update(
                    {
                        other_base,
                        f"{other_base}.anchor",
                        f"{other_base}.label",
                        f"{other_base}.seg1",
                        f"{other_base}.seg2",
                    }
                )
    deleted = []
    existing = [n for n in names if _exists(slide, n)]
    # Connectors and labels first, then the target.
    ordered = sorted(
        existing,
        key=lambda n: (
            0
            if _shape_info(slide, n).kind == "connector"
            else 1
            if n != name
            else 2
        ),
    )
    for candidate in ordered:
        if not _exists(slide, candidate):
            continue
        shape = _shape_or_raise(slide, candidate)
        if shape.shape_id == target_id and candidate != name:
            continue
        pu.delete_shape(shape)
        deleted.append(candidate)
    return deleted


def _align(slide, op: dict) -> None:
    names = list(_req(op, "names"))
    mode = str(_req(op, "mode"))
    target_name = op.get("target")
    prs_w = slide.part.package.presentation_part.presentation.slide_width / pu.EMU
    prs_h = slide.part.package.presentation_part.presentation.slide_height / pu.EMU
    if target_name and target_name != "canvas":
        t = _shape_info(slide, target_name)
        tx, ty, tright, tbottom = t.x, t.y, t.right, t.bottom
    else:
        tx, ty, tright, tbottom = 0.0, 0.0, prs_w, prs_h
    for name in names:
        info = _geom_info(slide, name)
        if mode == "left":
            info.shape.left = Inches(tx)
        elif mode == "center":
            info.shape.left = Inches((tx + tright) / 2 - info.w / 2)
        elif mode == "right":
            info.shape.left = Inches(tright - info.w)
        elif mode == "top":
            info.shape.top = Inches(ty)
        elif mode == "middle":
            info.shape.top = Inches((ty + tbottom) / 2 - info.h / 2)
        elif mode == "bottom":
            info.shape.top = Inches(tbottom - info.h)
        else:
            raise ValueError(f"unknown align mode {mode!r}")


def _distribute(slide, op: dict) -> None:
    names = list(_req(op, "names"))
    axis = op.get("axis", "h")
    mode = op.get("mode", "gap")
    infos = sorted(
        [_geom_info(slide, name) for name in names],
        key=lambda i: i.cx if axis == "h" else i.cy,
    )
    if len(infos) < 3:
        raise ValueError("distribute needs at least 3 shapes")
    if mode == "center":
        first, last = infos[0], infos[-1]
        if axis == "h":
            start, end = first.cx, last.cx
            step = (end - start) / (len(infos) - 1)
            for index, info in enumerate(infos):
                info.shape.left = Inches(start + step * index - info.w / 2)
        else:
            start, end = first.cy, last.cy
            step = (end - start) / (len(infos) - 1)
            for index, info in enumerate(infos):
                info.shape.top = Inches(start + step * index - info.h / 2)
        return

    if axis == "h":
        total = sum(i.w for i in infos)
        span = infos[-1].right - infos[0].x
        gap = (span - total) / (len(infos) - 1)
        cursor = infos[0].x
        for info in infos:
            info.shape.left = Inches(cursor)
            cursor += info.w + gap
    else:
        total = sum(i.h for i in infos)
        span = infos[-1].bottom - infos[0].y
        gap = (span - total) / (len(infos) - 1)
        cursor = infos[0].y
        for info in infos:
            info.shape.top = Inches(cursor)
            cursor += info.h + gap


def _layout_line(slide, op: dict, vertical: bool) -> None:
    names = list(_req(op, "names"))
    infos = [_geom_info(slide, name) for name in names]
    gap = float(op.get("gap", 0.16))
    if vertical:
        total = sum(i.h for i in infos) + gap * (len(infos) - 1)
        center = float(op.get("center", slide.part.package.presentation_part.presentation.slide_height / pu.EMU / 2))
        cursor = center - total / 2
        x_center = float(op.get("x", slide.part.package.presentation_part.presentation.slide_width / pu.EMU / 2))
        for info in infos:
            info.shape.top = Inches(cursor)
            info.shape.left = Inches(x_center - info.w / 2)
            cursor += info.h + gap
    else:
        total = sum(i.w for i in infos) + gap * (len(infos) - 1)
        center = float(op.get("center", slide.part.package.presentation_part.presentation.slide_width / pu.EMU / 2))
        cursor = center - total / 2
        y_center = float(op.get("y", slide.part.package.presentation_part.presentation.slide_height / pu.EMU / 2))
        for info in infos:
            info.shape.left = Inches(cursor)
            info.shape.top = Inches(y_center - info.h / 2)
            cursor += info.w + gap


def _set_z(slide, op: dict) -> None:
    shape = _shape_or_raise(slide, str(_req(op, "name")))
    position = op.get("position", "front")
    if position == "back":
        pu.send_to_back(shape)
    elif position == "front":
        pu.bring_to_front(shape)
    elif position == "forward":
        pu.bring_forward(shape)
    elif position == "backward":
        pu.send_backward(shape)
    else:
        raise ValueError(f"unknown z position {position!r}")


def _normalize_z(slide) -> None:
    tree = slide.shapes._spTree
    infos = list(pu.iter_shapes(slide))
    top = [i for i in infos if i.group is None]
    elements = [i.shape._element for i in top]
    for el in elements:
        if el.getparent() is tree:
            tree.remove(el)

    def rank(info: pu.ShapeInfo):
        name = info.name
        alt = pu.alt_text(info.shape) or ""
        if alt.startswith("pptdraw:route-anchor:"):
            return (1, info.z)
        if name.startswith("fig.container"):
            return (0, -info.w * info.h)
        if info.kind == "connector":
            return (1, info.z)
        if alt.startswith("pptdraw:edge-label:") or alt.startswith("pptdraw:detour-label:"):
            return (3, info.z)
        if name.startswith("fig.label") or info.kind == "text":
            return (2, info.z)
        return (1.5, info.z)

    for info in sorted(top, key=rank):
        tree.append(info.shape._element)


def _current_line_color(shape) -> str:
    value = pu.fill_hex(shape.line)
    if not value or value.startswith("theme:"):
        return "4B5763"
    return value


def _set_style(slide, op: dict) -> None:
    info = _shape_info(slide, str(_req(op, "name")))
    shape = info.shape
    is_connector = info.kind == "connector"
    preset = get_style(op["style"]) if op.get("style") else None
    line_keys = ("line", "line_width", "dash")
    fill_specified = "fill" in op or preset is not None
    line_specified = any(key in op for key in line_keys) or preset is not None
    fill = (
        _color(op["fill"])
        if "fill" in op
        else (_color(preset.fill) if preset else None)
    )
    line = (
        _color(op["line"])
        if "line" in op
        else (_color(preset.line) if preset else None)
    )
    width = float(
        op.get(
            "line_width",
            preset.line_width if preset else pu.line_width(shape),
        )
    )
    dash = op.get("dash", preset.dash if preset else pu.dash_style(shape))

    if is_connector:
        if line_specified:
            color = line if line is not None else _current_line_color(shape)
            shape.line.color.rgb = RGBColor.from_string((color or "4B5763").lstrip("#"))
            shape.line.width = Pt(width)
            shape.line.dash_style = pu.DASH_MAP.get(
                dash, pu.MSO_LINE_DASH_STYLE.SOLID
            )
    elif info.kind not in ("picture", "group"):
        if fill_specified:
            if fill is None:
                shape.fill.background()
            else:
                shape.fill.solid()
                shape.fill.fore_color.rgb = RGBColor.from_string(fill)
        if line_specified:
            color = line if line is not None else _current_line_color(shape)
            if color is None:
                shape.line.fill.background()
            else:
                shape.line.color.rgb = RGBColor.from_string(color)
                shape.line.width = Pt(width)
                shape.line.dash_style = pu.DASH_MAP.get(
                    dash, pu.MSO_LINE_DASH_STYLE.SOLID
                )
        if "radius" in op and info.kind in ("roundRect", "round", "rounded"):
            try:
                shape.adjustments[0] = max(
                    0.01,
                    min(
                        0.5,
                        float(op["radius"])
                        / max(min(info.w, info.h), 0.1),
                    ),
                )
            except (AttributeError, IndexError):
                pass
    if (
        "text_color" in op
        or "font_size" in op
        or "bold" in op
        or preset is not None
    ):
        if not getattr(shape, "has_text_frame", False):
            return
        size = float(op.get("font_size", pu.font_size_of(shape) or 10.5))
        current_color = pu.text_color(shape) or "1E2833"
        if current_color.startswith("theme:"):
            current_color = "1E2833"
        color = _color(
            op.get("text_color", preset.text if preset else current_color)
        ) or "1E2833"
        run = pu.first_run(shape)
        bold = bool(
            op.get(
                "bold",
                preset.bold if preset else bool(run and run.font.bold),
            )
        )
        pu.set_shape_text_style(
            shape,
            size=size,
            color=color,
            bold=bold,
            align=op.get("align", pu.paragraph_alignment(shape) or "center"),
            anchor=op.get("anchor", pu.vertical_anchor(shape) or "middle"),
        )


def _set_text(slide, op: dict) -> None:
    info = _shape_info(slide, str(_req(op, "name")))
    shape = info.shape
    if not getattr(shape, "has_text_frame", False):
        raise ValueError(f"{info.name} has no text frame")
    size = float(op.get("font_size", pu.font_size_of(shape) or 10.5))
    current_color = pu.text_color(shape) or "1E2833"
    if current_color.startswith("theme:"):
        current_color = "1E2833"
    color = _color(op.get("text_color", current_color)) or "1E2833"
    run = pu.first_run(shape)
    bold = bool(op.get("bold", bool(run and run.font.bold)))
    italic = bool(op.get("italic", bool(run and run.font.italic)))
    align = op.get("align", pu.paragraph_alignment(shape) or "center")
    anchor = op.get("anchor", pu.vertical_anchor(shape) or "middle")
    pu.set_text(
        shape,
        str(_req(op, "text")),
        size=size,
        color=color,
        bold=bold,
        italic=italic,
        align=align,
        anchor=anchor,
    )


def apply_ops(
    path: str | Path,
    doc: dict,
    *,
    out_path: str | Path | None = None,
    base_dir: str | Path | None = None,
    backup: bool = True,
) -> dict:
    src = Path(path).resolve()
    target = Path(out_path).resolve() if out_path else src
    base = Path(base_dir).resolve() if base_dir else Path.cwd()
    prs = Presentation(str(src))
    slide_no = int(doc.get("slide", 1))
    if slide_no < 1 or slide_no > len(prs.slides):
        raise ValueError(f"slide {slide_no} out of range (1..{len(prs.slides)})")
    slide = prs.slides[slide_no - 1]

    backup_path = None
    if backup and target == src:
        hist = src.parent / ".pptdraw" / "history"
        hist.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")[:-3]
        backup_path = hist / f"{src.stem}-{stamp}{src.suffix}"
        shutil.copyfile(src, backup_path)

    applied = []
    for index, op in enumerate(doc.get("ops", [])):
        kind = op.get("op")
        try:
            if kind == "add_shape":
                applied.append({"op": kind, "name": _add_shape(slide, op)})
            elif kind == "add_text":
                applied.append({"op": kind, "name": _add_text(slide, op)})
            elif kind == "add_container":
                applied.append({"op": kind, "name": _add_container(slide, op)})
            elif kind == "add_connector":
                applied.append({"op": kind, "name": _add_connector(slide, op)})
            elif kind == "add_route":
                applied.append({"op": kind, "names": _add_route(slide, op)})
            elif kind == "add_detour":
                applied.append({"op": kind, "names": _add_detour(slide, op)})
            elif kind == "add_picture":
                applied.append({"op": kind, "name": _add_picture(slide, op, base)})
            elif kind == "add_image_grid":
                applied.append(
                    {"op": kind, "names": _add_image_grid(slide, op, base)}
                )
            elif kind == "move":
                info = _geom_info(slide, str(_req(op, "name")))
                if "x" in op:
                    info.shape.left = Inches(float(op["x"]))
                else:
                    info.shape.left = Inches(info.x + float(op.get("dx", 0)))
                if "y" in op:
                    info.shape.top = Inches(float(op["y"]))
                else:
                    info.shape.top = Inches(info.y + float(op.get("dy", 0)))
                applied.append({"op": kind, "name": info.name})
            elif kind == "resize":
                info = _geom_info(slide, str(_req(op, "name")))
                if "w" in op:
                    info.shape.width = Inches(float(op["w"]))
                if "h" in op:
                    info.shape.height = Inches(float(op["h"]))
                applied.append({"op": kind, "name": info.name})
            elif kind == "set_text":
                _set_text(slide, op)
                applied.append({"op": kind, "name": op["name"]})
            elif kind == "set_style":
                _set_style(slide, op)
                applied.append({"op": kind, "name": op["name"]})
            elif kind == "delete":
                applied.append({"op": kind, "deleted": _delete(slide, op)})
            elif kind == "rename":
                info = _shape_info(slide, str(_req(op, "name")))
                new_name = str(_req(op, "new_name"))
                _unique_name(slide, new_name)
                old = info.name
                info.shape.name = new_name
                applied.append({"op": kind, "from": old, "to": new_name})
            elif kind == "align":
                _align(slide, op)
                applied.append({"op": kind, "names": op.get("names")})
            elif kind == "distribute":
                _distribute(slide, op)
                applied.append({"op": kind, "names": op.get("names")})
            elif kind == "layout_row":
                _layout_line(slide, op, vertical=False)
                applied.append({"op": kind, "names": op.get("names")})
            elif kind == "layout_column":
                _layout_line(slide, op, vertical=True)
                applied.append({"op": kind, "names": op.get("names")})
            elif kind == "set_z":
                _set_z(slide, op)
                applied.append({"op": kind, "name": op.get("name")})
            elif kind == "normalize_z":
                _normalize_z(slide)
                applied.append({"op": kind})
            elif kind == "set_background":
                pu.set_background(slide, _color(op.get("color", "FFFFFF")) or "FFFFFF")
                applied.append({"op": kind})
            elif kind == "fit_canvas":
                _fit_canvas(slide, op)
                applied.append({"op": kind})
            else:
                raise ValueError(f"unknown op {kind!r} at index {index}")
        except Exception as exc:
            raise RuntimeError(f"op #{index + 1} ({kind}) failed: {exc}") from exc

    pu.reflow_all(slide)
    _reposition_edge_labels(slide)
    _reposition_detour_labels(slide)

    target.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(suffix=".pptx", dir=str(target.parent))
    os.close(fd)
    try:
        prs.save(temp_name)
        os.replace(temp_name, target)
    finally:
        if os.path.exists(temp_name):
            os.remove(temp_name)

    return {
        "input": str(src),
        "output": str(target),
        "applied": applied,
        "backup": str(backup_path) if backup_path else None,
    }
