"""Approximate quality checks for paper figures.

These are not aesthetic judgments.  They catch the mechanical mistakes an LLM
makes most often: overlapping boxes, text that spills out, shapes outside the
slide, unreadably small labels, and duplicate semantic names.
"""

from __future__ import annotations

from .textutil import block_size


def _rects_overlap(a: dict, b: dict) -> tuple[bool, float]:
    x1 = max(a["x"], b["x"])
    y1 = max(a["y"], b["y"])
    x2 = min(a["x"] + a["w"], b["x"] + b["w"])
    y2 = min(a["y"] + a["h"], b["y"] + b["h"])
    if x2 <= x1 or y2 <= y1:
        return False, 0.0
    area = (x2 - x1) * (y2 - y1)
    smaller = min(a["w"] * a["h"], b["w"] * b["h"])
    return area / max(smaller, 1e-9) > 0.12, area


def lint_data(data: dict) -> list[dict]:
    issues: list[dict] = []
    canvas = data["canvas"]
    shapes = data.get("shapes", [])
    names = [s["name"] for s in shapes]

    duplicates = sorted({n for n in names if names.count(n) > 1})
    for name in duplicates:
        issues.append(
            {
                "severity": "error",
                "type": "duplicate_name",
                "message": f"duplicate shape name {name!r}; semantic names must be unique",
                "shapes": [name],
            }
        )

    for s in shapes:
        if s["kind"] == "connector":
            continue
        if (
            s["x"] < -0.01
            or s["y"] < -0.01
            or s["x"] + s["w"] > canvas["width"] + 0.01
            or s["y"] + s["h"] > canvas["height"] + 0.01
        ):
            issues.append(
                {
                    "severity": "error",
                    "type": "off_canvas",
                    "message": (
                        f"{s['name']} extends outside the "
                        f"{canvas['width']:.2f} x {canvas['height']:.2f} in canvas"
                    ),
                    "shapes": [s["name"]],
                }
            )

        text = s.get("text") or ""
        if text:
            size = s.get("font_size") or 10.5
            if size < 8:
                issues.append(
                    {
                        "severity": "warn",
                        "type": "small_font",
                        "message": f"{s['name']} uses {size:g} pt; below 8 pt is hard to read in print",
                        "shapes": [s["name"]],
                    }
                )
            if s["role"] in ("node", "image", "text", "label"):
                pad_w = 0.12 if s["role"] != "label" else 0.02
                pad_h = 0.05 if s["role"] != "label" else 0.01
                _, block_h, lines = block_size(
                    text, size, max(0.05, s["w"] - pad_w)
                )
                if block_h > s["h"] - pad_h + 0.015:
                    issues.append(
                        {
                            "severity": "warn",
                            "type": "text_overflow",
                            "message": (
                                f"{s['name']} text likely overflows: "
                                f"{len(lines)} line(s) need {block_h:.2f} in, box is {s['h']:.2f} in"
                            ),
                            "shapes": [s["name"]],
                        }
                    )

    nodes = [
        s
        for s in shapes
        if s["role"] in ("node", "image")
        and s["kind"] != "connector"
        and not s.get("group")
    ]
    for i, a in enumerate(nodes):
        for b in nodes[i + 1 :]:
            overlap, area = _rects_overlap(a, b)
            if overlap:
                issues.append(
                    {
                        "severity": "warn",
                        "type": "overlap",
                        "message": (
                            f"{a['name']} overlaps {b['name']} by {area:.2f} in²"
                        ),
                        "shapes": [a["name"], b["name"]],
                    }
                )

    labels = [s for s in shapes if s["role"] == "label" and s.get("text")]
    for label in labels:
        for node in nodes:
            overlap, area = _rects_overlap(label, node)
            if overlap:
                issues.append(
                    {
                        "severity": "warn",
                        "type": "label_overlap",
                        "message": (
                            f"label {label['name']} sits on top of {node['name']} "
                            f"({area:.2f} in² overlap)"
                        ),
                        "shapes": [label["name"], node["name"]],
                    }
                )

    bounds = data.get("bounds")
    if bounds:
        if bounds["x"] < 0.04 or bounds["y"] < 0.04:
            issues.append(
                {
                    "severity": "warn",
                    "type": "tight_margin",
                    "message": "content is closer than 0.04 in to the canvas edge",
                    "shapes": [],
                }
            )

    return issues


def lint_deck(path: str, slide_no: int = 1) -> list[dict]:
    from .inspect import inspect_deck

    return inspect_deck(path, slide_no, include_lint=True)["issues"]
