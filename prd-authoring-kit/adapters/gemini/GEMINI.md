<!-- PRD Authoring Kit · © Noah Zhan (@noah.zhan) · 二次分发/衍生须保留署名，不得标榜为自己原创创作。LICENSE / NOTICE 见根目录。 -->
# GEMINI.md —— PRD Authoring Kit (Gemini CLI 入口 · 薄指针)

> 安装：把本文件放为项目根的 `GEMINI.md`，或并入 `~/.gemini/GEMINI.md`（全局上下文）。
> 本文件是**薄指针**，不复述流程；唯一权威流程在 `references/00-orchestrator.md`，一切以它为准（避免与编排文件漂移）。

## 触发场景

当用户要**写 PRD / 出需求文档 / 把需求文档化 / 升级或改现有 PRD / 评审或自检 PRD / 判断能否过研发 nocode 门禁**，或给出飞书 PRD 链接、需求草稿、需求截图并想变成正式 PRD 时，进入下述流程。

## 第 0 步（不可跳过）：定位 KIT_ROOT 并回显三模式表

这是祈使句，不是脚注。**先做，再谈需求。**

1. 用你平台的文件查找能力定位 `00-orchestrator.md`（有 glob/file-search 工具用之；没有就用 shell：`find . ~/.prd-authoring-kit ~/.agents/skills ~/.gemini ~/.claude/skills -name 00-orchestrator.md 2>/dev/null` 或 `rg --files -g '**/00-orchestrator.md'`）；它的上一级目录是 `references/`，再上一级就是 **KIT_ROOT**。之后所有 `references/…` 与 `references/checks/…` 读取都加 `KIT_ROOT` 前缀。**多命中**先比 mtime 取最新、相同再取路径最深，**回显所选路径一行后直接用它**（不必停下等确认；多份通常是开发机 dev 仓库 + 安装副本并存）；**空命中**先探 `~/.prd-authoring-kit`、`~/.claude/skills/prd-authoring-kit` 与项目根，仍无则**停下问用户 kit 路径**，别凭本文件摘要即兴写 PRD。
2. 完整读 `KIT_ROOT/references/00-orchestrator.md`，**在回复里回显它的三模式表**（访谈 / 升级草稿 / 只自检），再严格按它执行。三模式表回显 = 已真正读到编排文件的证据。
3. **起草钉子**：进入访谈 / 升级后，起草前必读 `KIT_ROOT/references/02-prd-template.md` 骨架并对齐 `references/examples/` 对应档（标准档→`example-copytrading-PASS.md`，轻量档→`example-mini-lightweight.md`）；访谈走 `03`、升级走 `04`。

## 自检（必读原文 · 05 全部编号步骤都要跑）

- 发布进飞书前必跑 `KIT_ROOT/references/05-self-review-gate.md`。**自检 = 05 的全部编号步骤（0 结构扫描 → 1 → 2 → 2.5 → 3 汇总 → 4 判定与修复循环 → 5 输出标准报告），缺一不可**，最终必须产出步骤 5 的报告模板：
  - **步骤 0**：结构扫描（7 具名章节 + AI 友好度自证 + 复杂度预判）。
  - **步骤 1**：判 6 个适用域开关（`is_crypto_data` / `is_fund` / `is_push` / `has_tracking` / `declared_none` / `is_multiplatform`）；`is_fund=false` 也要**显式写明**「已确认全文无账户价值增减动作」，不静默跳过。
  - **步骤 2**：逐条**读 `KIT_ROOT/references/checks/` 原文**判「事实」（pass/fail），**严重度按 `05` 步骤 2 清单的 kit 口径**（部分 check 原文无 P0 字样属正常，以清单为准）。
  - **步骤 2.5**：过第二道门**逻辑内审六维 A/F/B/C/E/T**（判据见 `08`）+ 资金安全幂等有效性反证——报告模板六个勾位缺一不可。
  - **步骤 3/4/5**：汇总 → 不达标就改稿重跑（修复循环）→ 输出 05 步骤 5 的标准报告（放行留痕、适用域声明都在报告里）。
- Gemini 无子 agent —— 这**不影响**自检：内联逐条过每一条 check 即可，与 Claude 的并行子 agent 自检等价；「并行子 agent」仅是 Claude 可选加速，绝不因此跳过任何一条。
- **达标口径以 `00-orchestrator.md` / `05` 为准**（发布门槛见 05「放行三原则」：门禁 P0/P1 永不放行、②结构性断点默认阻塞可知情放行），本文件不复述具体数字阈值；P0 绝不放行。

## 降级（读不到就退，别卡住）

- 定位失败（含 find/rg 兜底也失败）/ 读不到 `references/` 或 `checks/` 原文 → **停下问用户 kit 路径**；仍读不到 checks 原文则退回 `01-authoring-rules.md` 内联评并注明「未逐条核对 checks 原文」。
- 无 `lark-cli` → 按 `00 §降级`「无 lark-cli 全程模式」：开场告知一次、读入靠用户粘贴、交付纯文本版 md（`07 §六` 格式）+ 自检简报、收尾附一次装法；绝不中途推销、绝不卡发布。
- 「并行子 agent 自检」仅 Claude 可选加速；Gemini 内联逐条即完整自检，不因缺子 agent 而跳过。

## 前提

- 授权预检按 00 恒定规则7 执行（`lark-cli auth status`；缺 scope 按规则7 内的清单一次性补齐——清单以 00 为唯一源，此处不复述以防漂移）。
- 发布位置**默认个人空间根、不主动问**（用户指定了目标 wiki / 文件夹就用指定的），按 `KIT_ROOT/references/06-lark-publish.md` 写飞书，发布后告知位置、可按需挪（提问纪律见 `00 恒定规则 10`）。
- **写飞书前必执行 `06` 步骤 0 净化**（那段 `awk | sed` 脚本 + 占位符红灯校验）再 `create`，别把半成品/指引/`[必填]` 标记发出去。

> Gemini CLI 无 skill 自动触发；本段为常驻指令。命中触发场景就先执行第 0 步，而不是凭摘要即兴写 PRD。
