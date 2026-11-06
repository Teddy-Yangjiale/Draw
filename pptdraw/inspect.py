"""Turn a .pptx into a compact, LLM-readable scene description."""

from __future__ import annotations

from pathlib import Path

from pptx import Presentation

from . import pptxutil as pu


def _role(name: str, kind: str, text: str, alt: str = "") -> str:
    if kind == "connector":
        return "edge"
    if kind == "group":
        return "group"
    if alt.startswith("pptdraw:route-anchor:"):
        return "route"
    if name.startswith("fig.container") or alt.startswith("pptdraw:container:"):
        return "container"
    if (
        alt.startswith("pptdraw:edge-label:")
        or alt.startswith("pptdraw:detour-label:")
        or "label" in name
        or name.startswith("fig.caption")
    ):
        return "label"
    if kind == "text":
        return "text"
    if kind == "picture":
        return "image"
    return "node"


def inspect_deck(path: str | Path, slide_no: int = 1, include_lint: bool = True) -> dict:
    prs = Presentation(str(path))
    if slide_no < 1 or slide_no > len(prs.slides):
        raise ValueError(f"slide {slide_no} out of range (1..{len(prs.slides)})")
    slide = prs.slides[slide_no - 1]
    infos = list(pu.iter_shapes(slide))
    by_id = {info.shape.shape_id: info for info in infos}
    id_to_name = {sid: info.name for sid, info in by_id.items()}

    shapes = []
    connectors = []
    for info in infos:
        data = pu.describe_shape(info, by_id)
        alt = pu.alt_text(info.shape) or ""
        data["role"] = _role(info.name, info.kind, data.get("text", ""), alt)
        if info.kind == "connector":
            data["from"] = id_to_name.get(data.get("from_id"))
            data["to"] = id_to_name.get(data.get("to_id"))
            data.pop("from_id", None)
            data.pop("to_id", None)
            connectors.append(data)
        shapes.append(data)

    points: list[tuple[float, float]] = []
    for s in shapes:
        if s["kind"] == "connector":
            points.extend((p[0], p[1]) for p in s.get("points", []))
        else:
            points.extend(
                [(s["x"], s["y"]), (s["x"] + s["w"], s["y"] + s["h"])]
            )
    if points:
        bounds = {
            "x": round(min(p[0] for p in points), 3),
            "y": round(min(p[1] for p in points), 3),
            "right": round(max(p[0] for p in points), 3),
            "bottom": round(max(p[1] for p in points), 3),
        }
    else:
        bounds = None

    result = {
        "file": str(Path(path).resolve()),
        "slide": slide_no,
        "slides": len(prs.slides),
        "canvas": {
            "width": round(prs.slide_width / pu.EMU, 3),
            "height": round(prs.slide_height / pu.EMU, 3),
        },
        "name": prs.core_properties.title or Path(path).stem,
        "shape_count": len(shapes),
        "connector_count": len(connectors),
        "bounds": bounds,
        "shapes": shapes,
    }
    if include_lint:
        from .quality import lint_data

        issues = lint_data(result)
        result["issues"] = issues
        result["issue_count"] = len(issues)
    return result


def outline(data: dict) -> str:
    """Compact text view: much cheaper than JSON for an LLM to read."""
    c = data["canvas"]
    lines = [
        f"# {Path(data['file']).name}  slide {data['slide']}  "
        f"{c['width']:.2f} x {c['height']:.2f} in  "
        f"{data['shape_count']} shapes"
    ]
    if data.get("bounds"):
        b = data["bounds"]
        lines.append(
            f"# content bounds x={b['x']:.2f} y={b['y']:.2f} "
            f"right={b['right']:.2f} bottom={b['bottom']:.2f}"
        )
    for s in data["shapes"]:
        if s["kind"] == "connector":
            if s.get("from") or s.get("to"):
                route = (
                    f"{s.get('from') or '?'}.{s.get('from_side') or '?'}"
                    f" -> {s.get('to') or '?'}.{s.get('to_side') or '?'}"
                )
            else:
                pts = s.get("points") or []
                route = (
                    f"({pts[0][0]:.2f},{pts[0][1]:.2f}) -> "
                    f"({pts[-1][0]:.2f},{pts[-1][1]:.2f})"
                    if len(pts) >= 2
                    else "free"
                )
            lines.append(
                f"[edge] {s['name']}: {route}"
                f"  arrow={s.get('arrow')} dash={s.get('dash')}"
            )
            continue
        text = (s.get("text") or "").replace("\n", " / ")
        text = f'  "{text}"' if text else ""
        role = s.get("role", "?")
        group = f"  [in {s['group']}]" if s.get("group") else ""
        lines.append(
            f"[{role}:{s['kind']}] {s['name']}  "
            f"({s['x']:.2f},{s['y']:.2f})-({s['x'] + s['w']:.2f},{s['y'] + s['h']:.2f})"
            f"{text}{group}"
        )
    if data.get("issues"):
        lines.append(f"# {len(data['issues'])} lint issue(s)")
        for issue in data["issues"]:
            lines.append(
                f"  ! [{issue['severity']}] {issue['type']}: {issue['message']}"
            )
    return "\n".join(lines)
