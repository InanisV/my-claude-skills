# N_eff、正交『结构』、与组合纪律（1/N 打败 MV OOS）

组合的 Sharpe 由**有效独立赌注数 N_eff** 撑起。基本定律：`IR ≈ IC × √breadth`。撞到"信号找不动了"的墙，往往不是没 alpha，是**你在同一种结构里找正交信号**——它们天然相关，N_eff 上不去。

## 1. 正交『结构』≠ 正交『信号』

- 同一结构内的信号（全是横截面 XS）**共享选币噪声** → 挤在一个 cluster，两两相关 ~0.3，N_eff 被高估。
- 真正抬 N_eff 的是**不同结构**：时序动量（directional/net-beta）⊥ 横截面（market-neutral）⊥ 宏观择时 ⊥ carry ⊥ RL/ML。它们的相关天然 ~0。

> 本 session 决定性对账：beta 仓 6 流**全是 XS**，N_eff 4.79，EW Sh 1.77。alpha 仓 5 腿跨**不同结构**（D16 时序动量 / Funding carry / PPO RL / v30 ML流 / CM30d 链上），N_eff 4.91，EW Sh **2.93**。差距不是 N_eff（4.79≈4.91），是**腿的质量 + 结构多样性**——尤其缺一条高 Sharpe 的**方向性时序动量**腿（D16 Sh 1.86，对一切正交）。

**用法**：要抬一个组合的 Sharpe，别再加同结构的变体（会被 EW 稀释）。加一条**真正不同结构**的腿。诊断：算流的相关矩阵 + N_eff（参与比 = `(Σλ)²/Σλ²`），找被高估的 cluster。

## 2. N_eff 的量化

```python
C = streams.corr().values
ev = np.linalg.eigvalsh(C); ev = ev[ev>1e-9]
n_eff = (ev.sum()**2) / (ev**2).sum()      # 参与比：越接近 N 越独立
```

flow cluster {taker,liq,mom,glsr} 两两 corr 0.30 → 实际只贡献 ~1.5 个独立赌注，不是 4 个。

## 3. 组合纪律：1/N 打败均值方差（DeMiguel 2009）

**等权（1/N）在 OOS 上打败均值方差/风险平价**——权重估计误差的代价超过收益。别过度优化组合。

> 本 session 实测：walk-forward Ridge 均值方差组合 OOS **更差**（Sh 1.38 < 等权 1.77），H2 崩到 0.5-0.6（估计误差过拟合）。H1-fixed 风险平价看着好（2.00）但那是**回测构造**（H1 估计应用到 H2），不可部署（见 `deployable-discipline.md`）。expanding-因果风险平价可部署但早期窗口噪声拉低（1.80）。**部署选等权**：几乎等于 fixed-RP，零估计误差，最稳。

## 4. 一句话决策树

- 组合 Sharpe 上不去 → 是不是所有腿同结构？加一条**不同结构**的腿（时序动量 / 宏观择时 / vol 溢价）。
- 想用花哨组合法（MV/HRP/RP）抬 Sharpe → 先跑 OOS 对比等权；八成不如等权，别自欺。
- MV 理论上限 `√(ΣSharpe_i²)` 够不着（估计误差），别拿它当目标。

> 相关：`leg-mining-harness.md`（并行挖多结构腿）、`ceiling-law.md`（N_eff→Sharpe→CAGR 上界）。
