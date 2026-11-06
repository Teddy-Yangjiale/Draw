"""Regenerate the visual comparison sheet used in the README/analysis."""

from __future__ import annotations

import re
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from pptdraw.fonts import font_path  # noqa: E402

FONT = font_path()
TOKEN = re.compile(
    r"[\u1100-\u11ff\u2e80-\u9fff\uac00-\ud7af\uf900-\ufaff\uff00-\uffef]"
)


def tokens(text: str) -> list[str]:
    out, buf = [], ""
    for ch in text:
        if ch == " " or TOKEN.match(ch):
            if buf:
                out.append(buf)
                buf = ""
            out.append(ch)
        else:
            buf += ch
    if buf:
        out.append(buf)
    return out


def wrap(draw, text, font, max_width):
    lines, current = [], ""
    for token in tokens(text):
        if token == " ":
            if current and not current.endswith(" "):
                current += " "
            continue
        candidate = current + token
        if draw.textlength(candidate, font=font) <= max_width or not current:
            if not current and draw.textlength(token, font=font) > max_width:
                for ch in token:
                    if draw.textlength(current + ch, font=font) <= max_width or not current:
                        current += ch
                    else:
                        lines.append(current)
                        current = ch
            else:
                current = candidate
        else:
            lines.append(current.rstrip())
            current = token
    if current.strip():
        lines.append(current.rstrip())
    return lines or [""]


def main() -> None:
    items = [
        (
            "SAM (ICCV 2023)  ·  Figure 4",
            "research/crops/sam.png",
            [
                "图像 → 绿色 encoder → token 堆叠 → 橙色 mask decoder → 多 mask 输出",
                "模块 = 浅色圆角矩形 + 同色系描边，无阴影",
                "箭头 1 pt 细线，端口严格对齐；多输出分支",
                "真图片承担输入/输出，示意图只画“机制”",
            ],
        ),
        (
            "Depth Anything (CVPR 2024)  ·  Figure 2",
            "research/crops/depth_anything.png",
            [
                "实线 = labeled 数据流；虚线 = unlabeled / 可选路径",
                "中性棕灰模块 + 珊瑚红重点色，层级非常清楚",
                "左右两端放图片与热力图，中间只留 2-3 个模块",
                "用颜色和线型同时编码“分支语义”",
            ],
        ),
        (
            "VGGT (CVPR 2025)  ·  Figure 2",
            "research/crops/vggt.png",
            [
                "彩色 token 堆叠 = 特征/序列，不用文字解释张量形状",
                "虚线圆角框 + ×L = 重复模块（PPT 里就是虚线框+文本框）",
                "主流程保持一条水平轴，分支只在局部上下展开",
                "输出用真实渲染图（camera/depth/point/track）",
            ],
        ),
        (
            "Grounding DINO (ECCV 2024)  ·  Figure 3",
            "research/crops/grounding_dino.png",
            [
                "主图 + 右侧 2 个“放大面板”，适合信息量大的方法",
                "紫色标题条给面板编号；面板内用同色系模块",
                "主图可以密，但放大面板必须更清楚",
                "斜线纹理/3D 小方块表示特征图，仍是可编辑形状+纹理",
            ],
        ),
        (
            "NeRF (CVPR 2020)  ·  Figure 2",
            "research/crops/nerf.png",
            [
                "3D 场景、相机视锥、光线、MLP、曲线、loss 组合",
                "这类图不是 PPT 原生图形，通常由 3D/绘图工具生成后嵌入",
                "PPT 适合做外层排版、编号、箭头和文字标注",
                "不要把 3D 渲染硬拆成一堆 PPT 形状",
            ],
        ),
    ]

    W, pad, img_w = 1900, 34, 1050
    text_w = W - img_w - 3 * pad
    head_f = ImageFont.truetype(FONT, 27)
    body_f = ImageFont.truetype(FONT, 24)
    title_f = ImageFont.truetype(FONT, 34)

    rows = []
    for head, path, bullets in items:
        im = Image.open(path).convert("RGB")
        scale = img_w / im.width
        im = im.resize((img_w, round(im.height * scale)), Image.LANCZOS)
        rows.append((head, im, bullets))

    H = pad
    for _, im, bullets in rows:
        H += 52 + max(im.height, len(bullets) * 44) + 30
    H += 260
    sheet = Image.new("RGB", (W, H), "white")
    d = ImageDraw.Draw(sheet)

    y = pad
    for head, im, bullets in rows:
        d.text((pad, y), head, font=head_f, fill=(24, 30, 38))
        y += 52
        sheet.paste(im, (pad, y))
        tx, ty = pad + img_w + pad, y + 4
        for bullet in bullets:
            d.ellipse((tx, ty + 10, tx + 9, ty + 19), fill=(91, 141, 184))
            lines = wrap(d, bullet, body_f, text_w - 30)
            for line in lines:
                d.text((tx + 20, ty), line, font=body_f, fill=(45, 52, 60))
                ty += 38
            ty += 6
        y += max(im.height, len(bullets) * 44) + 20
        d.line((pad, y, W - pad, y), fill=(222, 227, 232), width=2)
        y += 18

    box_top = y
    d.rounded_rectangle(
        (pad, box_top, W - pad, H - 30),
        radius=18,
        fill=(246, 249, 252),
        outline=(205, 218, 230),
        width=2,
    )
    d.text((pad + 28, box_top + 22), "共同规律（可直接写进绘图约束）", font=title_f, fill=(30, 60, 90))
    summary = [
        "01  一条水平主流程，5±2 个模块；主路径不要上下折返。",
        "02  浅色填充 + 同色系深色描边；同色=同一类，强调色只给最重要的分支。",
        "03  输入/输出优先用真实图片、热力图、点云；机制部分才用框和箭头。",
        "04  实线=主数据流；虚线=可选/重复/反馈；虚线框 + ×L=重复模块。",
        "05  箭头 1 pt 左右，端口对齐；文字 8-11 pt，短语，不写句子。",
        "06  白色背景，无阴影、无渐变、无 3D 立体框；图内不放标题和图注。",
    ]
    sy = box_top + 78
    for line in summary:
        d.text((pad + 32, sy), line, font=body_f, fill=(48, 58, 68))
        sy += 38
    sheet.save("research/figure_analysis_sheet.png")
    print(sheet.size)


if __name__ == "__main__":
    main()
