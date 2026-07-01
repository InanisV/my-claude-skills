# 研究 Sharpe vs 可部署 Sharpe 纪律

一个回测数字要上真金，先问：**它的每个部件都能在实盘因果重算吗？** 很多漂亮的研究口径根本不可部署。上真金前，把"研究 headline"和"活到生产的数字"分开写。

## 1. 回测构造 ≠ 可部署

| 回测构造（不可部署） | 为什么 | 可部署替代 |
|---|---|---|
| H1 估计权重应用到 H2 的风险平价 | 用了"未来 H1 全窗"才定的权重 | 等权，或 **expanding 因果**估计（只用 t 之前） |
| 全样本选的"最佳参数/tilt" | 后见之明 | 参数冻成常数 + true-OOS 验证；或 walk-forward 重选 |
| 从缓存 pkl 直接加载的腿收益流 | live 没有那个 pkl | 从**规则**重建，验证 corr=1.0 vs 缓存 |
| 跨仓移植的收益流（如 alpha 仓的 aD16） | live 依赖另一个仓的信号 | 在本仓**原生重建**，否则是**部署断点** |

> 本 session：研究干净天花板 Sh 2.3（含从 alpha 仓移植的 aD16 腿）。但 aD16 非 beta 原生 → 部署断点。可部署 beta-native 核心 = conditioned-6 + 4 条原生规则腿，等权 + DD-brake = **~280-304%@DD45-47（Sh 2.0-2.06）**，是研究口径 2.3 的诚实落地，2.6× 前一 live 冠军。**别把 2.3/413% 当可部署数字报。**

## 2. 部署门（上真金前逐条过）

1. [ ] 每个部件有**因果 live builder**（不依赖全样本/缓存/别的仓）？
2. [ ] 组合权重方案可 live 计算（等权 or expanding-因果，非 H1-fixed）？
3. [ ] 杠杆/DD-brake 从 **live equity_history** 因果算（回测与实盘同一 peak/DD 定义）？
4. [ ] 机器零 **parity 测试**：live 重算的 book/return == 回测 ground-truth（逐腿 corr=1.0、组合 book↔return witness、truncation 因果、never-univ==0）？
5. [ ] 继承所有已审计的风控门（DL/flow staleness、gate、gross cap、KILL_DD）？
6. [ ] 冷启动/重启中途回撤/未知态能正确恢复？

## 3. 报两个数字

汇报里**并列**：
- **研究口径**：最干净构造能到多少（含不可部署的移植腿/最优组合）——认知上界。
- **可部署口径**：真金能上的、每部件因果 live 可算的、过 parity+审计的数字。

差距本身是信息（本 session：2.3 研究 vs 2.15 可部署；缺口是 aD16 移植腿 + H1-RP 构造）。把两者混为一谈 = 对自己撒谎，也会让真金上一个审计会拆穿的数。

## 4. 新策略上线的安全形态

作为**opt-in 新策略**加进 dispatch（默认冠军不动、交易保持关闭），配独立 parity 测试 + 独立审计轮次，爆炸半径受控，人最后 review 才算数。

> 相关：`orthogonal-structures.md`（1/N vs MV 的部署含义）、`priorwork-reconcile.md`（移植腿的部署断点）、SKILL.md 实盘-回测对齐铁律 / 研究代码 vs 生产代码语义鸿沟（本文档是其上叠加的"腿依赖可部署性"层）。
