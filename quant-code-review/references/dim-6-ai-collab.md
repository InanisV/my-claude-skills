> **quant-code-review · 维度参考文件** — 由 SKILL.md 按维度 P.3 的适用性裁定按需加载，不要无差别全量读入。
> 文中交叉引用（如"见 2.8"、"参见 4.6"）按维度编号到 references/ 对应文件查找。

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

### 6.5 外部 Review 反馈不盲从 — 分类 + 算账（External Review Discipline）🔴 高优先级

> **背景故事**：2026-05-14 `crypto-deep-learning-beta` R12–R15 codex 审计循环。
> R13 codex 写："01:00:01 UTC is safe by assertion but tight operationally.
> **preferably** use a few-second buffer, e.g. 01:00:05 UTC"。Claude 直接接受了
> 这条建议，把 cron 从 01:00:01 改成 01:00:05，并 propagate 到 3 个 commit。
> Tom 在 R15 后追问："为什么不是 1s?"。Claude 这时做了 30 秒的算账：
> `4s × 30 positions × √(0.70²/yr / sec) × 20% turnover × 250/yr ≈ 2%/yr drag`
> vs `NTP-drift miss < 1/yr × 0.4%/event = 0.001%/yr`。Net = -2%/yr → 数学
> 明确否决了 codex 的建议。Cron 在 commit `6fc988d` 改回 01:00:01。
>
> 教训：Claude 把 codex 当成了 authority 而不是 reviewer。"preferably" 是
> 意见，不是 bug。三轮审计里有 3 处类似的 deference（cron buffer 是错的，
> 另外两处侥幸数学支持，但 process 同样错了 — 没算账就改）。

**核心原则**：外部审计（codex / peer review / lint / LLM suggestion）的反馈
不是 spec，是 raw findings。**接受前必须做分类 + 算账。**

```
□ 6.5.1 每条 finding 分类：Bug vs Preference
   □ Bug：具体 invariant 违反，可被 grep / diff / A-B 验证
     范例："build_panel 在 fillna(0.0) 处会掩盖 stale funding"
     → 是 bug，必修
   □ Preference：含 softening language 的意见
     范例："preferably 5s buffer", "I would halt", "tight operationally"
     → 是意见，需算账

   触发词清单（看到任意一个 → slow down）：
   - "preferably" / "would be safer" / "tight operationally"
   - "consider" / "may want to" / "I suggest" / "I would"
   - "tighter would catch X earlier"
   - "irrelevant slippage" / "small impact"（没量化的）
   - "best practice" / "stricter default"（没引证的）

□ 6.5.2 Preference 必须算账（EV math）
   公式：
     net = avoided_loss_per_event × event_frequency
           - drag_from_change × cycles_per_year

   - net > 0 → 接受变更，math 写在 commit body
   - net < 0 → 保留旧值，commit body 写 "[NOT FIXED] <finding>: rejected — net = X-Y = -Z"
   - 算不出 inputs → 问用户，**不要默认接受**

   范例（来自 R13 cron buffer，反例）：
     change cost  = 4s × 30 pos × √(0.70²/yr / sec) × 20% × 250/yr ≈ 2%/yr drag
     change benefit = (NTP miss < 1/yr) × 0.4%/event ≈ 0.001%/yr
     net = 0.001% - 2% = -2%/yr → 不接受。

□ 6.5.3 尊重用户的既往判断
   如果用户对同一参数已经表达过明确立场（"等 1 秒就够了"），
   默认动作是**保留用户的选择**。覆盖必须满足：
   □ codex 给出 NEW FACT (not new opinion):
     ✅ "code path crashes when X"
     ✅ "empirical A/B shows X% impact"
     ❌ "I would set this differently"
     ❌ "tighter is conservative"

□ 6.5.4 PASS WITH FOLLOWUPS ≠ "must close N followups"
   多轮审计的 PASS WITH FOLLOWUPS 经常带 P2/P3 preferences。
   loop exit 不等于必须关闭每一条。如果所有 followup 都是
   math-negative preferences，干净 exit 是合法结局。
   commit log 写 "considered + rejected" 即可。

□ 6.5.5 Audit-of-audits（部署前必跑）
   多轮审计循环结束 / 部署前必须出一张回顾表：
   | Round | Finding | Bug or Pref? | Math support? | Action | Status |
   如果 preferences 占比 > 10%，说明审计 prompt 太松，或者
   fix loop 把每条 finding 都当 bug 处理（deference 失败）。

□ 6.5.6 Anti-pattern: "Codex said so, I changed it"
   ❌ "Codex R13 found X, so I changed Y to Z."
   ✅ "Codex R13 flagged X as preference (softening language).
      Math: ... Net = -2%/yr. KEEPING old value. Documented."
   第一种是 deference，第二种是 review。永远写第二种。
```

**审计触发**：每次跑外部审计（codex L1/L2/L3、peer review、LLM critique）
之后，audit 报告需新增 triage 段：每条 finding 标 [Bug] / [Pref-accepted] /
[Pref-rejected]，pref 必须附 EV math。

**参考**：`codex-audit` skill 的 `references/finding-triage.md` 有完整 rubric
+ trigger phrases 表格 + 3 个 worked examples（cron buffer revert / shadow
halt 侥幸 / funding 24h→12h defensible）。
