> **quant-code-review · 维度参考文件** — 由 SKILL.md 按维度 P.3 的适用性裁定按需加载，不要无差别全量读入。
> 文中交叉引用（如"见 2.8"、"参见 4.6"）按维度编号到 references/ 对应文件查找。

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
- 幂等性：网络超时后的重发是否复用同一 clientOrderId（交易所端自动去重），
  防止"超时但实际已成交"时重发导致同一意图成交两次
- 下单后崩溃：重启后能否发现交易所上的已执行订单（用 clientOrderId 精确回查）
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

### 3.8.1 Per-run 目录隔离与跨日轮换（Per-run Folder Layout & UTC Daily Rotation）

**为什么必须单起一个子章节**：3.8 只要求"每次启动一个独立 session 文件"，
但实盘长时间运行时会出现两类混乱：
1. **同一次启动跨多天** — 一次 run 持续 7 天，如果全部写入一个大文件，
   按日期切分分析时要先做 `jq '.ts | startswith(...)'` 过滤，量大时极慢。
2. **多次重启混在同一目录** — 短期内重启 5 次，目录里出现
   `bot_20260401.log`、`bot_20260402.log`、... 完全无法区分哪两个文件属于
   同一次启动。对事故复盘尤其致命："上次 panic 时到底生成了哪几个日志文件？"

**解法**：引入 **"文件夹 = run，文件 = UTC 日期"** 的二维布局：

```
{state_dir}/logs/
├── bot_20260401_143022_a1b2c3d4/          ← run_1（4月1日启动）
│   ├── 2026-04-01.log                     （人眼可读）
│   ├── 2026-04-01.jsonl                   （结构化）
│   ├── 2026-04-02.log                     （run_1 跨到 4月2日）
│   └── 2026-04-02.jsonl
├── bot_20260402_091544_9f8e7d6c/          ← run_2（4月2日重启）
│   ├── 2026-04-02.log
│   └── 2026-04-02.jsonl
└── bot_20260405_160012_55aabbcc/          ← run_3（运行到现在）
    ├── 2026-04-05.log
    ├── 2026-04-05.jsonl
    ├── 2026-04-06.log
    └── 2026-04-06.jsonl
```

**审查清单**：

```
1. run_id 命名规范：
   □ 每次进程启动生成唯一 run_id
     推荐格式：{UTC启动时间YYYYMMDD_HHMMSS}_{8位随机hex}
     示例：20260401_143022_a1b2c3d4
   □ run_id 带时间前缀 → 目录按字典序排序即按启动时间排序
   □ 带随机后缀防止同秒重启时的目录名碰撞
     （SIGTERM 后 supervisor 立即拉起，2 个 run 启动时间戳可能完全相同）

2. 目录结构：
   □ 每个 run 独占一个文件夹，不和其他 run 共享文件
   □ 文件夹名 = bot_{run_id}（前缀让多策略共存时一眼区分）
   □ 整个 run 的所有输出（log/.jsonl/也许还有 reconciliation diff/
     事后手工 dump 的 state 快照）都写入这个文件夹内
   □ 文件夹是"run 的自包含容器"——把它打包发出去，收方能完整复现分析

3. 文件按 UTC 日期切分：
   □ 同一个 run 内，按 UTC 日期切分日志文件
     （不是启动日，不是服务器本地日——必须 UTC）
   □ 文件名：{YYYY-MM-DD}.log 和 {YYYY-MM-DD}.jsonl 各一份
     （.log 给人眼读，.jsonl 给脚本分析）
   □ 跨日时自动创建次日文件，不需要重启进程

4. 懒切换（Lazy-on-emit）不要用线程：
   □ 跨日切换必须在"写入日志"这一瞬间惰性触发，而不是起一个单独的
     timer 线程在午夜 0 点自动滚动
   □ 原因：timer 线程 = 多一个需要关心的并发点、多一个可能的卡死源头、
     多一个 unit test 难写的路径
   □ 正确实现：每次 emit 前检查 current_utc_date != file_utc_date，
     如果是就关闭旧 handle、打开新 handle（见下方参考实现）

5. 重试与关闭语义：
   □ 每次 emit 都 flush（延续 3.8 #7 的要求）
   □ 进程收到 SIGTERM/SIGINT 时 close 所有打开的 file handle，
     而不是依赖 GC——防止 OS-buffer 里最后几行日志丢失
   □ 如果写日志失败（磁盘满、权限错），降级为 stderr，不要 raise
     拖垮主循环（这是 3.10 "zero-fail posture" 的前哨）

6. 清理策略：
   □ 有明确的保留期（推荐 30-90 天）
   □ 清理按 run 目录为单位：
     find {state_dir}/logs/ -maxdepth 1 -type d -name 'bot_*' -mtime +90 \
       -exec rm -rf {} \;
   □ 不要按文件粒度清理——按文件删会破坏 run 的自包含性
     （上面删了 2026-04-01.log，下面还留着 2026-04-02.log，
     事故复盘时一脸懵）
   □ 清理任务写在 cron 或 systemd timer 里，不要写在 bot 主进程里
     （主进程 crash 时不清理 ≠ 灾难；但主进程因为清理 bug crash ＝ 灾难）

7. symlink 指向最新 run：
   □ {state_dir}/logs/latest → bot_20260405_160012_55aabbcc/
     （方便 `tail -f logs/latest/$(date -u +%F).log` 实时查看）
   □ symlink 在启动时原子更新（先写 tmp symlink 再 rename）
```

**参考实现（懒切换 Daily UTC File Handler）**：

```python
import logging
import os
from datetime import datetime, timezone
from pathlib import Path

class _DailyUtcFileHandler(logging.Handler):
    """日志按 UTC 日期切分文件，不使用定时线程。

    切换时机：每次 emit 前对比记录时间和当前打开文件的日期，
    不一致就关旧打开新。纯 lazy、无并发复杂度。

    与 TimedRotatingFileHandler 的区别：
    - TimedRotatingFileHandler 默认用本地时间（实盘常跨时区踩坑）
    - TimedRotatingFileHandler 在 rollover 时会改动既有文件名
      （把 app.log 重命名为 app.log.2026-04-01），破坏"文件名 = UTC 日期"的
      简单语义
    - 本实现直接按目标日期命名：2026-04-01.log / 2026-04-02.log，
      文件名本身就是最终形态
    """
    def __init__(self, log_dir: str, suffix: str = ".log", formatter=None):
        super().__init__()
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.suffix = suffix
        if formatter is not None:
            self.setFormatter(formatter)
        self._current_date: str | None = None
        self._stream = None

    def _date_for(self, record) -> str:
        # record.created 是 UTC epoch float
        return datetime.fromtimestamp(
            record.created, tz=timezone.utc
        ).strftime("%Y-%m-%d")

    def _switch(self, date_str: str):
        if self._stream is not None:
            try:
                self._stream.close()
            except Exception:
                pass
        path = self.log_dir / f"{date_str}{self.suffix}"
        self._stream = open(path, "a", encoding="utf-8")
        self._current_date = date_str

    def emit(self, record):
        try:
            date_str = self._date_for(record)
            if date_str != self._current_date:
                self._switch(date_str)
            msg = self.format(record)
            self._stream.write(msg + "\n")
            self._stream.flush()
        except Exception:
            self.handleError(record)

    def close(self):
        try:
            if self._stream is not None:
                self._stream.close()
                self._stream = None
        finally:
            super().close()


def setup_logging(state_dir: str, run_id: str):
    """在进程启动时调用一次。"""
    log_dir = Path(state_dir) / "logs" / f"bot_{run_id}"
    log_dir.mkdir(parents=True, exist_ok=True)

    plain_fmt = logging.Formatter(
        "%(asctime)s.%(msecs)03d [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )
    jsonl_fmt = JsonFormatter()  # 自定义 JSON formatter，ts 用 UTC iso8601

    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.addHandler(_DailyUtcFileHandler(str(log_dir), ".log", plain_fmt))
    root.addHandler(_DailyUtcFileHandler(str(log_dir), ".jsonl", jsonl_fmt))

    # 控制台同步输出（方便 docker logs / journalctl）
    console = logging.StreamHandler()
    console.setFormatter(plain_fmt)
    root.addHandler(console)

    # 更新 latest symlink（原子）
    latest = Path(state_dir) / "logs" / "latest"
    tmp = Path(state_dir) / "logs" / f".latest.{run_id}"
    if tmp.exists() or tmp.is_symlink():
        tmp.unlink()
    os.symlink(log_dir.name, tmp)
    os.replace(tmp, latest)


def new_run_id() -> str:
    """在 config.py 的 from_env() 或 main 入口早期调用。"""
    import secrets
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    return f"{ts}_{secrets.token_hex(4)}"
```

**常见反模式**：

| 反模式 | 后果 | 正确做法 |
|--------|------|----------|
| `TimedRotatingFileHandler` + 本地时间 | 跨时区服务器日志在"非半夜"滚动，和 K 线 UTC 时间对不上 | 自己实现，显式 `tz=timezone.utc` |
| 用 `threading.Timer` 在午夜切换 | 多一个并发点，stack-trace 里看到不该有的 timer 线程 | Lazy-on-emit，无线程 |
| 所有 run 写入同一个 `bot_{date}.log` | 事故时分不清哪几行是哪次启动 | 按 run_id 分文件夹 |
| run_id 里只有时间没有随机后缀 | 秒级重启时目录名碰撞 | 加 `secrets.token_hex(4)` |
| 按文件清理旧日志（`find ... *.log -mtime +90`） | 同一个 run 的文件被部分删除，剩下的成孤儿 | 按 run 目录整体删除 |
| 清理任务写在 bot 主进程里 | 清理 bug → 主进程 crash → 没人交易 | 独立 cron / systemd timer |
| latest symlink 用 `os.unlink + symlink` 两步 | 两步之间若 crash，latest 指向空 | 先 symlink 到 tmp 名再 `os.replace` |
| 不 flush，关闭也不 close | crash 时丢失 OS buffer 里的最后几百行 | 每条 flush + SIGTERM 时显式 close |

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

     数据源优先级（适用于所有交易所）：
       优先级 1：结构化公告 API（最稳定，返回 JSON，易解析）
       优先级 2：RSS 订阅（结构化，标准格式，大多数交易所都有）
       优先级 3：公告网页爬取（万能兜底——每个交易所都有公告页）
       实现方式：requests + BeautifulSoup 提取文本即可，不需要 headless browser

     各交易所具体接入：

     Binance：
       · 公告 API: https://www.binance.com/bapi/composite/v1/public/cms/article/list/query
         参数: type=1, catalogId=48 (期货公告), pageSize=20
       · 下架专题页（备选）: https://www.binance.com/en/support/announcement/delisting
       · 推荐频率: 每 6 小时

     Hyperliquid：
       · 无公告 API，但有公告网页:
         https://hyperliquid.gitbook.io/hyperliquid-docs (文档+公告)
         https://x.com/HyperliquidX (官方 Twitter，重大变更会发推)
       · 接入方式: 定期爬取文档页 / 博客页，提取新内容
         用 requests 拉 HTML → BeautifulSoup 提取文本 → 关键词过滤
       · 推荐频率: 每 6 小时
       · ⚠️ Hyperliquid 下架较少但没有结构化提前通知机制，
         网页爬取是最实际的方案

     OKX（未来扩展）：
       · 公告 API: https://www.okx.com/api/v5/support/announcements
       · 公告网页: https://www.okx.com/support/hc/en-us/sections/360000030652
       · 推荐频率: 每 6 小时

     Bybit（未来扩展）：
       · 公告 API: https://api.bybit.com/v5/announcements
       · 公告网页: https://announcements.bybit.com/
       · 推荐频率: 每 6 小时

     新增交易所时的接入检查清单：
       □ 是否有结构化公告 API？→ 有则直接调用（最优）
       □ 是否有 RSS 订阅？→ 有则用 feedparser 解析（次优）
       □ 公告网页 URL 是什么？→ requests + BeautifulSoup 爬取（万能兜底）
       □ 以上都确认后，实现 AnnouncementSource 子类并注册到 DelistingMonitor

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
     ⚠️ 模型选型以 3.9.1-I 为准（2026-04 更新：推荐 gpt-5-nano）。
     下述 gpt-4.1-nano 数字保留作成本量级参考：
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
   ⚠️ 默认频率以 3.9.1-C 为准：12h 起步（成本减半且对 7-30 天提前量毫无影响），
   仅当交易所有 24h 紧急下架史时才加密到 6h。下表 6h 为保守上限示例。
   ```
   ┌──────────────────────┬────────────┬──────────────────┬──────────────┐
   │ 步骤                 │ 频率       │ 成本             │ 原因         │
   ├──────────────────────┼────────────┼──────────────────┼──────────────┤
   │ 抓取公告             │ 每 6 小时  │ 免费(HTTP GET)   │ 下架公告提前 │
   │ (API 或网页爬取，    │            │                  │ 7-30天，6h   │
   │  所有交易所统一频率) │            │                  │ 延迟完全够   │
   ├──────────────────────┼────────────┼──────────────────┼──────────────┤
   │ 关键词预过滤         │ 每条公告   │ 免费(本地正则)   │ 过滤~95%     │
   │                      │            │                  │ 无关公告     │
   ├──────────────────────┼────────────┼──────────────────┼──────────────┤
   │ LLM 精析             │ 仅命中公告 │ ~$0.00013/次     │ 月均<$0.01   │
   │                      │ (0-2次/天) │ (gpt-4.1-nano)   │              │
   ├──────────────────────┼────────────┼──────────────────┼──────────────┤
   │ API 状态检查(第二层) │ 每次       │ 免费(交易所API)  │ 兜底第一层   │
   │                      │ rebalance  │                  │              │
   └──────────────────────┴────────────┴──────────────────┴──────────────┘
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

class WebScrapingAnnouncements(AnnouncementSource):
    """通用网页爬取方案 — 适用于没有公告 API 的交易所（如 Hyperliquid）。
    只需 requests + BeautifulSoup，不需要 headless browser。"""
    def __init__(self, exchange_name: str, url: str,
                 selector: str = "article, .content, main"):
        self.exchange = exchange_name
        self.url = url
        self.selector = selector
    def fetch_recent(self, since):
        from bs4 import BeautifulSoup
        resp = requests.get(self.url, timeout=30,
                            headers={"User-Agent": "Mozilla/5.0"})
        soup = BeautifulSoup(resp.text, "html.parser")
        blocks = soup.select(self.selector)
        # 将每个内容块作为一条"公告"返回，由关键词预过滤决定是否有价值
        return [{"title": b.get_text()[:100], "body": b.get_text(),
                 "time": datetime.now(timezone.utc)} for b in blocks]

# 使用示例：
# sources = [
#     BinanceAnnouncements(),                          # API 方式
#     WebScrapingAnnouncements("hyperliquid",           # 网页爬取
#         url="https://hyperliquid.gitbook.io/...",
#         selector="article"),
#     WebScrapingAnnouncements("okx",                   # 也可以用网页爬取
#         url="https://www.okx.com/support/hc/en-us/sections/360000030652",
#         selector=".article-list-item"),
# ]


# ── LLM 解析（gpt-4.1-nano，单次 < $0.0002）────────────────────
LLM_MODEL = "gpt-4.1-nano"  # 示例值；2026-04 起以 3.9.1-I 为准（推荐 gpt-5-nano）
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

#### 3.9.1 LLM 公告分类器的反噪声与成本控制（Aster 2026-04 血泪教训）

**为什么要单独列出这个子节**：原 3.9 已经给了一个"keyword + LLM"的基础框架，
但一次真实部署暴露了一整组"看起来合理但会让你亏钱或漏判"的陷阱。这些经验
来自 2026-04-24 Aster 实盘部署后的紧急修复 — 把它们系统化地沉淀下来，
免得下次在另一个交易所/另一个模型上重新踩一遍。

**核心原则（比工具重要）**：

```
1. False positive > False negative 的成本不对称：
   公告监控错判一次 = 平掉一个真仓（可能是正 PnL 的仓位） = 实际亏钱
   公告监控漏判一次 = 交易所 API 层兜底（PRE_DELIVERING / SETTLING 会拦截）
   → Prompt / 代码默认都必须是"when in doubt, return false"。
   → 合约决策依据永远优先选 deterministic（关键词 + 交易对精确匹配）而非 LLM。

2. LLM 是"噪声过滤兜底"，不是"事实来源"：
   当网页是 JS app shell / category 索引 / 符号目录时，交易所没有提供
   actionable 公告 — 此时 LLM 的任务是说"这不是公告"，而不是硬从噪声里
   挖出一个受影响符号。
   → 宁可让 LLM 经常 false（拒绝候选），也不要给模型"必须给出答案"的压力。

3. LLM 成本的指数放大来源不是单次调用，而是重复处理同一条公告：
   单次调用 $0.0002。但如果每 6h 轮询一次 × 每轮 50 条历史 rows × 每条都打
   LLM = 200 次/天 = $0.04/天 = $14.4/年。修复：持久化 rejection cache。
```

**审查清单（在原 3.9 基础上新增）**：

```
A. 数据源优先级 — 结构化 API > RSS > 纯文本 HTML
   □ 当交易所同时提供 list 网页（e.g. /announcement?category=DELISTING）
     和结构化 API（e.g. /bapi/.../announcement/search）时，必须 sniff URL
     并直接打 API，不要抓 HTML：
       - HTML 可能是 SPA app shell（只有 <div id="root">）→ 内容全为空
       - HTML 里的导航栏 / 侧栏 / "热门交易对" 区块包含全部 symbol
         → keyword 预过滤无法过滤掉这些 HTML，会 100% 命中并送进 LLM
         → LLM 看到"这页提到了 BTCUSDT / ETHUSDT / SOLUSDT..."可能被骗
   □ 对于 Aster 这类 SPA 交易所，实现一个 URL → structured-endpoint 的
     翻译层（见 Codex 的 _fetch_aster_announcement_items 示例）

B. 不要把 HTML app-shell 当成一条公告
   □ _parse_feed 必须识别 `<!doctype html`、`<html`、`<body` 前缀
     → 默认 return []，而不是"把整页 HTML 作为 body 单条 item"
   □ 只有启用 LLM 且显式 allow_unstructured_html=True 时才解析 HTML，
     而且要额外做 mini-parse（去掉 script/style/nav/aside）减少噪声
   □ 反例：把 app shell 当成一条 `AnnouncementItem(title=url, body=<整页>)`
     → LLM 看到全部 symbol，在保守模式下会"宁可多判"，触发错误 block

C. 轮询频率 — 对下架时间线做"够用即可"的选择
   □ 下架公告通常提前 7-30 天，6h 和 12h 的延迟对 actionability 毫无差别
   □ 默认 12h 而非 6h：成本降一半，同时日均真正触发 LLM 的次数降到 0-1 次
   □ 只有当交易所有"24h 紧急下架"史实时，才下探到 6h 或更密

D. LLM Rejection Cache — 单次判定永久生效
   □ 对每条 candidate item 计算 digest = sha256(title + body)
   □ 同时计算 universe_digest = sha256(sorted(requested_symbols))
   □ key = f"{item_digest}:{universe_digest}"
   □ 第一次 LLM 返回"affects_holdings=false" → 把 key 加入 rejected cache
   □ 下次轮询再看到同一 item（archive 不会变）→ 直接跳过 LLM 调用
   □ 失效策略：当 requested symbols 变化（universe_digest 变）→ cache miss
     → 重新评估（因为新增的标的可能真的被下架了）

E. Stale Row 过滤 — List 端点会返回 archive
   □ 交易所的 list API 每次都返回历史全量（最近 50-100 条），不是 delta
   □ 如果只靠 "seen_hashes" 去重，首次轮询时所有历史 archive rows 都是新的
     → 一次 burst 的 LLM 调用，并可能把 "XYZ delisted on 2025-03-15" 
        当成 actionable → 错误 block 一个早已不在 universe 的 symbol
   □ 规则：
     - 已解析出 deadline 且 deadline < now - 24h grace → stale，skip
     - 无 deadline 但 published_at < now - 14d → stale，skip（仅对已知
       list 端点生效，RSS / 明文 feed 不适用）
   □ Grace window 必须有（不是直接 deadline < now）— 处理时区边界 & 撤回

F. Spot / Contract 的消费侧过滤
   □ 合约 bot 的 universe 是 "XXXUSDT" 永续合约，但公告经常掺杂 spot
     下架（同一 ticker 但产品线完全不同）
   □ 在 keyword 命中后、调 LLM 前，先做 spot-only 检测：
     "Spot Trading / 现货" 且 不含 "Perpetual / Futures / Contract"
     → skip（哪怕 symbol 名称命中）
   □ 对偶规则 — 明确 contract 公告则本地直接 authoritative：
     "Perpetuals Delisted / Perpetual Contract Delist" + symbol 命中
     → 不必调 LLM，直接视为确认（避免 LLM 把合约下架 false-negative
       回去，从而让一个真的下架溜过去）

G. Prompt Engineering 的三条铁律
   □ 提供 alias hints — 让模型建立 canonical ↔ 别名映射
     例：`- 1000SHIBUSDT: 1000SHIBUSDT, 1000SHIB, SHIB, SHIBUSDT`
     否则公告说"SHIB delist"、universe 是 1000SHIBUSDT 时会漏判
   □ 显式列出"safe path"：遇到 category / app-shell / 符号目录直接
     return affects_holdings=false。这是一句 prompt 但挡掉 ~95% 的假阳
   □ 白名单裁剪 — 模型返回的 affected_symbols 必须与当前 universe 精确
     交集（代码层 set(requested) ∩ set(model_output)），防止模型幻觉
     出 universe 之外的 symbol，然后代码老老实实 block 了它

H. OpenAI API 客户端的坑
   □ 不同模型对参数的容忍度不同：
     - gpt-4.1-nano / gpt-4o-mini: 接受 temperature=0
     - gpt-5 / gpt-5-nano: **omit temperature**（发送会 400）
   □ HTTP 错误处理不要用 raise_for_status()：response body 里有真正有用
     的错误信息（如 "model does not support temperature"），直接 raise
     丢掉了 body。改成：
       ```python
       if resp.status_code >= 400:
           raise RuntimeError(f"LLM HTTP {resp.status_code}: "
                              f"{_truncate_text(resp.text, 500)}")
       ```
   □ response_format={"type": "json_object"} 是必须的（避免 markdown 代码
     块包裹的 JSON，parse 失败概率大幅降低）
   □ LLM 失败 → set() + log.warning，**绝不 block symbols**
     （安全故障模式：LLM 挂掉不能扩散成"自动平仓全部持仓"）

I. 默认模型选择（2026-04 准）
   □ 推荐：gpt-5-nano（OpenAI 最便宜的 flagship-mini，支持 JSON mode）
   □ 单次调用成本：~$0.0001（12k chars truncation 下）
   □ 备选：gpt-4.1-nano（略便宜，但分类能力略弱，prompt 要更显式）
   □ 不推荐：gpt-4 / claude-sonnet — 严重过量，浪费成本

J. 输入裁剪
   □ 单次调用必须 truncate 公告正文到 ~12000 chars（8-10k tokens）
   □ 裁剪策略：取前 N 字符 + "
...[truncated]" 标记
   □ 理由：
     a. 控制成本（输入 tokens 直接决定账单）
     b. 控制合规（避免把完整网页 dump 给外部 API）
     c. 长 HTML 的真实签名通常出现在开头 1-2 屏，后面都是噪声
```

**最终总结 — LLM 公告监控的"极简骨架"**：

```python
# 每次轮询
for item in fetch_items(url):                    # ← 优先结构化 API
    if is_html_appshell(item):                   # ← 反 SPA 污染
        continue
    if is_stale(item, now):                      # ← archive 过滤
        continue
    if not any(kw in item for kw in KEYWORDS):   # ← 本地关键词
        continue
    if is_spot_only_notice(item):                # ← 合约 bot 不关心
        continue
    local_hits = match_universe_symbols(item)    # ← 精确匹配
    if local_hits and is_contract_delist(item):
        affected = local_hits                    # ← authoritative
    else:
        cache_key = (item_digest, universe_digest)
        if cache_key in rejected_cache:          # ← 单次判定永久生效
            continue
        decision = call_llm(item)                # ← 只有这一步花钱
        if not decision.affects_holdings:
            rejected_cache.add(cache_key)
            continue
        affected = decision.affected_symbols & universe  # ← 白名单裁剪
    trigger_block(affected)
```

这个骨架背后的成本 — 每月约 0-5 次真实 LLM 调用（$0.0005-$0.01），
对比"抓取 HTML app shell + 每条都打 LLM" 的失败模式（$5-$50/月 + 
频繁错误 block），差距是 1000 倍。

---

### 3.10 告警与心跳协议（Alerting & Heartbeat Protocol）

**为什么重要**：实盘 bot 在服务器上"无人值守"地运行，当它真正需要人类介入的时候
（保证金爆仓边缘、IP 被交易所封、未处理异常导致主循环停摆），服务器上的日志再
漂亮也没人会去看。告警是把 "日志里一条 ERROR" 推到人类眼前的最后一米。

**但告警系统本身必须是"只增价值、不引入风险"的**。一个典型的失败模式：告警代码
本身 crash 了导致整个 bot 停转——3.10 的审查目标就是保证这种事不会发生。

**核心设计原则**：

1. **告警是日志的补充，不是替代**。所有发告警的事件必须同时进日志（3.8）。
   告警是"推送"，日志是"留痕"——推送失败时留痕不能跟着丢。
2. **零失败姿态（Zero-fail posture）**。所有告警 I/O 必须 `try/except Exception`
   包裹 + 超时保护。发送失败降级为 WARNING 级日志，永不抛出到上层。
3. **未配置时静默 no-op**。部署模板里没填 token/chat_id 时，告警模块应该静默关闭，
   不是报错也不是警告——有些用户就是不想用 Telegram。
4. **按 key 限频**。同一类事件短时间内（如 10 分钟）只推一次，防止 bug 导致告警
   风暴（把用户 Telegram 刷爆 + 触发交易所 rate limit）。
5. **心跳有"当日去重"语义**。每天固定 UTC 小时推一次"我还活着 + 今日 equity"，
   哪怕 bot 在那个小时里被调了 100 次 `maybe_send_heartbeat()` 也只发一条。

**审查清单**：

```
1. 通道选择与配置：
   □ 至少有一个"推送到人"的通道（Telegram / Discord / 钉钉 / 企业微信 /
     PagerDuty / 邮件）
   □ 通道凭据通过 env 注入，不 hardcode
     (TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID 或等价环境变量)
   □ env 缺失时代码走 no-op 路径（见下方参考实现的 enabled 判定）
   □ .env.example 里写了配置方法和获取 token 的步骤链接

2. 心跳（daily heartbeat）：
   □ 每天固定 UTC 小时推送一次当日 equity + 关键指标
   □ 含当日变化（PnL、% change vs 昨日 / vs 启动日）
   □ 含当前持仓数、margin_ratio、累计 drawdown
   □ 用 state 文件或内存变量做"当日去重"：
     last_heartbeat_date == today_utc → skip
   □ 心跳也要符合"零失败姿态"（参考实现里 try/except 包裹）
   □ 服务器时区不影响心跳时间（始终用 UTC 判断）

3. 关键事件告警（immediate alert）：
   必须告警的事件（缺少任何一项 = 🔴）：
   □ 进程启动（notify_startup） — 确认 bot 起来了
   □ 进程优雅关闭（notify_shutdown，含原因） — 区分手动停 vs crash
   □ MarginMonitor 触发减仓（3.6 联动） — 离爆仓最近的预警
   □ 交易所封禁/IP 被 ban — 继续 retry 只会加深封禁
   □ Kill switch 触发（连续减仓超过阈值） — 可能需要人肉介入
   □ 未捕获异常冒泡到主循环 — 代表 bot 已经不能正常工作了
   □ 账户 equity 单日跌幅超过阈值（如 >10%） — 异常风险事件

4. 限频（rate limiting）：
   □ 按告警 key 限频（例如 "margin_trip_SOL"、"ip_ban"、"tick_exception"）
   □ cooldown 默认 600 秒（10 分钟），可配
   □ 限频状态持久化到 state 文件 or 跨重启的 json
     （不持久化 = 重启后第一次事件必发，容易在 restart loop 时洪水）
   □ 限频被命中时，本地日志里要打一条 WARNING 说明"告警被限频"
     （不然用户会以为 bot 静默了）

5. 零失败姿态（最重要）：
   □ 所有 HTTP 调用有显式 timeout（推荐 5 秒）
   □ 所有 HTTP 调用外层 try/except Exception（不是 try/except HTTPError）
   □ 捕获到异常时，降级为 logging.warning(...)，不 raise
   □ 告警模块自身的 import 失败也要被主程序 try/except 兜住
     （requests 没装？直接让告警模块 import 成 None）
   □ 告警相关逻辑不放在 hot path（主循环 tick() 的性能敏感位置）
     → 实际的 HTTP 请求是阻塞的，如果放主循环会影响交易时效性
     → 推荐：在主循环里只写一个状态变量，由独立的告警线程/协程异步发送
     （或者对"极小频率"的事件直接阻塞 5 秒也可以接受 — 视频率而定）

6. 消息内容格式：
   □ 启动消息：bot 名称、版本/git_hash、配置摘要、启动 UTC 时间
   □ 关机消息：原因分类（GRACEFUL/CRASH/KILL_SWITCH/SIGNAL）、运行时长、
     最终 equity、session 内总交易次数
   □ 事件消息：事件类型（emoji 前缀更醒目）、时间（UTC）、
     关键数值（MR、equity、涉及标的、阈值）、是否需要人工介入
   □ 避免把完整 traceback 贴到 Telegram（容易超 4096 字符限制），
     改为发"traceback 的第一行 + 日志文件路径"
   □ 避免在消息里泄露 API key / 账户 ID

7. 命令控制（可选但需 7.7 联动）：
   □ 如果 bot 支持通过 Telegram 命令控制（如 /stop、/close_all），
     必须做 chat_id 白名单鉴权（见 7.7 "Telegram / 通知渠道安全"）
   □ 默认关闭命令控制（降低攻击面），手动配置白名单才启用
```

**参考实现（TelegramNotifier 伪代码）**：

```python
import json
import logging
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

log = logging.getLogger(__name__)

class TelegramNotifier:
    """Zero-fail Telegram 告警器。所有 IO 失败都降级为 log.warning()。
    未配置 token/chat_id 时静默 no-op。
    """
    API_BASE = "https://api.telegram.org"
    DEFAULT_TIMEOUT = 5.0
    DEFAULT_COOLDOWN = 600  # 10 分钟

    def __init__(
        self,
        bot_token: Optional[str],
        chat_id: Optional[str],
        state_path: Optional[str] = None,
        heartbeat_utc_hour: int = 0,  # 0-23, 每日 UTC 0 点推心跳
        cooldown_seconds: int = DEFAULT_COOLDOWN,
    ):
        self.enabled = bool(bot_token and chat_id)
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.heartbeat_utc_hour = heartbeat_utc_hour
        self.cooldown = cooldown_seconds
        self.state_path = Path(state_path) if state_path else None
        self._state = self._load_state()

    def _load_state(self) -> dict:
        if not self.state_path or not self.state_path.exists():
            return {"last_heartbeat_date": None, "last_alert_ts": {}}
        try:
            return json.loads(self.state_path.read_text())
        except Exception as e:
            log.warning("tg state load failed, starting fresh: %s", e)
            return {"last_heartbeat_date": None, "last_alert_ts": {}}

    def _save_state(self):
        if not self.state_path:
            return
        try:
            tmp = self.state_path.with_suffix(".tmp")
            tmp.write_text(json.dumps(self._state))
            os.replace(tmp, self.state_path)
        except Exception as e:
            log.warning("tg state save failed: %s", e)

    def _post(self, text: str) -> bool:
        """发送一条消息。永不抛异常，失败返回 False。"""
        if not self.enabled:
            return False
        try:
            import requests  # 局部 import，避免硬依赖
            url = f"{self.API_BASE}/bot{self.bot_token}/sendMessage"
            resp = requests.post(
                url,
                json={"chat_id": self.chat_id, "text": text,
                      "parse_mode": "Markdown"},
                timeout=self.DEFAULT_TIMEOUT,
            )
            if resp.status_code != 200:
                log.warning("tg send non-200: %s %s",
                            resp.status_code, resp.text[:200])
                return False
            return True
        except Exception as e:
            # 网络超时、DNS fail、证书错误、requests 没装——全部吃掉
            log.warning("tg send failed: %s", e)
            return False

    def notify_startup(self, bot_name: str, version: str,
                       config_summary: str):
        self._post(
            f"🟢 *{bot_name} started*\n"
            f"version: `{version}`\n"
            f"utc: `{datetime.now(timezone.utc).isoformat()}`\n"
            f"config: {config_summary}"
        )

    def notify_shutdown(self, reason: str, final_equity: float,
                        duration_s: float, n_trades: int):
        icon = "🔴" if reason in ("CRASH", "KILL_SWITCH") else "⚫"
        self._post(
            f"{icon} *bot stopped* ({reason})\n"
            f"runtime: `{duration_s/3600:.1f}h`\n"
            f"final equity: `${final_equity:.2f}`\n"
            f"trades this session: `{n_trades}`"
        )

    def maybe_send_heartbeat(self, equity: float, pnl_pct: float,
                              n_positions: int, margin_ratio: float):
        """每日 UTC {heartbeat_utc_hour} 点发心跳。同一天多次调用只发一次。"""
        if not self.enabled:
            return
        now = datetime.now(timezone.utc)
        if now.hour != self.heartbeat_utc_hour:
            return
        today = now.strftime("%Y-%m-%d")
        if self._state.get("last_heartbeat_date") == today:
            return
        # 先把"今天发过"持久化，再发消息。这样即使发失败，今天也不会洪水
        # （下一次 maybe_send_heartbeat 会被去重跳过）。
        self._state["last_heartbeat_date"] = today
        self._save_state()
        self._post(
            f"💓 *daily heartbeat* `{today}`\n"
            f"equity: `${equity:.2f}` ({pnl_pct:+.2f}%)\n"
            f"positions: `{n_positions}`  MR: `{margin_ratio*100:.1f}%`"
        )

    def alert(self, key: str, text: str, *, force: bool = False):
        """按 key 限频的告警。同一个 key 在 cooldown 内只发一次。"""
        if not self.enabled:
            return
        last = self._state.get("last_alert_ts", {}).get(key, 0)
        now_ts = time.time()
        if not force and (now_ts - last) < self.cooldown:
            log.warning("alert suppressed by cooldown: %s", key)
            return
        if self._post(text):
            self._state.setdefault("last_alert_ts", {})[key] = now_ts
            self._save_state()
```

**集成模式**（bot 主类中的"插桩点"）：

```python
# 启动时
self.tg = TelegramNotifier(
    bot_token=cfg.telegram_bot_token,
    chat_id=cfg.telegram_chat_id,
    state_path=f"{cfg.state_dir}/telegram_state.json",
    heartbeat_utc_hour=cfg.telegram_heartbeat_utc_hour,
)

def prepare(self):
    # ...现有逻辑...
    try:
        self.tg.notify_startup(
            bot_name="momentum-live",
            version=self.cfg.git_hash,
            config_summary=f"lev={self.cfg.leverage}x top_n={self.cfg.top_n}"
        )
    except Exception as e:  # 双保险：notifier 内已 try/except，外层再兜一层
        log.warning("tg notify_startup outer guard: %s", e)

def tick(self):
    try:
        # ...主循环逻辑...
        self._maybe_margin_check()  # 内部触发 self.tg.alert("margin_trip_XXX", ...)
        try:
            self.tg.maybe_send_heartbeat(
                equity=self.equity,
                pnl_pct=self.today_pnl_pct,
                n_positions=len(self.positions),
                margin_ratio=self.margin_ratio,
            )
        except Exception as e:
            log.warning("tg heartbeat outer guard: %s", e)
    except AsterBanned as e:
        self.tg.alert("ip_ban", f"🚨 IP banned: {e}")
        raise  # ban 必须冒泡让主循环停
    except Exception as e:
        self.tg.alert("tick_exception",
                      f"⚠️ unhandled tick exception: {type(e).__name__}: {e}")
        # 不要 raise——一次 tick 失败不应该拖垮整个 bot
        log.exception("tick failed")

def shutdown(self, reason: str):
    # ...现有逻辑...
    try:
        self.tg.notify_shutdown(
            reason=reason,
            final_equity=self.equity,
            duration_s=(time.time() - self.start_ts),
            n_trades=self.session_trade_count,
        )
    except Exception as e:
        log.warning("tg notify_shutdown outer guard: %s", e)
```

**常见反模式**：

| 反模式 | 后果 | 正确做法 |
|--------|------|----------|
| `requests.post(...)` 无 timeout | 网络抖动时主循环卡死 | 显式 timeout=5 |
| `try/except HTTPError` | 超时、DNS fail 等 socket 异常漏网 | `except Exception` |
| HTTP 失败时 raise | 告警故障拖垮 bot | log.warning + 返回 False |
| 没有 rate limiting | 一个 bug 触发 1000 条告警，用户屏蔽 bot，交易所限流 | 按 key 限频 |
| rate limit 状态只在内存 | 重启后首事件必发，restart loop 时洪水 | 持久化到 json |
| 心跳不做当日去重 | `maybe_send_heartbeat()` 每分钟调一次 → 60 条心跳 | 用 last_heartbeat_date 比对 |
| 心跳用服务器本地时间 | 跨时区部署时人类看到的心跳时间和预期不符 | 统一用 UTC |
| 启动时没告警 | 用户不知道 bot 起来了没，得登录服务器查 | notify_startup 必发 |
| 关机不发告警 | crash 发生在凌晨，用户早上看价格才发现 | notify_shutdown 含 reason |
| 把完整 traceback 贴 Telegram | 超 4096 字符，消息被截断看不全 | 发首行 + 日志文件路径 |
| Telegram 命令控制无鉴权 | token 泄露 = 账户被控制 | 白名单 chat_id，见 7.7 |
| 未配置 token 时 raise | 不想用告警的用户被强制配置 | `enabled = bool(token and chat_id)`，no-op |

**与日志体系（3.8）的关系**：
- 告警和日志**不是二选一**，而是同一个事件的两种去向
- 所有 `self.tg.alert(...)` 的调用点，同一逻辑位置也应该有
  `log.warning(...)` 或 `log.error(...)`
- 告警消息倾向于"精简 + 人眼可读"，日志记录倾向于"完整 + 机器可解析"
- 事后复盘时，**日志永远是真相**——告警只是"那个时刻我们 push 出去过"的
  弱证据（可能发失败了）

### 3.11 Maker-First 执行协议（Maker-First Order Protocol）🔴 强烈推荐

**为什么是独立子维度**：Maker/Taker 费差在主流永续合约上通常是 3–4 倍
（Hyperliquid: 1.5bps vs 4.5bps；Binance VIP0: 2bps vs 5bps）。对一个
年换手率 5000%+ 的高频策略，这 3bps 差值一年就是 150% 的收益差距——
"entry 全部走 taker" 和 "entry 60% maker / 40% taker" 的复利效应，在长回测里
足以把一个 profit factor 1.05 的边缘策略变成 PF 0.95 的亏损策略。
但这个维度在 Skill 原有结构中散落在 2.1（成本模型）、2.6（费率敏感度）、3.2
（订单执行异常）中，缺少"一整套 Maker-First 下单协议"的系统化审计视角——
本节补齐这个空白。

**Maker-First 的核心设计理念**（来自 crypto-factor-mining-beta 真实实现）：

```
Entry（增加敞口）：
  1. 以 mid_price 下 GTC Limit 单（如果不穿价差则为 maker）
  2. 等待 LIMIT_TIMEOUT 秒（推荐 10–15s）
  3. 若完全成交 → execution_style = "limit_only"（全部 maker 费率）
  4. 若部分/未成交 → cancel，remainder 走 IOC 市价单
     → execution_style = "limit_then_market" 或 "market_ioc"（mixed 或 taker 费率）

Exit（减少/关闭敞口）：
  直接 IOC 市价单（reduce_only=True）→ 100% taker
  理由：出场时确定性 > 成本。等 maker 可能错过止损/再平衡窗口。

回测对齐：
  entry_maker_pct × maker_fee + entry_taker_pct × taker_fee  # 加权 entry 费率
  exit_taker_pct × taker_fee                                 # 出场费率（= taker_fee）
  其中 entry_maker_pct / entry_taker_pct 必须与实盘实测的 fill 分布匹配
```

**为什么这个设计好**（审计时必须理解的第一性原理）：

1. **Entry 有时间冗余，Exit 没有**：入场信号在 bar-T close 成形，下一次 rebalance
   是 bar-T+1 close — 有 24 小时的窗口。花 15s 等 maker 成本极低。
   而 exit/risk-off 可能是因为 regime 切换或止损触发，等待 = 在错误方向敞口加剧。
2. **费率省下 60% 以上**：entry 60% maker（1.5bps） + 40% taker（4.5bps）
   = 2.7bps，对比纯 taker 4.5bps，省 40%；若静态看 entry 一侧，maker 部分省
   67%。换手率越高，复利越大。
3. **回测-实盘可对齐**：假设"100% maker"会在实盘不可复制；假设"100% taker"
   会把 alpha 都吃掉导致没策略可跑。60/40 split 是可校准、可验证的现实假设。

#### 3.11.1 Entry 下单链路审计

```
□ 是否使用 limit → market 两阶段下单（而非纯 market 或纯 limit）？
□ Limit 价格取什么？
  - 推荐：mid_price（不穿价差 → 成为 maker，等 taker 来吃单）
  - 可选：贴近对手方 1 tick（跨越价差 → 立即成交但变 taker，失去 maker 意义）
  - 警告：如果 limit_px 总是跨越价差，那就是假 maker-first，实际 100% taker
  - 验证：grep 下单逻辑，确认 limit_px 计算没有加 spread_buffer（若有应该是负的，朝对手方反向靠近）

□ TIF（Time-In-Force）选择：
  - 第一阶段 Limit：应为 GTC（Good-Til-Cancel），否则无法等待 maker fill
  - 第二阶段 Market：应为 IOC（Immediate-Or-Cancel，带宽松价格 buffer 模拟 market）
  - 警告：若第一阶段用 IOC/FOK，limit 永远无法 rest，退化为穿价单 = 100% taker
  - 可选改进：使用 ALO（Add-Liquidity-Only，Hyperliquid post-only）确保 100% maker，
    但要处理"价格穿越时被拒"的错误路径

□ LIMIT_TIMEOUT 参数化：
  - 必须可配置（代码 default + env override）
  - 推荐默认：10–15s（太短 → maker fill 率低；太长 → 信号已"过期"）
  - env override（如 EXEC_LIMIT_TIMEOUT_SECONDS）应触发 startup warning，
    提醒确认回测 entry_maker_pct/entry_taker_pct 仍然匹配新 timeout
  - 反例：如果从 5s 改到 30s 但 backtest 还用 entry_maker_pct=0.50，
    实盘实际 maker fill 率 > 0.75，回测低估了收益（浪费 alpha）；反之亦然

□ Cancel-then-market 的正确顺序：
  - 超时后必须先 cancel 再 market，否则可能双重成交（残留 limit 和新 market 都成交）
  - Cancel 必须确认成功（cancel 返回 + _wait_for_order_closed 轮询）
  - Cancel 失败时不能继续下 market 单，必须 bubble up 为错误
  - 反例：fire-and-forget cancel，随后立即 market，可能导致 2×sz 敞口

□ 部分成交的处理：
  - 必须准确测量 limit 阶段成交了多少（filled_at_limit）
  - Remainder = target_sz - filled_at_limit，然后 market 单只下 remainder
  - remainder × ref_px 若 < min_trade_notional，应跳过 market 单（避免触发交易所 $10 min）
  - 反例：不检查 limit 阶段成交，market 单总是下完整 sz → 超额建仓
```

#### 3.11.2 Fill Detection 可靠性（最易出 bug 的地方）

```
问题：SDK 的 limit order response 可能返回"status=resting"，但实际在 sleep 期间
被对手方成交。如果只依赖 order response 的 filled_sz，会严重漏计 maker fills。

正确做法（pre-post position delta）：
  pre_pos = get_positions_as_dict()[coin]
  place_limit_order(...)
  sleep(LIMIT_TIMEOUT)
  cancel_order(...)  # 包含 _wait_for_order_closed
  post_pos = get_positions_as_dict()[coin]
  filled_at_limit = abs(post_pos - pre_pos)  # 这才是真正的 limit 成交

□ 是否使用 pre/post position delta 测量 limit 阶段 fill？
□ 是否在 cancel 完成 → position query 之间有 guard 防止 race（等待所有 pending fill settle）？
□ 是否处理 coin 不在 positions dict 的情况（新开仓的 coin）？
□ Fee type 标记逻辑：
  - filled_at_limit == target_sz   → fee_type = "maker"
  - filled_at_limit > 0 but < target → fee_type = "mixed"
  - filled_at_limit == 0             → fee_type = "taker"
  - 每笔 trade 必须有明确 fee_type，不能默认 "unknown"

□ execution_style 分类（用于事后校准 entry_maker_pct）：
  - "limit_only"         — full maker fill
  - "limit_then_market"  — partial maker + partial taker
  - "market_ioc"         — 0 maker, all taker
  - "market_reduce_only" — exit，100% taker
  - 每笔 trade 必须记录 execution_style，否则无法反推实盘真实 maker pct
```

#### 3.11.3 Exit 走 Taker 的正当性（不要偷懒在 Exit 也用 maker-first）

```
□ Exit/reduce-only/stop-loss 是否统一走 market IOC（而非 limit→market）？
□ 对应回测的 exit_taker_pct 是否 = 1.00？
□ 常见错误：
  - "为了省费用，exit 也用 maker-first"
    → exit 慢一步 = 错过 rebalance 窗口 = 持仓偏离 target
    → 回测假设 exit 即时成交，实盘慢半拍 = alpha 蒸发
  - "stop-loss 用 limit 以避免滑点"
    → 止损最怕的就是不成交；limit 止损在极端行情中必然不成交
    → 必须 market 或用 stop-market order

□ Exit 的 reduce_only 标志：
  - 必须为 True，防止 flip（exit 超量反向开仓）
  - 全仓模式下 reduce_only 可以避免"本想平仓 100 但实际建了 50 空单"的错误
```

#### 3.11.4 费率闭环校准（Fee-Split Calibration Loop）

```
部署后 7-14 天，必须用实盘 trade logs 反推真实 maker/taker split，再回馈到回测 config。
这个循环是 Maker-First 设计能否兑现"既省费又对齐回测"的关键——没有校准闭环，
回测和实盘永远是两个平行宇宙。

Step 1 — 从实盘日志统计 fill 分布：
  jq -c 'select(.event=="trade_executed" and .direction=="entry")' live_logs/*.jsonl \
    | jq -s '
        group_by(.execution_style)
        | map({style: .[0].execution_style, count: length, sum_filled: (map(.filled_sz * .avg_px) | add)})
      '

Step 2 — 计算 notional-weighted maker pct：
  total_entry_notional = Σ filled_notional (direction=="entry")
  maker_notional = Σ filled_notional where execution_style=="limit_only"
                  + Σ (limit_filled × limit_px) where execution_style=="limit_then_market"
  realized_maker_pct = maker_notional / total_entry_notional

Step 3 — 对比回测假设：
  backtest.entry_maker_pct (当前 config) vs realized_maker_pct (实测)
  diff = |backtest - realized| / backtest
  - diff < 10% → ✅ 对齐良好
  - diff 10-25% → 🟡 轻微偏离，建议下个版本校准
  - diff > 25% → 🔴 严重偏离，必须立即更新回测 config 并重跑 sensitivity

Step 4 — 更新回测 config：
  将 realized_maker_pct 写回 strategy config（entry_maker_pct / entry_taker_pct）
  同时在 git commit message 中注明校准来源（"calibrated from 2026-04-10~04-24 live
  fill data, N=437 entries"）。这保留审计链。

Step 5 — 重跑 sensitivity check：
  以新 entry_maker_pct ± 10pp 跑一组回测（如 realized=0.62 时，跑 0.52/0.62/0.72）
  → 如果 CAGR 变化 < 5%，策略对 maker pct 假设不敏感（好）
  → 如果 CAGR 变化 > 20%，策略严重依赖 maker 假设（红旗，需加 fee robust 化）

□ 是否有自动化脚本跑这个校准流程？（推荐放在 scripts/calibrate_fee_split.py）
□ 是否有周期性校准规则？（推荐：每次部署新版本 + 每 4 周例行一次）
□ 校准结果是否写入 review 报告？（不能只改 config 不留记录）
```

#### 3.11.5 环境变量与回测 config 的联动警告

```
□ 与 execution 行为相关的 env vars 是否在 startup 时检查并警告？
  必查项：
  - EXEC_LIMIT_TIMEOUT_SECONDS — 影响 maker fill 率
  - EXEC_MIN_TRADE_NOTIONAL    — 影响 small trade skip 率
  - EXEC_IOC_PRICE_BUFFER_PCT  — 影响 IOC market 的最终成交价

□ 覆盖代码 default 时，是否提示"请重新校准回测假设"？
  推荐 log 模板：
    WARNING: EXEC_LIMIT_TIMEOUT_SECONDS overrides code default: effective=30s,
             code_default=15s. Confirm backtest entry_maker_pct/entry_taker_pct
             still match live execution.

□ 是否有机制防止 env override 悄悄漂移回测-实盘对齐？
  - 推荐：将 effective execution config 写入 per-run 日志 + monitor_export.json
  - 审计方法：启动日志中搜索"execution_config_override"事件
```

#### 3.11.6 极端场景防御

```
□ Mid-price 不可用时的降级：
  - 若 get_mid_price 失败（订单簿空、WS 断连），降级到 ref_px（上一个 known price）
  - 禁止 fallback 到 0 或 None（会导致 limit 价格异常）
  - 日志必须记录"mid price unavailable"事件

□ Limit 单 Rejection 的处理：
  - 可能原因：价格越界（HL 有 50% 价差限制）、notional < $10、reduce-only 不匹配
  - 被拒时必须立即降级到 market 单（不能 retry limit，浪费 timeout）
  - 每个 rejection reason 应分别 log，便于诊断

□ 并发 entries 的 race condition：
  - 如果 rebalance 同时对 20 个 coin 下 entry，每个都 sleep(LIMIT_TIMEOUT) 不能串行
  - 必须用 ThreadPoolExecutor 并发，每个 entry 独立计时
  - 审计：确认 concurrent entries 的 pre/post position snapshot 是每 coin 独立获取

□ Kill switch 触发时：
  - Maker-First 逻辑必须被 bypass，所有 open 仓位立即 market close
  - 审计：kill switch path 是否调用 _execute_exit（market）而非 _execute_entry（limit-first）
```

#### 3.11.7 回测侧的 Maker-First 费率建模检查清单

```
与 3.11.1-3.11.6 实盘侧审计对偶，回测侧必须实现以下模型：

□ BacktestConfig 必须暴露以下字段（使用 dataclass default 作为单一真相源）：
  - maker_fee / taker_fee (来自交易所实际费率)
  - entry_maker_pct / entry_taker_pct (sum = 1.0)
  - exit_taker_pct (通常 = 1.0)

□ 加权费率计算（用于每笔 entry）：
  entry_fee_rate = entry_maker_pct × maker_fee + entry_taker_pct × taker_fee
  exit_fee_rate  = exit_taker_pct × taker_fee

□ Fee 计算必须 based on turnover（而非单纯 trade count）：
  fee_cost_per_bar = turnover_i × entry_fee_rate  (for entries)
                   + turnover_i × exit_fee_rate    (for exits)
  反例：fee = n_trades × flat_fee — 完全错误，忽略了 position size

□ 滑点必须独立于 maker/taker 费率建模：
  - slippage_pct 代表 "IOC 市价单相对 mid 的价差成本"
  - 不能把 slippage 和 taker_fee 合并成"effective taker cost"，因为两者的物理含义不同
  - Maker 成交没有 slippage（你就是价差的一部分），所以 maker 部分只扣 maker_fee

□ Sensitivity check（必跑）：
  - entry_maker_pct 从 0.0 到 1.0 以 0.1 步长 sweep，观察 CAGR 曲线
  - 如果 maker_pct = 0.0 时策略亏损 → 警告：alpha 严重依赖 maker fill
  - 如果曲线变化 < 10pp → 策略对 fee split 假设不敏感（健康）
  - 如果曲线变化 > 50pp → 策略不稳健，必须先降低换手率再谈部署

□ Stop-loss / forced-close 必须用 exit_taker_pct 而非 entry 费率：
  grep "stop_loss\|forced_close\|margin_liquidation" 确认 fee 计算用的是 exit 费率
  反例：用 entry_maker_pct × maker_fee 计算止损费用 — 低估真实成本
```

#### 3.11.8 Maker-First 审计报告模板

```
每次审计输出以下表格：

| 检查项 | 实盘实现 | 回测对齐 | 风险等级 |
|--------|---------|---------|---------|
| Entry 两阶段（limit→market） | ✅/❌ | entry_maker_pct ≈ realized? | ... |
| Exit 单阶段（market IOC）    | ✅/❌ | exit_taker_pct = 1.00?       | ... |
| LIMIT_TIMEOUT 可配置         | ✅/❌ | env override 有警告?         | ... |
| Limit 价格 = mid             | ✅/❌ | 不穿价差                      | ... |
| TIF = GTC (limit) / IOC (market) | ✅/❌ | —                       | ... |
| Pre-post position 测 fill    | ✅/❌ | —                             | ... |
| Cancel 确认成功              | ✅/❌ | —                             | ... |
| execution_style 记录         | ✅/❌ | —                             | ... |
| fee_type 分类                | ✅/❌ | —                             | ... |
| min_trade_notional 检查      | ✅/❌ | 回测 config 同步?              | ... |
| Reduce-only exit             | ✅/❌ | —                             | ... |
| Fee-Split 校准流程           | ✅/❌ | realized vs config diff < 10%? | ... |
| Mid-price 降级处理           | ✅/❌ | —                             | ... |
| Kill switch bypass maker     | ✅/❌ | —                             | ... |
| Sensitivity on entry_maker_pct | — | CAGR 变化 < 20pp?              | ... |

风险等级：
- 🔴 Critical：实盘跑纯 taker 但回测假设 maker-first（或反过来）→ 立即修复
- 🟠 High：Fill detection 不可靠（用 order response 而非 position delta）
- 🟡 Medium：没有 fee-split 校准流程 / env override 无警告
- 🟢 Low：所有项实现合理，仅轻微改进空间
```

#### 3.11.9 Unknown-State Settlement 的保守策略（Maker Overfill 防御）

**问题场景**：Maker-first 两阶段执行中的关键一步是 cancel_and_settle —
它负责取消挂在交易所的 limit leg，并同步返回 limit 已成交的数量。但这一步
**可能失败**（网络抖动、交易所 rate limit、API 版本兼容问题、-2011 Unknown
Order 等）。此时代码只知道"我不知道 limit 到底成交了多少"，既可能全成交
可能全未成交，也可能部分成交。

**朴素但错误的做法**（Maker-First 第一版常见陷阱）：

```python
except CancelSettleError:
    maker_qty = Decimal(0)          # ❌ 假设没成交
    # 然后补一个全量 IOC market remainder
    self.market_ioc(order.symbol, side, order.qty)
```

这个假设的**灾难性后果**：如果 limit 其实已经成交（哪怕是部分），IOC 又下了
全量 → **overfill**。你的账户持仓会超出 target，直到下一个 tick 的 reconcile
才被发现 — 在此期间你扛着不受控的额外敞口，而且 reconcile 修复 overfill 只能
反向平仓（双份手续费 + 滑点 + 可能的 PnL 损失）。

**正确的对偶策略**：

```python
except CancelSettleError as e:
    maker_assumed_unknown = True
    maker_qty = order.qty               # ✅ 假设已全部成交
    maker_price = limit_price
    maker_raw = {
        "status": "UNKNOWN_CANCEL_SETTLE_FAILED",
        "assumed_full_maker": True,
        "executedQty": str(order.qty),
        "avgPrice": str(limit_price),
        "clientOrderId": cid,
        "error_code": str(e.code),
        "error_msg": e.msg,
    }
    # ⚠️ 不下 remainder IOC — 让下一 tick 的 reconcile 修复 underfill
```

**为什么"假设全成交"是更安全的默认**（第一性原理）：

```
│ 假设类型    │ Limit 真实状态 │ 系统行为        │ 结果         │
│────────────│───────────────│────────────────│─────────────│
│ 假设 0 成交 │ 实际 0 成交    │ IOC full qty   │ 正确         │
│ 假设 0 成交 │ 实际部分成交    │ IOC full qty   │ 🔴 OVERFILL │
│ 假设 0 成交 │ 实际全成交     │ IOC full qty   │ 🔴 2× OVERFILL │
│ 假设全成交  │ 实际 0 成交    │ 不下 remainder │ 🟡 UNDERFILL │
│ 假设全成交  │ 实际部分成交    │ 不下 remainder │ 🟡 UNDERFILL │
│ 假设全成交  │ 实际全成交     │ 不下 remainder │ 正确         │

OVERFILL 代价：立即扛超量敞口 + 下 tick 必须反向市价平（2× 手续费 + 滑点）
UNDERFILL 代价：等 1 tick reconcile 补单（1× 延迟，0 额外手续费）
→ Underfill 是严格更便宜的错误模式。
```

**审查清单**：

```
□ executor 中 cancel_and_settle 的所有异常分支是否采用"假设全成交"策略
  - 搜索 `except.*CancelSettle\|except AsterError.*settle` 找到所有 catch 点
  - 确认每个 catch 分支内 maker_qty = order.qty 而非 Decimal(0)
  - 确认没有在异常分支里下 remainder / fallback market

□ 是否引入独立的 execution_style 标记这种状态
  - 推荐：STYLE_LIMIT_UNKNOWN
  - 区别于 STYLE_LIMIT_ONLY（已确认全成交）和 STYLE_LIMIT_THEN_MARKET
    （已确认部分+补 market）
  - 作用：让 monitor / fee-split calibration 能识别出"本 tick 的 maker
    ratio 不可知"，不把这类 fill 算进 realized_maker_pct 分母

□ maker_raw 中是否保留原始 error_code / error_msg
  - 用于事后从 trade log 反查异常频率 — 如果 UNKNOWN 比例高，说明
    cancel_and_settle 的 API 层不稳定，需要定位根因
  - 推荐字段：{status, assumed_full_maker: True, error_code, error_msg,
    clientOrderId, executedQty, avgPrice}

□ Reconcile 的可靠性是这个策略的唯一后盾
  - 每个 tick 开始必须对 local position 与 exchange position 做 diff
  - 发现 local < exchange（underfill 等待补）→ 下一次 rebalance 自然补齐
  - 发现 local > exchange（异常，不应该发生）→ 对齐为 exchange，log WARN
  - 如果 reconcile 本身不可靠或缺失 → 🔴 这个"假设全成交"策略也不能用，
    退回到"只做 maker、拒绝 cancel-and-settle 失败" 的更保守路径

□ 对应的 fill detection 测量方式
  - 如果 executor 既支持 pre/post position delta 测 maker fill（见 3.11.2）
    又遇到 cancel_and_settle 失败 → 先看 position delta，能得到 ground truth
    的就用 ground truth，得不到才退到"假设全成交"
  - 顺序：position delta > assumed_full_maker > assumed_no_maker（绝不用）
```

**配套监控**：在 monitor_export.json 的 health 段内增加 `execution_unknown_count_24h`
计数器，让监控中心能在 UNKNOWN 占比异常时触发告警。如果 24h 内 UNKNOWN >
total_entries × 20% → 说明 API 层不稳定，需要人工介入；长期在低位（< 2%）
→ 属于正常的网络抖动，当前策略可以继续运行。

---

**与 2.1 / 2.6 / 3.2 的协同**：
- **2.1 成本模型**：回测的 maker/taker 拆分只是费率输入；本节定义如何产出这些拆分
- **2.6 费率复利效应**：回测的 commission sensitivity 依赖 entry_maker_pct
  假设的真实性；本节负责定期校准这个假设
- **3.2 订单执行异常**：处理订单 level 的 retry/partial fill；本节处理"协议级"
  的 limit→market 时序和 fee 语义

### 3.12 时间/环境前置（Timing & .env Prerequisites）🔴 强烈推荐

> **背景故事 1（NTP）**：2026-05-14 codex R13 P2 找到的 timing fragility。
> v1.37 cron 设计在 01:00:01 UTC（让 D 00:00 那根 1h bar 闭合），但服务器
> NTP 漂移 > 500ms 时，cron 可能在 wall-clock 00:59:59.x 触发，data_refresh
> 排除还未闭合的 bar，partial-bar guard trip，cycle halt。
>
> **背景故事 2（.env）**：codex R15 P2 找到的 deploy-blocker。Runbook 写
> "edit .env, then run `python3 -m src.live.run_bot`"，但 `run_bot.main()` 只
> 读 `os.environ`，不主动 parse `.env`。Smoke 脚本和 leverage 工具都自己
> parse，但主 bot 没有 → 操作员严格按 runbook 执行 → 静默 DRY-RUN，没下
> 真实单。Fail-closed but 逻辑上就是部署失败。

**核心问题**：实盘 bot 的前置环境（系统时间精度 + 环境变量加载）在 deploy
runbook 里被默认"应该正常"，但实际部署时这两件事经常出问题，而且都是
fail-closed（不会出错单，但会静默不工作或意外 halt），最难诊断。

**审查清单**：

```
□ 3.12.1 NTP 时间同步
   □ Deploy runbook 是否明确要求 NTP daemon（chrony / systemd-timesyncd）？
   □ 是否在 smoke / pre-flight 中校验 NTP 状态？
     ```bash
     timedatectl status   # 应显示 "NTP service: active"
     ```
   □ Cron 时间是否在 bar 边界后留 buffer（≥ 1s）应对漂移？
     - 1s buffer：modern NTP 漂移 < 100ms，足够
     - 5s+ buffer：过保守，每秒 ~0.045%/position×turnover 的 drag
     - 没 NTP：1s 不够，必须装 NTP
   □ Buffer 大小是否由数学决定，不是 "preferably" 决定？（见 6.5）

□ 3.12.2 .env 加载一致性
   □ Main bot entry（run_bot.py / main.py）是否 parse .env？
   □ Smoke / 辅助脚本是否 parse .env？
   □ **两者必须一致** — 不然 operator 跟着 runbook 跑会陷入"smoke 看
     起来加载了 .env，但实际 bot 没加载"的悖论
   □ 推荐实现（与 smoke 共享）：
     ```python
     def load_env_file():
         env = Path(__file__).parent / ".env"
         if env.exists():
             for line in env.read_text().splitlines():
                 line = line.strip()
                 if line and not line.startswith("#") and "=" in line:
                     k, v = line.split("=", 1)
                     os.environ.setdefault(k.strip(), v.strip())
     ```
   □ 用 `setdefault`（而非 `[]=`），让 explicit export 仍然 win
   □ 注意：模块顶层 import 的 const（如 `STRATEGY_NAME =
     os.environ.get(...)`) 是 module-load 时捕获的；这种值如果要
     被 .env 覆盖，必须在 main() 第一行 load_env_file，且 .env-only
     override 模块顶层 const 是 caveat（需要 export）

□ 3.12.3 启动脚本和实际入口的一致性
   □ Runbook 写 "python3 -m mymodule.main"，main() 的第一行是否
     做了所有必要的 env 准备（NTP check, .env load, signal-handling
     setup）？
   □ 如果某些 env-load 逻辑在外部 wrapper（systemd unit, docker
     entrypoint），文档里必须明示"不能直接 python -m ..."
   □ 不要让 operator 猜：runbook 给出的命令必须能直接拷贝执行

□ 3.12.4 时间精度敏感性测试
   □ 故意把系统时间往前调 1s（模拟 NTP 漂移）跑一次 dry-run
   □ 看 partial-bar guard / staleness 检查会否 trip
   □ 故意往后调 1s 也跑一次，看是否照常工作
   □ 这种 chaos test 在 deploy 前做一次比上线后再发现问题便宜得多
```

**自动化探测**（粗略 grep）：

```bash
# .env 加载位置一致性
grep -rn "def load_env\|os.environ.setdefault\|dotenv" src/ scripts/

# 主入口是否 load .env
sed -n "/def main/,/^def /p" src/live/run_bot.py | grep -i "env\|load"

# NTP / timing 文档
grep -rn "NTP\|timedatectl\|chrony" docs/ README.md
```

**Action priority**：

1. 🔴 Main bot entry 不 load .env，runbook 又说"编辑 .env" → silent DRY-RUN
2. 🔴 没有 NTP requirement 在 runbook，cron buffer < 1s → 服务器漂移即 halt
3. 🟡 Smoke 和主 bot 的 .env 加载不一致 → 给 operator 信号不一致的 cue
4. 🟢 没有 chaos test，但其他 check 都到位 → 上线后第一周观察

### 3.13 订单量化与交易规则约束（Tick/Lot/MinNotional Quantization）

**为什么重要**：交易所对每个 symbol 有 tickSize（价格步长）、stepSize（数量步长）、
minNotional（最小名义价值）约束。量化不当是实盘下单被拒的最常见原因（Binance
-1013 / -4003 / -1111 系列错误），且往往只在小额仓位或小币种上暴露 — 测试时
用 BTC 大仓位全部通过，上线后小币调仓全军覆没。

```
□ 数量取整方向必须是 floor（向下取整到 stepSize 整数倍）
  - round() 可能向上取整 → 下单量超过意图 / available balance 不足被拒
  - floor 后必须复查 notional 仍 ≥ minNotional，否则跳过该单并记录 skip 原因
□ 价格取整到 tickSize
  - buy limit 向下取整、sell limit 向上取整（保守方向），或统一取整后
    校验未穿越对手价
□ 精度用 Decimal 或整数 tick 计数，不用 float 直接格式化
  - float 会产生 "0.30000000000000004" 类字符串 → 交易所拒单
  - 反例：str(qty)；正例：按 stepSize 的小数位数 quantize 后格式化
□ exchangeInfo / meta 的刷新机制
  - tickSize/stepSize/minNotional 会随交易所调整而变化：启动时拉取 + 定期刷新
  - 硬编码精度表 → 🔴（交易所调整精度当天全部下单失败）
□ 回测镜像：回测的最小交易约束是否与实盘一致
  - 回测允许任意小数仓位但实盘有 minNotional → 小额调仓在实盘被跳过，
    weights 漂移累积 → 回测-实盘轨迹分叉
  - 参考 3.11.1 的 min_trade_notional skip 逻辑，回测应模拟同样的 skip
□ 累积偏差监控
  - 多次小额 skip 的累积 |target - actual| 偏差应有监控；建议在
    monitor_export 的 health 段记录 skipped_notional_24h，超过 equity 1% 告警
```
