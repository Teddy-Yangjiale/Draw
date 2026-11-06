# `ops.json` 操作参考

`pptdraw apply deck.pptx ops.json` 读取一个 JSON 文档，把语义操作应用到**现有 PPTX**。
它不是“重新生成整页”，而是像补丁一样只修改指定对象。

```json
{
  "slide": 1,
  "ops": [
    { "op": "add_shape", "name": "fig.encoder", "shape": "roundRect",
      "x": 1.4, "y": 0.9, "w": 1.2, "h": 0.6,
      "text": "Image\nEncoder", "style": "green", "font_size": 10 }
  ]
}
```

## 基本约定

- 单位：**英寸**；坐标原点在左上角。
- 颜色：`RRGGBB`，不带 `#`；`"none"` 表示无填充/无描边。
- 名称：`name` 必须唯一，建议用 `fig.` 前缀：
  - 模块：`fig.encoder`、`fig.decoder`
  - 容器：`fig.container.attention`（或任意名字 + `pptdraw:container` alt）
  - 连接线：`fig.edge.encoder--attention`
  - 标签：`fig.label.input`、`fig.edge.encoder--attention.label`
  - 路线锚点：`fig.edge.skip.anchor`
- `z` 层级：容器在底，连接线中间，模块在上，标签最上；可用 `normalize_z` 统一整理。
- 所有文字都是原生文本；不要把文字做成图片。

## 风格预设

`style` 可填：

```
plain, neutral, blue/primary, green/success, orange/accent,
purple, yellow/warning, gray/muted, dark, note, container, text, loss
```

| 名称 | 用途 |
|---|---|
| `blue` / `primary` | 编码器、特征、主模块 |
| `green` / `success` | 另一类模块（如 image encoder） |
| `orange` / `accent` | 解码器、重点模块 |
| `purple` | 提示/辅助分支 |
| `yellow` / `warning` | 监督、损失、注意 |
| `gray` / `muted` | 中性模块 |
| `note` | 虚线便签 |
| `container` | 虚线分组框 |
| `text` | 无填充无描边的纯文字 |
| `loss` | 红色文字（用于 loss） |

可覆盖：`fill`, `line`, `text_color`, `line_width`, `dash`, `font_size`, `bold`。

---

## 形状与文本

### `add_shape`

```json
{
  "op": "add_shape",
  "name": "fig.encoder",
  "shape": "roundRect",
  "x": 1.4, "y": 0.9, "w": 1.2, "h": 0.6,
  "text": "Image\nEncoder",
  "style": "green",
  "font_size": 10,
  "align": "center",
  "anchor": "middle",
  "radius": 0.08,
  "z": "back"
}
```

- `shape`：`rect`, `roundRect`, `ellipse`, `diamond`, `trapezoid`, `chevron`, `hexagon`, `pentagon`, `parallelogram`, `cylinder`/`can`, `cloud`, `star`。
- `w` / `h` 可省略，会按文字自动估算（建议仍显式给出，布局更稳）。
- `radius` 只对 `roundRect` 生效，单位英寸。
- `z: "back"` 会立即置于底层（容器常用）。

### `add_text`

用于面板编号、模块下方注释、`× L` 等。

```json
{
  "op": "add_text",
  "name": "fig.label.input",
  "text": "Input views",
  "x": 0.14, "y": 1.50, "w": 1.06, "h": 0.18,
  "font_size": 8.5,
  "text_color": "5B6773",
  "align": "center",
  "anchor": "top"
}
```

- `align`: `left` / `center` / `right`
- `anchor`: `top` / `middle` / `bottom`
- `bold`, `italic` 可选。

### `add_container`

虚线分组框，常用在“重复模块”“整体框架”“放大面板”。

```json
{
  "op": "add_container",
  "name": "fig.attention",
  "around": ["fig.attn.frame", "fig.attn.global"],
  "label": "Attention Block   × L",
  "padding": 0.12,
  "top_pad": 0.26,
  "style": "container"
}
```

- `around`：自动包住这些形状；也可改为显式 `x/y/w/h`。
- `top_pad`：给标签留出的顶部空间。
- 容器会自动置底；内部模块需要在容器之后创建，或最后 `normalize_z`。
- 容器标签是左上角文本，不是标题栏。

---

## 连接线

### `add_connector`（推荐，主流程用）

```json
{
  "op": "add_connector",
  "name": "fig.edge.encoder--attention",
  "from": "fig.encoder",
  "to": "fig.attention",
  "from_side": "right",
  "to_side": "left",
  "route": "straight",
  "arrow": "end",
  "line_width": 1.0,
  "color": "4B5763",
  "dash": "solid",
  "label": "fuse",
  "label_font_size": 8.5,
  "label_offset": 0.12
}
```

- `from` / `to` 可以是形状名，也可以是 `[x, y]` 坐标。
- 用形状名时，连接线会**挂接**在形状的端口上；人拖动形状后箭头会跟着走。
- `from_side` / `to_side`：`top` / `left` / `bottom` / `right`；省略时按相对位置自动选。
- `route`: `straight` 或 `elbow`。
- `arrow`: `end` / `start` / `both` / `none`。
- `label` 会生成一个独立文本标签（带白色底，压住线），不会把文字塞进连接线。

### `add_detour`（skip / feedback，推荐）

U 形绕线，用于“跳过连接”“反馈回路”。它用一根几乎不可见的锚线 + 两段挂接连接符实现，所以移动模块后仍能保持连接。

```json
{
  "op": "add_detour",
  "name": "fig.edge.skip",
  "from": "fig.encoder",
  "to": "fig.decoder",
  "side": "bottom",
  "offset": 0.75,
  "dash": "dash",
  "arrow": "end",
  "label": "skip connection"
}
```

- `side`: `bottom` / `top` / `left` / `right`
- `offset`: 距离模块边界的距离。
- 左右绕线要求两个模块的垂直中心不同；上下绕线要求水平中心不同，否则会报错（避免画出横穿模块的线）。
- 会生成：`<name>.anchor`（细线锚点）、`<name>.seg1`、`<name>.seg2`、`<name>.label`。
- 删除主模块时，`delete` 会自动级联删除整组。

### `add_route`（自由折线）

```json
{
  "op": "add_route",
  "name": "fig.edge.feedback",
  "points": [[1.0, 1.2], [1.0, 2.2], [5.0, 2.2], [5.0, 1.2]],
  "dash": "dash",
  "arrow": "end",
  "label": "feedback"
}
```

- 由多段直线组成，**不挂接**形状；适合复杂绕线/一次性说明。
- 如果之后要经常移动两端模块，优先用 `add_detour`。

---

## 图片

### `add_picture`

```json
{
  "op": "add_picture",
  "name": "fig.input",
  "path": "../assets/input.png",
  "x": 0.2, "y": 0.85, "w": 0.95, "h": 0.62
}
```

- `path` 相对 `ops.json` 所在目录解析，也可以绝对路径。
- 图片按 `contain` 方式放进 `w × h` 盒子，保持比例。
- 可加 `line` / `line_width` 给图片描边（论文图通常不需要）。

### `add_image_grid`

定性对比图/多面板图。

```json
{
  "op": "add_image_grid",
  "images": ["../assets/a.png", "../assets/b.png", "../assets/c.png", "../assets/d.png"],
  "labels": ["Input", "Baseline", "Ours", "GT"],
  "cols": 2,
  "x": 0.22, "y": 0.42,
  "cell_w": 1.45, "cell_h": 0.86,
  "gap": 0.14,
  "label_h": 0.18,
  "label_size": 8,
  "prefix": "fig.image.demo"
}
```

- 自动生成 `fig.image.demo.1...` 和 `fig.label.image.demo.1...`。
- `label_h` 为标签预留高度；不需要标签就不传 `labels`。

---

## 修改已有对象

### `move`

```json
{"op":"move","name":"fig.decoder","x":4.7,"y":1.1}
{"op":"move","name":"fig.decoder","dx":-0.1,"dy":0.05}
```

### `resize`

```json
{"op":"resize","name":"fig.encoder","w":1.3,"h":0.62}
```

### `set_text`

保留现有字体大小/颜色/对齐，除非显式覆盖。

```json
{"op":"set_text","name":"fig.encoder","text":"Visual Encoder\n(ViT-B)"}
```

### `set_style`

只改你给出的属性，不会重置其他属性。

```json
{"op":"set_style","name":"fig.decoder","style":"accent"}
{"op":"set_style","name":"fig.decoder","fill":"FBE7D8","line":"C98A62"}
{"op":"set_style","name":"fig.encoder","text_color":"C05243","font_size":9.5}
```

### `delete`

```json
{"op":"delete","name":"fig.encoder"}
```

会级联删除挂在它上面的连接线、边标签，以及 detour 整组。不会删除容器里的子模块（除非你删的是子模块本身）。

### `rename`

```json
{"op":"rename","name":"fig.attention","new_name":"fig.container.attention"}
```

### 对齐/分布/排列

```json
{"op":"align","names":["fig.a","fig.b","fig.c"],"mode":"middle","target":"canvas"}
{"op":"distribute","names":["fig.a","fig.b","fig.c"],"axis":"h","mode":"gap"}
{"op":"layout_row","names":["fig.a","fig.b","fig.c"],"gap":0.16,"y":1.2,"center":3.58}
{"op":"layout_column","names":["fig.a","fig.b","fig.c"],"gap":0.12,"x":1.8,"center":1.3}
```

- `align.mode`: `left` / `center` / `right` / `top` / `middle` / `bottom`
- `align.target`: `canvas`（默认）或某个形状名
- `distribute.mode`: `gap`（等间距）或 `center`（等中心距）
- `layout_row.center`：整行的 **x 中心**；`y`：每个盒子的 **y 中心**
- `layout_column.center`：整列的 **y 中心**；`x`：每个盒子的 **x 中心**

### 层级

```json
{"op":"set_z","name":"fig.attention","position":"back"}
{"op":"normalize_z"}
```

`position`: `back` / `front` / `forward` / `backward`。
`normalize_z` 会按“容器 → 连线 → 模块 → 标签”重新排序，建议每次批量创建后调用一次。

### 其他

```json
{"op":"set_background","color":"FFFFFF"}
```

### `fit_canvas`（裁掉多余白边）

```json
{"op":"fit_canvas","margin":0.1}
{"op":"fit_canvas","margin":0.1,"keep_width":true}
```

- 计算所有顶层形状（含连接线、标签、锚点）的包围盒，按内容重设画布。
- `keep_width: true` 只收高度，保持双栏图的 7.16 in 宽度。
- `keep_height: true` 只收宽度。
- PowerPoint 的最小画布是 1 in；内容更小时会自动居中并保留 1 in。

---

## 常见配方

### 1. 标准横向 pipeline

1. `add_picture` 输入图。
2. `add_shape` 4–6 个模块，y 对齐，x 等距。
3. `add_container` 包住重复模块。
4. `add_connector` 逐段连接（`from_side` / `to_side` 显式给）。
5. `add_text` 模块下方注释。
6. `normalize_z`。

### 2. skip / feedback

用 `add_detour`，不要用一条直连接线横穿模块。

### 3. 放大面板

1. 主图放左侧。
2. 右侧 `add_container` 画两个面板，标题用 `add_text` 放在面板左上角。
3. 面板内重复“模块 + 箭头”的小流水线。
4. 用 `add_detour` 或斜线表示“放大自哪个模块”。

### 4. 定性对比网格

用 `add_image_grid`，不要逐张手算坐标；标签用 `labels` 自动生成。

---

## 错误与回滚

- 操作名不存在、字段拼错、颜色非法、形状重名，都会在 `apply` 时报错并指出第几个 op。
- 每次原地 `apply` 前会备份到 `.pptdraw/history/`；`pptdraw undo deck.pptx` 恢复最近一份。
- 如果文件在 AI 上次修改后被人工改过，`apply` 仍然基于**当前文件**修改；不会覆盖未触及的对象。但请避免 AI 和人在同一时间写同一个文件。
