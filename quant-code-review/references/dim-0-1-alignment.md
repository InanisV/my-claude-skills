> **quant-code-review · 维度参考文件** — 由 SKILL.md 按维度 P.3 的适用性裁定按需加载，不要无差别全量读入。
> 文中交叉引用（如"见 2.8"、"参见 4.6"）按维度编号到 references/ 对应文件查找。

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

### 1.5 Bar 时间约定审计（Bar Timing Convention）🔴 高优先级

> **背景故事**：2026-05-14 `crypto-deep-learning-beta` codex R12 P0。
> binance 1h klines 用 `open_time` 索引（每根 bar 代表 `[open_time, open_time+1h)`），
> 而 `pandas.resample("1D", label="right", closed="right")` 锚定在 UTC 午夜。
> 结果：bin 标签 `D 00:00` 实际覆盖的 open_times 是 `(D-1 00:00, D 00:00]`，
> 包含 24 行 open_times `D-1 01:00 ... D 00:00`。其中最后一行 `open_time=D 00:00`
> 的那根 1h bar **要等到 D 01:00 才闭合**。所以 1D bar 标签 "D 00:00" 的 close
> 实际上是 D 01:00 的价格，bar 内容是 `[D-1 01:00, D 01:00) UTC`。
>
> 实盘后果：cron 在 D 00:00:01 触发时，data_refresh 排除了未闭合的
> `open_time=D 00:00` 那根 1h（因为 `open_time + 1h > now`），导致 1D resample
> 得到的 bar 只有 **23 个 subbars**，"close" 变成 D 00:00 的价格。
> A/B 实测一根 BTC bar 差 **$650 / 0.83%**。整个回测使用的是 24 subbar 的
> 数据，实盘用 23 subbar → 结构性偏移。
>
> 这个 bug 在 codex 找到之前，4 轮内部 review 全部漏掉。

**为什么必须做**：
- 1h kline 的索引（open_time vs close_time）+ resample 的 boundary
  （closed/label）组合形成的 **bar 真实时间范围**，跟人凭直觉理解的
  "calendar day D" 经常不一样
- 实盘 cron 时间必须对齐"bar 内容真正闭合"的时刻，而不是"bar 标签是今天"
- 用 close_time 重新索引能让 bar 时间范围回到自然 calendar day，
  但代价是整个 alpha-lab 的 hyperparameter 都要重训（R12 实测：
  v1.37 CAGR 从 +3583% 跌到 +1267%，-65%）

**审查清单**：

```
□ 1.5.1 索引 vs 边界 = 实际时间范围
   □ 找到 kline 加载位置（如 data_loader.load_klines_1h）
   □ 确认索引列：open_time 还是 close_time？
   □ 找到 resample 调用：参数 closed=left/right? label=left/right?
   □ 推导"标签 X 的 bar 真实代表哪段 wall-clock 时间"
     - open_time index + closed=right + label=right + 1D:
       bar "D 00:00" = open_times (D-1 00:00, D 00:00]
                     = wall-clock [D-1 01:00, D 01:00)  ← 注意偏移 1h
     - close_time index + closed=right + label=right + 1D:
       bar "D 00:00" = close_times (D-1 00:00, D 00:00]
                     = wall-clock [D-1 00:00, D 00:00)  ← 自然 calendar day

□ 1.5.2 实盘 cron 时间匹配
   □ 找到实盘 cron 调度（systemd / cron / loop sleep）
   □ 推算 cron 触发时，最新 1D bar 是否有完整 N 个 subbars
   □ 如果不是 N 个，可能是：(a) bar 未完全闭合，(b) cron 太早，
     (c) 索引/边界约定与回测不一致
   □ 关键：bar.close 的"真实时间" vs cron 时间的差距 = 实盘
     vs 回测的入场价格偏移 = 系统性 drag

□ 1.5.3 Partial-bar guard
   □ compute_weights / 信号入口必须断言"最新 bar 是完整 bar"
   □ grep "len(in_bin)" / "n_subbars" / "subbars" 检查是否有
     bar 完整性校验
   □ 缺失的话补一个 cheap check（如读 BTC 1h parquet，count
     open_times in (last_bar - 1d, last_bar]，应 = 24）
   □ 缺失 + 实盘在跨日刚开始时跑 → 🔴 已经悄悄用了 23-subbar 数据

□ 1.5.4 数据 refresh 的 boundary filter
   □ data_refresh 在 fetch klines 时是否过滤未闭合的 in-progress bar？
     通常 binance API 会返回当前小时的未完结 kline
   □ 标准做法：保留 open_time + interval_ms ≤ now 的 bar
   □ 缺失这个 filter → 数据里混入未闭合 bar，所有下游 resample 都坏
```

**自动化探测**（粗略 grep）：

```bash
# 找索引设置
grep -rn "set_index.*open_time\|set_index.*close_time" src/

# 找 resample 调用 + 参数
grep -rn "resample(" src/ | grep -v test

# 找 bar 完整性校验
grep -rn "subbars\|n_subbars\|24.*hours.*bar" src/
```

**Action priority**：

1. 🔴 索引约定 mismatch（回测和实盘的索引列不一致）→ **数据来源在两边
   要完全一致**，否则所有 close 价都偏 1h
2. 🔴 resample 边界 mismatch（一边 closed=right，另一边 closed=left）
   → 任意一个 bar 的 close 价都不一样
3. 🟡 cron 时间错位（数据约定正确但 cron 没等到 bar 完整闭合）→
   实盘吃 partial aggregate
4. 🟢 没有 partial-bar guard（约定都对，但缺乏 defense-in-depth）→
   加 `_assert_N_subbars` 类断言

**重要：换索引约定 = 重做 alpha-lab**

如果发现回测用的是不优 convention，**不要直接换索引重新跑**。R12 实测
教训：v1.37 在 open_time 上 CAGR +3583%，换成 close_time 后 CAGR 跌到
+1267%（-65%）。Hyperparameter 全部都是 alpha-lab 针对原 convention
搜出来的，换了 convention 等于在新 distribution 上跑一个未优化的
strategy。RL boost 会自动重训，但~50 个 hardcoded gates/thresholds/
scale 不会。完整 re-tuning 需要重做 alpha-lab，1-2 周以上。
