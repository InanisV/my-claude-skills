# Polymarket 实盘下单 13 步全链路参考

本文档是 SKILL.md 中"执行链路审计"的详细参考。审计时按需读取。

## 13 步执行链路

```
[1] Signal    →  [2] Risk Check  →  [3] Market Discovery  →  [4] Mid-Price
    ↓                                                            ↓
[5] V32 Gate  →  [6] Sizing     →  [7] FOK Submit         →  [8] Position Record
                                                                  ↓
[9] Wait Settlement  →  [10] Reconciliation  →  [11] Dead Token  →  [12] Queue
                                                                        ↓
                                                               [13] Chain Redeem
```

### Step 3: Market Discovery (78-85% success, 2-8s)

**功能：** 通过 Gamma API 搜索匹配的 Up/Down 二元期权市场
**失败原因：**
- 没有当前时间段可交易的 5min 市场
- API 超时（尤其是高峰期）
- 市场已过期但 API 未及时更新
**回测差异：** 回测假设 100% 可用

### Step 4: Mid-Price Lookup (62-68% success, 200-800ms)

**功能：** 查询 orderbook 获取 bid-ask 中间价
**失败原因：**
- Orderbook 为空（无做市商）
- Spread > V32_MAX_ORDERBOOK_SPREAD (0.50)
- 做市商在 p≈0.50 时因高费率不愿做市
**回测差异：** 回测假设固定价格 (contract_price + spread)

### Step 5: V32 Gate (71-82% success, 1-2ms)

**功能：** 验证 token price 在合理范围内，EV > min_ev
**失败原因：**
- token_price 超出 [V32_TOKEN_PRICE_MIN, V32_TOKEN_PRICE_MAX]
- 模型 confidence 与市场 price 偏差 > max_divergence
- 真实 EV（用市场价计算）< min_ev
**回测差异：** 回测 EV 用简化公式计算，通常更乐观

### Step 7: FOK Submit (87-93% success, 800ms-2.5s)

**功能：** 向 Polymarket CLOB 提交 Fill-or-Kill 市场单
**失败原因：**
- 可用流动性不足（5min 市场接近到期时尤其严重）
- API 速率限制（3,500 orders/10s burst）
- Cloudflare 拥堵导致请求排队
- 3 秒强制等待期间价格变动
**回测差异：** 回测用固定概率模拟（通常 26%），不考虑流动性动态

### Step 13: Chain Redeem (91-97% success, 7-40s)

**功能：** 在 Polygon 链上赎回已结算的 token
**失败原因：**
- Polygon RPC 节点拥堵
- Gas 费飙升（可能需要 3x 正常 gas）
- 合约调用失败需重试
**成本：** $0.15-0.30 per redemption
**回测差异：** 回测假设免费、即时、100% 成功

## Polymarket 5 分钟市场特征

### 基本信息
- 资产：仅 BTC（截至 2026 年 4 月）
- 结算周期：每 5 分钟创建新市场
- 日交易量：$60M+
- Oracle：Chainlink Data Streams（非 UMA）
- 结算方式：自动，无争议窗口

### 费率（Crypto 分类）
- Base rate：0.072 (7.2%)
- 公式（collateral 口径）：`fee = collateral × 0.072 × (1 - price)`
- p=0.50 时费率：3.60%
- 仅 Taker 付费，Maker 免费 + 返佣

### 订单类型
- GTC（Good-Til-Cancelled）：默认 limit order
- GTD（Good-Til-Date）：带过期时间的 limit order
- FOK（Fill-or-Kill）：全额成交或取消，**有 3 秒延迟**
- FAK（Fill-and-Kill）：部分成交 + 取消剩余

### 速率限制
- POST /order：3,500 req/10s burst
- CLOB 一般：9,000 req/10s
- 市场数据：1,500 req/10s

### 常见 gotchas
1. FOK 3 秒延迟 — 在 5min 窗口中占 1.7%
2. Spread > 0.10 时 displayed price 切换为 last trade price
3. 所有订单本质上都是 limit order（market order = 用市场价的 limit order）
4. Polygon 出块约 2 秒
5. 做市商在 p=0.50 时可能不愿提供深度（费率最高点）
