> **alpha-lab · 参考文件** — 由 SKILL.md 按场景按需加载（何时读见 SKILL.md 的 Reference 索引表）。

## 经典失败案例库（案例 1-6，按编号排列）

> 原版案例 1-4 与案例 6 在正文前段、案例 5（R89.7 工程审计层）在后段——
> 两库已合并，编号保持不变。里程碑检查点时翻一遍，确认没踩同样的坑。

这一章记录真实发生的研究方法论失败案例。每一条都是用真金白银换来的教训，
里程碑检查点时应该翻一遍，确认本次研究没有踩同样的坑。

---

### 案例 1：V15 DCA 的 Cross-Sectional 过拟合（2026-04-07）

**一句话教训**：时间维度的 walk-forward 全绿，不代表策略能部署。
横截面维度的 k-fold OOS 是独立的第二道防线，缺了就是裸奔。

**症状**：
- Alpha-lab milestone 报告：冠军 MEGA V2 CAGR 3314%, MaxDD -34.1%, Calmar 97.3
- 机制 1-8 全部通过：walk-forward 健康、decay ratio 良好、参数稳定、regime 一致
- 实盘部署 30 天内：$2981 → $1381（-53.7%）

**事后 forensic 归因**：
- 回测 universe：111 个币（`data/historical/` parquet 快照）
- 实盘 universe：530 个币（Binance USDT-M 动态全集）
- 16 笔已平仓亏损（-$1034.20）**100% 集中在 set(live) - set(bt) 差集**
- overlap 集合（回测见过的币）已实现 PnL = $0
- 差集里既有 2-3 年老币（TRU 3y, ONG 2.3y，数据采集缺口导致缺失）
  也有中青年币（4-19 个月新上线），但它们的共同特征是"**冠军搜索时从未见过**"

**为什么机制 1-8 没抓住这个**：

| 机制 | 检验的维度 | 为什么漏掉 |
|---|---|---|
| 机制 1（walk-forward）| 时间 OOS | 在 111 个币上切时间 fold，**币全程固定** |
| 机制 2（多重检验）| 实验次数 luck | 不涉及币种维度 |
| 机制 3（参数稳定性）| 参数 ±10% 扰动 | **币不变** |
| 机制 4（decay ratio）| 前半段 vs 后半段 | **币不变** |
| 机制 5（regime consistency）| BULL/BEAR/RANGE 分段 | **币不变** |
| 机制 6（交易次数）| 交易频率 | 不涉及币种维度 |
| 机制 7（复杂度税）| 参数数量 | 与币无关 |
| 机制 8（跳出局部最优）| 搜索方向 | 与币无关 |

**所有现有防线都默认"币是固定的"，没有任何一个机制检验"换一批币还 work 吗"**。
这是设计盲区，不是执行失误。

**如果当时有机制 9 会发生什么**：
- 把 111 个币按 listing age 分 5 folds
- 冠军候选在 fold 0-3 训练，fold 4 上测试
- 几乎可以肯定：fold 4（新上线币）上 CAGR 会显著低于 fold 0-3，甚至负数
- worst_fold_cagr 红线会直接 discard 这个 candidate
- 真正的冠军会被迫在"对新币也有效"的参数空间里搜索
- 很可能搜不到 CAGR 3314% 这种夸张数字——**但搜到的那个会真的能上线**

**同场景还踩过的其他坑（避免重复）**：

1. **把"让回测见过所有币"当治本方案**
   - 错误框架："让 bt_universe ⊇ live_universe"
   - 为什么错：实盘在时间轴上永远向前跑，新币每天上线，"完全覆盖"是
     一个会永远逃逸的追赶游戏
   - 正确框架：从"覆盖"转向"泛化"——目标不是"回测见过所有币"，而是
     "冠军参数对样本外的币依然有效"

2. **A/B 验证用研究起点做 baseline 而不是生产冠军**
   - 错误：用 H48_LC20_P50（CAGR 374%，alpha-lab 研究起点）做 baseline
     验证 rank normalization
   - 真相：生产冠军是 MEGA V2（CAGR 1967%），baseline 选错直接让验证结论失效
   - 规则：任何 A/B 的 baseline 必须是 live bot 当前实际加载的 profile，
     不是研究阶段中间版本，也不是历史 milestone 截图

3. **把"修 cool bug"当成修根因**
   - 错误行为：花数小时推进 rank normalization（算法层优雅修复），
     跳过 D1（数据样本扩充，工程问题）
   - 教训：数据和评估方法是**上游问题**，算法（新因子、新仓位、修饱和）是
     **下游问题**。上游没修之前，任何下游 A/B 的结论都不可信——你在错误的
     数据分布 + 错误的评估框架上优化

4. **用 allowlist 把实盘锁回 bt 见过的币集合**
   - 错误：V15_PAPER_SAFE 第一版引入 `universe_allowlist_file`
   - 为什么错：这是 band-aid，违背动态宇宙策略的设计哲学
   - 规则：回测的使命是"验证选币能力"，不是"限制交易范围"

**防线修复清单（已写进 skill）**：
1. 机制 9（跨币 k-fold OOS）
2. Setup Step 2 的 in-sample vs held-out 指标区分
3. 最终上线验证协议 The Final Gate 中加入横截面 OOS 关
4. 核心原则第 7 条（回测 = ML 训练）

**元教训**：alpha-lab 的设计偏向"时间序列 ML"范式（walk-forward、decay），
但动态宇宙策略同时也是"横截面 ML"问题（选币 = 对每个币预测期望收益的排序）。
横截面 ML 的标准工具是 cross-sectional k-fold，alpha-lab 之前漏掉了。
**这次事故不是执行层的 bug，是研究方法论框架本身有一个维度盲区**。

---

### 案例 2：V37 "全局最优"过不了泛化关（2026-04-14）

**一句话教训**：IS 全宇宙上表现惊艳的冠军，如果不经 TRAIN/TEST-fold 验证 +
多 seed 宇宙子集压力测试，部署后可能比 baseline 更差。

**症状**：
- btcmg+adpn+pre 在 168-sym 全宇宙上 IS CAGR 4404%、wDD -41.7%、Calmar 119.4
- 200+ 实验穷尽后宣布"全局最优"
- 三层泛化测试（次日补做）全部失败：
  - TRAIN gain +117% → TEST gain **-8%**（冠军在 held-out 币上不如 baseline）
  - adaptive_n 在 seed=789 子集上 MaxDD -35% → **-65%**（20pp 灾难性退化）
  - 时间衰减：冠军优势 2022 年 +1833%，2024 年 +333%，alpha 持续衰减

**根因**：
- `use_adaptive_n=True` 在信号强时集中到 1-2 个仓位。全宇宙够大时候选币多，
  集中到的通常是好币。子集宇宙小时候选池浅，集中到的可能是同质化的差币 → 崩溃。
- IS 指标一路向好蒙蔽了判断："IS CAGR 提升 31%"看起来很诱人，但 TEST fold 上完全
  没迁移。典型的过拟合到了宇宙组成。

**修正做法（V37 Gen-First Lab）**：
- 每个实验同时跑三层评估：168-sym IS + 5-fold cross-coin TRAIN/TEST + **11-seed 随机子集**
- keep/discard **只看 OOS/TEST 指标**，IS 仅用于诊断
- 子集 seed 从 3 个扩到 11 个（3-seed 低估 worst-DD 达 20pp）
- 最终冠军 `rs14_xp15` 的 IS CAGR 只有 3585%（比 btcmg 低），但 TEST 和子集全面占优

**通用教训**：
1. **IS 全宇宙指标只是参考，不是判据**。冠军判定必须在 held-out 数据上进行
2. **任何依赖"宇宙够大"才成立的特性（如 adaptive_n）在实盘是定时炸弹**——
   实盘宇宙组成随时因上架/退市/流动性变化而改变
3. **子集 seed 数 ≥ 11 是刚性要求**。3-seed 是筛选器，不是终审
4. **宣布全局最优前，必须先过泛化关**。先跑 Final Gate，再定结论

---

### 案例 3：Deselection Override 的发现之路（2026-04-13）

**一句话教训**：当 200+ 参数调优和 20+ 结构创新都无法突破 Pareto 前沿时，
问题可能不在信号层，而在**执行层的隐含假设**。

**症状**：
- V16-V36 共 1100+ 实验、20+ 架构创新（short hedging、adaptive leverage、
  bear trimming、CPPI limiter……），Calmar 天花板卡在 26.76
- 100-sym 宇宙 CAGR 2805% / MaxDD -36.4%（好），168-sym 宇宙 CAGR ~1000%（差 3x）

**根因发现**：
- 不是信号质量问题、不是杀手币问题、不是噪音问题
- 是**执行层隐含假设**：168-sym 宇宙候选币更多 → reselection 时 top-N 频繁变化
  → 旧持仓被强制平仓 → 亏损被锁定（loss crystallization）
- 这个问题在所有"改信号"的创新中不可见，因为信号再好，只要 selection 变了就平仓

**修正**：V37 Deselection Override — 解耦选币和平仓：
- 新开仓仍要求进入 top-N
- 已有仓位**不因 deselection 而平仓**，只按自身退出条件（loss_cap、trailing）退出
- CAGR 从 1000% → **5459%**，MaxDD 持平

**通用教训**：
1. **当所有信号层创新都撞墙时，检查执行层假设**。"选了就进、没选就平"不是唯一设计
2. **Diamond Hands 在 BEAR 市是神圣的**：15+ 实验证明，任何形式的 bear trimming
   （selective close、losscap tighten、position reduce）都会把核心 alpha 杀死，
   因为策略的 alpha 来源正是"扛住 BEAR 后的 V 型反弹"
3. **DCA 层数和 deselection 有交互**：V37 最佳配置 DCA=1（不加层），因为
   无 deselection 平仓 + 无 DCA 加仓 = 每个仓位干净进干净出

---

### 案例 4：Cross-Margin 清算级联 ≠ 杀手币（2026-04-13）

**一句话教训**：在 cross-margin 合约策略中，168-sym 宇宙的 MaxDD 爆表
不是因为多了"坏币"，而是因为仓位总 notional 超过了保证金的安全边界。
添加 per-position hard stop 无法防御这种系统级风险。

**症状**：
- 冠军参数在 100-sym 上 MaxDD -36.4%，换到 168-sym 就变 -108.6%（被清算）
- 直觉归因："168-sym 多了 69 个垃圾币拖累了"

**真相**：
- 那 69 个"额外币"全是成熟老币（>2.7 年，>983 天数据），seasoning gate 根本不会过滤
- 清算发生在 bar 743（2022-01-31），机制是：更多币 → 更多持仓 → 总 notional 更大
  → 累积未实现亏损 → 维持保证金率突破阈值 → **全账户一次性强平**
- per-position hard stop 没用：清算是 account-level 事件，在个股 stop 触发之前就被
  交易所一次性平掉了所有仓位
- exposure_pct 从 2.0→2.5 有 MaxDD cliff（-36.9% → -75.9%），一个参数 +0.5 就跨了悬崖

**通用教训**：
1. **Cross-margin 策略的 MaxDD 不是线性可控的**，存在清算悬崖
2. **"多加币 = 多风险"的归因要验证**：是那些币本身亏钱了，还是总仓位变大导致系统级崩溃？
3. **永远不要相信"per-position stop 能兜底"**——cross-margin 清算是 portfolio-level 事件
4. **Exposure cliff 要主动探测**：在 baseline 的 exposure 值上下 ±0.5 做 grid scan，
   找到悬崖在哪里，然后退一步

---


### 案例 5：R89.7 Phase 1 FAIL — 5 个 P0 + 设计层 bug（2026-05-01，工程审计层）

**背景**：Phase 0（lock / atomic write / alerts 等基础设施）经过 3 轮 codex
审计达到 PASS。Phase 1 是第一次真正使用这些基础设施的应用层 —— 4 个数据
刷新 cron 脚本（klines / coinmetrics / v30_features / ml_predictions）。

**结果**：codex 一次审计直接 FAIL，5 P0 + 3 P1 + 2 P2 + 一个设计层问题。

**5 个 P0 详细**：

```
P0-1: cron_runner 契约错配
  错：用 return rc 模式
  实：cron_runner 只看 exception，return code 完全被忽略
  后果：失败的 cron 写 last_success；dry-run 也写 last_success；
       手动 metadata 被覆盖
  根因：用 helper 前没读 helper body

P0-2: klines 接受未关闭的小时 bar
  错：until_ms = time.time()*1000（包含正在 forming 的 bar）
  实：next cursor = max(open_time)+1，partial 永久污染
  根因：没仔细想 Binance 时间窗语义

P0-3: CoinMetrics 接受当天行
  错：end_date = today
  实：当天 daily metric 还在更新，next cursor 跳过它
  根因：同 P0-2，没想清楚 closed-period 语义

P0-4: v30 wrapper 删 canonical 文件再跑 builder
  错：unlink(V30_OUT) → subprocess(builder) → 失败 = 永久丢失
  实：window 内 readers 看到 missing；builder crash 灾难
  根因：subprocess 包装研究脚本（反模式 1）

P0-5: ml_predictions 解析不了真实的 v30_features.json
  错：feature_list = meta.get("features", ...)
  实：实际 key 是 feature_cols（live/signals/v30_inference.py:108）
  根因：没 grep 消费者契约（反模式 2）
```

**设计层 bug**：即使 5 P0 修了，v30 features 也**不会 advance**——研究
builder 依赖静态 ml_features_v1.parquet，Phase 1 不刷新它。本地复现：
raw klines 在 2026-04-28，v1 + v30 卡在 2026-04-26。这是"包装研究脚本"
的更深层后果：研究脚本的输入假设和生产场景完全不匹配。

**"--help 全过 ≠ work"**：4 个脚本提交前我跑了 `python3 -m pytest` (99/99
green) + 4 个 `--help` (全 OK)。第一次真跑 `auto_refresh_ml_predictions`
就因为 P0-5 直接 DataCorruptionError。

**核心教训**：
- 研究代码 wrap 成生产 = code smell（反模式 1）
- 凭记忆写消费者契约 = 反模式 2
- syntax + help 当 smoke = 反模式 3
- 5 P0 中的 P0-1 是**"用 helper 前没读 helper body"**，与之前案例 1 (V15 DCA
  cross-sectional 过拟合)、案例 4 (cross-margin 清算级联) 一样属于"心智模型
  和实现差异"导致

**修复结构**：
```
Batch A：6 个表层修复（feature_cols / closed-period × 2 / 本地损坏 /
        threshold / Makefile）— 250 LoC
Batch B：cron_run() API + CronResult dataclass + 4 脚本重构 +
        ~30 测试 — 400 LoC
Batch C：真正的 production v30 builder（不 wrap 研究脚本）+
        data-timestamp freshness gate — 600 LoC
```

**给未来量化研究的对应教训**：

```
1. 研究代码不要 subprocess 当生产用
   → 类比：r28_ppo_rl.py 研究 trainer 不要直接被 weekly_retrain 调用
   → 应该：抽出 train_ppo() 核心函数，研究和生产都调用它

2. 写新 leg 前先看下游怎么读现有 leg
   → 类比：写新 inference 前，看现有 inference 的 schema
   → grep 比记忆可靠

3. unit test 全过 ≠ 端到端 work
   → 必须真实数据跑一次（dry-run 模式 + 至少 1 个真实 symbol）
   → "我相信它会工作" 经常错

4. 多个独立合理的设计组合可能错
   → 5 个 P0 + 1 个设计 bug 中，至少 2 个是"独立合理但组合错"
   → 修一个引入另一个的 reorder（P0.5 → P0.6 已经经历过）

5. FAIL 不是耻辱，是 audit 在工作
   → 接受 FAIL → 写修复计划 → 下个 session 干净开始
   → 比"这个能 hot fix 我就先上线" 强得多
```

---

### 案例 6：v14 战役 — 样本内三轴全优的候选死于 OOS 锁箱（2026-07）


**一句话教训**：训练窗上"CAGR、Sharpe、MaxDD 同时改善 + 去集中化 + 参数平坦"
的候选，仍然可以是期特定的假突破——只有消耗一次稀缺的 OOS 开封才能审出来。

**症状**：composite 的 p0.5 幂压缩（sign(z)·|z|^0.5）在 TRAIN（2023-11→2025-12）
上 308.9%/2.25/-33.5，对照基线 286.7%/2.21/-36.8 三轴全优；p∈{0.4,0.5,0.6} 扰动
平坦；触顶天数占比从 76.5% 降到 59.3%（真实去集中化）；11-seed 子集零破产。
按任何训练侧标准这是完美候选。

**OOS 开封（第 2/3 轮预算）**：OOS 2026H1 = 7.9%/Sharpe 0.40，
而不加压缩的在位冠军 OOS = 31.4%/0.86。压缩把尾部跟随换成均值稳定，
恰好匹配 2024-25 的行情结构、恰好不匹配 2026 的震荡。

**同战役的对照面**：tvv 因子通过了同一道门（OOS Sharpe 0.48→0.86 真实增益）——
锁箱不是一律否决，它区分了真因子与期特定变换。

**元教训**：
1. 训练侧证据的完备性（三轴+扰动+子集）不能替代时间 OOS——它们防的是
   不同的过拟合维度；
2. OOS 开封必须预算化，否则"再试一个变体"的循环会把 OOS 变成训练集；
3. 每次开封同时跑一个归因对照（裸基线同杠杆），把"候选 vs 基线"的 OOS 差
   与"整个策略族的期依赖"分离开。
