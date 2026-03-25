---
name: quant-code-review
description: |
  量化交易系统代码审计 — 在每次重大代码改动后自动执行全面审查。
  覆盖七个维度：(0) 模块清单盘点，(1) 实盘/回测策略逻辑对齐，(2) 回测引擎真实性，(3) 实盘运维鲁棒性，(4) 状态持久化完整性，(5) 代码性能，(6) AI协作代码质量。

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
1. **定位项目关键文件**：找到回测引擎和实盘bot的主文件、配置文件
2. **理解策略架构**：识别项目使用的策略类型（趋势跟踪、均值回归、套利、做市等）
3. **维度零：模块清单盘点**：先用自动化方法扫出"回测有但实盘没有"的功能模块（这一步往往能发现最严重的问题）
4. **按六个维度逐项检查**：使用下面的checklist框架，适配到具体项目
5. **输出结构化报告**

## 审计流程

按以下六个维度顺序执行（从维度零开始）。每个维度是一个 checklist 框架，根据具体项目适配检查项。

---

## 维度零：模块清单盘点（最先执行）

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

---

## 输出格式

审计完成后，输出一个结构化报告：

```
## 审计报告

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

### 维度三：运维鲁棒性
[逐项结果]

### 维度四：状态持久化完整性
| # | 检查项 | 状态 | 备注 |
|---|--------|------|------|
| 4.1 | 状态完整性 | ✅/❌ | 缺失的字段列表 |
| 4.2 | 持久化频率 | ✅/❌ | 当前频率 + 风险窗口 |
| 4.3 | 数据一致性 | ✅/❌ | 原子写/版本兼容/精度 |
| 4.4 | 重启校验 | ✅/❌ | reconciliation 覆盖情况 |

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
