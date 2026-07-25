# Quant Code Review — Audit Scripts

三个独立的自动化审计脚本（对应 SKILL.md 三个 🔴 高优先级维度）+ 一个多维度 grep 预扫描。**全部产出于 2026-04-19 V15_PROD cross-margin cascade -73.8% 事故的复盘**——每一个脚本都能在事故发生之前捕获该问题。

## 脚本清单

| 脚本 | 维度 | 解决什么问题 |
|---|---|---|
| `audit_risk_flags.py` | P.4 | Profile 里所有风控开关的"effectively-off ratio"。比例 > 50% 拒绝部署 |
| `audit_cascade_simulation.py` | 2.13 | 全 codebase 扫描 use_*_check / next_bar_entry 等真实性 flag 的实际值，区分 production / research |
| `audit_identity_hardcode.py` | 4.5.2 | monitor_export.identity.* 里的硬编码字符串识别（特别是内部 codename） |
| `grep_battery.sh` | 多维度 | 一键跑齐 SKILL.md 各维度散落的 grep 探测（只读预扫描，分节输出命中） |

## 在真实项目（4/19 之前的 V15_PROD codebase）上验证

### audit_risk_flags.py

```bash
python audit_risk_flags.py config/dca_v12_profiles.py V15_PROD
```

输出（节选）：
```
"profile": "V15_PROD",
"total_risk_flags": 27,
"effectively_off_count": 14,
"effectively_off_ratio": 0.519,
"severity": "🔴🔴 REJECT"
```
→ 51.9% effectively-off，触发 REJECT 拒绝部署。如果 V37 commit 前跑过，
就能阻止 dd_kill_pct=0.99 + use_liquidation_check=False 同时进 production。

### audit_cascade_simulation.py

```bash
python audit_cascade_simulation.py /path/to/project
```

输出（节选）：
```
use_liquidation_check  True= 10  False=125  Total=135
Issues: 134 total  (6 🔴 CRITICAL, 128 ⚠️ WARN)
🔴 CRITICAL  use_liquidation_check=False  config/dca_v12_profiles.py:214
    → "use_liquidation_check": False,     # V37: disabled (backtest-only)
```
→ 一个 flag 被关 125 次，证明这不是孤立失误，是整条研究链系统性失稳。

### audit_identity_hardcode.py

```bash
python audit_identity_hardcode.py /path/to/project
```

输出：
```
🔴 CRITICAL  strategy="Regime-Adaptive DCA V15 (MEGA V2)"
    → src/live_dca_bot.py:4972
    → Internal codename 'MEGA V2' hardcoded in identity
```
→ 直接锁定 4/19 事后误诊的源头：identity.strategy 是常量，与实际 profile 解耦。

## CI/CD 集成建议

在 git pre-commit hook 或 CI pipeline 里加入：

```yaml
# .github/workflows/quant-audit.yml
- name: Risk Flag Inventory (P.4)
  run: python skills/quant-code-review/scripts/audit_risk_flags.py config/profiles.py PROD_PROFILE
- name: Cascade Simulation Audit (2.13)
  run: python skills/quant-code-review/scripts/audit_cascade_simulation.py .
- name: Identity Hardcode Audit (4.5.2)
  run: python skills/quant-code-review/scripts/audit_identity_hardcode.py .
```

任一脚本 exit code != 0 应阻止 deploy。

## 退出码约定

- `0` — 通过
- `1` — WARN（research script 有问题，或 effectively-off ratio > 30%）
- `2` — CRITICAL（production profile 有问题，或 effectively-off ratio > 50%）

## 适配其他项目

这些脚本对模式做了通用化处理，适用于任何带 profile 配置 + backtest 引擎的量化项目。
项目特定的 risk flag 命名可在 `RISK_PATTERNS` 列表里追加。

---

> 本目录是 `quant-code-review` skill 的可执行附件。任何 quant project 在 commit
> production-affecting 改动前都应当跑一遍这三个脚本。如果 ≥ 1 个 CRITICAL，
> commit 应当被阻止直到修复。

## 安全注意

`audit_risk_flags.py` 默认用 `exec()` 加载 profile 模块（以支持 `{**BASE, ...}`
继承写法）。**只在受信任的仓库上运行**；审计第三方/不受信代码时加 `--ast`
（纯 AST 解析，不执行任何代码）。`grep_battery.sh` 为纯只读扫描，无此限制。
