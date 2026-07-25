> **alpha-lab · 参考文件** — 由 SKILL.md 按场景按需加载（何时读见 SKILL.md 的 Reference 索引表）。

# 防过拟合与 Decay 防御体系（机制 1-10）+ 泛化优先评估框架

## 防过拟合与 Decay 防御体系

这是量化版和 autoresearch 最大的区别。ML 训练有验证集天然防过拟合，
但量化回测没有——你优化的就是历史数据本身。更危险的是：做了 100 个实验后，
即使策略没有真正的 alpha，纯靠随机也能找到几个"看起来不错"的结果（多重检验问题）。

**本节的目标：确保科研找到的"全局最优"是真正经得起实盘检验的好策略，
而不是一个精心拟合历史数据的幻觉。**

---

### 机制 1：Walk-Forward 滚动验证（核心防线）

**这是对抗过拟合最强力的武器。**

```
原理：
  不要在全量数据上评估策略。将回测数据切分为"训练窗口"和"验证窗口"，
  滚动推进，模拟"用过去的数据做决策，在未来的数据上检验"。

实施方式：
  假设回测数据：2022-03 ~ 2026-03（4 年）

  方式一：固定 OOS（Out-of-Sample）保留区
  ┌──────────────────────────────┬──────────┐
  │  训练集 2022-03 ~ 2025-06   │  OOS     │
  │  （日常实验都在这个范围跑）   │2025-06~  │
  │                              │2026-03   │
  └──────────────────────────────┴──────────┘
  → 最后 9 个月的数据完全不碰，只在最终验证时使用一次
  → 日常实验的 score 只基于训练集计算
  → OOS 是"信封里的答案"——打开一次就失去效力
  → 多轮开封按铁律 1 预算制管理：默认 ≤3 轮 + append-only 审计留痕，
    最后一轮留给部署决策（见 references/campaign-laws.md 铁律 1）

  方式二：滚动 Walk-Forward（更严格）
  Window 1: 训练 2022-03~2023-09 → 验证 2023-09~2024-03
  Window 2: 训练 2022-03~2024-03 → 验证 2024-03~2024-09
  Window 3: 训练 2022-03~2024-09 → 验证 2024-09~2025-03
  Window 4: 训练 2022-03~2025-03 → 验证 2025-03~2025-09
  → 策略必须在每个验证窗口都盈利
  → Walk-Forward Efficiency = mean(OOS_return) / mean(IS_return)
  → WFE > 0.5 说明策略有真正的预测力；WFE < 0.3 = 严重过拟合嫌疑

启动时决定：
  在 Setup Step 0 中询问用户选择哪种方式（推荐方式一，简单有效）。
  如果回测数据 < 3 年，只能用方式一（保留最后 20% 做 OOS）。
```

### 机制 2：多重检验修正（实验次数越多越要怀疑）

```
问题：
  做了 100 个实验，最好的那个 score 提升了 8%。这是真 alpha 还是随机运气？
  如果扔 100 次硬币，最长连续正面可以轻松到 6-7 次。同理，100 个实验中
  出现一个"看起来很好"的结果，可能纯粹是运气。

应对方法：

  1. 跟踪"好运指标"（Luck Ratio）：
     luck_ratio = best_score_improvement / median_score_improvement
     → 如果 best 比 median 好 5 倍以上，要高度怀疑这是统计噪声
     → 真正的好改动应该在中位数以上但不会离谱地高

  2. 重复验证：
     对每个 keep 的实验，换一组稍微不同的参数（±5%）重跑一次。
     如果换参数后 score 显著下降 → 这是参数敏感型过拟合，不是真 alpha

  3. 心理锚点：
     每 20 个实验后问自己：
     "如果从零开始，只用当前的理解和策略架构，不做任何参数调优，
      score 会是多少？"
     → 这个"朴素 score"和优化后 score 的差距 = 过拟合的上限估计
```

### 机制 3：参数稳定性检验（Parameter Sensitivity）

```
核心原则：好策略应该是"参数不敏感"的——稍微变动参数不应导致表现崩塌。

检查方法（每个里程碑版本必做）：

  1. 识别所有关键参数（阈值、窗口长度、仓位系数等）
  2. 对每个参数做 ±10%、±20% 的扰动
  3. 重跑回测，记录 score 变化

  判定标准：
  ✅ 稳健：所有参数 ±20% 后 score 波动 < 15% → 真正的好策略
  🟡 可接受：大部分参数 ±20% 后 score 波动 < 25% → 轻微过拟合风险
  🔴 脆弱：存在参数 ±10% 后 score 暴跌 > 30% → 严重过拟合

  如果发现脆弱参数：
  → 该参数的当前值可能恰好"踩中"了历史数据的某个噪声特征
  → 应主动将参数移到"稳健区间"的中心（即使 score 略低）
  → 一个稍低 score 但参数稳健的策略 >> 高 score 但参数脆弱的策略

  简化版（快速执行）：
  → 不需要逐个参数扫描，可以直接做"联合扰动"：
     所有参数同时随机 ±10%，跑 5 次，看 score 分布的标准差
  → std(score) / mean(score) < 0.1 → 稳健
  → std(score) / mean(score) > 0.25 → 脆弱
```

### 机制 4：Performance Decay 检测（因子/信号衰减）

```
核心问题：策略在回测前半段表现好、后半段变差，是最常见的过拟合症状。
它也是实盘可能遇到的最大风险——你上线的那一刻，可能就是策略"后半段"的开始。

检测方法：

  1. 时间分段对比：
     将回测期等分为 2-4 段，分别计算每段的关键指标：

     Half 1 (2022-03 ~ 2024-03):  CAGR=180%  Sharpe=2.1  MaxDD=15%
     Half 2 (2024-03 ~ 2026-03):  CAGR=120%  Sharpe=1.4  MaxDD=22%
     → Decay Ratio = Half2_CAGR / Half1_CAGR = 0.67 → 🟡 有衰减趋势

     判定：
     Decay Ratio > 0.85 → ✅ 稳定，衰减可忽略
     Decay Ratio 0.6~0.85 → 🟡 有衰减，需关注但可接受
     Decay Ratio < 0.6 → 🔴 严重衰减，策略可能已经过时或过拟合

  2. 滚动窗口 Sharpe 趋势：
     用 6 个月滚动窗口计算 rolling_sharpe，画趋势图。
     → 如果 rolling_sharpe 呈下降趋势 → 信号在衰减
     → 如果 rolling_sharpe 围绕均值波动 → 正常的周期性
     → 对 rolling_sharpe 做线性回归，斜率 < 0 = 衰减信号

  3. 最近期表现权重：
     在最终评估中，给最近 1 年的表现更高的权重：
     adjusted_score = 0.3 * score_early + 0.7 * score_recent
     → 近期表现差的策略即使总分高，也不适合上实盘

  4. 因子贡献度变化：
     如果策略有多个信号/因子，检查各因子的贡献度是否随时间变化。
     → 某个因子在前两年贡献了 60% 的 alpha，后两年只有 10% → 该因子在衰减
     → 这比整体 CAGR 衰减更有诊断价值——你知道具体是哪个信号在失效
```

### 机制 5：Regime 分段验证

不接受"只在一个 regime 好的改动"。每次评估都看所有 regime 的表现。
`regime_consistency` 指标确保策略在不同市况下都 work。

### 机制 6：交易次数监控

Sharpe 可以通过减少交易（只做高确定性交易）虚假提升。
红线要求交易次数不能大幅低于 baseline。

### 机制 7：简洁性偏好与复杂度税

同 autoresearch：**删代码得到相同结果 = 好结果**。
越简洁的策略越不容易过拟合。每 10 个实验做一次"简洁性审计"：
尝试删除最近加入的功能，看 score 是否不变。

**复杂度税（Complexity Tax）**：

```
每个策略增加的"可调参数"都在消耗自由度。用复杂度税抑制过拟合：

complexity_penalty = 0.005 * num_new_params
adjusted_score = raw_score - complexity_penalty

例：baseline 有 8 个参数。添加一个新模块引入 3 个参数：
→ 额外扣 0.015 → 新模块需要带来 > 1.5% 的 score 提升才能覆盖复杂度税

为什么这有效：
过拟合的本质是"用更多参数去拟合有限的历史数据"。
复杂度税让"加参数"的门槛更高，迫使改进来自真正的结构性洞察。
```

### 机制 8：跳出局部最优（全局搜索意识）

**核心理念：局部最优 ≠ 全局最优。不要一条路走到黑。**

🧠 局部最优让人"束手无策"——但那几乎总是**认知高度不够**，不是真的没有更优解。
跳出的本质是**自我认知升级**：先按【🔴 认知升级阶梯】爬一级（尤其第 1 级"向外求"——
联网搜 arXiv/GitHub/非金融 AI 前沿），换一副认知眼镜，局部最优的墙往往就消失了。

当出现以下信号时，说明你可能陷入了局部最优：
```
触发信号（任一即触发）：
- 连续 8+ 个实验 score 提升 < 0.3%（在同一方向上微调）
- 当前阶段的所有"显而易见"的假设都试过了
- 最近 5 个实验全部 discard
- 假设和结果频繁不符（心智模型可能有误）
```

**跳出策略（按激进程度递增尝试）：**

```
Level 1 — 换方向（低风险）：
  停止当前方向的微调，切换到完全不同的优化维度。
  例：一直在调信号参数 → 转去优化仓位管理逻辑

Level 2 — 回退重来（中风险）：
  git reset 回到上一个里程碑版本（不是上一个 keep，而是更早的稳定点），
  从那个点出发走一条完全不同的路。
  例：回退到 baseline，尝试一个全新的模块组合

Level 3 — 结构性重构（高风险）：
  挑战当前策略的基本假设。尝试：
  - 删除被认为"必要"的核心模块，看 score 会怎样
  - 替换整个信号生成逻辑（如从趋势跟踪改为均值回归）
  - 合并/拆分现有模块
  注意：结构性重构前必须 commit + tag 当前最佳版本作为安全回退点

Level 4 — 反向实验（探索性）：
  故意做一个"应该会变差"的改动，观察实际结果。
  如果结果出乎意料地好，说明之前的心智模型有盲区，
  这个发现比 score 本身更有价值。
```

**跳出后的记录**：在 results.tsv 的 hypothesis 列标注 `[ESCAPE-L1/2/3/4]`，
方便回顾哪些跳出尝试成功了。

**关键心态**：宁可花 5 个实验探索一条全新的路（即使最终 discard），
也不要花 15 个实验在一个已经榨干的方向上挤出 0.1% 的提升。
目标是全局最优，不是当前方向的局部最优。

### 机制 9：Cross-Sectional Coin-Fold OOS Validation（跨币外样本验证）🔴 动态宇宙策略必须

**这是时间维度 walk-forward（机制 1）正交的第二道防线。**

```
核心洞察：

  时间维度的过拟合（机制 1 防御）：
    → 策略在历史某段时间上过拟合，新时间段上崩盘
    → 防线：训练 2022-2025，测试 2025-2026

  横截面维度的过拟合（机制 9 防御）：
    → 策略在历史某批币上过拟合，新币种上崩盘
    → 防线：训练在 coin fold A-D，测试 coin fold E

这两种过拟合是独立的。一个策略可以同时：
  (a) 通过 walk-forward（时间 OOS 全绿）
  (b) 崩在 cross-sectional OOS（换一批币就废）

真实案例（V15 DCA, 2026-04-07，详见下方失败路径案例库）：
  在 111 个币 × 4 年数据上做完整的 walk-forward 验证并通过所有时间维度
  的检验，冠军 CAGR 3314%、MaxDD -34.1%、Calmar 97.3。实盘部署在 530
  个币的动态宇宙上，30 天内 -53.7%。事后分析：100% 的已实现亏损集中
  在 set(live) - set(backtest_coins) 差集内，overlap 集合 PnL = $0。
  冠军参数对"从未在训练中见过的币"是完全未定义行为。

  这不是走漏了一个细节——这是 alpha-lab 的一整个维度缺失了。
  机制 1-8 全部是时间维度的防御，没有任何一个检验"换一批币还 work 吗"。
```

**触发条件**：以下任一条满足，必须启用跨币 k-fold：
- 策略是动态宇宙（top-N / rank-based，实盘会自动选币）
- 回测 universe > 50 个币（< 50 统计 power 不够，需要先扩样本）
- 实盘宇宙 ≥ 回测宇宙的 1.5 倍
- 策略参数数量 ≥ 5（即有过拟合风险）

**实施协议**：

```
Step 1 — Fold 划分（在 Setup Step 2 评估框架里就决定，不是事后补）：

  策略 A：随机 k-fold（k=5 推荐）
    universe = load_all_symbols()  # e.g. 530 coins
    np.random.seed(42)  # 锁定种子，结果可复现
    folds = np.array_split(np.random.permutation(universe), 5)

  策略 B：Stratified k-fold（更好，推荐用这个）
    按以下维度分层，保证每 fold 的币分布一致：
    - Listing age bucket（< 180d / 180-720d / > 720d）
    - Volatility tier（low/mid/high，用历史 ATR 分档）
    - Market cap tier（如能拿到）
    → 每 fold 内部是上述 buckets 的按比例采样

  策略 C：Time-stratified（最严格，动态宇宙必备）
    按币的"上线时间"分 fold。例：
      fold_0 = 2020 之前上线的币（"老古董"）
      fold_1 = 2020-2022 上线的币
      fold_2 = 2022-2023 上线的币
      fold_3 = 2023-2024 上线的币
      fold_4 = 2024 之后上线的币（"新上线"）

    然后做 leave-one-future-out：
      用 fold 0-3 训练/搜冠军，在 fold 4 上测试
    → 这最贴近实盘的真实场景（新币在未来持续到来）

Step 2 — 冠军搜索必须在 fold 分离下进行：

  for candidate_params in search_space:
      cv_scores = []
      for held_out_idx in range(5):
          train_universe = union(folds[i] for i in range(5) if i != held_out_idx)
          test_universe  = folds[held_out_idx]

          # 搜索阶段只能看 train_universe
          train_result = run_backtest(params=candidate_params,
                                      universe=train_universe)

          # 评估阶段只看 test_universe（held-out 币）
          test_result = run_backtest(params=candidate_params,
                                     universe=test_universe)

          cv_scores.append({
              'train_cagr': train_result.cagr,
              'test_cagr':  test_result.cagr,  # ← 这是真正关心的
              'test_maxdd': test_result.maxdd,
              'test_calmar': test_result.calmar,
          })

      # 冠军判定指标
      worst_fold_cagr = min(s['test_cagr'] for s in cv_scores)
      median_test_cagr = median(s['test_cagr'] for s in cv_scores)
      worst_fold_maxdd = max(s['test_maxdd'] for s in cv_scores)
      generalization_ratio = median_test_cagr / mean(s['train_cagr'] for s in cv_scores)

Step 3 — 红线（必须加进"红线守卫"章节）：

  🔴 worst_fold_cagr < 0         → discard, 过拟合到特定 fold
  🔴 worst_fold_maxdd > baseline_maxdd × 1.5
                                  → discard, 在某批币上崩盘
  🔴 generalization_ratio < 0.3  → discard, train 和 test 差距太大
  🟡 generalization_ratio < 0.5  → 标记但不立即 discard，
                                    要求深挖为什么 train/test 差距大
  ✅ generalization_ratio > 0.7  → 健康，champion 具备泛化能力

Step 4 — 冠军报告必须呈现 fold-level 数据，不是只有总体：

  报告格式（示例）：

  候选：MEGA_V2_candidate_X
  ┌────────────┬──────────┬──────────┬──────────┬──────────┐
  │ Fold       │ Train    │ Test     │ Test     │ Test     │
  │            │ CAGR     │ CAGR     │ MaxDD    │ Calmar   │
  ├────────────┼──────────┼──────────┼──────────┼──────────┤
  │ 0 (<2020)  │  2800%   │  2100%   │  -42%    │  50.0    │
  │ 1 (20-22)  │  3100%   │  1950%   │  -38%    │  51.3    │
  │ 2 (22-23)  │  2950%   │   180%   │  -71%    │   2.5 🔴 │
  │ 3 (23-24)  │  3200%   │   450%   │  -58%    │   7.8 🔴 │
  │ 4 (>2024)  │  3050%   │  -120%   │  -89%    │  neg  🔴 │
  ├────────────┼──────────┼──────────┼──────────┼──────────┤
  │ Aggregate  │  3020%   │   912%   │  -60%    │  15.2    │
  │ Worst      │          │  -120%   │  -89%    │          │
  └────────────┴──────────┴──────────┴──────────┴──────────┘

  🔴 判定：reject —— fold 2/3/4（新上线币）上完全不 work。
     "Aggregate CAGR 912%" 是在老币上的过拟合收益平均出来的，
     掩盖了新币上的灾难。

  这个表格**必须**生成。"Aggregate CAGR 3020% ✅" 这种汇总结论
  在动态宇宙策略里是不够的，是欺骗性的。
```

**与机制 1（Walk-Forward）的关系**：

```
机制 1 和机制 9 是**正交的两个维度**，必须同时做：

           时间 OOS (机制 1)
                 │
       不通过    │    通过
    ┌───────────┼───────────┐
不  │   双重     │  时间过拟合 │
通  │  过拟合    │ (能泛化到   │
过  │            │ 新币但不能  │
    │            │ 泛化到未来) │
横  │            │            │
截  ├───────────┼───────────┤
面  │ 币种过拟合 │  真正的     │
OOS │ (能泛化到  │  robust    │
    │ 未来但不能 │  alpha     │
(机 │ 泛化到新币)│  ✅ 上线    │
制  │            │            │
9)  │  V15 DCA   │            │
    │ ← 就是这里 │            │
    └───────────┴───────────┘
       通过

V15 DCA 过了机制 1（时间维度没崩），但没过机制 9（换一批币就崩）。
两个防线缺一不可。
```

**实战简化（如果时间紧/算力紧）**：

```
完整 k-fold 很贵。可以分阶段实施：

  Sprint 1（立即可做，低成本）：
    在现有冠军搜索之外，加一个一次性的 hold-out 验证：
    从 universe 里随机 sample 20% 的币作为 permanent holdout，
    绝对不用于任何参数搜索。每次冠军 milestone 都在这 20% 上测试一次。
    如果 milestone CAGR 在 holdout 上掉 > 50% → 过拟合警报。

  Sprint 2（重构冠军搜索）：
    真正的 k-fold 嵌入 champion search pipeline：
    让每组候选参数自动算 fold-level metrics，
    红线判定用 worst_fold 而不是 aggregate。

  Sprint 3（终极防线）：
    Stratified by listing age 的 time-future hold-out（Step 1 的策略 C）
    这最贴近实盘的"新币持续到来"真实场景。

能先做 Sprint 1 就比什么都没有强一个数量级。
```

### 机制 10：最终上线验证协议（The Final Gate）

**在宣布"找到全局最优"之前，必须通过这套最终验证。这是从科研到实盘的闸门。**

```
验证清单（全部通过才能宣布全局最优）：

□ 时间 OOS 验证（机制 1，如果采用了方式一固定保留区）：
  → 用保留的最后 N 个月数据跑一次回测
  → OOS_score / IS_score > 0.6 → ✅ 通过
  → OOS_score / IS_score < 0.4 → 🔴 过拟合确认，不能上线
  → 注意：OOS 开封消耗铁律 1 的预算（≤3 轮 + 审计留痕）；单纯"用完就
    不再是 OOS"是第一性原理，预算制是它的制度化

□ 🔴 横截面 OOS 验证（机制 9，动态宇宙策略必查）：
  → 在 held-out 币 fold 上（或 20% permanent holdout）跑最终冠军
  → worst_fold_cagr ≥ 0 且 generalization_ratio > 0.5 → ✅ 通过
  → worst_fold_cagr < 0 或 generalization_ratio < 0.3 → 🔴 币种过拟合，不能上线
  → 注意：这是和时间 OOS 正交的另一条防线，两个都必须通过
  → V15 DCA 事故就是在这一关缺位的情况下上线的

□ 参数稳定性检验：
  → 所有参数 ±20% 联合扰动，跑 5 次
  → score 标准差 / 均值 < 0.15 → ✅ 通过

□ Decay 检测：
  → 后半段 vs 前半段 Decay Ratio > 0.7 → ✅ 通过
  → Rolling Sharpe 线性回归斜率 ≥ 0 → ✅ 没有衰减

□ 多重检验意识：
  → 如果总共做了 N 个实验，最终 score 提升了 X%，
    是否有理由相信这不是 N 次试验中的随机最优？
  → "朴素 score"检验：只用当前架构+合理的默认参数（不调优），
    score 是否仍显著优于 baseline？

□ 简洁性确认：
  → 对最终版本再做一次简洁性审计
  → 删除任何一个模块都导致 score 下降 → ✅ 每个模块都有贡献

□ 成本与容量三查（上线前必过）：
  → cost-stress：费率上浮 50%（如 9→13.5bps）后策略仍存活（Sharpe 不塌方，
    de-lever 不可能抬 Sharpe）
  → 若做过降换手尝试：换手三项分解（成员变动/权重漂移/杠杆再平衡）已完成，
    确认高换手是不是 alpha 本体（铁律 15——是的话省成本 = 杀 alpha）
  → 容量估算：目标资金规模下 top-N 中小币的单笔冲击与 ADV 占比可接受
    （空头簿流动性下限经验：ADV 门槛，见 v14 战役 W2）

验证结果在研究总结报告中列出，作为"可上线信心评级"：
  ⭐⭐⭐ 全部通过 → 高信心，推荐上线
  ⭐⭐  仅 1 项未通过（且不是时间 OOS / 横截面 OOS 这两道硬关）
       → 中等信心，可上线但需密切监控
  ⭐    其余情况 → 低信心，建议继续优化或重新审视策略架构
```

---

## 🔴 泛化优先评估框架（Generalization-First Evaluation）

**这是从 V37 研究（2000+ 实验）中提炼出的完整评估协议。任何冠军候选的判定
都必须走完这三层，缺一层都不算验证过。**

### 三层泛化测试

```
┌─────────────────────────────────────────────────────────┐
│ Layer 1：IS 全宇宙回测                                    │
│ 目的：快速筛选，淘汰明显差的                               │
│ 方法：在完整回测宇宙上跑一次                               │
│ 判定：通过 IS 红线 → 进入 Layer 2                         │
│ 注意：IS 指标是参考，不是判据！                            │
└────────────────────────────────────┬────────────────────┘
                                     ↓
┌─────────────────────────────────────────────────────────┐
│ Layer 2：Cross-Coin K-Fold（TRAIN / TEST）              │
│ 目的：检验冠军参数是否对未见过的币有效                     │
│ 方法：                                                   │
│  1. 按 listing age stratified 分 k=5 folds              │
│  2. 在 fold 0-3 上训练（跑回测），fold 4 上测试           │
│  3. 轮换 5 次，每个 fold 都做一次 test                   │
│ 判定指标：                                               │
│  - worst_fold_cagr ≥ 0（不能有 fold 亏钱）               │
│  - TEST median CAGR > baseline TEST median               │
│  - TEST worst MaxDD < baseline worst MaxDD（或可接受范围）│
│ 🔴 gen_ratio 判读注意：                                  │
│  如果 TRAIN CAGR 极高（>5000%）但 gen_ratio < 0.3，       │
│  不要自动 discard！检查 TEST folds 的绝对值：             │
│  - 每个 TEST fold CAGR > 0 → gen_ratio 红线是假阳性     │
│  - 任一 TEST fold CAGR < 0 → gen_ratio 红线是真的        │
│  原则：绝对安全（每个 fold 都盈利）> 比例安全（ratio 高）  │
└────────────────────────────────────┬────────────────────┘
                                     ↓
┌─────────────────────────────────────────────────────────┐
│ Layer 3：多 Seed 宇宙子集压力测试                         │
│ 目的：检验冠军参数在宇宙随机子集上是否稳定                 │
│ 方法：                                                   │
│  1. 使用 ≥ 11 个随机 seed，每次随机抽取 ~60% 的宇宙       │
│  2. 在每个子集上跑完整回测                                │
│  3. 统计子集 CAGR 分布和 worst-case MaxDD                │
│ 判定指标：                                               │
│  - subset_worst_maxdd < 目标 MaxDD × 1.3                 │
│  - subset_mean_cagr > baseline_is_cagr × 0.5             │
│  - 没有任何一个 seed 出现清算或极端负收益                  │
│ 🔴 seed 数量铁律：                                       │
│  ❌ 3 个 seed 不够（实测低估 worst-DD 达 20pp）           │
│  ✅ 至少 11 个 seed                                      │
│  ✅ 如果 worst-DD 方差大，加到 21 个                      │
└─────────────────────────────────────────────────────────┘
```

### 评估结果记录格式

每个实验的 results.tsv 应扩展为：

```
commit | is_cagr | is_maxdd | test_median_cagr | test_worst_cagr | test_worst_maxdd | gen_ratio | sub11_mean_cagr | sub11_worst_maxdd | status | hypothesis
```

keep/discard **只看** test_* 和 sub11_* 列。is_* 列仅供诊断。
