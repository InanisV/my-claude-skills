# INDEX · 规则文件「标题 → 行号」（安装时自动生成，别手改；改了规则文件后由安装器或 bin/gen-index.sh 重算）

> 用法：读长文件前先看这里，`sed -n '<起>,<止>p' <文件>` 只读本步骤要的章节；分段读区间不重叠；同一会话同一区间不读第二遍。L 后面是行号，井号个数是标题层级。

## references/00-core-contract.md（10190 字符 · 60 行）
L2 # 结果契约卡（精简档入口 · 只写"必须成立的结果"�
L6 ## 0 开场（任何模式）
L13 ## 1 访谈 / 起草
L23 ## 2 自检（发布前必跑）
L31 ## 3 发布
L39 ## 4 变更（已有稿）
L45 ## 5 建卡（伴生 jira-card-kit）
L52 ## 6 登记（S3 / S4）
L58 ## 7 采集与 token

## references/00-orchestrator.md（35935 字符 · 169 行）
L2 # PRD Authoring Kit —— 编排主流程（跨平台唯一权威）
L8 ## 第 0 步（不可跳过）
L11 ## 执行强度分档（按模型能力选，与下方「标准档 /
L20 ## 开场：先收敛 → 识别模式 → 判体量
L55 ## 分档加载清单（按需惰性加载，别开场全读）
L71 ## Token 纪律（2026-09 起，两档通用——按 token 计费�
L84 ## 规则维护约定（给改 kit 的人，2026-10 起）
L92 ## 恒定规则（三模式都遵守）
L112 ## 标准流程
L148 ## 交付标准（详见 `05`）
L157 ## 降级（缺能力也别卡死）
L166 ## 别做的事

## references/01-authoring-rules.md（29416 字符 · 159 行）
L2 # Authoring Rules —— 怎么写才能过 nocode 门禁
L8 ## 0. 目标口径（先记死）
L28 ## 0.5 最小充分原则（比"过分"更重要——别被审查�
L51 ## 1. 元原则：为「会误判的 LLM 审查器」而写（写清
L69 ## 2. 五个 P0 阻塞项（重点防守）
L87 ## 3. 其余检查，按维度给通过写法
L89 ### 完整性（30%）
L93 ### 可量化性（30%，house 稿失分重灾区 → 重点补）
L98 ### 边界清晰度（20%）
L103 ### 技术可行性（20%）
L110 ## 4. 域规则：crypto / 交易所（本团队主场）
L122 ## 5. 埋点四检查（tracking_*）：一句话记法
L134 ## 6. 场景规则库（附加检查，命中才用）
L141 ## 7. 章节 → 检查 速查
L158 ## 8. 格式·文案·措辞

## references/02-prd-template.md（92095 字符 · 571 行）
L2 # PRD 模板 · house-style + nocode 严谨度
L71 # 编写记录
L87 # Background & Business Values 背景与价值
L100 ## 目标用户 **[nocode必填]**
L108 ## 成功指标 **[nocode必填]**
L119 # 需求范围与边界 需求范围&风险点
L121 ## 本期包含
L124 ## 本期不包含（Out of Scope） **[nocode必填]**
L132 ## 需求关联方与依赖 **[nocode必填]**
L161 # Overall User Scenarios 用户场景总览
L179 # 功能需求 User Stories 用户故事
L183 ## 模块地图
L208 ## 全局口径（全文只写一处，≤10 行；US-R 内引用�
L221 ## US1：作为（角色），我希望（能力），以便（价�
L223 ### US1-R1：（需求标题）
L416 ## 产品设计范式字典
L426 # 验收标准 **[nocode必填·独立成章]**
L430 ## US1-R1 功能验收
L435 ## 性能验收（有 NFR 则填）
L442 # 非功能需求 NFR（有则填，量化）
L454 # Data Requirements 数据与埋点 **[nocode必填：二选一]**
L470 # Localisation Requirements 本地化（有多语言则填）
L480 # 【待确认】（可选）
L483 # 风险与不确定性（可选）
L493 # 附录：边界细则（可选：规则变体、历史兼容、�
L495 # PRD Quality Gates (Delete after finalised)
L548 ## Kit 自查清单（发布前整节删除）

## references/03-interview-playbook.md（14729 字符 · 110 行）
L2 # Interview Playbook —— 从零对话把需求聊清
L6 ## 对话总原则
L16 ## 采集顺序（命中第一个空的就问，能推断的跳过�
L32 ## 功能深挖（分档，别对每个功能都上满五问）
L48 ## 方案给产品看之前（讨论阶段同样适用，不等起�
L59 ## 访谈期落盘：decisions.md（状态在磁盘上，不在上�
L66 ## 多系统 / 多相关方需求的三件工件 + 接口模型（�
L79 ## 停止判据（到这就起草，别多问）
L92 ## "直接写别问了" 快车道
L98 ## 起草 → 确认 → 发布
L104 ## 常见对话

## references/04-upgrade-draft.md（33243 字符 · 129 行）
L2 # Upgrade Existing Draft —— 把粗稿/旧PRD 升级到能过门�
L7 ## 步骤 1 · 读入原稿（含乱输入）
L19 ## 步骤 2 · 映射到模板结构
L26 ## 步骤 3 · 补齐 nocode 缺口（house 稿通病）
L49 ## 步骤 4 · 缺口太大时，定向补问
L53 ## 步骤 5 · 改前打招呼 → 自检 → 发布
L68 ## 步骤 6 · 技术方案对齐（研发方案出来后的必做 p
L80 ## 需求变更流程（已有达标稿的逻辑变更）
L109 ## 红标增量回写模式（研发已开工的在用 PRD）

## references/05-self-review-gate.md（88553 字符 · 377 行）
L2 # Self-Review Gate —— 自检（两种模式）
L10 ## 模式A·只自检（纯逻辑内审 · 独立入口）
L17 ### 三条铁律（只自检模式，先记死）
L22 ### 七步流程
L47 ### 对话输出模板（固定 · 照 dify 内审报告去 T 版）
L82 ## 模式B·发布前自检（写 / 升级模式内用 · 保持两�
L90 ## 审查器新版行为（2026-07，写作与自检都要知道）
L105 ## 自检的两栏口径（先理解）
L117 ## 步骤 0 · 结构扫描（编号步骤，不可跳过——含 
L174 ## 步骤 1 · 判定适用范围
L190 ## 步骤 2 · 逐条评判 18 条（① 门禁判定栏）
L226 ## 步骤 2.5 · 第二道门 · 逻辑内审（② kit 加严）
L250 ## 步骤 3 · 汇总
L258 ## 步骤 4 · 判定与修复
L278 ## 步骤 4.5 · 两视角复读（资深产品 / 资深研发各�
L290 ### 资深产品的八根探针（P）
L300 ### 资深研发的八根探针（D）
L314 ## 步骤 5 · 输出自检报告
L317 ### PRD 自检门禁报告（checks 原文基线 2026-07-08；审�
L338 ### 🔴 报告五行硬闸（两档通用，2026-09 补——标�
L342 ### 🔴 轻量档同样必须交付**可见的自检简报**（四
L358 ## 官方引擎软集成（装了就用，没装按现状）
L367 # ② agent 逐项自判，写 results.json：{"<check_id>": {"pass
L376 ## 与"升级现有草稿"配合

## references/06-lark-publish.md（39262 字符 · 213 行）
L2 # Lark Publish —— 用 lark-cli 把 PRD 写进飞书
L44 ## 步骤 0 · 发布前净化（必做，别把半成品发出去�
L49 # 从首个 H1 标题起保留正文(丢掉顶部说明块) → 删�
L53 # 红灯校验(用 if 而非 &&，避免 set -e 下 grep 无命中�
L60 ## 步骤 1（默认）· 新建文档，Markdown 导入
L66 # 返回 JSON 含 url / document_id
L75 ### 元素表富块写法（格内列表，实测）
L81 ## 步骤 2（可选，高保真）· DocxXML 富块 / 插图
L88 # 定位到某段后：--selection-with-ellipsis "锚点文字片段
L96 ### 元素表「原型」格贴图（设计稿截图，实测编排�
L140 ## 步骤 3 · 迭代更新已有文档（保护人工内容，别�
L165 # 改前记基线（img 形态兼容裸标签与转义两种）
L167 # … 执行你的 block 改动 …
L170 # 再核对：每个 @人 user-name 仍在、模块/小节数不变
L176 ## 步骤 4 · 收尾
L186 ## 埋点子表（**可选，默认不做**；方法见 `09-trackin
L193 ## 错误分诊（PM 友好话术）
L207 ## 提审 · PRD Bot 官方内审（发布后的正式准入入口�

## references/07-format-conventions.md（34329 字符 · 162 行）
L2 # 数字·文案·UI 格式规范（house canon）
L6 ## 一、数字格式
L20 ### 分段格式必须给完整口径（研发实测必问，缺了�
L38 ## 二、UI 词条约定（减少词条歧义）
L45 ## 二之二、产品口径 vs UED 职责（边界条：什么该写
L58 ## 二之三、产品行为 vs 实现机制（🔴 边界条：PRD �
L90 ## 三、措辞与排版禁忌（读起来不像 AI、也更好过�
L99 ## 四、标准兜底措辞（统一，避免同义不同写触发 i
L112 ## 五、可读性与 AI 友好排版（强制）
L130 ## 五之二、排版工具箱选型表（何时用什么·怎么�
L154 ## 六、无 lark-cli 纯文本交付格式（降级专用；与 §

## references/08-logic-review.md（16079 字符 · 116 行）
L2 # 逻辑内审 —— 让 PRD 逻辑经得住考验（写作侧纪律
L8 ## 0. 范围铁律（先记死）：审产品逻辑，不审实现规
L23 ## 0.6 强制产物：逐对象闭环矩阵（把六维从"凭印象
L44 ## 1. 六个维度（矩阵各列的落笔要点；判据以 checks-
L54 ### A 状态覆盖
L61 ### F 边界极值
L68 ### B 交互闭环
L74 ### C 条件分支
L80 ### E 跨模块自洽（我旧版第二道门最缺的一维）
L88 ### T 可测性
L94 ## 2. 跨维度死结（单点检查看不出，必须前后串联�
L99 ## 3. 判定与从严（curator 心法：砍掉 70-80% 噪音）
L111 ## 4. 怎么用

## references/09-tracking-gen.md（33320 字符 · 143 行）
L2 # 埋点生成 —— 从 PRD 自动产出埋点表（读线上公参
L6 ## 第 0 步：先确认要不要埋点
L9 ## 流程
L12 ## 1. 抽独立 UI 对象（不是每个字段都埋）
L28 ## 2. 埋点规范（公司口径）
L46 ## 3. 标准事件类型（6 种）与 Element vs Resource
L56 ## 4. 公参：查**线上**公参表校验（不硬编码、不编�
L73 ## 5. 输出埋点表（10 列，过审样例校准口径）
L105 ## 5.5 三视角复核（删前、录前必做——防过抽，也
L120 ## 6. 写回 PRD（默认不建子表，满足 nocode 准入 + 单�
L126 ## 7. 反编造（贯穿）
L131 ## 8. 录入公司埋点平台（产品要求时；实测 2026-09 �

## references/10-i18n-terms.md（9452 字符 · 64 行）
L2 # 国际化词条提取 —— 从 PRD 抽出要翻译的 UI 文案
L6 ## 铁律（违反则整份词条作废）
L12 ## 什么是词条
L18 ## 常见误判（不要抽）
L30 ## 在 PRD 里怎么找
L36 ## 输出与清洗
L42 ## 交叉检查：后端已拼接文案 × 多语言（开工阻塞�
L45 ## 喂给 Localisation 章节
L51 ## 词条表交付后的常规回合（维护 · 错误码 · 校对

## references/11-usage-telemetry.md（27867 字符 · 170 行）
L2 # 使用采集（telemetry · 尽力而为，绝不打扰用户）
L8 ## 何时记录
L26 ## 五条铁律（先记死）
L33 ## 环境要求（🔴 通用条款，改命令前先过一遍）
L39 ## 🔴 写入契约（两形态通用，违反 = 宁可不写）
L49 ## 🔴 需求名 = 跨技能统一去重键（八种交付共用一
L73 ## 形态 C · 脚本（v1.8.1 起，所有平台优先用它；A / 
L83 ## 怎么记（两种形态，先按平台选一种）
L98 ### 形态 A · Kiro / Claude / Gemini / Antigravity（一段自包�
L100 # PRD kit 使用采集 —— ⚠️【务必单行执行】(分号
L101 # 🔴 只用系统自带工具：jq / timeout 一律禁用(macOS �
L103 # 占位符：<文档名>=需求名(取法见上方 §需求名 = �
L114 ### 形态 B · Codex（沙箱兼容 · 分步各自独立裸跑）
L158 ## 排查：表里没某人的记录（七个已知根因）

## references/12-context-recall.md（32524 字符 · 293 行）
L2 # 背景自采集 —— 写 PRD 前先查历史需求库
L8 ## 一、先判「改动性质」→ 定检索意图（看这次在�
L34 ### 改动性质怎么判（机械，别凭语感）
L46 ### 检索键怎么提（三种意图各一条机械路子）
L65 ## 二、交付物：背景简报（访谈） / 检索脚注（升�
L69 ### 形态一 · 背景简报（全新需求 / 访谈；≤15 行，
L90 ### 形态二 · 检索脚注（新增型 / 修改型 / 抬标；贴
L115 ## 三、检索漏斗 L0 → L3（逐级放大，命中即停）
L117 ### L0 · 受控词表对齐（免费，0 次 API）
L129 ### L1 · 表查询（实测 ≈2–3 s/次）
L144 # ① 关键词查（默认，最省）——一个键、投影三�
L149 # ② 条件查（要同时按端/模块过滤时用）——contai
L160 ### L2 · 目录导航（拿到标题树再决定读哪节）
L170 ### L3 · 切片（只把该节读进上下文）
L190 ### 兜底 · 树浏览 → 搜索（顺序别反）
L195 ## 四、双闸（硬约束，违者退回）
L216 ## 五、平台形态（两形态同款结构，按平台选一种�
L235 ## 六、Claude Code 可选加速：派子代理精读
L248 ## 七、manifest 机制（内置 / 用户级覆盖 / 空清单）
L260 ## 八、安全边界（三句，无例外）
L266 ## 九、实测记录（2026-09-01，lark-cli 1.0.91，全程只读
L283 ## 十、需求收集表登记（流水线 S3；本文件唯一的�

## references/13-workflow.md（11310 字符 · 72 行）
L2 # 需求一条龙流水线 —— 从拿到需求到登记闭环，ki
L6 ## 一、七站一张表（S6 只对实验类需求）
L20 ## 二、闭环清单（写在 `kit-session-notes.md` 顶部，覆�
L34 ## 三、S3 / S4 的确认话术（一次问完，别拆成三问）
L42 ## 四、脚本（`scripts/register.py`，只调本机 `lark-cli`，
L61 ## 五、输入是聊天记录 / 同事催办时（S0 / S2 / S5 都�
L68 ## 六、S5 的两份沟通物：群消息与设计同步（都只�

## references/scenario-rules.md（10355 字符 · 84 行）
L2 # 场景规则库（共建模板）
L9 ## 使用说明
L17 ## 通用（全业务线适用）
L29 ## 行情 / 交易类
L38 ## 活动 / 运营类
L46 ## 资产 / 钱包类
L55 ## 高危链路与并存模式（2026-07 实测新增）
L63 ## 延迟触发 / 弹窗 / 计时类交互（2026-07 实测，dify �
L78 ## AI agent / 内容生成管道类（persona·自动生成·机审�

## references/examples/（对齐颗粒度时只读 1 份）
### references/examples/example-copytrading-PASS.md（46392 字符 · 593 行）
L5 # 编写记录
L13 # Background & Business Values 背景与价值
L23 ## 目标用户
L33 ## 成功指标
L43 # 需求范围与边界 需求范围&风险点
L45 ## 本期包含
L55 ## 本期不包含（Out of Scope）
L64 ## 需求关联方与依赖
L79 # Overall User Scenarios 用户场景总览
L108 # User Stories 用户故事
L112 ## US1：作为看不懂盘的合约用户，我希望在�
L345 ## US2：作为跟单用户，我希望在带单员卡片�
L456 # 验收标准
L460 ## US1-R1 功能验收
L469 ## US1-R2 功能验收
L477 ## US1-R3 功能验收
L485 ## US1-R4 功能验收
L495 ## US1-R5 功能验收
L503 ## US2-R1 功能验收
L510 ## US2-R2 功能验收
L519 ## 性能验收
L528 # 非功能需求 NFR
L541 # Data Requirements 数据与埋点 **（情况A）需要�
L557 # Localisation Requirements 本地化
L578 # 【待确认】
L586 # 风险与不确定性

### references/examples/example-house-insight-tab.md（40291 字符 · 604 行）
L8 # 编写记录
L18 # Background & Business Values 背景与价值
L28 ## 目标用户
L35 ## 成功指标
L45 # 需求范围&风险点
L47 ## 本期包含
L56 ## 本期不包含（Out of Scope）
L62 ## 需求关联方与依赖
L96 # Overall User Scenarios 用户场景总览
L114 # 功能需求 User Stories 用户故事
L116 ## 模块地图
L124 ## US1: 作为用户，我希望进入行情洞察 tab 就�
L510 ## 产品设计范式字典
L518 # 验收标准
L520 ## US1-R1 功能验收
L533 # Data Requirements 数据与埋点
L545 # Localisation Requirements 本地化
L557 # PRD Quality Gates (Delete after finalised)

### references/examples/example-mini-lightweight.md（4303 字符 · 68 行）
L5 # 编写记录
L13 # Background & Business Values 背景与价值
L25 # 功能需求 User Stories 用户故事
L27 ## US1：作为夜间使用 App 的用户，我希望在个�
L56 # 验收标准
L58 ## US1-R1 功能验收
L66 # Data Requirements 数据与埋点

### references/examples/example-real-draft-concise.md（2575 字符 · 44 行）
L5 # Background & Business Values 背景与价值
L13 # Overall User Scenarios 用户场景总览
L16 # User Stories 用户故事
L17 ## US1: 作为运营，想通过设置初始默认Tab来提�
L34 # Data Requirements（原稿：埋点待处理，空表）
L35 # Localisation Requirements（原稿：一个 i18n sheet 嵌
L36 # PRD Quality Gates（定稿前删）：隐私 / 超长 / �
L40 # 粒度启示（写作时对照）

## references/checks/（18 条门禁原文，每份 1–5k 字符，标准档全读一次即可）
- check_acceptance_derivable.md（3433 字符）
- check_acceptance_testable.md（2118 字符）
- check_core_feature_specificity.md（1302 字符）
- check_crypto_alert_cooldown.md（1059 字符）
- check_crypto_data_source.md（878 字符）
- check_crypto_fund_idempotency.md（459 字符）
- check_developer_confusion.md（5050 字符）
- check_exception_coverage.md（1231 字符）
- check_external_dependency_declaration.md（1896 字符）
- check_implementation_ambiguity.md（5677 字符）
- check_internal_consistency.md（6579 字符）
- check_scope_boundary.md（1205 字符）
- check_success_metric_quantification.md（1146 字符）
- check_target_user_clarity.md（1187 字符）
- check_tracking_feasibility.md（2088 字符）
- check_tracking_goal_coverage.md（1969 字符）
- check_tracking_platform_clarity.md（1410 字符）
- check_tracking_requirement_clarity.md（1901 字符）

## references/checks-logic/（逻辑内审镜像，模式A/步骤 2.5 逐个加载）
- 00-pipeline.md（11101 字符）
- L0-structure-map.md（1082 字符）
- L1-fallback-boundary.md（4026 字符）
- L2-branch-closure.md（3579 字符）
- L3-cross-module.md（4832 字符）
- L4-testability.md（2564 字符）
- LC-merge-dedupe.md（8909 字符）
