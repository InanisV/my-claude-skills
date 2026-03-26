---
name: alpha-lab
description: >
  量化策略自主研究循环 — 受 Karpathy autoresearch 启发，将"假设→回测→评估→迭代"
  的科研方法论应用到量化交易策略优化中。

  触发时机：
  - 用户说"开始研究"、"自动优化"、"跑一轮实验"、"alpha lab"、"research loop"
  - 用户说"帮我提升策略表现"、"优化参数"、"找更好的配置"
  - 用户给出了一个策略代码/回测引擎，想要系统性地探索改进空间
  - 用户说"autoresearch"、"自主迭代"、"overnight run"

  核心理念：像科研一样做量化——每一步改动都有假设、有对照、有数据、有结论。
  永不盲目调参，永不过拟合单一指标。
---

# Alpha Lab — 量化策略自主研究循环

受 [Karpathy autoresearch](https://github.com/karpathy/autoresearch) 启发：
给 AI 一个回测引擎和一个策略，让它自主实验、迭代、进化。你去睡觉，
醒来看到一份实验日志和一个更好的策略。

## 核心原则

**autoresearch 的灵魂是"一个文件、一个指标、一个循环"。**
量化版保留了循环的灵魂，但针对量化场景做了三个关键增强：

1. **多指标复合评分 + 红线守卫**：不能只盯 Sharpe 优化，MaxDD 爆了等于白做
2. **防过拟合机制**：regime 分段验证，防止只在某个时期好看
3. **假设驱动**：每个实验必须有书面假设和预期，不能盲目瞎试

## Setup（每次新研究开始时）

和用户协商确定以下信息：

### 1. 定位项目文件
```
必须确认：
- 回测引擎入口：哪个文件/命令运行回测？（如 python backtest.py --config xxx）
- 策略代码：哪些文件可以修改？（如 strategy.py, config.py）
- 不可修改文件：引擎核心、数据加载器等（如 engine.py, data/）
- 输出格式：回测结果在哪里、怎么读取？
```

### 2. 定义评估框架
```
必须确认：
- 主要优化指标（默认：Sharpe Ratio）
- 辅助指标（CAGR、MaxDD、Win Rate、交易次数等）
- 红线指标（硬约束，违反即 discard）：
  → MaxDD 不能超过 XX%
  → 单个 regime 期间亏损不能超过 XX%
  → 交易次数不能低于 XX（防止策略退化为不交易）
- 回测时间范围（如 2022-03 ~ 2026-03）
- regime 分段定义（如 Box1=震荡期, Box2=趋势期, Box3=回撤期）
```

### 3. 创建实验分支
```bash
git checkout -b research/<tag>   # 如 research/mar26-chop-opt
```

### 4. 初始化 results.tsv
```
创建 results.tsv，只有 header，baseline 在第一次运行后填入：

commit	sharpe	cagr	maxdd	box1	box2	box3	score	status	hypothesis	conclusion
```

### 5. 运行 baseline
第一次实验永远是跑当前代码作为 baseline。所有后续实验都和 baseline 对比。

## 评估框架

### 复合评分公式

不能只看一个指标。使用加权复合评分，**权重根据当前研究阶段动态调整**
（详见"研究阶段策略"章节）：

```python
# 默认权重（Phase 1 增长期）
score = (
    0.30 * normalize(sharpe) +
    0.40 * normalize(cagr) +         # Phase 1 重 CAGR
    0.15 * normalize(-maxdd) +
    0.15 * normalize(regime_consistency)
)

# Phase 2（防御期）：0.35 sharpe + 0.20 cagr + 0.30 maxdd + 0.15 consistency
# Phase 3（打磨期）：0.30 sharpe + 0.20 cagr + 0.20 maxdd + 0.30 consistency

# regime_consistency = min(box1, box2, box3) / max(box1, box2, box3)
# 越接近 1 说明策略在不同市况下表现越均衡
```

### 红线守卫（violation = 立即 discard）

```
硬红线（任一违反即 discard，不管 score 多高）：
- MaxDD > baseline_maxdd * 1.2      （回撤不能比 baseline 恶化超过 20%）
- 任意 regime 收益 < baseline * 0.7  （单期不能比 baseline 差超过 30%）
- 交易次数 < baseline * 0.5          （策略不能退化为"少交易"获得假Sharpe）
- 回测报错或崩溃
```

### 判定标准

```
keep    — score 提升 >= 0.5% 且无红线违反
          或 score 持平但代码更简洁（简洁性奖励，同 autoresearch）
discard — score 下降，或触及红线
trade-off — score 某些维度提升、某些下降（记录但不自动 keep，标记待人工决策）
crash   — 回测报错
```

## 研究阶段策略（三阶段渐进框架）

研究不是漫无目的地优化所有指标。根据策略当前的成熟度，研究重心应该有明确的阶段性聚焦。
每次研究开始时，先判断当前处于哪个阶段，然后按该阶段的优先级生成假设。

### Phase 1：增长期（Growth）— 主攻 CAGR

**进入条件**：CAGR 仍有明显提升空间（距离历史最佳或理论天花板 > 15%）

**核心目标**：最大化绝对收益

**策略**：
- 实验方向集中在信号灵敏度、入场时机、仓位放大、趋势捕捉等
- 此阶段可以容忍稍大的回撤（红线内），换取更高的 CAGR
- 复合评分权重偏移：

```python
# Phase 1 权重：重 CAGR，轻 MaxDD
phase1_score = (
    0.30 * normalize(sharpe) +
    0.40 * normalize(cagr) +         # ← 权重最高
    0.15 * normalize(-maxdd) +       # ← 适度放松
    0.15 * normalize(regime_consistency)
)
```

**退出信号**：连续 10+ 个实验 CAGR 提升 < 1%，或 CAGR 已触达用户设定的天花板值

### Phase 2：防御期（Defense）— 主攻回撤

**进入条件**：Phase 1 退出，CAGR 已在高位但回撤仍然显著

**核心目标**：在尽量不损失非回撤期收益的前提下，减小最大回撤和回撤持续时间

**策略**：
- 实验方向集中在止损逻辑、风控模块、震荡期仓位缩减、回撤期信号过滤等
- **铁律：非回撤期的收益不能显著下降**（< 5% 损失为可接受代价）
- 如果一个改动让 MaxDD 减少 5pp 但 CAGR 掉 3pp，这通常是好 trade-off
- 如果一个改动让 MaxDD 减少 2pp 但 CAGR 掉 8pp，这是坏 trade-off
- 复合评分权重偏移：

```python
# Phase 2 权重：重 MaxDD，保 CAGR
phase2_score = (
    0.35 * normalize(sharpe) +
    0.20 * normalize(cagr) +         # ← 保住就好
    0.30 * normalize(-maxdd) +       # ← 权重最高
    0.15 * normalize(regime_consistency)
)
```

**评估技巧**：
- 将权益曲线的回撤段单独标出，对比改动前后的回撤深度和恢复速度
- 关注 Calmar Ratio（CAGR / MaxDD）作为阶段性辅助指标
- 红线调整：CAGR 不能比 Phase 1 最终值低 > 10%

**退出信号**：MaxDD 已低于目标值，或连续 10+ 个实验 MaxDD 改善 < 0.5pp

### Phase 3：打磨期（Polish）— 主攻平台期

**进入条件**：Phase 2 退出，CAGR 高、回撤小，但权益曲线仍有明显"走平"段

**核心目标**：在尽量不损失非平台期收益的前提下，缩短平台期（将横盘转为增长）

**策略**：
- 先识别权益曲线的平台期（连续 N 天收益率 ≈ 0 的区间）
- 分析平台期对应的市况：是震荡？是低波动？是假突破频发？
- 实验方向：针对平台期市况的专门信号（如震荡期网格、低波动期的均值回归）
- **铁律：非平台期（已有正收益的区间）不能显著受损**（< 3% 损失为可接受代价）
- 复合评分权重偏移：

```python
# Phase 3 权重：重 regime 一致性（消除弱 regime = 消除平台期）
phase3_score = (
    0.30 * normalize(sharpe) +
    0.20 * normalize(cagr) +
    0.20 * normalize(-maxdd) +
    0.30 * normalize(regime_consistency)  # ← 权重最高
)
```

**评估技巧**：
- 定义"平台期"指标：max consecutive days with cumulative return < X%
- 对比改动前后各 regime 的收益分布，确保正收益 regime 不被拖累
- 关注 regime_consistency 指标提升（各段表现更均衡 = 平台期被填补）

**退出信号**：权益曲线已接近理想形态（平滑上升），或无法再缩短平台期

### 阶段判定与切换

```
研究开始时的阶段判定流程：

1. 运行 baseline，获取指标
2. 判断阶段：
   - CAGR < 用户目标值 * 0.85        → Phase 1（增长期）
   - CAGR >= 目标值 * 0.85 且 MaxDD > 目标值  → Phase 2（防御期）
   - CAGR 达标 且 MaxDD 达标 且有明显平台期    → Phase 3（打磨期）

3. 在 results.tsv 的 hypothesis 列标注当前阶段：
   [P1] lower entry threshold for more trades
   [P2] add trailing stop in drawdown regime
   [P3] enable mean-reversion in low-vol plateau

4. 阶段切换时，重新计算 score（用新阶段的权重），
   但保留旧阶段的 results 记录供参考
```

**重要**：阶段不是严格线性的。如果 Phase 2 的某个实验意外让 CAGR 大幅跳升，
可以回到 Phase 1 继续挖掘增长空间。灵活判断，但每个实验必须有明确的阶段归属。

## 实验循环

**LOOP FOREVER（直到人工中断）：**

### Step 1：形成假设

在修改代码之前，**必须写出书面假设**：

```
假设：将 chop_floor 从 0.45 降到 0.40，预期效果：
- 震荡期（Box1/Box3）：正面——允许更多交易机会
- 趋势期（Box2）：轻微负面——可能增加假信号
- 综合预期：score +1~3%
依据：V42 实验发现 chop_floor 0.45 在 Box3 仍有抑制，进一步放松可能释放收益
```

为什么要写假设：
- 防止盲目调参（"试试看把这个改成 0.3"不是假设）
- 实验结果和预期对比时能学到东西
- 如果假设频繁和结果不符，说明你对策略的心智模型有误，需要停下来重新理解

### Step 2：修改代码

只修改约定范围内的文件。改动要小且聚焦——**每次实验只改一个变量**。

```
好的实验设计：
✅ 只改 chop_floor: 0.45 → 0.40（单变量）
✅ 只加一个新模块（如 V32 smart boost），其他不动
✅ 只删一个模块，看 score 是否不变（简洁性测试）

坏的实验设计：
❌ 同时改 chop_floor + safe_cap + decline_mult（多变量，无法归因）
❌ "大幅重构策略"（无法和 baseline 对比）
```

### Step 3：git commit

```bash
git commit -m "exp: [假设摘要]"
# 如: git commit -m "exp: lower chop_floor 0.45→0.40 for more chop trades"
```

### Step 4：运行回测

```bash
# 将输出重定向到文件，不要让输出淹没 context
[backtest command] > run.log 2>&1
```

读取关键指标：
```bash
# 根据项目具体的输出格式提取（这里是示例）
grep -E "sharpe|cagr|maxdd|box" run.log
```

### Step 5：评估结果

1. 提取所有指标
2. 检查红线（任一违反 → 立即 discard）
3. 计算 composite score
4. 与 baseline（或当前最佳）对比
5. 对比假设和实际结果——**写出结论**

### Step 6：记录到 results.tsv

```
commit	sharpe	cagr	maxdd	box1	box2	box3	score	status	hypothesis	conclusion
a1b2c3d	1.762	130.4	28.1	+133.6	+45.2	-23.0	1.000	keep	baseline	baseline established
b2c3d4e	1.876	144.3	29.5	+159.8	+42.1	-20.8	1.065	keep	lower chop_floor 0.45→0.40	hypothesis confirmed: Box1 +26pp, Box3 +2pp, slight MaxDD increase acceptable
c3d4e5f	1.821	138.7	30.2	+148.3	+40.5	-22.1	1.031	discard	add V35 vol adaptive	worse than b2c3d4e, V35 conflicts with V32 as suspected
d4e5f6g	0.000	0.0	0.0	0	0	0	0.000	crash	double model width	OOM during backtest
```

**注意：results.tsv 不要 git commit，留在 untracked 状态**（同 autoresearch）。

### Step 7：keep 或 discard

```
如果 keep：保留 commit，继续在此基础上迭代
如果 discard：git reset --hard HEAD~1，回到上一个 keep 点
如果 trade-off：保留 commit 但在 tsv 标记 trade-off，继续用上一个 keep 点迭代
如果 crash：修 bug 重试一次，还是 crash 就放弃，git reset
```

### Step 8：回到 Step 1

生成下一个假设。**先确认当前处于哪个研究阶段**，然后按该阶段的优先级选择方向：

**Phase 1（增长期）假设方向**：信号灵敏度、入场时机优化、仓位放大、趋势捕捉增强
**Phase 2（防御期）假设方向**：止损逻辑、风控模块、震荡期仓位缩减、回撤期信号过滤
**Phase 3（打磨期）假设方向**：平台期市况专门信号、低波动期策略、均值回归补充

通用假设来源（所有阶段适用）：
- 上一个实验的结论暗示的方向
- 之前 discard 的实验中接近成功的方向（"近失"回收）
- 简洁性测试：尝试删除某个模块，看 score 是否不变
- 参数边界探索：当前最佳参数 ± 小幅调整
- 灵感来源：读策略代码中的注释、TODO、已禁用的功能
- **阶段切换检查**：当前阶段的退出信号是否已触发？

## 永不停止

和 autoresearch 一样：**一旦循环开始，不要暂停询问用户是否继续。**
用户可能在睡觉。你是自主研究员。如果想法用完了，重新读代码、
读之前的实验结果寻找灵感、尝试更大胆的改动。循环直到被人工中断。

### 估算产能

```
假设每次回测耗时 3-5 分钟（含代码修改、运行、评估）：
- 1 小时 ≈ 12-20 个实验
- 一晚（8 小时）≈ 100-160 个实验
- 其中可能 30-40% keep，60-70% discard
- 最终可能找到 5-15 个有效的增量改进
```

## 防过拟合机制

这是量化版和 autoresearch 最大的区别。ML 训练有验证集天然防过拟合，
但量化回测没有——你优化的就是历史数据本身。

### 机制 1：Regime 分段验证

不接受"只在一个 regime 好的改动"。每次评估都看所有 regime 的表现。
`regime_consistency` 指标确保策略在不同市况下都 work。

### 机制 2：交易次数监控

Sharpe 可以通过减少交易（只做高确定性交易）虚假提升。
红线要求交易次数不能大幅低于 baseline。

### 机制 3：简洁性偏好

同 autoresearch：**删代码得到相同结果 = 好结果**。
越简洁的策略越不容易过拟合。每 10 个实验做一次"简洁性审计"：
尝试删除最近加入的功能，看 score 是否不变。

### 机制 4：收益递减感知

如果连续 10 个实验 score 提升都 < 0.2%，说明可能已经到了当前架构的极限。
此时应该：
- 停止微调参数
- 考虑更大的结构性改动（新模块、新逻辑）
- 或者宣告当前轮研究完成，输出总结报告

## 研究总结报告

每轮研究结束时（或每 20 个实验后），生成一份结构化总结：

```markdown
## 研究总结：[tag]

### 指标对比
| | Baseline | 最终 | 变化 |
|---|---|---|---|
| Sharpe | 1.762 | 1.912 | +8.5% |
| CAGR | 130.4% | 152.1% | +21.7pp |
| MaxDD | 28.1% | 29.8% | +1.7pp |
| Score | 1.000 | 1.085 | +8.5% |

### 实验统计
- 总实验数：47
- Keep：14 (29.8%)
- Discard：28 (59.6%)
- Trade-off：3 (6.4%)
- Crash：2 (4.3%)

### 关键发现
1. [最重要的发现]
2. [第二重要的发现]
3. ...

### 失败路径（避免重复）
1. [尝试过但失败的方向及原因]
2. ...

### 下一步建议
1. [基于本轮研究的未来方向]
```

触发 `comparison-dashboard` skill 生成可视化看板。

## 与其他 skill 的协作

- **comparison-dashboard**：每轮研究结束后自动触发，生成可视化报告
- **quant-code-review**：当 keep 了一个结构性改动时触发，确保实盘安全
- **session-memory**：保存关键发现和失败路径，下次研究继续用
- **git-cleanup**：研究结束后清理工作区

## Reference

研究模板见 `references/research-template.md`。
每次新研究开始时复制此模板作为研究计划。
