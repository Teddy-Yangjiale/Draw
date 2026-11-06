"""A small CLI for AI-assisted, human-editable paper figures."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

from . import __version__
from .deck import PRESETS, new_deck, parse_size
from .inspect import inspect_deck, outline
from .ops import apply_ops
from .preview import available_engines, find_libreoffice, render
from .quality import lint_data


def _load_json(path: str | Path) -> dict:
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def _dump(data) -> str:
    return json.dumps(data, ensure_ascii=False, indent=2)


def cmd_new(args) -> int:
    if args.size in PRESETS:
        size = PRESETS[args.size]
    else:
        size = parse_size(args.size)
    path = new_deck(args.output, size=size, title=args.title)
    print(
        _dump(
            {
                "output": str(path),
                "canvas": {"width": size[0], "height": size[1]},
            }
        )
    )
    return 0


def cmd_demo(args) -> int:
    from .demo import build_demo

    output = Path(args.output)
    if output.suffix.lower() != ".pptx":
        output = output.with_suffix(".pptx")
    if output.exists() and not args.force:
        print(f"error: {output} already exists; pass --force to overwrite", file=sys.stderr)
        return 2
    report = build_demo(output, args.assets)
    if args.png:
        png = Path(args.png) if args.png != "auto" else output.with_suffix(".png")
        info = render(output, png, dpi=args.dpi)
        report["preview"] = info
    print(_dump(report))
    return 0


def cmd_inspect(args) -> int:
    data = inspect_deck(args.file, args.slide, include_lint=not args.no_lint)
    if args.png:
        info = render(args.file, args.png, dpi=args.dpi, slide_no=args.slide)
        data["preview"] = info
    text = _dump(data) if args.format == "json" else outline(data)
    if args.out:
        Path(args.out).write_text(text + "\n", encoding="utf-8")
        print(f"wrote {args.out}")
    else:
        print(text)
    return 0


def cmd_lint(args) -> int:
    data = inspect_deck(args.file, args.slide, include_lint=True)
    issues = data["issues"]
    if args.format == "json":
        print(_dump({"file": data["file"], "issues": issues, "count": len(issues)}))
    else:
        if not issues:
            print("✓ no mechanical issues found")
        for issue in issues:
            print(f"[{issue['severity']}] {issue['type']}: {issue['message']}")
        print(f"\n{len(issues)} issue(s)")
    return 1 if any(i["severity"] == "error" for i in issues) else 0


def cmd_render(args) -> int:
    info = render(
        args.file,
        args.output,
        dpi=args.dpi,
        slide_no=args.slide,
        engine=args.engine,
    )
    print(_dump(info))
    return 0


def cmd_apply(args) -> int:
    doc = _load_json(args.ops)
    if args.slide is not None:
        doc["slide"] = args.slide
    report = apply_ops(
        args.deck,
        doc,
        out_path=args.output,
        base_dir=Path(args.ops).resolve().parent,
        backup=not args.no_backup,
    )
    if args.png:
        png = Path(args.png) if args.png != "auto" else Path(report["output"]).with_suffix(".png")
        report["preview"] = render(report["output"], png, dpi=args.dpi)
    print(_dump(report))
    return 0


def cmd_undo(args) -> int:
    deck = Path(args.deck).resolve()
    hist = deck.parent / ".pptdraw" / "history"
    backups = sorted(hist.glob(f"{deck.stem}-*.pptx"))
    if not backups:
        print(f"no backup found in {hist}", file=sys.stderr)
        return 2
    latest = backups[-1]
    if deck.exists() and not args.no_backup:
        from datetime import datetime

        stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")[:-3]
        shutil.copyfile(deck, hist / f"{deck.stem}-{stamp}-before-undo.pptx.bak")
    shutil.copyfile(latest, deck)
    latest.unlink(missing_ok=True)
    print(_dump({"restored": str(deck), "from": str(latest)}))
    return 0


def cmd_export_pdf(args) -> int:
    soffice = find_libreoffice()
    if not soffice:
        print(
            "error: LibreOffice not found. Open the .pptx in WPS/PowerPoint and "
            "export as PDF (vector), or install LibreOffice.",
            file=sys.stderr,
        )
        return 2
    import subprocess
    import tempfile

    src = Path(args.file).resolve()
    dst = Path(args.output).resolve()
    dst.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="pptdraw-pdf-") as td:
        subprocess.run(
            [soffice, "--headless", "--convert-to", "pdf", "--outdir", td, str(src)],
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=180,
        )
        pdf = Path(td) / f"{src.stem}.pdf"
        if not pdf.exists():
            print("error: LibreOffice did not produce a PDF", file=sys.stderr)
            return 2
        shutil.copyfile(pdf, dst)
    print(_dump({"pdf": str(dst)}))
    return 0


def cmd_doctor(args) -> int:
    from .fonts import describe as describe_fonts
    from .textutil import font_path

    engines = available_engines()
    fonts = describe_fonts()
    try:
        font = font_path()
    except Exception as exc:
        font = f"NOT FOUND ({exc})"
    print(f"pptdraw {__version__}")
    print(f"os: {sys.platform}")
    print(f"python: {sys.version.split()[0]}")
    try:
        import pptx

        print(f"python-pptx: {pptx.__version__}")
    except Exception:
        print("python-pptx: MISSING")
    print(f"measurement font: {font}")
    print(f"pptx latin font: {fonts['pptx_latin']}")
    print(f"pptx east-asian font: {fonts['pptx_east_asian']}")
    print(f"Quick Look: {engines['quicklook']}")
    print(f"LibreOffice: {engines['libreoffice'] or 'not found'}")
    print(f"PowerPoint COM: {engines['powerpoint']}")
    print(f"PyMuPDF: {engines['pymupdf']}")
    if sys.platform == "darwin":
        print(f"WPS app: {Path('/Applications/wpsoffice.app').exists()}")
    if not engines["libreoffice"] and not engines["quicklook"] and not engines["powerpoint"]:
        print("warning: no preview renderer; inspect/apply still work")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="pptdraw",
        description="AI-editable, human-editable paper figures as native PPTX.",
    )
    parser.add_argument("--version", action="version", version=__version__)
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("new", help="create a blank paper-sized deck")
    p.add_argument("output")
    p.add_argument("--size", default="double", help="preset or WxH inches")
    p.add_argument("--title", default="Paper figure")
    p.set_defaults(func=cmd_new)

    p = sub.add_parser("demo", help="build the CVPR-style demo deck")
    p.add_argument("output", nargs="?", default="out/cvpr_demo.pptx")
    p.add_argument("--assets", default="out/assets")
    p.add_argument("--png", nargs="?", const="auto", default=None)
    p.add_argument("--dpi", type=int, default=220)
    p.add_argument("--force", action="store_true")
    p.set_defaults(func=cmd_demo)

    p = sub.add_parser("inspect", help="print the slide as LLM-readable structure")
    p.add_argument("file")
    p.add_argument("--slide", type=int, default=1)
    p.add_argument("--format", choices=["outline", "json"], default="outline")
    p.add_argument("--json", dest="format", action="store_const", const="json")
    p.add_argument("--no-lint", action="store_true")
    p.add_argument("--png", default=None, help="also render a preview PNG")
    p.add_argument("--dpi", type=int, default=220)
    p.add_argument("--out", default=None)
    p.set_defaults(func=cmd_inspect)

    p = sub.add_parser("apply", help="apply semantic edit operations to a deck")
    p.add_argument("deck")
    p.add_argument("ops")
    p.add_argument("-o", "--output", default=None)
    p.add_argument("--slide", type=int, default=None)
    p.add_argument("--png", nargs="?", const="auto", default=None)
    p.add_argument("--dpi", type=int, default=220)
    p.add_argument("--no-backup", action="store_true")
    p.set_defaults(func=cmd_apply)

    p = sub.add_parser("render", help="render a slide to PNG")
    p.add_argument("file")
    p.add_argument("-o", "--output", required=True)
    p.add_argument("--slide", type=int, default=1)
    p.add_argument("--dpi", type=int, default=220)
    p.add_argument("--engine", choices=["auto", "quicklook", "libreoffice", "powerpoint"], default="auto")
    p.set_defaults(func=cmd_render)

    p = sub.add_parser("lint", help="check overlaps, overflow and off-canvas shapes")
    p.add_argument("file")
    p.add_argument("--slide", type=int, default=1)
    p.add_argument("--format", choices=["text", "json"], default="text")
    p.set_defaults(func=cmd_lint)

    p = sub.add_parser("undo", help="restore the latest backup")
    p.add_argument("deck")
    p.add_argument("--no-backup", action="store_true")
    p.set_defaults(func=cmd_undo)

    p = sub.add_parser("export-pdf", help="convert to vector PDF with LibreOffice")
    p.add_argument("file")
    p.add_argument("-o", "--output", required=True)
    p.set_defaults(func=cmd_export_pdf)

    p = sub.add_parser("doctor", help="show installed renderers and fonts")
    p.set_defaults(func=cmd_doctor)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
