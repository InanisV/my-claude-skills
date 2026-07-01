# CAGR 天花板定律 — exp(Sharpe²/2) 与 CAGR@DD 的清算

撞墙时不要盲目追一个 CAGR 数字。先算：**这个策略在理论上最高能到多少？** 这把"能不能到 1000%"从口号变成一个可证的算式。

## 1. 核心恒等式

一个年化 Sharpe = S 的策略，**在任意杠杆下**，最大可达几何 CAGR：

```
CAGR_max ≈ exp(S² / 2) − 1        （满 Kelly 杠杆处取得）
```

杠杆把 μ 和 σ 一起放大，但几何回报 = μ − σ²/2 里的 σ²/2 拖累是二次的 —— 过了 Kelly 点，加杠杆反而降 CAGR。所以 CAGR 的上限只由 **Sharpe** 决定，杠杆无法突破。

| Sharpe | CAGR_max (满 Kelly) | 满 Kelly 时的 MaxDD 量级 |
|---|---|---|
| 1.5 | ~200% | ~50-65% |
| 2.0 | ~640% | ~60-75% |
| 2.3 | ~1300% | ~70-80% |
| 3.0 | ~8900% | ~35%（远低于 Kelly 就够了）|

## 2. 反解：给定 CAGR 目标 → 需要的 Sharpe

`1000% CAGR = 净值 11×`。要 exp(S²/2) ≥ 11 → S²/2 ≥ ln11 = 2.40 → **S ≥ 2.19**（满 Kelly，DD~70-80%）。

但你几乎不会跑满 Kelly（回撤太深）。要在 **DD ≤ 55%** 拿到同一个 CAGR，你得跑在 sub-Kelly，于是需要**更高**的 Sharpe：

| 目标 | DD~80%（近 Kelly）| DD~55% | DD~40% |
|---|---|---|---|
| 1000% CAGR | Sh ~2.2 | Sh ~2.5-2.7 | Sh ~2.9-3.0 |

**用法**：把"给我 X% CAGR"翻译成"你需要 Sharpe Y，它落在 DD Z"。如果你手里干净的诚实 Sharpe 是 2.3，那么 1000% 只在 DD~80% 可达。这不是认知极限，是**守恒律**——像光速，你只能换赛道（更高 Sharpe，或更深 DD），不能违反它。

## 3. 实测杠杆-DD 前沿（比公式更诚实）

公式给上界；真实路径有聚集回撤，落点更保守。standard recipe：

```python
def frontier(pnl_1x, base_lev_grid):
    for L in base_lev_grid:
        rL = pnl_1x * L                      # 或加 DD-brake（见下）
        eq = (1+rL).cumprod()
        cagr = eq.iloc[-1]**(365/len(rL)) - 1
        dd   = (eq/eq.cummax()-1).min()
        # 记录 (L, cagr, dd)；找 CAGR 首次≥目标时的 DD
```

- **DD-brake**（回撤中降杠杆，`base_lev → base_lev·floor` over [dd_lo, dd_hi]）能在同 Sharpe 下改善 realized Calmar（削平尾部，允许更高 base_lev）—— 实测常 +100-120pp@DD50。但它 reshape 路径，**不改 exp(S²/2) 上界**。
- vol-target + brake 双叠加常**过阻尼**（Sharpe 掉），别默认叠加，二选一实测。

## 4. 加冕/汇报时必写

任何"我能到 X%"的结论旁边，写出：**(a) 依赖的 Sharpe，(b) 它的 exp(S²/2) 上界，(c) 目标 CAGR 落在的 DD**。这样"够不到 1000%@40"会立刻显形为"1000%@40 需要 Sh 2.9，而我诚实测到 2.3" —— 一个测量事实，不是失败。

> 本 session 实例：诚实干净核心 Sh 2.3 → 1000% 落在 DD~80%；可部署 beta-native（conditioned EW + DD-brake）**~280-304%@DD45-47**（Sh 2.0-2.06）。1000%@DD≤55 需 Sh 2.5-2.7，缺口的腿过不了泄漏审计（见 `inflation-patterns.md` / `leakage-audit-mlrl.md`）。区分**研究 Sharpe**（含 aD16 移植腿的 2.3）与**可部署 Sharpe**（beta-native 2.15）见 `deployable-discipline.md`。
