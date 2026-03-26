# Research Plan: [TAG]

> 每次新研究开始时复制此模板，填入具体信息。

## 1. 研究目标

**一句话目标**：[如：优化震荡期表现，目标 Box1/Box3 各提升 10%+]

**背景**：[当前策略版本、已知问题、本轮研究的动机]

## 2. 项目定位

| 项目 | 路径 / 命令 |
|------|------------|
| 回测命令 | `python backtest.py --config preset_xxx` |
| 可修改文件 | `strategy.py`, `config.py` |
| 不可修改文件 | `engine.py`, `data/`, `prepare.py` |
| 结果输出 | `results/` 目录下的 JSON/HTML |
| 指标提取 | `grep "sharpe\|cagr\|maxdd" run.log` |

## 3. 评估框架

### 指标权重
```
score = 0.40 * sharpe + 0.25 * cagr + 0.20 * (-maxdd) + 0.15 * regime_consistency
```

### 红线
```
MaxDD > ____%        → discard
任意 regime < baseline * 0.7  → discard
交易次数 < baseline * 0.5     → discard
```

### Regime 定义
```
Box1: [时间范围] — [描述，如"震荡下行期"]
Box2: [时间范围] — [描述，如"趋势上涨期"]
Box3: [时间范围] — [描述，如"高波动震荡期"]
```

## 4. Baseline

| 指标 | 值 |
|------|-----|
| Sharpe | |
| CAGR | |
| MaxDD | |
| Box1 | |
| Box2 | |
| Box3 | |
| 交易次数 | |
| Score | 1.000 (基准) |

## 5. 假设清单（研究开始前头脑风暴）

按优先级排列，研究中会按序尝试。也可随时根据实验结果调整。

1. **[假设名]**：[改动内容] → 预期 [效果]，依据 [理由]
2. **[假设名]**：...
3. **[假设名]**：...

## 6. 实验日志

> 自动填写，不需要手动维护。见 results.tsv。

## 7. 研究总结（研究结束后填写）

### 最终结果 vs Baseline
| | Baseline | 最终 | 变化 |
|---|---|---|---|
| Sharpe | | | |
| CAGR | | | |
| MaxDD | | | |
| Score | 1.000 | | |

### 关键发现
1.
2.
3.

### 失败路径
1.
2.

### 下一轮研究方向
1.
2.
