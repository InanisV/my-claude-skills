# ML/RL 腿泄漏审计协议

ML/RL 腿（LightGBM/PPO/神经网）是虚高最爱藏身处。`H2 > H1` **不是**无泄漏的证据——如果模型训练窗覆盖了 H2，那 H2 强只是样本内拟合。任何进入组合的 ML/RL 腿必须过这套。

## 1. train/test 重叠陷阱（本 session 第 8 个虚高）

查训练脚本的 `train_start` / `train_end` 和曲线文件的 `holdout_start`：

```
PPO 实例：train_ppo.py train 2024-01-01 .. 2025-12-01
          但 "holdout" 从 2025-01-04 起 → 与训练窗重叠！
          2025-01..2025-12 全是样本内。
```

**真-OOS = 所有训练截止之后的窗口**（此例 2025-12 之后）。在真-OOS 上重测：

```
PPO 真-OOS Sharpe: 样本内 1.75 → 真OOS 0.07  = 已死（虚高确认）
```

规则腿（TSMOM、机械 funding）无训练 → 全窗干净，是参照锚。

## 2. peek-ahead 探针（因果性的签名）

对腿的信号做时移，看 Sharpe 怎么变：

```python
p_causal = book_from_signal(sig)            # .shift(1) 应用
p_peek   = book_from_signal(sig.shift(-1))  # 偷看未来 1 bar
p_lag    = book_from_signal(sig.shift(+1))  # 多滞后 1 bar
```

- **真因果 book**：`p_peek` Sharpe **暴涨**（如 1.43→5.32），`p_lag` **变差**（1.43→1.28）。
- **偷看的 book**：`p_peek` 几乎不变（它已经在偷看）。

本 session 用它证明 legfan10 各腿因果干净。

## 3. return-shuffle vs SIGNAL-shuffle（别混）

- **SIGNAL-shuffle**（横截面打乱信号）：多元化/alpha 贡献的 null（rigor 套件）。
- **return-shuffle**（打乱标签/目标）：ML 管线 sanity —— 在**打乱的目标**上重训模型，若还"学到" alpha，就是管线泄漏（特征里混了未来）。

## 4. 五步 checklist

1. [ ] 找到训练截止（`train_end`）和 holdout 起点；确认**无重叠**。
2. [ ] 在**真-OOS**（所有训练之后）重测腿 Sharpe；若从样本内大幅衰减（>60%）→ 泄漏，剔除。
3. [ ] peek-ahead 探针：shift(-1) 暴涨 / shift(+1) 变差，签名对得上？
4. [ ] return-shuffle 重训：打乱目标后模型不该有 alpha。
5. [ ] 特征逐个查因果（rolling/pct_change/quantile 都 past-only；无 `.rolling(center=True)`；截止日边界无泄漏）。

## 5. 保守处置

真-OOS 只有几个月时噪声大——**无法证实干净就当泄漏剔除**，别把不确定的 ML 腿放进要上真金的组合。本 session：剔除泄漏的 PPO，只留规则 aD16（真-OOS 2.91，规则构造不可能泄漏）+ beta-native 挖出的规则腿。

> 相关：`inflation-patterns.md`（ML/RL 样本内膨胀条）、`priorwork-reconcile.md`（移植 sibling 仓的腿时用这套审它）。
