# 腿挖掘 harness + 穷尽 workflow（手工搜索穷尽时的规模化）

当手工设计穷尽（"试不动了"），别停——**规模化并行搜索**：一个共享 harness 让每个挖掘 agent 只写信号，加一个穷尽 workflow 并行跑几十种**根本不同的结构**，每条都带泄漏+OOS+family-null 防护。

## 1. 共享 harness（legkit 模式）

关键：让挖掘 agent **零 harness 出错空间**——只写信号构造，harness 负责 gate/费用/因果/评估。

```python
# legkit.py 暴露（全部 [idx×coins]，因果安全）：
#   close, ret, um(gated univ mask), vol30, funding, btc, fng, qv, S6(核心流), core, idx, H1, H2
# 一个函数把信号变成诚实 pnl：
book_from_signal(sig, mode="xs"|"xs_weight"|"directional", fee=9e-4)
#   内部：.shift(1) 因果、gate 到 um、9bps、funding×1、vol-match 到核心
# 一个标准评估：
report(pnl, name) -> {sh, h1, h2, maxcorr6, combine7_sh, combine7_h2, combine7_lift, cagr@DD...}
```

agent 的脚本就三行：建 `sig` → `pnl = book_from_signal(sig, mode)` → `report(pnl, name)`。自测 harness（跑一个已知信号 sanity）再放 agent 进来。

## 2. 穷尽 workflow（4 阶段）

```
Construct（并行 N 个构造，每个一种不同结构）
  → 过滤 survivors（maxcorr6<0.4 AND h2>0.3 AND combine_lift>0）
  → Combine（多方法：EW / 风险平价 / regime / 子集，按 H2-OOS 选）
  → Verify（对抗审计：family-null best-of-N + signal-shuffle + 泄漏 + cost-stress）
```

构造清单要**跨结构**（本 session 14 种）：Donchian 突破 / 波动率管理动量 / 动量加速度 / 长周期 TSMOM / MACD / funding 动量 / 短期反转 / 低波 / 偏度 / regime / 量确认 / 区间压缩 / 双动量 / beta 轮动 / 长周期均值回归。

## 3. family-null 是命门（best-of-N over 全部含死的）

survivors 是"N 里最好的" → 必须过 **LIFT best-of-N family null**：shared-index 循环块 bootstrap（块~20d）over **全部 N 个构造含死的**，centered H0=0，报 observed best lift 的 P。P<0.05 才算真。

> 本 session 实例（17 agents，967k tok）：14 构造 → 4 干净正交幸存者 → RP 组合 Sh 1.99 → 认证干净（family-null P=0.0033、shuffle z=4.33、泄漏干净、cost 9-15bps 扛住）。**没有第 9 个虚高。** 提升真但**温和**（+0.22 Sh）——穷尽搜索的诚实终点常是"确认墙"，不是新大陆。

## 4. 挖出来的腿要能部署

workflow 常挑一个"最佳变体"（按 full-sample combine_lift）—— 这是**轻度嵌套选择**，family-null 的 FPR 要算进这层。部署时把选中的参数**冻成常数**（不 live 重选），并从规则重建、验证 corr=1.0 vs 缓存（parity 地基）。研究口径 vs 可部署口径见 `deployable-discipline.md`。

> 复用资产：`legkit.py`、`champion_legfan10.py`（从规则重建+验证的模板）、exhaustive-leg-mining workflow 脚本。新数据来了在同一套上重跑即可。
