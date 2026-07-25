> **quant-code-review · 维度参考文件** — 由 SKILL.md 按维度 P.3 的适用性裁定按需加载，不要无差别全量读入。
> 文中交叉引用（如"见 2.8"、"参见 4.6"）按维度编号到 references/ 对应文件查找。

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
- Kill switch / 熔断触发状态 — 必须跨重启保持（否则 supervisor 自动拉起进程
  = 变相绕过熔断；触发过的 kill switch 静默失效）
- unknown_state_symbols 硬闩锁（见 4.6，同理必须跨重启保持）
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

### 4.5.1 Heartbeat 与 Full Snapshot 的分层新鲜度（Two-Tier Freshness）

**背景故事**：4.5 里默认每个 bot 只有一个 `heartbeat_timeout` 阈值，监控中心
据此判断"STALE / OK"。这在 tick cadence ≤ heartbeat_timeout 的快策略上没问题，
但对于 tick cadence = 1h、daemon heartbeat = 5min 的 bar-close 类策略（典型如
E444、DCA、任何按小时 rebalance 的策略）会触发一个隐蔽的 false-STALE 陷阱：

```
T+0s        tick 执行 export() → _last_full_export_at = now
T+300s      daemon heartbeat → 刷新 _updated_at（但不刷 _last_full_export_at）
T+385s      heartbeat_timeout 到 → bot 其实没问题，但监控 STALE ✗
T+600s      heartbeat 又刷 _updated_at → 监控 OK/STALE 抖动
...
T+3600s     下一次 tick → 再次 export() → snapshot age 归零

结果：每个 tick 周期里有 ~54 分钟 bot 被错误地标记为 STALE。
运维端每小时被误告警一次 → 告警疲劳 → 真正 STALE 事件被忽略。
```

**根因**：_last_full_export_at（最后一次完整 tick 写入）和 last_heartbeat
（daemon 最后一次轻量刷新）是**两个不同时间概念**，但代码里被用同一个
heartbeat_timeout 做判断。

**修复设计 — 两个独立的 freshness 阈值**：

```
heartbeat_timeout_seconds        默认 385s（300s heartbeat × 1.28）
  └─ 判断 daemon thread 是否还在刷 _updated_at
  └─ 如果 now - _updated_at > heartbeat_timeout → HEARTBEAT_LOST

full_snapshot_timeout_seconds    默认 max(heartbeat_timeout × 2, 5400s)
                                 即 1.5 × 典型 1h tick cadence
  └─ 判断 tick 本身是否停转（最后一次完整 export 是多久之前）
  └─ 如果 now - _last_full_export_at > full_snapshot_timeout → TICK_STUCK
```

这两个阈值分别对应两类完全不同的故障：
- HEARTBEAT_LOST = 进程死了 / daemon 线程卡住（必须立即介入）
- TICK_STUCK = 进程还在但策略循环跑不动（可能是 API 限速、K 线拉不到、
  宇宙计算卡死 — 一样必须介入，但性质不同）

**审查清单（在原 4.5 基础上新增）**：

```
□ MonitorExporter 构造函数是否暴露两个独立参数：
  - heartbeat_timeout_seconds（已有）
  - full_snapshot_timeout_seconds（新增）

□ 两个阈值的默认值关系
  - heartbeat_timeout >= heartbeat_interval / 0.8
    （守住"daemon 每 5min 刷一次" 的契约）
  - full_snapshot_timeout >= tick_cadence × 1.5
    （策略允许单个 tick 比正常慢 50% — 常见是 fetch K 线超时）
  - full_snapshot_timeout >= heartbeat_timeout × 2
    （哪怕 tick_cadence 很短，也不能混淆两个概念）

□ monitor_export.json health 段是否同时暴露两个字段：
  health.heartbeat_timeout_seconds
  health.full_snapshot_timeout_seconds
  → 监控中心按各自阈值独立判断

□ _health_status 判定逻辑
  错误示例（真实 bug）：
    if age > heartbeat_timeout: return "STALE"   # 🔴 把 tick-cadence 年龄和
                                                 #    heartbeat 年龄混为一谈
  正确示例：
    if now - updated_at > heartbeat_timeout: return "STALE:heartbeat_lost"
    if now - full_export_at > full_snapshot_timeout: return "STALE:tick_stuck"
    return "OK"

□ Bootstrap from state file 时是否同时恢复两个阈值
  如果只读 heartbeat_timeout 不读 full_snapshot_timeout → 重启后降级回旧行为
  推荐：
    if v := health.get("heartbeat_timeout_seconds"):         self.heartbeat_timeout_seconds = float(v)
    if v := health.get("full_snapshot_timeout_seconds"):     self.full_snapshot_timeout_seconds = float(v)

□ Env override 必须支持两个阈值（否则没法在部署时单独调整）
  - <BOT>_MONITOR_HEARTBEAT_TIMEOUT_SECONDS
  - <BOT>_MONITOR_FULL_SNAPSHOT_TIMEOUT_SECONDS
  - 以 config.py 中的 default 作为 single source of truth；env 只做 override
  - 读取时必须 validate（max(1, int(v))）防止 0/负数 导致永远 STALE

□ STOPPED 状态下两个字段都要被写入 export
  - is_running=False 时仍然需要暴露两个 timeout，让监控中心的 schema
    检查不会因为缺字段而报错
  - last_heartbeat 可以用"shutdown 时刻"兜底；full_snapshot_age 用
    _last_full_export_at 正常计算（不要 reset 为 0）
```

**操作层建议**：

- 对于**已部署**的策略，补丁时要考虑向后兼容：旧版本的 monitor_export.json
  没有 full_snapshot_timeout_seconds 字段 → bootstrap 时走默认值（隐式迁移）
  → 监控中心对缺字段的消费也要有 fallback（`health.get("full_snapshot_timeout_seconds", health["heartbeat_timeout_seconds"] * 2)`）。
  不要写成"没字段就报错"。

- DEPLOY_RUNBOOK 中的 env-var 表格必须同时列出两个 timeout，并在注释里
  明确"heartbeat 是 daemon 线程级新鲜度，full_snapshot 是 tick-cadence 级
  新鲜度"，运维才知道该调哪个。

- 回归测试必须覆盖三种场景：
  a. tick 正常、heartbeat 正常 → OK
  b. tick 卡死、heartbeat 继续 → STALE (full_snapshot_timed_out)
  c. heartbeat 停止（进程死） → STALE (heartbeat_lost)
  任何一种被错判为"OK"或另一种 reason → 立即红

**与原 4.5 的关系**：4.5 定义了"什么字段必须存在"的 schema；4.5.1 定义了
"这些字段的时间语义如何分层"。两者叠加后，一个合格的 Monitor Protocol v1.1
实现需要同时满足：schema 完整 + 双阈值 freshness 判定。

---

**Beta 作为标杆**：Beta 的 StateManager._append_equity_snapshot() 已实现大部分要求。

**改造成本**：对已有策略，在主循环末尾加 3-5 行代码调用 MonitorExporter.export()。

**与维度 3.8 的关系**：3.8 关注交易决策日志（事后分析），4.5 关注实时状态导出（监控消费）。
两者互补但不重叠：3.8 记录"为什么做了这个决策"，4.5 导出"当前策略处于什么状态"。

### 4.5.2 Identity 字段反硬编码（Identity Anti-Hardcode）🔴 高优先级

> **背景故事**：2026-04-25 调查 4/19 cascade 时，第一反应是看 `monitor_export.identity.strategy`，
> 看到 "Regime-Adaptive DCA V15 (MEGA V2)" 就判断 H1+H2 没部署 → 给情绪低谷的 Tom 扣了一顶
> 错误的帽子。实际查证后发现：identity.strategy 是 `live_dca_bot.py` 第 4972 行硬编码的常量
> 字符串，跟 V15_PROD profile 加载完全无关；H1+H2 (use_maturity_factor=True, w_maturity=0.30
> 等) 在 profile 里是开着的。
>
> 后果：在事故调查这种高压场景下，cosmetic 字段误导了诊断方向，险些把"信号层修复 H1+H2"
> 当成 root cause。如果不是后续亲自查 profile 文件，错误诊断可能持续多轮，每一轮都浪费
> Tom 的情绪和决策窗口。

**核心规则**：**identity 类字段必须从配置反射，不能硬编码字符串。**

**为什么必须强制**：
- 硬编码字符串与实际 profile 解耦：profile 切换、参数 toggle 都不会反映在 identity 里
- monitor_export 是事故调查的第一入口，cosmetic 字段比"无字段"更危险（无字段会逼你查别处，cosmetic 会误导你停在表面）
- 在 LLM 协作场景尤其危险：assistant 看到 identity 字符串容易直接 attribution，跳过验证步骤

**审查清单**：

```
□ 4.5.2.1 Identity 字段不得为硬编码常量
   □ grep monitor_export 所有 identity.* 字段的赋值位置
   □ 任何形如 "strategy": "V15 MEGA V2 ..." 的字符串字面量 → 🔴
   □ 必须改为从 BotConfig 反射构造，例如：
     ```python
     identity = {
         "bot_name": cfg.label,                          # ← from profile.label
         "strategy": describe_strategy(cfg),             # ← derived from cfg fields
         "exchange": cfg.exchange,
         "session_id": str(self.session_id),
         "profile_name": cfg.label,                      # ★ NEW: explicit profile name
         "profile_signature": profile_signature(cfg),    # ★ NEW: hash of risk-relevant fields
     }
     ```

□ 4.5.2.2 关键 toggle 必须出现在 identity 里
   □ identity.strategy 字符串中必须显式包含影响策略行为的关键 toggle 值，例如：
     "V15_PROD (maturity=True/0.30, conf_floor=0.20, max_exp=2.0, dd_kill=0.99, liq_check=False)"
   □ 这样事故调查时一眼能看出"实际跑的是什么"，不需要再去 grep profile

□ 4.5.2.3 Profile signature 字段
   □ 在 identity 里增加 profile_signature 字段：对所有 risk-relevant 字段
     做 stable hash（如 SHA256 前 8 位）
   □ 调查时可以快速判断：当前 profile 是否与某个已知 commit 一致
   □ 实现示例：
     ```python
     def profile_signature(cfg):
         risk_keys = sorted([k for k in cfg.__dataclass_fields__
                              if any(p in k for p in
                                     ['use_', 'kill', 'tier', 'scale',
                                      'exposure', 'concurrent', 'maturity',
                                      'confidence', 'liquidation'])])
         payload = json.dumps({k: getattr(cfg, k) for k in risk_keys}, sort_keys=True)
         return hashlib.sha256(payload.encode()).hexdigest()[:8]
     ```

□ 4.5.2.4 Identity 字段 vs 实际 BotConfig 一致性测试
   □ 单元测试：apply_profile(BotConfig(), 'V15_PROD') 之后，
     monitor_export.identity 字段必须能反推出当前的 profile 名和关键 toggle
   □ 测试断言例：
     `assert "maturity=True" in monitor_export['identity']['strategy']`
   □ 反模式识别：identity.strategy 是常量字符串、不依赖 cfg.* → 🔴

□ 4.5.2.5 LLM/调查友好的描述格式
   □ identity.strategy 应当是人类（和 LLM）一眼能 parse 的格式
   □ 推荐格式：
     "{profile_label} (key1={val1}, key2={val2}, ...) sig={signature}"
   □ 不推荐：codename "MEGA V2" 这种内部代号 — 失去与配置的可追溯性
```

**修复模板**（对当前项目最小改动）：

```python
# Before（4/19 事故时的代码，反模式）：
def export_identity(self):
    return {
        "bot_name": "V15_PROD",
        "strategy": "Regime-Adaptive DCA V15 (MEGA V2)",  # ← 硬编码常量
        "exchange": "binance",
    }

# After（修复后）：
def export_identity(self):
    cfg = self.cfg
    key_toggles = [
        f"maturity={cfg.use_maturity_factor}/{cfg.w_maturity}" if cfg.use_maturity_factor else "maturity=off",
        f"conf={cfg.use_confidence_weighting}/{cfg.confidence_floor}" if cfg.use_confidence_weighting else "conf=off",
        f"max_exp={cfg.max_exposure_pct}",
        f"dd_kill={cfg.dd_kill_pct}",
        f"liq_check={cfg.use_liquidation_check}",
    ]
    return {
        "bot_name": cfg.label,
        "strategy": f"{cfg.label} ({', '.join(key_toggles)})",
        "exchange": cfg.exchange,
        "profile_name": cfg.label,
        "profile_signature": profile_signature(cfg),
    }
```

**验证示例**（修复后的 identity 长什么样）：
```json
"identity": {
  "bot_name": "V15_PROD",
  "strategy": "V15_PROD (maturity=True/0.3, conf=True/0.2, max_exp=2.0, dd_kill=0.99, liq_check=False)",
  "exchange": "binance",
  "profile_name": "V15_PROD",
  "profile_signature": "a3f8b1c2"
}
```

→ 一眼能看出：H1+H2 是开着的（maturity=True, conf=True），但 dd_kill 和 liq_check 都关了。
事故调查不会再误判。

**红线**：production bot 的 identity.strategy 字符串里不出现任何硬编码 codename
（如 "MEGA V2"、"H1+H2 Champion"、"V37 Global Optimum"），必须由配置反射。

### 4.6 Unknown-State 订单 Hard Latch（Order Ack 丢失保护）🔴 高优先级

> **背景故事**：2026-05-14 codex R12 P1。Executor 的 cancel-race 保护路径中，
> 如果 cancel/market-fallback 期间交易所 ack 丢失，那些订单的 fill 状态
> "未知" — 可能已成交，可能挂在 order book 上待成交。原代码：抛
> `OrderStateUnknownError`，把 partial_results 存到 state，返回 rc=2，loop
> 继续。但 `consecutive_errors` 会被后续成功 cycle 重置，孤儿 limit
> 单还挂在交易所上 — **下个 cycle 的新 limit 单会和孤儿单同时 fill =
> double-fill 风险**。
>
> 教训：order ack 丢失不能用 "continue + log" 应对，必须 **hard latch** —
> 状态保留到操作员手动 reconcile + clear。

**核心原则**：实盘 bot 不能假设"自己知道交易所的状态"。当那个假设破裂
（ack 丢失、网络 partition、cancel-race），唯一安全的行为是 **halt
+ require operator intervention**，不是 "continue and hope"。

**审查清单**：

```
□ 4.6.1 Unknown-state 路径识别
   □ Executor 是否有 cancel-race 保护（cancel 后再下 market 时检查
     filled_qty）？
   □ Cancel response 不返回 executedQty 时是否 re-query get_order？
   □ Re-query 也失败时是否抛专用异常（如 OrderStateUnknownError）？
   □ 异常是否携带受影响的 symbols 列表？

□ 4.6.2 State persistence on unknown
   □ 抛异常前是否把已知部分（partial_results）持久化到 state？
   □ 是否设置一个**专用字段**（如 unknown_state_symbols）保存
     受影响 symbols？
   □ State save 是否 atomic（tempfile + rename）？

□ 4.6.3 下一轮 cycle 入口 latch
   □ run_cycle / main loop 入口是否 **先检查** unknown_state_symbols？
   □ 如果非空，**拒绝交易** + telegram alert，return rc=1？
   □ 拒绝必须在 plan_orders **之前**，因为：
     - get_current_state 读 positionRisk 看不到挂着的孤儿 limit 单
     - plan_orders 看 current vs target，会再下一笔 → 双开仓 race
   □ 是否区分 consecutive_errors（软熔断，可自愈）vs unknown_state
     （硬 latch，需人工）？

□ 4.6.4 Operator 清理流程文档
   □ Runbook 是否有 "Clearing the unknown-state latch" 章节？
   □ 流程应包含：
     a. Aster UI 上 cancel-all 受影响 symbols
     b. 对比三个数字：current_pos vs target_weights × equity vs
        submitted_orders 里相关条目
     c. 如果一致：edit state.json 把 unknown_state_symbols 改成 []
     d. 如果不一致：手动调仓 match target，再 clear
   □ 必须明示："**不要直接删 unknown_state_symbols 就重启**" —
     孤儿单还在交易所上，下个 cycle 立刻 double-fill

□ 4.6.5 文档引用字段正确性
   □ Clearance procedure 引用的 state 字段必须是**真实被更新的**
     字段（如 target_weights, submitted_orders），不能引用
     placeholder 字段（如 R14 中发现的 last_executed_weights 从未
     被 executor 更新过）
   □ 写文档时跟着 grep "state.<field> ="确认每个引用的字段都有
     真实写入路径

□ 4.6.6 测试覆盖
   □ 是否有 mock test 模拟 cancel response 缺 executedQty 路径？
   □ 是否有 mock test 模拟 re-query get_order 失败路径？
   □ 是否有 integration test 验证 latch 在下一 cycle 入口生效？
```

**自动化探测**：

```bash
# 找 unknown-state 异常和 latch
grep -rn "OrderStateUnknown\|unknown_state\|ack.*lost\|reconcile" src/

# 验证 state 字段引用一致性（文档 vs 代码）
grep -rn "last_executed_weights\|target_weights\|submitted_orders" \
  docs/ src/live/state.py src/live/executor.py
```

**Action priority**：

1. 🔴 没有 OrderStateUnknownError 路径，cancel-race 直接 fail-open → 必修
2. 🔴 异常抛出后 loop 继续，没有 hard latch → 必修
3. 🟡 Runbook 没有 clearance procedure → operator 不知道怎么恢复
4. 🟡 Latch 引用了 placeholder state 字段 → 流程文档失效
5. 🟢 缺测试覆盖 → 上线后第一次 reconcile 会很慌
