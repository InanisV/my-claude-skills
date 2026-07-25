> **quant-code-review · 维度参考文件** — 由 SKILL.md 按维度 P.3 的适用性裁定按需加载，不要无差别全量读入。
> 文中交叉引用（如"见 2.8"、"参见 4.6"）按维度编号到 references/ 对应文件查找。

## 维度 P：项目阶段与部署就绪度（前置，最先执行）

**这个维度是所有后续维度的前提。** 如果不先判断项目处于什么阶段，后续维度的检查就
可能在空气上打拳 — 比如在一个纯回测项目上检查"实盘/回测对齐"，维度0/1/3/4全部
变成空检查、静默通过，但实际上最大的风险是：**实盘根本不存在**。

这个盲区曾在真实项目中发生：回测引擎经过充分审计（费率、保证金、清算模型全部对齐
交易所），所有维度都显示✅。用户以为"可以部署了"，但实际上：没有执行器、没有 API
集成、没有实时数据源、没有仓位管理器、没有 README。距离"填上 API key 就能跑"
还差整个实盘层。

### P.1 项目组件扫描

```
方法（自动化）：
1. 扫描项目目录结构，识别以下组件是否存在：
   - 回测引擎: backtest*.py, engine*.py, simulator*.py
   - 因子/信号库: factor*.py, signal*.py, alpha*.py, indicator*.py
   - 策略配置: strategy*.py, config*.py, settings*.py, *.yaml, *.json (config)
   - 实盘执行器: bot*.py, trader*.py, executor*.py, live*.py, runner*.py
   - 交易所 API 集成: exchange*.py, client*.py, *_sdk*, *hyperliquid*, *binance*, *ccxt*
   - 订单管理: order*.py, execution*.py, placement*.py
   - 仓位管理: position*.py (非回测内部), portfolio*.py (实盘)
   - 实时数据源: websocket*.py, stream*.py, feed*.py, realtime*.py
   - 风控模块: risk*.py, killswitch*, circuit_breaker*
   - 部署配置: Dockerfile, docker-compose*, systemd*, supervisord*, *.service
   - 依赖管理: requirements.txt, pyproject.toml, setup.py, poetry.lock
   - 文档: README*, DEPLOY*, SETUP*, docs/
   - 密钥管理: .env.example, config.example.*, *secret*, *credential*

2. 对每个组件输出存在性状态

3. 判断项目阶段：
   A. 纯回测/研究阶段: 只有回测引擎和因子库，无实盘组件
   B. 开发中: 有部分实盘组件但不完整
   C. 可部署: 所有关键组件齐全
   D. 已上线: 有运行日志/状态文件证明实盘在运行

为什么最先做这一步：
- 1 分钟的目录扫描就能避免后续所有维度的空检查
- 如果项目还在 Phase A，维度 0/1/3/4 的"实盘侧"检查全部不适用
  → 应明确输出"⚠️ 实盘组件缺失，以下维度仅检查回测侧"
  → 而不是静默跳过让用户误以为"全部通过"
- 经验教训：回测审计全绿 ≠ 可以部署，这个误解浪费了数天的排查时间
```

### P.2 部署就绪度清单（Deployment Readiness Checklist）

只有在 P.1 判定目标是部署（用户提到"上线"、"部署"、"实盘"、"服务器"等）时才需要
逐项检查。纯研究项目可以跳过，但必须在报告中明确标注"部署就绪度：未评估（纯研究项目）"。

```
必要组件（缺任何一个都无法"填上 API key 就能跑"）：

□ P.2.1 交易所 SDK/API 集成
  - 是否引入了交易所 SDK（如 hyperliquid-python-sdk, ccxt, python-binance）
  - 是否有认证模块（API key + secret 加载、签名）
  - 是否支持目标交易所的所有必要端点（下单、查持仓、查余额、查行情）
  - 是否区分了 testnet 和 mainnet 环境

□ P.2.2 实盘执行器（Live Executor）
  - 是否有信号→订单的转换逻辑（target_positions → orders）
  - 是否处理了订单类型（limit / market / 超时切换）
  - 是否有成交确认和状态同步机制
  - 是否有限价单超时后自动转市价单的逻辑（对应回测中的 entry 50% maker / 50% taker 假设）

□ P.2.3 实时数据源
  - 是否有 bar 数据获取机制（REST 轮询 / WebSocket 推送）
  - 获取频率是否与回测的 rebalance_freq 一致
  - 是否有足够的历史数据用于因子计算（lookback window）

□ P.2.4 仓位同步与对账（Reconciliation）
  - 是否有本地持仓与交易所持仓的对比机制
  - 是否处理了幽灵仓位（本地有、交易所无）和孤儿仓位（交易所有、本地无）
  - 是否有定期 reconciliation 的调度

□ P.2.5 密钥与配置管理
  - 是否有 .env / .env.example 模板（API key, secret, passphrase）
  - 密钥是否通过环境变量加载（而非硬编码在代码中）
  - 是否有 config 文件区分 dev / staging / prod 环境
  - .gitignore 是否排除了 .env 和其他密钥文件

□ P.2.6 依赖管理
  - 是否有 requirements.txt 或 pyproject.toml 列出所有依赖
  - 是否 pin 了版本号（避免依赖升级导致行为变化）
  - 是否包含了交易所 SDK 依赖

□ P.2.7 入口与调度
  - 是否有清晰的启动入口（main.py / run_bot.py / cli 命令）
  - 是否有周期性调度（cron / APScheduler / 循环 sleep）
  - 是否有 graceful shutdown（SIGINT/SIGTERM handler）
  - 是否有部署脚本或容器化方案（Dockerfile / docker-compose / systemd service）

□ P.2.8 README 与部署文档
  - README 是否包含：项目简介、策略说明、安装步骤、配置说明、运行命令
  - 是否有明确的 Quick Start（5 步之内从 clone 到运行）
  - 是否说明了回测与实盘的关系（哪些参数共享、如何切换）
  - 是否有风险提示和免责声明

□ P.2.9 监控与告警
  - 是否有健康检查（heartbeat / process alive 检测）
  - 是否有 PnL / 持仓 / 余额的定期报告（Telegram / Discord / 邮件）
  - 是否有异常告警（连续亏损、API 报错、仓位偏离预期）
  - 是否有 kill switch（手动/自动停止交易的紧急机制）

□ P.2.10 试运行与灰度上线路径
  - 是否有 dry-run / paper 模式（信号照跑、不下真实单、全链路日志照写）
  - 是否支持 testnet 环境切换（与 P.2.1 联动）
  - 首次实盘是否有小资金灰度约定（如 ≤10% 目标资金跑 1-2 周，对比实盘
    fill 率/费率/信号与回测的偏差后再放量）
  - DRY-RUN 开关默认值必须在安全侧（默认不下真实单），且启动日志显著
    打印当前模式（见 3.12 .env 教训：静默 DRY-RUN 也是部署失败）
```

### P.3 维度适用性裁定

基于 P.1 的判定结果，自动裁定后续维度的适用性：

```
项目阶段 A（纯回测/研究）：
  ✅ 维度 2（回测真实性）— 全量检查
  ✅ 维度 5（代码性能）— 只检查回测性能
  ✅ 维度 6（AI 协作质量）— 全量检查
  ✅ 维度 7（供应链安全）— 检查 7.1 依赖链 + 7.3 密钥管理（即使纯回测也需要保护 API Key 和依赖安全）
  🔴 维度 P.2（部署就绪度）— 输出缺失清单，标注"距离可部署缺以下组件"
  ⚪ 维度 0（模块盘点）— 标注"仅回测侧，实盘侧 N/A"
  ⚪ 维度 1（策略对齐）— 标注"无实盘可对比，N/A"
  ⚪ 维度 3（运维鲁棒性）— 标注"实盘不存在，N/A"
  ⚪ 维度 4（状态持久化）— 标注"实盘不存在，N/A"

项目阶段 B（开发中）：
  全部维度适用，但对缺失组件标注"开发中 / TODO"
  🔴 维度 4.5（监控导出协议）— 必须在上线前实现，开发阶段就应开始接入

项目阶段 C/D（可部署/已上线）：
  全部维度全量检查（维度 7 全量，含运行时隔离和网络出站控制）
  🔴 维度 4.5（监控导出协议）— 必查！缺失 = 策略处于监控盲区，必须立即修复
  🔴 维度 P.4（Profile 风险开关清单）— 必查！4/19 cascade 教训
```

### P.4 Profile 风险开关清单审计（Profile Risk-Switch Inventory）🔴 高优先级

> **背景故事**：2026-04-19 V15_PROD 实盘从 $3505 → $918 (-73.8%)。事后定位发现：
> profile 里 `dd_tier_1: 0.99 / dd_scale_1: 1.0 / dd_kill_pct: 0.99 / use_liquidation_check: False`
> —— 几乎所有"风控开关"都被设为 effectively-off 值。这些值不是 bug，是过去半年里
> 为了拉 CAGR 一个一个手动调高的，每次调整都觉得"这次没事"，累积起来造成系统性失稳。
> profile 文件 200+ 行，没有任何机制强迫你把所有风控开关一起看。
>
> 教训：**production profile 必须有强制 inventory，把所有 risk-related flag 显性枚举，
> 对每一个 effectively-off 值要求技术理由 + 至少一个对照实验 commit**。

**为什么必须做**：
- profile 文件长，分散在十几个章节，看局部参数无法发现"整体风控被关空"
- 单个参数调整看起来都"合理"（"DD kill 0.99 是因为 0.35 太敏感"），但累加起来等于无防御
- 实盘亏损发生时，看到的是"all my flags say protected"，但实际全是 off

**审查清单**：

```
□ P.4.1 自动化清单生成
   □ 每个 production profile 必须配套生成一份"风险开关清单"
     （格式：表格，列出每个 risk-related flag 的当前值 + 默认值 + effectively-off 判定）
   □ 推荐用脚本自动生成：scan profile dict 找所有匹配以下模式的 key：
     - use_*_check / use_*_simulation / use_*_defense / use_*_hibernation
     - *_kill_* / *_kill_pct / *_kill_threshold
     - dd_tier_* / dd_scale_* / dd_score_*
     - max_exposure_pct / max_concurrent_positions / max_dca_layers
     - regime_scale_* / regime_threshold_* / regime_lc_*
     - hysteresis_* / cooldown_*
     - *_per_position_cap_* / *_position_cap_*
   □ 自动化脚本示例参见 audit_risk_flags.py（skill 内置）

□ P.4.2 Effectively-Off 值识别
   对每个 risk flag 判定是否 effectively-off：
   □ Boolean flag = False → 标记 ⚠️
   □ DD/threshold flag ≥ 0.95 → 标记 ⚠️（等于"几乎不会触发"）
   □ Scale flag = 1.0（应当 < 1.0 才有效）→ 标记 ⚠️
   □ Cap/limit flag = inf 或 None → 标记 ⚠️
   □ Score boost flag = 0.0（应当 > 0 才有效）→ 标记 ⚠️
   □ 任何"effectively-off"值必须在审计报告中显性列出

□ P.4.3 技术理由 + 对照实验要求
   每一个被标为 ⚠️ 的 flag，必须：
   □ profile 文件内有 inline 注释，引用一个 commit hash 或文档说明为什么调成这个值
   □ 该 commit 必须包含一组 A/B 对照实验数据（开/关该 flag 的回测结果）
   □ 对照实验必须用 use_liquidation_check=True 的真实回测（参见 2.13）
   □ 缺乏注释 + 对照 → 🔴 关键问题（这是 4/19 cascade 的直接成因）

□ P.4.4 累积效应警报
   □ 计算"effectively-off flag 占总 risk flag 的比例"
   □ 如果 > 30%，🔴 必须警报："profile 累积关闭过多风控开关，CAGR 突破可能建立在
     虚假地基上"
   □ 如果 > 50%，🔴🔴 拒绝部署：必须重新评估每个 effectively-off 的累积影响

□ P.4.5 Profile diff 审计
   □ 任何 profile 修改 PR 必须显示"风险开关清单 diff"
     （不是普通的 git diff，而是聚焦在 risk flag 上）
   □ 修改 PR 描述必须回答：本次修改是否关闭/松动了任何 risk flag？为什么？
```

**自动化脚本**：`scripts/audit_risk_flags.py`（skill 内置，**单一真相源** —
该版本含 AST fallback 解析、更全的 risk pattern、max_exposure 检查，请勿在文档中
另行内联复制源码，防止两份代码漂移）：

```bash
python scripts/audit_risk_flags.py config/profiles.py V15_PROD
# exit 0 = OK / 1 = WARN (off-ratio > 30%) / 2 = REJECT (off-ratio > 50%)
# 审计不受信仓库时加 --ast（禁用 exec，纯 AST 解析）
```

**真实案例（4/19 V15_PROD）**：
- 总 risk flag: 17
- effectively-off: 9（dd_tier_1/2/3 + dd_scale_1/2/3 + dd_score_1/2/3 + dd_kill_pct + use_liquidation_check）
- 比例: 53% → 🔴🔴 REJECT
- 实际后果：实盘 -73.8%

如果这个 audit 在 V37 commit e80de33（4/13）就跑过，能避免 6 天的虚假研究 + 实盘事故。
