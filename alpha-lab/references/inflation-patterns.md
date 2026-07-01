# 回测虚高/泄漏模式目录 + 加冕前 checklist

任何"惊艳"的结果在庆祝**之前**过一遍这张表。本 session 一条弧线抓了 8 个虚高，全部靠这些检测法。虚高不是道德问题，是默认状态——**没被证否的高分默认是虚高**。

## {虚高类 → 机理 → 检测法 → 一句话嗅探}

| 虚高类 | 怎么把 headline 抬高 | 检测法 | 嗅探 |
|---|---|---|---|
| **Gate-bypass** | 某条流忽略 `view["univ"]`，在全宇宙选币 → headline ungated | 每条流**先 gate 后 rank**；对比 gated vs ungated | 有流的选币能碰到不在 univ 的币 |
| **Funding ×N** | 在已按日汇总的 panel 上再 `funding×3` | funding×1 sanity；grep 每处 funding 乘子 | carry 腿 standalone Sharpe 高得离谱 |
| **静态 tilt lookahead** | 用后见之明选一个静态权重/阈值（如 .45 tilt） | TIME-SPLIT：该常数在 H1 上选、H2 上验 | "恰好"选中的魔法常数 |
| **Dredge best-of-N** | 从 N 个构造里挑最高 standalone Sharpe，无 family null | **LIFT best-of-N family null**（shared-index 循环块 bootstrap，over 全部构造**含死的**）P<0.05 | 幸存者是"试了很多里最好的" |
| **年化口径错配** | 365 vs 252 混用（DVOL 隐含 vs 已实现） | 统一年化常数；量纲检查 | vol/Sharpe 差 √(365/252)≈1.2× |
| **Accrual-无-MTM** | carry 类只记应计不记市值重估 | 强制 mark-to-market 每 bar | carry 曲线异常平滑 |
| **多重比较运气** | tick 微观特征试了 20 个，1 个"survive" | family null over 全部特征×符号；true-OOS | 单个特征在朴素筛选下亮眼 |
| **ML/RL 样本内膨胀** | "holdout" 与训练窗**重叠** → holdout 也是样本内 | true-OOS = 所有训练截止**之后**；peek-ahead 探针（见 `leakage-audit-mlrl.md`） | 训 2024-01..2025-12，"holdout" 从 2025-01 起 |
| **port_base × boost 会计** | 组合构造后再乘 boost，重复计入 | 逐笔追组合权重的施加顺序 | headline 是另一个数的倍数 |
| **短波动率尾部陷阱** | 中位数很好但均值≈0（右尾巨亏） | 看**均值**不看中位；逐年；DD | 中位 -19% 但等权组合赚 ~0 |

## 检测工具（rigor 套件的应用，见 SKILL.md 的 rigor 章）

- **SIGNAL-shuffle**（横截面打乱信号，非 return-shuffle）：多元化/alpha 的正确 null，要 z>2 且 shuffled 版本**主动变差**。
- **FAMILY-NULL best-of-N**：shared-index 循环块 bootstrap（块~20d），over **全部**候选构造（**必须含死的**），centered H0=0。用 standalone-Sharpe best-of-N 会假过（本 session bookimb 就这样假过 0.0355）。
- **peek-ahead 探针**：`shift(-1)` 应让 Sharpe **暴涨**、`shift(+1)` 应**变差** —— 真因果 book 的签名。
- **cost-stress**：9→15bps，Sharpe 掉多少。de-lever 不可能抬 Sharpe。
- **true-OOS**：所有腿训练截止之后的窗口。

## 加冕前 checklist（全过才升级冠军）

1. [ ] 每条流 gate-first，funding×1，9bps，`.shift(1)` 全在？
2. [ ] LIFT best-of-N family null P<0.05（over 全部构造含死的）？
3. [ ] SIGNAL-shuffle z>2 且方向正确？
4. [ ] TIME-SPLIT / true-OOS：H2 持平不崩？
5. [ ] ML/RL 腿过 `leakage-audit-mlrl.md`？
6. [ ] cost-stress 9→15bps 仍活？
7. [ ] 逐年均衡（非彩票年主导）、看均值非中位？
8. [ ] 数字是**可部署**口径还是**研究**口径（见 `deployable-discipline.md`）？

> 铁律：**宁可报告费后死亡，也不报告一个审计会拆穿的数字。** 造一个建立在泄漏腿上的假 900% 是最大的失败。
