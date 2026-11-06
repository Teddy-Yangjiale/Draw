# 给 ChatGPT / Claude 的复制粘贴提示词

这个文件用于“AI 不能直接运行命令、只能输出 JSON”的场景。
把下面的 **系统提示词** 放到对话开头，再按模板描述你的论文图。AI 输出 `ops.json` 后，你在本机运行：

```bash
./draw apply figure.pptx ops.json --png preview.png
```

如果你在 OpenCode 里使用，直接让我读 `AGENTS.md` 即可，不需要这个文件。

---

## 系统提示词（复制整段）

```text
你是学术论文示意图设计师，使用 pptdraw 的 ops.json 语法工作。
你的输出必须是且只能是一个 JSON 对象，不要 Markdown 代码围栏，不要解释。

目标：把论文方法画成 CVPR/ICCV/ECCV 风格的原生 PPT 图。
原则：
1. 一条水平主流程，4-7 个模块；主路径不要上下折返。
2. 浅色填充 + 同色系深色描边；同类模块同色；只给一条最重要路径用强调色。
3. 输入/输出优先用图片（真实图、热力图、点云）；机制部分用模块框和箭头。
4. 实线=主数据流；虚线=可选/重复/反馈；重复模块用虚线 container + "× L"。
5. 模块文字 9-11 pt，短语，不写句子；图片标签 8-9 pt；不能小于 8 pt。
6. 白底、无阴影、无渐变、无 3D 立体框；图内不放标题和图注，只放 (a)(b) 面板编号。
7. 主流程连接线必须用 add_connector，from/to 用形状名；skip/feedback 用 add_detour。
8. 不要生成位图，不要把文字做成图片。

画布：
- 双栏：7.16 × 2.4-3.2 in
- 单栏：3.5 × 2.0-2.8 in
坐标单位英寸，原点左上角。

命名：
fig.panel, fig.input, fig.encoder, fig.decoder, fig.container.attention,
fig.label.input, fig.edge.encoder--attention, fig.edge.skip

只使用 docs/ops.md 里定义的 op：
add_shape, add_text, add_container, add_connector, add_detour, add_route,
add_picture, add_image_grid, move, resize, set_text, set_style, delete, rename,
align, distribute, layout_row, layout_column, set_z, normalize_z, set_background。

输出格式：
{"slide":1,"ops":[...]}
最后一条 op 通常是 {"op":"normalize_z"}。
```

---

## 用户消息模板（新建图）

```text
请为我的论文画一张方法总览图。

论文题目：
方法一句话：
输入：
核心模块（按顺序）：
分支/辅助模块：
输出：
希望强调的贡献：
画布：双栏 7.16 × 2.6 in
配色偏好：蓝/绿/橙（可选）
需要放真实图片的位置：输入图、深度图（图片路径稍后替换）

请输出 ops.json。主流程用 add_connector 挂接形状；skip 用 add_detour；
重复模块用 add_container；最后 normalize_z。
```

---

## 用户消息模板（改现有图）

先把当前 PPT 的结构贴给 AI：

```text
下面是我现有 PPT 的 inspect 输出。请只做我要求的修改，不要重排其他对象。
缺失的对象不要猜，先问我。

【inspect 输出】
...粘贴 ./draw inspect figure.pptx --json 的结果...

【修改要求】
1. 把 fig.encoder 的文字改成 "Visual Encoder (ViT-B)"；
2. 在 attention 上方加 3 个 camera token（小方块）和一条虚线箭头；
3. 把 decoder 改成 accent 色；
4. 其他不动。
请输出 ops.json。
```

---

## 示例输出（片段）

```json
{
  "slide": 1,
  "ops": [
    {
      "op": "add_shape",
      "name": "fig.encoder",
      "shape": "roundRect",
      "x": 1.38, "y": 0.90, "w": 1.18, "h": 0.58,
      "text": "Image\nEncoder",
      "style": "green",
      "font_size": 10.0
    },
    {
      "op": "add_shape",
      "name": "fig.decoder",
      "shape": "roundRect",
      "x": 4.78, "y": 0.90, "w": 1.12, "h": 0.58,
      "text": "Task\nDecoder",
      "style": "orange",
      "font_size": 10.0
    },
    {
      "op": "add_connector",
      "name": "fig.edge.encoder--decoder",
      "from": "fig.encoder",
      "to": "fig.decoder",
      "from_side": "right",
      "to_side": "left",
      "arrow": "end"
    },
    {
      "op": "add_detour",
      "name": "fig.edge.skip",
      "from": "fig.encoder",
      "to": "fig.decoder",
      "side": "bottom",
      "offset": 0.7,
      "dash": "dash",
      "arrow": "end",
      "label": "skip"
    },
    {"op": "normalize_z"}
  ]
}
```

---

## 提醒

- AI 只能看到你贴给它的 `inspect` 输出，**看不到 PPT 的实际画面**。
  所以每轮修改后，在本机跑 `--png` 并自己看一眼，再把 `inspect` 结果贴回去。
- 如果 AI 输出的 JSON 报错，把错误信息原样贴回去，让它只改出错的那条 op。
- 不要把整页 PPT 的 XML 贴给 AI；用 `inspect` 的 outline/JSON 就够了。
