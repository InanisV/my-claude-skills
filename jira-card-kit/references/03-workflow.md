# 工作流：从需求到建单

## 1. 从 PRD 提取（有 lark 链接且 lark-cli 可用时）

用 `lark-cli docs +fetch --doc <PRD链接> --as user` 读 PRD（大文档先 `--scope outline` 再按需读节），提取下表；提取不到的进入提问清单：

| 提取目标 | 在 PRD 里找什么 | 映射到 |
|---------|----------------|--------|
| 需求名 | 文档标题（去掉【端】前缀）| summary 需求名部分 |
| 涉及端 | 标题前缀/范围章节（iOS/Android/H5/WEB）| 建卡组合 |
| 业务线 | 标题前缀（【AI】等）/所属项目 | summary 业务线标签 |
| 是否需要埋点 | 有无埋点章节/埋点表 | cf_16301 |
| 是否涉及新页面 | 交互稿是否含全新页面 | cf_15401 |
| 是否需要UI | 有无视觉/UI 交付物 | cf_11530 |
| 是否需要国际化 | 有无文案/多语言表 | cf_11531 |
| 后端/接口依赖 | 有无后端 PRD、接口章节 | cf_11506 + Blocks 链接 |
| 运营配置（WEB）| 有无后台配置章节 | cf_15700 |

⚠️ **受益方（cf_16706）不在提取表里，是刻意的**——它是成本归属决策，不是文档事实，禁止从 PRD 的项目名/Epic/业务线标签推断。必须走下面的提问流程由用户确认。

## 2. 一次性提问（提问纪律）

原则：**一轮问完、每题带默认值、能推断的不问**。典型问题集（按需删减）：

1. 🔴 **受益方（硬闸：产品本人亲口确认，AI 不得代为判断）**：问"这个需求做成后收益归谁？若是产品自提，有没有业务方愿意埋单（没有就只能挂产品线）"。**禁止给"默认 AI - Ealy"这类建议值**、禁止照抄主卡（kit 早期两处都犯过：先是把历史高频值当默认，后是推断+照抄主卡，两次都错）。拿到答复后填 `plan.meta.beneficiary_confirmed_by`（确认人）+ `beneficiary_rationale`（依据原话浓缩），缺一 validate 就报错。用户没正面回答就再问一次，别自己定。
2. 端范围：iOS+Android 双端？还是单端/加 H5？（默认按 PRD）
3. UI 设计师是谁？（需要 UI 时必问；用 `user-search` 把名字解析成 username）
4. Epic：默认 APP-24564（AI智能推荐专项），对吗？
5. 优先级：默认 P1+？
6. 组件模块：按业务线映射给默认（如 AI→首页模块），拿不准才问
7. 有没有要连的已有卡（后端 AIL 卡 / H5 卡）？依赖方向？

国际化任务 assignee = 建卡人自己（`whoami` 拿 name），不用问。

## 3. 生成 plan.json → validate → 用户确认

- 文件命名：`plan-<需求名拼音或英文缩写>.json`，放当前目录。
- 卡的顺序：故事在前、子任务在后（执行器要求父卡先建）。
- `python3 scripts/jira_cards.py validate plan-xxx.json` 通过后，**把计划表原样贴给用户**，等明确的"确认/建吧/OK"。
- 用户改字段 → 改 plan → 重新 validate → 重新确认。没有确认绝不 apply。

## 4. apply 与异常处理

- `python3 scripts/jira_cards.py apply plan-xxx.json`
- 全部成功 → 进入汇报。
- 中途失败：执行器停止建后续卡、保留已建卡（不自动删）。如实告诉用户已建了哪些、失败原因（常见：字段值和允许值不逐字一致、组件名写错、username 不存在）。修 plan 后重跑 apply 自动续传。
- 需要撤销：让用户在 Jira 界面删卡（kit 无删卡能力，这是刻意设计）。

## 5. 汇报格式（可直接贴群）

```
【需求名】Jira 卡已建：
- APP-xxxxx 【iOS】【AI】需求名（主卡） https://jira.mxcb.xyz/browse/APP-xxxxx
- APP-xxxxx 【Android】【AI】需求名 https://jira.mxcb.xyz/browse/APP-xxxxx
- APP-xxxxx 【UI设计】【AI】需求名 @设计师
- APP-xxxxx 【国际化】【AI】需求名
链接已挂（Clone/Relates/Blocks）。开发/测试负责人、埋点子任务等系统会自动补，无需处理。
```

汇报后提醒一句：几分钟后可以刷新主卡确认机器人已接管（PMO 填负责人、埋点子任务自动出现）。
