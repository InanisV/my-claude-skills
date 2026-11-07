# PRD 画板设计系统（唯一权威；`scripts/prd_diagram.py` 实现它）

> 为什么有这份：产品 2026-11-04「泳道图、流程图、状态图没有一套规范，每个需求的图都长得不一样，希望固定一套设计风格、提升设计品味。」实测同一仓库两篇 PRD 出了三套配色、mermaid 导入又是第四套。结论：**风格不靠规则文字约束模型，靠脚本写死**——AI 只写内容 spec，不写颜色 / 尺寸 / 坐标。
> 改样式 = 同时改本文件与脚本顶部 `STYLE`（两处数值一致）。画什么图、画几张、泳道怎么分道仍按 `07 §五` 第 10 条与 `07 §五之二` 选型表。

## 1 适用

PRD 里只用三种图，一页一图：

| 图型 | spec `type` | 什么时候画 |
|---|---|---|
| 相关方 / 系统泳道图 | `swimlane` | ≥2 个系统或团队之间流转；有人工介入再加相关方泳道（`07 §五之二`） |
| 流程图 | `flow` | 单系统、≥4 步或有分支的流程 |
| 状态图 | `state` | 对象 ≥3 个状态（状态表仍是唯一权威，图只做导览） |

架构图、对比图等其它图型 PRD 不用。

## 2 色板（三色纪律，低饱和）

| 角色 | 色值 | 用在 |
|---|---|---|
| 墨色 | `#1F2329` | 标题、正文、状态框描边 |
| 次级灰 | `#646A73` | 副标题、连线标签、脚注、泳道系统名 |
| 线灰 | `#7F8A9C` | 连线 |
| 边灰 | `#B8C2CC` | 普通方框描边、判定菱形描边 |
| 带灰 | `#E1E5EA` | 泳道带描边、条件标签框描边 |
| 带底 | `#F5F7FA` | 泳道带底 |
| 白 | `#FFFFFF` | 画布、方框底 |
| 品牌蓝（唯一强调色） | `#2B6AFF` | 泳道左侧 4px 色条、步骤编号、状态图起点圆点 |

- **所有泳道同一色条**，不按角色换色。
- 两种语义浅色，只在本图有该语义时出现，并自动进图例：

| 语义 | 底 | 描边 | spec 写法 |
|---|---|---|---|
| 人工介入 | `#FFF4E0` | `#D9A441` | 泳道 / 流程步骤 `"kind": "human"`；状态图迁移 `"by": "human"`（标签框上色） |
| 用户可见结果 | `#E8F3EC` | `#4C9A6A` | 泳道 / 流程步骤 `"kind": "visible"` |

- 禁止：其它任何颜色、渐变、阴影、图标、emoji。

## 3 字号

| 元素 | 规格 |
|---|---|
| 标题 | 20 bold 墨，≤24 字 |
| 副标题 | 13 次级灰，≤1 行、≤40 字，写这张图回答什么 |
| 泳道名 | 14 bold 墨，≤8 字；可选第二行系统名 12 次级灰，≤10 字 |
| 方框正文 | 13 墨，≤2 行（脚本自动折行） |
| 步骤编号 | 11 bold 蓝，写在方框正文前 |
| 状态框正文 | 15 bold 墨 |
| 连线标签 | 12 次级灰，≤12 字 |
| 图例 | 12 墨 |
| 脚注 | 12 次级灰，≤3 行、每行 ≤60 字 |

## 4 几何

| 项 | 值 |
|---|---|
| 画布 | 白底，四周内边距 40 |
| 标题区 | 高 72（图例放不下标题行时下移一行，标题区 +28） |
| 泳道带 | 高 112，带间距 12，圆角 8，左侧色条 4 × 带高 |
| 泳道名区 | 宽 140 |
| 步骤框 | 160 × 56，圆角 8，描边 1 |
| 步骤列 | 列宽 208（框 160 + 间距 48） |
| 状态框 | 168 × 48，圆角 8，描边 1.5 墨 |
| 判定菱形 | 120 × 72，白底边灰 |
| 起止框（流程） | 120 × 40 胶囊，描边 1.5 墨 |
| 终态框（状态） | 双描边：外框 1.5 + 内缩 4 的内框 1 |
| 条件标签框（状态） | 白底带灰描边，高 22，压在连线上 |
| 图例 | 标题行右侧；只列本图用到的种类；顺序固定：实线 / 虚线 / 人工介入 / 用户可见结果 |

**方框字数**：方框 ≤14 字（与 `07 §五` 第 10 条一致）；宽 160 的框 13 号字一行放 10 字，脚本按「首行 ≤9 字（给编号让位）、次行 ≤10 字」自动折成两行，优先在标点处或「并 / 和 / 与 / 及 / 或」这类连词前断（少切开双字词）；显式 `\n` 原样尊重。判定菱形每行 ≤7 字、≤2 行；状态名 ≤9 字。

## 5 连线

- 颜色线灰、粗 1.5、终点开口箭头，起点无箭头；**禁止双向箭头**（往返拆成两条）。
- **实线 = 请求 / 操作 / 状态变化；虚线 = 结论 / 事件 / 状态不变的处理**。
- 一律正交折线，禁止曲线；字数统计按「汉字 = 1、英文数字 ≈ 0.55」。
- 布线由脚本完成，三种图同一套规则：在「列间通道 × 行间 / 泳道内留白走廊」上为每条线选路——**不穿框、不出图区（不进标题 / 图例区）、不与别的线共线或首尾相接成一根线**，交叉和拐弯尽量少。
- **同一来源多条出线从不同边出、各走独立竖段**：正向边默认右出（横向推进），右边被占再上 / 下出；同一边出多条时错开出口。判定菱形只从四个顶点出线。
- 回边（指回更早的步骤）走留白走廊绕回，从目标框的上 / 下边进入；泳道图的回边走泳道内框上下的留白。
- 标签贴在本线某段的中点旁（横段在上 / 下，竖段在右 / 左），不压框、不压别的标签、不压线；实在避不开才加白底压在线上。状态图的条件标签框同样贴线摆放。

## 6 布局

- **泳道图**：泳道按出场顺序自上而下；步骤按编号自左向右**一步一列**（同一泳道连续两步也各占一列）；起点在第一列。分支写 `5a` / `5b`——同列、必须落在不同泳道。
- **流程图**：自左向右；每个节点的第一条出边沿同一行，其余分支往下一行（该行该列已占就再往下）；判定用菱形，出边标「是 / 否」。
- **状态图**：自左向右；起点 = 实心蓝圆点 12；终态双描边；人工动作写成贴在边上的条件标签框并用人工介入底色；自环（状态不变的处理）画在框的右上角。

## 7 密度上限（沿用 `07 §五` 第 10 条；`lint` 判）

| 图型 | 上限 |
|---|---|
| 泳道图 | 泳道 ≤5 条、每道 ≤7 框、全图 ≤16 框 |
| 流程 / 状态图 | ≤12 节点、≤20 条边 |

超了拆图，每张图一个标题。泳道只画流程里有动作的参与方（`07 §五` 第 10 条）——没有步骤的泳道 `lint` 报错。

## 8 spec 范例（可直接跑；与 `references/examples/diagrams/` 下同名文件逐字一致）

spec 只写内容。出现 `fill` / `color` / `x` / `y` / `width` / `height` 等样式或坐标字段 → `lint` 报错。

**泳道**（`swimlane.json`）：

```json
{
  "type": "swimlane",
  "title": "内容提交与审核 · 相关方泳道",
  "subtitle": "一条内容从提交到用户看到审核结果，经过谁、在哪一步有人工介入",
  "lanes": [
    {"id": "user", "name": "用户", "sub": "作者"},
    {"id": "fe", "name": "前端", "sub": "H5 / App"},
    {"id": "be", "name": "后端", "sub": "业务服务"},
    {"id": "partner", "name": "合作方", "sub": "审核服务"}
  ],
  "steps": [
    {"n": 1, "lane": "user", "text": "提交内容"},
    {"n": 2, "lane": "fe", "text": "校验并上传"},
    {"n": 3, "lane": "be", "text": "生成待审记录"},
    {"n": 4, "lane": "partner", "text": "机审打分"},
    {"n": 5, "lane": "partner", "text": "人工复核", "kind": "human"},
    {"n": 6, "lane": "be", "text": "写入审核结论"},
    {"n": 7, "lane": "fe", "text": "展示审核结果", "kind": "visible"}
  ],
  "edges": [
    {"from": 1, "to": 2, "style": "solid"},
    {"from": 2, "to": 3, "label": "提交请求", "style": "solid"},
    {"from": 3, "to": 4, "label": "送审", "style": "solid"},
    {"from": 4, "to": 5, "label": "疑似违规", "style": "dashed"},
    {"from": 5, "to": 6, "label": "复核结论", "style": "dashed"},
    {"from": 6, "to": 7, "label": "推送结果", "style": "dashed"}
  ],
  "notes": ["机审直接通过的内容跳过第 5 步，由后端直接写入结论。"]
}
```

字段：`lanes[].sub` 可选（系统名）；`steps[].n` 为数字或 `5a` 式；`steps[].kind` = `normal`（默认）/ `human` / `visible`；`edges[].style` = `solid`（默认）/ `dashed`；`label` 可选。

**流程**（`flow.json`）：

```json
{
  "type": "flow",
  "title": "列表页加载流程",
  "subtitle": "用户进入列表页后，登录与数据两道判定决定看到什么",
  "nodes": [
    {"id": "start", "text": "进入列表页", "shape": "start"},
    {"id": "login", "text": "已登录？", "shape": "decision"},
    {"id": "guide", "text": "引导登录", "shape": "box"},
    {"id": "load", "text": "加载列表数据", "shape": "box"},
    {"id": "has", "text": "有数据？", "shape": "decision"},
    {"id": "show", "text": "展示列表", "shape": "box", "kind": "visible"},
    {"id": "empty", "text": "展示空状态", "shape": "box", "kind": "visible"},
    {"id": "end", "text": "结束", "shape": "end"}
  ],
  "edges": [
    {"from": "start", "to": "login", "style": "solid"},
    {"from": "login", "to": "load", "label": "是", "style": "solid"},
    {"from": "login", "to": "guide", "label": "否", "style": "solid"},
    {"from": "guide", "to": "login", "label": "登录成功", "style": "dashed"},
    {"from": "load", "to": "has", "style": "solid"},
    {"from": "has", "to": "show", "label": "是", "style": "solid"},
    {"from": "has", "to": "empty", "label": "否", "style": "solid"},
    {"from": "show", "to": "end", "style": "solid"},
    {"from": "empty", "to": "end", "style": "solid"}
  ],
  "notes": []
}
```

字段：`shape` = `box`（默认）/ `decision` / `start` / `end`；`box` 可带 `kind`。出边的书写顺序决定布局：第一条沿同一行。

**状态**（`state.json`）：

```json
{
  "type": "state",
  "title": "申请单状态流转",
  "subtitle": "一张申请单有哪些状态、谁在什么条件下推动它变化",
  "states": [
    {"id": "pending", "text": "待处理", "final": false},
    {"id": "approved", "text": "已通过", "final": true},
    {"id": "rejected", "text": "未通过", "final": false},
    {"id": "withdrawn", "text": "已撤回", "final": true}
  ],
  "initial": "pending",
  "transitions": [
    {"from": "pending", "to": "approved", "label": "系统校验通过", "by": "system", "style": "solid"},
    {"from": "pending", "to": "rejected", "label": "运营人工驳回", "by": "human", "style": "solid"},
    {"from": "rejected", "to": "pending", "label": "用户重新提交", "by": "system", "style": "solid"},
    {"from": "pending", "to": "pending", "label": "补充材料", "by": "system", "style": "dashed"},
    {"from": "pending", "to": "withdrawn", "label": "用户撤回", "by": "system", "style": "solid"}
  ],
  "notes": ["已通过 / 已撤回为终态，不再接受任何操作。"]
}
```

字段：`by` = `system`（默认）/ `human`；`from == to` 即自环（状态不变的处理，配 `dashed`）。

## 9 工作流

1. AI 把图的内容写成 spec：工作目录 `diagrams/<图名>.json`（图名用英文 / 拼音，发布时拼进幂等 token）。
2. `python3 <KIT_ROOT>/scripts/prd_diagram.py lint diagrams/<图名>.json` —— 退出码 2 就按提示改 spec（缩字、拆图），不许绕过。
3. `python3 <KIT_ROOT>/scripts/prd_diagram.py render diagrams/<图名>.json --png diagrams/<图名>.png`，**Read 图片目检**：标题 / 图例 / 编号 / 实虚线 / 语义色在、文字无截断、连线不穿框。
4. 文档里该位置放一个空画板块（XML `<whiteboard type="blank"></whiteboard>`；建文档时随正文写入，或 `docs +update` 插入），从返回的 `new_blocks[].block_token` 或 `docs +fetch` 回读的 `<whiteboard token="…"/>` 拿 token（`06`）。
5. `python3 <KIT_ROOT>/scripts/prd_diagram.py publish diagrams/<图名>.json --whiteboard-token <token>` → 打印 `PUBLISHED <token>` 即成功；否则打印 lark-cli 错误首行，按 `06` 错误分诊。
6. `python3 <KIT_ROOT>/scripts/prd_diagram.py verify --whiteboard-token <token> --out diagrams/ [--name <图名>]`（`--name` 只允许 `[A-Za-z0-9_-]{1,40}`） → Read 导出的 `.jpg` 再看一眼，与本地 PNG 一致才算完（云端预览有几秒延迟：导出的还是旧图就隔几秒再跑一次 `verify`）。

- 🔴 **AI 不许手写 DSL / raw 节点 / 颜色**，也不许为了「好看」改 spec 之外的东西；样式问题改脚本（维护者）。
- **mermaid fence 只在本机没有 node 时兜底**（`render` / `publish` 会打印「本机没有 node/npm…」）：样式会是飞书默认，发布简报里写一句「本机无 node，画板为 mermaid 兜底样式，装 node 后可用 prd_diagram.py 重发」。无 lark-cli 的纯文本降级仍按 `07 §六` 第 3 条写 mermaid fence。
- spec 文件留在工作目录（不进 PRD 正文）；图改了只改 spec 重跑 5–6 步（`publish` 是整板覆盖）。
- `publish` 是写操作，lark-cli 若弹确认按提示确认；AI 在确认前把图名与目标文档说给产品听一遍。
