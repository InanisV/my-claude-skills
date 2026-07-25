> **quant-code-review · 维度参考文件** — 由 SKILL.md 按维度 P.3 的适用性裁定按需加载，不要无差别全量读入。
> 文中交叉引用（如"见 2.8"、"参见 4.6"）按维度编号到 references/ 对应文件查找。

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

#### 2.2.1 Next-Bar Entry 敏感度测试（可操作化协议）

**为什么必须测**：回测默认在 bar-T close 成交，但实盘信号形成于 bar-T 收盘，
真实成交最早只能发生在 bar-T+1 open。这一个 bar 的时间差在高波动加密市场里
可能是 ±2-5% 的价格漂移。如果策略的 alpha 完全来自"bar-T close 买入 →
bar-T close 平仓"这种 same-bar look-ahead 假象，它在实盘中会立即蒸发 —
所有执行链路修得再好都救不回来。

**实装范式（5 处改动即可覆盖多数 DCA / 趋势策略）**：

```python
# 1. Config 里加 flag（默认 False 仅为回归期保证 legacy 基线 bit-identical；
#    回归通过后，研究/生产运行必须 next_bar_entry=True — 与 2.13 的默认要求一致）
@dataclass
class BacktestConfig:
    ...
    next_bar_entry: bool = False

# 2. 在 backtest engine 内部定义 helper（与 get_val 并列）
def fill_base_price(sym, bar, fallback_close):
    """Return raw fill price (pre-slippage) honoring cfg.next_bar_entry.
    When True → bar+1 open; falls back to current-bar close on last bar
    / data gap.  When False → current-bar close (legacy)."""
    if getattr(cfg, 'next_bar_entry', False):
        nxt = get_val(sym, 'open', bar + 1)
        if not np.isnan(nxt):
            return nxt
    return fallback_close

# 3. 所有 entry site 替换成（保留原有 slippage 和 NaN 守卫）
# 原：entry_price = current_price * (1 + cfg.slippage)
# 新：entry_price = fill_base_price(sym, bar, current_price) * (1 + cfg.slippage)
```

典型需要替换的 entry sites：新开仓、DCA 加仓、BEAR DCA、plateau/overlay entry。
**信号决策价格不要改**，只替换成交价。

**敏感度判读阈值**：

| Δ CAGR（相对） | 判定 | 说明 |
|---:|---|---|
| < 5% | 🟢 PASS | 策略 alpha 与成交时点几乎无关，结构性稳健 |
| 5% – 20% | 🟡 YELLOW | 存在中度 entry-timing 敏感度，可以部署但要在实盘加仓/减仓策略中留出保守 buffer |
| 20% – 50% | 🟠 ORANGE | alpha 显著依赖 bar 内 timing，建议重新设计信号形成窗口 |
| > 50% | 🔴 FAIL | alpha 几乎全部来自 same-bar look-ahead — 实盘会立即崩溃，不要上线 |

**回归安全铁律**：next_bar_entry=False 必须与 patch 前的缓存结果 bit-identical。
如果 legacy mode 结果漂移了哪怕 0.01%，说明 helper 实装有 bug。务必对一次 baseline
确认 CAGR / MDD / Trades 三个数字都完全一致再继续。

**真实案例参考（crypto-factor-mining-alpha, 2026-04-17）**：
- 207-sym 扩展宇宙，V15_PROD champion（含 H1+H2）
- Legacy CAGR 10865.2% → next_bar CAGR 10797.9%
- Δ = -0.6% 相对 → 🟢 PASS，alpha 不是 same-bar lookahead

### 2.3 数据偏差

```
检查项：
- 是否有幸存者偏差（只用了当前存在的标的回测，忽略了已退市的）
- 是否有前视偏差（用了未来数据做决策）
- 数据是否有足够的样本外验证
- 不同市场周期（牛/熊/震荡）是否都覆盖
- 数据质量：缺失值、异常值、拆分/合并调整
```

#### 2.3.1 前视偏差专项排查（Lookahead Grep Battery）

前视偏差是回测虚高的第一大来源，且形式隐蔽多样。除 2.2.1（同 bar 成交）和
1.5（bar 时间约定）外，以下模式必须逐一排查：

```
□ 信号计算窗口包含当前未闭合 bar（rolling 窗口右端点 = 决策 bar）
□ 负向 shift：df.shift(-1) / .iloc[i+1] 出现在特征或信号路径
  （出现在 label 构造中是合法的，出现在特征中是 🔴）
□ 居中窗口：rolling(..., center=True) — 每个点都用了未来数据
□ 全样本统计泄漏：z-score / scaler 用整段数据 fit（对整个 df 做
  fit_transform），而非 expanding / rolling / 仅训练段 fit
□ 选币宇宙用全期指标：如"按 2 年总成交量排序选 top N" — 回测第一天
  就用了两年后的信息。正确做法：每个 rebalance 时点只用截至当时的数据
□ ML 特征/标签 off-by-one：label = ret[t+1] 但特征含 t+1 信息；
  train/test 随机 shuffle 切分（时间序列必须按时间切分）
□ 指标 warmup 期：前 N 根 bar 指标为 NaN 时是否被静默填充为
  "有信号"的值（fillna 方向错误）
□ 复权/拆分调整用"当前因子"回填历史（未来信息混入历史价格）

自动化探测：
grep -rn "shift(-" src/ | grep -v test        # 负向 shift
grep -rn "center=True" src/                    # 居中窗口
grep -rn "fit_transform\|scaler.fit" src/      # 全样本拟合
grep -rn "sort_values.*volume" src/            # 选币是否用全期统计

判定：任一命中且位于信号/选币路径 → 🔴（该回测结果作废，修复后全部重跑）
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

⚠️ 年化口径检查（crypto 24/7 市场）：
- CAGR / Sharpe 年化因子必须用 365（日频）/ 8760（小时频），不是股票的 252
  → 用 252 年化日频 crypto Sharpe 会低估 ~20%（sqrt(365/252)≈1.20），
    跨策略、跨资产对比时口径失真
- 收益序列频率与年化因子必须匹配（1h bar 用 sqrt(8760)，日频用 sqrt(365)）
- 有充提的实盘收益必须用 TWRR/MWRR（见 3.7），不能用 final/initial - 1
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

### 2.12 动态宇宙覆盖审计（Dynamic Universe Coverage Gap）

**问题陈述**：回测的 symbol universe 通常由一次性抓取脚本产出（如
`fetch_universe_full.py` 抓 2 年以上的所有永续合约），而实盘的 universe
每次选股时实时从交易所 API 读取。两边天然不同步：
- 回测 universe：数据抓取日前已上架且满足 seasoning 的标的（静态快照）
- 实盘 universe：当下交易所所有 trading 状态的永续合约（动态）

典型 gap 表现：live factor_scores 打分了 497 个标的，但 data/historical
目录下只有 180 个能跑回测 → **回测验证的 alpha 只是在潜在选股池 36% 的
子集里验证过**。H1+H2 / 新币鲁棒性 / 成熟度因子 这类"针对新老币区别"
的机制尤其危险 — 小池子里验过的结论不保证在大池子里成立。

**⚠ 这不是幸存者偏差**。幸存者偏差是"用当前存在标的 = 忽略已退市"，
是 TRUE NEGATIVE（把真实发生过的坏结果从样本里移除）。动态宇宙 gap 是
"回测看到的选股池比实盘小" — 是 COVERAGE SHORTFALL（没见过实盘会看到
的标的）。两者根因不同，验证方法也不同，必须作为独立审计项。

**自动化检测方法**：

```bash
# Step 1 — 量化 gap 比值
# 从 live state file 或最近一次实盘 log 中抽取 live_scored_symbols
LIVE_N=$(jq '.factor_scores | length' live_state.json 2>/dev/null || echo "?")
# 数 data/historical 目录下回测可用的唯一 1h symbol 数
BT_N=$(ls data/historical/*.parquet | grep -E '_1h' | sort -u | wc -l)
GAP_RATIO=$(python -c "print(round($LIVE_N / max($BT_N, 1), 2))")
echo "live=$LIVE_N  backtest=$BT_N  ratio=$GAP_RATIO"

# Step 2 — 找出实盘有但回测没有的 symbols
comm -23 <(jq -r '.factor_scores | keys[]' live_state.json | sort) \
         <(ls data/historical/*_1h*.parquet | sed 's#.*/##; s/_1h.*//' | sort -u) \
         > missing_symbols.txt
```

**判读标准**：

| gap ratio (live / backtest) | 判定 | 说明 |
|---:|---|---|
| ≤ 1.1 | 🟢 PASS | 覆盖几乎完整 |
| 1.1 – 1.5 | 🟡 YELLOW | 存在适度 gap，多数情况下是近期上架的新币还未回填；列出缺失清单 |
| 1.5 – 2.0 | 🟠 ORANGE | 显著 gap，必须在部署前补齐并重跑 k-fold |
| > 2.0 | 🔴 FAIL | 严重 gap — 回测验证的只是选股池的少数子集，alpha 可能不具代表性 |

**gap 闭合流程**：

1. 用 `fetch_universe_full.py --min-days N`（或等价工具）补齐 missing_symbols.txt
   中的所有 seasoning 通过的标的 → 预期 backtest_n 显著上升
2. **重跑 k-fold 验证**：champion 配置与 baseline 配置在扩展 universe 上
   各自跑一轮（最好按 listing age 做 time-stratified 5-fold）
3. **严格优势 criterion**：champion 必须在每一折 test 上同时满足：
   - ΔCAGR > 0（vs baseline）
   - ΔMDD ≥ 0（less negative is better, or equal）
4. 如果任何一折违反严格优势 → 原 champion 是 small-universe 过拟合产物，
   必须重新搜索 / 降参数 / 引入更鲁棒的因子

**baseline 配置**：必须显式构造，不能继承 live profile。因为 live profile
可能已经含有 champion 的改动（H1/H2/maturity factor 等）。正确做法：从
research starting point（pre-improvement baseline）出发，只保留要比较的
基础配置，**显式禁用**新加的特性。

典型错误：`baseline_expanded = {}` （空 overrides 继承 V15_PROD canonical） →
baseline 与 champion 结果完全相同 → 看不到 alpha 贡献。

**残留 gap 的处理**：部分 missing symbols 可能因为 seasoning 不够
（listing < min_listing_hours）或上币太晚（< min_days）注定无法纳入回测。
这些残留在报告里标注清楚即可，不影响判决 — 实盘 min_listing_hours 门控
会自然过滤掉它们。

**真实案例参考（crypto-factor-mining-alpha, 2026-04-17）**：
- Live 打分 universe: 497 symbols
- 回测 universe (pre-fix): 180 symbols
- Gap ratio = 2.76 → 🔴 FAIL
- 运行 `fetch_universe_full.py --min-days 730` 补齐 39 个缺失币种
- 回测 universe (post-fix): 207 symbols → gap 2.40（仍 ORANGE，剩余 290
  为近期上市 < 730 天新币，自然被 seasoning 门控过滤）
- H1+H2 champion 在 207-sym 5-fold 上每一折严格优势 baseline：
  ΔCAGR +694 ~ +2216 pp, MDD 每折都改善 → 通过扩展宇宙再验证

---

### 2.13 回测真实性 Flag 审计（Backtest Realism Flag Audit）🔴 高优先级

> **背景故事**：2026-04-19 V15_PROD 实盘 cross-margin cascade -73.8%。事后追因发现：
> 4/13 V37 时期把 `use_liquidation_check` 设为 False 写入 V15_PROD profile，注释只有
> "V37: disabled (backtest-only)" 五个字。此后 6 天的所有"研究突破"
> （V37 Global Optimum CAGR 5459%、H1+H2 champion fDD -37.7%）都是在 cascade 不模拟
> 的虚假世界里算出来的。同一个 H1+H2 配置开启 use_liquidation_check=True 重跑：
> CAGR 10865% → 8801%，**fDD -37.7% → -79.1%**（与实盘 -73.8% 同量级）。
>
> 关键洞察：**回测引擎里"实现存在"≠"实验启用"**。维度 2.8 检查的是"有没有 cascade
> sim 实现"，但即使实现完美，也可能被一个 flag 默默关掉。真正的实验脚本里这个 flag
> 是 True 还是 False，要单独审计。

**为什么必须单独成维度**：
- 维度 2.8 解决"实现层"问题：cross margin sim 写得对不对
- 维度 2.13 解决"启用层"问题：跑回测时这些 sim 真的开了吗
- 这两个问题正交，全 pass 维度 2.8 也可能 cascade liquidates 不被模拟
- 4/19 之前的 backtest engine review (90/90 tests pass) 没覆盖这层，是审计盲区

**所有真实性相关 flag 清单**（典型量化项目）：

| Flag | 关掉的后果 | 默认应为 |
|---|---|---|
| `use_liquidation_check` | cross-margin cascade 不模拟，MaxDD 严重低估 | True |
| `use_wick_check` | intra-bar wick 不触发 stop-loss / liquidation，MaxDD 低估 | True |
| `use_funding_cost` | 持仓成本不扣除，长持仓策略 CAGR 严重高估 | True (合约策略) |
| `use_slippage` | 成交价等于 mid price，高频/小币种策略 CAGR 高估 | True |
| `use_partial_fill` | 默认全成交，流动性差的币种容量假设失真 | 视项目而定 |
| `next_bar_entry` | 同 bar 信号同 bar 成交 → look-ahead bias | True（研究/生产结论必须基于 True；仅 legacy 引擎回归基线期可暂为 False，见 2.2.1 回归铁律） |
| `use_realistic_spread` | 假设无买卖差价，做市/HFT 策略尤其失真 | True |

**审查清单**：

```
□ 2.13.1 自动化扫描所有 backtest 脚本
   □ grep `backtest_scripts/` 找出所有 use_*_check / use_*_simulation /
     use_*_cost / next_bar_entry 的实际值
   □ 输出表格：脚本路径 × flag × 值 × 是否对照 default
   □ 任何被设为 False/disabled 的实验性脚本，标记为 ⚠️
   □ 任何被设为 False 的 production profile，标记为 🔴

□ 2.13.2 ProductionProfile vs ResearchScript 一致性
   □ 同一个 flag 在 production profile 和研究脚本里必须一致
   □ 例：V15_PROD 里 use_liquidation_check=False，那研究脚本也应该 False
     才能解释生产数字；或者研究是 True 但生产也应改 True
   □ 不一致 → 🔴（"用 True 算出来的数字部署到 False 的环境去跑"或反之）

□ 2.13.3 关闭 flag 必须带技术理由
   □ 任何 use_*_check=False 的设定必须有 inline comment 引用 commit hash
   □ 该 commit 必须包含至少一个对照实验（开/关该 flag 的同时运行结果）
   □ 缺乏技术理由 → 🔴 关键问题
   □ 反模式识别：注释只有 "disabled"、"backtest-only"、"deprecated" 等
     不解释 why 的字眼 → 🔴

□ 2.13.4 Flag 关闭后的"突破数字"必须重新验证
   □ 如果发现某轮研究使用了 use_*_check=False，所有该轮产出的"champion 配置"
     必须在 use_*_check=True 下重跑后才能进入决策
   □ 重跑结果如果 MaxDD 恶化 > 10pp，原 champion 称号失效，须重新评估
   □ 真实案例：H1+H2 fDD -37.7% (False) → -79.1% (True)，差距 41.4pp，
     champion 称号应被撤销

□ 2.13.5 "Safety mechanism by hiding the alarm" 反模式识别
   □ 检查 git log 和注释里有没有这种模式：发现某种回测失败 → 关掉模拟
     而不是改策略
   □ 真实案例：run_safety_sweep.py 注释 "12 个 safety mechanism 候选" 中
     第 9 个 "Liquidation disabled" — 这是把"看不到"当成"安全"，必须
     标记为 🔴 反模式
   □ 类似句式："改了之后 cascade 就不发生了" 如果改的是模拟开关而非策略
     行为 → 🔴

□ 2.13.6 "高 CAGR 自动触发 cascade 频率检查"门控
   □ 任何回测 CAGR > 3000% / Calmar > 100 / MaxDD < -40% 的"突破"，
     必须在报告中显性给出：
     - liquidation_events 总数与年化频率
     - cascade 发生时的 universe 状态
     - use_liquidation_check 的实际值
   □ 如果上述三项缺一，🔴 拒绝标记为"突破"
```

**自动化脚本**：`scripts/audit_cascade_simulation.py`（skill 内置，**单一真相源** —
含 use_intra_bar 等扩展 flag、production/research 路径分级）：

```bash
python scripts/audit_cascade_simulation.py /path/to/project
# exit 0 = OK / 1 = WARN (research 脚本有 False) / 2 = CRITICAL (production profile 有 False)
```

**红线（不可妥协）**：
1. 任何 production profile 里 use_liquidation_check=False → 🔴 立刻修
2. 任何 research script 里 use_liquidation_check=False 且基于其结果做了部署决策 → 🔴 重跑
3. 任何"safety mechanism"候选包含关闭模拟 flag → 🔴 拒绝该候选

### 2.14 过拟合与参数稳健性（Champion 验收门槛）

**为什么必须有这个维度**：alpha-lab 式研究循环会产出大量实验，"champion 配置"
往往是几百次尝试中的最优点。搜索次数越多，最优点纯属运气的概率越大（多重检验
问题）。2.12 的 k-fold 覆盖了 universe 维度，本节覆盖参数与时间维度。

```
□ 2.14.1 参数邻域扰动测试（champion 部署前必跑）
   □ 对 champion 的每个关键连续参数做 ±10-20% 扰动（至少覆盖：入场阈值、
     窗口长度、杠杆/sizing 系数、止盈止损位），逐一重跑回测
   □ 判定：
     - 邻域内 CAGR 平缓变化（任一扰动后仍为 champion 的 50% 以上）
       → 🟢 稳健（真实 alpha 在参数空间中是"高原"）
     - 任一 ±10% 扰动使 CAGR 跌超 50% 或转负 → 🔴 尖峰过拟合，
       champion 大概率是噪声最优点，不可部署（过拟合是"针尖"）

□ 2.14.2 时间切片一致性
   □ per-year（或 per-quarter）收益分解：champion 的超额收益是否集中在
     单一时段？
   □ 超过 70% 的超额收益来自不到 20% 的时间 → 🟡 检查该时段是否为
     不可复现的市场结构（如某次极端行情、单一币种暴动）
   □ champion vs baseline 必须在多数年份占优，而非靠一年翻盘

□ 2.14.3 多重检验意识（实验记录审计）
   □ 从实验日志统计本轮研究总共尝试的配置数 N_trials；报告缺失该数字 → 🟡
   □ N_trials 越大，"最优结果"的期望虚高越严重（√(2·ln N) 量级），
     champion 的样本外优势必须显著超过该量级才可信
   □ 实操代理指标：top-10 配置的参数是否聚集在同一邻域？
     - 聚集（高原）→ 结构性 alpha；分散在参数空间各处 → 挑出来的运气

□ 2.14.4 与既有检查的联动（champion 四重验收）
   □ 2.12：扩展 universe k-fold 严格优势（universe 维度）
   □ 2.13：champion 数字必须来自 realism flags 全开的运行（真实性维度）
   □ 2.2.1：next-bar entry 敏感度 ΔCAGR 相对值 < 20%（执行时点维度）
   □ 2.14.1-2.14.3：参数/时间稳健性（本节）
   四重全过，champion 才进入部署流程（由 1.4 部署缺口检查接棒）
```
