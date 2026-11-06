"""Low-level helpers for reading and writing editable PowerPoint objects.

The important design choice: we never flatten a figure into a PNG.  Every
module, arrow and label stays a native PowerPoint shape/text box so the human
can keep editing it in WPS/PowerPoint.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Iterator

from lxml import etree
from pptx.dml.color import RGBColor
from pptx.enum.dml import MSO_LINE_DASH_STYLE
from pptx.enum.shapes import MSO_CONNECTOR, MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.oxml.ns import qn
from pptx.util import Inches, Pt

from . import fonts

EMU = 914400.0

SHAPE_MAP = {
    "rect": MSO_SHAPE.RECTANGLE,
    "rectangle": MSO_SHAPE.RECTANGLE,
    "roundRect": MSO_SHAPE.ROUNDED_RECTANGLE,
    "round": MSO_SHAPE.ROUNDED_RECTANGLE,
    "rounded": MSO_SHAPE.ROUNDED_RECTANGLE,
    "ellipse": MSO_SHAPE.OVAL,
    "oval": MSO_SHAPE.OVAL,
    "diamond": MSO_SHAPE.DIAMOND,
    "trapezoid": MSO_SHAPE.TRAPEZOID,
    "chevron": MSO_SHAPE.CHEVRON,
    "hexagon": MSO_SHAPE.HEXAGON,
    "pentagon": MSO_SHAPE.PENTAGON,
    "parallelogram": MSO_SHAPE.PARALLELOGRAM,
    "cylinder": MSO_SHAPE.CAN,
    "can": MSO_SHAPE.CAN,
    "cloud": MSO_SHAPE.CLOUD,
    "star": MSO_SHAPE.STAR_4_POINT,
}

SIDE_INDEX = {"top": 0, "left": 1, "bottom": 2, "right": 3}
INDEX_SIDE = {v: k for k, v in SIDE_INDEX.items()}

DASH_MAP = {
    "dash": MSO_LINE_DASH_STYLE.DASH,
    "dot": MSO_LINE_DASH_STYLE.ROUND_DOT,
    "dashdot": MSO_LINE_DASH_STYLE.DASH_DOT,
    "solid": MSO_LINE_DASH_STYLE.SOLID,
}


@dataclass
class ShapeInfo:
    shape: object
    name: str
    kind: str
    x: float
    y: float
    w: float
    h: float
    z: int
    group: str | None = None

    @property
    def right(self) -> float:
        return self.x + self.w

    @property
    def bottom(self) -> float:
        return self.y + self.h

    @property
    def cx(self) -> float:
        return self.x + self.w / 2

    @property
    def cy(self) -> float:
        return self.y + self.h / 2

    def as_dict(self) -> dict:
        return {
            "name": self.name,
            "kind": self.kind,
            "x": round(self.x, 3),
            "y": round(self.y, 3),
            "w": round(self.w, 3),
            "h": round(self.h, 3),
            "z": self.z,
            **({"group": self.group} if self.group else {}),
        }


def _inches(value) -> float:
    return (value or 0) / EMU


def _prst(shape) -> str | None:
    el = shape._element.find(".//" + qn("a:prstGeom"))
    if el is None:
        return None
    return el.get("prst")


def shape_kind(shape) -> str:
    tag = shape._element.tag
    if tag == qn("p:cxnSp"):
        return "connector"
    if tag == qn("p:pic"):
        return "picture"
    if tag == qn("p:grpSp"):
        return "group"
    if tag == qn("p:graphicFrame"):
        return "frame"
    if tag == qn("p:sp"):
        cNv = shape._element.find(".//" + qn("p:cNvSpPr"))
        if cNv is not None and cNv.get("txBox") in ("1", "true"):
            return "text"
        return _prst(shape) or "shape"
    return "other"


def _group_frame(shape) -> tuple[float, float, float, float] | None:
    xfrm = shape._element.find(qn("p:grpSpPr"))
    if xfrm is None:
        return None
    xfrm = xfrm.find(qn("a:xfrm"))
    if xfrm is None:
        return None
    off = xfrm.find(qn("a:off"))
    ext = xfrm.find(qn("a:ext"))
    ch_off = xfrm.find(qn("a:chOff"))
    ch_ext = xfrm.find(qn("a:chExt"))
    if None in (off, ext, ch_off, ch_ext):
        return None
    return (
        _inches(int(off.get("x"))),
        _inches(int(off.get("y"))),
        _inches(int(ext.get("cx"))),
        _inches(int(ext.get("cy"))),
        _inches(int(ch_off.get("x"))),
        _inches(int(ch_off.get("y"))),
        _inches(int(ch_ext.get("cx"))),
        _inches(int(ch_ext.get("cy"))),
    )


def iter_shapes(slide, include_groups: bool = True) -> Iterator[ShapeInfo]:
    """Yield absolute geometry for every shape, flattening groups.

    Coordinates are in inches on the slide, even for children of groups.
    """

    def walk(shapes, tx, ty, sx, sy, group_name):
        for z, shape in enumerate(shapes):
            try:
                x = tx(_inches(shape.left))
                y = ty(_inches(shape.top))
                w = _inches(shape.width) * sx
                h = _inches(shape.height) * sy
            except TypeError:
                continue
            kind = shape_kind(shape)
            info = ShapeInfo(
                shape=shape,
                name=shape.name,
                kind=kind,
                x=x,
                y=y,
                w=w,
                h=h,
                z=z,
                group=group_name,
            )
            yield info
            if kind == "group" and include_groups:
                frame = _group_frame(shape)
                if not frame:
                    continue
                _ox, _oy, _ow, _oh, cx, cy, cw, ch = frame
                if not cw or not ch:
                    continue
                gx, gy, gw, gh = x, y, w, h
                csx, csy = gw / cw, gh / ch
                yield from walk(
                    shape.shapes,
                    lambda v, gx=gx, cx=cx, csx=csx: gx + (v - cx) * csx,
                    lambda v, gy=gy, cy=cy, csy=csy: gy + (v - cy) * csy,
                    csx,
                    csy,
                    group_name or shape.name,
                )

    yield from walk(slide.shapes, lambda v: v, lambda v: v, 1.0, 1.0, None)


def find_shape(slide, name: str):
    for info in iter_shapes(slide):
        if info.name == name:
            return info.shape
    raise KeyError(f"no shape named {name!r}")


def shape_by_id(slide) -> dict[int, ShapeInfo]:
    return {info.shape.shape_id: info for info in iter_shapes(slide)}


def describe_shape(
    info: ShapeInfo, infos: dict[int, ShapeInfo] | None = None
) -> dict:
    shape = info.shape
    data = info.as_dict()
    kind = info.kind
    if kind == "connector":
        c = connector_connections(shape)
        data["from_id"] = c.get("begin_id")
        data["to_id"] = c.get("end_id")
        data["from_side"] = INDEX_SIDE.get(c.get("begin_idx"))
        data["to_side"] = INDEX_SIDE.get(c.get("end_idx"))
        data["arrow"] = arrow_ends(shape)
        data["line"] = fill_hex(shape.line)
        data["line_width"] = line_width(shape)
        data["dash"] = dash_style(shape)
        x1, y1, x2, y2 = connector_endpoints(shape, infos)
        data["points"] = [
            [round(x1, 3), round(y1, 3)],
            [round(x2, 3), round(y2, 3)],
        ]
        return data

    text = text_of(shape)
    if text:
        data["text"] = text
        data["font_size"] = font_size_of(shape)
        data["bold"] = bool(first_run(shape) and first_run(shape).font.bold)
        data["align"] = paragraph_alignment(shape)
        data["valign"] = vertical_anchor(shape)
        data["text_color"] = text_color(shape)
        if "\n" in text:
            data["lines"] = text.split("\n")
    if kind not in ("picture", "group", "frame"):
        data["fill"] = fill_hex(shape.fill)
        data["line"] = fill_hex(shape.line)
        data["line_width"] = line_width(shape)
        data["dash"] = dash_style(shape)
    rotation = getattr(shape, "rotation", 0) or 0
    if rotation:
        data["rotation"] = round(rotation, 1)
    alt = alt_text(shape)
    if alt:
        data["alt"] = alt
    return data


# Connections are resolved in inspect.py where the full id -> name map is available.


def text_of(shape) -> str:
    if not getattr(shape, "has_text_frame", False):
        return ""
    return shape.text_frame.text


def first_run(shape):
    if not getattr(shape, "has_text_frame", False):
        return None
    for paragraph in shape.text_frame.paragraphs:
        if paragraph.runs:
            return paragraph.runs[0]
    return None


def font_size_of(shape) -> float | None:
    run = first_run(shape)
    if run is not None and run.font.size is not None:
        return round(run.font.size.pt, 2)
    return None


def text_color(shape) -> str | None:
    run = first_run(shape)
    if run is None:
        return None
    try:
        rgb = run.font.color.rgb
        if rgb is not None:
            return str(rgb)
    except (AttributeError, ValueError):
        pass
    try:
        return f"theme:{run.font.color.theme_color.name.lower()}"
    except (AttributeError, ValueError):
        return None


def paragraph_alignment(shape) -> str | None:
    if not getattr(shape, "has_text_frame", False):
        return None
    for p in shape.text_frame.paragraphs:
        if p.alignment is not None:
            return p.alignment.name.lower()
    return None


def vertical_anchor(shape) -> str | None:
    if not getattr(shape, "has_text_frame", False):
        return None
    anchor = shape.text_frame.vertical_anchor
    return anchor.name.lower() if anchor is not None else None


def alt_text(shape) -> str | None:
    el = shape._element.find(".//" + qn("p:cNvPr"))
    return el.get("descr") if el is not None else None


def set_alt_text(shape, text: str) -> None:
    el = shape._element.find(".//" + qn("p:cNvPr"))
    if el is not None:
        el.set("descr", text)


def fill_hex(fill) -> str | None:
    try:
        is_line = hasattr(fill, "color") and not hasattr(fill, "fore_color")
        fill_format = fill.fill if is_line else fill
        if fill_format.type is None:
            return None
        if fill_format.type.name == "BACKGROUND":
            return None
        if fill_format.type.name == "SOLID":
            color = fill.color if is_line else fill.fore_color
            try:
                return str(color.rgb)
            except (AttributeError, ValueError):
                try:
                    return f"theme:{color.theme_color.name.lower()}"
                except (AttributeError, ValueError):
                    return None
    except (AttributeError, ValueError):
        return None
    return None


def line_width(shape) -> float:
    try:
        w = shape.line.width
        if w is None:
            return 0.75
        return round(w.pt, 2)
    except (AttributeError, ValueError):
        return 0.75


def dash_style(shape) -> str:
    try:
        ln = shape.line._get_or_add_ln()
        el = ln.find(qn("a:prstDash"))
        if el is None:
            return "solid"
        value = el.get("val")
        return {
            "dash": "dash",
            "sysDash": "dash",
            "sysDot": "dot",
            "dot": "dot",
            "dashDot": "dashdot",
            "lgDash": "dash",
        }.get(value, value or "solid")
    except (AttributeError, ValueError):
        return "solid"


def connector_connections(shape) -> dict:
    out = {}
    for key, tag in (("begin", "a:stCxn"), ("end", "a:endCxn")):
        el = shape._element.find(".//" + qn(tag))
        if el is not None:
            out[f"{key}_id"] = int(el.get("id"))
            out[f"{key}_idx"] = int(el.get("idx"))
    return out


def arrow_ends(shape) -> str:
    ln = shape.line._get_or_add_ln()
    head = ln.find(qn("a:headEnd"))
    tail = ln.find(qn("a:tailEnd"))
    start = head is not None and head.get("type") not in (None, "none")
    end = tail is not None and tail.get("type") not in (None, "none")
    if start and end:
        return "both"
    if start:
        return "start"
    if end:
        return "end"
    return "none"


def set_arrow_ends(shape, ends: str) -> None:
    ln = shape.line._get_or_add_ln()
    for tag in ("a:headEnd", "a:tailEnd"):
        for el in ln.findall(qn(tag)):
            ln.remove(el)
    if ends in ("start", "both"):
        el = etree.SubElement(ln, qn("a:headEnd"))
        el.set("type", "triangle")
        el.set("w", "med")
        el.set("len", "med")
    if ends in ("end", "both"):
        el = etree.SubElement(ln, qn("a:tailEnd"))
        el.set("type", "triangle")
        el.set("w", "med")
        el.set("len", "med")


def set_connector_geometry(shape, x1: float, y1: float, x2: float, y2: float) -> None:
    x, y = min(x1, x2), min(y1, y2)
    w, h = abs(x2 - x1), abs(y2 - y1)
    shape.left, shape.top = Inches(x), Inches(y)
    shape.width, shape.height = Inches(max(w, 1 / 1000)), Inches(max(h, 1 / 1000))
    xfrm = shape._element.find(".//" + qn("a:xfrm"))
    if xfrm is None:
        return
    if x2 < x1:
        xfrm.set("flipH", "1")
    else:
        xfrm.attrib.pop("flipH", None)
    if y2 < y1:
        xfrm.set("flipV", "1")
    else:
        xfrm.attrib.pop("flipV", None)


def connector_endpoints(shape, infos: dict[int, ShapeInfo] | None = None):
    """Return (x1,y1,x2,y2) for a connector.

    If the connector is attached to shapes, endpoints are derived from the
    connection sites so the preview reflects the current layout.  Otherwise the
    stored geometry is used.
    """
    c = connector_connections(shape)
    if infos and c.get("begin_id") in infos and c.get("end_id") in infos:
        a = infos[c["begin_id"]]
        b = infos[c["end_id"]]
        x1, y1 = site_point(a, c.get("begin_idx", 3))
        x2, y2 = site_point(b, c.get("end_idx", 1))
        return x1, y1, x2, y2

    x = _inches(shape.left)
    y = _inches(shape.top)
    w = _inches(shape.width)
    h = _inches(shape.height)
    xfrm = shape._element.find(".//" + qn("a:xfrm"))
    flip_h = xfrm is not None and xfrm.get("flipH") in ("1", "true")
    flip_v = xfrm is not None and xfrm.get("flipV") in ("1", "true")
    x1, x2 = (x + w, x) if flip_h else (x, x + w)
    y1, y2 = (y + h, y) if flip_v else (y, y + h)
    return x1, y1, x2, y2


def site_point(info: ShapeInfo, idx: int) -> tuple[float, float]:
    side = INDEX_SIDE.get(idx, "right")
    if side == "top":
        return info.cx, info.y
    if side == "bottom":
        return info.cx, info.bottom
    if side == "left":
        return info.x, info.cy
    return info.right, info.cy


def reflow_connector(shape, infos: dict[int, ShapeInfo]) -> None:
    c = connector_connections(shape)
    if c.get("begin_id") not in infos or c.get("end_id") not in infos:
        return
    x1, y1, x2, y2 = connector_endpoints(shape, infos)
    set_connector_geometry(shape, x1, y1, x2, y2)


def reflow_all(slide) -> None:
    infos = shape_by_id(slide)
    for info in iter_shapes(slide):
        if info.kind == "connector":
            reflow_connector(info.shape, infos)


# ----------------------------- text formatting -----------------------------


def _set_ea(run, typeface: str | None = None) -> None:
    typeface = typeface or fonts.ea_font()
    rPr = run._r.get_or_add_rPr()
    ea = rPr.find(qn("a:ea"))
    if ea is None:
        ea = etree.Element(qn("a:ea"))
        cs = rPr.find(qn("a:cs"))
        if cs is not None:
            cs.addprevious(ea)
        else:
            rPr.append(ea)
    ea.set("typeface", typeface)


def set_run(
    run,
    font: str | None = None,
    size: float | None = None,
    color: str | None = None,
    bold: bool | None = None,
    italic: bool | None = None,
) -> None:
    run.font.name = font or fonts.latin_font()
    if size is not None:
        run.font.size = Pt(size)
    if color:
        run.font.color.rgb = RGBColor.from_string(color.lstrip("#").upper())
    if bold is not None:
        run.font.bold = bold
    if italic is not None:
        run.font.italic = italic
    _set_ea(run)


def set_text(
    shape,
    text: str,
    *,
    size: float = 10.5,
    color: str = "1E2833",
    bold: bool = False,
    italic: bool = False,
    align: str = "center",
    anchor: str = "middle",
    font: str | None = None,
    margins: tuple[float, float, float, float] | None = None,
) -> None:
    tf = shape.text_frame
    tf.clear()
    tf.word_wrap = True
    tf.auto_size = None
    if margins:
        left, right, top, bottom = margins
        tf.margin_left = Inches(left)
        tf.margin_right = Inches(right)
        tf.margin_top = Inches(top)
        tf.margin_bottom = Inches(bottom)
    else:
        tf.margin_left = tf.margin_right = Inches(0.06)
        tf.margin_top = tf.margin_bottom = Inches(0.025)
    alignment = {
        "left": PP_ALIGN.LEFT,
        "center": PP_ALIGN.CENTER,
        "right": PP_ALIGN.RIGHT,
    }.get(align, PP_ALIGN.CENTER)
    tf.vertical_anchor = {
        "top": MSO_ANCHOR.TOP,
        "middle": MSO_ANCHOR.MIDDLE,
        "bottom": MSO_ANCHOR.BOTTOM,
    }.get(anchor, MSO_ANCHOR.MIDDLE)

    lines = str(text).split("\n")
    for index, line in enumerate(lines):
        paragraph = tf.paragraphs[0] if index == 0 else tf.add_paragraph()
        paragraph.alignment = alignment
        paragraph.line_spacing = 1.0
        paragraph.space_before = Pt(0)
        paragraph.space_after = Pt(0)
        run = paragraph.add_run()
        run.text = line
        set_run(run, font=font or fonts.latin_font(), size=size, color=color, bold=bold, italic=italic)


def set_shape_style(
    shape,
    *,
    fill: str | None,
    line: str | None,
    line_width_pt: float = 1.0,
    dash: str = "solid",
    color: str | None = None,
    bold: bool | None = None,
    size: float | None = None,
) -> None:
    # Remove the theme style so shapes stay flat and do not acquire shadows.
    style = shape._element.find(qn("p:style"))
    if style is not None:
        shape._element.remove(style)

    is_connector = shape._element.tag == qn("p:cxnSp")
    if not is_connector:
        if fill is None:
            shape.fill.background()
        else:
            shape.fill.solid()
            shape.fill.fore_color.rgb = RGBColor.from_string(fill.lstrip("#").upper())

    if line is None:
        shape.line.fill.background()
    else:
        shape.line.color.rgb = RGBColor.from_string(line.lstrip("#").upper())
        shape.line.width = Pt(line_width_pt)
        shape.line.dash_style = DASH_MAP.get(dash, MSO_LINE_DASH_STYLE.SOLID)

    if color is not None and getattr(shape, "has_text_frame", False):
        for paragraph in shape.text_frame.paragraphs:
            for run in paragraph.runs:
                run.font.color.rgb = RGBColor.from_string(color.lstrip("#").upper())
                if bold is not None:
                    run.font.bold = bold
                if size is not None:
                    run.font.size = Pt(size)


def set_shape_text_style(
    shape,
    *,
    size: float,
    color: str,
    bold: bool,
    align: str,
    anchor: str,
) -> None:
    if not getattr(shape, "has_text_frame", False):
        return
    tf = shape.text_frame
    tf.vertical_anchor = {
        "top": MSO_ANCHOR.TOP,
        "middle": MSO_ANCHOR.MIDDLE,
        "bottom": MSO_ANCHOR.BOTTOM,
    }.get(anchor, MSO_ANCHOR.MIDDLE)
    alignment = {
        "left": PP_ALIGN.LEFT,
        "center": PP_ALIGN.CENTER,
        "right": PP_ALIGN.RIGHT,
    }.get(align, PP_ALIGN.CENTER)
    for paragraph in tf.paragraphs:
        paragraph.alignment = alignment
        for run in paragraph.runs:
            run.font.size = Pt(size)
            run.font.bold = bold
            run.font.color.rgb = RGBColor.from_string(color.lstrip("#").upper())
            _set_ea(run)


# ------------------------------- shape order -------------------------------


def _sp_tree(shape):
    return shape._element.getparent()


def send_to_back(shape) -> None:
    tree = _sp_tree(shape)
    tree.remove(shape._element)
    # p:nvGrpSpPr and p:grpSpPr must stay first.
    tree.insert(2, shape._element)


def bring_to_front(shape) -> None:
    tree = _sp_tree(shape)
    tree.remove(shape._element)
    tree.append(shape._element)


def send_backward(shape) -> None:
    tree = _sp_tree(shape)
    index = tree.index(shape._element)
    if index > 2:
        tree.remove(shape._element)
        tree.insert(index - 1, shape._element)


def bring_forward(shape) -> None:
    tree = _sp_tree(shape)
    index = tree.index(shape._element)
    if index < len(tree) - 1:
        tree.remove(shape._element)
        tree.insert(index + 1, shape._element)


def delete_shape(shape) -> None:
    tree = _sp_tree(shape)
    tree.remove(shape._element)


def z_index(shape) -> int:
    return list(_sp_tree(shape)).index(shape._element)


# ------------------------------- constructors ------------------------------


def add_autoshape(slide, kind: str, x: float, y: float, w: float, h: float):
    shape_type = SHAPE_MAP.get(kind)
    if shape_type is None:
        raise ValueError(
            f"unknown shape {kind!r}; choose from {', '.join(sorted(SHAPE_MAP))}"
        )
    shape = slide.shapes.add_shape(
        shape_type, Inches(x), Inches(y), Inches(w), Inches(h)
    )
    return shape


def add_connector(
    slide,
    kind: str,
    x1: float,
    y1: float,
    x2: float,
    y2: float,
    begin_shape=None,
    begin_idx: int | None = None,
    end_shape=None,
    end_idx: int | None = None,
):
    connector_type = MSO_CONNECTOR.ELBOW if kind == "elbow" else MSO_CONNECTOR.STRAIGHT
    connector = slide.shapes.add_connector(
        connector_type, Inches(x1), Inches(y1), Inches(x2), Inches(y2)
    )
    if begin_shape is not None and end_shape is not None:
        connector.begin_connect(begin_shape, begin_idx if begin_idx is not None else 3)
        connector.end_connect(end_shape, end_idx if end_idx is not None else 1)
        infos = shape_by_id(slide)
        reflow_connector(connector, infos)
    else:
        set_connector_geometry(connector, x1, y1, x2, y2)
    return connector


def ensure_round_radius(shape) -> None:
    try:
        if shape.adjustments and len(shape.adjustments):
            shape.adjustments[0] = 0.12
    except (AttributeError, IndexError):
        pass


def set_background(slide, color: str = "FFFFFF") -> None:
    fill = slide.background.fill
    fill.solid()
    fill.fore_color.rgb = RGBColor.from_string(color)


def snap(value: float, grid: float = 0.05) -> float:
    return round(round(value / grid) * grid, 3)


def distance(a: tuple[float, float], b: tuple[float, float]) -> float:
    return math.hypot(a[0] - b[0], a[1] - b[1])
