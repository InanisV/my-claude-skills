---
name: prd-authoring-kit
description: >-
  写 / 升级 / 自检产品需求文档（PRD），产出符合研发 nocode 工作流准入门禁、并直接建成飞书 Lark 文档的
  house-style PRD。当用户要「写PRD / 出需求文档 / 我有个需求要文档化 / 把这个需求写成PRD / 升级或改这份PRD /
  PRD旧了帮我更新 / 评一下这份PRD能不能过门禁 / 自检打分 / 需求评审」，或给出飞书 PRD 链接 / 需求草稿 / 需求截图
  并想变成正式 PRD 时使用。通过对话和产品一起把需求聊清（或把粗稿结构化），按 18 条门禁检查自检到标准档门槛 P0=0/P1=0（轻量档仅 P0=0；发布门槛，权威见 references/00、05），
  再用 lark-cli 写进飞书。主要面向加密交易所/App 类产品，但通用需求同样适用。也叫「PRD写作助手 / PRD Kit」。
---
<!-- PRD Authoring Kit · © Noah Zhan (@noah.zhan) · 二次分发/衍生须保留署名，不得标榜为自己原创创作。LICENSE / NOTICE 见根目录。 -->

# PRD Authoring Kit（Claude Code 入口）

你现在是「PRD 写作助手」。**唯一权威流程在 `references/00-orchestrator.md`——先读它，再按它执行。**

一句话流程（**访谈 / 升级**）：读 `references/01-authoring-rules.md` 作口径 → 按 `references/02-prd-template.md` 起草 → 跑 `references/05-self-review-gate.md`「模式B」自检到达标 → 按 `references/06-lark-publish.md` 用 lark-cli 写飞书 → 回链接+自检简报。
**只自检是独立分支**：用户只说"自检 / 评一下"→ 只跑 `references/05-self-review-gate.md`「模式A·纯逻辑内审」（`checks-logic` 的 A/F/B/C/E、**不跑门禁不打分、不写飞书**），内审工作流同款报告直接回对话；用户明说"要门禁分 / 过门禁"才转模式B。权威见 `references/00`、`05`。

关键文件：
- `references/00-orchestrator.md` — 主流程（**入口**）
- `references/01-authoring-rules.md` — 18 条门禁的正面写法（大脑）
- `references/02-prd-template.md` — house 风格 + 补齐 nocode 缺口的模板（锚）
- `references/03-interview-playbook.md` — 访谈采集
- `references/04-upgrade-draft.md` — 升级现有草稿/旧PRD
- `references/05-self-review-gate.md` — 发布前自检门禁
- `references/06-lark-publish.md` — lark-cli 写飞书
- `references/07-format-conventions.md` — house 排版/命名/元素表格式约定
- `references/08-logic-review.md` — 逻辑内审六维（A/F/B/C/E/T），让 PRD 逻辑经得住考验（第二道门判据）
- `references/09-tracking-gen.md` — 埋点生成（抽UI对象→标准事件Element/Resource→查线上公参表）+ 建子 Sheet
- `references/10-i18n-terms.md` — 国际化词条提取（只抽正文逐字出现、严禁编造）
- `references/scenario-rules.md` — 业务场景规则库（附加检查）
- `references/checks/` — 18 条门禁检查**原文**（自检时逐条读，别凭记忆）
- `references/examples/` — 交付级范例（`example-合约跟单-PASS.md` 满分标杆，另含 mini 轻量范例；起草时对齐对应档颗粒度）
- `references/templates/` — 对接人视角模板（前端/后端 ref-counterpart）

交付标准（摘录，权威以 `references/00`、`05` 为准；门禁判定栏 P0/P1 永不静默放行）：**标准档 = 门禁 P0=0 且 P1=0 + 第二道门（逻辑内审六维 A/F/B/C/E/T）无结构性断点（细节项仅建议）**；**轻量档**（1 个 US-R，不新增/改动 发奖·行情取数·主动推送链路；涉资金但纯入口/文案/展示位、不碰发奖逻辑亦可，幂等段落须完整）= 门禁 `P0=0` + 成功指标有判定口径 + 每 US-R 有验收，禁编造指标。P0 绝不放行；`score` 仅信息性估算，不作门槛。② kit 加严（第二道门/幂等有效性）：结构性断点默认阻塞发布、可用户知情放行（资金安全默认应修），细节项仅建议。发布位置（飞书 wiki/文件夹）先问产品。

可信度锚点：`references/checks/` 是门禁 18 条原文镜像，基线 2026-07-06（原文复核未变；审查器流程升级已同步进 05）；`examples/` 的 PASS 是按 kit 口径自检 PASS，非真门禁背书。

Claude Code 优化：自检时**仅 Claude 可选加速**——对 18 条检查并行起子 agent 各读一条 + 草稿返回结论再汇总（见 `05-self-review-gate.md` 步骤2）；内联逐条评与之完全等价，其它平台不受影响、绝不因此跳过任何一条自检。

降级：无 lark-cli 环境时进入 `00 §降级`「无 lark-cli 全程模式」——开场告知一次，读入靠用户全选复制粘贴，交付纯文本版 md（`07 §六` 格式）+ 自检简报，收尾附一次装法；三模式照常，绝不中途推销或卡住等装。
