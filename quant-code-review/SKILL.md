---
name: quant-code-review
description: |
  量化交易系统代码审计 — 代码改动后的多维度审查，支持 Quick（diff 驱动）与
  Full（全量）两种模式。维度：P 阶段与部署就绪度（P.4 风险开关清单）、0 模块
  盘点、1 实盘/回测对齐（1.4 部署缺口、1.5 bar 时间约定）、2 回测真实性
  （2.13 真实性 flag、2.14 过拟合稳健性）、3 运维鲁棒性（3.11 Maker-First、
  3.12 NTP/.env、3.13 订单量化）、4 状态持久化（4.5 Monitor Protocol、
  4.5.2 Identity 反硬编码、4.6 Unknown-state latch）、5 性能、6 AI 协作
  （6.5 外部 Review 纪律）、7 供应链安全。

  🔴 必查：4.5；P.4+2.13+4.5.2（"4/19 Cascade 三件套"，源自 2026-04 实盘
  -73.8% 事故）；1.5+4.6+6.5（源自 2026-05 codex R12-R15：bar 时间 1h 偏移、
  unknown-state double-fill、外部建议盲从）。任一维度发现问题按 🔴 关键问题上报。

  触发时机：策略逻辑/实盘 bot/回测引擎改动后；用户说 "review"、"审查"、
  "检查一下"、"code review"、"改完了"、"提交了"、"commit 了"；Claude 自己
  完成代码改动准备 commit 之前；即使一个参数微调，都可能带来策略行为重大偏离。

  适用于所有量化项目（现货/合约/期权、CTA/套利/做市/DCA/网格等）。
  Polymarket 回测-实盘差异专项另用 polymarket-execution-audit。
metadata:
  version: "0.3.0"
  author: "Tom Zhang"
---

# 量化交易系统代码审计

## 核心原则

**实盘必须和回测对齐。** 这是整个审计的第一性原理。任何回测中没有的东西都不应出现在实盘中（运维层面的鲁棒性设施除外）。反过来，回测中存在的任何逻辑，实盘必须精确复制。

这个原则的推论：
- 不要添加"看起来合理"但未经回测验证的风控
- 参数值必须完全一致，"更保守"不等于"更好"
- 不仅代码逻辑要对齐，数据计算方式、更新频率、窗口大小都要对齐

第二原则：**回测的可信度上限 = 输入数据的真实度 × 模拟机制的启用度。** 引擎实现得再对，flag 被关掉（2.13）或数据是假的（2.10），产出的一切结论都在虚假世界里成立。

## 结构与加载方式（先读这里）

本 skill 采用分层结构。**不要一次性读入全部 references/** — 先跑维度 P 裁定
适用范围，再只 Read 适用维度的文件，把上下文留给被审计的代码本身。

| 文件 | 内容 | 何时加载 |
|---|---|---|
| `references/dim-P-stage.md` | 维度 P：阶段评估、P.2 部署就绪度、P.3 适用性裁定、P.4 🔴风险开关清单 | **每次审计都先加载** |
| `references/dim-0-1-alignment.md` | 维度 0 模块盘点；维度 1 实盘/回测对齐（1.4 🔴部署缺口、1.5 🔴bar 时间约定） | 有实盘组件时 |
| `references/dim-2-backtest.md` | 维度 2 回测真实性（2.1-2.14，含 2.13 🔴真实性 flag、2.14 过拟合稳健性） | 涉及回测引擎/策略逻辑时 |
| `references/dim-3-ops.md` | 维度 3 运维鲁棒性（3.1-3.13，含 3.11 Maker-First、3.12 NTP/.env） | 实盘阶段 B/C/D |
| `references/dim-4-state.md` | 维度 4 状态持久化（含 4.5 🔴Monitor Protocol、4.5.2 🔴Identity、4.6 🔴硬闩锁） | 实盘阶段 B/C/D |
| `references/dim-5-perf.md` | 维度 5 代码性能 | Full 模式或性能问题 |
| `references/dim-6-ai-collab.md` | 维度 6 AI 协作质量（含 6.5 🔴外部 Review 纪律） | AI 参与编码/外部 review 后 |
| `references/dim-7-supply-chain.md` | 维度 7 供应链与运行时安全（7.1-7.8） | 依赖/密钥/部署改动时；Full 必查 |
| `references/report-template.md` | 审计报告完整模板（与全部维度同步） | 输出报告前 |
| `references/lessons.md` | 59 条实战经验教训（事故复盘沉淀） | 写报告前对照；模式相似时引用 |

## 两种审计模式

**Quick 模式**（默认 — 小 diff、参数微调、单模块改动）：
1. `git diff` 确定改动面（文件 + 参数）
2. 必跑三个内置脚本（见下方"自动化前置扫描"）— 无论 diff 多小
3. 按 diff 涉及的维度加载对应 reference，仅逐项检查受影响小节
4. 过一遍下方"红线清单"（成本极低，但每条都是事故级）
5. 输出精简报告：涉及维度结果 + 红线状态 + 发现的问题/建议修复

**Full 模式**（重大改动、新项目接入、上线前、事故后复盘、用户明确要求全面审查）：
- P → 0 → 1 → 2 → 3 → 4 → 5 → 6 → 7 全维度，按 P.3 裁定跳过 N/A 维度
- 输出 `references/report-template.md` 完整结构

模式选择拿不准时：涉及 production profile / 下单链路 / 保证金 / 状态持久化的
任何改动一律 Full。参数微调若命中 P.4 risk flag 模式，也升级为 Full。

## 审计流程（Full 模式）

1. **维度 P：项目阶段评估**（Read `references/dim-P-stage.md`）— 判断纯回测 /
   开发中 / 可部署 / 已上线，据 P.3 裁定后续维度适用范围
2. **定位项目关键文件**：回测引擎、实盘 bot 主文件、配置/profile 文件
3. **理解策略架构**：趋势跟踪 / 均值回归 / 套利 / 做市 / DCA / 网格等
4. **自动化前置扫描**（见下节）：三个专项脚本 + grep battery
5. **维度零：模块清单盘点**：扫出"回测有但实盘没有"的模块（发现率最高的一步）
6. **按裁定结果逐维度检查**：按需 Read 对应 reference，适配到具体项目
7. **输出结构化报告**（Read `references/report-template.md`）

## 自动化前置扫描（scripts/ 内置）

| 脚本 | 维度 | 作用 | 退出码 |
|---|---|---|---|
| `audit_risk_flags.py` | P.4 | Profile 风控开关 effectively-off 比例 | 1=WARN(off比例超30%) 2=REJECT(超50%) |
| `audit_cascade_simulation.py` | 2.13 | 全库扫描 use_*_check / next_bar_entry 实际值 | 1=research 有 False 2=production 有 False |
| `audit_identity_hardcode.py` | 4.5.2 | identity 字段硬编码 codename 识别 | 1=WARN 2=CRITICAL |
| `grep_battery.sh` | 多维度 | 各维度 grep 探测一键预扫描（只读） | — |

```bash
python scripts/audit_risk_flags.py config/profiles.py PROD_PROFILE   # 不受信仓库加 --ast
python scripts/audit_cascade_simulation.py .
python scripts/audit_identity_hardcode.py .
bash   scripts/grep_battery.sh .
```

任一脚本 CRITICAL（exit 2）→ 报告中列为 🔴，阻止 commit/部署直到修复。
CI/pre-commit 集成方式见 `scripts/README.md`。

## 严重度定义（全 skill 统一）

| 等级 | 含义 | 处置 |
|---|---|---|
| 🔴🔴 REJECT | 拒绝部署级（如 P.4 off-ratio 大于 50%） | 阻止 commit/部署，重评估 |
| 🔴 Critical | 必须修复；🔴 高优先级必查项发现问题一律记此级 | 部署前必修 |
| 🟠 High | 显著风险（如 fill detection 不可靠） | 部署前应修 |
| 🟡 Medium | 应修复，可带条件部署 | 排期修复 + 报告留痕 |
| 🟢 Low/Info | 改进建议 | 酌情 |

各 reference 中出现的 🟠 ORANGE / 🟡 YELLOW 等判级均映射到本表。

## 🔴 红线清单（任何模式都必查，不可妥协）

1. production profile 里 `use_liquidation_check=False` 或任何 realism flag 关闭
   且无 commit 级技术理由（2.13）
2. 基于 realism-flag-off 跑出的"突破数字"未在 flag 全开下重跑就进入决策（2.13.4）
3. "safety mechanism" 候选实为关闭模拟 flag —"把看不到当成安全"（2.13.5）
4. P.4 effectively-off ratio 大于 50% → 拒绝部署（P.4.4）
5. identity.strategy 为硬编码 codename，不从 cfg 反射（4.5.2）
6. 实盘策略无 monitor_export.json，或心跳间隔超过 heartbeat_timeout × 0.8（4.5）
7. order ack 丢失（unknown-state）后无 hard latch，主循环继续交易（4.6）
8. 交易所 API key 开启 withdraw/transfer 权限（7.3/7.5/7.8）
9. 真实密钥硬编码在代码中，或 git 历史泄露未轮换（7.3）
10. 实盘执行方式与回测费率模型互不镜像（如实盘纯 taker、回测按 maker-first
    加权计费）（3.11/2.6）
11. 实盘亏损排查未先确认"跑的是不是仓库里最好的那个策略"就深入执行层（1.4）
12. 外部 review 的 preference 类建议未算账（EV math）就直接采纳（6.5）

## 输出格式

按 `references/report-template.md` 输出。Quick 模式只输出：涉及维度的结果表 +
红线清单状态 + "发现的问题"（按 🔴🟠🟡🟢 排列）+ "建议修复"（标优先级）。
🔴 高优先级必查项（4.5 / P.4 / 2.13 / 4.5.2 / 1.5 / 4.6 / 6.5）无论结果如何
都必须在报告中显式出现，不允许静默跳过。

## 经验教训

59 条实战经验（每条都来自真实事故或真实审计）存于 `references/lessons.md`。
写最终报告前加载对照一遍：项目当前模式与某条教训相似时，直接引用编号并按
该教训的验证方法复查。

## 与其他 skill 的边界

- Polymarket 二元期权/CLOB 执行链路专项 → `polymarket-execution-audit`
- 审计结论的独立复核（codex 三层审计、finding 分类 Bug vs Preference）→
  `codex-audit`（与本 skill 的 6.5 维度联动）
- 策略研究/参数优化/找 alpha → `alpha-lab`（本 skill 负责验收其产出：
  champion 需过 2.12-2.14 四重验收 + 1.4 部署缺口检查）
- 每次 git commit 前的工作区清理 → `git-cleanup`（先清理，后审计，再 commit）
