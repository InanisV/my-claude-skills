<!-- PRD Authoring Kit · © Noah Zhan (@noah.zhan) · 二次分发/衍生须保留署名，不得标榜为自己原创创作。LICENSE / NOTICE 见根目录。 -->
# AGENTS.md —— PRD Authoring Kit (Codex 入口)

> **2026-08 起 Codex 有更优接法**：官方 skills 位（`~/.agents/skills/prd-authoring-kit`，`install.sh codex` 已自动装）——自动触发、全局生效、无需本文件与 AGENTS.md 加载句；本文件保留为旧接法兼容与 Cursor 等无 skills 机制平台的入口。
>
> 安装：把本文件内容并入你的 Codex `AGENTS.md`（仓库根目录，或 `~/.codex/AGENTS.md`）。
> 本文件是**薄指针**——不在这里复述规则，真正的口径都在 kit 里。它是**常驻指令**，命中意图即生效。

## 何时触发

当用户要**写 PRD / 出需求文档 / 把需求文档化 / 升级或改现有 PRD / 评审或自检 PRD / 判断能否过研发 nocode 门禁 / 登记需求 / 填写需求登记 / 登记校对 / 填文案登记表 / 登记实验 / 建个 Epic**，或给出飞书 PRD 链接、需求草稿、需求截图并想变成正式 PRD 时——命中即进入下面的流程，**不要凭本文件的摘要即兴写 PRD**。

## 第 0 步（不可跳过）：定位 KIT_ROOT 并读主流程

**这是祈使句，不是脚注。未完成本步、未回显模式表，不得输出任何 PRD 内容。**

1. 用你平台的文件查找能力定位 `00-orchestrator.md`（有 glob/file-search 工具用之；没有就用 shell：`find . ~/.prd-authoring-kit ~/.agents/skills ~/.codex ~/.claude/skills -name 00-orchestrator.md 2>/dev/null` 或 `rg --files -g '**/00-orchestrator.md'`）：
   - **命中一份** → 它所在目录即 `references/`，其上一级即 **KIT_ROOT**。
   - **多份命中 → 🔴 按「安装位优先级」选，不比 mtime**（mtime 反映"最近被碰过"，不是版本新旧——实测：一个刚建的发布快照/刚解压的 zip 放在 `~/Downloads` 就把正式安装位挤掉，AI 用了老版本还以为是最新）：**① 平台官方 skills 位**（Codex `~/.agents/skills/prd-authoring-kit`、Claude `~/.claude/skills/prd-authoring-kit`）→ **② `~/.prd-authoring-kit`** → **③ 当前项目内 `./prd-authoring-kit`**（Kiro 场景）→ **④ 其它任何位置**（下载目录/开发仓库/发布快照）**只在 ①②③ 全无时才用，且必须回显一行警告**"用的是非安装位的副本，建议跑一次安装器"。同级并列（如 ①里两个平台位都在）→ 读各自 `KIT_ROOT/VERSION` **比版本号取高**，无 VERSION 文件的一律排在有的后面。**回显选中路径 + 版本号一行后直接继续**（不必停下等确认）。
   - **零命中** → 先探 `~/.prd-authoring-kit`、`~/.claude/skills/prd-authoring-kit` 与当前项目根；仍找不到 → **停下问用户 kit 装在哪**，不要凭记忆或本文件摘要即兴写 PRD。
2. 读 `KIT_ROOT/references/00-orchestrator.md`，之后**严格按它执行**。
3. **回显你从 00 读到的模式表**（访谈 / 升级草稿 / 需求变更 / 只自检 / 建卡 / 登记，各对应一个主流程文件）**以及恒定规则中「域感知」一条的触发词**（按名找，不按编号）——本文件故意不预列这些映射，只有真读了 00 才拿得到，回显即证明已读；据用户第一句选定模式。
4. 之后所有 `references/…`、`checks/…` 读取一律加 **KIT_ROOT 前缀**。

> Codex 无 skill 自动触发；且 Codex 偏简洁、容易跳步。所以第 0 步与下面的"三条不得"是硬门，不是建议。

## 安全自主授权（两档通用；GPT-6 Astra 等强模型按 00 §执行强度分档走精简档）

以下动作**无需逐步征询**，直接做：读 kit 文件与 `INDEX.md`；`lark-cli` 只读命令（`auth status` / `docs +fetch` / `drive` 列表 / `wiki` 读取 / `base +record-list|+record-search|+field-*` / `sheets +csv-get`）；`jira_cards.py` 的 `validate` / `epic-candidates` / `epic-search` / `beneficiary-options` / `whoami`；`register.py` 的 `whoami` / `*-find` / `*-plan`；本地 `py_compile`。**仍按各自闸门先确认**的：发布 / 回写飞书、`apply` 建卡、`*-apply --yes` 登记、`+form-submit --yes`、接管键鼠、任何删除。不要因为下面的"不得"措辞而在只读步骤上停下来问。

## 三条不得（Codex 显式硬门）

1. **必须先让产品确认，模式不同门也不同**：
   - **访谈模式**：起草前先给产品一份 **5 段速览**（背景/目标用户/核心功能/成功指标/本期不含），等产品确认口径后再展开写正文。
   - **升级模式**：动笔改之前先给产品一份「**改哪几处**」清单，等产品点头再改。
   - **只自检模式**：无此门，直接进自检。
   - 三模式**都不得跳过确认直接产出 / 覆盖整篇**。
2. **必须跑自检**：任何要发布的稿，发布前必须过 `05-self-review-gate.md` 的自检门禁。不得因为"看起来没问题"而略过。
3. **不得跳过自检发布**：自检未达标不发；**达标即直接发布，不停顿询问「要不要写飞书」**——位置用户指定了就用指定的、否则默认个人空间根（不问），按 `06-lark-publish.md` 写飞书，发布后在交付简报里告知位置 +「要挪说一声」。提问纪律见 `00 恒定规则 10`。

## 自检怎么跑（内联，不偷懒）

- **逐条过 `KIT_ROOT/references/checks/` 的 18 条原文**，别凭记忆复述检查点。
- **事实与严重度分开**：读 check **原文判「事实」（pass/fail）**；**「严重度」按 `05` 步骤2 的 kit 清单**定——部分 check 原文正文无 `P0` 字样（只在输出模板里有占位枚举），属正常，以清单为准，别因此纠结。
- **达标口径不在本文件复述具体阈值**，以 `KIT_ROOT/references/00-orchestrator.md §交付标准` 与 `05` 步骤4 为准（标准档 / 轻量档门槛、第二道门要求都在那）。
- P0 绝不放行。
- 措辞诚实：自检的价值是**显著提高一次过概率**，不写"确保/保证一次过"。
- "并行子 agent 自检"是 Claude 才有的可选加速；Codex 内联逐条等价，**绝不因此跳过自检**。

## 降级（别卡住发布）

1. **无 `lark-cli`** → 按 `00 §降级`「无 lark-cli 全程模式」：开场告知一次；读飞书链接改为请用户全选复制粘贴；交付纯文本版 md（`07 §六` 格式）+ 自检简报；收尾附一次装法。**绝不中途反复让用户装、绝不卡在发布环节。**
2. **读不到 `checks/` 原文** → 退回 `01-authoring-rules.md` 内联评判，并在简报中**注明**是降级评。
3. 前提：授权预检按 00 恒定规则7 执行（`lark-cli auth status`；缺 scope 按规则7 内的清单一次性补齐——清单以 00 为唯一源，此处不复述以防漂移）；发布位置默认个人空间根、不主动问（用户指定则用指定位置）。

## 起草锚与颗粒度（薄指针）

- 起草锚是 `KIT_ROOT/references/02-prd-template.md`；颗粒度对齐 `KIT_ROOT/references/examples/`（标准档 = `example-copytrading-PASS`，轻量档 = `example-mini-lightweight`）。
- 访谈走 `03-interview-playbook.md`、升级走 `04-upgrade-draft.md`——具体怎么问 / 怎么改以这两份为准，本文件不复述。

## 定位说明

本 kit 主要面向加密交易所 / App；通用需求**也可用**（不过度承诺）。所有权威口径以 `KIT_ROOT/references/` 下文件为准，本文件只负责把你指过去。
