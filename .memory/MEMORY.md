# Session Memory
> Last updated: 2026-03-21 — initialized from 9 historical sessions

## Active Projects

### Crypto Trading Bot (quant-trading-stable)
- **Status**: 进行中 — 实盘运行但持续亏损，正在积极优化
- **Current version**: V40+ (从 V4 → V5 → V7 → V16 → V40 一路迭代)
- **Key files**: `src/bot.py`, `src/factors/live_engine.py`, `config/settings.py`, `backtest_standalone.py`
- **Architecture**: Regime-Adaptive DCA + Factor-Boosted Entry + Trailing Profit + Polymarket Oracle
- **Recent progress**:
  - V7 trailing profit 策略回测表现优秀（回撤可控、持续上行）
  - V16 加入了 kelly_scale 和 Drawdown Shield
  - V40 进行了引擎级架构优化
  - 实盘发现持续亏损，正在分析是算法问题还是实现问题
  - 运维层 14 个关键场景全覆盖，3 个可修复问题已修复
- **Next steps**:
  - 引擎级重构：信号强度加权替代等权分配
  - Per-symbol trailing stop 内置到引擎
  - 解决 Polymarket 市场窗口与 settle_after 参数不对齐的问题
  - 分析实盘亏损根因（算法 vs 实现）
- **Open questions**:
  - Alpha 效率损耗严重（纯信号 CAGR 365% vs 实际 52%，7x 损耗）
  - 动态 N（币种轮动）在真实引擎中因等权分配和信号滞后而失效
  - Polymarket 市场 settle 时间窗口经常不对齐，导致 bot 无法开仓

### Skill 开发与维护
- **Status**: 进行中
- **Recent progress**:
  - 评估了 gstack 和 office-hours 两个 GitHub 仓库的 skill
  - 将 gstack 的精华融入 dev-planner（问题验证、安全控制、Bug 调查协议、开发复盘）
  - 新建 session-memory skill（本文件）
- **Next steps**: 安装 session-memory skill 到 .skills 目录

## Key Decisions

### 2026-03 选择 Trailing Profit 作为 V7 核心机制
- **Context**: V5 的固定止盈在趋势行情中过早离场
- **Decision**: 实现 3% 激活 + 自适应回调（小利润 1.5%、大利润 3%）
- **Rationale**: 让赢家跑得更远，同时用 1% 硬止损控制亏损
- **Result**: 回测表现显著提升，回撤可控

### 2026-03 4-Level Regime Detection
- **Decision**: 使用 ADX + MA50/MA200 crossover 区分 Bull/Caution/Range/Bear
- **Rationale**: 不同市况需要不同的仓位管理和入场标准
- **Result**: 回测中有效减少了震荡市的假信号

### 2026-03 引擎重构方向确定
- **Context**: 纯信号模拟 vs 实际引擎存在 7x alpha 损耗
- **Decision**: 下一步做信号强度加权 + per-symbol trailing stop
- **Rationale**: 等权分配和缺少个股止盈是最大效率损耗源

## Learnings

### 2026-03 动态 N 在真实引擎中失效
- **What happened**: 纯信号模拟中动态 N（质量门槛制）CAGR 390%+，但引入真实引擎后效果消失
- **Lesson**: 新币种轮动需要 warmup 才能产生有效信号，等权分配也稀释了强信号
- **Action**: 需要引擎架构级重构才能真正利用动态 N

### 2026-03 Polymarket 市场窗口对齐问题
- **What happened**: Bot 运行近 10 小时完全没有开仓，因为 settle_after 参数与可用市场不匹配
- **Lesson**: Polymarket 的 5min up/down 市场结算时间变化大，固定的容忍窗口不够灵活
- **Action**: 需要调整 settle_after 参数容忍度，或实现自适应市场匹配

### 2026-03 减仓策略把回撤变成了震荡
- **What happened**: 为控制回撤实施减仓，结果收益被砍，回撤变成了横盘震荡
- **Lesson**: 简单的仓位缩减不是解决回撤的正确方式，需要更精细的信号级控制

## User Preferences
- 语言：中文交流
- 工作风格：快速迭代，数据驱动决策
- 偏好量化结果（夏普、CAGR、MaxDD 等具体数字）
- 使用 Cowork 模式，多个会话并行处理不同方面
- 关注 X (Twitter) 上的技术社区动态
- 实盘交易，对亏损敏感（"真金白银"）
- 项目代码在 GitHub: `quant-trading-stable`

## Recent Sessions

### 2026-03-21 分析亏损并优化算法 (running, 152+ turns)
- **Goal**: 深入分析实盘持续亏损原因，优化算法
- **Outcome**: 进行中，V16 的 kelly_scale 和 Drawdown Shield 正在整合
- **Next**: 待完成

### 2026-03-21 优化 V40 架构 (running, 26+ turns)
- **Goal**: 优化加密交易策略架构
- **Outcome**: 进行中，测试套件文件生成中
- **Next**: 待完成

### 2026-03-20 评估 GitHub 仓库 skill
- **Goal**: 评估 gstack 和 office-hours 两个仓库，提取有用的 skill 模式
- **Outcome**: 将 5 项核心改进融入 dev-planner（问题验证、安全控制、Bug 调查、复盘、完整性原则）
- **Key changes**: dev-planner SKILL.md 升级版生成到 `dev-planner-upgrade/`
- **Next**: 手动替换到 .skills 目录

### 2026-03-19 检查实盘交易日志
- **Goal**: 分析最新实盘 log
- **Outcome**: 发现 Bot 运行近 10 小时完全没有开仓
- **Key changes**: 定位到 Polymarket settle_after 参数不对齐问题
- **Next**: 调整 settle_after 容忍度

### 2026-03-19 回测并可视化结果
- **Goal**: 全面回测比较不同配置
- **Outcome**: 63 个配置中找到最优前沿（2 标的 aggressive $2.80M CAGR 130%）
- **Key changes**: 生成 final_panorama.html 全景仪表板
- **Next**: 引擎级重构（信号强度加权 + per-symbol trailing stop）

### 2026-03 V7 策略优化到实盘
- **Goal**: V7 以上继续优化并部署实盘
- **Outcome**: V7 全部 21 条逻辑路径对齐，运维层 14 场景覆盖，实盘可用
- **Key changes**: 多个版本提交（V4 → V5 → V7），完整对齐检查
- **Next**: 后续版本（V16, V40）继续优化

### 2026-03 因子挖掘移植
- **Goal**: 将因子挖掘算法移植到加密交易
- **Outcome**: rv_mom + wick 因子成功集成，SOL/XRP 权重对齐
- **Key changes**: `backtest_standalone.py` 支持 4 资产，多进程加速
- **Next**: 继续回测验证

### 2026-03 设计加密交易算法
- **Goal**: 从零设计 Regime-Adaptive DCA 策略
- **Outcome**: 完成 V4 基础框架，确立 4-level regime detection
- **Key changes**: 初始提交 `fb48440`
- **Next**: 迭代优化（已在后续会话中完成）
