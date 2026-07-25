> **alpha-lab · 参考文件** — 由 SKILL.md 按场景按需加载（何时读见 SKILL.md 的 Reference 索引表）。

# 审计协议集：事故调查 / 多轮独立审计 / 修复回归预防 / 四类审计观点

## 🔴 事故调查方法论（Incident Forensics Protocol）

**实盘出事后，AI 最容易犯的错是"先构造叙事，再找支撑证据"。
正确的顺序是反的：先穷尽证据，再允许叙事浮现。**

### 铁律

```
1. 先读文档再说话
   → 第一个 tool call 必须是 Glob/Read 找项目中的 audit/incident/postmortem 文件
   → 通读完毕之前，不允许说任何带百分号的归因

2. 数据 → 执行 → 算法（诊断顺序）
   → 数据层：回测和实盘用的数据一样吗？universe、价格源、费率、funding
   → 执行层：下单、杠杆、wick check、滑点有偏差吗？
   → 算法层：因子计算、选币逻辑、仓位管理有 bug 吗？
   → 上游没修之前，不要推进下游的 A/B 实验

3. 区分根因和放大器
   → 测试方法：假设只修这一层，其他层不动，问题是否消失？
   → 只有回答"会"的那一层才是根因
   → AI 天然偏好修"cool bug"（算法层），回避修"boring root cause"（数据/工程层）

4. 区分数据采集缺口和 survivorship bias
   → set(live) - set(bt) 里的亏损币，先查 onboardDate
   → age > 1 year 的币缺失 = 数据采集缺口（修数据管道）
   → age < listing_date_of_data_snapshot 的币缺失 = 真 survivorship（修采集逻辑）
   → 两种病理的修复方案完全不同

5. 不要编造精确数字
   → "主犯 70% / 从犯 20% / 帮凶 10%" — 除非有 groupby 可以复算，否则禁止
   → 算不出来用模糊词："大部分"、"一部分"、"少量"
```


---

## 🔴 多轮独立审计协议（Multi-Round Independent Audit Protocol）

**最危险的 bug 不在第一遍审计中发现。它们藏在"修了上一个 bug 之后引入的代码"
里，或者藏在"两个独立正确的设计组合起来错了"的接缝里。这两类 bug 永远需要
至少 2-3 轮独立审计才能挖出来。**

### 核心数据（来自 R89.7 Phase 0 实战）

```
轮次              发现方式                  找到的真问题数
───────────────────────────────────────────────────────────
Round 1 (清单式)   带 verification 清单      3🔴 + 8🟡
Round 2 (清单式)   带 P0.5 修复清单          1🔴 (前轮修复引入) + 2 并发缺口
Round 3 (开放式)   无清单, "你自己审"        1🔴 (组合 bug) + 1 文档残留
Round 4 (Phase 1)  开放式, 第一次审 Phase 1  5 P0 + 3 P1 + 设计层 bug → FAIL
```

**关键观察**：
- Round 2 找的 1🔴 是 Round 1 的修复**引入**的（保留 unlink-on-release "做 housekeeping"）
- Round 3 找的 1🔴 是清单**永远不会列**的组合 bug（send-fail 不推 cooldown
  + Markdown 默认 = CRITICAL 永久 silent drop）
- 每轮都收敛但**永远不会零产出**——直到 Phase 1 的 FAIL 出现新一类问题

### 在量化研究中的对应

```
量化研究中"修了上一个 bug 引入新 bug"的真实场景：

✅ 修复 leg A 的 cross-margin 风险 → 改了仓位上限 → leg B 的杠杆假设失效
✅ 修复回测引擎的 fee 计算 → 旧的所有 results.tsv 数字都需要重新解读
✅ 修复 walk-forward 的 train_end 边界 → 之前的 OOS 实际是 IS overlap

量化研究中"组合 bug"的真实场景：

✅ Leg A 单独 Final Gate 通过 + Leg B 单独通过 → 组合后相关性爆了
✅ Universe 扩展 + DD brake 调严 → 单看每条都对，组合后选币变少且回撤增大
✅ Vol-target=0.4 + Calmar reward + 3x leverage → 单维度合理，组合 = 50% MaxDD
```

### 三轮审计协议（必须执行）

**适用场景**：
- 修复了关键策略 bug 后（特别是涉及 leg 协作 / fee 模型 / 回测引擎核心逻辑）
- 产生新冠军且 Final Gate 通过后（不只一次 Final Gate）
- 即将上线实盘前
- 任何"我自己看了一遍觉得没问题"的关键节点

**协议**：

```
Round 1 — 清单式审计（catch 已知失败模式）
  → 维护一份"失败模式清单"（如：look-ahead bias、fee 假设、universe 漂移、
    回测引擎对齐、jitter 范围、状态恢复...）
  → 逐项验证：每条都能给出"通过/不通过"的具体证据
  → 适合：捕获已知陷阱

Round 2 — 修复回归审计（catch 上一轮修复引入的 bug）
  → 输入：Round 1 的修复清单
  → 验证目标：每条修复**真的修了**那个问题
  → 关键追问："这个修复有没有引入新的副作用？"
  → 特别关注："聪明地保留 X 当作 housekeeping" 这种叙事
  → 适合：防止"修一个引入一个"

Round 3 — 开放式审计（catch 组合 bug 和盲点）
  → 不给清单，让审计员用自己的方法论
  → 提示语："如果这套代码运行 90 天无人值守，什么会静默失败？"
  → 关键问题："哪些独立正确的设计组合起来会错？"
  → 适合：捕获组合 bug + 我和审计员都没想到的盲点
```

**Round 3 的提示语模板**（可以直接复制给独立审计员）：

```
我已经做了 N 轮内部审计。这一轮请你**用自己的方法论**审，不给清单。

设想这套策略/代码上线 90 天无人值守，期间会发生：
  - API 暂时返回坏数据
  - 网络抽风
  - 一个 leg 训练出来的模型突然有一行 NaN
  - cron 调度器 reboot 后双跑
  - 时钟 NTP 跳 30 分钟
  - 一个币 delist
  - 一种 regime 我从未见过

什么会静默失败？什么会响铃失败？哪些独立正确的设计组合起来会错？

不要为了"找够 N 个问题"而捏造发现——找不到就直接说"我看了，没找到"。
```

### 审计员选择

```
✅ 好的审计员（按推荐顺序）：
1. 独立的 AI（codex / Claude opus / GPT-5），不参与开发
2. 同事 / 朋友里有量化经验的人，看大方向
3. 你自己，但**至少隔一周**回来重看（避免短期记忆偏差）

❌ 不好的审计员：
1. 当时正在写这个代码的 AI（同 session 自审 = 共享盲点）
2. 你自己，刚写完一气呵成（confirmation bias 最强的时候）
```

### 审计停止规则

```
✅ 可以停的信号：
- 连续 2 轮独立审计没找到 P0/P1 问题
- 第 3 轮明确说 "I looked hard and didn't find anything"
- 失败模式清单全绿 + 开放式审计无新发现

❌ 不能停的信号：
- 这一轮找到的问题里有"前一轮修复引入的"
- 这一轮找到的问题在文档/契约里写错了（说明心智模型还没对齐）
- 找到了 design-level 问题（比 implementation bug 更深，需要重设计）
```

### 不同问题类型的修复优先级

```
🔴🔴 P0 (必修，且新 bug 不能放过)：
  - 数据正确性（look-ahead、survivorship、stale data）
  - 实盘-回测对齐（profile key 不匹配、决策路径不同）
  - 修复引入的回归（Round 2 的核心目标）
  - 组合 bug（Round 3 的核心目标）

🔴 P1 (本期必修)：
  - 验证薄弱（声称的检查实际没做）
  - 错误归类（local 损坏当 transient 处理）
  - 监控盲点（fail 但记录为 success）

🟡 P2 (followup)：
  - 文档残留（旧描述没更新）
  - 性能优化
  - 命名一致性
```


---

## 🔴 修复-引入-回归预防协议（Fix-Induced Regression Prevention）

**修复一个 bug 引入另一个 bug 的概率比想象中高得多。R89.7 Phase 0 三轮
codex 审计中，每一次"修复"都至少引入一个新的需要后续审计的副作用。**

### 三个真实案例

**案例 A：cron_lock 的 unlink-on-release（P0.5 → P0.6）**
```
Round 1 发现：stale-PID + unlink-and-retry 路径会 split-brain
P0.5 修复：移除 stale-takeover 路径

但我"聪明地"保留了 unlink-on-release："文件残留太丑了，release 时清掉"
副作用：waiter 持有的 fd 变成孤儿 inode；release 后 waiter flock 成功
       + 新 acquirer 在新 inode flock 成功 = 同时进入 critical section
Round 2 发现：新 race，FAIL

教训：每修一个 race，都问"这个修复在多进程下展开会怎样？"
```

**案例 B：alert send-failure cooldown（P0.5）+ Markdown 默认（P0.7）**
```
两个独立的设计：
  设计 A (P0.5)：send 失败不推 cooldown → 永远重试
  设计 B (默认)：parse_mode="Markdown" 美化消息

每个独立看都对。组合起来：
  CRITICAL 含 stack trace（含反引号、下划线）→ Markdown parse error
  → send 永远失败 → 永远重试 → 永远 parse error → CRITICAL 永久 silent drop

Round 3 发现：组合 bug，整个 R89.7 "0 人工介入"承诺破产

教训：每加一个 retry 机制，问"如果失败是 deterministic 的，这个 retry 会
     变成什么？"
```

**案例 C：atomic_write_dir oldswap 残留**
```
Round 1 修复：加 oldswap recovery（target 缺失时从 oldswap 恢复）
但 cleanup 只在"target 缺失"分支里做

副作用：crash-after-publish-before-cleanup 留下的 oldswap 不会被清理
       + 时间戳碰撞 → "Directory not empty"

Round 2 发现：另一种 crash 模式没覆盖，FAIL

教训：crash recovery 要列出**所有可能的 crash 点**，不只是修复时想到的那个。
```

### 预防协议

**每次写"修复"时，强制走完三问**：

```
□ Q1: 这个修复在哪些 caller 场景下会展开？
   - 单进程 / 多进程 / 多线程
   - 正常路径 / 异常路径 / SIGKILL
   - 列出至少 3 种调用 timeline

□ Q2: 我保留的"原有合理设计"在新 context 下还合理吗？
   - 例：保留 unlink 是为了"清洁"——但 unlink 的安全前提是
     "我们持有 lock"，新代码改变了 lock 持有时机吗？
   - 例：保留 Markdown 是为了"美观"——但消息内容来源变了吗？
     现在会包含哪些字符？

□ Q3: 这个修复 + 现有 N 个独立设计 = 是否有意外组合？
   - 列出所有"独立看都对"的现有设计
   - 矩阵地问："修复 + 设计 A 会怎样？修复 + 设计 B 会怎样？"
   - 特别关注 retry / cooldown / cache 这类有"重复执行"语义的设计
```

**在量化研究中的对应**：

```
案例 A 的对应（修一个引入一个）：
  □ 修复 leg A 的 cross-margin 风险 → 改了仓位上限
  □ Q1: leg B/C 是否依赖原来的仓位上限做 sizing？
  □ Q2: 仓位上限的"原有合理性"建立在哪些假设上？
  □ Q3: 改后跑 K-fold 重新验证全部 leg，不只 leg A

案例 B 的对应（组合 bug）：
  □ 修复 universe 扩展 + 修复 DD brake → 都通过 Final Gate
  □ Q1: 这两个修复独立 vs 组合的回测结果差多少？
  □ Q2: 每个修复的"独立合理性"假设了对方的什么前提？
  □ Q3: **强制做一次组合回测**，不假设"独立通过 = 组合通过"

案例 C 的对应（覆盖不全）：
  □ 加 crash recovery → 覆盖了 mid-rename 场景
  □ Q1: 列出所有 crash 点（before/after each os call）
  □ Q2: 每个 crash 点对应的 recovery 路径是什么？
  □ Q3: 实际给每个 crash 点写一个 chaos test
```


---

## 量化研究的"四类审计观点"

把 R89.7 学到的多视角审计方法系统化为量化研究中可用的观点矩阵。

每次 Final Gate 之前，从这四个独立观点过一遍：

```
观点 1：清单视角（Catch the Known）
  问题：我列出来的"已知失败模式"是否每条都有验证？
  工具：失败模式清单 + 一对一验证证据
  捕获：look-ahead、survivorship、universe 漂移、fee 假设、对齐...
  适合：第一轮 / 防止低级错

观点 2：回归视角（Catch the Re-introduced）
  问题：上一次修复的 bug 在新代码里有没有变种重新出现？
  工具：旧 audit report + 修复 commit 列表
  捕获：修一个引入另一个、commit 间的语义漂移
  适合：每次重大改动后

观点 3：开放视角（Catch the Combinations）
  问题：如果这套策略 90 天无人值守，什么会静默失败？
  工具：独立审计员（外部 AI / 同事 / 隔周的自己）
  捕获：组合 bug、文档/代码差异、设计层盲点
  适合：上实盘前 / 找冠军后

观点 4：消费者视角（Catch the Contract Drift）
  问题：我的输出会被谁读？他们读的方式是不是和我写的方式一致？
  工具：grep 下游所有 reader + 把它们的期望写成单测
  捕获：schema drift、key naming、量纲不一致、unit-scale 假设错配
  适合：每次新 leg 上线前
```

四个观点是**叠加而非替代**的。R89.7 经验显示：每个独立的观点都会找到
其他观点找不到的 bug。
