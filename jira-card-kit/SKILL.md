---
name: jira-card-kit
description: 把产品需求（PRD 链接或口头描述）按 MEXC 房规拆成 Jira 卡并批量创建：APP 双端标准包（iOS/Android 故事 + UI设计任务 + 国际化任务 + Cloners/Relates 链接）、WEB/H5 故事、跨端 Blocks 依赖。当用户说「建 jira 单 / 建卡 / 拆单 / 把这个 PRD 建成 jira / 提测拆卡 / 开发排期建单」，或给出 PRD 链接并要求进 Jira 时使用。只建卡不删卡；创建前必出计划表经用户确认。
---

# jira-card-kit（MEXC Jira 建单）

把一个需求变成一组符合房规的 Jira 卡。**铁律：先出建单计划表 → 用户明确确认 → 才执行创建；绝不静默建卡，绝不删卡，绝不碰机器人管的字段。**

执行器：`scripts/jira_cards.py`（零依赖，读 `~/.claude/settings.json` env 里的 `JIRA_URL`/`JIRA_PERSONAL_TOKEN`，或同名环境变量）。

## 流程（按序执行，每步首次进入时读对应参考）

1. **认证自检**：`python3 scripts/jira_cards.py whoami`。失败则引导用户按团队文档配 token（见 README 安装节），不要继续。
2. **收集需求信息**：
   - 输入是 lark PRD 链接且 `lark-cli` 可用 → 读 PRD 提取字段答案（提取映射见 [references/03-workflow.md](references/03-workflow.md)）；
   - 无 PRD → 按 03-workflow 的问题清单向用户收集。
   - 读 [references/01-card-model.md](references/01-card-model.md) 确定这个需求该建哪几张卡（标准包结构、机器人边界——很多卡和字段系统会自动生成，别重复建）。
3. **一次性补齐提问**：只问无法推断的项（设计师人选、端范围、业务线标签、Epic、跨端依赖），能给默认值的都带默认值。禁止挤牙膏式追问。
   🔴 **唯一例外——受益方 customfield_16706 是硬闸**：它决定人力成本记在哪个团队账上（定额消费、季末回溯审计），组织明令"谁收益填谁、不要想当然"。**必须由使用本 kit 的产品本人亲口确认，AI 才能代写**——不许给默认值、不许从 Epic/项目名/需求名推断、不许照抄主卡或相似卡（主卡自己也可能填错）。问法："这个需求做成后收益归谁？如果是产品自提，有没有业务方愿意埋单？"拿到答复后把确认人填进 `plan.meta.beneficiary_confirmed_by`、依据填进 `beneficiary_rationale`；**两者缺一 validate 直接报错、建不了卡**。判定规则见 [references/02-field-model.md](references/02-field-model.md) 红线节。
4. **生成 plan.json**：字段值与 payload 形状严格按 [references/02-field-model.md](references/02-field-model.md)；文件放当前工作目录或临时目录。参考 `examples/plan-app-pair.json`（APP 双端）与 `examples/plan-web-story.json`（WEB 故事）。
5. **校验并出计划表**：`python3 scripts/jira_cards.py validate <plan.json>`，把输出的计划表**连同「受益方确认」区块**原样展示给用户，**等用户明确说"确认/建吧"**。用户改哪就改哪，改完重新 validate。受益方那一段不许省略——它是最容易错、后果最实的字段。
6. **执行**：`python3 scripts/jira_cards.py apply <plan.json>`。部分失败时如实报告已建卡清单（结果在 `<plan>.result.json`，修正后重跑 apply 自动续传，已建的不会重复建）。
7. **汇报**：把 apply 输出的卡链接清单整理给用户（可直接贴群）。提醒：机器人会在几分钟内自动补开发/测试负责人、埋点子任务等，不用管。

## 边界

- v1 支持：APP 标准包、WEB/H5 故事、连到已有卡的 Blocks/Relates 链接。其他项目（OPT/XHHD/AIL/GJH…）明确告知暂不支持，别硬建。
- 只创建，不删卡、不改状态、不改其它字段。**唯一的改卡能力是 `set-beneficiary`**（受益方错填是组织级高频问题，必须能纠正；默认只预览，加 `--apply` 才写入）。用户要删卡或改别的字段 → 请他自己在 Jira 界面处理。
- 【新页面】子任务不在建卡标准包里（历史数据 23/28 是开发排期后才补建的）；用户明确要求时才作为独立子任务加进 plan。
