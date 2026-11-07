# INDEX · 规则文件「标题 → 行号」（安装时自动生成，别手改；改了规则文件后由安装器或 bin/gen-index.sh 重算）

> 用法：读长文件前先看这里，`sed -n '<起>,<止>p' <文件>` 只读本步骤要的章节；分段读区间不重叠；同一会话同一区间不读第二遍。L 后面是行号，井号个数是标题层级。

## references/00-core-contract.md（6086 字符 · 63 行）
L2 # 结果契约卡（精简档入口 · 只写"必须成立的结果"，不写做法）
L6 ## 0 开场（任何模式）
L15 ## 1 访谈 / 起草
L25 ## 2 自检（发布前必跑）
L33 ## 3 发布
L41 ## 4 变更（已有稿）
L48 ## 5 建卡（伴生 jira-card-kit）
L55 ## 6 登记（S3 / S4）
L61 ## 7 采集与 token

## references/00-orchestrator.md（20000 字符 · 171 行）
L2 # PRD Authoring Kit —— 编排主流程（跨平台唯一权威）
L8 ## 第 0 步（不可跳过）
L11 ## 执行强度分档（按模型能力选，与下方「标准档 / 轻量档」是两个维度；2026-09 起）
L20 ## 开场：先收敛 → 识别模式 → 判体量
L57 ## 分档加载清单（按需惰性加载，别开场全读）
L73 ## Token 纪律（2026-09 起，两档通用——按 token 计费的模型上，回合数 × 上下文体量才是账单）
L86 ## 规则维护约定（给改 kit 的人，2026-10 起）
L94 ## 恒定规则（三模式都遵守）
L114 ## 标准流程
L150 ## 交付标准（详见 `05`）
L159 ## 降级（缺能力也别卡死）
L168 ## 别做的事

## references/01-authoring-rules.md（14769 字符 · 161 行）
L2 # Authoring Rules —— 怎么写才能过 nocode 门禁
L8 ## 0. 目标口径（先记死）
L28 ## 0.5 最小充分原则（比"过分"更重要——别被审查规则牵着走）
L53 ## 1. 元原则：为「会误判的 LLM 审查器」而写（写清楚，但别写多）
L71 ## 2. 五个 P0 阻塞项（重点防守）
L89 ## 3. 其余检查，按维度给通过写法
L91 ### 完整性（30%）
L95 ### 可量化性（30%，house 稿失分重灾区 → 重点补）
L100 ### 边界清晰度（20%）
L105 ### 技术可行性（20%）
L112 ## 4. 域规则：crypto / 交易所（本团队主场）
L124 ## 5. 埋点四检查（tracking_*）：一句话记法
L136 ## 6. 场景规则库（附加检查，命中才用）
L143 ## 7. 章节 → 检查 速查
L160 ## 8. 格式·文案·措辞

## references/02-prd-template.md（50035 字符 · 607 行）
L2 # PRD 模板 · house-style + nocode 严谨度
L87 # 编写记录
L102 # Background & Business Values 背景与价值
L115 ## 目标用户 **[nocode必填]**
L123 ## 成功指标 **[nocode必填]**
L134 # 需求范围与边界 需求范围&风险点
L136 ## 名词解释（只在有 1–3 条跨 ≥2 模块、望文会误读的词时建；0 条不建节；>3 条说明定义该下沉到使用它的模块）
L144 ## 模块地图
L158 ## 本期不包含（Out of Scope） **[nocode必填]**
L166 ## 需求关联方与依赖 **[nocode必填]**
L190 # Overall User Scenarios 用户场景总览
L200 # 功能需求 User Stories 用户故事
L227 ## 全局口径（默认不建；只有机制级定义——分页游标过期、计数 / 时间格式、轮询节奏——元素行写不下、且 ≥2 个 US-R 共用时
L235 ## 核心规则（默认不建）
L237 ### 规则 1：（主题，如 图审合流 / 处置与回退 / 频次与上限）
L245 ## US1：作为（角色），我希望（能力），以便（价值）
L247 ### US1-R1：（需求标题）
L442 ## 产品设计范式字典
L452 # 验收标准 **[nocode必填·独立成章]**
L456 ## US1-R1 功能验收
L461 ## 性能验收（有 NFR 则填）
L468 # 非功能需求 NFR（有则填，量化）
L480 # Data Requirements 数据与埋点 **[nocode必填：二选一]**
L496 # Localisation Requirements 本地化（有多语言则填）
L506 # 附录：合作方交付（派生需求）（情况 C 才有；放在本地化之后、待确认之前）
L516 # 【待确认】（可选）
L519 # 风险与不确定性（可选）
L529 # 附录：边界细则（可选：规则变体、历史兼容、极端输入；主流程不引用也能读懂）
L531 # PRD Quality Gates (Delete after finalised)
L584 ## Kit 自查清单（发布前整节删除）

## references/03-interview-playbook.md（8048 字符 · 115 行）
L2 # Interview Playbook —— 从零对话把需求聊清
L6 ## 对话总原则
L17 ## 采集顺序（命中第一个空的就问，能推断的跳过）
L33 ## 功能深挖（分档，别对每个功能都上满五问）
L49 ## 方案给产品看之前（讨论阶段同样适用，不等起草）
L60 ## 访谈期落盘：decisions.md（状态在磁盘上，不在上下文里）
L70 ## 多系统 / 多相关方需求的三件工件 + 接口模型（拿不到不起草）
L83 ## 停止判据（到这就起草，别多问）
L97 ## "直接写别问了" 快车道
L103 ## 起草 → 确认 → 发布
L109 ## 常见对话

## references/04-upgrade-draft.md（19364 字符 · 186 行）
L2 # Upgrade Existing Draft —— 把粗稿/旧PRD 升级到能过门禁
L7 ## 步骤 1 · 读入原稿（含乱输入）
L19 ## 步骤 2 · 映射到模板结构
L26 ## 步骤 3 · 补齐 nocode 缺口（house 稿通病）
L49 ## 步骤 4 · 缺口太大时，定向补问
L53 ## 步骤 5 · 改前打招呼 → 自检 → 发布
L68 ## 步骤 6 · 技术方案对齐（研发方案出来后的必做 pass）
L80 ## 需求变更流程（已有达标稿的逻辑变更）
L166 ## 红标增量回写模式（研发已开工的在用 PRD）

## references/05-self-review-gate.md（44521 字符 · 389 行）
L2 # Self-Review Gate —— 自检（两种模式）
L10 ## 模式A·只自检（纯逻辑内审 · 独立入口）
L17 ### 三条铁律（只自检模式，先记死）
L22 ### 七步流程
L47 ### 对话输出模板（固定 · 照 dify 内审报告去 T 版）
L82 ## 模式B·发布前自检（写 / 升级模式内用 · 保持两道门 · 内容不动）
L90 ## 审查器新版行为（2026-07，写作与自检都要知道）
L105 ## 自检的两栏口径（先理解）
L117 ## 步骤 0 · 结构扫描（编号步骤，不可跳过——含 AI 友好度自证 + 复杂度预判）
L179 ## 步骤 1 · 判定适用范围
L195 ## 步骤 2 · 逐条评判 18 条（① 门禁判定栏）
L231 ## 步骤 2.5 · 第二道门 · 逻辑内审（② kit 加严）
L255 ## 步骤 3 · 汇总
L263 ## 步骤 4 · 判定与修复
L283 ## 步骤 4.5 · 两视角复读（资深产品 / 资深研发各读一遍——模拟需求评审会；两档通用，模式A 同跑）
L295 ### 资深产品的九根探针（P）
L310 ### 资深研发的九根探针（D）
L325 ## 步骤 5 · 输出自检报告
L328 ### PRD 自检门禁报告（checks 原文基线 2026-07-08；审查器流程已升级、kit 口径已同步；门禁再升级请重新校准
L350 ### 🔴 报告五行硬闸（两档通用，2026-09 补——标准档同样不许口头化）
L354 ### 🔴 轻量档同样必须交付**可见的自检简报**（四行硬闸，2026-08 立 · 2026-09 加两视角一行 · 无简报 = 
L370 ## 官方引擎软集成（装了就用，没装按现状）
L379 # ② agent 逐项自判，写 results.json：{"<check_id>": {"pass": bool, "issues
L388 ## 与"升级现有草稿"配合

## references/06-lark-publish.md（21929 字符 · 215 行）
L2 # Lark Publish —— 用 lark-cli 把 PRD 写进飞书
L44 ## 步骤 0 · 发布前净化（必做，别把半成品发出去）
L49 # 从首个 H1 标题起保留正文(丢掉顶部说明块) → 删指引行/注释/内联[必填]标记 → 删 Kit 自查清单到文末
L53 # 红灯校验(用 if 而非 &&，避免 set -e 下 grep 无命中返回1 误终止脚本)
L60 ## 步骤 1（轻量档默认）· 新建文档，Markdown 导入
L68 # 返回 JSON 含 url / document_id
L77 ### 元素表富块写法（格内列表，实测）
L83 ## 步骤 2（标准档默认，高保真）· DocxXML 富块 / 插图
L90 # 定位到某段后：--selection-with-ellipsis "锚点文字片段"（可加 --before）
L98 ### 元素表「原型」格贴图（设计稿截图，实测编排）
L142 ## 步骤 3 · 迭代更新已有文档（保护人工内容，别整篇覆盖）
L167 # 改前记基线（img 形态兼容裸标签与转义两种）
L169 # … 执行你的 block 改动 …
L172 # 再核对：每个 @人 user-name 仍在、模块/小节数不变、文末无残留 AI 水印/占位
L178 ## 步骤 4 · 收尾
L188 ## 埋点子表（**可选，默认不做**；方法见 `09-tracking-gen.md §6`）
L195 ## 错误分诊（PM 友好话术）
L209 ## 提审 · PRD Bot 官方内审（发布后的正式准入入口）

## references/07-format-conventions.md（17025 字符 · 163 行）
L2 # 数字·文案·UI 格式规范（house canon）
L6 ## 一、数字格式
L20 ### 分段格式必须给完整口径（研发实测必问，缺了就是返工）
L38 ## 二、UI 词条约定（减少词条歧义）
L45 ## 二之二、产品口径 vs UED 职责（边界条：什么该写、什么一个字都别写）
L58 ## 二之三、产品行为 vs 实现机制（🔴 边界条：PRD 写行为，技术方案写机制）
L90 ## 三、措辞与排版禁忌（读起来不像 AI、也更好过审查器）
L99 ## 四、标准兜底措辞（统一，避免同义不同写触发 internal_consistency 误判）
L112 ## 五、可读性与 AI 友好排版（强制）
L131 ## 五之二、排版工具箱选型表（何时用什么·怎么不滥用）
L155 ## 六、无 lark-cli 纯文本交付格式（降级专用；与 §五/§五之二 冲突时**本节优先**）

## references/08-logic-review.md（6907 字符 · 116 行）
L2 # 逻辑内审 —— 让 PRD 逻辑经得住考验（写作侧纪律 + 第二道门自检执行器）
L8 ## 0. 范围铁律（先记死）：审产品逻辑，不审实现规格
L23 ## 0.6 强制产物：逐对象闭环矩阵（把六维从"凭印象判"变成"填表，空格即缺口"）
L44 ## 1. 六个维度（矩阵各列的落笔要点；判据以 checks-logic 镜像为准；必须有原文依据才算"覆盖"）
L54 ### A 状态覆盖
L61 ### F 边界极值
L68 ### B 交互闭环
L74 ### C 条件分支
L80 ### E 跨模块自洽（我旧版第二道门最缺的一维）
L88 ### T 可测性
L94 ## 2. 跨维度死结（单点检查看不出，必须前后串联）
L99 ## 3. 判定与从严（curator 心法：砍掉 70-80% 噪音）
L111 ## 4. 怎么用

## references/09-tracking-gen.md（15575 字符 · 143 行）
L2 # 埋点生成 —— 从 PRD 自动产出埋点表（读线上公参）
L6 ## 第 0 步：先确认要不要埋点
L9 ## 流程
L12 ## 1. 抽独立 UI 对象（不是每个字段都埋）
L28 ## 2. 埋点规范（公司口径）
L46 ## 3. 标准事件类型（6 种）与 Element vs Resource
L56 ## 4. 公参：查**线上**公参表校验（不硬编码、不编造）
L73 ## 5. 输出埋点表（10 列，过审样例校准口径）
L105 ## 5.5 三视角复核（删前、录前必做——防过抽，也防过删）
L120 ## 6. 写回 PRD（默认不建子表，满足 nocode 准入 + 单一真源）
L126 ## 7. 反编造（贯穿）
L131 ## 8. 录入公司埋点平台（产品要求时；实测 2026-09 广场一期，五轮返工的教训）

## references/10-i18n-terms.md（4341 字符 · 64 行）
L2 # 国际化词条提取 —— 从 PRD 抽出要翻译的 UI 文案
L6 ## 铁律（违反则整份词条作废）
L12 ## 什么是词条
L18 ## 常见误判（不要抽）
L30 ## 在 PRD 里怎么找
L36 ## 输出与清洗
L42 ## 交叉检查：后端已拼接文案 × 多语言（开工阻塞项）
L45 ## 喂给 Localisation 章节
L51 ## 词条表交付后的常规回合（维护 · 错误码 · 校对登记）——2026-08 广场一期实战

## references/11-usage-telemetry.md（15222 字符 · 173 行）
L2 # 使用采集（telemetry · 尽力而为，绝不打扰用户）
L8 ## 何时记录
L27 ## 五条铁律（先记死）
L34 ## 环境要求（🔴 通用条款，改命令前先过一遍）
L40 ## 🔴 写入契约（两形态通用，违反 = 宁可不写）
L50 ## 🔴 需求名 = 跨技能统一去重键（九种交付共用一个名字）
L74 ## 形态 C · 脚本（v1.8.1 起，所有平台优先用它；A / B 只在没有脚本时兜底）
L84 ## 怎么记（两种形态，先按平台选一种）
L99 ### 形态 A · Kiro / Claude / Gemini / Antigravity（一段自包含 bash，单行执行）
L101 # PRD kit 使用采集 —— ⚠️【务必单行执行】(分号连接、别换行、别把 if 拆多行) + 结尾 echo；
L102 # 🔴 只用系统自带工具：jq / timeout 一律禁用(macOS 不自带→整条静默失效)。占位符按下方注释替换后整条粘为一行跑
L104 # 占位符：<spreadsheet_token> / <sheet_id> = `python3 <KIT_ROOT>/script
L115 ### 形态 B · Codex（沙箱兼容 · 分步各自独立裸跑）
L161 ## 排查：表里没某人的记录（七个已知根因）

## references/12-context-recall.md（17802 字符 · 299 行）
L2 # 背景自采集 —— 写 PRD 前先查历史需求库
L8 ## 一、先判「改动性质」→ 定检索意图（看这次在改什么，不看走了哪个模式）
L34 ### 改动性质怎么判（机械，别凭语感）
L46 ### 检索键怎么提（三种意图各一条机械路子）
L65 ## 二、交付物：背景简报（访谈） / 检索脚注（升级 · 变更 · 回写）
L69 ### 形态一 · 背景简报（全新需求 / 访谈；≤15 行，可见）
L90 ### 形态二 · 检索脚注（新增型 / 修改型 / 抬标；贴在改动旁边，不另起一篇）
L115 ## 三、检索漏斗 L0 → L3（逐级放大，命中即停）
L117 ### L0 · 受控词表对齐（免费，0 次 API）
L129 ### L1 · 表查询（实测 ≈2–3 s/次）
L144 # ① 关键词查（默认，最省）——一个键、投影三列、限 10 行
L149 # ② 条件查（要同时按端/模块过滤时用）——contains 用 intersects
L160 ### L2 · 目录导航（拿到标题树再决定读哪节）
L170 ### L3 · 切片（只把该节读进上下文）
L190 ### 兜底 · 树浏览 → 搜索（顺序别反）
L195 ## 四、双闸（硬约束，违者退回）
L216 ## 五、平台形态（两形态同款结构，按平台选一种）
L235 ## 六、Claude Code 可选加速：派子代理精读
L248 ## 七、manifest 机制（内置 / 用户级覆盖 / 空清单）
L261 ## 八、安全边界（三句，无例外）
L267 ## 九、实测记录（2026-09-01，lark-cli 1.0.91，全程只读）
L284 ## 十、需求收集表登记（流水线 S3；本文件唯一的写动作）

## references/13-workflow.md（9356 字符 · 114 行）
L2 # 需求一条龙流水线 —— 从拿到需求到登记闭环，kit 全程包圆
L6 ## 一、八站一张表（S6 只对实验类需求）
L21 ## 二、闭环清单（写在 `kit-session-notes.md` 顶部，覆盖式维护）
L36 ## 三、S3 / S4 的确认话术（一次问完，别拆成三问）
L45 ## 四、脚本（`scripts/register.py`，只调本机 `lark-cli`，不碰任何密钥）
L66 ## 五、输入是聊天记录 / 同事催办时（S0 / S2 / S5 都会遇到）
L73 ## 六、S5 的两份沟通物：群消息与设计同步（都只交文案，不代发）
L79 ## 七、台账巡检（S7）—— 列本人未完结的需求，APP 看修复版本、其余看预期交付日期

## references/14-diagram-style.md（7989 字符 · 212 行）
L1 # PRD 画板设计系统（唯一权威；`scripts/prd_diagram.py` 实现它）
L6 ## 1 适用
L18 ## 2 色板（三色纪律，低饱和）
L41 ## 3 字号
L55 ## 4 几何
L74 ## 5 连线
L84 ## 6 布局
L90 ## 7 密度上限（沿用 `07 §五` 第 10 条；`lint` 判）
L99 ## 8 spec 范例（可直接跑；与 `references/examples/diagrams/` 下同名文件逐字一致）
L200 ## 9 工作流

## references/scenario-rules.md（4397 字符 · 84 行）
L2 # 场景规则库（共建模板）
L9 ## 使用说明
L17 ## 通用（全业务线适用）
L29 ## 行情 / 交易类
L38 ## 活动 / 运营类
L46 ## 资产 / 钱包类
L55 ## 高危链路与并存模式（2026-07 实测新增）
L63 ## 延迟触发 / 弹窗 / 计时类交互（2026-07 实测，dify 高频抓；命中必填矩阵行）
L78 ## AI agent / 内容生成管道类（persona·自动生成·机审·打分·机器人应答；命中任一即逐条过）

## references/examples/（对齐颗粒度时只读 1 份）
### references/examples/example-copytrading-PASS.md（20113 字符 · 561 行）
L5 # 编写记录
L13 # Background & Business Values 背景与价值
L23 ## 目标用户
L33 ## 成功指标
L43 # 需求范围与边界 需求范围&风险点
L45 ## 本期包含
L55 ## 本期不包含（Out of Scope）
L64 ## 需求关联方与依赖
L79 # Overall User Scenarios 用户场景总览
L89 # User Stories 用户故事
L93 ## US1：作为看不懂盘的合约用户，我希望在带单员详情页一键配置并绑定跟单，以便无需手动盯盘就能复制高手操作
L317 ## US2：作为跟单用户，我希望在带单员卡片看到可信业绩、并在跟单关键节点收到通知，以便决策跟谁跟以及知道我的跟单发
L424 # 验收标准
L428 ## US1-R1 功能验收
L437 ## US1-R2 功能验收
L445 ## US1-R3 功能验收
L453 ## US1-R4 功能验收
L463 ## US1-R5 功能验收
L471 ## US2-R1 功能验收
L478 ## US2-R2 功能验收
L487 ## 性能验收
L496 # 非功能需求 NFR
L509 # Data Requirements 数据与埋点 **（情况A）需要埋点**
L525 # Localisation Requirements 本地化
L546 # 【待确认】
L554 # 风险与不确定性

### references/examples/example-house-insight-tab.md（19719 字符 · 573 行）
L8 # 编写记录
L16 # Background & Business Values 背景与价值
L26 ## 目标用户
L33 ## 成功指标
L43 # 需求范围&风险点
L45 ## 模块地图
L53 ## 本期不包含（Out of Scope）
L59 ## 需求关联方与依赖
L85 # Overall User Scenarios 用户场景总览
L91 # 功能需求 User Stories 用户故事
L93 ## US1: 作为用户，我希望进入行情洞察 tab 就看到现在值得交易什么、为什么
L479 ## 产品设计范式字典
L487 # 验收标准
L489 ## US1-R1 功能验收
L502 # Data Requirements 数据与埋点
L514 # Localisation Requirements 本地化
L526 # PRD Quality Gates (Delete after finalised)

### references/examples/example-mini-lightweight.md（1914 字符 · 66 行）
L5 # 编写记录
L13 # Background & Business Values 背景与价值
L25 # 功能需求 User Stories 用户故事
L27 ## US1：作为夜间使用 App 的用户，我希望在个人中心切换夜间模式，以便在暗光环境下更舒适地使用
L54 # 验收标准
L56 ## US1-R1 功能验收
L64 # Data Requirements 数据与埋点

### references/examples/example-real-draft-concise.md（1235 字符 · 42 行）
L5 # Background & Business Values 背景与价值
L13 # Overall User Scenarios 用户场景总览
L16 # User Stories 用户故事
L17 ## US1: 作为运营，想通过设置初始默认Tab来提升曝光及业务量
L32 # Data Requirements（原稿：埋点待处理，空表）
L33 # Localisation Requirements（原稿：一个 i18n sheet 嵌入）
L34 # PRD Quality Gates（定稿前删）：隐私 / 超长 / 登录态 / 弱网断网 / 双端统一 / 手势 /
L38 # 粒度启示（写作时对照）

## references/checks/（18 条门禁原文，每份 1–5k 字符，标准档全读一次即可）
- check_acceptance_derivable.md（1371 字符）
- check_acceptance_testable.md（906 字符）
- check_core_feature_specificity.md（574 字符）
- check_crypto_alert_cooldown.md（475 字符）
- check_crypto_data_source.md（416 字符）
- check_crypto_fund_idempotency.md（257 字符）
- check_developer_confusion.md（2016 字符）
- check_exception_coverage.md（545 字符）
- check_external_dependency_declaration.md（834 字符）
- check_implementation_ambiguity.md（2512 字符）
- check_internal_consistency.md（2862 字符）
- check_scope_boundary.md（559 字符）
- check_success_metric_quantification.md（520 字符）
- check_target_user_clarity.md（529 字符）
- check_tracking_feasibility.md（864 字符）
- check_tracking_goal_coverage.md（843 字符）
- check_tracking_platform_clarity.md（654 字符）
- check_tracking_requirement_clarity.md（809 字符）

## references/checks-logic/（逻辑内审镜像，模式A/步骤 2.5 逐个加载）
- 00-pipeline.md（5510 字符）
- L0-structure-map.md（555 字符）
- L1-fallback-boundary.md（1836 字符）
- L2-branch-closure.md（1675 字符）
- L3-cross-module.md（2177 字符）
- L4-testability.md（1295 字符）
- LC-merge-dedupe.md（3807 字符）
