# AGENTS.md — 论文示意图绘制协议

本仓库是一个“AI + 人共同编辑原生 PPTX”的工具。
当用户要求“画论文图 / 方法总览图 / 架构图 / 流程图 / 定性对比图”时，按本协议工作。

## 先读

1. `research/figure_analysis.md`：16 篇 CVPR/AAAI/NeurIPS/ICLR/ICML/SIGGRAPH 论文的图法拆解。
2. `docs/figure_playbook.md`：六种图型的尺寸、配色、箭头、检查清单。
3. `docs/ops.md`：完整操作 API。
4. `README.md`：整体工作流与限制。

## 绝对原则

- **不要生成位图来代替示意图**；不要把文字转成图片。
- **不要直接改 OOXML/XML**；只通过 `./draw apply ...` 的 `ops.json` 修改。
- **PPTX 是唯一事实来源**。不要每次从零重建；先 `inspect` 当前文件。
- **保留人的修改**。不要删除/重命名不是自己创建的对象，除非用户明确要求。
- **主流程箭头用原生连接符**（`add_connector`，`from`/`to` 用形状名），不要用自由线条。
- **skip/feedback 用 `add_detour`**；不要用一条直线横穿模块。
- **输入/输出优先用图片**（真实图、热力图、点云、渲染图）；不要用文字框假装图片。
- **不要用阴影、渐变、3D 立体框、艺术字**。论文图要平。
- **图内不放标题和图注**；图注交给 LaTeX/Word。面板编号 `(a)` `(b)` 可以放。

## 工作流

### 0. 环境

```bash
./draw doctor
```

Windows 把 `./draw` 换成 `draw.cmd`，或直接用 `py -m pptdraw` / `pptdraw`。
没有预览引擎时不要慌：`inspect` / `apply` / `lint` 仍可用；只是不能看 PNG。macOS 用 WPS Quick Look，Windows 用 LibreOffice 或 PowerPoint COM，Linux 用 LibreOffice。

### 1. 查看现有文件

```bash
./draw inspect figure.pptx --png preview.png --dpi 220
```

- 先用文本 outline 了解对象名、位置、文字、连接关系。
- 用图片查看器看 `preview.png`（不是用文字猜）。
- 如果文件不存在：`./draw new figure.pptx --size 7.16x2.6`。

### 2. 规划

在写 JSON 前，先用一两句话确定**图型**：单主干 pipeline / 冻结-可训练双区 / 逐步机制 / 主图+放大 / 结果网格 / 3D 概念 / 轨迹映射。不同图型的尺寸和配色见 `docs/figure_playbook.md`。

- 画布：双栏 `7.16 × 2.4–3.2 in`，单栏 `3.5 × 2.0–2.8 in`。
- 主流程：从左到右 4–7 个模块；主路径一条水平轴。
- 分支：最多 2 条；用上下分支或右侧放大面板。
- 容器：哪些模块是“重复/整体”？用 `add_container`。
- 输入/输出：哪些位置放图片？先确认图片路径存在。
- 强调：只给一条最重要路径用 `orange`/`accent` 或红色文字。

### 3. 写 ops.json

写到 `.pptdraw/<name>.json`，不要散落在根目录。

标准顺序：

1. 背景/面板编号。
2. 输入图片。
3. 容器（先放内部模块，再 `add_container`）。
4. 模块。
5. 主流程连接线。
6. skip/feedback（`add_detour`）。
7. 标签。
8. `normalize_z`。

命名：

```
fig.panel
fig.input / fig.output.depth / fig.output.points
fig.encoder / fig.decoder / fig.fusion
fig.attn.frame / fig.attn.global
fig.container.attention
fig.label.input / fig.label.depth
fig.edge.input--encoder / fig.edge.encoder--attention
fig.edge.skip
```

### 4. 应用 + 预览 + 检查

```bash
./draw apply figure.pptx .pptdraw/<name>.json \
  --png out/<name>.png --dpi 220
./draw lint figure.pptx
```

- **必须看 PNG**。检查：
  - 箭头是否穿过模块/文字；
  - 文字是否溢出（`lint` 会给 warning）；
  - 模块是否等高、等距、同一条基线；
  - 输入/输出图片是否被拉伸；
  - 容器标签是否压住内部模块；
  - 整图是否留白均匀。
- `lint` 有 error 必须修；warning 视情况修（容器与子模块的重叠是正常的，已被排除）。
- 一次只改一类问题，避免大范围重排。

### 5. 结束

```bash
./draw inspect figure.pptx
./draw lint figure.pptx
```

最终交付：

- `.pptx`：可编辑源文件；
- `.png`：预览（不是投稿用）；
- 告诉用户：用 WPS/PowerPoint 打开继续改；投稿前“另存为 PDF”得到矢量图；
- 如果用户要 PDF 且本机有 LibreOffice：`./draw export-pdf figure.pptx -o figure.pdf`。

## 布局约束（硬规则）

- 画布边距 ≥ `0.12 in`；模块之间 ≥ `0.12 in`；主流程模块间距 `0.15–0.25 in`。
- 模块高度 `0.5–0.7 in`；同一行高度一致。
- 模块文字 9–11 pt；图片下方标签 8–9 pt；**不得小于 8 pt**。
- 线宽 0.75–1.25 pt；箭头 `end`；虚线只用于“可选/重复/反馈/未标注”。
- 一条主流程最多 7 个模块；超过就拆成 `(a)` 总览 + `(b)` 细节，或把细节放进右侧放大面板。
- 颜色最多 3 个主色 + 1 个强调色；同类模块必须同色。
- 同色系：`blue`、`green`、`orange`、`purple`、`yellow`、`gray`；强调用 `accent` 或 `loss`。
- 图片必须保持比例（`add_picture` 默认 contain）；不要手动拉伸。
- 面板标题条/容器标题放在左上角，字号 8.5–9 pt，颜色 `5B6773`。

## 与人协作

- 用户可能已经在 WPS 里改过：先 `inspect`，以当前文件为准。
- 如果用户删除/重命名了某个目标对象：**停止并询问**，不要用相似名字猜。
- 如果目标对象在 group 里：不要 `move`/`resize` 子对象；提示用户先在 PPT 里取消组合，或只改整个 group。
- 不要把用户新加的对象纳入 `normalize_z` 之外的重排；`normalize_z` 只调整层级，不改位置。
- 用户打开文件时，不要执行 `apply`；先让用户关闭。AI 写完后再让用户重新打开。
- 每次原地修改都有备份；如果改坏了，告诉用户可以 `./draw undo figure.pptx`。

## 常见错误

| 错误 | 后果 | 正确做法 |
|---|---|---|
| 用 `add_route` 画主流程 | 移动模块后箭头不跟随 | 用 `add_connector` 挂接形状 |
| 用直线横穿容器画 skip | 线穿过模块 | 用 `add_detour` |
| 文字框太小 | 打印时溢出 | 看 `lint` 的 `text_overflow`，加宽/加高/减字 |
| 模块大小不一 | 图看起来“手作感” | 同一行统一 `h`，用 `align`/`layout_row` |
| 颜色太多 | 读者不知道重点 | 同类同色，只留一个强调色 |
| 图内写标题/图注 | 与论文 caption 重复 | 删掉，只留面板编号 |
| 把公式/文字做成图片 | 不可编辑、放大糊 | 用原生文本 + Unicode，或公式作为透明图片单独处理 |
| 直接改 XML | 文件损坏风险 | 只走 ops API |

## 交付话术

完成后向用户说明：

1. 生成/修改了哪个 `.pptx` 和 `.png`；
2. 主要改了什么（1–3 条）；
3. 如何打开继续改（WPS/PowerPoint）；
4. 投稿前如何导出矢量 PDF；
5. 如果预览是 Quick Look/LibreOffice，提醒“最终以 WPS/PowerPoint 为准”。
