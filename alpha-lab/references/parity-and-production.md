> **alpha-lab · 参考文件** — 由 SKILL.md 按场景按需加载（何时读见 SKILL.md 的 Reference 索引表）。

# 数据真实性 / 实盘-回测对齐 / 研究代码 vs 生产代码

## 🔴 回测数据真实性铁律（Data Authenticity）

**回测引擎的一切假设都必须基于真实的历史数据，不能用合成数据、简化模型或
"差不多"的近似替代。数据不真实 = 回测结论不可信 = 部署必出事。**

这一铁律与"禁止投机取巧"互补：投机取巧是故意美化假设，数据不真实通常是
无意的疏忽或工程偷懒——但后果一样严重。

### 必须使用真实数据的六个维度

```
1. 价格数据（OHLCV）
   ✅ 必须使用交易所真实历史 K 线（Binance API / 第三方数据供应商）
   ❌ 不能用模拟生成的价格序列、随机游走、GBM 合成数据
   ❌ 不能用日线数据做分钟级策略的回测（粒度必须匹配实盘执行周期）
   → 验证方法：抽查回测数据中的极端事件（如 2022-05 LUNA 崩盘、
     2024-08-05 日元套利清算），确认价格走势与真实历史一致

2. 手续费 / 费率
   ✅ 必须使用回测起点时刻的真实 fee schedule（如 Binance VIP0 taker 4.5bps）
   ❌ 不能假设 0 fee 或 maker-only
   ❌ 不能中途改 fee 来美化结果（详见"禁止费率投机"）
   → 如果实盘账户有 BNB 抵扣或 VIP 折扣，回测仍用 worst-case 费率

3. Funding Rate
   ✅ 永续合约策略必须使用真实历史 funding rate 序列
   ❌ 不能假设 funding = 0
   ❌ 不能用固定值（如 0.01%/8h）近似——真实 funding 波动极大
   → 数据来源：Binance /fapi/v1/fundingRate 历史端点
   → 回测引擎按 8h 结算周期扣除 funding cost
   → 实盘必须有等价的 funding 归因模型（live: exchange income API;
     paper: 模拟 8h 结算扣费）

4. 成交量 / 流动性
   ✅ 因子计算用的成交量必须是真实历史量
   ❌ 不能假设无限流动性（尤其小币种）
   → 回测应模拟滑点（固定 slippage 是最低标准；基于成交量的动态滑点更好）

5. 标的宇宙 / 上市时间
   ✅ 必须使用交易所真实的上架/下架时间线
   ❌ 不能让一个 2024 年上线的币参与 2022 年的回测（look-ahead bias）
   ❌ 不能忽略已退市的币（survivorship bias）
   → 动态宇宙策略用 onboardDate 元数据做入池时间控制
   → 数据采集缺口 ≠ survivorship bias（详见案例库）

6. Wick / Intrabar 价格
   ✅ 止损 / trailing / 清算检查必须使用 bar 的 high/low（模拟 intrabar 极端价格）
   ❌ 不能只用 close 做风控判断（实盘中间价可能已经触发了止损）
   → 回测用 use_wick_check + bar_high/bar_low
   → 实盘必须实现等价的 intrabar exit 逻辑（用 signal_bar OHLC）
   → 如果实盘只能拿到 close，则回测也必须关闭 wick check 保持一致
```

### 数据真实性审计检查清单

**在每次 alpha-lab 研究的 Setup 阶段，必须完成以下检查：**

```
□ OHLCV 来源：确认回测数据来自交易所真实 API，不是合成/插值
□ 时间对齐：K 线时间戳用 UTC，和交易所 API 返回格式一致
□ Funding rate：确认有真实历史序列，且引擎按正确的结算周期扣费
□ Fee 设置：确认 commission 和 slippage 不低于实盘 worst-case
□ Universe timeline：确认币的入池时间基于真实 onboardDate，不允许 look-ahead
□ Wick 一致性：回测 use_wick_check 开关状态 = 实盘实际执行能力
□ 数据完整性：抽检 3-5 个知名事件（LUNA 崩盘、FTX 暴雷、BTC 减半后行情）
   在回测数据中的价格是否与公开记录一致
```

**如果任何一项不通过，研究不能启动。** 在假数据上跑出的冠军没有任何意义。


---

## 🔴 实盘-回测对齐铁律（Live-Backtest Parity）

**冠军参数在回测中表现好只是第一步。如果实盘代码和回测代码在任何维度上有偏差，
那回测结果就不代表实盘预期。这个偏差是最隐蔽的风险——测试可能全绿，
但生产路径和测试路径走的不是同一条路。**

### 必须对齐的八个维度

```
1. 参数值
   → profile 中的每一个 key 必须在 live BotConfig 上有对应的字段
   → 🔴 unknown key 必须 hard fail，不能 warning 后忽略
   → 测试：对 V15_PROD 的每个 key 断言 live 值 == profile 值

2. 决策路径
   → 回测用 bar_high/bar_low 做 wick exit → 实盘必须也拿 OHLC signal bar
   → 回测用 funding rate 扣费 → 实盘/paper 必须有等价归因
   → 回测按 score threshold 拒绝所有差币 → 实盘空 selection 必须清空，
     不能因为"保守"而保留上一轮选币

3. 数据窗口
   → f_maturity 需要 2880 bar 历史 → 实盘 coin_selection_lookback 必须 ≥ 2880
   → 如果实盘 lookback < 回测窗口，因子计算结果可能方向相反
     （实测：同一个成熟币，720-bar f_maturity = -0.36，2880-bar = +0.99）
   → 测试必须用生产级 lookback 值，不能用"方便测试"的长窗口掩盖问题

4. 执行模型
   → 回测用固定 slippage/commission → 实盘用 BBO limit-first + fallback market
   → 这个偏差目前无法消除，但方向已知（实盘 fee 通常 ≤ 回测假设）
   → 可接受，但需在研究报告中注明

5. 风控路径
   → 杠杆设置失败 → 实盘必须 fail-fast（拒绝下单 + 写 trade_skipped log）
   → MarginMonitor 减仓 → 必须先 cancel open orders 再 reduce
   → 回测启用的模块（wick, funding, leverage_sizing）→ 实盘不能静默忽略

6. 选币语义
   → "所有币低于阈值"在回测中 = 空仓（不开新仓）
   → 实盘必须区分"合法空选"（set selected=[]）和"计算失败"（保留旧选币）
   → 混淆两者会导致 H2 confidence-weighting 失效

7. Raw vs Shrunk Score 使用范围
   → 回测的 _cached_scores = raw（用于 exit、losscap、DCA gating）
   → H2 shrunk scores 只用于 top-N 选择
   → 实盘的 _factor_scores 必须 = raw，selection_scores = shrunk
   → 如果实盘 exit 路径误用了 shrunk scores，会和回测行为偏离

8. 状态恢复
   → 实盘重启后从 state.json 恢复 → 确认所有新增字段有 fallback 默认值
   → funding 累计、announcement hash、selection 缓存都要持久化
```

### 对齐审计时机

```
- 每次向 live profile 添加新 key 后 → 必须审计 live 是否实现了对应逻辑
- 每次修改回测引擎的 exit/entry 路径后 → 必须检查 live 是否有等价路径
- 每次 code review 时，"对齐"是独立于"正确性"的审计维度
- 🔴 unknown key 允许列表必须为空集。有例外 → 必须在代码和测试中注释为什么
```


---

## 🔴 研究代码 vs 生产代码语义鸿沟（Research vs Production Semantic Gap）

**研究代码和生产代码看起来都是 Python，但语义假设完全不同。
直接 wrap 研究代码做生产 = 必爆。**

### 研究代码的隐含假设

```
研究代码的"幸福路径"假设：
  ✅ 输出路径固定（OUT_PATH = REPO/research/foo.parquet）
  ✅ "OUT 存在就 skip"（缓存友好，但破坏可重跑）
  ✅ "全量重建" 是常态（增量？什么是增量？）
  ✅ 失败 = 抛异常 = 我看到 traceback = 调试
  ✅ "我手动跑"（人在场调试 + 无 cron 调度）
  ✅ 输出格式可以"改一下"（下游就一两个 reader，我直接改）
  ✅ 日志打 print 就行（我盯着看）
  ✅ universe / 时间窗 / fee 假设硬编码（research run 一致就行）
```

### 生产代码的硬约束

```
生产代码的现实：
  ❌ 可能要写多个路径（per-symbol / per-window / atomic）
  ❌ "OUT 存在就 skip" = cron 永远 no-op，必须破坏
  ❌ 增量必须支持（全量重建 cron 资源吃不消 / 时间窗不够）
  ❌ 失败 = 静默或响铃 = 没人看 = 必须分类 + 记录 + 触发 alert
  ❌ "无人值守" cron 调度 + 多机时钟漂移 + 网络抽风
  ❌ 输出格式是契约（10 个下游 reader 都依赖，改 = 全跑一遍）
  ❌ 必须结构化日志（journalctl 几个月后还要查）
  ❌ universe / 时间窗 / fee 必须从配置读，且要支持 hot-update
```

### 三个反模式（必须避免）

**反模式 1：subprocess 包装研究脚本**

```python
# ❌ 错误（R89.7 Phase 1 P0-4 的真实 bug）
def auto_refresh_v30_features():
    if V30_OUT.exists():
        V30_OUT.unlink()  # 突破"skip-if-exists"
    subprocess.run([sys.executable, "scripts/r63_build_v30_features.py"])
    # 生产现实：subprocess crash → V30_OUT 永久消失
    # 研究脚本不知道有 atomic 需求，写到一半也不会 cleanup

# ✅ 正确：要么 refactor 研究脚本，要么写新的生产 builder
def build_v30_features_for_production(out_path: Path):
    # 直接调用核心函数，写到 caller 指定的 scratch path
    df = compute_v30(klines, funding, universe)
    df.to_parquet(out_path)

# 然后在 cron 脚本里：
with atomic_write_file(canonical_out) as scratch:
    build_v30_features_for_production(scratch)
```

**反模式 2：消费者契约靠记忆**

```python
# ❌ 错误（R89.7 Phase 1 P0-5 的真实 bug）
def load_v30_features():
    meta = json.loads(open("v30_features.json").read())
    # 我"记得"key 是 features
    feature_list = meta.get("features", meta)  # 错——实际是 feature_cols

# ✅ 正确：写新代码前先 grep 现有消费者
# $ grep -n "feature_cols\|features" live/signals/v30_inference.py
# → live/signals/v30_inference.py:108 用 meta["feature_cols"]
# → 这是真正的 contract，不是研究脚本里的随便起个名字
def load_v30_features():
    meta = json.loads(open("v30_features.json").read())
    feature_list = meta["feature_cols"]  # 跟 v30_inference.py 严格一致
```

**反模式 3：`--help` 通过当作 work**

```bash
# ❌ 错误（R89.7 Phase 1 整个的脚本验证策略）
python3 scripts/auto_refresh_klines.py --help  # OK
python3 scripts/auto_refresh_coinmetrics.py --help  # OK
python3 scripts/auto_refresh_v30_features.py --help  # OK
python3 scripts/auto_refresh_ml_predictions.py --help  # OK
# "4 个脚本都通过了 smoke" → commit → codex 审 → FAIL

# ✅ 正确：至少跑一次真实场景的 dry-run
python3 scripts/auto_refresh_klines.py --dry-run --symbols BTCUSDT
# 真的发 1 次 HTTP，真的解析返回，真的写 tmp 文件
# 如果 metadata key 错了 / 增量逻辑错了 / atomic write 错了，这步就会暴露
```

### 在量化研究中的对应

```
反模式 1 的量化版本：
  ❌ 把 r28_ppo_rl.py（研究 trainer）直接 subprocess 在 weekly_retrain.sh 里
     → trainer crash 留下半训好的 zip？trainer 用的 sb3 版本变了？
  ✅ 抽出 train_ppo(env, config, seed) 核心函数，
     研究脚本和生产 retrain 都调用它

反模式 2 的量化版本：
  ❌ 写新 leg 时凭记忆假设"v30 输出 schema 是 (symbol, ts, pred)"
  ✅ 先 grep "ml_predictions_v30" 看下游 5 个 reader 怎么读，
     按它们的实际期望写

反模式 3 的量化版本：
  ❌ 跑一次小 universe / 1 个月数据，结果数字合理 → 上 final gate
  ✅ 至少跑一次"全 universe + 全期 + 真实 fee + walk-forward"，
     即使慢，必须真实端到端。"我以为它会工作" 经常 = "它不工作"
```
