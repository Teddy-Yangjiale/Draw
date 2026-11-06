from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image
from pptx import Presentation
from pptx.util import Inches

from pptdraw.deck import new_deck
from pptdraw.inspect import inspect_deck
from pptdraw.ops import apply_ops
from pptdraw.quality import lint_deck


def _png(path: Path, color=(220, 235, 248)) -> str:
    Image.new("RGB", (160, 100), color).save(path)
    return str(path)


def _basic_ops(image: str) -> dict:
    return {
        "slide": 1,
        "ops": [
            {
                "op": "add_shape",
                "name": "fig.encoder",
                "shape": "roundRect",
                "x": 0.7,
                "y": 0.8,
                "w": 1.2,
                "h": 0.55,
                "text": "Image\nEncoder",
                "style": "green",
                "font_size": 10,
            },
            {
                "op": "add_shape",
                "name": "fig.decoder",
                "shape": "roundRect",
                "x": 3.9,
                "y": 0.8,
                "w": 1.2,
                "h": 0.55,
                "text": "Task\nDecoder",
                "style": "orange",
                "font_size": 10,
            },
            {
                "op": "add_picture",
                "name": "fig.input",
                "path": image,
                "x": 0.1,
                "y": 0.82,
                "w": 0.45,
                "h": 0.5,
            },
            {
                "op": "add_container",
                "name": "fig.container.demo",
                "around": ["fig.encoder", "fig.decoder"],
                "label": "Demo block",
                "top_pad": 0.25,
            },
            {
                "op": "add_connector",
                "name": "fig.edge.encoder--decoder",
                "from": "fig.encoder",
                "to": "fig.decoder",
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
                "offset": 0.65,
                "dash": "dash",
                "arrow": "end",
                "label": "skip",
            },
            {
                "op": "add_text",
                "name": "fig.panel",
                "text": "(a) Demo",
                "x": 0.1,
                "y": 0.1,
                "w": 1.2,
                "h": 0.22,
                "font_size": 9,
                "align": "left",
                "anchor": "top",
            },
            {"op": "normalize_z"},
        ],
    }


def test_build_inspect_and_lint(tmp_path: Path):
    image = _png(tmp_path / "input.png")
    deck = tmp_path / "figure.pptx"
    new_deck(deck, size=(7.16, 2.6), title="test")
    report = apply_ops(deck, _basic_ops(image), base_dir=tmp_path)

    assert deck.exists()
    assert report["output"] == str(deck.resolve())
    data = inspect_deck(deck)
    names = {s["name"] for s in data["shapes"]}
    assert {
        "fig.encoder",
        "fig.decoder",
        "fig.input",
        "fig.container.demo",
        "fig.edge.encoder--decoder",
        "fig.edge.skip.seg1",
        "fig.edge.skip.seg2",
        "fig.edge.skip.anchor",
    } <= names

    connectors = {s["name"]: s for s in data["shapes"] if s["kind"] == "connector"}
    assert connectors["fig.edge.encoder--decoder"]["from"] == "fig.encoder"
    assert connectors["fig.edge.encoder--decoder"]["to"] == "fig.decoder"
    assert connectors["fig.edge.encoder--decoder"]["arrow"] == "end"

    assert lint_deck(deck) == []


def test_set_text_style_move_and_backup(tmp_path: Path):
    deck = tmp_path / "figure.pptx"
    new_deck(deck, size=(7.16, 2.6))
    image = _png(tmp_path / "input.png")
    apply_ops(deck, _basic_ops(image), base_dir=tmp_path, backup=False)

    ops = {
        "ops": [
            {"op": "set_text", "name": "fig.encoder", "text": "ViT-B"},
            {
                "op": "set_style",
                "name": "fig.decoder",
                "style": "accent",
                "line_width": 1.2,
            },
            {"op": "move", "name": "fig.decoder", "dx": 0.1, "dy": 0.05},
            {"op": "resize", "name": "fig.encoder", "w": 1.35},
        ]
    }
    report = apply_ops(deck, ops)
    assert report["backup"] is not None
    assert Path(report["backup"]).exists()

    data = inspect_deck(deck)
    by_name = {s["name"]: s for s in data["shapes"]}
    assert by_name["fig.encoder"]["text"] == "ViT-B"
    assert by_name["fig.encoder"]["w"] == pytest.approx(1.35, abs=0.01)
    assert by_name["fig.decoder"]["fill"] == "FBE7D8"
    assert by_name["fig.decoder"]["x"] == pytest.approx(4.0, abs=0.01)


def test_delete_cascades_detour(tmp_path: Path):
    deck = tmp_path / "figure.pptx"
    new_deck(deck)
    image = _png(tmp_path / "input.png")
    apply_ops(deck, _basic_ops(image), base_dir=tmp_path, backup=False)
    apply_ops(deck, {"ops": [{"op": "delete", "name": "fig.encoder"}]}, backup=False)

    names = {s["name"] for s in inspect_deck(deck)["shapes"]}
    assert "fig.encoder" not in names
    assert "fig.edge.encoder--decoder" not in names
    assert not any(n.startswith("fig.edge.skip") for n in names)
    assert "fig.decoder" in names


def test_image_grid(tmp_path: Path):
    images = [_png(tmp_path / f"img{i}.png", color=(200 + i, 220, 240 - i)) for i in range(4)]
    deck = tmp_path / "grid.pptx"
    new_deck(deck, size=(3.5, 2.3))
    ops = {
        "ops": [
            {
                "op": "add_image_grid",
                "images": images,
                "labels": ["A", "B", "C", "D"],
                "cols": 2,
                "x": 0.2,
                "y": 0.3,
                "cell_w": 1.4,
                "cell_h": 0.8,
                "gap": 0.1,
                "label_h": 0.18,
                "prefix": "fig.image.test",
            },
            {"op": "normalize_z"},
        ]
    }
    apply_ops(deck, ops, backup=False)
    names = {s["name"] for s in inspect_deck(deck)["shapes"]}
    assert {f"fig.image.test.{i}" for i in range(1, 5)} <= names
    assert {f"fig.label.test.{i}" for i in range(1, 5)} <= names


def test_group_children_are_readable(tmp_path: Path):
    deck = tmp_path / "group.pptx"
    new_deck(deck)
    prs = Presentation(deck)
    slide = prs.slides[0]
    group = slide.shapes.add_group_shape()
    group.name = "fig.group.test"
    group.shapes.add_shape(1, Inches(1), Inches(1), Inches(0.5), Inches(0.3))
    group.shapes.add_shape(1, Inches(2), Inches(1), Inches(0.5), Inches(0.3))
    prs.save(deck)

    children = [s for s in inspect_deck(deck)["shapes"] if s.get("group") == "fig.group.test"]
    assert len(children) == 2
    assert all(s["role"] == "node" for s in children)


def test_duplicate_name_is_rejected(tmp_path: Path):
    deck = tmp_path / "figure.pptx"
    new_deck(deck)
    image = _png(tmp_path / "input.png")
    apply_ops(deck, _basic_ops(image), base_dir=tmp_path, backup=False)
    with pytest.raises(RuntimeError, match="already exists"):
        apply_ops(
            deck,
            {
                "ops": [
                    {
                        "op": "add_shape",
                        "name": "fig.encoder",
                        "x": 0,
                        "y": 0,
                        "w": 1,
                        "h": 0.5,
                        "text": "duplicate",
                    }
                ]
            },
            backup=False,
        )


def test_cjk_text_roundtrip(tmp_path: Path):
    deck = tmp_path / "cjk.pptx"
    new_deck(deck)
    apply_ops(
        deck,
        {
            "ops": [
                {
                    "op": "add_shape",
                    "name": "fig.cjk",
                    "x": 0.5,
                    "y": 0.5,
                    "w": 1.6,
                    "h": 0.6,
                    "text": "编码器 Encoder",
                    "style": "blue",
                    "font_size": 10,
                }
            ]
        },
        backup=False,
    )
    data = inspect_deck(deck)
    shape = next(s for s in data["shapes"] if s["name"] == "fig.cjk")
    assert "编码器" in shape["text"]


def test_fit_canvas_crops_to_content(tmp_path: Path):
    deck = tmp_path / "fit.pptx"
    new_deck(deck, size=(7.16, 2.6))
    apply_ops(
        deck,
        {
            "ops": [
                {
                    "op": "add_shape",
                    "name": "fig.only",
                    "x": 2.0,
                    "y": 1.0,
                    "w": 1.2,
                    "h": 0.5,
                    "text": "Only",
                },
                {"op": "fit_canvas", "margin": 0.1},
            ]
        },
        backup=False,
    )
    prs = Presentation(str(deck))
    assert prs.slide_width / 914400 < 2.0
    assert prs.slide_height / 914400 <= 1.0
    data = inspect_deck(deck)
    shape = next(s for s in data["shapes"] if s["name"] == "fig.only")
    assert shape["x"] == pytest.approx(0.1, abs=0.02)
    assert shape["y"] == pytest.approx(0.25, abs=0.02)
