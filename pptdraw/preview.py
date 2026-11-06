"""Render a PPTX slide to PNG for the AI's visual check.

Renderer order:
  macOS   : Quick Look (WPS/PowerPoint plugin) -> LibreOffice
  Windows : LibreOffice -> PowerPoint COM automation
  Linux   : LibreOffice

The final, authoritative render is always WPS/PowerPoint itself.  This preview is
for layout iteration, not for camera-ready output.
"""

from __future__ import annotations

import hashlib
import os
import platform
import shutil
import subprocess
import tempfile
from pathlib import Path

from pptx import Presentation
from pptx.oxml.ns import qn

from . import pptxutil as pu


def _single_slide_copy(src: Path, dst: Path, slide_no: int) -> None:
    prs = Presentation(str(src))
    if slide_no < 1 or slide_no > len(prs.slides):
        raise ValueError(f"slide {slide_no} out of range (1..{len(prs.slides)})")
    if len(prs.slides) == 1:
        shutil.copyfile(src, dst)
        return
    sld_ids = prs.slides._sldIdLst
    for index, sld_id in enumerate(list(sld_ids)):
        if index == slide_no - 1:
            continue
        r_id = sld_id.get(qn("r:id"))
        if r_id:
            prs.part.drop_rel(r_id)
        sld_ids.remove(sld_id)
    prs.save(str(dst))


def find_libreoffice() -> str | None:
    for name in ("soffice", "libreoffice"):
        found = shutil.which(name)
        if found:
            return found
    system = platform.system()
    candidates: list[str] = []
    if system == "Darwin":
        candidates = [
            "/Applications/LibreOffice.app/Contents/MacOS/soffice",
            "/opt/homebrew/bin/soffice",
            "/usr/local/bin/soffice",
        ]
    elif system == "Windows":
        candidates = [
            r"C:\Program Files\LibreOffice\program\soffice.exe",
            r"C:\Program Files (x86)\LibreOffice\program\soffice.exe",
        ]
        local = os.environ.get("LOCALAPPDATA")
        if local:
            candidates.append(str(Path(local) / "Programs/LibreOffice/program/soffice.exe"))
    for candidate in candidates:
        if Path(candidate).exists():
            return candidate
    return None


def _powershell() -> str | None:
    return shutil.which("powershell") or shutil.which("pwsh")


def _has_pymupdf() -> bool:
    try:
        import pymupdf  # noqa: F401

        return True
    except Exception:
        return False


def _quicklook(tmp: Path, out: Path, px: int) -> bool:
    exe = shutil.which("qlmanage")
    if not exe or platform.system() != "Darwin":
        return False
    work = tmp.parent / "ql"
    work.mkdir(exist_ok=True)
    try:
        subprocess.run(
            [exe, "-t", "-s", str(px), "-o", str(work), str(tmp)],
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=90,
        )
    except (subprocess.TimeoutExpired, OSError):
        return False
    produced = work / f"{tmp.name}.png"
    if not produced.exists():
        candidates = list(work.glob("*.png"))
        if not candidates:
            return False
        produced = candidates[0]
    shutil.copyfile(produced, out)
    return True


def _libreoffice_pdf(
    exe: str, tmp: Path, out: Path, slide_no: int, dpi: int
) -> bool:
    work = tmp.parent / "lo"
    work.mkdir(exist_ok=True)
    try:
        subprocess.run(
            [
                exe,
                "--headless",
                "--convert-to",
                "pdf",
                "--outdir",
                str(work),
                str(tmp),
            ],
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=180,
        )
    except (subprocess.TimeoutExpired, OSError):
        return False
    pdf = work / f"{tmp.stem}.pdf"
    if not pdf.exists():
        return False

    if _has_pymupdf():
        try:
            import pymupdf

            doc = pymupdf.open(pdf)
            page = doc[min(slide_no - 1, doc.page_count - 1)]
            pix = page.get_pixmap(dpi=dpi, alpha=False)
            pix.save(str(out))
            return True
        except Exception:
            pass

    pdftoppm = shutil.which("pdftoppm")
    if pdftoppm:
        prefix = work / "page"
        try:
            subprocess.run(
                [
                    pdftoppm,
                    "-f",
                    str(slide_no),
                    "-singlefile",
                    "-r",
                    str(dpi),
                    "-png",
                    str(pdf),
                    str(prefix),
                ],
                check=False,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=90,
            )
            produced = work / "page.png"
            if produced.exists():
                shutil.copyfile(produced, out)
                return True
        except (subprocess.TimeoutExpired, OSError):
            pass
    return False


def _libreoffice_png(exe: str, tmp: Path, out: Path) -> bool:
    """Last-resort logo preview if PDF rendering is unavailable."""
    work = tmp.parent / "lo_png"
    work.mkdir(exist_ok=True)
    try:
        subprocess.run(
            [
                exe,
                "--headless",
                "--convert-to",
                "png",
                "--outdir",
                str(work),
                str(tmp),
            ],
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=120,
        )
    except (subprocess.TimeoutExpired, OSError):
        return False
    produced = work / f"{tmp.stem}.png"
    if not produced.exists():
        candidates = list(work.glob("*.png"))
        if not candidates:
            return False
        produced = candidates[0]
    shutil.copyfile(produced, out)
    return True


def _powerpoint(tmp: Path, out: Path, width: int, height: int) -> bool:
    """Windows-only: use PowerPoint COM to export slide 1 as PNG."""
    if platform.system() != "Windows":
        return False
    powershell = _powershell()
    if not powershell:
        return False
    script = tmp.parent / "export.ps1"
    script.write_text(
        "\n".join(
            [
                "param([string]$In,[string]$Out,[int]$Width,[int]$Height)",
                "$ErrorActionPreference = 'Stop'",
                "$ppt = New-Object -ComObject PowerPoint.Application",
                "try {",
                "  $ppt.Visible = $true",
                "  $pres = $ppt.Presentations.Open($In, $true, $false, $false)",
                "  try {",
                "    $slide = $pres.Slides.Item(1)",
                '    $slide.Export($Out, "PNG", $Width, $Height)',
                "  } finally { $pres.Close() }",
                "} finally {",
                "  $ppt.Quit()",
                "  [System.Runtime.InteropServices.Marshal]::ReleaseComObject($ppt) | Out-Null",
                "}",
            ]
        ),
        encoding="utf-8",
    )
    try:
        subprocess.run(
            [
                powershell,
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(script),
                "-In",
                str(tmp),
                "-Out",
                str(out),
                "-Width",
                str(width),
                "-Height",
                str(height),
            ],
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=120,
        )
    except (subprocess.TimeoutExpired, OSError):
        return False
    return out.exists() and out.stat().st_size > 0


def render(
    path: str | Path,
    out: str | Path,
    *,
    dpi: int = 220,
    slide_no: int = 1,
    engine: str = "auto",
) -> dict:
    src = Path(path).resolve()
    dst = Path(out).resolve()
    dst.parent.mkdir(parents=True, exist_ok=True)
    prs = Presentation(str(src))
    width_in = prs.slide_width / pu.EMU
    height_in = prs.slide_height / pu.EMU
    px = max(800, min(6000, round(width_in * dpi)))
    py = max(450, min(6000, round(height_in * dpi)))

    with tempfile.TemporaryDirectory(prefix="pptdraw-") as td:
        td_path = Path(td)
        digest = hashlib.md5(src.read_bytes()).hexdigest()[:10]
        tmp = td_path / f"slide-{digest}.pptx"
        _single_slide_copy(src, tmp, slide_no)

        system = platform.system()
        used = None

        def try_engine(name: str) -> bool:
            nonlocal used
            if name == "quicklook":
                ok = _quicklook(tmp, dst, px)
            elif name == "libreoffice":
                exe = find_libreoffice()
                ok = bool(exe) and (
                    _libreoffice_pdf(exe, tmp, dst, 1, dpi)
                    or _libreoffice_png(exe, tmp, dst)
                )
            elif name == "powerpoint":
                ok = _powerpoint(tmp, dst, px, py)
            else:
                ok = False
            if ok:
                used = name
            return ok

        if engine == "auto":
            order = (
                ["quicklook", "libreoffice"]
                if system == "Darwin"
                else ["libreoffice", "powerpoint"]
                if system == "Windows"
                else ["libreoffice"]
            )
            for name in order:
                if try_engine(name):
                    break
        else:
            try_engine(engine)

        if used is None:
            raise RuntimeError(
                "No PPTX renderer available.\n"
                "  macOS  : install WPS (Quick Look) or LibreOffice; "
                "`brew install --cask libreoffice`\n"
                "  Windows: install LibreOffice, or PowerPoint + PowerShell\n"
                "  Linux  : install LibreOffice (`sudo apt install libreoffice`)\n"
                "`pptdraw inspect` / `pptdraw apply` still work without a renderer."
            )
    return {
        "path": str(dst),
        "engine": used,
        "dpi": dpi,
        "width_px": px,
        "height_px": py,
    }


def available_engines() -> dict[str, bool | str | None]:
    return {
        "quicklook": bool(shutil.which("qlmanage")) and platform.system() == "Darwin",
        "libreoffice": find_libreoffice(),
        "powerpoint": bool(_powershell()) and platform.system() == "Windows",
        "pymupdf": _has_pymupdf(),
    }
