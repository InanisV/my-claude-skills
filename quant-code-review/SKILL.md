---
name: quant-code-review
description: |
  量化交易系统代码审计 — 在每次重大代码改动后自动执行全面审查。
  覆盖十个维度：(P) 项目阶段与部署就绪度（前置，最先执行），(0) 模块清单盘点，(1) 实盘/回测策略逻辑对齐（含 🔴1.4 策略部署缺口检测 — 高优先级），(2) 回测引擎真实性（含 2.10 数据真实性审计 + 2.11 Margin-Ratio 自动减仓），(3) 实盘运维鲁棒性（含 3.6 MarginMonitor 实时保证金监控 + 3.7 账户资金流水过滤 + 3.8 实盘日志体系 + 3.9 交易对下架防御），(4) 状态持久化完整性（含 🔴4.5 Monitor Protocol 监控导出协议 — 高优先级必查），(5) 代码性能，(6) AI协作代码质量，(7) 供应链与运行时安全。

  🔴 特别注意：维度 4.5（Monitor Protocol 监控导出协议）是高优先级必查项！
  每个实盘策略都必须实现 monitor_export.json 标准导出。审查时如果发现缺失，
  必须作为 🔴 关键问题上报，不能降级为建议或跳过。改造成本仅 3-5 行代码。

  触发时机（非常重要）：
  - 完成策略逻辑修改后（参数、信号、仓位管理、PnL模型等）
  - 完成实盘bot代码改动后
  - 完成回测引擎改动后
  - 用户说"review"、"审查"、"检查一下"、"code review"
  - 用户说"改完了"、"提交了"、"commit了"之后
  - Claude自己完成了一组代码改动准备commit之前

  即使改动看起来很小也要触发。经验表明：一个参数的微调、一个fetch数量的变化、
  一个fee从hardcoded改成config读取，都可能带来策略行为的重大偏离。

  适用于所有量化交易项目（现货/合约/期权、CTA/套利/做市/DCA/网格等）。
---

# 量化交易系统代码审计

## 核心原则

**实盘必须和回测对齐。** 这是整个审计的第一性原理。任何回测中没有的东西都不应出现在实盘中（运维层面的鲁棒性设施除外）。反过来，回测中存在的任何逻辑，实盘必须精确复制。

这个原则的推论：
- 不要添加"看起来合理"但未经回测验证的风控
- 参数值必须完全一致，"更保守"不等于"更好"
- 不仅代码逻辑要对齐，数据计算方式、更新频率、窗口大小都要对齐

## 使用方法

每次触发时，Claude需要：
1. **维度 P：项目阶段评估**：先判断项目处于什么阶段（纯回测 / 回测+实盘 / 纯实盘），决定后续维度的适用范围
2. **定位项目关键文件**：找到回测引擎和实盘bot的主文件、配置文件
3. **理解策略架构**：识别项目使用的策略类型（趋势跟踪、均值回归、套利、做市等）
4. **维度零：模块清单盘点**：先用自动化方法扫出"回测有但实盘没有"的功能模块（这一步往往能发现最严重的问题）
5. **按七个维度逐项检查**：使用下面的checklist框架，适配到具体项目
6. **输出结构化报告**

## 审计流程

按以下维度顺序执行（P → 0-7 + 2.10 数据真实性子维度）。维度 P 最先执行，它决定后续哪些维度适用。每个维度是一个 checklist 框架，根据具体项目适配检查项。

---

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
```

---

## 维度零：模块清单盘点（维度 P 之后执行）

这一步的目的是快速发现**回测中有但实盘中完全缺失的功能模块**。这类问题在实际审计中最容易被忽视，但影响最严重 — 它意味着实盘运行的根本不是回测验证过的策略。

回测引擎通常作为"策略实验室"，开发节奏比实盘快。新模块（仓位管理、风控、信号增强等）往往先在回测中实现和验证，但可能遗漏了向实盘的移植。

### 0.1 功能模块实现状态扫描

```
方法（自动化优先）：
1. 在回测代码中找到所有 feature flag / enable 开关
   - 典型模式: grep -rn "_ENABLE\|_enable" backtest/ strategy/ portfolio/
   - 或按项目惯例的命名模式（如 MODULE_ON, use_xxx, xxx_active 等）
2. 对发现的每个模块名，在实盘代码中搜索同名引用
   - grep -rn "MODULE_NAME" live/ bot/ trader/
3. 对每个模块输出: [模块名] [回测: 有/无] [实盘: 有/无] [当前是否启用]
4. 重点关注："回测有 + 实盘无 + 当前启用"的组合 — 这是最严重的

为什么先做这一步：
- 速度快（几秒钟的grep即可完成）
- 发现率高（历史经验中超过一半的严重问题在这步暴露）
- 如果发现缺失模块，后续维度一的逐项对齐可以更有针对性
```

### 0.2 配置注册完整性

检查回测配置中的所有参数是否在实盘的基础配置/settings中有注册（即有默认值）。

```
背景：
回测引擎和实盘通常使用不同的配置加载机制。典型差异：
- 回测器: 用 proxy/overlay 对象（如 getattr 兜底），即使参数不在基础配置中也能工作
- 实盘: 用 apply_overrides / setattr 等严格方式，要求参数必须预先注册

这种差异会导致：一组参数在回测中跑得完美，但实盘加载时直接崩溃。

方法：
1. 找到实盘的配置加载入口（通常在 main 文件中，如 apply_overrides / load_config）
2. 检查加载机制是否有 key 存在性检查（hasattr / KeyError / 白名单）
3. 如果有严格检查，验证所有被回测使用的参数 key 在基础 settings 模块中都有默认值
4. 特别关注：新模块引入的参数 — 这些最容易遗漏注册

常见问题模式：
- 回测能跑通（proxy对象兜底），实盘崩溃（严格检查失败）
- 旧 preset 没问题（不含新参数），新 preset 崩溃（含新参数但 settings 无默认值）
```

---

## 维度一：实盘/回测策略对齐

这是最重要的维度。需要将回测和实盘的**每一条决策路径**逐一对照。

### 1.1 参数值对比

自动提取回测Config和实盘Config的所有共有参数，逐一比较默认值：

```
方法：
1. 找到回测和实盘各自的Config/Settings类或配置文件
2. 列出所有参数名和默认值
3. 逐一比较，标记不一致的项
4. 如果有 preset/profile 机制，确认当前活跃的 preset 参数是否与回测运行完全一致

常见陷阱：
- 止盈/止损阈值不同
- 杠杆/仓位大小不同
- 移动平均窗口/指标周期不同
- 手续费/滑点设置不同
- 任何看起来"更保守"但实际偏离了回测优化结果的值

自动化建议：
- 如果项目使用 JSON/dict 形式的回测 suite，可以写脚本逐 key 对比
- 对比时注意浮点精度（用 abs(a-b) < 1e-9 而非 a == b）
- 列表/数组类型的参数也要逐元素比较
```

### 1.2 决策路径逐项对齐

以下是量化交易系统中常见的决策路径类别。根据具体项目选择适用的检查：

| # | 决策路径类别 | 检查要点 |
|---|---|---|
| 1 | 市场状态/Regime检测 | 使用的指标、周期、阈值、分类逻辑、NaN保护 |
| 2 | 状态→参数映射 | 不同市场状态下的杠杆/仓位/风控参数映射 |
| 3 | 波动率处理 | 波动率计算方式、缩放逻辑、数据窗口 |
| 4 | 权益曲线/动量过滤 | 窗口大小、更新频率、阈值、启停逻辑 |
| 5 | 综合参数计算 | 多因子组合公式、最小/最大值限制 |
| 6 | 标的选择/过滤 | 选择指标公式、数据周期、排序方式、数量 |
| 7 | 选择/再平衡频率 | 触发间隔、冷却时间 |
| 8 | 执行顺序 | 平仓→调仓→开仓的处理顺序是否一致 |
| 9 | 止盈逻辑 | 触发条件、使用的PnL计算方式、阈值 |
| 10 | 移动止盈/Trailing | 激活条件、回调值、不同档位的阈值 |
| 11 | 止损逻辑 | 计算方式、触发阈值、对比基准 |
| 12 | 加仓/DCA逻辑 | 触发条件、加仓大小、层数上限 |
| 13 | 减仓逻辑 | 触发条件、减仓比例 |
| 14 | 信号/因子增强 | 因子名称、阈值、组合逻辑（AND/OR） |
| 15 | 仓位大小/权重计算 | 加权方式(等权/风险平价/信号加权)、缩放因子、自适应调整 |
| 16 | 风险敞口检查 | 总敞口计算方式、上限 |
| 17 | PnL模型 | 持仓PnL、平仓PnL、风控PnL是否使用同一模型 |
| 18 | 手续费模型 | 费率值、maker/taker区分、单边/双边、来源 |
| 19 | 资金费率 | 是否纳入成本计算（合约类策略） |
| 20 | 滑点模型 | 是否模拟、模拟方式 |

**注意**：不是所有项目都包含上述全部路径。审计时应先梳理出当前项目实际包含的决策路径，然后逐一对照。如果项目有上表未覆盖的独特逻辑，也要纳入检查。

**结合维度零的结果**：如果维度零发现了缺失模块，在这里对相应决策路径标记为❌，并详细说明回测中的实现位置和功能，以便后续移植。

### 1.3 数据需求一致性

检查实盘获取的数据量是否满足所有下游计算的需求：

```
方法：
1. 从下游反推：列出所有需要历史数据的计算（均线、波动率、指标等）
2. 找到每个计算需要的最小数据量
3. 检查实盘fetch的数据量是否 >= max(所有需求) + buffer
4. 特别检查：每个启用模块的 lookback 窗口是否都被纳入了 fetch 计算

常见陷阱：
- fetch的K线数量不够计算长周期均线（如取250根但需要720根）
- 标的选择和信号计算使用不同的数据窗口
- 回测天然有完整历史数据，但实盘需要主动fetch足够多
- 新增模块的 lookback 窗口未纳入 fetch 计算（被其他更大窗口隐式覆盖≠安全）
```

### 1.4 策略部署缺口检测（Strategy Deployment Gap）🔴 高优先级

**血的教训（2026-04-10 真实案例）：** R4 walk-forward LogReg 信号引擎在 Alpha Lab 中
完成了 21 轮实验验证（WR 57.6%, CAGR >>1000%），代码已合并到仓库（r4_signal_engine.py、
contrarian_filter.py 都在 src/factors/ 下），但 bot.py 的信号生成流程仍在调用旧的
V20 generate_v20_signal()（CAGR 仅 217%）。结果：实盘持续亏损数周，所有人都在查
执行层面的 bug（手续费、fill rate、滑点），没有人想过"我们根本没有在跑那个好策略"。

**为什么这个问题极难发现：**
- **锚定效应**：R4 代码已合并，心理上认为"已经部署了"
- **沉没成本**：已经花大量时间在执行层面排查，不愿承认方向错了
- **局部视角**：每次 review 只看本次改动的 diff，不会主动检查"仓库里有没有未上线的好策略"
- **研发脱节**：Alpha Lab 的输出（config JSON + 独立模块）和实盘的输入（bot.py 信号流）之间没有自动化的桥接检查

```
自动化检测方法（5 步扫描）：

Step 1 — 扫描部署清单中的未完成项：
  grep -rn "TODO.*wire\|TODO.*deploy\|TODO.*switch\|TODO.*port\|TODO.*integrate" config/ docs/
  → 如果 research config 的 deployment_checklist 有未勾选的 P0 项，立即标红

Step 2 — 扫描仓库中"存在但未被调用"的信号引擎：
  # 找到所有 *_signal_engine.py 或 *_engine.py
  # 检查它们是否被 bot.py / main.py import 和实例化
  grep -rn "import.*SignalEngine\|from.*signal_engine" src/bot.py
  → 如果存在信号引擎模块但未被主流程 import，标红

Step 3 — 对比 research config 与 live config 的策略类型：
  # research config 中声明的 signal_engine.type
  # vs bot.py 中实际实例化的信号引擎类
  → 如果不一致，标红并报告差异

Step 4 — 检查 _production_status 字段：
  grep -rn "_production_status\|DEPLOYED\|NOT_DEPLOYED" config/
  → 如果 research config 标记为 validated 但 production_status ≠ DEPLOYED，标红

Step 5 — 实盘亏损时的系统性诊断：
  当用户报告"实盘亏损"时，在检查执行层面（手续费、fill、滑点）之前，
  必须先问：
  (a) 实盘跑的是哪个信号引擎？
  (b) 仓库里最好的信号引擎是哪个？
  (c) 它们是同一个吗？
  → 如果不是同一个，这就是根因，不需要继续查执行层面
```

**发现部署缺口后的行动优先级：**
1. 🔴 立即停止在执行层面的排查（避免沉没成本陷阱）
2. 🔴 评估部署缺口的影响：旧策略 CAGR vs 新策略 CAGR
3. 🟡 制定部署计划：将研究策略接入实盘信号流
4. 🟡 部署后端到端验证：确认实盘输出与研究输出一致
5. 🟢 建立防复发机制：在 CI/CD 或 review 流程中加入 Step 1-4 的自动检查

---

## 维度二：回测引擎真实性

检查回测引擎是否有过于理想化的假设。

### 2.1 成本模型

```
检查项：
- Commission是否合理（参考对应交易所的实际费率）
- 是否区分了maker和taker
- 滑点是否被模拟（尤其对流动性差的标的）
- 是否考虑了funding rate成本（合约类策略，长期持仓）
- 是否考虑了借贷成本（杠杆/做空类策略）
```

### 2.2 执行假设

```
检查项：
- 是否假设了完美成交（用close price而非模拟spread/slippage）
- 加仓/DCA是否假设了即时成交
- 信号触发后是否假设了立即建仓（实盘可能有延迟）
- 强平/清算逻辑是否反映了交易所的真实机制（详见 2.8 全仓保证金与爆仓模拟）
- 是否假设了无限流动性（大单是否会impact market）
- 限价单是否假设了100%成交
```

### 2.3 数据偏差

```
检查项：
- 是否有幸存者偏差（只用了当前存在的标的回测，忽略了已退市的）
- 是否有前视偏差（用了未来数据做决策）
- 数据是否有足够的样本外验证
- 不同市场周期（牛/熊/震荡）是否都覆盖
- 数据质量：缺失值、异常值、拆分/合并调整
```

### 2.4 PnL计算

```
检查项：
- PnL模型是否自洽（所有路径用同一个模型）
- equity更新是否在正确的时间点
- 是否有数值精度问题（浮点累积误差）
- 最终equity和trade log的PnL之和是否一致
- 杠杆PnL的计算方式是否与交易所一致

⚠️ 回报率类型检查（经验教训 — 真实案例导致 10-30% CAGR 偏差）：
- 组合级 PnL 必须使用 simple returns（算术回报 = pct_change）
- log returns（对数回报 = ln(P1/P0)）不具有线性可加性：
    sum(w_i * log_r_i) ≠ log(sum(w_i * simple_r_i))
- 在高波动市场（加密货币常见 ±10-20% 日涨幅），偏差可达 0.5-2%/天
- 高杠杆（5x+）下偏差被进一步放大
- 诊断：grep "np.log\|log_return\|log(" 找到所有对数回报的使用
  → 如果用于组合 PnL 加权求和 → 🔴 必须改为 pct_change / simple returns

⚠️ Turnover 计算检查（经验教训 — 真实案例导致费用低估 50%）：
- 再平衡策略的 turnover 应为 sum(|weight_changes|)（双边）
- 不应除以 2：每一次 weight 变化都是独立交易，各自产生手续费
  → 卖出 A（-0.5）和买入 B（+0.5）= 两笔交易，turnover 应为 1.0
  → 除以 2 得到 0.5，导致费用和滑点被低估约 50%
- 诊断：grep "/ 2\|÷ 2\|half\|round.trip" 在 turnover 计算附近
  → 如果 turnover 被除以 2 且用于计算 fee/slippage → 🔴 费用低估
```

### 2.5 杠杆与保证金模型（合约策略必查，默认全仓模式）

这是回测引擎中最容易出错、后果最严重的子系统。一个公式写错可以让回测收益
从 -3% 变成 +147%（真实案例），导致你上线一个实际亏损的策略。
回测默认使用全仓 (Cross Margin) 模式，保证金管理与爆仓模拟的完整检查见 2.8 节。

```
检查项：

1. 回测默认使用全仓模式 (Cross Margin)，验证 PnL 公式匹配：
   - 全仓 (Cross)【默认】：PnL = notional × price_change_pct = balance × pos_pct × Δp/p
     → 杠杆设置仅影响保证金分配，不影响 PnL 大小
     → 如果代码中出现 sqrt(leverage) 或 leverage 乘以 PnL，在全仓模式下是 BUG
     → 所有仓位共享账户余额作为保证金池（详见 2.8 节）
   - 逐仓 (Isolated)【需特别标注】：PnL = margin × leverage × price_change_pct
     → 杠杆直接放大收益和亏损，保证金是独立的
     → 如果项目使用逐仓模式，必须在配置和文档中显式声明，不可默认假设

2. 仓位大小计算必须匹配保证金模式：
   - 全仓模式按 notional 下单：notional = balance × position_pct
     → 杠杆不应出现在仓位大小公式中
   - 逐仓模式按 margin 下单：margin = balance × position_pct,
     notional = margin × leverage → 杠杆参与 notional 计算

3. 手续费必须基于 notional 金额计算，不受杠杆 PnL 模型影响：
   - fee = notional × fee_rate（双边 = 开仓 + 平仓各一次）
   - 绝不能用 fee = margin × fee_rate（会低估手续费 leverage 倍）
   - 绝不能让 PnL 放大系数影响 fee 计算（如 fee 没乘 sqrt(lev) 但 PnL 乘了，
     等于间接降低了有效费率）

4. 验证方法 — 有效费率反推：
   effective_fee_bps = median(|fee_per_trade|) / median(notional_per_trade) × 10000
   如果 effective_fee_bps 显著低于交易所公告费率，说明 fee 模型有 bug

5. 验证方法 — 零 alpha 压力测试：
   - 设 commission = 交易所实际费率，关闭所有 alpha 信号（随机入场）
   - 期望结果：total_return ≈ -(commission × trade_count × 2) / capital
   - 如果 total_return 明显偏正 → PnL 模型虚增了收益
   - 如果 total_return 明显偏负 → 手续费被多算了

6. 清算逻辑：
   - 全仓模式清算价取决于整个账户余额，不是单个仓位的保证金
   - 回测中是否模拟了清算？如果没有，至少要检查是否存在 equity < 0 的 bar
   - Wick（影线）穿透：bar 内最低价可能触发清算但 close 价没有
     → 如果只用 close 做判断，会遗漏 wick 触发的强平

典型 bug 模式（真实案例）：

  # BUG: 全仓模式下用了 sqrt(leverage) 放大 PnL
  pnl_leverage = sqrt(cfg.leverage)  # 3x → 1.73x
  pnl_dollar = notional * price_change * pnl_leverage  # 虚增 73%

  # 但手续费没有乘以 pnl_leverage
  fee = notional * commission_rate  # 正确的 notional 基准

  # 结果：PnL 被放大 1.73x，fee 没变
  # 有效费率 = commission_rate / pnl_leverage ≈ 4bps / 1.73 ≈ 2.3bps
  # 低于任何交易所的最低档！
  # 这个 bug 让一个实际 PF=0.99 的策略看起来 PF=1.19, CAGR +147%

诊断 checklist：
□ grep "sqrt.*lev\|leverage.*pnl\|pnl.*leverage" — 找到杠杆参与 PnL 计算的位置
□ 确认 PnL 公式与交易所 API 文档一致
□ 计算有效费率并与交易所公告费率比较
□ 跑一组 commission sweep（1bps → 5bps），观察 CAGR 变化曲线
   → 如果 1bps 差异导致 CAGR 变化 >50%，说明策略真实 alpha ≈ 0
□ 检查实盘 bot 是否也有同样的 PnL 公式（如果有，修回测也要同步修实盘）
```

### 2.6 手续费复利效应

手续费的影响不是线性的，而是通过 equity 复利放大。每笔交易少扣 $0.69 的 fee，
经过 5000 笔交易的复利，最终 equity 差异可达 $370K（真实案例，$10K 初始资金）。

```
检查项：
- 是否做了 commission sensitivity analysis（不同费率下的 CAGR/PF）
- 费率从 1bps 到 5bps 的 CAGR 变化是否平滑：
  → 跳崖式下降（如 2bps: +50%, 3bps: -10%）说明策略 alpha 极薄，
    完全依赖 fee 假设，实盘风险极高
- 在交易所实际费率（通常 taker 3-5bps）下，策略是否仍然正 CAGR
- maker vs taker 费率区分：
  → 回测假设 100% maker（更低费率）但实盘多数成交是 taker
  → 应按 taker 费率做主要测试，maker 费率只作为乐观边界

Profit Factor (PF) 解读：
- PF > 1.05 → 可能有 alpha（但仍需确认 fee 假设）
- PF 1.00-1.05 → 灰色地带，alpha 可能完全来自 fee 假设的差异
- PF < 1.00 → 策略在当前 fee 假设下亏损，必须改进信号质量
```

### 2.7 因子/信号有效性

因子驱动策略（factor-driven）中，因子的设计决定了策略的命运。
一组"看起来合理"的因子可能完全无法产生 alpha。

```
检查项：

1. 因子方向性 vs 条件性：
   - 方向性因子：预测价格上涨/下跌（如 momentum, trend quality,
     mean-reversion bounce）
     → 对 long-only 策略必须使用方向性因子
   - 条件性因子：检测市场状态但不预测方向（如 volume anomaly,
     vol compression, wick rejection）
     → 这些因子适合做 regime filter 或 sizing 调整，但不能作为入场信号
   - 诊断：如果所有因子组合下 CAGR 都接近 0 或为负，首先检查因子是否有方向性

2. 因子正交性：
   - 高度相关的因子（如 7d momentum 和 14d momentum）不增加信息量
   - 理想的因子集应覆盖不同的 alpha 来源：
     → 动量类（momentum, acceleration）
     → 相对强度类（BTC-relative, sector-relative）
     → 微观结构类（funding rate, volume breakout）
     → 均值回归类（crash bounce, oversold recovery）

3. Score threshold 对 trade count 和质量的影响：
   - threshold 太低 → 大量低质量交易，被手续费吞噬 alpha
   - threshold 太高 → 交易太少，equity curve 不平滑
   - 必须做 threshold sweep 并画 CAGR vs threshold 曲线
   - 典型现象：trade count 减半但 CAGR 翻数倍（甜蜜点存在）

4. 因子在不同市场环境下的表现：
   - 牛市因子（momentum）在熊市可能反转
   - 均值回归因子在趋势市中可能持续亏损
   - 检查 per-year 收益分布，如果某年大幅亏损，需分析该年的因子表现
```

### 2.8 全仓模式保证金与爆仓模拟（Cross Margin Liquidation）

全仓模式下，所有仓位共享账户余额作为保证金池。这意味着：
- 一个仓位的浮亏会减少其他仓位的可用保证金
- 一个仓位的极端亏损可能连带清算所有仓位
- 回测必须在**每根 bar** 上追踪全账户保证金状态

这是回测引擎中最容易"假设掉"的子系统。实盘中交易所每秒都在做这个计算，
如果回测跳过了它，等于在一个"永远不会爆仓"的平行宇宙中测试策略。

```
检查项：

1. 核心公式验证（全仓模式）：

   账户权益 (Equity):
     equity = wallet_balance + Σ unrealized_pnl_i

   其中:
     unrealized_pnl_i = position_size_i × (mark_price_i - entry_price_i) × direction_i
     direction: long = +1, short = -1

   维持保证金 (Maintenance Margin):
     maintenance_margin = Σ (|notional_i| × mmr_i)
     其中 mmr_i 是交易所按档位递增的维持保证金率
     （如 Binance USDT-M：notional < $50K 时 mmr=0.4%，
       $50K-$250K 时 mmr=0.5%，依此递增至 50%）
     注意：不同交易所的档位表不同，应从配置中读取而非硬编码

   保证金率 (Margin Ratio):
     margin_ratio = maintenance_margin / equity
     当 margin_ratio >= 100%（即 equity <= maintenance_margin）时触发清算

   清算价近似计算（单仓位简化）:
     long:  liq_price ≈ entry × (1 - (equity - maint_margin) / |notional|)
     short: liq_price ≈ entry × (1 + (equity - maint_margin) / |notional|)

   多仓位场景：清算价不是固定值，而是随所有仓位的 mark price 动态变化

1b. 平台特定保证金规则适配（多交易所项目必查）：

   **核心原则：Margin Sim 的计算规则必须对齐实盘所用交易所的真实规则。**
   不同交易所的全仓保证金算法存在显著差异，不能用一套通用公式"差不多就行"。

   平台差异对照表：

   | 维度 | Binance USDT-M | Hyperliquid | OKX | Bybit |
   |------|----------------|-------------|-----|-------|
   | 阶梯保证金档位 | 按币种独立，6-12档 | 统一 3 档 | 按币种独立，5-8档 | 按币种独立 |
   | MMR 计算 | notional × mmr - cum | 类似但档位阈值不同 | notional × mmr - cum | notional × mmr |
   | 清算触发条件 | equity ≤ maint_margin | account_value ≤ maint_margin | margin_ratio ≥ 100% | margin_ratio ≥ 100% |
   | 清算执行方式 | 逐仓平亏损最大仓位 | 全仓一次清算 | 逐仓减仓至安全 | 逐仓减仓至安全 |
   | Funding 频率 | 每 8h（部分 4h） | 每 1h | 每 8h | 每 8h |
   | 保险基金机制 | 有，穿仓由保险基金覆盖 | 有，Vault 机制 | 有 | 有 |
   | Mark Price | 加权平均 + funding | Oracle 价格 | 加权平均 | 加权平均 |
   | Brackets 数据源 | GET /fapi/v1/leverageBracket | /info endpoint | GET /api/v5/public/position-tiers | GET /v5/market/risk-limit |

   审计 checklist（多平台适配）：

   □ 确认 margin_simulator 加载的阶梯保证金数据来源与实盘交易所一致
     → 不同交易所的 JSON schema 不同，解析器必须适配
     → brackets 数据应定期更新（交易所会调整档位），建议脚本化拉取

   □ 如果项目支持多交易所（如同时跑 Binance 和 Hyperliquid），
     margin_simulator 必须根据当前实盘配置的交易所动态切换规则：
     → 配置中应有 EXCHANGE 或 PLATFORM 参数指定当前交易所
     → margin sim 根据该参数加载对应的 brackets 和 MMR 算法
     → 不允许 hardcode 某一个交易所的规则

   □ Funding rate settlement 频率必须匹配实盘交易所：
     → Binance 大多 8h 但部分合约 4h
     → Hyperliquid 每 1h（差 8 倍！对长持仓策略影响巨大）
     → 如果回测按 8h 扣 funding 但实盘在 1h 频率的交易所，成本模型偏差很大

   □ Mark Price 的计算方式因交易所而异：
     → 有些用 index price + funding premium，有些直接用 oracle price
     → 回测中用 close price 做近似是可接受的，但审计时需标注这个简化

   □ contract_size / contract_multiplier 因交易所和币种而异：
     → Binance USDT-M 合约大多 contract_size = 1.0（直接以币计价）
     → 部分交易所的 inverse 合约（如 BTCUSD）contract_size ≠ 1.0
     → 如果 PnL 计算中用到 contract_size，确认数据来源正确
     → 审计时检查所有 universe 内币种的 contract_size 是否都已验证

   □ 如果项目从交易所 A 迁移到交易所 B，必须：
     a. 更新 leverage brackets 数据文件
     b. 验证 MMR 计算公式是否仍适用（有些交易所没有 cum 字段）
     c. 更新 funding rate settlement 频率
     d. 重新跑回测，对比迁移前后的 margin metrics
     e. 特别注意：小币种在不同交易所的 MMR 差异可能很大

2. 每根 bar 的保证金检查（回测引擎必须实现）：

   for each bar:
     a. 用 bar 的价格更新所有仓位的 unrealized_pnl
     b. 计算 equity = wallet_balance + Σ unrealized_pnl
     c. 计算 maintenance_margin = Σ (|notional| × mmr)
     d. 检查 equity <= maintenance_margin → 触发清算
     e. 同时用 bar 的极端价格做 wick 检查（见第 3 点）

   如果回测只在"生成交易信号"时检查保证金，中间的 bar 可能
   已经触发爆仓但被完全跳过 — 这是最常见的爆仓模拟遗漏

3. 插针 / Wick 模拟（intra-bar liquidation）：

   问题：一根 1h bar 的 close = $100，但 low = $80。
   如果只用 close 做判断，$80 触发的爆仓被完全忽略。
   加密市场的插针是常态（BTC 多次出现 5min 内跌 10%+ 后 V 型反弹），
   不模拟 wick = 严重高估策略生存能力。

   方法一【最低要求】：使用 bar 的极端价格做清算/止损判断
     - Long 仓位：用 low 检查是否触发清算或止损
     - Short 仓位：用 high 检查是否触发清算或止损
     - 如果触发：在清算价（而非 low/high）成交，因为交易所清算引擎
       会尝试在清算价附近成交，不是在最极端价格成交
     - 实现成本：几乎为零，只需在现有判断中加入 high/low 检查
     - 局限：无法正确处理"先触发止盈再触发止损"或反过来的顺序问题

   方法二【推荐】：使用 OHLC 顺序模拟 bar 内价格路径
     - 根据 bar 方向推断价格路径：
       → 阳线（close > open）：open → low → high → close
       → 阴线（close < open）：open → high → low → close
     - 按此路径顺序检查所有触发条件（止盈、止损、清算、加仓）
     - 第一个被触发的条件优先执行，后续条件不再检查
     - 好处：解决了"同一根 bar 内先止盈还是先止损"的二义性
     - 实现成本：中等，需要将价格路径分成 4 个检查点
     - 注意：bar 内路径假设终究是猜测，极端行情下仍可能偏差

   无论哪种方法，必须检查：
   □ 清算/止损判断是否只使用了 close price → 几乎一定是 bug
   □ 是否对 long 用 low、对 short 用 high 做了极端价格检查
   □ 触发清算后的成交价假设是否合理（清算价 ≠ bar 最低价）

4. 爆仓后的处理逻辑：

   全仓模式爆仓 = 所有仓位被清算（但实际交易所有部分清算机制）

   最低实现（推荐用于回测）：
   - 触发清算时：关闭所有仓位
   - equity 设为 0（或扣除清算手续费后的残余）
   - 策略停止交易（回测可配置是否允许"重新注资"继续）
   - 在回测报告中标记清算事件的时间、价格、当时的保证金率

   更精确的实现（可选）：
   - 模拟交易所的部分清算机制：先取消挂单，再逐步减仓
   - 每次减仓后重新计算保证金率，直到恢复健康水平
   - 部分清算对 equity 的影响更小，但实现复杂度更高

   检查回测代码中 equity < 0 的情况：
   → 如果 equity 曾出现负值且没被处理，说明缺少爆仓检查
   → 全仓模式下 equity < 0 理论上不应该出现（交易所在接近 0 时就清算了）

5. 可用余额追踪（Available Balance）：

   available_balance = equity - Σ initial_margin_i
   其中 initial_margin_i = |notional_i| / leverage_i

   这个值决定了能否开新仓：
   - 如果 available_balance < 新仓位的 initial_margin → 开仓应被拒绝
   - 回测中如果忽略这个检查，会出现"幽灵杠杆"效果：
     一个仓位浮亏很大但还没触发清算，回测却继续用全部 equity 开新仓
     → 总敞口远超实际可用保证金，回测结果无法在实盘复制

   检查项：
   □ 回测是否追踪了 available_balance（或等价概念）
   □ 开仓前是否检查 available_balance 足够覆盖 initial_margin
   □ 多仓位同时开仓时是否有总敞口限制
   □ 浮亏是否正确地减少了 available_balance

6. Funding Rate（资金费率）模拟：

   全仓模式下 funding rate 直接影响 wallet_balance：
     每个 settlement 周期：
       wallet_balance += position_size × funding_rate × direction
       (正 funding rate + long = 付费；负 funding rate + long = 收费)

   关键注意事项：

   a. Settlement 频率因交易所和交易对而异：
      - 大多数 Binance USDT-M 合约：每 8h（00:00/08:00/16:00 UTC）
      - 部分 Binance 合约：每 4h
      - dYdX：每 1h
      - 不同交易对可能有不同频率，必须从数据中确认而非硬编码

   b. 数据来源：
      - 历史 funding rate 可通过交易所 API 获取
        （如 ccxt 的 fetchFundingRateHistory）
      - 不要使用固定假设值（如"假设每次 0.01%"）— 实际 funding rate
        在极端行情中可能飙升到 0.1%+ 甚至更高
      - 如果无法获取历史数据，至少用该交易对的历史平均值，并在报告中标注

   c. 对长持仓策略（持仓 >24h）影响巨大：
      - 以 8h 频率、每次 0.01% 计算：30 天 ≈ 0.9% of notional
      - 极端行情期间 funding rate 飙升，30 天可能达到 3-5%
      - 这个成本量级和交易手续费相当，不可忽略

   检查项：
   □ 回测是否在每个 funding settlement 周期扣除/添加 funding fee
   □ settlement 频率是否与实际交易对匹配（不是所有合约都是 8h）
   □ funding rate 数据是否为历史实际值
   □ funding fee 基于 notional 计算（正确）而非基于 margin（错误）
   □ funding fee 是否影响了 equity 和后续的保证金率计算

7. ADL（自动减仓）风险提示：

   交易所在对手方爆仓且保险基金不足时，会触发 ADL（Auto-Deleveraging），
   强制减少盈利方的仓位。

   这个机制无法在回测中精确模拟（依赖交易所内部排名算法），但审计时
   需要意识到：
   - 回测中的大幅盈利仓位，在实盘极端行情中可能被 ADL 提前平仓
   - 如果策略依赖"在极端行情中持有大仓位赚取巨额利润"，ADL 风险很高
   - 回测结果在极端行情时段会比实盘乐观
   - 在回测报告中标注：如果某笔交易的盈利超过 X%（如 50%），
     该笔交易的实盘可复制性存疑（ADL 风险）

8. 验证方法 — 极端行情压力测试：

   设计以下测试场景并验证回测引擎的行为：

   a. Flash Crash 测试（插针爆仓）：
      - 构造一根 bar：close 正常，但 low 比 close 低 20%
      - 在 3x 杠杆下开 long，仓位占 equity 的 80%
      - 预期：该 bar 应触发清算（80% × 20% = 16% 亏损 > 可用保证金）
      - 如果回测报告此 bar 无事发生 → 缺少 wick 检查

   b. 多仓位连锁清算测试（全仓共享保证金）：
      - 同时持有 3 个不同标的的 long 仓位，各占 equity 的 30%
      - 其中一个标的暴跌 15%
      - 预期：该仓位浮亏 = 30% × 15% = 4.5% equity，
        如果总维持保证金要求接近剩余 equity → 可能触发全账户清算
      - 如果回测只清算了那一个仓位而保留其他两个 → 可能是逐仓逻辑的 bug

   c. 保证金不足开仓测试（available balance）：
      - equity = $10,000, 已有 $8,000 notional 仓位, leverage = 5x
      - initial_margin = $8,000 / 5 = $1,600
      - available_balance = $10,000 - $1,600 = $8,400
      - 尝试开 $50,000 notional 新仓位（需要 $10,000 initial margin）
      - 预期：开仓应被拒绝或限制大小至 available_balance × leverage
      - 如果回测允许开仓 → 缺少 available_balance 检查

   d. Funding Rate 累积测试：
      - 持仓 30 天，使用历史 funding rate 数据
      - 计算预期 funding 成本并与回测结果对比
      - 预期：两者误差 < 1%
      - 如果回测完全没有 funding 成本 → 缺少 funding 模拟

诊断 checklist（汇总）：
□ grep "margin_ratio\|maintenance_margin\|liquidat\|margin_rate" — 找到保证金代码
□ grep "available.*balance\|free.*margin\|can_open" — 找到可用余额检查
□ grep "funding.*rate\|funding.*fee\|settlement" — 找到 funding rate 代码
□ 确认每根 bar 都有保证金检查，而非只在交易信号时检查
□ 确认清算判断使用了 high/low 而非只用 close
□ 确认 equity < 0 在回测结果中从未出现（出现 = 缺少爆仓检查）
□ 确认多仓位场景下 equity 是共享计算的（全仓模式核心）
□ 确认开仓时有 available_balance 检查
□ 如果策略持仓超过一个 funding 周期，确认 funding rate 被纳入计算
□ 跑一次极端行情压力测试（上述 a-d），验证引擎在极端条件下的行为
```

### 2.9 回测日志输出与可分析性

回测日志是策略迭代的基础设施。如果日志不够完整，你无法回答"这笔为什么亏了"；
如果日志管理混乱，你无法回答"上周那个版本比现在好在哪"。

回测日志和实盘运行日志（3.5 节）是两个完全不同的东西：
- 实盘日志：用于**监控和排障**，记录运行时事件（下单/报错/重连）
- 回测日志：用于**策略分析和版本对比**，记录每笔交易的决策过程和结果

```
检查项：

1. Trade Log（交易记录）— 最核心的输出，必须是结构化格式（CSV/JSON）：

   必须字段（缺任何一个 = 无法做基本分析）：
   - trade_id: 唯一标识
   - symbol: 交易标的
   - direction: long / short
   - entry_time / exit_time: 开仓和平仓时间
   - entry_price / exit_price: 开仓和平仓价格
   - position_size: 仓位大小（notional，不是 margin）
   - pnl_gross: 毛利（不含手续费）
   - fee_total: 手续费总额（开仓 + 平仓 + funding）
   - pnl_net: 净利（= pnl_gross - fee_total）
   - exit_reason: 平仓原因（止盈/止损/清算/信号反转/强制平仓...）

   推荐字段（缺了能跑，但无法做深度归因分析）：
   - entry_signal: 触发开仓的信号或因子得分
   - market_regime: 开仓时的市场状态（如果策略有 regime 检测）
   - score_at_entry: 综合信号评分
   - leverage: 实际使用的杠杆
   - holding_bars: 持仓根数
   - max_favorable / max_adverse: 持仓期间最大浮盈/浮亏
   - funding_fee: 持仓期间累计 funding cost（合约）
   - trailing_activated: 是否触发过移动止盈
   - dca_count: 加仓次数

   验证方法：
   □ Σ pnl_net（所有交易）+ 残余持仓浮盈 ≈ 最终 equity - 初始 equity
     如果对不上 → PnL 模型或日志记录有 bug
   □ 每笔交易的 fee_total / notional × 10000 ≈ 预期费率 (bps)
     如果偏差大 → fee 计算或记录有误
   □ exit_reason 是否有值、是否覆盖了所有平仓路径
     如果存在空值 → 某些平仓路径没有正确标记原因

2. Equity Log（权益曲线时间序列）— 用于画图和计算风险指标：

   每根 bar 一条记录（或至少每个交易周期一条）：
   - timestamp
   - equity: 总权益（wallet_balance + unrealized_pnl）
   - wallet_balance: 已实现权益
   - unrealized_pnl: 未实现浮盈/浮亏
   - drawdown_pct: 当前回撤百分比
   - position_count: 当前持仓数量
   - total_exposure: 总敞口（Σ |notional|）
   - margin_ratio: 保证金率（全仓模式，见 2.8）

   这个日志的分析价值：
   - 画 equity curve 和 drawdown overlay
   - 计算 rolling Sharpe、rolling max drawdown
   - 定位最大回撤的起止时间，结合 trade log 分析原因
   - 观察 margin_ratio 是否曾接近危险区域

3. Decision Log（决策日志）— 最容易被忽略但调试价值最高：

   记录策略在每个决策点"做了什么"以及"为什么没做"：
   - 开仓决策：信号得分、阈值、是否满足入场条件
   - 跳过开仓的原因：信号不够强 / 保证金不足 / 冷却期 / 敞口上限
   - 关仓决策：触发了哪个退出条件
   - 选币决策：哪些标的被选中、哪些被过滤掉、评分排名

   这个日志不需要每根 bar 都记录（太多了），但至少在以下时刻记录：
   - 信号触发但未执行时（记录拒绝原因）
   - 实际开仓/关仓时（记录触发条件和关键参数值）
   - 选币/再平衡时（记录候选列表和最终选择）

   为什么重要：
   - 没有 decision log，你只能看到"发生了什么"，看不到"为什么没发生"
   - 策略优化时最大的盲区是"被过滤掉的好机会"和"不该放过的坏交易"
   - 如果所有被跳过的信号都记录了原因，你能快速判断是阈值太高还是
     保证金限制太紧

4. Run Summary（运行摘要）— 每次回测的"身份证"：

   每次回测运行必须输出一个摘要，包含：

   a. 运行元数据：
      - 运行时间戳
      - 代码版本（git commit hash，如果有）
      - 使用的配置/preset 名称
      - 关键参数快照（至少包含：策略名、标的列表、杠杆、fee rate、
        回测时间范围、初始资金）

   b. 核心绩效指标：
      - Total Return / CAGR
      - Sharpe Ratio / Sortino Ratio
      - Max Drawdown（金额和百分比）
      - Profit Factor
      - Win Rate / 平均盈亏比
      - Total Trades / 平均持仓时长
      - Total Fees / Fee-to-PnL Ratio

   c. 风险指标（全仓模式必须）：
      - 最低 equity 点
      - 最高 margin_ratio（最接近爆仓的时刻）
      - 是否触发过清算
      - 累计 funding cost

   为什么需要运行元数据：
   - 两周后你看到一个日志文件，如果没有配置快照，你不知道它是用什么参数跑的
   - 对比两次回测结果时，先 diff 配置快照，确认差异只来自你想测试的变量

5. 日志文件管理 — 每次运行必须生成独立文件：

   a. 核心原则：每次回测启动 = 一组新的日志文件
      - 绝不 append 到旧文件（无法区分不同运行的结果）
      - 绝不覆盖旧文件（丢失历史对比数据）

   b. 文件命名规范（推荐）：
      {strategy}_{preset}_{YYYYMMDD_HHmmss}/
        ├── trades.csv          # Trade Log
        ├── equity.csv          # Equity Log
        ├── decisions.log       # Decision Log（可选，文本格式也行）
        └── summary.json        # Run Summary（JSON 方便程序读取）

      或用单目录 + 前缀：
        backtest_results/
        ├── 20250325_143022_momentum_v2_trades.csv
        ├── 20250325_143022_momentum_v2_equity.csv
        └── 20250325_143022_momentum_v2_summary.json

      关键：时间戳在最前面或目录名中 → 按文件名排序 = 按时间排序
      推荐包含策略名/preset名 → 不用打开文件就知道是什么配置

   c. 格式选择：
      - Trade Log / Equity Log：CSV（pandas 直接读取，方便分析）
      - Run Summary：JSON（结构化，方便程序对比）
      - Decision Log：CSV 或纯文本（取决于是否需要程序化分析）
      - 不推荐用纯 print 输出 — 无法程序化分析，只能人工看

   d. 旧日志清理策略：
      - 不要自动删除旧日志（你以为不需要，直到某天要回溯对比）
      - 如果磁盘空间有限，可以设一个保留策略（如保留最近 100 次运行）
      - 至少保留每次"配置变更"后的第一次运行结果

6. 可分析性验证 — 日志能回答以下问题吗：

   基本分析（trade log 足够回答）：
   □ 按标的/方向/月份分组的 win rate 和 PnL
   □ 持仓时长 vs PnL 的分布
   □ 最大单笔亏损的完整信息（何时何价入场、为什么出场）
   □ exit_reason 的分布（止盈 vs 止损 vs 清算的比例）

   深度分析（需要推荐字段 + equity log）：
   □ 按 market_regime 分组的策略表现
   □ 信号得分 vs 实际 PnL 的相关性（信号质量评估）
   □ 最大回撤期间发生了哪些交易
   □ 保证金率的时间分布（是否经常接近危险线）

   版本对比（需要 run summary + 一致的文件命名）：
   □ 两次运行的配置 diff
   □ 两个版本的 equity curve 叠加对比
   □ 参数 sweep 多次运行的 CAGR/Sharpe 对比表

   调试分析（需要 decision log）：
   □ "这段时间为什么没有交易"→ 查 decision log 中的拒绝原因
   □ "这笔交易的入场信号是什么"→ 查 trade log 的 entry_signal
   □ "选币为什么没选到 X"→ 查选币决策记录

诊断 checklist：
□ 回测是否输出了结构化的 trade log（CSV/JSON，非纯 print）
□ trade log 是否包含所有必须字段（至少 11 个）
□ trade log 的 Σ pnl_net 是否与最终 equity 变化一致
□ 是否有 equity 时间序列输出（用于画 equity curve）
□ 每次回测运行是否生成独立的新文件（非 append / 非覆盖）
□ 文件命名是否包含时间戳和策略/配置标识
□ 是否有 run summary 包含配置快照和核心指标
□ exit_reason 是否覆盖了所有可能的平仓路径
□ 日志格式是否支持 pandas 直接读取分析
```

### 2.10 数据真实性审计（Data Authenticity）

**核心原则：回测的可信度上限 = 输入数据的真实度。**

回测引擎的数学公式可以完美无缺，但如果输入的费率、funding rate、价格数据本身不真实，
结果就是"在虚假世界里的正确计算"。这个维度专门检查回测使用的**每一项外部数据**
是否来自目标交易所的真实历史记录。

```
为什么这个维度容易被遗漏：

1. "合理的常量"陷阱：开发者用一个"看起来对"的固定值（如 funding rate = 0.01%/8h），
   实际值可能在 -0.375% ~ +0.5% 之间波动，且与市场情绪高度相关
2. "交易所都差不多"陷阱：Binance 的价格和 Hyperliquid 的价格在同一秒可能差 0.5-2%，
   小币种更大；fee 结构、funding 频率、清算规则也完全不同
3. "回测时没这个数据"陷阱：目标交易所上线时间晚（如 HL 2023.11），
   之前的时间段只能用替代数据，但必须在报告中标注而非默认"够用了"

经验法则：如果一个回测的成本参数是 hardcoded 常量而非从历史数据文件读取的时间序列，
那它几乎一定是错的——只是错多错少的问题。
```

#### 2.10.1 价格数据来源审计

```
检查项：

1. 数据来源 vs 目标交易所是否一致：
   □ 回测使用的 OHLCV 数据来自哪个交易所？（检查 data_downloader / data loader 代码）
   □ 实盘将在哪个交易所执行？
   □ 如果不一致（如用 Binance 数据回测但在 Hyperliquid 实盘），需要评估：
     - 主流币（BTC/ETH/SOL）：日频下偏差 <0.1%，通常可接受
     - 中小币种：偏差可达 0.5-2%，尤其在流动性差的时段
     - 回测报告中必须标注"价格数据来源与实盘交易所不同"

2. 时间覆盖的完整性：
   □ 目标交易所何时上线？回测时间范围是否超出了交易所存在的时间段？
   □ 如果目标交易所晚于回测开始时间（如 HL 2023.11 上线但回测从 2022 开始），
     必须在报告中标注哪些时间段使用了替代数据源
   □ 不同数据源之间是否有拼接断点？（价格跳变、成交量突变）

3. 幸存者偏差的数据层面：
   □ 回测标的池是"当前存在的币种"还是"历史上每个时刻实际可交易的币种"？
   □ 如果只用当前存在的币种：已退市/归零的币种被排除 = 幸存者偏差
   □ 做空策略尤其受影响：最好的空头标的（归零币）不在回测池中

4. 数据质量验证：
   □ 是否有明显的异常值？（单根 bar 涨跌 >50%，0 成交量的 bar）
   □ OHLC 一致性：是否满足 low ≤ open,close ≤ high？
   □ 时区是否对齐？（UTC vs 本地时间混用是常见 bug）

诊断方法：
□ grep 数据加载代码中的 exchange/source 标识
□ 对比回测开始时间 vs 目标交易所上线时间
□ 统计每个币种的首条数据时间，识别"中途加入"的币种
```

#### 2.10.2 费率数据真实性

```
检查项：

1. Maker/Taker 费率：
   □ 费率值是 hardcoded 常量还是从交易所配置读取？
   □ 常量值是否与目标交易所当前标准费率一致？
   □ 对于多交易所项目：不同交易所的费率是否正确区分？
   □ 建议：至少用 taker 费率做一组 sensitivity test 作为悲观边界

2. Funding Rate — 🔴 最高优先级检查项：
   □ funding rate 是固定常量还是历史时间序列？
   □ 如果是固定值 → 🔴 这几乎一定需要修复（除非策略不持仓过 funding settlement）
   □ 如果是时间序列：数据来源是否为目标交易所的历史 API？
   □ settlement 频率是否正确？（8h / 4h / 1h — 因交易所和交易对而异）
   □ 是否按币种区分了 funding rate？（不同币种的 funding rate 差异很大）

   为什么固定 funding rate 是严重问题：
   - 牛市中多头拥挤，funding rate 可飙升至 0.1%+/次，远超"平均值"
   - 熊市中空头拥挤，funding rate 转负，空头反而要付费
   - 动量策略天然与 funding 方向相同（牛市做多 = 高 funding 成本），
     固定值会系统性低估成本

   诊断方法：
   □ grep "funding.*rate\|funding.*daily\|funding.*pct" — 找到 funding 参数
   □ 检查该参数是 float 常量还是 pd.Series / Dict
   □ 如果是常量 → 报告为 🔴 High Risk

3. 滑点模型：
   □ 滑点是固定百分比还是基于订单簿/成交量的动态模型？
   □ 固定滑点对于日频限价单策略通常可接受
   □ 但对于 taker 订单或大单，固定滑点可能严重低估
```

#### 2.10.3 保证金规则真实性

```
检查项：

1. 维持保证金率 (MMR)：
   □ MMR 值是否来自目标交易所的 API / 文档？
   □ 是否使用了阶梯保证金（不同 notional 档位不同 MMR）？
   □ 不同币种的 MMR 是否正确区分？（小币种 MMR 远高于主流币）

2. 清算规则：
   □ 清算触发条件是否与目标交易所一致？
   □ 清算手续费 / 罚金是否纳入？（通常 0.5-1.5%）

3. 最大杠杆限制：
   □ 目标交易所对该币种的最大杠杆是多少？
   □ 回测中的杠杆设置是否超过了交易所允许的最大值？

诊断方法：
□ 检查代码中是否有 margin / liquidation 相关的数据文件
□ 如果完全没有保证金模拟 → 至少检查回测中 equity 是否曾接近 0
```

#### 2.10.4 数据真实性审计报告模板

```
每次审计输出以下表格：

| 数据项 | 来源 | 类型 | 目标交易所 | 匹配度 | 风险等级 |
|--------|------|------|-----------|--------|---------|
| OHLCV 价格 | ? | 历史时间序列/其他 | ? | ✅/🟡/🔴 | Low/Med/High/Crit |
| Maker Fee | ? | 固定常量/动态 | ? | ... | ... |
| Taker Fee | ? | 固定常量/动态 | ? | ... | ... |
| Funding Rate | ? | 固定常量/历史序列 | ? | ... | ... |
| 滑点 | ? | 固定/动态 | ? | ... | ... |
| MMR / 清算 | ? | 实现/未实现 | ? | ... | ... |
| 标的池 | ? | 静态/动态 | ? | ... | ... |

风险等级判定标准：
- Critical：缺失该数据可能导致回测结果在实盘中完全不可复制（如无清算模拟）
- High：使用固定值替代波动很大的历史数据（如 funding rate）
- Medium：数据来源不同但量级合理（如不同交易所的价格）
- Low：与真实值完全一致或偏差可忽略

修复前后的 CAGR/Sharpe/MaxDD 变化幅度本身就是重要信息：
→ 变化 <5%：策略 alpha 不依赖该数据假设（好事）
→ 变化 >20%：回测结果严重依赖该假设（红旗）
```

### 2.11 Margin-Ratio 自动减仓机制（Auto-Deleverage Protection）

静态杠杆上限（如 3.05x）只能防御已知历史最差 wick，无法防御未来更大的黑天鹅。
真正的防线是**实时 margin_ratio 监控 + 阈值触发自动减仓**。这是回测引擎和
实盘 bot 都应该具备的能力，但两者的实现方式完全不同。

```
核心概念：

1. Margin Ratio 阈值体系：
   margin_ratio = maintenance_margin / equity
   - margin_ratio < 0.3: 健康
   - margin_ratio 0.3-0.5: 正常偏高
   - margin_ratio 0.5-0.7: 危险区，应开始减仓
   - margin_ratio >= 1.0: 触发交易所清算

2. 两级阈值机制：
   - Soft threshold（如 0.5）：比例减仓（Proportional Deleverage）
     → keep_ratio = target_ratio / current_margin_ratio
     → 所有仓位按 keep_ratio 同比例缩减
     → 目标：把 margin_ratio 降到 target（如 0.3）
   - Hard threshold（如 0.7）：紧急清仓（Emergency Flatten）
     → 取消所有挂单，市价平仓所有仓位
     → 这是最后一道防线，在交易所清算之前主动退出

3. 为什么需要两级：
   - Soft 处理"缓慢恶化"场景（市场持续下跌，MR 逐步升高）
   - Hard 处理"闪崩"场景（几分钟内 MR 飙升，来不及比例减仓）
   - 只有 Hard 没有 Soft = 要么不动要么全平，太粗暴
   - 只有 Soft 没有 Hard = 极端情况下比例减仓来不及，直接被交易所清算

4. ⚠️ Margin-Ratio 减仓 ≠ Drawdown 减仓（这是完全不同的机制）：
   - Drawdown 减仓：基于 equity 从峰值回撤的百分比触发
     → 问题：drawdown 50% 时减仓 = 在最差点卖出，之后市场反弹你仓位小了
     → 经验：drawdown-based deleveraging 几乎一定降低长期 CAGR
   - Margin-Ratio 减仓：基于保证金率（接近爆仓的程度）触发
     → 只在真正面临清算风险时触发，频率极低（历史上可能 0-2 次）
     → 不是为了"控制回撤"，而是为了"防止死亡"
   - 关键区分：不要因为"drawdown 减仓不好"就拒绝所有减仓机制

回测 vs 实盘的实现差异（⚠️ 最容易搞错的地方）：

5. 回测中的 margin-ratio auto-deleverage：

   问题：回测只有日频（或4h/1h）bar，无法获得真实的实时 margin_ratio。
   一根日 bar 的 wick 可能在 1 分钟内完成，close 时 MR 已经恢复正常。

   解决方案：Blended Wick Estimate（混合估计）
     blended_mr = close_mr + blend × (wick_mr - close_mr)
     - blend = 0: 纯 close MR（保守，等于不做 wick 减仓）
     - blend = 0.5: close 和 wick 的中点（近似 10-30s 轮询监控能看到的值）
     - blend = 1.0: 纯 wick MR（激进，假设监控恰好在最差时刻触发）

   ⚠️ 关键发现（真实案例 — 2025-10-10 BTC 闪崩）：
   - Wick MR = 0.929，Close MR = 0.123，Gap = 0.806
   - Wick 和 close 的 MR 差了 6.7 倍！
   - 如果用 blend=1.0（纯 wick），回测触发紧急清仓，equity $2.9M → $550K
   - 但 close 时策略本会恢复到 $3.6M（因为价格 V 型反弹）
   - 这说明日频 bar 的 wick 严重高估了实时监控会看到的压力
   - 其他 876 个交易日：wick MR 全部 < 0.39，只有这一天是极端异常值

   推荐配置：
   - 回测默认 blend = 0（不触发 wick 减仓），靠静态杠杆上限保护
   - 可选 blend = 0.3-0.5 做压力测试，评估减仓机制的影响范围
   - 实盘直接用 API 返回的实时 margin_ratio，不需要 blend

6. 实盘中的 MarginMonitor（实时保证金监控）：

   架构设计：独立的监控循环，与策略主循环解耦
   - 轮询间隔：10-30 秒（HL API 友好，足够捕捉大部分闪崩）
   - 运行方式：daemon 线程（推荐单进程部署）或独立进程（冗余保护）
   - Cooldown：减仓后等待 60 秒再次检查（防止快速行情中连续触发）
   - Kill switch：连续减仓 N 次（如 3 次）后完全停止交易

   必须与策略主循环解耦的原因：
   - 策略可能在等待数据 fetch、因子计算、订单执行
   - 如果 margin 检查嵌在策略循环里，闪崩时可能卡在某一步等不到检查点
   - 独立线程可以在策略忙碌甚至卡住时仍然保护账户
   - 即使策略崩溃，如果 MarginMonitor 在独立进程中，仍能兜底

   实现 checklist：
   □ 轮询 API 获取账户状态（equity, margin_used, positions）
   □ 计算 margin_ratio = total_margin_used / equity
   □ Soft threshold → 比例减仓（cancel all orders → reduce positions proportionally）
   □ Hard threshold → 紧急清仓（cancel all orders → market close all positions）
   □ 每次减仓后发送 Telegram/Discord 通知（包含 MR 值、equity、操作详情）
   □ 减仓事件计数器 + kill switch（超过 N 次触发全面停止）
   □ Cooldown 机制防止在高波动中连续触发
   □ 作为 daemon thread 运行，确保 bot 主循环崩溃时仍能保护
   □ Graceful shutdown 支持（通过 stop() 方法或 running flag）
   □ API 请求失败时的 error handling（不能因为网络抖动就停止监控）

7. Deleverage 的成本模型（回测中）：

   触发减仓时的成本计算：
   - 平仓手续费：closed_notional × taker_fee_rate（紧急减仓一定是 taker）
   - 滑点：closed_notional × slippage（紧急情况下滑点可能比正常更大）
   - PnL 实现：按当前价格结算已关闭仓位的浮盈/浮亏
   - 减仓后恢复成本：下一个 rebalance 重建仓位时会产生额外开仓费用

   回测中减仓后的仓位恢复：
   - 减仓后 next bar 以缩减后的仓位继续（不自动恢复到原始 target）
   - 下一个 rebalance 周期会重新计算 target weights 并重建仓位
   - 如果市场恢复，策略会自然恢复仓位（但会再次产生开仓成本）

检查项汇总：

□ 回测是否实现了 margin-ratio auto-deleverage 机制
  → 至少作为可选功能（config 开关），用于压力测试
□ 如果实现了 blend 参数：
  → 默认值是否为 0 或接近 0（避免 wick 假象误导回测结果）
  → 是否有文档说明 blend 值的含义和推荐范围
□ deleverage 事件是否被记录在回测结果中
  → 触发时间、触发 MR、deleverage 比例、成本
  → 如果从未触发但有极端 wick bar，说明阈值可能太松或 blend 太低
□ 实盘是否有独立的 MarginMonitor 模块
  → 是否与策略主循环解耦（daemon thread 或独立进程）
  → 轮询间隔是否合理（10-30s）
  → 是否有 cooldown、kill switch、通知机制
□ 实盘 MarginMonitor 的阈值是否与回测策略的设计意图对齐
  → 回测中分析过的 soft/hard threshold 应该在实盘中使用
  → 但实盘不需要 blend（直接用 API 返回的实时 MR）
□ 极端场景验证：
  → API 请求失败（网络中断）时 MarginMonitor 如何处理？（应 retry，不 crash）
  → equity <= 0（已被交易所清算）时是否有保护？（应 log + notify + stop）
  → 所有减仓订单都失败（交易所拒绝）时是否有告警？
```

---

## 维度三：实盘运维鲁棒性

### 3.1 冷启动与状态恢复

```
检查项：
- 无state file首次启动：所有变量的初始化是否合理
- 有state file重启恢复：所有字段是否完整恢复
- State file损坏：是否有异常保护，能否降级为冷启动
- State持久化完整性：关键历史数据是否完整保存（非截断）
- 原子写入：是否write-to-temp + rename防止写入中断导致损坏
```

### 3.2 订单执行异常

```
检查项：
- 网络超时/断连：是否有重试机制（指数退避）
- 订单被拒：是否有guard防止立即重复下单
- 部分成交：是否有reconciliation检测并处理
- 限价单竞态：cancel后是否re-fetch确认最终状态
- 下单后崩溃：重启后能否发现交易所上的已执行订单
```

### 3.3 持仓管理异常

```
检查项：
- 幽灵仓位（本地有、交易所无）：如何检测和处理
- 孤儿仓位（交易所有、本地无）：是否自动发现并跟踪
- 数量不匹配：是否有容差检查和自动sync
- 杠杆/保证金设置失败：日志级别是否足够，后续处理是否正确
```

### 3.4 资源与稳定性

```
检查项：
- 资金不足保护：balance ≤ 0时是否跳过开仓
- 连续错误处理：是否有递增退避和最终暂停/告警
- 信号处理：SIGINT/SIGTERM是否graceful shutdown + save state
- 内存管理：队列有上限、日志不无限增长
- 连接恢复：API对象是否能自动重连
- Rate limit：是否遵守交易所API限频
```

### 3.5 日志与可观测性

```
检查项：
- 关键操作是否有结构化日志（下单/成交/取消/异常）
- 每个周期是否输出状态摘要（市场状态、仓位、余额）
- 错误是否有足够上下文用于排查
- 敏感信息（API key/secret）是否被过滤
- 是否有告警机制（异常连续发生时通知）
```

### 3.6 实时保证金监控（MarginMonitor）

```
这不是"锦上添花"的功能，而是合约策略实盘的必要组件。
没有 MarginMonitor 的合约 bot 就像没有安全气囊的赛车 — 大部分时候没区别，
出事的那一天就是全部的区别。

检查项：

1. 是否存在独立的保证金监控模块：
   □ 是否与策略主循环在不同线程/进程中运行
   □ 是否有独立的轮询循环（不依赖策略的 rebalance 周期）
   □ 策略主循环崩溃/挂起时，监控是否仍然运行

2. 监控频率与阈值配置：
   □ 轮询间隔是否可配置（推荐 10-30 秒）
   □ soft/hard threshold 是否可配置（推荐 0.5/0.7）
   □ target_ratio（减仓目标）是否可配置（推荐 0.3）
   □ 这些阈值是否与回测中使用的保证金分析结论一致

3. 减仓执行逻辑：
   □ 减仓前是否先取消所有挂单（防止挂单成交导致仓位增加）
   □ 比例减仓是否按 keep_ratio 同比例缩减所有仓位（不偏向某些仓位）
   □ 紧急清仓是否关闭所有仓位（包括不在策略 target 中的孤儿仓位）
   □ 减仓订单是否用 reduce_only=True（防止方向错误导致仓位增加）

4. 安全机制：
   □ 减仓后是否有 cooldown 期（防止快速行情中连续触发）
   □ 是否有 kill switch（连续减仓 N 次后完全停止交易）
   □ kill switch 触发后是否需要人工干预才能恢复（不应自动重启交易）

5. 通知与日志：
   □ 每次减仓是否发送即时通知（Telegram/Discord/邮件）
   □ 通知内容是否包含关键信息（MR 值、equity、操作详情、减仓次数）
   □ 是否有结构化日志记录所有监控事件（不只是减仓，也包括接近阈值的警告）

6. 容错性：
   □ API 请求失败时是否有重试（不能因为一次超时就停止监控）
   □ equity = 0 或负值时的边界处理（已被清算的情况）
   □ 减仓订单被交易所拒绝时的处理（如仓位已被清算）
```

### 3.7 账户资金流水过滤（Transfer/Deposit/Withdrawal Isolation）

**为什么重要**：实盘 bot 通过 `equity` 变化来计算 PnL。但账户 equity 的变化不全是策略贡献——充值（deposit）会让 equity 暴涨（看起来像盈利），提现（withdrawal）会让 equity 骤降（看起来像亏损）。如果不隔离这些外部资金流，策略的 PnL、Sharpe、MaxDD 全部失真，导致：
- 策略表现评估完全不可信
- 仓位管理基于错误的 equity 做决策（如 position sizing 按 equity 百分比计算）
- 回撤保护/止损逻辑在充值后被错误重置
- 实盘与回测的 PnL 无法对比（回测不存在充提）

**隐蔽场景（容易遗漏的 equity 变化来源）**：
- 合约 funding fee 结算（定期且双向，容易与策略盈亏混淆）
- 空投、返佣、邀请奖励等平台活动
- 跨账户划转（现货→合约、子账户→主账户）
- 手动交易（用户在 bot 之外手动开平仓）
- 清算保险基金返还
- Bonus / Coupon 到账（部分交易所有体验金机制）

**审查清单**：

```
1. Equity 变化来源识别：
   □ 每次 equity 变化是否区分了：策略交易盈亏 vs 外部资金流
   □ 是否存在 "unexplained delta" 检测逻辑：
     delta = new_equity - old_equity
     expected_delta = sum(position_pnl_changes) + sum(realized_pnl) - sum(fees)
     unexplained = delta - expected_delta
     if abs(unexplained) > threshold → 标记为疑似外部资金流
   □ threshold 是否合理设置（推荐：max(1 USDT, 0.1% * equity)，过小会误报）

2. Exchange API 资金流查询：
   □ 是否调用了交易所的 income/transaction history API
     - Binance: GET /fapi/v1/income (type: TRANSFER, DEPOSIT, WITHDRAW, FUNDING_FEE, COMMISSION, INSURANCE_CLEAR, etc.)
     - OKX: GET /api/v5/account/bills (type: 1=transfer, 2=trade, etc.)
     - Bybit: GET /v5/account/transaction-log
   □ 是否对 income type 做了完整分类：
     - 策略相关：REALIZED_PNL, COMMISSION/FEE → 计入 PnL
     - 外部资金流：TRANSFER, DEPOSIT, WITHDRAW → 不计入 PnL
     - Funding fee：根据策略设计决定（如策略本身利用 funding rate → 计入；否则单独记录）
     - 其他：INSURANCE_CLEAR, AIRDROP, REBATE, BONUS → 不计入 PnL，单独记录
   □ API 调用频率是否足够（至少每次 equity 快照时同步查询）
   □ 是否处理了 API 分页（income history 可能很长）

3. Adjusted Equity 跟踪：
   □ 是否维护了 cumulative_transfers 变量：
     cumulative_transfers += deposit_amount  （充值累加）
     cumulative_transfers -= withdrawal_amount  （提现累减）
   □ 策略使用的 equity 是否为 adjusted_equity：
     adjusted_equity = raw_equity - cumulative_transfers
   □ 所有下游计算是否基于 adjusted_equity：
     - PnL 计算：pnl = adjusted_equity - initial_equity
     - 收益率：return = adjusted_equity / initial_equity - 1
     - Drawdown：基于 adjusted_equity 的 peak 计算
     - Position sizing：基于 adjusted_equity 计算仓位大小
   □ initial_equity 是否正确记录（首次启动时的 equity，不含后续充提）

4. 状态持久化（与维度四联动）：
   □ cumulative_transfers 是否持久化到 state file
   □ transfer_history（每笔充提记录）是否持久化
   □ 重启后是否正确恢复 adjusted_equity

5. 日志与告警：
   □ 检测到外部资金流时是否记录详细日志（时间、金额、类型、来源）
   □ unexplained_delta 超过较大阈值时是否发送告警
     （可能意味着：被盗、API key 泄露、有人手动操作了账户）
   □ 定期报告中是否区分展示：策略 PnL vs 外部资金流 vs 总 equity 变化
```

**参考实现（EquityTracker 伪代码）**：

```python
class EquityTracker:
    def __init__(self, initial_equity: float):
        self.initial_equity = initial_equity
        self.cumulative_transfers = 0.0  # 累计外部资金流
        self.transfer_history = []       # 每笔记录
        self.last_income_timestamp = 0   # API 增量查询游标

    def sync_transfers(self, exchange_client):
        """从交易所 API 同步资金流水"""
        incomes = exchange_client.get_income_history(
            start_time=self.last_income_timestamp,
            income_types=["TRANSFER", "DEPOSIT", "WITHDRAW",
                         "INSURANCE_CLEAR", "AIRDROP", "REBATE"]
        )
        for inc in incomes:
            self.cumulative_transfers += inc.amount  # deposit>0, withdraw<0
            self.transfer_history.append(inc)
            self.last_income_timestamp = max(self.last_income_timestamp, inc.timestamp)

    def get_adjusted_equity(self, raw_equity: float) -> float:
        """返回排除外部资金流后的策略净值"""
        return raw_equity - self.cumulative_transfers

    def detect_unexplained_delta(self, old_equity, new_equity,
                                  position_pnl_delta, fees):
        """检测不可解释的 equity 变化"""
        expected_delta = position_pnl_delta - fees
        actual_delta = new_equity - old_equity
        unexplained = actual_delta - expected_delta
        threshold = max(1.0, 0.001 * old_equity)
        if abs(unexplained) > threshold:
            logger.warning(f"Unexplained equity delta: {unexplained:.2f} USDT")
            return unexplained
        return 0.0
```

**回测中的考量**：
- 标准回测（固定初始资金）：不存在充提问题，无需处理
- DCA 策略回测（定期加仓）：需要使用 MWRR（Modified Dietz）或 TWRR（时间加权收益率）而非简单的 `final/initial - 1`
  - TWRR = ∏(1 + r_i) - 1，其中 r_i 是每个子周期（两次资金流之间）的收益率
  - MWRR = (final_equity - initial_equity - sum(cashflows)) / (initial_equity + sum(w_i * cf_i))
  - 如果回测引擎支持 DCA 但只用简单收益率 → **严重 bug**，标记为 🔴
- 实盘-回测对比时：实盘必须用 adjusted_equity，否则对比无意义

### 3.8 实盘日志体系（Performance-Analysis-Ready Logging）

**为什么重要**：实盘 bot 的日志不只是用来排错的——它是事后分析策略表现的唯一数据源。如果日志不完整、格式混乱、或者多次启动的记录混在一起，你根本无法回答以下关键问题：
- 这个版本比上个版本好在哪？差在哪？
- 那笔亏损交易当时的决策依据是什么？信号分数是多少？
- 为什么那段时间一笔交易都没有？是没信号，还是被风控拦截了？
- 策略从第几天开始表现衰减？是市场环境变了还是代码改了？

**核心原则：每次启动 = 一个独立的 session，对应独立的日志文件。**

**审查清单**：

```
1. 日志文件隔离（每次启动独立文件）：
   □ 每次启动是否创建新的日志文件（而非 append 到旧文件）
   □ 文件名是否包含足够的辨识信息：
     推荐格式：{strategy}_{version}_{YYYYMMDD_HHmmss}_{session_id}.jsonl
     示例：momentum_v2.3.1_20260401_143022_a1b2c3.jsonl
     反例：bot.log、output.txt、latest.log（无法区分版本和时间）
   □ 是否避免了 log rotation 把同一个 session 拆到多个文件
     （rotation 只应在 session 之间生效，不应在 session 内部切割）
   □ 是否有 symlink 指向最新的 session 日志（方便 tail -f 实时查看）
     示例：latest.log -> momentum_v2.3.1_20260401_143022_a1b2c3.jsonl

2. Session 元数据（启动时必须记录）：
   □ 启动时间（UTC，毫秒精度）
   □ 策略版本标识（git commit hash 或 version tag）
   □ 完整的配置快照（config dump，含所有参数值）
     - 不只是用户修改的参数，也包含所有 default 值
     - 需要能从日志独立还原"这次运行用了什么配置"
   □ 运行环境信息（Python 版本、关键依赖版本、OS、hostname）
   □ 交易所连接信息（exchange, market_type, 但不包含 API key）
   □ 初始账户状态（equity, positions, available_balance）
   □ 上次 session 的结束原因（graceful shutdown / crash / kill switch / manual stop）

3. 交易决策日志（每个 rebalance 周期必须记录）：
   □ 是否记录了每笔实际执行的交易：
     - 标的、方向、数量、目标价、实际成交价、滑点
     - 手续费（预估 vs 实际）
     - 下单方式（limit/market）、是否 reduce_only
     - 从信号产生到成交的延迟（latency）
   □ 是否记录了"决定不交易"的原因（这比交易记录更重要！）：
     - 信号分数低于阈值 → 记录分数值和阈值
     - 冷却期未过 → 记录剩余冷却时间
     - 保证金不足 → 记录 available_balance 和需要的 margin
     - 风控拦截 → 记录触发的风控规则
     - Regime filter → 记录当前 regime 和对应的 leverage 设置
     示例：{"decision": "skip", "symbol": "ETH", "reason": "score_below_threshold",
            "score": 0.42, "threshold": 0.50, "next_check": "2026-04-01T15:00:00Z"}
   □ 每个周期的完整决策上下文：
     - 所有候选标的的因子得分（不只是最终选中的）
     - 当前 regime 判定及依据
     - 仓位权重计算中间值
     - 目标仓位 vs 当前仓位 vs 实际执行的调整

4. 定期快照（固定间隔的状态记录）：
   □ 是否有固定间隔（推荐每 1-5 分钟）的 equity 快照
   □ 快照是否包含：
     - 总 equity（raw 和 adjusted）
     - 各仓位的 unrealized PnL
     - margin_ratio
     - 当前 drawdown（from peak）
     - 累计已实现 PnL（本 session 内）
   □ 是否有每日 summary（每天固定时间输出当日汇总）：
     - 当日交易次数、胜率、总 PnL
     - 当日最大回撤
     - 当日手续费总额
     - 当日 funding fee 收支

5. 异常与风控事件日志：
   □ API 错误（含完整 response body，不只是 status code）
   □ 订单被拒绝（原因、当时的账户状态）
   □ MarginMonitor 触发（MR 值、动作、减仓详情）
   □ Kill switch 触发（连续减仓次数、触发时的完整状态）
   □ 未预期的 equity 变化（unexplained_delta，与 3.7 联动）
   □ 数据异常（K 线缺失、价格跳变超过阈值）
   □ 连接断开/重连事件

6. 关机日志（session 结束时必须记录）：
   □ 关机原因分类：
     - GRACEFUL: 用户手动停止或计划内维护
     - CRASH: 未捕获异常（含完整 traceback）
     - KILL_SWITCH: 风控触发的自动停止
     - OOM: 内存不足
     - SIGNAL: 收到 SIGTERM/SIGINT
   □ 关机时的最终状态快照（与启动时相同格式，方便对比）
   □ Session 汇总统计：
     - 运行时长
     - 总交易次数、胜率
     - 总 PnL（绝对值 + 百分比）
     - 最大回撤
     - 总手续费
     - 发生的异常事件数量

7. 日志格式与可查询性：
   □ 格式是否为结构化格式（强烈推荐 JSON Lines / .jsonl）
     - 反模式：纯文本 print()、Python logging 的默认 format
     - 原因：结构化日志可以用 jq/pandas 直接分析，纯文本需要正则解析
   □ 每条日志是否包含统一的基础字段：
     {"ts": "2026-04-01T14:30:22.456Z", "level": "INFO",
      "session_id": "a1b2c3", "event": "trade_executed", ...}
   □ 时间戳是否统一为 UTC（避免时区混乱）
   □ 数值精度是否足够（价格至少 8 位小数，数量至少 6 位）
   □ 是否避免了在日志中记录敏感信息（API key, secret, passphrase）
```

**参考实现（SessionLogger 伪代码）**：

```python
import json
import os
from datetime import datetime, timezone

class SessionLogger:
    def __init__(self, strategy_name: str, version: str, log_dir: str = "./logs"):
        self.session_id = os.urandom(4).hex()
        self.start_time = datetime.now(timezone.utc)
        ts = self.start_time.strftime("%Y%m%d_%H%M%S")
        self.filename = f"{strategy_name}_{version}_{ts}_{self.session_id}.jsonl"
        self.filepath = os.path.join(log_dir, self.filename)
        os.makedirs(log_dir, exist_ok=True)
        self._file = open(self.filepath, "a")

        # symlink latest.log → 当前 session 文件
        latest = os.path.join(log_dir, "latest.log")
        if os.path.islink(latest):
            os.unlink(latest)
        os.symlink(self.filename, latest)

        # 统计计数器
        self.stats = {"trades": 0, "skips": 0, "errors": 0,
                      "total_pnl": 0.0, "total_fees": 0.0}

    def log(self, event: str, level: str = "INFO", **data):
        record = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "level": level,
            "session_id": self.session_id,
            "event": event,
            **data
        }
        self._file.write(json.dumps(record, default=str) + "\n")
        self._file.flush()  # 实盘日志必须立即刷盘，crash 时不丢数据

    def log_startup(self, config: dict, git_hash: str,
                    initial_equity: float, positions: list):
        self.log("session_start",
                 config=config,
                 git_hash=git_hash,
                 initial_equity=initial_equity,
                 positions=positions,
                 python_version=sys.version,
                 pid=os.getpid())

    def log_trade(self, symbol, side, qty, target_price, fill_price,
                  fee, order_type, latency_ms, reason):
        slippage_bps = abs(fill_price - target_price) / target_price * 10000
        self.log("trade_executed",
                 symbol=symbol, side=side, qty=qty,
                 target_price=target_price, fill_price=fill_price,
                 slippage_bps=round(slippage_bps, 2),
                 fee=fee, order_type=order_type,
                 latency_ms=latency_ms, reason=reason)
        self.stats["trades"] += 1
        self.stats["total_fees"] += fee

    def log_skip(self, symbol, reason, **context):
        """记录"决定不交易"— 这条比 trade 更重要"""
        self.log("trade_skipped", symbol=symbol,
                 reason=reason, **context)
        self.stats["skips"] += 1

    def log_equity_snapshot(self, raw_equity, adjusted_equity,
                            positions_pnl, margin_ratio, drawdown_pct):
        self.log("equity_snapshot",
                 raw_equity=raw_equity,
                 adjusted_equity=adjusted_equity,
                 positions_pnl=positions_pnl,
                 margin_ratio=margin_ratio,
                 drawdown_pct=drawdown_pct)

    def log_shutdown(self, reason: str, final_equity: float,
                     error: str = None):
        self.log("session_end",
                 reason=reason,
                 final_equity=final_equity,
                 duration_seconds=(datetime.now(timezone.utc)
                                   - self.start_time).total_seconds(),
                 stats=self.stats,
                 error=error)
        self._file.close()
```

**日志分析场景示例**（验证日志是否支撑这些查询）：

```bash
# 1. 某个 session 的交易统计
cat session_xxx.jsonl | jq 'select(.event=="trade_executed")' | jq -s 'length'

# 2. 为什么某段时间没有交易？
cat session_xxx.jsonl | jq 'select(.event=="trade_skipped" and .ts >= "2026-04-01" and .ts < "2026-04-02")'

# 3. 对比两个版本的胜率
cat v2.3_*.jsonl | jq 'select(.event=="session_end") | .stats'
cat v2.4_*.jsonl | jq 'select(.event=="session_end") | .stats'

# 4. 滑点分析
cat session_xxx.jsonl | jq 'select(.event=="trade_executed") | .slippage_bps' | \
  jq -s 'add/length'  # 平均滑点

# 5. 每日 equity 曲线（pandas 友好）
import pandas as pd
df = pd.read_json("session_xxx.jsonl", lines=True)
equity = df[df.event == "equity_snapshot"][["ts", "adjusted_equity"]]
```

**常见反模式**：

| 反模式 | 后果 | 正确做法 |
|--------|------|----------|
| 所有 session 写同一个 `bot.log` | 无法区分版本表现 | 每次启动新文件 |
| 只 log 交易，不 log 跳过原因 | "为什么没交易"无法回答 | `trade_skipped` 事件 |
| 用 `print()` 而非结构化日志 | 无法用程序分析 | JSON Lines |
| 不记录启动时的 config | 事后无法还原"当时的参数" | startup 事件含完整 config |
| 不记录关机原因 | 不知道 session 是正常结束还是崩了 | shutdown 事件含 reason |
| 日志中记录 API key | 安全泄露 | 脱敏处理 |
| equity 快照间隔不固定 | 画出的曲线时间轴不均匀 | 固定间隔（如每 60 秒） |
| 不 flush | crash 时丢失最后几分钟的日志 | 每条 flush 或定期 flush |
| log rotation 在 session 内切割 | 同一次运行的日志散布多个文件 | rotation 只在 session 边界 |

**与回测日志的对齐**：
- 回测引擎的 trade log 格式应与实盘日志的 `trade_executed` 事件使用相同 schema
- 这样同一套分析脚本可以同时分析回测和实盘结果
- 如果回测日志和实盘日志格式不一致 → 标记为 🟡，建议统一

### 3.9 交易对下架防御（Delisting Defense）

**问题的本质**：交易所下架交易对时，通常的时间线是：

```
[公告日]          [最后交易日前 ~48h]     [最后交易日]       [强制结算]
   │                    │                    │                │
   │  ← 7-30 天提前期 → │ ← 流动性枯竭期 →  │                │
   │                    │                    │                │
   ✅ 最佳退出窗口       🟡 勉强能退出        🔴 极差滑点      ❌ 交易所强平
   （流动性正常,        （滑点开始增大,       （撮合可能失败）   （被动接受价格）
    可以从容平仓）       但还能成交）
```

**关键认知**：等到 API 中 `symbol.status` 变成 SETTLING/PRE_DELIVERING 的时候，
你已经在"流动性枯竭期"甚至更晚了——这时候做什么都是在被动应对。**真正的防御窗口
是公告发出的那一刻**，此时距离下架还有 7-30 天，流动性完全正常，可以从容退出。

因此，防御架构必须是**三层纵深**，按时间顺序：

```
第一层：公告监控 + LLM 解析  →  最早感知（7-30 天提前量）→ 最高价值
第二层：API 状态 + 异常信号  →  中等感知（数小时-数天）    → 安全网
第三层：订单被拒 / 异常处理  →  最晚感知（已经在下架中）   → 最后防线
```

**审查清单**：

```
════════════════════════════════════════════════════════════════
第一层：公告监控 + LLM 智能解析（核心防线，最有价值）
════════════════════════════════════════════════════════════════

这是整个防御体系中投入产出比最高的一层。提前 7-30 天知道下架，
意味着你可以在流动性完全正常的市场中从容退出，零额外成本。

1. 公告数据源接入（每个在用的交易所都必须有）：
   □ 是否有定期抓取交易所公告的机制
   □ 每个交易所是否都有对应的公告源（不能只覆盖 Binance 而遗漏 Hyperliquid）

     数据源参考（按交易所）：

     Binance（有结构化 API，最容易接入）：
       · 公告页 API: https://www.binance.com/bapi/composite/v1/public/cms/article/list/query
         参数: type=1, catalogId=48 (期货公告), pageSize=20
       · 下架专题页: https://www.binance.com/en/support/announcement/delisting
       · 推荐频率: 每 6 小时（公告提前 7-30 天，6h 延迟完全可接受）

     Hyperliquid（无公告 API，需监听社交渠道）：
       · 官方 Discord: #announcements 频道
         → 用 Discord Bot 监听，消息通过 webhook 推送到监控服务
       · 官方 Twitter/X: @HyperliquidX
         → 可用 Twitter API v2 filtered stream 或定时拉取
       · 备选: 关注 Hyperliquid 的 Medium/Blog
       · 推荐频率: Discord webhook 实时推送，Twitter 每 2 小时拉取
       · ⚠️ Hyperliquid 下架较少但一旦发生没有结构化提前通知，
         社交渠道是唯一来源，不可跳过

     OKX（未来扩展）：
       · API: https://www.okx.com/api/v5/support/announcements
       · 推荐频率: 每 6 小时

     Bybit（未来扩展）：
       · API: https://api.bybit.com/v5/announcements
       · 推荐频率: 每 6 小时

     通用原则（新增交易所时的检查项）：
       · 该交易所是否有结构化公告 API？→ 有则直接调用
       · 如果没有 → 是否有 RSS / Discord / Twitter 可监听？
       · 完全没有公告渠道 → 🔴 标记为高风险，需人工定期巡查

   □ 公告抓取是否独立于 bot 主循环（bot 挂了公告监控仍在运行）
   □ 抓取失败时是否有告警（不能静默失败，否则防线形同虚设）

2. 两步解析：关键词预过滤 + LLM 精析（成本控制的核心）：

   交易所每天发 5-20 条公告，绝大多数与下架无关（活动、上新币、API 升级等）。
   如果每条都调 LLM，既浪费钱也增加延迟。正确做法是两步：

   Step A — 关键词预过滤（零成本，本地执行）：
   □ 是否有关键词过滤层，只将"疑似相关"公告送进 LLM
   □ 关键词列表是否覆盖中英文和各种表述：

     DELIST_KEYWORDS = [
         # 英文
         "delist", "delisting", "remove", "removal",
         "halt", "suspend", "cease trading",
         "last day of trading", "settle", "settlement",
         "contract migration", "contract swap",
         "margin tier", "maintenance margin",
         "monitoring tag",
         # 中文
         "下架", "摘牌", "停止交易", "暂停交易",
         "合约迁移", "保证金调整",
     ]

   □ 过滤逻辑：title + body 中出现任一关键词 → 送 LLM
     大约 95% 的公告会被过滤掉，每天实际调 LLM 0-2 次

   Step B — LLM 结构化提取（仅对关键词命中的公告）：
   □ 抓取到的公告是否经过 LLM 分析，提取结构化信息
   □ LLM prompt 是否包含当前持仓标的列表（只关心影响我们的公告）
   □ LLM 需要提取的关键字段：
     - affected_symbols: list[str]    — 受影响的交易对
     - event_type: str                — delist / halt / migration / margin_change
     - deadline: datetime             — 最后交易时间
     - action_required: str           — 需要用户做什么
     - urgency: high/medium/low       — 紧急程度
     - raw_summary: str               — 公告摘要
   □ 是否要求 LLM 输出 JSON（方便程序直接解析）
   □ LLM 解析结果是否持久化（防止重复处理同一条公告）
   □ 是否有 fallback：LLM 不确定时标记为 "needs_human_review" 而非忽略

   LLM 模型选择与成本分析：
     这个任务本质是"短文本分类 + 实体提取"，不需要强推理能力。
     推荐 OpenAI gpt-4.1-nano（截至 2025 年最便宜的可用模型）：
       · 输入 $0.10 / 1M tokens，输出 $0.40 / 1M tokens
       · 单次调用：~500 tokens 输入 + ~200 tokens 输出 ≈ $0.00013
       · 月成本估算（有关键词预过滤的情况下）：
         每天 0-2 次 LLM 调用 × 30 天 = 0-60 次/月
         月成本 ≈ $0.008（不到 1 美分）
       · 备选: gpt-4o-mini（$0.15/$0.60），能力更强但贵 50%
       · 不推荐: gpt-4o / claude-sonnet 等大模型 — 大材小用，浪费成本

     ⚠️ 如果没有关键词预过滤，直接每条公告调 LLM：
       每天 10-20 条 × 30 天 = 300-600 次/月
       月成本 ≈ $0.04-$0.08（仍然很便宜，但无谓浪费）

   LLM prompt 参考：
   ```
   你是一个交易所公告分析助手。请分析以下公告，判断是否涉及交易对的
   下架、暂停、迁移、或保证金调整。

   我当前持有的交易对：{current_holdings}

   请以 JSON 格式回答：
   {{
     "affects_holdings": true/false,
     "affected_symbols": ["SYM1", "SYM2"],
     "event_type": "delist/halt/migration/margin_change/other",
     "deadline": "2026-05-01T00:00:00Z 或 null",
     "urgency": "high/medium/low",
     "summary": "一句话摘要"
   }}

   如果不确定某个标的是否受影响，宁可误报也不要漏报。
   如果公告与交易对下架/暂停/迁移完全无关，直接返回 affects_holdings: false。

   公告内容：
   {announcement_text}
   ```

   监控频率汇总（平衡检测速度和资源消耗）：
   ```
   ┌───────────────────┬─────────────┬──────────────────┬────────────┐
   │ 步骤              │ 频率        │ 成本             │ 原因       │
   ├───────────────────┼─────────────┼──────────────────┼────────────┤
   │ 抓取公告(有API)   │ 每 6 小时   │ 免费(HTTP GET)   │ 下架公告提前│
   │ (Binance/OKX等)   │             │                  │ 7-30天，6h │
   │                   │             │                  │ 延迟够了   │
   ├───────────────────┼─────────────┼──────────────────┼────────────┤
   │ 抓取公告(社交渠道)│ 实时推送    │ 免费(webhook)    │ HL 等无API │
   │ (Discord/Twitter) │ 或每 2 小时 │ 或免费(API pull)  │ 的交易所   │
   ├───────────────────┼─────────────┼──────────────────┼────────────┤
   │ 关键词预过滤      │ 每条公告    │ 免费(本地)       │ 过滤95%    │
   │                   │             │                  │ 无关公告   │
   ├───────────────────┼─────────────┼──────────────────┼────────────┤
   │ LLM 精析          │ 仅命中公告  │ ~$0.00013/次     │ 月均<$0.01 │
   │                   │ (0-2次/天)  │ (gpt-4.1-nano)   │            │
   ├───────────────────┼─────────────┼──────────────────┼────────────┤
   │ API 状态检查      │ 每次rebalance│ 免费(交易所API)  │ 兜底第一层 │
   │ (第二层)          │ + 每4小时   │                  │            │
   └───────────────────┴─────────────┴──────────────────┴────────────┘
   整体月成本：< $0.01（几乎免费）
   ```

3. 检测到影响后的自动化响应：
   □ 公告确认影响持仓标的后，是否自动：
     a. 发送即时通知（Telegram/Discord）给用户，包含：
        - 受影响标的和当前仓位
        - 下架截止时间
        - 建议操作和时间窗口
     b. 将该标的加入 "pending_delist" 列表（禁止新开仓）
     c. 如果设置了自动平仓策略 → 在流动性正常时段从容平仓
        （不需要紧急 market order，因为提前期足够长）
   □ 平仓时机选择是否智能（不是立刻 market order，而是：）
     - 距离 deadline > 7 天：只加入黑名单，等下一次 rebalance 自然退出
     - 距离 deadline 3-7 天：在下一个 rebalance 周期主动平仓
     - 距离 deadline < 3 天：立即平仓（limit → timeout → market）
     - 距离 deadline < 24h：紧急 market order

════════════════════════════════════════════════════════════════
第二层：API 状态检查 + 异常信号（安全网）
════════════════════════════════════════════════════════════════

第一层可能漏掉公告（抓取频率不够高、LLM 解析遗漏、非标准渠道发布等）。
第二层是兜底——通过 API 和市场数据异常来发现第一层没捕获的问题。

4. Symbol 状态定期检查：
   □ 是否定期（推荐每次 rebalance 前 + 每 4 小时一次独立检查）
     调用交易所 API 核实持仓标的状态
     - Binance: GET /fapi/v1/exchangeInfo → symbol.status
       · TRADING = 正常
       · PRE_DELIVERING / SETTLING = ⚠️ 已在下架流程中
     - Hyperliquid: POST /info (meta) → universe[]
       · symbol 不在列表中 = 已下架或不存在
   □ 标的池是否从交易所实时获取（而非硬编码列表）
   □ 开仓前是否检查 symbol 状态（快速拒绝不可交易的标的）

5. 异常信号检测（领先指标，比 API 状态更早）：
   □ 是否监控持仓标的的以下异常：
     - Open interest 24h 内下降 > 50%（大量用户在集中平仓）
     - 订单簿深度突然大幅收窄（做市商撤单）
     - Funding rate 连续异常（极端正/负，说明市场严重失衡）
   □ 这些指标不一定意味着下架，但值得发出预警让人工确认

════════════════════════════════════════════════════════════════
第三层：运行时容错（最后防线）
════════════════════════════════════════════════════════════════

如果前两层全部失效，bot 在实际交易中会遇到异常。这一层确保 bot 不会
因为交易对问题而崩溃或进入异常状态。

6. 订单被拒的优雅处理：
   □ 如果开仓/平仓订单被交易所拒绝（原因包含 "not trading" / "symbol not found"
     / "reduce only" 等关键词），是否：
     a. 识别出这是 symbol 问题（不是网络/限速等瞬时问题）
     b. 将该 symbol 加入运行时黑名单
     c. 如果是持仓标的被拒 → 发送紧急告警
     d. 不重试（区别于网络错误的重试逻辑）
   □ bot 主循环是否能在某个标的不可交易的情况下继续运行
     （不能因为一个标的的问题导致整个策略停转）
```

**跨交易所适配建议**：

```python
import hashlib, json, re, requests
from datetime import datetime, timezone
from openai import OpenAI

# ── 关键词预过滤 ──────────────────────────────────────────────
DELIST_KEYWORDS = re.compile(
    r"delist|removal|remove trading|halt|suspend|cease trad|"
    r"last day of trading|settl|migration|contract swap|"
    r"margin tier|maintenance margin|monitoring tag|"
    r"下架|摘牌|停止交易|暂停交易|合约迁移|保证金调整",
    re.IGNORECASE,
)

def passes_keyword_filter(text: str) -> bool:
    """零成本本地过滤，约 95% 的公告在这里被丢弃"""
    return bool(DELIST_KEYWORDS.search(text))


# ── 公告数据源（每个交易所一个插件）────────────────────────────
class AnnouncementSource:
    """每个交易所实现一个，只需实现 fetch_recent"""
    exchange: str
    def fetch_recent(self, since: datetime) -> list[dict]:
        """返回 [{"title": str, "body": str, "time": datetime}]"""
        ...

class BinanceAnnouncements(AnnouncementSource):
    exchange = "binance"
    def fetch_recent(self, since):
        resp = requests.get(
            "https://www.binance.com/bapi/composite/v1/public/cms/article/list/query",
            params={"type": 1, "catalogId": 48, "pageSize": 20}
        )
        return [{"title": a["title"], "body": a.get("body", ""),
                 "time": parse_time(a["releaseDate"])}
                for a in resp.json()["data"]["articles"]
                if parse_time(a["releaseDate"]) > since]

class HyperliquidAnnouncements(AnnouncementSource):
    """Hyperliquid 无公告 API，通过 Discord webhook 接收推送。
    Discord Bot 将 #announcements 频道的新消息写入本地 JSON 队列文件，
    本类从该文件读取。如果没有 Discord Bot，fallback 到手动检查。"""
    exchange = "hyperliquid"
    def __init__(self, queue_file="./hl_announcements.json"):
        self.queue_file = queue_file
    def fetch_recent(self, since):
        try:
            with open(self.queue_file) as f:
                msgs = json.load(f)
            return [m for m in msgs if parse_time(m["time"]) > since]
        except FileNotFoundError:
            return []  # 没有 Discord Bot 时静默（第二层兜底）


# ── LLM 解析（gpt-4.1-nano，单次 < $0.0002）────────────────────
LLM_MODEL = "gpt-4.1-nano"  # 最便宜的可用模型，足够做分类+实体提取
# 备选: "gpt-4o-mini" — 能力更强，贵 ~50%，复杂公告场景可升级

DELIST_PROMPT = """你是一个交易所公告分析助手。请分析以下公告，判断是否涉及交易对的
下架、暂停、迁移、或保证金调整。

我当前持有的交易对：{held_symbols}

请以 JSON 格式回答（不要包含其他内容）：
{{"affects_holdings": true/false, "affected_symbols": ["SYM1"],
  "event_type": "delist/halt/migration/margin_change/other",
  "deadline": "ISO8601 或 null", "urgency": "high/medium/low",
  "summary": "一句话摘要"}}

宁可误报也不要漏报。如果与下架/暂停/迁移完全无关，返回 affects_holdings: false。

公告标题：{title}
公告内容：{body}"""


# ── 主监控逻辑 ─────────────────────────────────────────────────
class DelistingMonitor:
    def __init__(self, sources: list[AnnouncementSource],
                 held_symbols: list[str], notifier,
                 openai_api_key: str):
        self.sources = sources
        self.held_symbols = held_symbols
        self.notifier = notifier
        self.client = OpenAI(api_key=openai_api_key)
        self.processed = set()  # 已处理公告的 hash

    def check(self):
        """定期调用（Binance 每 6h，HL Discord 实时推送后调用）"""
        for source in self.sources:
            for ann in source.fetch_recent(since=self._last_check):
                text = ann["title"] + "\n" + ann["body"]
                h = hashlib.md5(text.encode()).hexdigest()
                if h in self.processed:
                    continue
                self.processed.add(h)

                # Step A: 关键词预过滤（免费，过滤 95% 无关公告）
                if not passes_keyword_filter(text):
                    continue

                # Step B: LLM 精析（仅关键词命中的公告，每天 0-2 次）
                result = self._llm_analyze(ann)
                if result.get("affects_holdings"):
                    self.notifier.send_urgent(
                        f"⚠️ [{source.exchange}] 下架预警\n"
                        f"标的: {result['affected_symbols']}\n"
                        f"类型: {result['event_type']}\n"
                        f"截止: {result['deadline']}\n"
                        f"摘要: {result['summary']}"
                    )

    def _llm_analyze(self, ann: dict) -> dict:
        resp = self.client.chat.completions.create(
            model=LLM_MODEL,
            messages=[{"role": "user", "content": DELIST_PROMPT.format(
                held_symbols=", ".join(self.held_symbols),
                title=ann["title"], body=ann["body"]
            )}],
            response_format={"type": "json_object"},
            temperature=0,
        )
        return json.loads(resp.choices[0].message.content)
```

**回测中的考量**：
- **存活者偏差（Survivorship Bias）**：如果回测只使用当前仍在交易的标的，
  会系统性地排除掉那些因表现差而被下架的币种，导致回测结果虚高
  → 回测标的池应包含历史上存在但已下架的标的（需要历史数据支持）
- **下架事件模拟**：回测中是否模拟了持仓标的下架的场景？
  → 至少应检查：如果某个标的突然从标的池中消失，策略是否能正常处理
  → 如果回测不处理，但实盘也不处理 → 🔴 双重盲区
- **历史数据断裂**：已下架标的的历史数据可能在交易所 API 上不再可用
  → 需要本地缓存或使用第三方历史数据源

---

## 维度四：状态持久化完整性

维度三的 3.1 只检查了"重启后能不能恢复"，这个维度深入检查"所有关键运行时状态是否被完整、及时、安全地持久化"。实盘 bot 在内存中维护的状态远比"仓位列表"丰富，任何遗漏都可能导致重启后策略行为偏移，严重时等于跑了一个全新的、未经回测验证的策略。

### 4.1 状态完整性清单

逐项检查以下运行时状态是否被持久化到 state file：

```
必须持久化（缺失=重启后策略行为改变）：
- 当前持仓列表及每个仓位的完整属性（entry_price, size, side, entry_time,
  peak_pnl, trailing_active, dca_count, 等所有自定义字段）
- 账户余额 / equity
- 当前市场状态/Regime 判定结果
- 权益曲线历史（equity_history）— 用于 momentum filter 等下游计算
- 标的选择结果及上次选择时间
- 各类冷却计时器（cooldown timers）
- 风控 guard 状态（如 uncertain_fill_guard、consecutive_error_count）
- 当前周期计数器（cycle_count）

应该持久化（缺失=重启后短期不准确，逐渐自愈）：
- 因子/信号的历史值（factors_history）— 决定了重启后是否需要 warmup 期
- 波动率计算的中间状态
- 自适应参数的当前值（如动态止盈阈值、自适应仓位大小）
- 上次成功执行各类操作的时间戳

可以不持久化（重启后可从交易所/数据源重建）：
- 最新的 OHLCV 数据（重启后重新 fetch）
- 订单簿快照
- 交易所连接状态
```

### 4.2 持久化频率与时机

```
检查项：
- state 是否在每个交易周期结束时保存（而非只在关仓时保存）
  → 如果只在关仓时保存，周期中间崩溃会丢失仓位内的状态更新（如 peak_pnl）
- state 保存是否在关键操作之后立即触发：
  → 开仓后、加仓后、关仓后、选币后、regime变化后
- 是否有"最大间隔"保障：即使没有交易事件，超过 N 分钟也强制保存一次
- 保存频率 vs 性能的权衡：是否避免了每秒写入（SSD磨损、I/O阻塞）

常见陷阱：
- 只在 graceful shutdown 时保存 → kill -9 / OOM 会丢失所有运行时变化
- 保存了仓位但没保存 equity_history → 重启后 momentum filter 失效，
  可能在不该开仓时开仓
- 保存了仓位列表但没保存仓位内的 trailing 状态 → 重启后 trailing stop 重置，
  等于放弃了已经积累的浮盈保护
```

### 4.3 持久化数据的一致性

```
检查项：
- 原子写入：是否用 write-to-temp + os.replace()，而非直接覆写 state file
  → 直接覆写在写入过程中崩溃会产生半截文件
- 字段版本兼容：代码更新增加了新的 state 字段后，旧 state file 加载是否有
  默认值兜底（dict.get(key, default)），而非 KeyError 崩溃
- 序列化完整性：复杂对象（如 datetime, Decimal, numpy array）是否能正确
  序列化/反序列化（JSON 对这些类型不是原生支持的）
- 数值精度：浮点数经过 JSON 序列化后精度是否丢失到影响策略判断的程度
- state file 大小监控：equity_history 等列表是否有上限，防止 state file
  无限膨胀（100MB+ 的 state file 加载会显著影响重启速度）

常见问题模式：
- equity_history 只存最近 100 条但某个指标需要 720 条 → 重启后指标计算不准
  直到积累够数据（这期间策略行为偏移且完全不可见）
- 新版本增加了 trailing_active 字段但旧 state 没有 → 加载后该字段为 None，
  后续比较触发 TypeError
```

### 4.4 重启后的状态校验

```
检查项：
- 加载 state 后是否与交易所实际状态做 reconciliation（核对持仓、余额）
- reconciliation 发现不一致时的处理策略：
  → 以交易所为准？以本地为准？合并？
  → 是否有日志记录不一致的具体内容
- 是否有"state 太旧"检测：如果 state file 的时间戳比当前时间早 N 小时，
  是否发出警告（可能是恢复了一个过期备份）
- 选币结果是否在重启后立即重新执行（_last_coin_selection_time 重置为 0）
  还是沿用旧结果（可能已经不是最优标的）
```

### 4.5 监控数据导出协议（Monitor Protocol Compliance）🔴 高优先级

> **⚠️ 本维度为高优先级必查项。** 每个实盘策略（阶段 B/C/D）都必须实现 Monitor Protocol。
> 如果发现 monitor_export.json 不存在或不合规，必须在审计报告中作为 🔴 关键问题列出，
> 并给出具体的修复步骤和代码示例。不要跳过此维度，不要降级为"建议"——这是强制要求。
> 改造成本极低（3-5 行代码），但缺失的后果是监控中心无法消费该策略的数据，
> 等于该策略处于"监控盲区"——出问题时发现不了、事后也无法分析。

**为什么重要**：当你有 3 个、5 个、10 个策略时，每个 bot 的 state 文件格式不同，
监控中心必须为每个策略写独立的 collector — 这是不可持续的。一个统一的"监控导出
协议"让每个 bot 旁路输出一个标准格式的 JSON 文件，监控中心只需读这一个文件。

**经验教训来源**：Trading Monitor Center 项目开发过程中发现：
- Alpha 的 equity_history 是 float deque，无时间戳，无法重建时间轴
- Beta 的 equity_history 带时间戳 + transfers，是最完善的（应作为标杆）
- Polymarket 只有风控短窗口，equity 数据无法用于趋势分析
→ 监控中心不得不为三个策略各写一个 collector，新增策略成本高

**标准：Monitor Protocol v1**

每个 bot 必须在自己的目录下维护一个 `monitor_export.json` 文件，格式如下：

```
文件位置: {bot_dir}/monitor_export.json (与 state file 同级)
更新频率: 每个交易周期结束时 (或最少每 5 分钟)
写入方式: atomic write (tmp + os.replace)

🔴 心跳频率硬性要求:
  _updated_at 必须按策略配置的 heartbeat_timeout 频率持续刷新，
  即使没有交易发生！监控中心通过此字段判断进程存活。
  - Alpha (heartbeat_timeout=300s):  每个 DCA 周期必须 export, 最大间隔 ≤ 4分钟
  - Beta  (heartbeat_timeout=86400s): 即使只做日级再平衡, 至少每12小时刷新一次
  - Polymarket (heartbeat_timeout=1800s): 每个结算周期必须 export, 最大间隔 ≤ 20分钟
  - 通用规则: 最大 export 间隔 ≤ heartbeat_timeout × 0.8

  对于循环间隔可能超过 heartbeat_timeout 的策略(如 Beta 日级再平衡),
  必须实现"空闲心跳"机制 — 在 heartbeat_timeout/2 间隔内刷新 _updated_at。
  示例: daemon thread 每12小时调用 exporter.export() 导出当前快照。

  违反此要求会导致: HEARTBEAT_LOST 误告警 → 运维疲劳 → 真正告警被忽略

必须字段:
{
  "_protocol_version": 1,
  "_updated_at": "ISO 8601 UTC",

  "identity": {
    "bot_name": "string — 唯一标识, 监控中心据此区分",
    "strategy": "string — 策略类型描述",
    "exchange": "string — 交易所名称"
  },

  "equity": {
    "current": float,            # adjusted equity (扣除转入转出) ← 最核心
    "raw_balance": float,        # 交易所原始余额
    "cumulative_transfers": float,# 累计充提净额
    "peak": float,               # adjusted equity 历史峰值
    "drawdown_pct": float,       # 当前回撤 (负数)
    "unrealized_pnl": float      # 未实现盈亏
  },

  "positions": {
    "count": int,
    "total_unrealized_pnl": float,
    "details": [...]              # 可选: 逐仓明细
  },

  "health": {
    "is_running": bool,
    "last_heartbeat": "ISO 8601",
    "uptime_seconds": int,
    "last_trade_time": "ISO 8601 or null",
    "last_error": "string or null",
    "error_count_24h": int
  },

  "equity_history": [             # 带时间戳的滚动快照
    {"t": "ISO 8601", "eq": float, "raw": float, "pnl": float, "pos": int},
    ...  // 建议 >= 4320 条 (5min间隔 × 15天)
  ]
}
```

**审查清单**：

```
1. monitor_export.json 是否存在：
   □ bot 目录下是否有 monitor_export.json 的写入逻辑
   □ 如果不存在 → 🔴（新策略上线前必须实现）
   □ 如果使用了 trading-monitor-center/monitor_protocol.py 的
     MonitorExporter → 自动符合标准

2. 必须字段完整性：
   □ identity.bot_name 是否与 monitor center config 中 short_name 一致
   □ equity.current 是否是 transfer-adjusted 的（不是 raw balance）
     → 不做 transfer adjustment 会导致充值时 equity 曲线跳变，
       误报"巨额盈利"，提现时误报"巨额亏损"
   □ equity.cumulative_transfers 是否被追踪
   □ equity_history 是否带时间戳（不能只是 float 数组！）
   □ health.last_heartbeat 是否每周期更新

3. equity_history 质量：
   □ 是否带 ISO 8601 时间戳
   □ 是否使用 adjusted equity（不是 raw balance）
   □ 保留条数 >= 4320（5min × 15天）
   □ 是否有裁剪逻辑防止无限增长
   □ 重启后是否从 export 文件恢复（不从零开始）

4. 写入安全：
   □ 是否使用 atomic write（tmp + rename）
   □ 写入失败是否不影响主策略逻辑
   □ export 是旁路操作，不阻塞主交易循环

5. 一致性：
   □ export 的 equity.current 与 bot 内部 state 的 equity 一致
   □ _updated_at 反映最后一次 export 时间

6. 🔴 心跳频率合规（新增 — 必查！）：
   □ 策略主循环是否在每个周期结束时调用 exporter.export()
     → 即使本周期没有交易，也必须 export 以刷新 _updated_at
   □ 策略的实际 export 最大间隔是否 ≤ heartbeat_timeout × 0.8
     → 参考 monitor center config.py 中 BotConfig.heartbeat_timeout
   □ 对于循环间隔可能超过 heartbeat_timeout 的策略:
     是否有空闲心跳机制（daemon thread / timer / scheduler）
     → 典型案例: Beta 策略日级再平衡, 但 heartbeat_timeout=86400s,
       必须有线程在两次再平衡之间至少刷新一次（每12小时）
   □ 如果不合规 → 🔴 关键问题:
     "策略 X 的 export 间隔可能超过 heartbeat_timeout,
      会导致 HEARTBEAT_LOST 误告警。需要在主循环每个周期末尾
      无条件调用 exporter.export(), 或实现空闲心跳线程。"
```

**Beta 作为标杆**：Beta 的 StateManager._append_equity_snapshot() 已实现大部分要求。

**改造成本**：对已有策略，在主循环末尾加 3-5 行代码调用 MonitorExporter.export()。

**与维度 3.8 的关系**：3.8 关注交易决策日志（事后分析），4.5 关注实时状态导出（监控消费）。
两者互补但不重叠：3.8 记录"为什么做了这个决策"，4.5 导出"当前策略处于什么状态"。

---

## 维度五：代码性能

量化 bot 的性能瓶颈和普通应用不同：热路径是每个交易周期重复执行的决策循环，一次多余的 API 调用可能意味着几秒的延迟，在快速行情中就是错过入场或出场的窗口。

### 5.1 热路径效率

```
检查项：
- 主循环（每个交易周期）中是否有不必要的重复计算：
  → 每次循环都重新计算不变的值（如 fee rate、leverage limits）
  → 每次循环都重新读取不变的配置
- 指标/因子计算是否做了增量更新（incremental）：
  → 好：收到新 bar 时只更新最新值
  → 差：每次都对完整历史重新计算（如对整个 equity_history 做 rolling mean）
- 标的选择/排序是否在每个周期都执行：
  → 通常应有冷却机制，如每 24h 执行一次
- 循环内是否有嵌套的 O(n²) 或更差的算法：
  → 遍历仓位列表中嵌套遍历订单列表
  → 对大列表做线性搜索而非用 dict/set

自动化检查建议：
- grep 主循环体中的 API 调用次数，标记每周期 >3 次的情况
- 检查是否有缓存机制（如 lru_cache、手动 dict 缓存）
```

### 5.2 API 调用优化

```
检查项：
- 是否合并了可批量执行的 API 调用：
  → 差：逐个标的 fetch_ohlcv（N 个标的 = N 次调用）
  → 好：一次 fetch 多个标的，或并发请求
- 是否避免了冗余调用：
  → 同一个周期内多次 fetch_balance / fetch_positions
  → 可以 fetch 一次，传递给需要的函数
- 是否遵守了 rate limit 且利用了限额：
  → 过于保守（每次调用间隔 5 秒）浪费了可用带宽
  → 过于激进（无间隔连续调用）触发限频封禁
- 超时设置是否合理：
  → 无超时 = 网络抖动时整个 bot 挂起
  → 超时太短 = 正常的慢响应被误判为失败
```

### 5.3 内存管理

```
检查项：
- 列表/队列是否有大小上限：
  → equity_history、trade_log、factors_history 等持续增长的数据结构
  → 如果没有上限，运行几周后可能占用 GB 级内存
- 是否有内存泄漏模式：
  → 闭包捕获了大对象
  → 事件监听器只注册不注销
  → 缓存只增不删（dict 持续膨胀）
- DataFrame/numpy array 是否在不需要时释放：
  → 大历史数据 fetch 后只取最后 N 条，原始数据是否被 GC
- 日志对象是否有 rotation：
  → 内存中的日志 handler 是否有 maxBytes / backupCount

自动化检查建议：
- 搜索 append / extend 调用，检查对应列表是否有 maxlen 或截断逻辑
- 搜索 dict 赋值，检查是否有清理机制
```

### 5.4 并发与异步

```
检查项：
- I/O 密集型操作（API 调用、文件写入）是否阻塞了主循环：
  → state 保存是否是同步写入（每次暂停几十毫秒）
  → 可以考虑异步写入或 write-behind 机制
- 多标的处理是否并发：
  → 串行处理 N 个标的的信号/下单 vs 并发处理
  → 注意并发下单时的 race condition（总敞口检查）
- 是否有不必要的 sleep：
  → 固定 sleep(60) vs 自适应间隔（行情剧烈时缩短）
  → sleep 期间是否响应信号（SIGINT）

性能 vs 安全的权衡：
- 异步写 state 可以提升性能，但增加了崩溃时丢失数据的风险
- 并发下单可以减少延迟，但需要额外的敞口锁/原子检查
- 审计时标注权衡即可，不需要一刀切地要求"全部异步"
```

---

## 维度六：AI 协作代码质量

使用 AI 辅助编码时，AI 会产生一些"看起来健壮实则有害"的代码模式。这些模式在量化交易系统中危害尤其大——错误被掩盖意味着策略在用错误的价格/仓位/信号做决策，而你浑然不知。

### 6.1 防御性 Fallback 掩盖错误

```
反模式：
  price = product?.price ?? 0
  user_name = user?.name || "Unknown"
  leverage = config.get("leverage", 1)   # 配置缺失时默默用1x

为什么危险：
- 当 price 不该为空却为空时，这段代码不会报错，而是悄悄把价格算成 0
- 在量化场景中：entry_price 取到 0 → PnL 计算爆炸 → 止损在离谱的价位触发
- 更隐蔽的：leverage 配置没加载成功，默默回退到 1x，你以为跑的是 3x 策略

检查项：
- grep 所有 `?? 0`、`|| 0`、`.get(key, 0)`、`or 0`、`if x is None: x = 0`
- 对每一个 fallback 问：如果这个值真的缺失了，用默认值继续运行是对的吗？
  还是应该立即报错让你知道？
- 关键路径（价格、仓位、余额、杠杆）的 fallback 默认值应该用
  raise / assert 替代，而非静默兜底
- 配置加载失败时应 fail-fast，不应用 fallback 值继续运行

正确做法：
  # 不要兜底，让错误暴露
  assert product.price is not None, f"price missing for {symbol}"
  # 配置缺失时立即崩溃，而非默默用默认值
  leverage = config["leverage"]  # KeyError 比默默用错值好
```

### 6.2 try/catch 吞掉错误

```
反模式：
  async def execute_trade(signal):
      try:
          position = await check_position(symbol)
          order = await place_order(symbol, side, size)
          await update_state(order)
          return order
      except Exception as e:
          logger.error(f"Trade failed: {e}")
          return None  # 调用方拿到 None，不知道是哪步失败的

为什么危险：
- check_position 失败了？place_order 有 bug？update_state 写坏了？
  全被吞进同一个 catch，调用方只看到一个 None
- 在量化场景中：order 下单成功但 update_state 失败 → 本地状态没更新 →
  下个周期以为没有仓位 → 重复开仓 → 双倍敞口
- 更糟：吞掉 TypeError / AttributeError 等编程错误，本该修的 bug 变成了
  偶尔出现的"交易失败"日志，排查难度指数级上升

检查项：
- 搜索所有 `except Exception` 和 `except:` 块
- 对每个 catch 块问：它捕获的是"预期的运行时异常"还是"所有可能的错误"？
- 业务逻辑层不应有宽泛的 try/catch — 让错误冒泡到最外层统一处理
- 如果必须 catch，至少区分"可重试的 I/O 错误"和"不可重试的逻辑错误"

正确做法：
  # 只捕获你预期的、知道怎么处理的异常
  try:
      order = await place_order(symbol, side, size)
  except ccxt.InsufficientFunds:
      logger.warning(f"余额不足，跳过 {symbol}")
      return None
  except ccxt.NetworkError:
      logger.error(f"网络错误，稍后重试")
      raise  # 让上层处理重试
  # TypeError / KeyError / AttributeError 等编程错误：不捕获，让它崩
```

### 6.3 测试质量审计

AI 生成的测试代码有三种常见的"永远通过"模式，在量化系统中必须警惕：

```
反模式一：断言太弱（永远通过的测试）
  # AI 最爱的写法
  result = await backtest(config)
  assert result is not None          # 只检查不是 None — 毫无意义
  assert len(result.trades) > 0      # 有交易就行 — 不验证交易是否正确

  # 正确：验证具体的业务结果
  assert result.total_return == pytest.approx(0.15, abs=0.01)
  assert result.max_drawdown < 0.20
  assert all(t.pnl != 0 for t in result.trades)  # 不应有零PnL交易

反模式二：硬编码拟合测试
  # AI 不理解逻辑，直接硬编码"正确"返回值让测试通过
  def calculate_signal(prices):
      if prices[-1] == 100 and prices[-2] == 95:  # 恰好匹配测试用例
          return 1.0
      return 0.0

  → 测试全绿，但逻辑根本没实现 — 只是一张针对测试数据的查找表
  → 检查方法：用随机值和边界值运行测试，看是否仍然通过

反模式三：先修 Bug 再补测试
  → Bug 已经修了，你怎么知道补的测试真能抓住这个 bug？
  → 正确流程（TDD）：先写测试 → 确认失败（红）→ 修复代码 → 确认通过（绿）
  → 先红后绿 — 亲眼看到测试从红变绿，才能证明测试有效
  → 审计时关注：是否有测试只验证了 happy path 而没有验证它能检测到错误

检查项：
- 搜索测试文件中的 assert / expect 语句，检查断言的具体性
- 标记只检查 is not None / toBeDefined / > 0 的弱断言
- 对关键策略逻辑的测试：是否覆盖了边界条件（空仓位、零余额、极端价格）
- 是否有"删除被测函数核心逻辑后测试仍然通过"的风险
```

### 6.4 调试日志纪律

```
反模式：修 Bug 时顺手删掉调试日志
  你：加调试日志 → AI 插入日志 → 运行，拿到线索
  → AI "发现问题"，修复代码的同时顺手把调试日志也清掉了
  → 问题没解决 → 你不得不让 AI 重新插入一遍日志 → 循环

为什么在量化系统中尤其重要：
- 实盘 bug 很难复现 — 依赖特定的市场状态 + 持仓状态 + 时间窗口
- 调试日志是唯一的"黑匣子"，删了就没了
- 某些 bug 只在凌晨 3 点行情剧烈波动时出现，你不可能坐在那等

纪律：
- 调试日志由人决定何时清除，AI 修复代码时不要动日志
- 等你确认问题真正解决后，再统一清理
- 关键路径（下单、持仓变更、状态保存）的日志永远不删，只调整级别
- 审计时检查：最近的 commit 是否在修 bug 的同时删除了 logging 语句
```

## 维度七：供应链与运行时安全

量化交易系统是高价值目标：它持有交易所 API Key（通常有交易权限），7x24 无人值守运行，
直接操控真金白银。供应链攻击一旦成功，攻击者可以：窃取 API Key 转移资产、
篡改策略逻辑制造亏损、植入后门长期潜伏。

**真实案例参考**（2026-03 axios 供应链攻击）：
攻击者通过盗取 npm 维护者凭证，发布了含恶意 postinstall 脚本的 axios 1.14.1。
该脚本通过 XOR+Base64 双层混淆，下载跨平台 RAT（远程访问木马），并在安装完成后
自动清除所有痕迹（用干净的 package.json 替换恶意版本）。从发布到下架仅 2-3 小时，
但足以感染大量 CI/CD 管道。

### 7.1 依赖链审计

```
核心原则：你的安全性等于你最弱的依赖的安全性。

检查项：

□ Lockfile 存在且被 commit
  → Python: requirements.txt 或 poetry.lock（带哈希 --hash）
  → Node: package-lock.json 或 yarn.lock
  → 没有 lockfile = 每次 install 可能拉到不同版本 = 不可复现 + 投毒窗口

□ 版本锁定（pinning）
  → 🔴 "ccxt>=4.0" — 开放范围，可能被投毒的新版本命中
  → ✅ "ccxt==4.2.31" — 精确锁定
  → 检查所有 requirements.txt / package.json 中的版本约束

□ 幽灵依赖检测（Phantom Dependencies）
  → 在 manifest（package.json / requirements.txt）中声明了，但代码中从未 import
  → 这是 axios 攻击的核心手法：加入 plain-crypto-js 作为依赖，
    代码不引用它，但 postinstall 脚本会自动执行
  → 扫描方法：列出所有声明的依赖 → grep 代码中的 import/require → 找出差集

□ 依赖数量合理性
  → 量化系统的核心依赖通常不多：ccxt/exchange SDK、numpy/pandas、TA 库
  → 如果 dependencies 列表异常庞大（>30），逐一审查每个依赖的必要性
  → 关注"你不认识的"依赖——你说不出它干什么的，就不应该在项目里

□ 新增依赖审查
  → 每次 code review 时，如果 requirements.txt / package.json 有改动：
    - 新加的依赖是什么？干什么的？谁维护的？
    - npm/PyPI 上发布多久了？下载量如何？
    - 有没有 typosquatting 嫌疑（如 ccxt-utils vs ccxt_utils）
```

### 7.2 安装脚本与构建钩子

```
核心原则：postinstall / setup.py 中的任意代码执行是供应链攻击的主要入口。

检查项：

□ postinstall 脚本审计（Node 项目）
  → 检查 node_modules 中所有 package.json 的 "scripts" 字段
  → 快速扫描：find node_modules -name package.json -exec grep -l "postinstall\|preinstall" {} \;
  → 任何触发外部下载（curl/wget/fetch）或执行（exec/spawn/eval）的 postinstall = 🔴

□ setup.py / pyproject.toml 审计（Python 项目）
  → setup.py 可以在 install 时执行任意 Python 代码
  → 检查 cmdclass 自定义命令、__builtins__ 操作、网络请求
  → 优选使用声明式 pyproject.toml 而非可执行的 setup.py

□ 混淆代码检测
  → 扫描依赖中的 eval()、exec()、compile()、__import__()
  → 检查 Base64 编码块、XOR 解码函数、charCodeAt 链
  → 量化项目的依赖不应该包含混淆代码——这不是前端 minification

□ CI/CD 安全
  → GitHub Actions / CI 中的 npm install / pip install 是否使用 --ignore-scripts？
  → 是否有 lockfile integrity check（如 npm ci 而非 npm install）？
  → CI 环境是否有出站网络白名单？
```

### 7.3 密钥与敏感信息管理

```
核心原则：API Key 是交易系统的"最高权限凭证"，泄露 = 资产被转移。

检查项：

□ 硬编码密钥扫描
  → grep -rn "api_key\|api_secret\|apiKey\|apiSecret\|private_key" --include="*.py" --include="*.js" --include="*.ts"
  → 排除 .env.example / config.example 中的占位符
  → 🔴 任何真实密钥出现在代码文件中 = Critical（即使在 .gitignore 的文件里也不行，
    因为可能有其他工具/agent 读取代码时泄露）

□ .env / 配置文件安全
  → .env 是否在 .gitignore 中？
  → .env 的权限是否 600（仅所有者可读写）？
  → 是否有 .env.example 模板（不含真实值）？
  → 配置中是否有 withdrawal 相关权限？量化 bot 通常只需 trade 权限，不需要 withdraw

□ Git 历史中的密钥泄露
  → 即使当前代码没有密钥，历史 commit 中可能曾经有
  → git log -p --all -S "api_key" --since="1 year ago" 快速扫描
  → 如发现历史泄露 → 🔴 必须立即轮换该密钥

□ AI Agent 上下文中的密钥暴露
  → 量化项目经常使用 AI（包括本 skill 所在的 Claude）辅助开发
  → 确保 .env 文件不会被 AI agent 读取或出现在对话上下文中
  → 确保 config 加载逻辑不会在日志/错误信息中打印密钥值
  → logger.error(f"Config: {config}") → 🔴 如果 config 包含密钥
```

### 7.4 网络出站控制

```
核心原则：交易 bot 的合法出站连接非常有限——只有交易所 API。
任何其他出站请求都是异常信号。

检查项：

□ 合法出站清单
  → 列出代码中所有硬编码的 URL/域名/IP
  → 交易所 API（api.binance.com, api.hyperliquid.xyz 等）→ ✅ 合法
  → Telegram Bot API（用于通知）→ ✅ 合法
  → 其他任何域名 → 🟡 需要解释为什么需要

□ 动态 URL 检测
  → 搜索从环境变量/配置/远程读取 URL 后发起请求的代码
  → requests.get(config["webhook_url"]) → 🟡 URL 来源可控吗？
  → eval(response.text) / exec(downloaded_code) → 🔴 远程代码执行

□ DNS 与出站防火墙（生产环境）
  → 实盘 bot 运行的服务器是否配置了出站白名单？
  → 建议：iptables / ufw 只允许交易所 IP + Telegram IP 的出站连接
  → 所有非白名单出站请求 = 告警

□ WebSocket 连接审计
  → 量化系统常用 WS 接收实时数据
  → 检查 WS 连接的目标地址是否全部指向合法交易所
  → 检查 WS 消息处理是否有反序列化漏洞（如 pickle.loads / JSON.parse + eval）
```

### 7.5 运行时隔离与权限最小化

```
核心原则：即使代码被攻破，限制攻击者能做的事。

检查项：

□ 运行用户权限
  → bot 是否以 root 运行？→ 🔴 不要用 root
  → 应创建专用用户，只对必要目录有读写权限

□ API Key 权限最小化
  → 交易所 API Key 是否只开启了必要权限？
  → ✅ spot trading / futures trading
  → 🔴 withdrawal（提现）— 量化 bot 绝不需要提现权限
  → 🟡 universal transfer — 除非策略需要跨账户调拨
  → 如果交易所支持 IP 白名单 → 必须绑定 bot 服务器 IP

□ 文件系统隔离
  → bot 是否只能访问自己的工作目录？
  → 是否能读取其他用户的 home 目录、~/.ssh/、~/.aws/ 等敏感路径？
  → Docker 化部署可以天然实现文件系统隔离

□ 进程监控
  → 是否有机制检测 bot 进程产生的异常子进程？
  → 正常的量化 bot 不应 fork/spawn 未知子进程
  → 如果使用 systemd：配置 ProtectHome=true, ProtectSystem=strict
```

### 7.6 代码完整性与变更审计

```
核心原则：确保运行的代码就是你审计过的代码。

检查项：

□ 部署完整性
  → 生产环境的代码是否从 git tag/release 部署？
  → 是否有机制验证部署的代码和 git 中的一致（如 git diff --stat）？
  → 手动改了生产服务器上的文件但没 commit → 🔴 不可追溯

□ AI Agent 代码变更审计（与 alpha-lab 配合）
  → 当 AI agent（如 alpha-lab 研究循环）自主修改策略代码时：
  → 每次修改都有 git commit → ✅（已在 alpha-lab 中要求）
  → 里程碑版本经过 quant-code-review → ✅（已在 alpha-lab 中要求）
  → 但需额外检查：AI 是否引入了不在修改范围内的变更？
    git diff --stat 是否只改了预期的文件？
  → 🔴 AI 修改了 .env / config 中的 API endpoint / 加了新依赖但没说明

□ 依赖更新时的差异审查
  → pip install --upgrade / npm update 后：
  → 检查 lockfile diff，确认只有预期的包被更新
  → 对更新的包检查 changelog，是否有异常（如 maintainer 变更、
    突然增加新依赖、postinstall 脚本变更）

□ 定期安全扫描
  → pip audit / npm audit 定期运行
  → 关注 Critical 和 High 级别的 CVE
  → 尤其关注涉及 RCE（远程代码执行）和 SSRF 的漏洞
```

### 7.7 量化系统特有的攻击面

```
这些攻击面是量化交易系统独有的，通用安全指南通常不会覆盖：

□ 数据源投毒
  → 如果策略依赖第三方数据源（非交易所直接 API），
    数据被篡改 → 策略做出错误决策 → 亏损
  → 检查：数据源是否有 HTTPS + 证书验证？
  → 检查：是否有数据合理性校验（价格在合理范围内、无突变等）？

□ 策略逻辑外泄
  → 策略代码是核心知识产权
  → 是否有日志/错误信息泄露策略细节？
  → 是否有遥测/分析工具在收集代码行为数据？
  → AI agent 对话记录中是否包含完整策略逻辑？

□ Telegram / 通知渠道安全
  → Telegram Bot Token 泄露 = 攻击者可以伪造通知
  → 更严重：如果 bot 支持通过 Telegram 命令控制（如 /stop /close_all），
    Token 泄露 = 攻击者可以远程操控你的交易
  → 检查：Telegram 命令是否有鉴权（如白名单 chat_id）？

□ 时间同步攻击
  → 量化系统依赖准确的时间戳（K线对齐、funding settlement 时间等）
  → NTP 被劫持或服务器时间漂移 → 策略在错误的时间做决策
  → 检查：服务器是否配置了多个 NTP 源？是否有时间偏差告警？
```

---

## 输出格式

审计完成后，输出一个结构化报告：

```
## 审计报告

### 维度 P：项目阶段与部署就绪度
- **项目阶段**: [A 纯回测 / B 开发中 / C 可部署 / D 已上线]
- **组件扫描**: [N/M 关键组件存在]
- **后续维度适用性**: [列出哪些维度适用、哪些 N/A]

P.2 部署就绪度（如适用）：
| # | 组件 | 状态 | 备注 |
|---|------|------|------|
| P.2.1 | 交易所 API 集成 | ✅/❌ | SDK/认证/端点 |
| P.2.2 | 实盘执行器 | ✅/❌ | 信号→订单/成交确认 |
| P.2.3 | 实时数据源 | ✅/❌ | REST/WS/lookback |
| P.2.4 | 仓位对账 | ✅/❌ | reconciliation |
| P.2.5 | 密钥配置 | ✅/❌ | .env/环境变量 |
| P.2.6 | 依赖管理 | ✅/❌ | requirements/pinned |
| P.2.7 | 入口与调度 | ✅/❌ | main/scheduler/shutdown |
| P.2.8 | README | ✅/❌ | quick start/config doc |
| P.2.9 | 监控告警 | ✅/❌ | heartbeat/alert/kill switch |

### 维度零：模块清单盘点
| 模块名 | 回测 | 实盘 | 当前启用 | 状态 |
|--------|------|------|---------|------|
| ... | ✅ | ✅ | 是 | ✅ |
| ... | ✅ | ❌ | 是 | 🔴 缺失 |

配置注册完整性：[全部注册 / N个缺失（列出）]

### 维度一：实盘/回测对齐
| # | 检查项 | 状态 | 备注 |
|---|--------|------|------|
| 1 | ... | ✅ | ... |
| 2 | ... | ❌ | 具体问题描述 |

参数对比结果：[全部匹配 / N个不匹配（列出）]
数据需求：[满足 / 不满足（列出）]

### 维度二：回测真实性
| # | 检查项 | 状态 | 备注 |
|---|--------|------|------|
| 2.1 | 成本模型 | ✅/❌ | fee rate / maker-taker / 滑点 |
| 2.2 | 执行假设 | ✅/❌ | 成交假设 / 延迟 |
| 2.3 | 数据偏差 | ✅/❌ | 幸存者/前视偏差 |
| 2.4 | PnL计算 | ✅/❌ | 自洽性 / 精度 |
| 2.5 | 杠杆保证金模型 | ✅/❌ | PnL公式 / 全仓模式 |
| 2.6 | 手续费复利 | ✅/❌ | commission sweep 结果 |
| 2.7 | 因子有效性 | ✅/❌ | 方向性 / 正交性 |
| 2.8 | 全仓爆仓模拟 | ✅/❌ | 保证金率/wick/available balance/funding |
| 2.9 | 回测日志可分析性 | ✅/❌ | trade log/equity log/文件管理 |
| 2.11 | Margin-Ratio 自动减仓 | ✅/❌/N/A | 回测 blend / 实盘 MarginMonitor |

2.8 详细子项：
- 每bar保证金检查：[有/无]
- Wick模拟方式：[close only(🔴)/high-low(🟡)/OHLC路径(✅)]
- Available Balance追踪：[有/无]
- Funding Rate模拟：[有/无/不适用(现货)]
- 极端行情压力测试：[通过/未通过/未执行]

2.9 回测日志：
- Trade Log：[结构化输出(✅)/纯print(🔴)/无(🔴)]
- Trade Log 必须字段完整性：[完整/缺N个（列出）]
- Equity Log：[有/无]
- 文件管理：[每次新文件(✅)/append旧文件(🔴)/覆盖(🔴)]
- 文件命名含时间戳+配置：[是/否]
- Run Summary含配置快照：[是/否]
- Σ pnl_net 与 equity 变化一致性：[通过/偏差X%]

2.11 自动减仓：
- 回测 margin-ratio deleverage：[实现(✅)/可选(🟡)/无(❌)]
- Blend 参数默认值：[0(✅)/0.5(🟡)/1.0(🔴 — 会被 wick 假象误导)]
- Deleverage 事件记录：[有/无]
- 实盘 MarginMonitor：[独立模块(✅)/嵌入主循环(🟡)/无(🔴)]
- MarginMonitor 线程解耦：[daemon thread/独立进程(✅)/同步(🔴)]
- Cooldown + Kill switch：[有/无]
- 通知机制：[Telegram(✅)/日志(🟡)/无(🔴)]

### 维度三：运维鲁棒性
[逐项结果，含 3.6 MarginMonitor + 3.7 资金流水过滤 + 3.8 日志体系 + 3.9 交易对生命周期]
- 3.7 Transfer Isolation：[已实现(✅)/部分(🟡)/未实现(🔴)]
- adjusted_equity 使用：[全部下游(✅)/部分(🟡)/未使用(🔴)]
- unexplained_delta 检测：[有(✅)/无(🔴)]
- Exchange income API 集成：[有(✅)/无(🔴)]
- 3.8 日志体系：[完备(✅)/部分(🟡)/不足(🔴)]
- 每次启动独立日志文件：[是(✅)/否(🔴)]
- 结构化格式（JSON Lines）：[是(✅)/否(🔴)]
- 启动元数据（config+git hash）：[有(✅)/无(🔴)]
- 决策日志（含 skip 原因）：[有(✅)/仅交易(🟡)/无(🔴)]
- 定期 equity 快照：[有(✅)/无(🔴)]
- 关机原因记录：[有(✅)/无(🔴)]
- 3.9 交易对下架防御：[完备(✅)/部分(🟡)/未实现(🔴)]
- 第一层 公告监控+LLM 解析：[已实现(✅)/计划中(🟡)/无(🔴)]
- 第二层 API 状态定期检查：[有(✅)/无(🔴)]
- 第三层 订单被拒容错处理：[有(✅)/无(🔴)]
- 受影响标的自动禁止开仓：[有(✅)/无(🔴)]

### 维度四：状态持久化完整性
| # | 检查项 | 状态 | 备注 |
|---|--------|------|------|
| 4.1 | 状态完整性 | ✅/❌ | 缺失的字段列表 |
| 4.2 | 持久化频率 | ✅/❌ | 当前频率 + 风险窗口 |
| 4.3 | 数据一致性 | ✅/❌ | 原子写/版本兼容/精度 |
| 4.4 | 重启校验 | ✅/❌ | reconciliation 覆盖情况 |
| 4.5 | 🔴监控导出协议 | ✅/🟡/❌ | monitor_export.json 合规性（高优先级必查） |

⚠️ **4.5 必须单独展开说明**（不能只填表格，必须额外输出以下内容）：
```
4.5 Monitor Protocol 检查结果：
- monitor_export.json 是否存在：[是/否]
- 如果否 → 🔴 关键问题，给出具体的接入步骤（参考 MonitorExporter）
- equity.current 是否 transfer-adjusted：[是/否/不适用]
- equity_history 是否带时间戳：[是/否]
- 写入方式是否 atomic：[是/否]
- 🔴 心跳频率合规：[是/否]
  - 策略 heartbeat_timeout：[X 秒]
  - 实际最大 export 间隔：[Y 秒]
  - 是否 ≤ heartbeat_timeout × 0.8：[是/否]
  - 空闲心跳机制（仅长周期策略需要）：[有/无/不适用]
  - 如果否 → 🔴 关键问题: 会导致 HEARTBEAT_LOST 误告警
- 修复建议：[具体代码位置和改动方案]
```

### 维度五：代码性能
| # | 检查项 | 状态 | 备注 |
|---|--------|------|------|
| 5.1 | 热路径效率 | ✅/🟡/❌ | 每周期耗时估算 |
| 5.2 | API 调用 | ✅/🟡/❌ | 每周期调用次数 |
| 5.3 | 内存管理 | ✅/🟡/❌ | 增长型数据结构数量 |
| 5.4 | 并发与异步 | ✅/🟡/❌ | 阻塞点列表 |

### 维度六：AI 协作代码质量
| # | 检查项 | 状态 | 备注 |
|---|--------|------|------|
| 6.1 | 防御性 Fallback | ✅/🟡/❌ | 关键路径 fallback 数量 |
| 6.2 | try/catch 范围 | ✅/🟡/❌ | 宽泛 catch 块数量 |
| 6.3 | 测试质量 | ✅/🟡/❌ | 弱断言 / 硬编码拟合 / TDD |
| 6.4 | 调试日志纪律 | ✅/🟡/❌ | 是否有修 bug 时误删日志 |

### 维度七：供应链与运行时安全
| # | 检查项 | 状态 | 备注 |
|---|--------|------|------|
| 7.1 | 依赖链审计 | ✅/🟡/🔴 | lockfile/pinning/幽灵依赖 |
| 7.2 | 安装脚本审计 | ✅/🟡/🔴 | postinstall/混淆代码 |
| 7.3 | 密钥管理 | ✅/🟡/🔴 | 硬编码/.env/git历史/权限 |
| 7.4 | 网络出站控制 | ✅/🟡/🔴 | 合法出站清单/动态URL/防火墙 |
| 7.5 | 运行时隔离 | ✅/🟡/🔴 | 用户权限/API权限/文件系统 |
| 7.6 | 代码完整性 | ✅/🟡/🔴 | 部署验证/AI变更审计/依赖diff |
| 7.7 | 量化特有攻击面 | ✅/🟡/🔴 | 数据源/策略外泄/通知渠道/NTP |

7.3 关键子项：
- API Key 提现权限：[未开启(✅)/已开启(🔴)]
- API Key IP白名单：[已绑定(✅)/未绑定(🟡)]
- .env 在 .gitignore：[是(✅)/否(🔴)]
- Git 历史密钥泄露：[未发现(✅)/发现N处(🔴)]

### 发现的问题
[按严重程度排列：🔴 Critical / 🟡 Warning / 🟢 Info]

### 建议修复
[具体改动建议，标明优先级]
```

---

## 经验教训（从实际审计中总结）

这些是从真实量化项目审计中发现的典型问题，作为检查提醒：

1. **回测新增模块必须同步到实盘** — 回测器作为"实验室"迭代快，新模块（仓位加权、风控、自适应调整等）经常在回测中实现后遗漏向实盘的移植。用 grep `_ENABLE` 在回测目录 vs 实盘目录比对，是发现这类问题最快的方式。
2. **参数注册和参数值是两个层面的问题** — 参数值对齐了不代表安全。如果实盘的配置加载机制是严格的（要求 key 预先存在），新增参数未注册默认值会导致启动崩溃，即使参数值本身完全正确。
3. **回测配置加载机制和实盘往往不同** — 回测器常用 proxy/overlay 对象（getattr 兜底，宽松），实盘常用 apply_overrides / setattr（严格，要求 key 预先存在）。这种差异会隐藏很多问题：回测跑得完美，实盘启动即崩。审计时必须确认两者的加载机制，以及严格端是否所有 key 都已注册。
4. **手续费不要硬编码** — 应从config读取，方便回测和实盘统一调整
5. **标的选择指标必须完全一致** — 公式差一点就选出完全不同的标的，等于跑了一个没回测过的策略
6. **数据量不足会污染所有下游计算** — 取不够K线会让长周期指标退化为短周期，所有依赖它的决策都会偏移。特别注意：新增模块的 lookback 窗口可能被旧模块的更大窗口"隐式覆盖"，但这不安全 — 配置一旦改变就会暴露。应在 fetch 逻辑中显式注册每个模块的窗口需求。
7. **历史数据的更新频率和持久化都要对齐** — per-bar vs per-close差很多倍；存储条数截断会影响窗口计算
8. **PnL模型影响的不只是收益数字** — 不同的杠杆PnL计算方式会让止损在完全不同的价位触发
9. **关键设置失败不能静默** — DEBUG级别的日志等于没有，杠杆/保证金设错了整个策略行为都变了
10. **"更保守"的参数不一定更好** — 回测已经为某组参数做过优化，随意调整等于否定了回测结果
11. **旧 preset 安全不代表新 preset 安全** — 如果项目有多个 preset/profile，切换 default 时必须完整验证新 preset 的所有参数在实盘端可加载。旧 preset 可能恰好不用某些新参数，所以从未暴露注册缺失。
12. **equity_history 截断是隐形杀手** — 只存 100 条但 momentum filter 需要 720 条，重启后 filter 行为完全变了但不会报错，只是默默用了不完整的数据做判断。这类问题只有在重启后第一个交易周期才会暴露，且很难事后排查。
13. **state file 版本迁移必须有默认值** — 代码新增字段后旧 state file 没有该字段是必然的。如果用 `state['new_field']` 而非 `state.get('new_field', default)` 读取，下一次重启就会崩溃。
14. **每周期重新计算完整指标是常见的性能陷阱** — 对 5000 根 K 线做 rolling mean 每周期耗时可能超过 100ms，4 个标的就是 400ms+。改成增量更新（只算最新一根）可以降到微秒级。
15. **串行 API 调用是延迟大户** — 4 个标的串行 fetch_ohlcv 平均耗时 2-4 秒，改成 asyncio.gather 可以压到 1 秒以内。在快速行情中，3 秒的延迟可能意味着错过最优入场点。
16. **Fallback 默认值是定时炸弹** — `price ?? 0` 在正常时永远不会触发，你以为代码很"健壮"。但某天数据源出了问题，price 真的为空，代码不报错，默默用 0 计算 PnL，止损在离谱的价位触发。关键路径的缺失值应该 fail-fast（assert/raise），而非静默兜底。
17. **宽泛的 try/catch 是 bug 的藏身之处** — `except Exception` 把 I/O 错误和编程错误（TypeError/KeyError）混在一起处理。实盘中下单成功但状态更新抛了 KeyError，被 catch 吞掉了，下个周期就会重复开仓。只捕获你预期的、知道怎么处理的异常。
18. **测试要能"红"才有价值** — 如果删掉被测函数的核心逻辑后测试仍然通过，这个测试就是摆设。用 mutation testing 思维审查：故意改错一个阈值，看测试是否能发现。
19. **调试日志删早了比没有更糟** — 实盘 bug 依赖特定的市场+持仓+时间窗口组合，极难复现。AI 修 bug 时顺手删日志是常见陋习。纪律：日志由人决定何时清理，修复期间只增不删。
20. **全仓模式下杠杆不参与 PnL 计算** — 在 Binance USDT-M Cross Margin 中，杠杆仅影响保证金分配，不影响实际盈亏。`PnL = notional × Δp/p`，不需要乘以任何杠杆系数。如果回测中 PnL 公式包含 `sqrt(leverage)` 或 `leverage` 乘数，那是一个会让结果虚高数十倍的严重 bug。这个 bug 曾把一个真实 CAGR ≈ 0% 的策略包装成 CAGR +147%。
21. **有效费率反推是最快的 fee model 验证方法** — `effective_bps = median(|fee|) / median(notional) × 10000`。如果计算出的有效费率 < 交易所最低档公告费率（如 Binance VIP0 taker 4.5bps），fee model 几乎一定有 bug。不需要逐行审计代码，一个数字就能暴露问题。
22. **Commission sweep 是策略真实性的石蕊测试** — 在 1bps 到 5bps 之间以 0.5bps 步长 sweep commission，画 CAGR 曲线。健康的策略应在 3-5bps 区间仍保持正 CAGR。如果 CAGR 在 2-3bps 之间由正转负，说明策略全部"alpha"来自 fee 假设，不是真正的信号。
23. **条件因子 ≠ 方向因子** — volume anomaly、wick rejection、volatility compression 这类因子检测"有趣的市场状态"但不预测价格方向。对 long-only 策略完全无效（真实案例：6 个条件因子全部产生负 CAGR）。方向性因子（momentum, BTC-relative strength, trend quality）才能预测"做多会赚钱"。
24. **Score threshold 是被低估的超参数** — 因子得分的入场阈值对收益影响巨大。实测中 threshold 0.30 → 9073 trades, CAGR +0.3%；threshold 0.50 → 4487 trades, CAGR +13.3%。交易数量减半但 CAGR 翻 40 倍。原因：低质量交易的手续费会侵蚀高质量交易赚来的 alpha。
25. **回测性能优化的两个关键模式** — (a) 对时间序列数据用 `pd.merge_asof()` 预计算对齐，避免 per-bar 的 pandas 过滤查找（真实案例：从 timeout 降到 78 秒）；(b) 因子得分用缓存+冷却间隔（如 24h 重算一次），避免每根 bar 对所有标的重算全部因子。
26. **全仓模式下爆仓是全账户事件** — 一个仓位的暴亏会吃掉所有仓位的保证金。回测如果把每个仓位当作独立逐仓处理（只关心单个仓位的 PnL），会严重低估尾部风险。真实场景：3 个各占 30% equity 的 long 仓位，其中一个跌 15%，在全仓模式下总 equity 损失 4.5%，可能触发全账户清算。"伪全仓"回测只会清算那一个仓位。
27. **插针是加密市场的常态，不是异常** — BTC 在 2021-2024 年间多次出现 5min 内下跌 10%+ 后 V 型反弹。如果回测只用 close 判断清算和止损，这些插针对回测完全不存在。实盘中你的仓位会被清算，然后眼看价格弹回。使用 bar 的 high/low 做极端价格检查是最低限度的保护；用 OHLC 路径顺序模拟（阳线 O→L→H→C，阴线 O→H→L→C）则能正确处理同一根 bar 内止盈和止损的优先级。
28. **Available Balance 是隐形的开仓限制** — 全仓模式下，已有仓位的 initial margin 会锁定一部分 equity。如果回测不追踪 available_balance，会出现"幽灵杠杆"：总敞口远超实际可用保证金，回测结果看起来很好，但实盘根本无法复制这些交易（开仓被交易所拒绝）。
29. **Funding Rate 的频率和幅度都不能假设** — 不同交易所、不同交易对的 settlement 周期各异（8h/4h/1h），极端行情时 funding rate 可以从正常的 0.01% 飙升到 0.1%+。用固定值（如"每次 0.01%"）做回测会严重低估持仓成本。必须使用交易所 API 提供的历史 funding rate 数据（如 ccxt 的 fetchFundingRateHistory），且按交易对实际的 settlement 频率扣除。
30. **回测日志 append 到旧文件是版本对比的噩梦** — 你跑了 20 次参数 sweep，结果全混在一个 trades.csv 里，哪些行属于哪次运行？无法区分。每次运行必须生成独立文件，文件名包含时间戳和关键配置标识。两周后你要回溯"上周那个好结果用的什么参数"，靠的就是文件名和 summary.json 里的配置快照。
31. **"为什么没有交易"比"为什么交易了"更难调试** — 回测跑出来 30 天只有 2 笔交易，问题在哪？如果只有 trade log，你只能看到那 2 笔交易的信息。但真正需要知道的是：其他时间策略在干什么？信号触发了但被什么条件拦截了？是阈值太高、保证金不足、还是冷却期？没有 decision log（记录每次"决定不交易"的原因），策略调试就是盲人摸象。
32. **回测审计全绿 ≠ 可以部署** — 这是最容易犯的认知错误。维度 0-6 全部通过只说明"回测引擎本身是准确的"，不代表"系统可以上线交易"。如果没有实盘执行器、没有交易所 API 集成、没有密钥管理、没有部署脚本、没有 README，距离"填上 API key 就能跑"还差整个实盘层。真实案例：一个项目的回测引擎经过 3 轮完整审计（费率、保证金、清算模型全部对齐交易所），用户以为可以部署了，结果发现根本没有执行器代码。这个盲区促使我们增加了维度 P（部署就绪度前置评估）。
33. **单元测试的 BacktestConfig 默认值陷阱** — 写回测引擎的单元测试时，如果不显式设置所有影响结果的 config 字段（如 max_position_per_coin, max_gross_leverage），默认值会悄悄截断仓位，导致测试结果与预期不符但不报错。更隐蔽的变体：单币种 top_n=1 + bottom_n=1 无法测试仓位翻转（short 覆盖 long），需要 2+ 币种才能正确测试 turnover 和 fee。教训：测试中必须显式设置所有会影响被测逻辑的参数，不能信赖默认值。
34. **实盘执行假设必须在回测中有镜像** — 如果实盘用"先 limit 超时后 market"的下单策略（entry 50% maker / 50% taker），回测的 fee model 也必须反映这个假设。反过来，如果回测假设了某种 fee split，实盘的下单逻辑也必须与之匹配。这种双向对齐经常被忽视——人们习惯从实盘→回测单向检查，忘了回测→实盘也需要验证。
35. **Wick MR 和 Close MR 的 gap 可以超过 6 倍** — 真实案例（2025-10-10）：BTC 闪崩导致一根日 bar 的 wick margin_ratio = 0.929（接近爆仓），但 close margin_ratio = 0.123（非常健康）。Gap = 0.806。这说明：(a) 日频 bar 的 wick 极端高估实时监控会看到的压力，因为 wick 可能只持续几分钟；(b) 在回测中用纯 wick MR 触发减仓（blend=1.0）会导致严重误判，本来能赚 $700K 的 bar 变成亏 $2.4M；(c) 推荐回测用 blend=0（纯 close），实盘用实时 API MR。这个 gap 是设计回测 vs 实盘减仓策略时最关键的认知。
36. **静态杠杆上限 + 实时 MarginMonitor 是互补而非替代的两道防线** — 静态杠杆上限（如 3.05x）保护已知的历史最差 wick；MarginMonitor（soft=0.5, hard=0.7）保护未知的未来黑天鹅。两者缺一不可：(a) 没有静态限制，MarginMonitor 会频繁触发，每次都有减仓成本和滑点，侵蚀长期收益；(b) 没有 MarginMonitor，当出现超过历史极值的 wick 时没有任何自适应防御。正确的架构：静态限制负责"日常安全"，MarginMonitor 只在极端情况下作为最后防线触发。如果 MarginMonitor 在回测中频繁触发（>2次/年），说明静态杠杆上限设得太高。
37. **Margin-Ratio 减仓和 Drawdown 减仓是完全不同的东西** — Drawdown 减仓（equity 从峰值回撤 X% 时减仓）几乎一定降低长期 CAGR，因为它在最差时点减仓，之后市场反弹时仓位小了。Margin-Ratio 减仓只在保证金接近爆仓线时触发（频率极低，可能整个回测期 0 次），目的不是"控制回撤"而是"防止死亡"。不要因为之前测试过 drawdown 减仓效果不好就拒绝所有自动减仓机制——这两个机制的触发条件、触发频率、设计目标完全不同。
38. **全仓模式下杠杆影响持仓规模而非 PnL 放大倍数** — 在 HL 全仓模式中，target_leverage 控制的是 position_notional / equity 的比例（即你把多少 equity 暴露在市场中），而不是交易所的杠杆倍数设置。PnL 公式始终是 notional × Δp/p。3.05x target_leverage 意味着你的总仓位名义价值是 equity 的 3.05 倍。这与"交易所杠杆设为 3x"是两回事——交易所杠杆只影响 initial margin 要求。容易搞混的原因是：在逐仓模式下杠杆确实直接影响 PnL 放大，但全仓模式不是这样。
39. **Equity 增长后保证金率会自然恶化** — 随着策略赚钱，equity 从 $10K 涨到 $2.9M，持仓 notional 也等比增长（保持同样的 target_leverage）。但大 notional 进入交易所的高档位保证金（如 HL 的阶梯 MMR），导致同样的 weights 在高 equity 时 margin_ratio 更高。真实案例：在 $10K equity 时 3.05x 杠杆的 margin_ratio ≈ 0.05（极安全），但在 $2.9M equity 时同样的杠杆 margin_ratio 上升到 0.12+。这意味着策略成功本身会增加爆仓风险，必须在回测中用阶梯 MMR 正确模拟，不能用固定 MMR。
40. **Bear regime 零仓位是真正的 alpha** — 如果回测数据显示 bear 市交易是净亏损的（即使是做空），最优策略可能是 bear 期间完全空仓（regime_leverage_bear = 0.0）。这不是"躲避风险"——它实际上同时提升了 CAGR（+10pp）和降低了 MaxDD，因为避免了 bear 市中动量因子反转带来的系统性亏损。这个发现的前提是：strategy 有可靠的 regime 检测机制。如果 regime 检测不准，零 bear 仓位可能错过 V 型反弹。
41. **轮询式 MarginMonitor 无法防御瞬时闪崩** — 这是一个必须清醒认知的局限。即使 MarginMonitor 每 15 秒轮询一次，如果 wick 在 3 秒内触及最低点又弹回（加密市场常见），monitor 可能完全看不到 MR 峰值。真实案例：2025-10-10 wick MR=0.93，但这个极端值可能只存在了几秒。MarginMonitor 真正擅长防御的是"缓慢恶化"场景（连续多天阴跌，MR 从 0.3 逐步升到 0.7）。对于瞬时闪崩，唯一可靠的防御是静态杠杆上限（确保即使历史最差 wick 也不爆仓）。架构含义：(a) 不要依赖 MarginMonitor 作为唯一防线；(b) 静态杠杆上限要留足 buffer（如 MR=0.93 时的 3.05x，而不是 MR=0.999 的 3.10x）；(c) MarginMonitor 是补充保护（处理超越历史的缓慢恶化），不是主要保护。
42. **供应链攻击的窗口可以短到 2 小时** — 2026-03 axios 事件：攻击者用窃取的 npm 凭证发布了含恶意 postinstall 脚本的版本，2-3 小时后就被下架了——但这个时间窗口足以感染所有在此期间运行 `npm install` 的 CI/CD 管道。对量化系统的启示：(a) 永远精确锁定依赖版本（`==` 而非 `>=`），不要自动拉取最新版；(b) `npm ci --ignore-scripts` 或 `pip install --no-deps` 在自动化环境中是基本功；(c) 新版本发布后至少等 24-48 小时再更新，因为大部分恶意包在发布后 24 小时内会被检测和下架。
43. **幽灵依赖是供应链投毒的典型手法** — axios 攻击中，恶意代码不在 axios 自身，而是通过新增一个"幽灵依赖"（`plain-crypto-js`）注入——该包在代码中从未被 import，唯一目的是触发 postinstall 脚本下载 RAT。审计时必须检查：manifest（package.json/requirements.txt）中的每个依赖是否真的被代码引用。用不到的依赖 = 潜在攻击面。
44. **API Key 提现权限是量化系统最大的单点风险** — 如果 API Key 同时有 trade + withdraw 权限，一旦密钥泄露（通过供应链攻击、日志泄露、或 AI 对话上下文），攻击者可以直接提走全部资产。这比策略代码泄露严重得多——代码泄露只是知识产权损失，提现权限泄露是真金白银的损失。铁律：量化 bot 的 API Key 永远不开 withdraw 权限；如果交易所支持 IP 白名单，必须绑定。
45. **AI Agent 自主修改代码时是供应链风险的放大器** — alpha-lab 等 AI 研究循环会自主修改策略代码并运行回测。如果 AI 被 prompt injection 或恶意上下文影响（如读取了含恶意指令的"研究论文"），可能引入隐蔽的后门（如在特定日期触发异常交易逻辑）。防御：(a) AI 修改的范围限定在约定文件内（alpha-lab 已有此规则）；(b) 每次里程碑必须经过 code review；(c) `git diff --stat` 验证只改了预期文件；(d) 不要让 AI agent 读取 .env 或密钥文件。
46. **充值/提现会伪装成策略盈亏** — 如果实盘 bot 直接用 `new_equity - old_equity` 计算 PnL，任何充值都会被计为"盈利"，提现计为"亏损"。这不只是数字失真——它会导致仓位管理基于错误的 equity 做决策（如按 equity 百分比开仓时，充值后仓位会突然变大），回撤保护被错误重置（充值让 equity 创新高，drawdown 归零），实盘-回测对比完全失去意义（回测不存在充提）。防御：维护 `adjusted_equity = raw_equity - cumulative_transfers`，所有下游计算（PnL、drawdown、position sizing）必须基于 adjusted_equity。更隐蔽的资金流还包括：funding fee 结算、空投、跨账户划转、手动交易——这些需要通过交易所 income API 分类识别。
47. **日志不隔离 = 版本对比是盲猜** — 实盘 bot 如果所有 session 写同一个 `bot.log`，你无法回答"v2.3 和 v2.4 哪个表现好"这种基本问题。更隐蔽的问题：只记录了交易但没记录"为什么没交易"（trade_skipped），导致"那段时间为什么没开仓"永远是个谜。同样危险的是不记录启动时的完整 config——两周后你想复现某次好的表现，却不知道当时用的什么参数。正确做法：每次启动创建独立的 `.jsonl` 文件，文件名含策略版本+时间戳+session_id；启动时 dump 完整 config 和 git hash；每个决策周期记录 trade_executed 和 trade_skipped；关机时记录原因和 session 汇总统计。这套日志不只是用来排错——它是策略迭代的数据基础。
48. **每个策略的 state 格式不同 = 监控中心的噩梦** — 真实案例：三个策略（Alpha/Beta/Polymarket）的 equity_history 格式完全不同——Alpha 是无时间戳的 float deque，Beta 是带时间戳+transfers 的 dict 列表，Polymarket 只有短窗口 float 列表。监控中心不得不为每个策略写独立的 collector，新增策略的接入成本极高。解决方案：定义统一的 Monitor Protocol——每个 bot 旁路输出一个标准格式的 `monitor_export.json`（不改动 bot 内部的 state 文件），包含 identity、equity（必须是 transfer-adjusted）、positions、health、equity_history（必须带 ISO 8601 时间戳）。关键要求：(a) equity.current 必须是扣除充提后的 adjusted equity，不是 raw balance；(b) equity_history 必须带时间戳，否则无法重建时间轴；(c) 写入必须 atomic（tmp + os.replace），防止监控中心读到半截文件；(d) 旁路导出，export 失败不影响主策略逻辑。
49. **交易对下架防御的关键是公告监控而非 API 状态检查** — 等到交易所 API 中 symbol.status 变成 SETTLING/PRE_DELIVERING 时，流动性已经枯竭，滑点巨大，你已经在被动应对了。真正有价值的防御窗口是公告发出的那一刻（提前 7-30 天），此时市场流动性完全正常，可以从容退出。正确的三层纵深架构：(a) 第一层（核心）：定期抓取交易所公告，用 LLM 解析是否影响持仓标的，提取截止时间和建议操作——这是投入产出比最高的防线，提前期最长，退出成本最低；(b) 第二层（安全网）：API 状态定期检查 + 异常信号检测（OI 骤降、订单簿收窄），兜底第一层遗漏的情况；(c) 第三层（最后防线）：订单被拒时的优雅处理，确保 bot 不会因为单个标的的问题而整体崩溃。平仓时机也应智能化：距离 deadline > 7 天时只需禁止开仓等自然退出；3-7 天时在下次 rebalance 主动平仓；< 3 天才需要立即操作。不要一检测到就 market order 紧急平仓——这是把从容的 7 天窗口浪费成了恐慌的 7 秒。
50. **Strategy Deployment Gap：research 完成 ≠ 部署完成** — 2026-04-10 真实案例：R4 信号引擎在 Alpha Lab 完成 21 轮实验验证（WR 57.6%, CAGR >>1000%），代码已合并到仓库，但 bot.py 仍在调用旧的 V20 信号引擎（CAGR 仅 217%）。实盘持续亏损数周，所有排查都聚焦在执行层面（手续费、fill rate、滑点），没人想过"我们根本没有在跑那个好策略"。根因：Alpha Lab 的产出（独立模块 + config JSON）和实盘的接入（bot.py 信号流）之间没有任何自动化的桥接检查。代码合并 ≠ 信号流接入 ≠ 实盘生效。每次 Alpha Lab 产出新的 champion，必须有一个显式的"部署到实盘"步骤，并在部署后验证实盘确实在调用新引擎。
50. **锚定效应会让你在错误的层面排查数周** — 当实盘亏损时，人的第一反应是"执行有问题"（手续费算错了、fill rate 太低、滑点太大）。如果第一次排查确实发现了一些执行层面的小问题（费率不精确、gas 成本被低估），锚定效应会加强——你会更加确信"就是执行的问题"，然后在这个方向上越走越深。但真正的根因可能完全在另一个层面：你跑的就不是那个好策略。教训：实盘亏损排查的第一步不应该是查执行，而应该是确认"我们在跑哪个策略，它是不是仓库里最好的那个"。
51. **Research 到 Production 的"最后一公里"需要正式 checkpoint** — 量化系统的 R&D 流程（idea → 回测 → Alpha Lab 验证 → champion config）和部署流程（config → wire into bot → integration test → paper trading → live）之间存在天然断层。R&D 的交付物是"一个 JSON config + 一组独立模块"，但部署需要的是"bot.py 中的信号流改动 + 冷启动适配 + 风控集成"。这个 gap 不会自动弥合。必须有一个显式的 deployment checklist（就像 r4_champion_config.json 中的 deployment_checklist），且每次 review 时必须检查这个 checklist 的完成状态。
