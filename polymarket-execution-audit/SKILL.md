---
name: polymarket-execution-audit
description: |
  Polymarket 二元期权交易系统审计专家 — 专注于回测引擎与实盘系统之间的差异检测。
  覆盖 Polymarket 特有的 CLOB 下单链路、动态费率、市场匹配、FOK 执行、结算语义等环节。

  触发时机（宁可多触发也不要漏触发）：
  - 用户提到"Polymarket"、"二元期权"、"binary option"、"CLOB"、"prediction market"
  - 用户说"审计回测"、"回测不准"、"实盘亏损"、"backtest vs live"、"为什么实盘亏钱"
  - 发现回测结果与实盘表现有显著差异时
  - 修改了交易相关代码（手续费、仓位计算、信号生成、结算逻辑）后
  - 用户要求检查执行链路、下单流程、成交率、费率模型
  - 任何涉及 Polymarket 策略从回测到实盘部署的场景

  不要用于：纯策略研究/参数优化（用 alpha-lab）、通用代码审查（用 quant-code-review）、
  非 Polymarket 的交易所策略。
---

# Polymarket 二元期权系统审计

## 核心理念

Polymarket 二元期权交易与传统量化交易有本质区别。回测引擎通常会在多个维度上过度简化真实交易环境，导致**系统性乐观偏差**。每个环节偏乐观一点点，累积起来就差好几倍。

本 skill 基于 2 次深度审计（2026-04-05/06, 共 10 轮迭代）的经验总结，覆盖已发现的所有陷阱。

## 审计清单

按照以下顺序逐项检查。每个检查点标注了【严重度】和【典型影响】。

### Phase 1: 信号架构对齐检查 🔴

**这是最常见也最致命的问题。**

1. **信号代码一致性**
   - 回测信号生成函数是否与实盘代码**完全一致**？
   - 常见陷阱：研究阶段用独立脚本开发新信号（如 BB position），但忘记移植到 `src/` 实盘代码
   - 检查方法：`diff` 回测信号函数 vs 实盘信号函数，逐行对比
   - 【严重度：致命】如果信号架构不同，回测结果完全不可用

2. **因子计算一致性**
   - 回测因子计算（通常是 vectorized numpy）vs 实盘因子计算（通常是 incremental/streaming）
   - 重点检查：
     - SMA/EMA 的窗口长度和预热 (warmup) 期是否一致
     - RSI 计算方式（SMA vs EMA smoothing）是否一致
     - 因子标准化/clip 范围是否一致
   - 【严重度：严重】即使信号逻辑相同，因子值不同也会产生不同信号

3. **参数来源一致性**
   - 回测用的参数（kelly_base, thresholds, confidence levels）从哪里来？
   - 实盘用的参数从哪里来？（hardcoded? config file? backtest_optimal_params.json?）
   - 检查方法：列出所有关键参数，在回测和实盘中各查一次值
   - 【严重度：严重】参数不一致 = 运行不同的策略

### Phase 2: 手续费模型验证 🔴

**Polymarket 费率公式独特且容易搞错。**

4. **费率公式正确性**
   - Polymarket 官方公式（shares 口径）：`fee = shares × base_rate × price × (1-price)`
   - 转换到 collateral 口径：`fee = collateral × base_rate × (1-price)`
   - 其中 base_rate：Crypto=0.072, Politics=0.05, Sports=0.0375
   - **常见错误：** 使用 `collateral × base_rate × price × (1-price)`（多了一个 `price`）
   - 这个错误导致费率被低估 2.0-2.3 倍
   - 【严重度：严重】直接影响盈亏平衡胜率和 CAGR

5. **费率在 EV 计算中的体现**
   - EV gate 中的 cost 常数是否包含了正确的费率？
   - 常见错误：用一个小常数（如 0.001）近似费率，实际费率可能是 0.018
   - 导致 EV gate 过宽，放行了负 EV 信号
   - 验证方法：在 p=0.50 时，计算 break-even WR：
     - 正确应约为 53.8%（含 0.5% slippage + 3.6% fee）
     - 如果 break-even WR < 52.5%，说明费率计算有误
   - 【严重度：严重】

6. **Maker vs Taker 费率**
   - Polymarket：**仅 Taker 付费**，Maker 免费 + 获得 20-25% 返佣
   - 如果策略是 Taker（大多数量化策略都是），需要按 Taker 费率计算
   - 如果策略可以做 Maker（limit order），费率为零 + 返佣收入
   - 【严重度：中等】

### Phase 3: 执行链路审计 🔴

**Polymarket 下单有 13 个步骤，每步都可能失败。**

7. **端到端成功率**
   - 回测通常假设 ~90% 信号被执行（仅 FOK 拒绝）
   - 实盘实际成功率约 33-42%（市场匹配 78% × mid-price 可用 65% × V32 gate 76% × FOK 90% × 赎回 94%）
   - 检查回测是否模拟了以下拒绝场景：
     - [ ] 市场不存在/过期（15-22% 失败率）
     - [ ] Orderbook spread 过宽（32-38% 失败率）
     - [ ] Token price 超出 [min, max] 范围
     - [ ] EV gate 拒绝（18-29%）
     - [ ] FOK 无法全额成交
   - 【严重度：严重】回测可能高估执行率 2-3 倍

8. **下单延迟**
   - Polymarket FOK/FAK 订单有 **3 秒强制延迟** + 2 秒 Polygon 出块
   - 总延迟 ~5-8 秒 = 5 分钟窗口的 1.7%
   - 回测通常假设零延迟（同根 K 线信号和执行）
   - 对均值回归策略影响较大：延迟可能错过最佳入场点
   - 验证方法：在回测中用 `closes[i+1]` 的开盘价替代 `closes[i]` 作为入场价，观察 WR 变化
   - 【严重度：中等】

9. **FOK vs FAK 选择**
   - FOK（Fill-or-Kill）：全额成交或全部取消
   - FAK（Fill-and-Kill）：部分成交，取消剩余
   - 小额订单用 FOK 合理，大额可考虑 FAK 提高成交率
   - 【严重度：低】

### Phase 4: 结算语义验证 🟡

10. **结算参考价 vs 入场价**
    - Polymarket：`market_reference_price` vs `settlement_price`（市场创建时 vs 到期时）
    - 回测通常用：`closes[entry_bar]` vs `closes[settlement_bar]`（Bot 入场时 vs 结算时）
    - 对于 5 分钟市场：如果 Bot 在市场创建时入场，差异较小
    - 对于长 horizon 市场：差异可能导致胜负判定相反
    - 检查方法：确认实盘的 settlement_direction() 用哪个价格作为 entry
    - 【严重度：5 分钟市场中等，长 horizon 致命】

11. **VOID（平盘）处理**
    - Polymarket：相对变动 < flat_tolerance → VOID → 退还本金（扣费）
    - 回测：通常只比较 `>` 或 `<`，`==` 极罕见
    - 5 分钟市场中 VOID 概率更高（短时间 BTC 不动的概率更大）
    - 【严重度：低-中等】

### Phase 5: 赎回和链上成本 🟡

12. **赎回成本**
    - 每笔赢的交易需要链上赎回：Polygon gas $0.15-0.30/笔
    - 高频策略（50+笔/天）的赎回成本显著
    - 例：50笔/天 × 55% 胜率 × $0.20 = $5.50/天
    - 初始资金 $200 → 日均 2.75% 固定成本
    - 【严重度：小额高频策略高，大额低频策略低】

13. **赎回失败处理**
    - 链上赎回失败率 3-9%（Polygon RPC 拥堵时更高）
    - 失败的赎回需要重试（可能 3x gas）
    - 回测完全不模拟赎回成本和失败
    - 【严重度：中等】

### Phase 6: 数据与统计验证 🟡

14. **随机种子敏感性**
    - 如果回测用固定随机种子（常见于 FOK 拒绝模拟），需验证多种子下结果稳定性
    - 用 5-10 个不同种子运行，检查 CAGR 和 WR 的标准差
    - 如果 std(CAGR) > mean(CAGR) × 20%，结果不可靠
    - 【严重度：中等】

15. **样本量充分性**
    - 填单量（filled_trades）< 1000 时，WR 的置信区间较宽
    - WR=55% 在 1000 笔交易下的 95% CI 约 [52%, 58%]
    - 如果 break-even WR=53.8%，52% 下限可能已低于盈亏平衡
    - 【严重度：中等】

16. **前视偏差检查**
    - 检查因子计算是否使用了未来数据
    - 常见陷阱：`pd.Series.rolling()` 默认包含当前 bar（这通常是正确的）
    - 但某些自定义因子可能不小心用了 `[i+1]` 或 `shift(-1)`
    - 【严重度：致命（如果存在）】

## 数值验证模板

修改费率公式后，运行以下验证脚本（修改参数适配具体策略）：

```python
# 费率对比
for p in [0.50, 0.51, 0.52, 0.55, 0.58, 0.60]:
    wrong = p * (1-p) * 0.0624           # 常见错误公式
    correct = 0.072 * (1-p)              # Polymarket 官方 (crypto)
    print(f"p={p:.2f}: wrong={wrong*100:.2f}% correct={correct*100:.2f}% ratio={correct/wrong:.2f}x")

# Break-even WR
p = 0.515  # token entry price (with spread)
slippage = 0.005
fee_per_token = 0.072 * (1-p) * p
total_cost = slippage + fee_per_token
win_net = (1-p) - total_cost
lose_net = p + total_cost
be_wr = lose_net / (win_net + lose_net)
print(f"Break-even WR at p={p}: {be_wr*100:.2f}%")
```

## 报告模板

审计报告应包含以下章节：

1. **核心结论**（1-3 句话总结最严重的发现）
2. **致命问题**（任意一个可导致策略失效的问题，按影响排序）
3. **严重问题**（显著影响收益但不致命的问题）
4. **次要问题**（需要修复但影响较小）
5. **数值验证**（修正前后的对比数据）
6. **修复方案**（按优先级排列的具体代码修改）
7. **综合影响估算**（修正所有问题后的预期 CAGR 范围）
8. **行动建议**（P0/P1/P2 优先级）

## 经验教训（来自实际审计）

1. **不要相信 CAGR > 500% 的回测结果** — 先检查费率和执行率假设
2. **研究脚本和实盘代码一定要对齐** — 最常见的"实盘亏钱"原因是跑的不是同一个策略
3. **Polymarket 费率是 collateral × 0.072 × (1-p)** — 不是 collateral × 0.0624 × p × (1-p)
4. **实盘端到端执行率约 33-42%** — 回测假设的 90%+ 是严重高估
5. **5 分钟市场的 3 秒下单延迟是结构性约束** — 无法优化掉
6. **break-even WR ≈ 53.8%** — 策略需要 >55% WR 才有足够的安全边际
7. **赎回成本对小额高频策略影响显著** — $200 本金每天可能损失 2-3%
8. **每个环节偏乐观一点点，最终差距就是几倍** — 审计时要假设最坏情况
