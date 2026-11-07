#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# PRD Authoring Kit · © Noah Zhan (@noah.zhan) · 二次分发/衍生须保留署名，不得标榜为自己原创创作。LICENSE / NOTICE 见根目录。
"""PRD 确定性 lint —— 把 05 步骤 0 里能机械化的检查打成 FAIL / WARN / INFO 事实表。

执行而非阅读：`python3 scripts/prd_lint.py <md>`
用法：python3 scripts/prd_lint.py <PRD.md> [--json] [--profile standard|light]
输入：kit 起草稿 `PRD-<需求名>.md`，或 `lark-cli docs +fetch --doc-format markdown` 导出的正文。

本脚本只测事实、不做判断；WARN 要模型按 05 判，FAIL 必须修；每条 FAIL 的修法指回 kit 节。
- FAIL = 确定性规则命中，必须修；WARN = 启发式命中，模型按 05 逐条判；INFO = 只给事实，抄进报告；OK = 未命中。
- 退出码：有 FAIL → 1；否则 0；参数 / 读文件错误 → 2。--json 输出与表格同构。
- `--profile light`：L01 只要求 功能需求 / 验收标准 / Data Requirements 三章，其余检查不变。
- 只用标准库、Python 3.9 兼容；不读网络、不碰飞书 / Jira。

口径细节（与 kit 规则对齐，免得误伤）：
- 稿型自动判定：首个非空行是 `<title>` 或全文含 `<whiteboard token=` → 导出稿；否则起草稿。起草稿里第一个 `# ` 之前的说明块
  （06 净化会丢掉）不参与检查；起草稿里的 ```mermaid fence 是画板载体（导入自动转），L02 只把引用块 / 缩进内的 fence 与
  「mermaid 文本供 / 源码」说明句算残留；导出稿里所有 mermaid 代码块都算残留；导出稿里的 `<画板：` 占位行（02 / 14）也算残留（2.2.0）。
- 已是模板残留的行（`> 【指引` 行、`Kit 自查清单` 节）只由 L02 报，其余检查跳过，免得一处残留报五遍。
- L03：「见待确认 #N」这类编号引用、埋点表里的【待确认】标注、UI 词条「」内的「待确认…」与 Localisation 词条表行不算裸挂。
- L08：复用标记修饰事件本身（「复用 / 沿用 / 既有…事件」「事件…复用」「（旧）/ 旧事件」）时 module 已有值沿历史值不报；
  描述里顺带一句「入口沿用 X」不算。
- L09：反引号内容含 `=` / `×` / `÷` 视为公式（05 ⑥b 豁免）。
- L10：「显著 / 交互效应…」与 LaTeX 只扫成功指标节（05 ③：别扩到全文）。
- L11 复述按 US-R 分桶（功能需求 US-R 段 + 验收章同编号小节一桶，US-R 外正文一桶），桶内同句 ≥3 才 WARN；跨模块重复只进 detail。
- L13：链接 URL（`[文字](url)`、href / src / path 属性、`<img>`、`![](路径)`）里的坐标与路径不算——07 §三 允许坐标只活在链接里，
  图片载体不是正文文字。
- 读者负荷（05 步骤 4 体量预算）：L19 正文 >12000 CJK → WARN；L22 只数验收章 `- [ ]` 那一行的 CJK（续行不计）；L23 数编写记录章
  表格数据行（「版本历史」章不算）；L24 数埋点章非表格行（含章标题）的 CJK，链接本身（锚文本 + URL）与画板源码不计、同行其余文字照计。
- L06 指针行（1.8.13 起；不再认「带出处」豁免）：只查元素表「说明」列、`#### 需求逻辑` 规则表行（首列外各格）、`#### 兜底逻辑`
  段落；判定单元 = 一条 <li>，列表外按 ；。切出的一句，每个命中单元计一处。(a) 整单元「同上」是唯一无条件命中；(b) 指向短语（见 / 按全局口径、采用全局、采用 / 沿用 H5 对应、
  详见 / 参见 X、全局…规则、沿用 / 复用 / 采用 / 按 / 依照 / 见 / 同 + 同一分句 20 字内有 PRD / § / US N / 口径 / 规则 / 链接 / http /
  现有 / 既有 / 对应状态）从动词删到下一个 ，、；。：后剩余 CJK <10 才命中——本地结论在前、出处括注的不算（链接按锚文本 + http 记号计；
  按钮 / 可见 / 同步 这类词里的字不算动词）。≥10 处 FAIL，1–9 WARN。另给迁移词子计数（后端说明格 + 表外段落里的 沿用 / 复用 / 现有 /
  既有，只计数不定级），供核对继承表行数。
- L25 跨模块规则裸名引：`### US-R` 段（到下一个 US-R / 二级 / 一级标题，验收章外；表外按行、表内按格；线框原型图 / UED设计稿槽
  与带 figma / http 链接的句不扫）里每处 见 / 按全局口径、采用全局、全局…规则、采用 / 沿用 H5 对应、见 / 按 / 采用 核心规则（「详见」
  「同上」不算）、或「采用 / 按 / 见 +
  本稿全局口径 / 核心规则节下小节标题名」→ FAIL；有全局口径 / 核心规则节 → INFO（默认不建，detail 给表行数与字数）。
- L26：说明格带沿用词、bullet ≥3，且 ≥2 条 bullet 讲沿用才报——金标里一条「复用现有组件」夹在新行为中间，正是该有的一句引用。
- L29–L35 都跳过编写记录 / 版本历史章（历史行照实保留）；L29–L31 另跳过 Data Requirements、Localisation 章与埋点表，
  L30 / L31 / L34 另跳过【待确认】章（未定项本该住那里）。原则：合法句不能卡死 05 的「lint 0 FAIL」，FAIL 只留给几乎不可能合法的写法。
- L29：「输入 / 输出参数」「返回包含」「参与 / 参考」不算；「接口文档」（关联方表交付物名）、「幂等键」（资金必填表表头）不在词表；
  「调用顺序研发按现状定」这类按现状一句引用（02 状态表指引 ✅ 写法）只记 INFO。
- L30 按「主体 + 章节」分级：取「由 X 定 / 决定 / 确定 / 评估 / 确认」「待 X 评估 / 确认」的 X——我方侧（运营 / 产品 / 研发 / 后端 / UED…）
  记 INFO 归属声明；合作方侧（UC / 客服 / 对方 / 第三方…）无取值时派生需求章 FAIL、其它章 WARN；主体不明时派生需求章 WARN、其它章 INFO。
  X 是指代（该 / 本…）、状态词或用户，或「定」属于 固定 / 选定 / 判定… 或后接 义 / 位 / 时 / 向 / 价 / 制 / 期 / 额 时不算；命中行（表内取整行）
  带取值（数字 + 单位）、写了接口形式 / 页面交互 / 接口下发、产品下放 / 让对方自己定的降 INFO；「建议」只在派生需求章内计且只记 INFO
  （行内 / 表头带依据、对标、竞品的不记）；「候选」单独不计，「候选值 / 建议每」按行内点名的一方定主体。
- L31 只认调用模式：「若…同步 / 异步 + 调用 / 返回 / 接口 / 请求 / 实现 / 处理 / 现状」「若为同步 / 异步」「同步则…异步则」「同步 / 异步现状」；
  同步发布 / 多端同步 / 数据同步 / 同步到 / 同步失败 / 同步更新 / 同步开关 / 开启…同步 是产品功能，不算。
- L32 记录表 = 表头含 类型 + 结论，或 类型 + 原因 + 记录 / 处理人；表头含 用户看到 / 兜底 / 异常类型 / 触发原因 的不算。
- L33 只认含 stateDiagram 的 mermaid 块（流程图不对账）；边数 = `-->` 条数（一行链式按条数）；不在 US 内只报边数。
  L18 同口径放宽：US 含 stateDiagram 时验收上限 = max(8, 边数 + 3)。
- L34：「方案 B / 方案二」后 12 字内标了 候选 / 供估量 / 估量 / 备选 的只记 INFO（02 允许保留另一方案细稿供估量）。
- L35：数字后接单位（倍 / 分 / USDT / BNB / 版本…）、前有「版本」、或 0.x 小数不算编号；功能清单 / 模块地图 / 名词解释 / 读者路由 /
  导览 / 关键结论小节里的表格行（目录式指路）不计。
- L36–L38 跳过编写记录 / Localisation / 待确认章。L36 只查「需求关联方与依赖」章里首列表头是 关联方 / 依赖方 / 相关方 / 团队 / 角色 /
  依赖 / 系统 的表（派生需求的 能力 / 事项 表不查），首格去空白与 团队 / 同学 / 侧 / 组 后缀后整格等于 数分 / 数据分析 / UED / 客服培训 才报，
  同表同一方只报一次。L37 全局口径行只有整格是沿用声明（按 ，；。切分句、每句都是「X 不变 / 沿用 X / 继续使用现有 X / 保持现状」）才 WARN，
  另含行为子句的只 INFO；核心规则行只 INFO；「删完无行」只数 WARN 行。L38 US 模块 = `##` / `###` 的 US 标题（排除含「验收」与验收章内的，
  有 US-R 的按 US-R 计）；引用按核心规则小节计（小节标题去「规则 N：」/ 节号，小节内各行首格也算），无小节退回按行（纯序号行跳过），
  名字 <4 字不计；≤2 个模块但核心规则节内有 stateDiagram 或 `<whiteboard` 画板时降 INFO。
- L39–L43 前置区 = 第一个 US 起点（`##` / `###` 的 US 标题或含「用户故事 N」的标题）之前的正文（含标题字，不含任一级的编写记录 /
  版本历史、待确认、Quality Gates 章与起草稿说明块）。L39（2.2.0）总数 >1,500 → WARN 并点名最大块（≤2 级标题分块），否则 INFO（计数跳过 `> 【指引` 与「（填写」占位行）。L40 ① 只有「角色与系统边界」
  WARN，分工 / 职责 / 边界 / 交接 / 合作总览只 INFO（需求范围节不算）；② 表头同时含 对应图 / 泳道 / 图 与 主责 / 交接 才 WARN，关联方类表不查。
  L41 背景章有「方案」表、表 ≥3 张或 >600 字 WARN；正文提及方案 A / B、表 2 张、400–600 字只 INFO；AB 实验不记；指引行不计。
  L43 扫验收章之前：`#` / `##` 派生需求章（附录外）INFO；`###` 派生需求小节带「事项」表才 INFO（只有能力表可留关联方节）。
- L05 把 HTML 稿的每个 `<p>` 当一段表外散文（与 markdown 段落同阈值）。L26 带出处的沿用句不计。
  L35 另数字母 + 两位数编号（只认 A/C/D/F/G/Q/R：G02 / C01 / A13）：正文引用 ≥10 处 WARN；只有引用、标题行与表格首列都没定义的编号报悬空（Jira 键先剔除）。
- L44 空槽：US-R 段内（最近的 ≤3 级标题是验收章外的 US-R；附录不查）的 `####` 槽标题（需求逻辑 / 前端说明 / 后端说明 / 兜底逻辑 /
  线框原型图 / UED设计稿）与 `#####` 板块标题后跳过空行、`---`、HTML 注释，直接是同级或更高级标题、或到文件尾 → FAIL（下级标题算内容；
  标题自带「：不涉及」正文的不算空，只有括注「（本模块无新增规则）」的算空；只有图片 / 链接行算非空）。L28 不计空槽。
- L45 后端说明列：元素表「后端说明」列非空非 / — - 的格分 句子（含要求动词且 CJK ≥8，或 07 §五 6 的指针形态：「字段 X…」「接口 /path」
  「来源：X」「由后端…」「…为空…」）/ 仅链接或名字（含 http 或 PRD / 规范 / 专项 / 词条、无动词）/ 名词短语（其余 ≤15 字）/ 其它；
  动词表不含 后 / 前 / 时 / 以 / 同 / 沿 单字。名词 + 仅链接 >50% → WARN，否则 INFO。跳过编写记录章。
- L46 编写记录列：编写记录章第一张表 ≠7 列或缺 Commented / 评论、Confirmed / 确认 → FAIL；轻量档不豁免。
- L47 模块地图：「模块地图」标题下（没有就取功能需求章第一个 US 标题前）首列带 US-R 编号的表；每行去编号 / 空白 / 首尾分隔符后的名字与
  同编号 US-R 标题逐字比、与验收章标题（任意位置去「(功能)验收(标准)」与外括号）/ 验收表首格按包含比，不同 → WARN（地图格先去 markdown
  链接语法）；列头含研发重点 / 测试重点 → WARN（1.8.13 起三列）；
  <3 列 → WARN；「本次」列 ≥4 行全同值 → INFO。
- L19（1.8.14）detail 另给读者负荷事实（不定级）：模块 CJK 中位 / 最大（`### US-R` 段，验收章内不算）· 验收章 CJK · 埋点章 CJK 与占比。
- L24（1.8.14）另数埋点章内的表：非 §5 埋点表（表头含 事件名称 + 事件属性，旧式 事件名 + 属性 同算）且非 ≤3 列 ≤8 行小表
  （09 必附的「分析问题 | 口径 | 事件与边界」三列表）→ 每张一条 INFO；FAIL / WARN 仍只看表外字数（400 / 800 不变）。
- L48 复合 bullet：元素表「说明」「后端说明」列（后端 / 格跳过；编写记录 / Data Requirements / Localisation 章不查）。单元：
  格内有列表时每条 <li> 一个（嵌套 li 各算一个），列表外的散文（去掉 <ul>/<ol> 与组名「X：」后 ≥4 CJK）另算一个；格内无列表时
  管道格带 ①–⑳（07 §六 写法，组间用「；」衔接）按圈号与「；」切、组名单元不算，其余整格一个。链接本身先剔掉；判定前剔掉引号
  「」『』“”"" 与括注（）() 整段。<li> / 整格单元里「；」「;」「。」后还有 ≥4 CJK = 复合；§六 圈号单元只判「。」。单元 ≥30 时比例 ≥35% FAIL、≥15% WARN，
  其余（含单元 <30）INFO；<30 且 ≥35% 时 detail 提示按 05 ③ 人工核。detail 另给长 bullet 数（>40 字且 ≥3 个「，」子句，不定级）。
- L49 单行板块：US-R 段内 `#####` 板块到下一个标题之间只有 1 张元素表且只有 1 个数据行 → 每处一条 INFO（永不 WARN、无图片豁免）；
  弹窗 / 真板块按 05 ⑤ 补行，非板块并进相邻表。
- L50 公司占位残留（2.1.0）：全文（起草稿说明块与【指引】/ 自查清单残留行除外，代码块照扫）出现 `{{company.` → 每处一条 FAIL，
  detail 列行号 + 占位名；修法指回 02【指引｜公司占位】（用 company_config.py get 的值替换，没有配置就进待确认）。
- L51 前置区结构（2.2.0，02 前置区六条机械上限）：只看 L39 同一前置区，FAIL，命中数 = 违规项数：a 以「本期包含」开头的标题（同时含
  「模块地图」的不算）与「模块地图」标题并存 1 项；b 名词解释节所有表数据行 + 顶层列表项合计 >3 → 1 项；c「本期不包含 / Out of Scope」节列表顶层项 >6、任一项 >30 汉字、列表之后还有段落（表外散文 /
  引用 / HTML 行，指引与占位行不算）各 1 项；d 成功指标节内所有表的数据行合计 >3、任一表「口径」列任一格 >40 汉字 各 1 项；
  e 关联方节表头含「功能」列的表：任一格条数 >2 或任一条 >20 汉字 → 1 项（<li> 各算一条，列表外 ≥4 汉字的散文另算一条，
  无列表按 <br> 切；条数再按 、/ ；切片段计，链接先剔）。汉字 = CJK 字符。
- L52 组件复用拆写（2.2.2，02 §US-R 切分粒度「例外·组件复用」）：验收章外的 US-R 段（≤3 级 US-R 标题到下一个同级或更高级标题）里元素表
  （表头含「元素」+「说明」）「元素」列归一（NFKC、去空白与 * ` _ ~、转小写）后取集合；只比文档顺序上相邻、且两段都有元素表的一对：
  重合率 = 交集 / 并集 ≥70%，或交集 ≥4 行且两边各至多多 1 行（落点命名的「区域整体」行这类同义差异）→ 每对一条 WARN，detail 如实报
  比率与各差行数；无元素表的段跳过（不跨过它去比更远的段）。只量不判，退出码不受影响；≥70% 只是疑似信号，合不合并按 02 判。
  L52 OK ≠ 没有组件复读：组件嵌在大页面元素表里（Jaccard 量不出）、或落点之间夹着无元素表的 US-R 时都不报——页面表里有 ≥3 行同名组件行时人工按组件复用查。
"""

import argparse
import bisect
import html
import json
import re
import sys
import unicodedata
from collections import Counter

# ---------------------------------------------------------------- 常量与正则

SEV_RANK = {'FAIL': 3, 'WARN': 2, 'INFO': 1}

FIX = {
    'L01': '按 02 模板补齐具名章；验收标准须 # 顶级独立成章',
    'L02': '按 06 §净化：删指引行、填完占位、删自查清单与裸 mermaid；画板占位用 prd_diagram.py publish 换成真画板块（14 §9）',
    'L03': '按 05 步骤0 ⑭ 分诊：问掉 / 自决 / 写成「由 X 新增提供 Y（待联调）」',
    'L04': '按 01 §0.5 删自律动词句，只写系统做什么',
    'L05': '按 05 步骤0 ⑫ 拆成列表或小表（段≤3 行、≤1 个「；」）',
    'L06': '每行写本地结论（这个元素在这条规则下的结果），出处只括注 / 进继承表（01 §0.5 模块自足）',
    'L07': '按 02 原型格口径 / 06 ②：原型格只放图、一格一图，缺图写进简报',
    'L08': '按 09 §5：module 填由数分定值、页面描述单值、jira_id 只一个',
    'L09': '按 07 §二 / 05 ⑥a⑥b：UI 文案用中文「」，去反引号与英文引号',
    'L10': '按 02 成功指标指引 / 05 四把闸：从简 1 行，口径写分子分母周期',
    'L11': '按 02 复述上限：同一模块内定义处 1 + 验收 1，其余删；跨模块各写一句本地结论不算复述',
    'L12': '按 10 §双向闭环：正文「」词条与词条表互相补齐，删未用词条',
    'L13': '按 07 §三：删屏号 / node-id / 本机路径，设计稿用截图或带锚文本链接',
    'L14': '按 07 §三：删 AI 味词，列表项去句尾「；」，→ 改编号步骤',
    'L15': '按 07 §四 用词表：计量单位全文定一种',
    'L16': '按 07 §五 第 10 条：一图 ≤12 节点、每泳道 ≤7 框，超了拆图',
    'L17': '按 05 步骤0 ⑨d：US 角色改业务真人，机制降为占位或删',
    'L18': '按 02 验收指引：每 US-R 一节、一行只验一件事、≤8 行',
    'L19': '超金标 1.4×：回 01 §0.5 决策点测试删常识、改规则表，不是删字',
    'L20': '按 07 §三 自造缩略语：展开成完整句或紧跟一个例子',
    'L22': '按 02 验收指引：每条 ≤60 字只写判定，构造步骤归 QA',
    'L24': '按 09 §6：表外只留平台链接与口径小表，分析方法不进 PRD',
    'L27': '按 01 §0.5：正面陈述一句一事，否定只留决策',
    'L28': '按 02 需求逻辑指引：段落改规则表 条件|行为|用户看到',
    'L25': '写本地结论，章名只作括注；默认不建全局口径 / 核心规则章（02）',
    'L26': '按 02 规则细则指引 / 05 ⑬：沿用行为一句引用，别展开',
    'L29': '按 01 §0.5 朗读测试 / 07 §二之三：接口与工程不变量移出正文',
    'L30': '按 02 派生需求指引：写取值 + 依据，不写由对方定',
    'L31': '按 02 状态表指引：写不变量，不写多套实现',
    'L32': '按 02 状态表指引：记录表必配词汇表（类型 / 结论取值 / 原因取值）',
    'L33': '按 02 验收指引：有状态图的模块每条边一条验收',
    'L34': '按 02 状态表指引：正文按推荐方案写，另一方案进待确认一行',
    'L35': '按 02 规则只住一处：引用写规则名 + 一句结论，不写编号',
    'L36': '按 02 关联方入表判据：职能支持方不入表，写进埋点表 / 指标口径',
    'L37': '按 02 全局口径指引：沿用即沉默，删行；删空整节删',
    'L38': '按 02 核心规则指引：单模块用的规则搬进该模块元素表',
    'L39': '按 02 前置区指引：先删分工 / 方案对比 / 沿用段 / 复述表；先看点名的最大块',
    'L40': '按 02 分工不写：关联方表四列 + US-R 后端说明',
    'L41': '按 02 背景章：背景 / 价值各 ≤2 句 + 信息表',
    'L42': '按 02 目标用户指引：C 端只列主要使用者',
    'L43': '按 02 情况 C：事项表与功能描述进附录，能力表可留关联方节',
    'L44': '删标题或补内容（02 需求逻辑指引：槽不许空）',
    'L45': '后端说明格 = 对后端的要求句（给什么 / 多少 / 何时 / 缺了怎么办）或 /（02 / 07 §五 11）',
    'L46': '照 02 house 七列：# / Version / Description / Author / Commented / Confirmed / Date',
    'L47': '三列、模块名与 ### 标题及验收节逐字一致（02 模块地图指引）',
    'L48': '一条 bullet 一条规则：「；」或第二句拼接的规则拆成单独 bullet；拆句变长不回炉（07 §五.1 / 05 审计轮次不扩写）',
    'L49': '单行板块：弹窗 / 真板块按 05 ⑤ 补行，非板块并进相邻表（02 板块指引）',
    'L50': '按 02【指引｜公司占位】：用 company_config.py get <键> 的值替换；无公司配置则换成可读文字「（公司配置未导入，待回填：…）」并进待确认，发布稿不许残留',
    'L51': '按 02 前置区六条机械上限：留模块地图删本期包含 · 名词解释 ≤3 · 本期不包含 ≤6 条、每条 ≤30 字、无收尾段 · 口径 ≤40 字、指标 ≤3 行 · 功能列表每方 ≤2 条、每条 ≤20 字',
    'L52': '按 02 §US-R 切分粒度「例外·组件复用」：先判说明列是否同一套规则、只是位置不同（规则不同的不合并）；是 → 一个组件 US-R（组件规则只写一次）+ 出现位置表（一处一行只写差异），落点行写「组件名 + 本处差异」'
}

NAMES = {
    'L01': '章节骨架', 'L02': '模板残留', 'L03': '待确认', 'L04': 'AI 自律动词', 'L05': '表外散文',
    'L06': '指针行（本地结论缺）', 'L07': '原型格', 'L08': '埋点表', 'L09': 'UI 文案形态', 'L10': '成功指标',
    'L11': '复述', 'L12': '词条差集', 'L13': '机器坐标 / 本机路径', 'L14': '措辞与排版', 'L15': '计量单位混用',
    'L16': '图密度', 'L17': 'US 角色红线', 'L18': '验收', 'L19': '体量', 'L20': '自造缩略语',
    'L22': '验收条长度', 'L24': '埋点章表外文字', 'L27': '否定句密度', 'L28': '需求逻辑散文', 'L25': '跨模块规则裸名引', 'L26': '沿用行为展开',
    'L29': '技术方案词（朗读测试）', 'L30': '合作方规则悬空', 'L31': '多套实现分支', 'L32': '记录表配词汇表',
    'L33': '状态图与验收对账', 'L34': '未拍板方案并存', 'L35': '裸编号回指',
    'L36': '职能支持方入关联方表', 'L37': '沿用声明占行', 'L38': '核心规则无人引用 / 规模不足',
    'L39': '前置区预算', 'L40': '分工类节与表', 'L41': '背景章装了别的', 'L42': '目标用户行数',
    'L43': '派生需求位置', 'L44': '空槽', 'L45': '后端说明列', 'L46': '编写记录列', 'L47': '模块地图',
    'L48': '复合 bullet', 'L49': '单行板块', 'L50': '公司占位残留', 'L51': '前置区结构',
    'L52': '组件复用拆写',
}

RE_HEADING = re.compile(r'^ {0,3}(#{1,6})\s+(.*?)\s*#*\s*$')
RE_FENCE_OPEN = re.compile(r'^(\s*(?:>\s*)*)(`{3,}|~{3,})\s*([A-Za-z0-9_+-]*)\s*$')
RE_FENCE_CLOSE = re.compile(r'^\s*(`{3,}|~{3,})\s*$')
RE_QUOTE_PREFIX = re.compile(r'^\s*(?:>\s*)+')
RE_PIPE_ROW = re.compile(r'^\s*(?:>\s*)*\|')
RE_PIPE_SEP = re.compile(r'^\s*\|?\s*:?-+:?\s*(?:\|\s*:?-+:?\s*)*\|?\s*$')
RE_PIPE_SPLIT = re.compile(r'(?<!\\)\|')
RE_HR = re.compile(r'^\s*(?:(?:-\s*){3,}|(?:\*\s*){3,}|(?:_\s*){3,})$')
RE_LIST = re.compile(r'^\s*(?:[-*+]|\d{1,3}[.)]|\d{1,3}、)\s+')
RE_LIST_NUM = re.compile(r'^\s*(\d{1,3})[.)、]\s+')
RE_CHECKBOX = re.compile(r'^\s*[-*+]\s+\[[ xX]\]')
RE_TAG = re.compile(r'<[^>]+>')
RE_BR = re.compile(r'<br\s*/?>', re.I)
RE_TR = re.compile(r'<tr\b[^>]*>', re.I)
RE_TR_END = re.compile(r'</tr\s*>', re.I)
RE_CELL_OPEN = re.compile(r'<(td|th)\b([^>]*)>', re.I)
RE_CELL_CLOSE_TAIL = re.compile(r'</t[dh]\s*>\s*$', re.I)
RE_ROWSPAN = re.compile(r'rowspan\s*=\s*["\']?(\d+)', re.I)
RE_COLSPAN = re.compile(r'colspan\s*=\s*["\']?(\d+)', re.I)
RE_LI = re.compile(r'<li\b[^>]*>(.*?)(?=<li\b|</li>|<ul\b|<ol\b|</ul>|</ol>|$)', re.I | re.S)
RE_IMG = re.compile(r'<img\b|!\[', re.I)
RE_CJK = re.compile(r'[一-鿿]')
RE_US_R_ID = re.compile(r'US\s*(\d+)\s*[-‐‑–—－]\s*R\s*(\d+)', re.I)
RE_US_HEADING = re.compile(r'^\s*US\s*\d+', re.I)

# L01
RE_SEC_LOG = re.compile(r'编写记录')
RE_SEC_BG = re.compile(r'Background|背景')
RE_SEC_METRIC = re.compile(r'成功指标')
RE_SEC_SCOPE = re.compile(r'需求范围')
RE_SEC_DEPS = re.compile(r'需求关联方|关联方与依赖')
RE_SEC_FR = re.compile(r'(?<!非)功能需求|核心功能')
RE_SEC_US_ONLY = re.compile(r'User\s*Stories', re.I)
RE_SEC_AC = re.compile(r'验收标准')
RE_SEC_AC_POINTER = re.compile(r'见.{0,8}验收标准')
RE_SEC_DATA = re.compile(r'Data\s*Requirements|数据与埋点|数据需求|埋点', re.I)
RE_SEC_LOC = re.compile(r'Localisation|Localization|本地化', re.I)
RE_NO_TRACKING = re.compile(r'无需埋点|无埋点|不需要埋点|不涉及埋点')
RE_SEC_PENDING = re.compile(r'待确认')
RE_SEC_KIT = re.compile(r'Kit\s*自查清单')

# L02
RE_FILL = re.compile(r'[（(]填写[：:]')
RE_GUIDE = re.compile(r'【指引')
RE_WB_PLACEHOLDER = re.compile(r'<画板[：:]')  # 02 / 14 起草稿画板占位；导出稿里残留 = 没 publish
RE_MERMAID_PROSE = re.compile(r'mermaid\s*(?:文本|源码|代码)\s*供|以下为\s*mermaid|mermaid\s*源码', re.I)

# L03
RE_PENDING = re.compile(r'待确认|待定|待对齐|待补|上线前对齐|后续确认|\bTBD\b')
RE_PENDING_REF = re.compile(r'(?:见|详见|参见)?\s*【?待确认】?\s*(?:#|＃|第)\s*\d+\s*条?')
RE_PENDING_OK_A = re.compile(r'由.{1,20}提供')
RE_PENDING_OK_B = re.compile(r'待联调')

# L04
RE_SELF = re.compile(r'不宣称|不声称|不虚报|不伪称|不冒充|不补造|宣称|虚报|伪称|补造')
RE_SELF_SOFT = re.compile(r'不猜测|不盲目|不静默')  # 否定本身可能就是规则（「不静默补发」）→ WARN 交模型判

# L06
RE_REUSE = re.compile(r'沿用|复用|现有|既有')
RE_REUSE_CLUE = re.compile(r'http|「|US\d|[A-Z]{2,}-\d+|接口|见|§|第\s*\d+\s*节|(?:H5|MVP|原|旧版?|App|Web)\s*端?\s*PRD|链接|larksuite|feishu')  # 只给 L26：带出处的沿用句不计
# L06 / L25 指针行：(a) 裸指针直接命中；(b) 指向动词 + 20 字内指向目标，去掉「动词→句末 / 分号 / 句号」后剩余 CJK <10
RE_BARE = re.compile(r'见全局口径|按全局口径|采用全局|采用 ?H5 ?对应|沿用 ?H5 ?对应')  # 裸名引片段：与其它指向短语同闸（剩余 CJK <10 才算）
RE_BARE_SOFT = re.compile(r'(?<![可常看预显少罕遇])(?:详见|参见)|全局.{0,6}规则')  # 有条件：去掉后剩余 CJK <10 才算
RE_L25_BARE = re.compile(r'见全局口径|按全局口径|采用全局|全局.{0,6}规则|采用 ?H5 ?对应|沿用 ?H5 ?对应|(?:见|按|采用)\s*[「『]?核心规则')
RE_L25_SKIP = re.compile(r'figma|\bhttps?\b', re.I)  # pointer_text 把链接换成 http 记号
RE_SAME_CELL = re.compile(r'^\s*同上\s*[。，,.]?\s*$')  # 「同上」只有整格 / 整句才算
RE_CLAUSE_END = re.compile(r'[，、；。：,;:]')  # 冒号后通常就是本地结论（「按 X 口径展示：千分位…」）
RE_POINTER_HEAD = re.compile(r'沿用|复用|采用|依照|按(?![钮键])|(?<![可常看预显少罕遇])见|(?<![不相共协如一等])同(?![步时一样意类级屏款期])')
RE_POINTER_TAIL = re.compile(r'PRD|§|US ?\d|口径|规则|链接|http|现有|既有|对应状态')
RE_POINTER_END = re.compile(r'[。；;]')
RE_A_HREF_HTTP = re.compile(r'<a\b[^>]*\bhref\s*=\s*["\']?https?:[^>]*>', re.I)
RE_MD_LINK_HTTP = re.compile(r'\[([^\]]*)\]\(\s*https?:[^)]*\)')
RE_HTML_PARA = re.compile(r'^\s*<p[\s>]', re.I)  # HTML 稿的 <p> 段落 = 表外散文
RE_LETTER_CODE = re.compile(r'(?<![A-Za-z0-9#:\-])(?!A50)([ACDFGQR])(\d{2})(?![0-9])')  # 只认 A/C/D/F/G/Q/R；色值 #E11D48、P33-C01、A65:K78、K 线 M15 / H12、A50 指数不算
RE_JIRA_KEY = re.compile(r'\b[A-Z]+-\d+|\b[A-Z]{1,3}\d+:[A-Z]{1,3}\d+|[A-Z]{1,3}\d+\s*单元格'
                         r'|(?:[MHDW]\d{2}\s*[/、,，]\s*)+[MHDW]\d{2}')  # Jira 键、表格区域 / 单元格、K 线周期列表先剔掉

# L09
RE_CODE_SPAN = re.compile(r'(`+)(.+?)\1')
RE_CODE_TAG = re.compile(r'<code>(.*?)</code>', re.I | re.S)
RE_CN_QUOTE = re.compile(r'「([^「」\n]{1,80})」')
RE_TWO_LATIN = re.compile(r'[A-Za-z]{2,}\s+[A-Za-z]{2,}')
RE_FORMULA = re.compile(r'=|×|÷')

# L10
RE_METRIC_ANALYSIS = re.compile(r'显著|交互效应|主效应|合并.{0,4}组|分别比较|样本量|检验.{0,6}(?:效应|假设|显著)')
RE_LATEX = re.compile(r'\\frac|(?<!\\)\$[^$]+?(?<!\\)\$')
RE_METRIC_KOU = re.compile(r'分母|分子|周期|/|÷')
RE_METRIC_SWITCH = re.compile(r'覆盖率.{0,6}100%|全部|所有.{0,4}100%')

# L13
RE_MD_IMAGE = re.compile(r'!\[[^\]]*\]\([^)]*\)')
RE_MD_LINK = re.compile(r'\[([^\]]*)\]\([^)]*\)')
RE_IMG_TAG = re.compile(r'<img\b[^>]*>', re.I)
RE_URL_ATTR = re.compile(r'\b(?:href|src|path|url)\s*=\s*(?:"[^"]*"|\'[^\']*\')', re.I)
RE_COORD = re.compile(r'node-id=|(?<![\d:.\-/])\d{2,4}:\d{4,7}(?![\d:])|/Users/|figma\.com/(?:file|design)/', re.I)
RE_PNG = re.compile(r'[^\s"\'()<>「」\[\]，。；、]*\.png\b', re.I)

# L14
RE_AI_WORDS = re.compile(r'值得注意的是|需要指出|综上所述|旨在|赋能|助力|一站式|无缝')
RE_ROUTE_LINE = re.compile(r'^\s*(?:>\s*)*读者路由')

# L15
RE_MS = re.compile(r'毫秒')
RE_SEC = re.compile(r'\d\s*秒')
RE_CODEPOINT = re.compile(r'码点')
RE_CODEUNIT = re.compile(r'码元')
RE_UTF16 = re.compile(r'UTF-?16', re.I)
RE_UNI_CP = re.compile(r'Unicode\s*码点', re.I)

# L16
RE_DIAGRAM_WORD = re.compile(r'画板|流程图|泳道|脑图|mindnote|<whiteboard', re.I)
RE_MM_SKIP = re.compile(r'^\s*(?:%%|classDef\b|class\b|style\b|linkStyle\b|click\b|direction\b|accTitle\b|accDescr\b|title\b|note\b)', re.I)
RE_MM_HEADER = re.compile(r'^\s*(flowchart|graph|stateDiagram(?:-v2)?|sequenceDiagram|classDiagram|erDiagram|journey|gantt|pie|mindmap|timeline|gitGraph|quadrantChart|block-beta)\b', re.I)
RE_MM_EDGE = re.compile(r'<?(?:-{2,}|={2,}|-\.+-|~{3,})[>ox]?')
RE_MM_EDGE_SPLIT = re.compile(r'\s*<?(?:-{2,}|={2,}|-\.+-|~{3,})[>ox]?\s*')
RE_MM_PIPE_LABEL = re.compile(r'\|[^|]*\|')
RE_MM_DASH_LABEL = re.compile(r'(?<![-.=])--(?![->])\s*[^-\n]*?\s*-->')
RE_MM_EQ_LABEL = re.compile(r'(?<![-.=])==(?![=>])\s*[^=\n]*?\s*==>')
RE_MM_DOT_LABEL = re.compile(r'(?<![-.])-\.(?![-.>])\s*[^.\n]*?\s*\.->')
RE_MM_QUOTED = re.compile(r'"[^"]*"')
RE_MM_SHAPES = [re.compile(p) for p in (
    r'\(\[[^\]]*\]\)', r'\[\[[^\]]*\]\]', r'\[\([^)]*\)\]', r'\(\(\([^)]*\)\)\)', r'\(\([^)]*\)\)',
    r'\{\{[^}]*\}\}', r'\[/[^\]]*[/\\]\]', r'\[\\[^\]]*[/\\]\]', r'\[[^\]]*\]', r'\([^)]*\)', r'\{[^}]*\}',
    r'(?<=[A-Za-z0-9_])>[^\]\n]*\]')]
RE_MM_ID = re.compile(r'^([A-Za-z0-9_一-鿿][\w一-鿿.-]*)')
RE_MM_SUBGRAPH = re.compile(r'^\s*subgraph\b\s*(.*)$', re.I)
RE_MM_END = re.compile(r'^\s*end\s*;?\s*$', re.I)
RE_MM_STATE_DECL = re.compile(r'^\s*state\s+(?:""\s+as\s+)?([\w一-鿿]+)', re.I)
RE_MM_SEQ_PART = re.compile(r'^\s*(?:participant|actor)\s+(.+?)(?:\s+as\s+.*)?\s*$', re.I)
RE_MM_SEQ_MSG = re.compile(r'^\s*([^\s:>+-][^:>]*?)\s*(?:-{1,2}>>|-{1,2}>|-{1,2}x|-{1,2}\))\s*[+-]?\s*([^:]+?)\s*:')
MM_KEYWORDS = {'end', 'subgraph', 'flowchart', 'graph', 'direction', 'td', 'tb', 'lr', 'rl', 'bt', 'state'}

# L17
RE_US_ROLE = re.compile(r'作为[^，,]{0,12}(研发|开发|系统|服务|接口|后端|前端)')

# L20
RE_ABBR_SUFFIX = re.compile(r'[号态序位]')
ABBR_BOUNDARY = set('的地得了着过在是和与及或并且而则若按为把被将从对向给让使由于以等每各该本此其这那个条张次种即均都也还就才只仅不没未无非可能会要需应已再又时')
ABBR_NEXT_WORD = set('位置 号码 态度 态势 序列 序幕 位于 位移 号召 号称'.split())
ABBR_UI_STATE = ('登录态', '加载态', '选中态', '禁用态', '默认态', '点击态', '展开态', '收起态', '空态', '失败态', '成功态',
                 '进行中态', '提交中态', '加载中态', '置灰态', '高亮态', '可用态', '编辑态', '预览态', '只读态', '激活态',
                 '异常态', '断网态', '错误态', '正常态', '初始态', '完成态', '审核中态')
ABBR_COMMON = set((
    '状态 形态 空态 动态 常态 姿态 心态 生态 业态 事态 终态 初态 稳态 静态 时态 表态 失态 液态 固态 体态 神态 样态 '
    '编号 序号 账号 信号 符号 型号 括号 问号 引号 逗号 句号 卡号 单号 口号 称号 记号 暗号 等号 加号 减号 冒号 分号 '
    '叹号 顿号 井号 星号 字号 年号 代号 名号 批号 挂号 '
    '排序 顺序 程序 次序 秩序 工序 时序 倒序 正序 升序 降序 有序 无序 乱序 词序 语序 '
    '单位 占位 槽位 到位 首位 末位 尾位 点位 岗位 部位 地位 方位 价位 仓位 档位 席位 数位 职位 定位 就位 归位 '
    '上位 下位 高位 低位 空位 展位 站位 卡位 坑位 机位 各位 每位 两位 几位 个位 十位 百位 千位 '
    '资源位 运营位 广告位 推荐位 小数位 千分位 百分位 分位 省略号 正负号 负号 正号 手机号 订单号 版本号'
).split())

# L23–L26
RE_SEC_HISTORY = re.compile(r'版本历史')
RE_SEC_GLOBAL = re.compile(r'全局口径')
RE_LINKISH = re.compile(r'!?\[[^\]]*\]\([^)]*\)|<a\b[^>]*>.*?</a\s*>|https?://[^\s<>()「」]+', re.I)
RE_US_R_HEAD = re.compile(r'^\s*US\s*\d+\s*[-‐‑–—－]\s*R\s*\d+', re.I)
RE_REUSE_ROW = re.compile(r'沿用|MVP|现有')

# L08 复用事件
RE_REUSE_EVENT = re.compile(r'(?:复用|沿用|既有).{0,4}事件|事件.{0,6}(?:复用|沿用|既有)|[（(]旧[）)]|旧事件')

# L29–L35
RE_TECH = re.compile(r'(?<!输)[入出]参(?![与考赛照加])|回包(?![含括装])|鉴权链路|传输重试|调用顺序|同步返回|异步返回|'
                     r'并发(?:合并|处理)|迟到(?:响应|结果)')
RE_TECH_DEFER = re.compile(r'[^，,。；;|]{0,8}?(?:按现状|沿现状|按现有|沿现有)')
RE_SEC_DERIVED = re.compile(r'派生需求|交\s*(?:[A-Z]{2,}|客服|法务|合作方)|能力表')
RE_DANGLE_YOU = re.compile(r'(?<![理自缘事原经因来])由')
RE_DANGLE_VERB = re.compile(r'决定|确定|定|评估|确认')
RE_DANGLE_WAIT = re.compile(r'待([^，,。；;、|\n]{0,6}?)(评估|确认)')
RE_DANGLE_OTHER = re.compile(r'建议每|候选值|由对方')
RE_SIDE_PARTNER = re.compile(r'UC|客服|对方|合作方|第三方|对接方|供应商|渠道|合作团队')
RE_SIDE_OURS = re.compile(r'运营|产品|研发|前端|后端|UED|设计|数分|大数据|合约侧|行情|技术|联调|前后端|客户端|服务端')
RE_DANGLE_SUGGEST = re.compile(r'建议(?!每)')  # 只在派生需求章内计
RE_DANGLE_ALLOW = re.compile(r'接口(?:形式|契约|下发)|页面交互|交互由|由数分定值')
RE_DANGLE_DELEGATE = re.compile(r'下放|让[^，,。；;|]{0,10}?自己(?:定|决定)')
RE_DANGLE_BASIS = re.compile(r'依据|对标|竞品')
RE_DANGLE_SUBJ_FP = re.compile(r'^\s*(?:该|此|本|其|这|那|待|已|未|用户|作者|本人)')
DANGLE_DING_FP = set('固选限判锁稳特一待未设指既预')  # 「X定」是形容或系统判定（固定 / 选定 / 判定…），整个「由」不算
DANGLE_DING_NEXT = set('义位时向价制期额')  # 「定义 / 定位 / 定时 / 定价…」不是「由对方定」，这个「定」不算
RE_SUPPORT_PARTY = re.compile(r'^(?:数分|数据分析|UED|客服培训)$', re.I)  # 整格匹配；法务 / 合规 / 测试 / 设计可能交付专用内容，不列
RE_PARTY_SUFFIX = re.compile(r'(?:团队|同学|侧|组)$')
RE_PARTY_HEAD = re.compile(r'关联方|依赖方|相关方|对接方|团队|角色|依赖|系统')
RE_SEC_CORE = re.compile(r'核心规则')
RE_REUSE_DECL = re.compile(r'不变|不改变|均不变|继续使用|沿用|沿现有|保持现状')
RE_REUSE_DECL_OK = re.compile(r'新增|改为')  # 另：带取值（has_value，H5 / US3 这类标识不算）的行不算沿用声明
RE_REUSE_CLAUSE = re.compile(r'^.{0,10}(?:不变|不改变|均不变|继续使用现有.{0,8}|沿用.{0,12}|保持现状)$')
RE_CLAUSE_SPLIT = re.compile(r'[，,；;。！!？?]+')
RE_CLAUSE_PUNCT = re.compile(r'[\s、：:（）()「」『』“”"\'【】\[\]·…—-]+')
RE_RULE_PREFIX = re.compile(r'^\s*(?:规则\s*\d+\s*[：:]\s*|\d+(?:\.\d+)*\s*[、.．]?\s*)')
RE_ORDINAL_CELL = re.compile(r'^[#＃]?[\d一二三四五六七八九十]+[.、)）]?$')
RE_SEC_GATES = re.compile(r'Quality\s*Gates', re.I)
RE_SEC_MULTI = re.compile(r'派生需求|合作方交付')
RE_SEC_APPX_PARTNER = re.compile(r'附录\s*[：:]?\s*合作方交付')
RE_DUTY_HEAD_WARN = re.compile(r'角色与系统边界')
RE_DUTY_HEAD_INFO = re.compile(r'分工|职责|边界|交接')  # 产品可能点名要职责边界表（10-26）：只提示并进关联方表或附录
RE_DUTY_OVERVIEW = re.compile(r'合作总览')  # 07 仍允许产品点名时画相关方合作总览
RE_RECAP_A = re.compile(r'对应图|泳道|图')
RE_RECAP_B = re.compile(r'主责|处理主责|交接')
RE_RECAP_SKIP = re.compile(r'关联方|依赖|关联系统|负责内容')  # 关联方类表（含同义列名）不算复述表
RE_US_START = re.compile(r'^\s*US\s*\d|用户故事\s*\d', re.I)
RE_DEPS_EXTRA_COL = re.compile(r'确认时点|确认负责人|协调')
RE_SCHEME_BG = re.compile(r'方案\s*[ABＡＢ](?![A-Za-z0-9])|方案[一二](?![致样般直定下些期次])|两方案')
RE_BG_STOP = re.compile(r'目标用户|成功指标')
RE_SEC_TARGET = re.compile(r'目标用户')
RE_SEC_MODMAP = re.compile(r'模块地图')
RE_SEC_INDEX = re.compile(r'功能清单|模块地图|名词解释|读者路由|导览|关键结论')  # 关键结论：他人稿开篇摘要表，同属目录式指路
RE_NUM = re.compile(r'\d+(?:\.\d+)?')
RE_UNIT_AFTER = re.compile(r'\s*(?:%|％|倍|MB|KB|GB|px|PX|ms|USDT|USDC|BNB|BTC|ETH|美元|版本|小时|分钟|分(?![别页组类配享开析支])'
                           r'|[次天日周月年个条张人字元秒项档级位])')
RE_CN_VALUE = re.compile(r'(?!二次)[两二三四五六七八九十百千万]+\s*(?:次|天|日|小时|分钟|周|个月|年|倍|人)')  # 「二次确认 / 二次重置」是形容词
RE_IMPL_IF = re.compile(r'(?:若|如果|假如)[^。；;\n]{0,10}?(?<!不)(?:同步|异步)(?:调用|返回|接口|请求|实现|处理|现状)')
RE_IMPL_AS = re.compile(r'若为(?:同步|异步)')
RE_IMPL_PAIR = re.compile(r'同步则.*?异步则|异步则.*?同步则')
RE_IMPL_HEDGE = re.compile(r'(?<!不)(?:同步|异步)现状|现状[^，,。；;|\n]{0,6}?(?:为|是)(?:同步|异步)')
RE_IMPL_FEATURE = re.compile(r'同步发布|多端同步|数据同步|同步到|同步失败|同步更新|同步开关|开启.{0,4}同步')
RE_REC_EXCLUDE = re.compile(r'用户看到|兜底|异常类型|触发原因')
RE_VOCAB = re.compile(r'词汇|结论取值|原因取值')
RE_MM_ARROW = re.compile(r'-{2,}>')
RE_SCHEME = re.compile(r'方案\s*([ABＡＢ一二])')
SCHEME_CN_FP = {'一': set('致样般直定下些旦并起同律切'), '二': set('期次')}  # 方案一致 / 方案一并 / 方案二期 不算
RE_SCHEME_CAND = re.compile(r'候选|供估量|估量|备选')
RE_AB_TEST = re.compile(r'实验组|对照组|A\s*/?\s*B\s*(?:实验|测试)|分流实验')
RE_BARE_REF = re.compile(r'(?:(?<![可预常少罕显看])见|按|参考)\s*(§?)\s*(\d+)(?:\.\d+)+'
                         r'(?!\d|\s*(?:%|％|倍|元|美元|秒|分钟|小时|天|周|个|次|条|张|位|档|MB|KB|GB|px|字|人|万|亿|USDT|USDC|BNB|BTC|ETH'
                         r'|版本|分(?![别页组类配享开析支])))')


# ---------------------------------------------------------------- 文档模型


def _in_ued_slot(lines, i):
    """最近的 #### 小节标题含 UED → 该行属于 UED 设计稿槽（模板允许写「待补」）。"""
    j = i
    while j >= 0:
        s = lines[j].strip()
        if s.startswith('#### '):
            return 'UED' in s.upper()
        if s.startswith('### ') or s.startswith('## ') or s.startswith('# '):
            return False
        j -= 1
    return False

def strip_tags(s):
    s = RE_BR.sub(' ', s)
    s = RE_TAG.sub(' ', s)
    return html.unescape(s)


def cell_text(raw):
    s = RE_BR.sub(' ', raw)
    s = re.sub(r'<li\b[^>]*>', ' ', s, flags=re.I)
    s = RE_TAG.sub(' ', s)
    s = html.unescape(s)
    return re.sub(r'\s+', ' ', s).strip()


def split_pipe(line):
    s = RE_QUOTE_PREFIX.sub('', line).strip()
    if s.startswith('|'):
        s = s[1:]
    if s.endswith('|') and not s.endswith('\\|'):
        s = s[:-1]
    return [c.strip() for c in RE_PIPE_SPLIT.split(s)]


class Doc(object):
    def __init__(self, text):
        text = text.replace('\r\n', '\n').replace('\r', '\n')
        if text.startswith('\ufeff'):
            text = text[1:]
        self.lines = text.split('\n')
        n = len(self.lines)
        self.kind = [None] * n
        self.fences = []
        self.whiteboards = []
        self.html_regions = []
        self._classify()
        self._headings()
        self._kind_of_doc()
        self._tables()
        self._residual()

    # -- 行类型
    def _classify(self):
        lines, kind = self.lines, self.kind
        fence = None
        for i, ln in enumerate(lines):
            if fence is not None:
                kind[i] = 'code'
                body = RE_QUOTE_PREFIX.sub('', ln) if fence['quoted'] else ln
                m = RE_FENCE_CLOSE.match(body)
                if m and m.group(1)[0] == fence['char'] and len(m.group(1)) >= fence['len']:
                    fence['end'] = i
                    self.fences.append(fence)
                    fence = None
                else:
                    fence['body'].append(body)
                continue
            m = RE_FENCE_OPEN.match(ln)
            if m:
                prefix = m.group(1)
                fence = {'start': i, 'end': None, 'char': m.group(2)[0], 'len': len(m.group(2)),
                         'lang': m.group(3).lower(), 'quoted': '>' in prefix,
                         'indent': len(prefix.replace('>', '').expandtabs(4)), 'body': []}
                kind[i] = 'code'
        if fence is not None:
            fence['end'] = len(lines) - 1
            self.fences.append(fence)

        depth, tstart, in_comment, wb, in_math = 0, None, False, None, False
        # 只认真正的标签（反引号里的 `<table>` 不算），且后文要有收尾标签——否则一处字面量会吞掉全文
        tag_low = [RE_CODE_SPAN.sub(' ', ln).lower() if kind[i] != 'code' else '' for i, ln in enumerate(lines)]
        last_table_close = max([i for i, x in enumerate(tag_low) if '</table' in x] or [-1])
        last_comment_close = max([i for i, x in enumerate(tag_low) if '-->' in x] or [-1])
        for i, ln in enumerate(lines):
            if kind[i] == 'code':
                continue
            low = tag_low[i]
            s = ln.strip()
            if in_comment:
                kind[i] = 'comment'
                if '-->' in ln:
                    in_comment = False
                continue
            if s.startswith('<!--'):
                kind[i] = 'comment'
                if '-->' not in s[4:] and last_comment_close > i:
                    in_comment = True
                continue
            if depth > 0 or (re.search(r'<table\b[^>]*>', low) and last_table_close >= i):
                if depth == 0:
                    tstart = i
                depth += low.count('<table') - low.count('</table')
                kind[i] = 'htable'
                if depth <= 0:
                    self.html_regions.append((tstart, i))
                    depth = 0
                continue
            if wb is not None:
                if not s or RE_HEADING.match(ln):
                    self.whiteboards.append(wb)
                    wb = None
                else:
                    kind[i] = 'wb'
                    if '</whiteboard' in ln.lower():
                        wb['body'].append(re.sub(r'</whiteboard\s*>.*$', '', ln, flags=re.I))
                        self.whiteboards.append(wb)
                        wb = None
                    else:
                        wb['body'].append(ln)
                    continue
            if re.search(r'<whiteboard\b', low):
                kind[i] = 'wb'
                tag = re.search(r'<whiteboard\b[^>]*>', ln, re.I)
                attrs = tag.group(0) if tag else ln
                wtype = re.search(r'type\s*=\s*"([^"]*)"', attrs)
                item = {'start': i, 'type': (wtype.group(1).lower() if wtype else ''),
                        'token': 'token=' in attrs, 'body': []}
                rest = ln[tag.end():] if tag else ''
                closed = attrs.rstrip().endswith('/>') or '</whiteboard' in low
                if rest.strip():
                    item['body'].append(re.sub(r'</whiteboard\s*>.*$', '', rest, flags=re.I))
                if closed or item['token']:
                    self.whiteboards.append(item)
                else:
                    wb = item
                continue
            if in_math or s.startswith('$$'):
                kind[i] = 'math'
                if ln.count('$$') % 2 == 1:
                    in_math = not in_math
                continue
        if depth > 0 and tstart is not None:
            self.html_regions.append((tstart, len(lines) - 1))
        if wb is not None:
            self.whiteboards.append(wb)

        last = None
        for i, ln in enumerate(lines):
            if kind[i] is not None:
                last = kind[i]
                continue
            s = ln.strip()
            if not s:
                kind[i] = 'blank'
                continue
            if RE_HEADING.match(ln) and not ln.lstrip().startswith('>'):
                k = 'heading'
            elif RE_PIPE_ROW.match(ln):
                k = 'ptable'
            elif RE_HR.match(ln):
                k = 'hr'
            elif ln.lstrip().startswith('>'):
                k = 'quote'
            elif RE_LIST.match(ln):
                k = 'list'
            elif last == 'list' and len(ln) - len(ln.lstrip(' \t')) >= 2:
                k = 'list'
            elif s.startswith('<'):
                k = 'html'
            else:
                k = 'prose'
            kind[i] = k
            last = k

    # -- 标题与节
    def _headings(self):
        self.headings = []
        for i, ln in enumerate(self.lines):
            if self.kind[i] != 'heading':
                continue
            m = RE_HEADING.match(ln)
            text = re.sub(r'[*`]', '', m.group(2)).strip()
            self.headings.append({'i': i, 'level': len(m.group(1)), 'text': text})
        n = len(self.lines)
        for k, h in enumerate(self.headings):
            end = n - 1
            for h2 in self.headings[k + 1:]:
                if h2['level'] <= h['level']:
                    end = h2['i'] - 1
                    break
            h['end'] = end
        self.first_h1 = next((h['i'] for h in self.headings if h['level'] == 1), None)

    def find_sections(self, regex, levels=None):
        return [h for h in self.headings if (levels is None or h['level'] in levels) and regex.search(h['text'])]

    def _kind_of_doc(self):
        first = next((ln.strip() for ln in self.lines if ln.strip()), '')
        joined = '\n'.join(self.lines)
        basis = []
        if first.lower().startswith('<title'):
            basis.append('首行 <title>')
        if re.search(r'<whiteboard\b[^>]*token=', joined, re.I):
            basis.append('画板 token')
        if re.search(r'<img\b[^>]*\bmime=', joined, re.I):
            basis.append('图片 mime')
        self.export_basis = basis
        self.is_export = bool(basis)
        n = len(self.lines)
        self.preamble = set()
        if not self.is_export and self.first_h1 is not None:
            self.preamble = set(range(0, self.first_h1))
        self.in_body = [self.kind[i] not in ('code', 'comment') and i not in self.preamble for i in range(n)]

    # -- 表格
    def _tables(self):
        self.tables = []
        lines, kind = self.lines, self.kind
        i, n = 0, len(lines)
        while i < n:
            if kind[i] == 'ptable' and self.in_body[i]:
                j = i
                while j + 1 < n and kind[j + 1] == 'ptable':
                    j += 1
                rows = []
                for r in range(i, j + 1):
                    if RE_PIPE_SEP.match(RE_QUOTE_PREFIX.sub('', lines[r])):
                        continue
                    cells = [{'raw': c, 'text': cell_text(c), 'line': r, 'origin': True, 'pieces': [(r, c)]}
                             for c in split_pipe(lines[r])]
                    rows.append({'line': r, 'cells': cells})
                if rows:
                    self.tables.append({'kind': 'pipe', 'start': i, 'end': j, 'grid': rows})
                i = j + 1
                continue
            i += 1
        for (a, b) in self.html_regions:
            if not self.in_body[a]:
                continue
            self.tables.append({'kind': 'html', 'start': a, 'end': b, 'grid': self._parse_html_table(a, b)})
        self.tables.sort(key=lambda t: t['start'])
        for t in self.tables:
            t['header'] = [c['text'] for c in t['grid'][0]['cells']] if t['grid'] else []
            t['lines'] = set(range(t['start'], t['end'] + 1))

    def _parse_html_table(self, a, b):
        region = self.lines[a:b + 1]
        text = '\n'.join(region)
        starts, pos = [], 0
        for ln in region:
            starts.append(pos)
            pos += len(ln) + 1

        def line_of(p):
            return a + bisect.bisect_right(starts, p) - 1

        trs = [m.start() for m in RE_TR.finditer(text)]
        raw_rows = []
        for k, p in enumerate(trs):
            seg = text[p:trs[k + 1] if k + 1 < len(trs) else len(text)]
            m_end = RE_TR_END.search(seg)
            if m_end:
                seg = seg[:m_end.start()]
            opens = list(RE_CELL_OPEN.finditer(seg))
            cells = []
            for j, m in enumerate(opens):
                full = seg[m.end():opens[j + 1].start() if j + 1 < len(opens) else len(seg)]
                first_line = line_of(p + m.end())
                pieces = [(first_line + k, piece) for k, piece in enumerate(full.split('\n')) if piece.strip()]
                raw = RE_CELL_CLOSE_TAIL.sub('', full.strip())
                rs = RE_ROWSPAN.search(m.group(2))
                cs = RE_COLSPAN.search(m.group(2))
                cells.append({'raw': raw, 'text': cell_text(raw), 'line': line_of(p + m.start()), 'pieces': pieces,
                              'rowspan': max(1, int(rs.group(1))) if rs else 1,
                              'colspan': max(1, int(cs.group(1))) if cs else 1})
            raw_rows.append({'line': line_of(p), 'cells': cells})
        grid, pending = [], {}
        for r in raw_rows:
            out, col, queue = [], 0, list(r['cells'])
            while queue or col in pending:
                if col in pending:
                    left, c = pending[col]
                    out.append(dict(c, origin=False))
                    if left <= 1:
                        del pending[col]
                    else:
                        pending[col] = (left - 1, c)
                    col += 1
                    continue
                c = queue.pop(0)
                for k in range(c['colspan']):
                    out.append(dict(c, origin=(k == 0)))
                    if c['rowspan'] > 1:
                        pending[col] = (c['rowspan'] - 1, c)
                    col += 1
            grid.append({'line': r['line'], 'cells': out})
        return grid

    # -- 模板残留行（只由 L02 报）
    def _residual(self):
        self.residual = set()
        for h in self.find_sections(RE_SEC_KIT):
            self.residual.update(range(h['i'], h['end'] + 1))
        for i, ln in enumerate(self.lines):
            if self.kind[i] != 'code' and re.match(r'^\s*>\s*【指引', ln):
                self.residual.add(i)

    # -- 便捷迭代
    def body(self, residual=False, tables=True, kinds=None):
        for i, ln in enumerate(self.lines):
            if not self.in_body[i]:
                continue
            if not residual and i in self.residual:
                continue
            k = self.kind[i]
            if not tables and k in ('ptable', 'htable'):
                continue
            if kinds is not None and k not in kinds:
                continue
            yield i, ln, k

    def units(self, residual=False):
        """表外按行、表内按单元格给出 (行号, 可见文本, 原文)——导出稿常把整张 HTML 表压在一行里。"""
        for i, ln, k in self.body(residual=residual, tables=False):
            yield i, strip_tags(ln), ln
        for t in self.tables:
            if not residual and t['start'] in self.residual:
                continue
            for row in t['grid']:
                for cell in row['cells']:
                    if cell.get('origin', True):
                        for line, piece in cell['pieces']:
                            yield line, cell_text(piece), piece

    def table_line_set(self, pred):
        s = set()
        for t in self.tables:
            if pred(t):
                s |= t['lines']
        return s

    def us_r_ids_outside(self, exclude):
        ids = []
        for h in self.headings:
            if h['i'] in exclude or not self.in_body[h['i']] or h['i'] in self.residual:
                continue
            m = re.match(r'^\s*US\s*(\d+)\s*[-‐‑–—－]\s*R\s*(\d+)', h['text'], re.I)
            if m:
                key = 'US%s-R%s' % (m.group(1), m.group(2))
                if key not in ids:
                    ids.append(key)
        return ids


# ---------------------------------------------------------------- 检查结果

class Check(object):
    def __init__(self, cid):
        self.id = cid
        self.name = NAMES[cid]
        self.fix = FIX[cid]
        self.findings = []
        self.detail = ''
        self.hits_override = 'auto'

    def add(self, sev, idx, msg=''):
        self.findings.append((sev, None if idx is None else idx + 1, msg))

    @property
    def status(self):
        best = 0
        for sev, _, _ in self.findings:
            best = max(best, SEV_RANK[sev])
        return {3: 'FAIL', 2: 'WARN', 1: 'INFO', 0: 'OK'}[best]

    @property
    def hits(self):
        if self.hits_override != 'auto':
            return self.hits_override
        hard = [f for f in self.findings if f[0] in ('FAIL', 'WARN')]
        return len(hard) if hard else len(self.findings)

    def lines(self):
        st = self.status
        first = sorted(set(f[1] for f in self.findings if f[1] is not None and f[0] == st))
        rest = sorted(set(f[1] for f in self.findings if f[1] is not None) - set(first))
        return first + rest

    def to_dict(self):
        return {'id': self.id, 'name': self.name, 'status': self.status, 'hits': self.hits,
                'lines': self.lines(), 'detail': self.detail, 'fix': self.fix,
                'findings': [{'severity': s, 'line': l, 'message': m} for s, l, m in self.findings]}


def short(s, n=18):
    s = re.sub(r'\s+', ' ', s).strip()
    return s if len(s) <= n else s[:n] + '…'


def vis(ln):
    return strip_tags(ln)


# ---------------------------------------------------------------- 各检查

def check_l01(doc, profile):
    c = Check('L01')
    items = [
        ('编写记录', RE_SEC_LOG, (1,)), ('背景', RE_SEC_BG, (1,)), ('成功指标', RE_SEC_METRIC, (1, 2)),
        ('需求范围与边界', RE_SEC_SCOPE, (1,)), ('需求关联方与依赖', RE_SEC_DEPS, (1, 2)),
        ('功能需求', RE_SEC_FR, (1,)), ('验收标准', RE_SEC_AC, (1,)), ('Data Requirements', RE_SEC_DATA, (1,)),
    ]
    if profile == 'light':
        items = [it for it in items if it[0] in ('功能需求', '验收标准', 'Data Requirements')]
    parts = []
    for name, rx, levels in items:
        hits = [h for h in doc.find_sections(rx, levels) if doc.in_body[h['i']]]
        if hits:
            parts.append('%s 有' % name)
            continue
        if name == '验收标准':
            deeper = [h for h in doc.find_sections(RE_SEC_AC) if h['level'] > 1 and doc.in_body[h['i']]
                      and not RE_SEC_AC_POINTER.search(h['text'])]
            if deeper:
                c.add('FAIL', deeper[0]['i'], '验收标准非顶级（%s）' % ('#' * deeper[0]['level']))
                parts.append('验收标准 非顶级')
                continue
        if name == '功能需求' and [h for h in doc.find_sections(RE_SEC_US_ONLY, (1,)) if doc.in_body[h['i']]]:
            c.add('INFO', None, '功能需求章名只有 User Stories')
            parts.append('功能需求 无（章名只有 User Stories）')
            continue
        c.add('INFO', None, '%s 无' % name)
        parts.append('%s 无' % name)
    c.detail = ' · '.join(parts)
    c.hits_override = sum(1 for p in parts if not p.endswith(' 有'))
    return c


def check_l02(doc):
    c = Check('L02')
    cnt = Counter()
    for i, ln, k in doc.body(residual=True):
        for _ in RE_FILL.finditer(ln):
            c.add('FAIL', i, '（填写：')
            cnt['（填写：'] += 1
        if RE_GUIDE.search(ln):
            c.add('FAIL', i, '【指引')
            cnt['【指引'] += len(RE_GUIDE.findall(ln))
        if k == 'heading' and RE_SEC_KIT.search(ln):
            c.add('FAIL', i, 'Kit 自查清单')
            cnt['Kit 自查清单'] += 1
        if k != 'heading' and RE_MERMAID_PROSE.search(ln):
            c.add('FAIL', i, 'mermaid 说明句')
            cnt['mermaid 说明句'] += 1
        if doc.is_export and RE_WB_PLACEHOLDER.search(ln):
            c.add('FAIL', i, '画板占位：用 prd_diagram.py publish 换成真画板块')
            cnt['画板占位'] += 1
    total_mm = 0
    for f in doc.fences:
        if f['lang'] != 'mermaid' or f['start'] in doc.preamble:
            continue
        total_mm += 1
        if doc.is_export or f['quoted'] or f['indent'] >= 2:
            c.add('FAIL', f['start'], '裸 mermaid')
            cnt['裸 mermaid'] += 1
    kind = ('导出稿（%s）' % '、'.join(doc.export_basis)) if doc.is_export else '起草稿'
    parts = ['%s %d' % (k, cnt[k]) for k in ('（填写：', '【指引', 'Kit 自查清单', '裸 mermaid', 'mermaid 说明句', '画板占位') if cnt[k]]
    note = '判为%s' % kind
    if not doc.is_export and total_mm:
        note += '，mermaid fence %d 个是画板载体不计' % total_mm
    c.detail = ('；'.join(parts) + '（%s）' % note) if parts else note
    return c


def check_l03(doc, track_lines):
    c = Check('L03')
    secs = [h for h in doc.find_sections(RE_SEC_PENDING, (1,)) if doc.in_body[h['i']]]
    if not secs:
        secs = [h for h in doc.headings if '【待确认】' in h['text'] and doc.in_body[h['i']]]
    sec_lines = set()
    detail = []
    for h in secs[:1]:
        sec_lines = set(range(h['i'], h['end'] + 1))
        nums, bullets, rows = [], 0, 0
        for i in range(h['i'] + 1, h['end'] + 1):
            if not doc.in_body[i]:
                continue
            ln = doc.lines[i]
            k = doc.kind[i]
            if k == 'list' and len(ln) - len(ln.lstrip(' \t')) < 2 and RE_LIST.match(ln):
                m = RE_LIST_NUM.match(ln)
                if m:
                    nums.append(int(m.group(1)))
                else:
                    bullets += 1
        for t in doc.tables:
            if t['start'] > h['i'] and t['end'] <= h['end']:
                rows += max(0, len(t['grid']) - 1)
        total = len(nums) + bullets + rows
        detail.append('【待确认】章 %d 条' % total)
        if total > 5:
            c.add('FAIL', h['i'], '待确认 %d 条 >5' % total)
        if bullets:
            c.add('WARN', h['i'], '未编号 %d 条' % bullets)
            detail.append('未编号 %d' % bullets)
        if nums and nums != list(range(1, len(nums) + 1)):
            c.add('WARN', h['i'], '编号不连续 %s' % nums)
            detail.append('编号不连续 %s' % ','.join(str(x) for x in nums))
    loc = set()
    for h in doc.find_sections(RE_SEC_LOC, (1,)):
        loc |= set(range(h['i'], h['end'] + 1))
    loc_rows = doc.table_line_set(lambda t: t['start'] in loc)  # Localisation 词条表行：词条原文本身可以叫「待确认…」
    bare = 0
    for i, txt, raw in doc.units():
        if i in sec_lines or i in track_lines or i in loc_rows:
            continue
        t = RE_CN_QUOTE.sub(' ', RE_PENDING_REF.sub(' ', txt))  # 「」内是 UI 词条（如页签「待确认回应」），不是裸挂
        m = RE_PENDING.search(t)
        if not m:
            continue
        if '待补' in t and _in_ued_slot(doc.lines, i):
            continue  # UED 设计稿槽允许写「待补」（02 模板占位），不算裸挂
        if RE_PENDING_OK_A.search(t) and RE_PENDING_OK_B.search(t):
            continue
        c.add('FAIL', i, m.group(0))
        bare += 1
    detail.append('章外裸挂 %d 行' % bare)
    c.detail = '；'.join(detail)
    return c


def check_l04(doc):
    c = Check('L04')
    cnt = Counter()
    for i, ln, k in doc.body():
        for m in RE_SELF.finditer(vis(ln)):
            c.add('FAIL', i, m.group(0))
        for m in RE_SELF_SOFT.finditer(vis(ln)):
            c.add('WARN', i, m.group(0))
            cnt[m.group(0)] += 1
    c.detail = ' '.join('%s×%d' % kv for kv in cnt.most_common(6))
    return c


def check_l05(doc):
    c = Check('L05')
    runs, cur = [], []
    for i in range(len(doc.lines)):
        if doc.in_body[i] and i not in doc.residual and doc.kind[i] == 'html' and RE_HTML_PARA.match(doc.lines[i]):
            if cur:
                runs.append(cur)
            runs.append([i])  # 一个 <p> 就是一段，与 markdown 段落同阈值
            cur = []
        elif doc.in_body[i] and i not in doc.residual and doc.kind[i] == 'prose':
            cur.append(i)
        else:
            if cur:
                runs.append(cur)
            cur = []
    if cur:
        runs.append(cur)
    long_n = semi_n = 0
    for run in runs:
        joined = ''.join(vis(doc.lines[i]) for i in run)
        why = []
        if len(run) >= 4:
            why.append('%d 行' % len(run))
            long_n += 1
        if joined.count('；') >= 2:
            why.append('%d 个「；」' % joined.count('；'))
            semi_n += 1
        if why:
            c.add('WARN', run[0], '、'.join(why))
    if c.findings:
        c.detail = '%d 段（≥4 行 %d · ≥2 个「；」%d）' % (len(c.findings), long_n, semi_n)
    return c


def pointer_text(raw):
    """指针判定用的可见文本：链接换成锚文本 + 「http」记号（不带 CJK），<li> / </p> 当句末。"""
    s = RE_A_HREF_HTTP.sub(' http ', raw)
    s = RE_MD_LINK_HTTP.sub(r'\1 http ', s)
    s = re.sub(r'<li\b[^>]*>|</p\s*>', '。', s, flags=re.I)
    return cell_text(s)


def _pshow(w, n=16):
    return short(re.sub(r'\s*\bhttp\b\s*', ' ', w), n)


def pointer_units(t):
    """判定单元：一条 <li>，或（列表外）按 ；。切出的一句；pointer_text 已把 <li> / </p> 换成句号。"""
    return [u for u in RE_POINTER_END.split(t) if RE_CJK.search(u)]


def pointer_hit(t):
    """一个判定单元（一条 <li> / 一句）是不是指针：返回命中片段，否则 None。
    整单元「同上」是唯一无条件命中；其余指向短语（见 / 按全局口径、采用全局、采用 / 沿用 H5 对应、详见 / 参见 X、
    全局…规则、沿用 / 复用 / 采用 / 按 / 依照 / 见 / 同 + 同一分句 20 字内的 PRD / § / 规则…）从动词删到下一个 ，、；。：
    后剩余 CJK <10 才命中——前面有本地结论、出处只作括注的不算。"""
    if RE_SAME_CELL.match(t):
        return '同上'
    spans = []

    def clause_end(p):
        e = RE_CLAUSE_END.search(t, p)
        return e.start() if e else len(t)

    for rx in (RE_BARE, RE_BARE_SOFT):
        for m in rx.finditer(t):
            spans.append((m.start(), clause_end(m.end())))
    for m in RE_POINTER_HEAD.finditer(t):
        e = clause_end(m.end())
        if RE_POINTER_TAIL.search(t[m.end():min(e, m.end() + 20)]):
            spans.append((m.start(), e))
    if not spans:
        return None
    spans.sort()
    rest, last = [], 0
    for a, b in spans:
        rest.append(t[last:max(a, last)])
        last = max(last, b)
    rest.append(t[last:])
    if len(RE_CJK.findall(''.join(rest))) < 10:
        a, b = spans[0]
        return t[a:b]
    return None


def is_element_table(t):
    hd = t['header']
    return any('元素' in h for h in hd) and any('说明' in h and '后端' not in h for h in hd)


def check_l06(doc):
    c = Check('L06')
    skip = _history_lines(doc)
    hits, cnt = [], Counter()
    for t in doc.tables:
        if t['start'] in doc.residual or t['start'] in skip:
            continue
        if is_element_table(t):
            col = find_col(t['header'], lambda h: '说明' in h and '后端' not in h)
            for row in t['grid'][1:]:
                if col >= len(row['cells']) or not row['cells'][col].get('origin', True):
                    continue
                cell = row['cells'][col]
                for u in pointer_units(pointer_text(cell['raw'])):
                    w = pointer_hit(u)
                    if w:
                        hits.append((cell['line'], w, short(u, 20)))
                        cnt['元素说明'] += 1
        elif _in_slot(doc.lines, t['start'], '需求逻辑'):
            for row in t['grid'][1:]:
                cells = [x for x in row['cells'] if x.get('origin', True)]
                cells = cells[1:] if len(cells) > 1 else cells
                for u in pointer_units('。'.join(pointer_text(x['raw']) for x in cells)):
                    w = pointer_hit(u)
                    if w:
                        hits.append((row['line'], w, short(u, 20)))
                        cnt['需求逻辑规则表'] += 1
    migr = Counter()  # 迁移词子计数（只给数，不定级）：后端说明格 + 表外段落里的 沿用 / 复用 / 现有 / 既有
    for t in doc.tables:
        if t['start'] in doc.residual or t['start'] in skip or not is_element_table(t):
            continue
        be = find_col(t['header'], lambda h: '后端' in h)
        if be is None:
            continue
        for row in t['grid'][1:]:
            if be < len(row['cells']) and row['cells'][be].get('origin', True):
                migr['后端说明'] += len(RE_REUSE.findall(row['cells'][be]['text']))
    for i, ln, k in doc.body(tables=False):
        if k not in ('prose', 'list', 'quote', 'html') or i in skip:
            continue
        migr['段落'] += len(RE_REUSE.findall(vis(ln)))
        if not _in_slot(doc.lines, i, '兜底逻辑'):
            continue
        for u in pointer_units(pointer_text(ln)):
            w = pointer_hit(u)
            if w:
                hits.append((i, w, short(u, 20)))
                cnt['兜底句'] += 1
    parts = []
    if hits:
        hits.sort(key=lambda x: x[0])
        sev = 'FAIL' if len(hits) >= 10 else 'WARN'
        for i, w, ctx in hits:  # --json 列全部命中
            c.add(sev, i, '「%s」%s' % (_pshow(w), _pshow(ctx, 20)))
        c.hits_override = len(hits)
        parts.append('%d 处只指不说（%s）：前 8 处：%s' % (
            len(hits), ' · '.join('%s %d' % kv for kv in cnt.most_common()),
            '；'.join('L%d「%s」' % (i + 1, _pshow(w)) for i, w, _ in hits[:8])))
    n_migr = sum(migr.values())
    if n_migr:
        if not hits:
            c.add('INFO', None, 'facts')
            c.hits_override = None
        parts.append('迁移词子计数（只给数）：沿用 / 复用 / 现有 / 既有 %d 处（后端说明 %d · 段落 %d）——核对继承表行数 ≥ 正文沿用处' % (
            n_migr, migr['后端说明'], migr['段落']))
    c.detail = '；'.join(parts)
    return c


def find_col(header, pred):
    for k, h in enumerate(header):
        if pred(h):
            return k
    return None


def check_l07(doc):
    c = Check('L07')
    text_n = two_n = tables = 0
    for t in doc.tables:
        col = find_col(t['header'], lambda h: '原型' in h)
        if col is None:
            continue
        tables += 1
        for row in t['grid'][1:]:
            if col >= len(row['cells']):
                continue
            cell = row['cells'][col]
            if not cell.get('origin', True):
                continue
            imgs = len(RE_IMG.findall(cell['raw']))
            if imgs >= 2:
                c.add('FAIL', cell['line'], '同格 %d 张图' % imgs)
                two_n += 1
            elif imgs == 0:
                c.add('WARN', cell['line'], short(cell['text']) or '空')
                text_n += 1
    if tables:
        c.detail = '%d 张含原型列的表：无图格 %d · 同格多图 %d' % (tables, text_n, two_n)
    return c


def is_track_table(t):
    return find_col(t['header'], lambda h: '事件属性英文' in h) is not None


def norm_key(s):
    return re.sub(r'[`\s]', '', s or '').strip()


def check_l08(doc):
    c = Check('L08')
    parts = []
    jira_vals = {}
    groups_total = groups_missing = shot_empty = shot_placeholder = reused_module = 0
    # 公共属性可在埋点表前一行声明一次（09 §5）：「公共属性：jira_id=WEB-123…」→ 表内不再逐事件要 jira_id 行
    declared_jira, declared_line = None, None
    for i, ln in enumerate(doc.lines):
        if '公共属性' in ln:
            m = re.search(r'jira_id\s*[=＝:：]\s*([A-Z][A-Z0-9]+-\d+)', ln)
            if m:
                declared_jira, declared_line = m.group(1), i
                break
    for t in doc.tables:
        if not is_track_table(t):
            continue
        hd = t['header']
        ev = find_col(hd, lambda h: '事件名称英文' in h or ('事件名' in h and '英文' in h))
        at = find_col(hd, lambda h: '事件属性英文' in h)
        va = find_col(hd, lambda h: '属性值' in h)
        sh = find_col(hd, lambda h: '截图' in h)

        def cell(row, k):
            if k is None or k >= len(row['cells']):
                return None
            return row['cells'][k]

        group = None
        groups = []
        for row in t['grid'][1:]:
            evc = cell(row, ev)
            evname = norm_key(evc['text']) if evc else ''
            if evname:
                group = {'name': evname, 'line': row['line'], 'jira': False, 'row': row}
                groups.append(group)
            attr = norm_key(cell(row, at)['text']) if cell(row, at) else ''
            valc = cell(row, va)
            val = valc['text'] if valc else ''
            if attr == 'module' and '数分定值' not in val:
                reused = any(RE_REUSE_EVENT.search(x['text']) for r in ([row] + ([group['row']] if group else []))
                             for x in r['cells'])
                if reused and val.strip() not in ('', '/', '-', '--', '—'):
                    reused_module += 1  # 复用 / 沿用既有事件：module 沿历史值（09 §2 复用对照），不报
                else:
                    c.add('FAIL', row['line'], 'module=%s' % (short(val, 10) or '空'))
            if attr == 'page_description' and re.search(r'/|、|或', val):
                c.add('FAIL', row['line'], 'page_description 多值')
            if attr == 'jira_id':
                v = norm_key(val)
                jira_vals.setdefault(v, row['line'])
                if group is not None:
                    group['jira'] = True
        for g in groups:
            groups_total += 1
            if declared_jira:
                g['jira'] = True
            if not g['name'].startswith('$') and not g['jira']:
                c.add('WARN', g['line'], '%s 缺 jira_id' % short(g['name'], 26))
                groups_missing += 1
            sc = cell(g['row'], sh)
            if sc is not None:
                st = sc['text'].strip()
                if st in ('', '/', '-', '--', '—'):
                    shot_empty += 1
                    c.add('INFO', g['line'], '截图空')
                elif not RE_IMG.search(sc['raw']):
                    shot_placeholder += 1
    if declared_jira:
        jira_vals.setdefault(declared_jira, declared_line)
        parts.append('公共属性声明 jira_id=%s' % declared_jira)
    if len(jira_vals) > 1:
        first = min(jira_vals.values())
        c.add('FAIL', first, 'jira_id %d 个值' % len(jira_vals))
        parts.append('jira_id %d 个值（%s）' % (len(jira_vals), ' / '.join(sorted(jira_vals))))
    nfail_module = sum(1 for f in c.findings if f[2].startswith('module='))
    nfail_pd = sum(1 for f in c.findings if f[2].startswith('page_description'))
    if groups_total:
        parts.insert(0, '事件 %d 条' % groups_total)
        if nfail_module:
            parts.append('module 未写由数分定值 %d' % nfail_module)
        if reused_module:
            parts.append('复用 / 沿用事件 module 沿历史值 %d（不报）' % reused_module)
        if nfail_pd:
            parts.append('page_description 多值 %d' % nfail_pd)
        if groups_missing:
            parts.append('缺 jira_id %d' % groups_missing)
        parts.append('截图空 %d（另有无图占位 %d）' % (shot_empty, shot_placeholder))
    if not groups_total:
        secs = [h for h in doc.find_sections(RE_SEC_DATA, (1,)) if doc.in_body[h['i']]]
        if secs:
            h = secs[0]
            sec_txt = ' '.join(vis(doc.lines[i]) for i in range(h['i'], h['end'] + 1) if doc.in_body[i])
            sec_tabs = [t for t in doc.tables if h['i'] < t['start'] <= h['end']]
            if RE_NO_TRACKING.search(sec_txt):
                parts.append('声明无需埋点')
            elif sec_tabs:
                c.add('INFO', sec_tabs[0]['start'], '埋点表表头非 09 §5 十列')
                parts.append('埋点表表头非 09 §5 十列（无「事件属性英文」列），未检')
            else:
                c.add('INFO', h['i'], '未找到埋点表')
                parts.append('Data Requirements 里未找到埋点表')
    c.detail = '；'.join(parts)
    return c


def pair_quotes(s, q='"'):
    pos = [m.start() for m in re.finditer(re.escape(q), s)]
    for k in range(0, len(pos) - 1, 2):
        yield s[pos[k] + 1:pos[k + 1]], pos[k]


def check_l09(doc):
    c = Check('L09')
    cnt = Counter()
    for i, ln, k in doc.body():
        for m in RE_CODE_SPAN.finditer(ln.replace('\\`', '\x00')):
            inner = m.group(2).strip()
            if inner and RE_CJK.match(inner) and not RE_FORMULA.search(inner):
                c.add('FAIL', i, '`%s`' % short(inner, 10))
                cnt['反引号中文'] += 1
        for m in RE_CODE_TAG.finditer(ln):
            inner = strip_tags(m.group(1)).strip()
            if inner and RE_CJK.match(inner) and not RE_FORMULA.search(inner):
                c.add('FAIL', i, '<code>%s' % short(inner, 10))
                cnt['反引号中文'] += 1
        t = vis(ln)
        for m in RE_CN_QUOTE.finditer(t):
            if RE_TWO_LATIN.search(m.group(1)):
                c.add('WARN', i, '「%s」' % short(m.group(1), 12))
                cnt['「」内英文'] += 1
        for inner, _ in pair_quotes(t):
            if inner and RE_CJK.match(inner):
                c.add('WARN', i, '"%s"' % short(inner, 10))
                cnt['英文引号包中文'] += 1
    c.detail = ' · '.join('%s %d' % (k, cnt[k]) for k in ('反引号中文', '「」内英文', '英文引号包中文') if cnt[k])
    return c


def check_l10(doc):
    c = Check('L10')
    secs = [h for h in doc.find_sections(RE_SEC_METRIC, (1, 2)) if doc.in_body[h['i']]]
    if not secs:
        secs = [h for h in doc.find_sections(RE_SEC_METRIC) if doc.in_body[h['i']]]
    ranges = []
    for h in secs:
        ranges.append((h['i'] + 1, h['end'], h['i']))
    if not ranges:
        fallback = [i for i, ln, k in doc.body() if k != 'heading' and '成功指标' in ln]
        ranges = [(i, i, i) for i in fallback]
        if not ranges:
            c.add('INFO', None, '未找到成功指标节')
            c.detail = '未找到成功指标节'
            return c
    parts = []
    data_rows = 0
    for (a, b, hi) in ranges:
        tabs = [t for t in doc.tables if t['start'] >= a and t['end'] <= b and t['start'] not in doc.residual]
        for t in tabs:
            rows = t['grid'][1:]
            data_rows += len(rows)
            kou = find_col(t['header'], lambda h: '口径' in h)
            name_col = find_col(t['header'], lambda h: '指标' in h)
            name_col = 0 if name_col is None else name_col
            tgt_col = find_col(t['header'], lambda h: '目标' in h)
            if kou is None:
                c.add('WARN', t['start'], '指标表无口径列')
            for row in rows:
                cells = row['cells']
                if kou is not None and kou < len(cells) and not RE_METRIC_KOU.search(cells[kou]['text']):
                    c.add('WARN', row['line'], '口径缺分子/分母/周期')
                probe = ' '.join(cells[k]['text'] for k in (name_col, tgt_col) if k is not None and k < len(cells))
                if RE_METRIC_SWITCH.search(probe):
                    c.add('WARN', row['line'], '开关型不是指标')
        if not tabs:
            txt = ' '.join(vis(doc.lines[i]) for i in range(a, b + 1) if doc.in_body[i] and i not in doc.residual)
            if txt.strip() and not RE_METRIC_KOU.search(txt):
                c.add('WARN', a if a <= b else hi, '口径缺分子/分母/周期')
            if RE_METRIC_SWITCH.search(txt):
                c.add('WARN', a if a <= b else hi, '开关型不是指标')
        for i in range(a, b + 1):
            if not doc.in_body[i] or i in doc.residual:
                continue
            ln = doc.lines[i]
            for m in RE_METRIC_ANALYSIS.finditer(vis(ln)):
                c.add('FAIL', i, '分析方案词「%s」' % m.group(0))
            if RE_LATEX.search(ln):
                c.add('INFO', i, 'LaTeX')  # 07 §五 第 8 条：比率公式一律 LaTeX，这是 house 写法，只记事实
                if re.search(r'[＝=]\s*[^\n|]{1,30}[/／÷][^\n|]{1,30}', ln) and not RE_LATEX.search(ln):
                    c.add('WARN', i, '文字式分子分母句，按 07 §五 第 8 条转 LaTeX')
    if data_rows > 2:
        c.add('WARN', ranges[0][2], '指标 %d 行，从简' % data_rows)
    parts.append('指标行 %d' % data_rows)
    for label in ('分析方案词', 'LaTeX', '口径缺', '开关型', '从简', '无口径列'):
        n = sum(1 for f in c.findings if label in f[2])
        if n:
            parts.append('%s %d' % (label, n))
    c.detail = ' · '.join(parts)
    return c


def norm_sentence(s):
    s = strip_tags(s)
    s = RE_QUOTE_PREFIX.sub('', s)
    s = re.sub(r'^\s*(?:[-*+]\s+(?:\[[ xX]\]\s*)?|\d{1,3}[.)、]\s*)', '', s)
    s = re.sub(r'[*_`\s]', '', s)
    return s.strip('，,。.；;：:！!？?、）)」』"\'（(「『')


def check_l11(doc):
    """复述上限按 US-R 段分桶：同一模块（功能需求里的 US-R 段 + 验收章里同编号小节）内同一句 ≥3 处才报；
    跨模块各写一句本地结论不算（01 §0.5 模块自足）。US-R 之外的正文合成一个桶。全文 ≥3 但无桶内命中的只进 detail。"""
    c = Check('L11')
    bucket = Counter()
    total = Counter()
    first = {}
    key = None
    for i, ln, k in doc.body(tables=False):
        if k == 'heading':
            h = next((x for x in doc.headings if x['i'] == i), None)
            if h is not None:
                m = RE_US_R_ID.search(h['text'])
                if m and h['level'] >= 2:
                    key = 'US%s-R%s' % m.groups()
                elif h['level'] <= 2:
                    key = None
            continue
        if k in ('hr', 'math', 'wb', 'html', 'blank'):
            continue
        for seg in re.split(r'[。；]|<br\s*/?>', ln):
            s = norm_sentence(seg)
            if len(s) >= 12:
                bucket[(key, s)] += 1
                total[s] += 1
                first.setdefault((key, s), i)
    rep = [(kk, s, n) for (kk, s), n in bucket.items() if n >= 3]
    rep.sort(key=lambda x: (-x[2], first[(x[0], x[1])]))
    for kk, s, n in rep:
        c.add('WARN', first[(kk, s)], '%s%s×%d' % ('%s 内 ' % kk if kk else '', short(s, 16), n))
    parts = []
    if rep:
        parts.append('%d 条（同一模块内）：%s' % (len(rep), '；'.join(
            '%s「%s」×%d' % (kk + ' ' if kk else '', short(s, 16), n) for kk, s, n in rep[:5])))
    hit_s = set(s for _, s, _ in rep)
    cross = [(s, n) for s, n in total.items() if n >= 3 and s not in hit_s]
    if cross:
        cross.sort(key=lambda x: -x[1])
        if not rep:
            c.add('INFO', None, 'facts')
            c.hits_override = None
        parts.append('全文 ≥3 处但分散在不同模块 %d 条（只计数，不报）：%s' % (
            len(cross), '；'.join('「%s」×%d' % (short(s, 12), n) for s, n in cross[:3])))
    c.detail = '；'.join(parts)
    return c


def check_l12(doc, track_lines):
    c = Check('L12')
    loc_lines = set()
    for h in doc.find_sections(RE_SEC_LOC, (1,)):
        loc_lines |= set(range(h['i'], h['end'] + 1))
    A, A_line = [], {}
    for i, ln, k in doc.body():
        if i in loc_lines or i in track_lines:
            continue
        for m in RE_CN_QUOTE.finditer(vis(ln)):
            term = m.group(1).strip()
            if term and term not in A_line:
                A.append(term)
                A_line[term] = i
    B, B_line = [], {}
    for t in doc.tables:
        if t['start'] not in loc_lines:
            continue
        for row in t['grid'][1:]:
            if not row['cells']:
                continue
            term = re.sub(r'^[「`"\s]+|[」`"\s]+$', '', row['cells'][0]['text']).strip()
            if term and term not in B_line:
                B.append(term)
                B_line[term] = row['line']
    if not loc_lines:
        if A:
            c.add('WARN', None, '无 Localisation 节')
            c.detail = '无 Localisation 节，正文「」词条 %d 个' % len(A)
        return c
    a_b = [x for x in A if x not in B_line]
    b_a = [x for x in B if x not in A_line]
    for x in a_b:
        c.add('WARN', A_line[x], 'A−B「%s」' % short(x, 12))
    for x in b_a:
        c.add('WARN', B_line[x], 'B−A「%s」' % short(x, 12))
    c.detail = 'A−B %d：%s；B−A %d：%s' % (
        len(a_b), ''.join('「%s」' % short(x, 12) for x in a_b[:20]) or '—',
        len(b_a), ''.join('「%s」' % short(x, 12) for x in b_a[:20]) or '—')
    return c


def l13_scrub(ln):
    s = RE_MD_IMAGE.sub(' ', ln)
    s = RE_MD_LINK.sub(lambda m: '[%s]' % m.group(1), s)
    s = RE_IMG_TAG.sub(' ', s)
    return RE_URL_ATTR.sub(' ', s)


def check_l13(doc):
    c = Check('L13')
    cnt = Counter()
    for i, ln, k in doc.body():
        s = l13_scrub(ln)
        for m in RE_COORD.finditer(s):
            w = m.group(0)
            label = 'node-id' if w.lower().startswith('node-id') else ('/Users/' if w.lower() == '/users/' else (
                'figma 链接' if 'figma' in w.lower() else '屏号'))
            c.add('FAIL', i, label)
            cnt[label] += 1
        for m in RE_PNG.finditer(s):
            tok = m.group(0)
            if '://' in tok or not tok[:-4]:
                continue
            c.add('FAIL', i, short(tok, 20))
            cnt['.png 路径'] += 1
    c.detail = ' · '.join('%s %d' % kv for kv in cnt.most_common())
    return c


def check_l14(doc):
    c = Check('L14')
    cnt = Counter()
    for i, ln, k in doc.body():
        t = vis(ln)
        for m in RE_AI_WORDS.finditer(t):
            c.add('WARN', i, m.group(0))
            cnt['AI 味词'] += 1
        if k == 'list' and RE_LIST.match(ln) and t.rstrip().endswith('；'):
            c.add('WARN', i, '列表项句尾「；」')
            cnt['句尾「；」'] += 1
        if '<li' in ln.lower():
            for m in RE_LI.finditer(ln):
                if strip_tags(m.group(1)).strip().endswith('；'):
                    c.add('WARN', i, '列表项句尾「；」')
                    cnt['句尾「；」'] += 1
        if k not in ('ptable', 'htable') and '→' in t and not RE_ROUTE_LINE.match(ln):
            n = t.count('→')
            c.add('WARN', i, '→×%d' % n)
            cnt['表外 →'] += n
    c.detail = ' · '.join('%s %d' % (k, cnt[k]) for k in ('AI 味词', '句尾「；」', '表外 →') if cnt[k])
    return c


def check_l15(doc):
    c = Check('L15')
    pos = {}
    for i, ln, k in doc.body():
        t = vis(ln)
        for key, rx in (('码点', RE_CODEPOINT), ('码元', RE_CODEUNIT), ('毫秒', RE_MS), ('秒', RE_SEC),
                        ('UTF-16', RE_UTF16), ('Unicode 码点', RE_UNI_CP)):
            if rx.search(t):
                pos.setdefault(key, []).append(i)
    parts = []
    for a, b in (('码点', '码元'), ('毫秒', '秒'), ('UTF-16', 'Unicode 码点')):
        if a in pos and b in pos:
            for i in (pos[a][:2] + pos[b][:2]):
                c.add('WARN', i, '%s / %s' % (a, b))
            parts.append('%s×%d 与 %s×%d 混用' % (a, len(pos[a]), b, len(pos[b])))
    c.detail = '；'.join(parts)
    return c


def mm_nodes(body_lines):
    """返回 (节点集合, {子图名: 节点数})；只数边两端与独立声明的节点。"""
    head = ''
    for ln in body_lines:
        if ln.strip() and not ln.strip().startswith('%%'):
            head = ln
            break
    mh = RE_MM_HEADER.match(head)
    dtype = mh.group(1).lower() if mh else ''
    nodes, owner, stack = [], {}, []

    def see(node):
        if not node or node.lower() in MM_KEYWORDS:
            return
        if node not in owner:
            nodes.append(node)
            owner[node] = stack[-1] if stack else None

    if dtype == 'sequencediagram':
        for ln in body_lines:
            m = RE_MM_SEQ_PART.match(ln)
            if m:
                see(m.group(1).strip())
                continue
            m = RE_MM_SEQ_MSG.match(ln)
            if m:
                see(m.group(1).strip())
                see(m.group(2).strip())
        return nodes, {}
    sub_count = Counter()
    for raw in body_lines:
        ln = raw.split('%%')[0]
        if not ln.strip() or RE_MM_HEADER.match(ln) or RE_MM_SKIP.match(ln):
            continue
        msg = RE_MM_SUBGRAPH.match(ln)
        if msg:
            name = re.sub(r'\[.*$', '', msg.group(1)).strip().strip('"') or ('subgraph%d' % len(sub_count))
            stack.append(name)
            sub_count[name] += 0
            continue
        if RE_MM_END.match(ln):
            if stack:
                stack.pop()
            continue
        s = ln.replace('[*]', ' STARTEND ')
        sd = RE_MM_STATE_DECL.match(s)
        if sd:
            see(sd.group(1))
            continue
        s = RE_MM_QUOTED.sub('""', s)
        s = re.sub(r':::[\w-]+', '', s)
        for rx in RE_MM_SHAPES:
            s = rx.sub('', s)
        s = RE_MM_PIPE_LABEL.sub(' ', s)
        s = RE_MM_DASH_LABEL.sub(' --> ', s)
        s = RE_MM_EQ_LABEL.sub(' ==> ', s)
        s = RE_MM_DOT_LABEL.sub(' -.-> ', s)
        if dtype.startswith('state'):
            s = s.split(':')[0]
        if RE_MM_EDGE.search(s):
            for tok in RE_MM_EDGE_SPLIT.split(s):
                for part in tok.split('&'):
                    m = RE_MM_ID.match(part.strip())
                    if m:
                        see(m.group(1))
        else:
            m = re.match(r'^\s*([A-Za-z0-9_一-鿿][\w一-鿿-]*)\s*;?\s*$', s)
            if m:
                see(m.group(1))
    for node in nodes:
        if owner[node] is not None:
            sub_count[owner[node]] += 1
    return nodes, dict(sub_count)


def check_l16(doc, n_us_r):
    c = Check('L16')
    sources = []
    for f in doc.fences:
        if f['lang'] == 'mermaid' and f['start'] not in doc.preamble:
            sources.append((f['start'], f['body']))
    for w in doc.whiteboards:
        if w['type'] == 'mermaid' and w['body'] and w['start'] not in doc.preamble:
            sources.append((w['start'], w['body']))
    sources.sort(key=lambda x: x[0])
    parts = []
    for start, body in sources:
        nodes, subs = mm_nodes(body)
        desc = '%d 节点' % len(nodes)
        if len(nodes) > 12:
            c.add('FAIL', start, '%d 节点 >12' % len(nodes))
        for name, n in sorted(subs.items()):
            if n > 7:
                c.add('FAIL', start, '泳道「%s」%d 节点 >7' % (short(name, 10), n))
        if subs:
            desc += '（泳道最多 %d）' % max(subs.values())
        parts.append('L%d 图 %s' % (start + 1, desc))
    if not sources and not doc.whiteboards:
        has_word = any(RE_DIAGRAM_WORD.search(ln) for i, ln, k in doc.body(residual=False))
        if not has_word and n_us_r >= 2:
            c.add('WARN', None, '缺导览图')
            parts.append('缺导览图（%d 个 US-R、无图）' % n_us_r)
    elif not sources:
        parts.append('画板 %d 个（无 mermaid 源可数）' % len(doc.whiteboards))
    c.detail = '；'.join(parts)
    return c


def check_l17(doc):
    c = Check('L17')
    for h in doc.headings:
        if h['level'] < 2 or not doc.in_body[h['i']] or h['i'] in doc.residual:
            continue
        if RE_US_HEADING.match(h['text']):
            m = RE_US_ROLE.search(h['text'])
            if m:
                c.add('FAIL', h['i'], short(m.group(0), 16))
    if c.findings:
        c.detail = '；'.join('L%d「%s」' % (f[1], f[2]) for f in c.findings[:5])
    return c


def check_l18(doc):
    c = Check('L18')
    ac = [h for h in doc.find_sections(RE_SEC_AC, (1,)) if doc.in_body[h['i']]]
    if not ac:  # 非顶级的验收章由 L01 报 FAIL，这里照样读它的 US-R 小节
        ac = [h for h in doc.find_sections(RE_SEC_AC) if doc.in_body[h['i']] and not RE_SEC_AC_POINTER.search(h['text'])][:1]
    ac_lines = set()
    ac_ids = []
    counts = []
    ac_all = set()
    for h in ac:
        ac_all |= set(range(h['i'], h['end'] + 1))
    sd_edges = [(_us_at(doc, s0, ac_all), _mm_edge_count(b)) for s0, b in _state_fences(doc)]
    raised = []
    for h in ac:
        ac_lines |= set(range(h['i'], h['end'] + 1))
        subs = [s for s in doc.headings if h['i'] < s['i'] <= h['end'] and RE_US_R_ID.search(s['text'])]
        for s in subs:
            ids = ['US%s-R%s' % m for m in RE_US_R_ID.findall(s['text'])]
            for x in ids:
                if x not in ac_ids:
                    ac_ids.append(x)
            items = []
            fallback = []
            for i in range(s['i'] + 1, s['end'] + 1):
                if not doc.in_body[i]:
                    continue
                ln = doc.lines[i]
                if RE_CHECKBOX.match(ln):
                    items.append(i)
                elif doc.kind[i] == 'list' and RE_LIST.match(ln):
                    fallback.append(i)
            if not items:
                items = fallback
                for t in doc.tables:
                    if s['i'] < t['start'] and t['end'] <= s['end']:
                        items += [r['line'] for r in t['grid'][1:]]
            label = '/'.join(ids)
            counts.append('%s %d' % (label, len(items)))
            edges = sum(e for us, e in sd_edges if us in ids or us in [x.split('-')[0] for x in ids])
            cap = max(8, edges + 3) if edges else 8  # 状态流转类模块：每条边一条验收，上限按边数
            if cap > 8:
                raised.append('%s 上限 %d' % (label, cap))
            if not items:
                c.add('FAIL', s['i'], '%s 无验收' % label)
            elif len(items) > cap:
                c.add('WARN', s['i'], '%s %d 行 >%d' % (label, len(items), cap))
            for i in items:
                t = vis(doc.lines[i])
                if t.count('；') >= 2 or t.count('且') >= 2:
                    c.add('WARN', i, '一行只验一件事')
    fr = doc.us_r_ids_outside(ac_lines)
    missing = [x for x in fr if x not in ac_ids]
    for x in missing:
        hh = next((h for h in doc.headings if h['i'] not in ac_lines and RE_US_R_ID.search(h['text'])
                   and 'US%s-R%s' % RE_US_R_ID.search(h['text']).groups() == x), None)
        c.add('FAIL', hh['i'] if hh else None, '%s 缺验收小节' % x)
    parts = []
    if not ac:
        parts.append('无验收标准章')
    if counts:
        parts.append('各节勾选项：' + ' · '.join(counts))
    if missing:
        parts.append('缺验收小节：' + ' '.join(missing))
        tab_rows = [r for h in ac for t in doc.tables if h['i'] < t['start'] <= h['end'] for r in t['grid'][1:]]
        if tab_rows:
            parts.append('验收章是表格形态（%d 行，未按 US-R 分节）：拆成 ## US-R 小节 + 勾选项' % len(tab_rows))
    one = sum(1 for f in c.findings if f[2] == '一行只验一件事')
    if one:
        parts.append('一行多事 %d' % one)
    if raised:
        parts.append('状态流转类模块按边数：' + ' · '.join(raised))
    c.detail = '；'.join(parts)
    return c, fr


def cjk_count(doc):
    n = 0
    for i, ln, k in doc.body(residual=True):
        n += len(RE_CJK.findall(strip_tags(ln)))
    return n


def check_l19(doc, cjk, n_us_r, load=None):
    c = Check('L19')
    n_tables = len(doc.tables)
    n_img = sum(len(RE_IMG.findall(ln)) for i, ln, k in doc.body(residual=True))
    c.add('INFO', None, 'facts')
    c.detail = '正文 CJK %d 字 · 表 %d · 图 %d · US-R %d' % (cjk, n_tables, n_img, n_us_r)
    load = load if load is not None else reader_load(doc, cjk)
    parts = []  # 读者负荷事实（不定级）
    if load['module_cjk_max'] is not None:
        parts.append('模块 CJK 中位 %d / 最大 %d（US-R 段）' % (load['module_cjk_median'], load['module_cjk_max']))
    parts.append('验收章 CJK %d' % load['ac_cjk'])
    parts.append('埋点章 CJK %d（占正文 %.0f%%）' % (load['tracking_cjk'], (load['tracking_cjk_ratio'] or 0) * 100))
    c.detail += ' · ' + ' · '.join(parts)
    c.hits_override = None
    if cjk > 12000:
        c.add('WARN', None, '超金标 1.4×（12k）——体量是症状：回 01 §0.5 决策点测试逐条删常识、需求逻辑改规则表，不是删字')
        c.detail += ' · >12000：超金标 1.4×，回 01 §0.5 决策点测试 / 02 规则表，不是删字'
        c.hits_override = 1
    return c


def check_l20(doc):
    c = Check('L20')
    full = '\n'.join(strip_tags(ln) for i, ln, k in doc.body())
    out = []
    seen = set()
    for i, ln, k in doc.body():
        t = strip_tags(ln)
        t = RE_CN_QUOTE.sub(' ', t)
        t = re.sub(r'"[^"\n]*"|“[^”\n]*”|『[^』\n]*』|`[^`\n]*`', ' ', t)
        for m in RE_ABBR_SUFFIX.finditer(t):
            j = m.start()
            if j < 1 or not RE_CJK.match(t[j - 1]) or t[j - 1:j + 1] in ABBR_COMMON or t[j:j + 2] in ABBR_NEXT_WORD:
                continue
            st = j
            while st - 1 >= 0 and j - (st - 1) <= 3 and RE_CJK.match(t[st - 1]) and t[st - 1] not in ABBR_BOUNDARY:
                st -= 1
            word = t[st:j + 1]
            if len(word) - 1 < 2 or word in seen or word[-3:] in ABBR_COMMON or word[-2:] in ABBR_COMMON:
                continue
            if any(word.endswith(x) for x in ABBR_UI_STATE):
                continue
            seen.add(word)
            if full.count(word) == 1:
                out.append((word, i))
    for word, i in out[:10]:
        c.add('INFO', i, word)
    if out:
        c.detail = '%d 个候选（供人判）：%s' % (len(out), ' '.join(w for w, _ in out[:10]))
    return c


def check_l22(doc):
    c = Check('L22')
    ac = [h for h in doc.find_sections(RE_SEC_AC, (1,)) if doc.in_body[h['i']]]
    if not ac:  # 与 L18 同口径：非顶级的验收章照样读
        ac = [h for h in doc.find_sections(RE_SEC_AC) if doc.in_body[h['i']] and not RE_SEC_AC_POINTER.search(h['text'])][:1]
    sizes = []
    for h in ac:
        for i in range(h['i'] + 1, h['end'] + 1):
            if not doc.in_body[i] or i in doc.residual or not RE_CHECKBOX.match(doc.lines[i]):
                continue
            n = len(RE_CJK.findall(vis(doc.lines[i])))
            sizes.append(n)
            if n > 120:
                c.add('FAIL', i, '%d 字 >120' % n)
            elif n > 60:
                c.add('WARN', i, '%d 字 >60' % n)
    if not sizes:
        c.detail = '验收章无「- [ ]」勾选项' if ac else '无验收标准章'
        return c, None
    avg, top = int(float(sum(sizes)) / len(sizes) + 0.5), max(sizes)
    over = sum(1 for n in sizes if n > 60)
    c.add('INFO', None, 'avg %d / max %d' % (avg, top))
    c.detail = '验收 %d 条 · avg %d / max %d' % (len(sizes), avg, top)
    if over:
        c.detail += ' · >60 %d 条（其中 >120 %d 条）' % (over, sum(1 for n in sizes if n > 120))
    c.hits_override = over or None
    return c, (avg, top)


def check_l23(doc):
    c = Check('L23')
    secs = [h for h in doc.find_sections(RE_SEC_LOG, (1,)) if doc.in_body[h['i']] and not RE_SEC_HISTORY.search(h['text'])]
    if not secs:
        secs = [h for h in doc.find_sections(RE_SEC_LOG) if doc.in_body[h['i']] and not RE_SEC_HISTORY.search(h['text'])]
    if not secs:
        c.detail = '无编写记录章'
        return c, None
    h = secs[0]
    tabs = [t for t in doc.tables if h['i'] < t['start'] <= h['end']]
    rows = sum(1 for t in tabs for r in t['grid'][1:] if any(x['text'] for x in r['cells']))
    if rows > 5:
        c.add('WARN', tabs[0]['start'], '%d 行 >5' % rows)
        c.detail = '编写记录 %d 行 >5：顶部只留 5 行，其余搬「版本历史」' % rows
    else:
        c.add('INFO', None, '%d 行' % rows)
        c.detail = '编写记录 %d 行' % rows + ('' if tabs else '（章内无表格）')
        c.hits_override = None
    return c, rows

RE_NEG = re.compile(r'(^|[，,；;（(\s])(不|禁止|忽略|无需|不得|不再|不自动|不允许|别)')


def _rule_sentences(doc):
    """规则句 = 元素表 / 兜底表 / 规则表格内的分句 + 需求逻辑槽内的正文分句（不含标题、不含验收章）。"""
    out = []
    for t in doc.tables:
        hd = ' '.join(h for h in t['header'])
        if not re.search(r'说明|行为|规则|兜底|口径', hd):
            continue
        for r in t['grid'][1:]:
            for cell in r['cells']:
                txt = cell['text']
                for s in re.split(r'[。；;\n]|• ', txt):
                    if len(RE_CJK.findall(s)) >= 6:
                        out.append((r['line'], s))
    for i, ln, k in doc.body():
        if k != 'prose' or not _in_slot(doc.lines, i, '需求逻辑'):
            continue
        for s in re.split(r'[。；;]', strip_tags(ln)):
            if len(RE_CJK.findall(s)) >= 6:
                out.append((i, s))
    return out


def _in_slot(lines, i, key):
    j = i
    while j >= 0:
        s = lines[j].strip()
        if s.startswith('#### '):
            return key in s
        if s.startswith('### ') or s.startswith('## ') or s.startswith('# '):
            return False
        j -= 1
    return False


def check_l27(doc):
    c = Check('L27')
    sents = _rule_sentences(doc)
    if not sents:
        c.detail = '无规则句'
        return c
    neg = [(i, s) for i, s in sents if RE_NEG.search(s)]
    share = len(neg) / float(len(sents))
    c.detail = '规则句 %d · 否定句 %d（%.0f%%）' % (len(sents), len(neg), share * 100)
    if len(sents) >= 20 and share > 0.5:
        for i, s in neg[:5]:
            c.add('WARN', i, short(s, 24))
        c.hits_override = len(neg)
        c.detail += '：否定堆叠，按 01 §0.5 改正面陈述、否定只留决策'
    else:
        c.add('INFO', None, 'facts')
        c.hits_override = None
    return c


def check_l28(doc):
    c = Check('L28')
    slots = []
    empty = set(h['i'] for h in _empty_slots(doc))
    for i, ln in enumerate(doc.lines):
        if ln.strip().startswith('#### ') and '需求逻辑' in ln and i not in empty:
            j = i + 1
            while j < len(doc.lines) and not re.match(r'^#{1,4} ', doc.lines[j]):
                j += 1
            prose = [k for k in range(i + 1, j) if doc.in_body[k] and doc.kind[k] == 'prose' and len(RE_CJK.findall(doc.lines[k])) >= 6]
            slots.append((i, len(prose)))
    n_empty = sum(1 for i in empty if '需求逻辑' in doc.lines[i])
    if not slots:
        c.detail = '无需求逻辑槽' + ('（空槽 %d 个由 L44 报）' % n_empty if n_empty else '')
        return c
    heavy = [(i, n) for i, n in slots if n > 8]
    c.detail = '需求逻辑槽 %d 个%s · 表外正文行 max %d' % (len(slots), '（另空槽 %d 个由 L44 报）' % n_empty if n_empty else '',
                                                    max(n for _, n in slots))
    if heavy:
        for i, n in heavy:
            c.add('WARN', i, '表外正文 %d 行' % n)
        c.detail += '：段落改规则表（02 需求逻辑指引）'
    else:
        c.add('INFO', None, 'facts')
        c.hits_override = None
    return c


def check_l24(doc):
    c = Check('L24')
    secs = [h for h in doc.find_sections(RE_SEC_DATA, (1,)) if doc.in_body[h['i']]]
    secs.sort(key=lambda h: (not re.search(r'Data\s*Requirements', h['text'], re.I), h['i']))
    if not secs:
        c.detail = '无 Data Requirements 章'
        return c, None
    h = secs[0]
    total, per = 0, []
    for i in range(h['i'], h['end'] + 1):
        if not doc.in_body[i] or i in doc.residual or doc.kind[i] not in ('heading', 'prose', 'list', 'quote', 'html'):
            continue
        n = len(RE_CJK.findall(strip_tags(RE_LINKISH.sub(' ', doc.lines[i]))))
        if n:
            total += n
            per.append((n, i))
    per.sort(key=lambda x: (-x[0], x[1]))
    longest = '、'.join('L%d %d 字' % (i + 1, n) for n, i in per[:3])
    tab_info = []  # 1.8.14：表内只给事实——非埋点表 INFO（09 必附的「分析问题 | 口径 | 事件与边界」三列小表不算）
    for t in doc.tables:
        if not (h['i'] < t['start'] <= h['end']) or t['start'] in doc.residual or not t['grid']:
            continue
        hd = t['header']
        rows = t['grid'][1:]
        n_cjk = sum(len(RE_CJK.findall(x['text'])) for r in rows for x in r['cells'] if x.get('origin', True))
        # §5 埋点表：表头含 事件名称 + 事件属性；旧式「事件名 / 属性」列名同算（金标 copytrading）
        tracking = (any('事件名' in x for x in hd) and any('属性' in x for x in hd)) or is_track_table(t)
        if tracking or (len(hd) <= 3 and len(rows) <= 8):
            continue
        tab_info.append((t['start'], len(hd), len(rows), n_cjk))
    if total > 800:
        c.add('FAIL', h['i'], '表外 %d 字 >800：分析方法不进 PRD' % total)
        c.detail = '表外 %d 字 >800：分析方法不进 PRD（最长 %s）' % (total, longest)
    elif total > 400:
        c.add('WARN', h['i'], '表外 %d 字 >400' % total)
        c.detail = '表外 %d 字 >400（最长 %s）' % (total, longest)
    else:
        c.add('INFO', None, '表外 %d 字' % total)
        c.detail = '表外 %d 字' % total
        c.hits_override = None
    for i, ncol, nr, nc in tab_info:
        c.add('INFO', i, '埋点章非埋点表：%d 列 %d 行 %d 字（09 §6）' % (ncol, nr, nc))
    if tab_info:
        c.detail += '；埋点章非埋点表 %d 张（%s）' % (len(tab_info), '、'.join('L%d %d 列 %d 行 %d 字' % (i + 1, a, b, d)
                                                                  for i, a, b, d in tab_info))
    return c, total


def _rule_secs(doc):
    """全局口径 / 核心规则节（编写记录章除外）。"""
    hist = _history_lines(doc)
    return [h for h in doc.headings if doc.in_body[h['i']] and h['i'] not in doc.residual and h['i'] not in hist
            and (RE_SEC_GLOBAL.search(h['text']) or RE_SEC_CORE.search(h['text']))]


def check_l25(doc):
    c = Check('L25')
    ac_lines = set()
    for h in doc.find_sections(RE_SEC_AC, (1,)):
        ac_lines |= set(range(h['i'], h['end'] + 1))
    heads = doc.headings
    segs = []
    for k, h in enumerate(heads):
        if (h['level'] != 3 or not RE_US_R_HEAD.match(h['text']) or not doc.in_body[h['i']]
                or h['i'] in doc.residual or h['i'] in ac_lines):
            continue
        end = len(doc.lines) - 1
        for h2 in heads[k + 1:]:
            if h2['level'] <= 2 or RE_US_R_HEAD.match(h2['text']):
                end = h2['i'] - 1
                break
        segs.append(set(i for i in range(h['i'], end + 1)
                        if doc.in_body[i] and i not in doc.residual and doc.kind[i] != 'wb'))
    seg_lines = set().union(*segs) if segs else set()
    secs = _rule_secs(doc)
    names = []
    for h in secs:  # 本稿全局口径 / 核心规则节下的小节标题（动态拼正则）
        subs = [s for s in heads if h['i'] < s['i'] <= h['end'] and doc.in_body[s['i']]]
        if subs:
            top = min(s['level'] for s in subs)
            for s in subs:
                nm = RE_RULE_PREFIX.sub('', s['text']).strip()
                if s['level'] == top and len(nm) >= 2 and nm not in names:
                    names.append(nm)
    rx_name = (re.compile(r'(?:采用|按|见)\s*[「『]?(?:%s)' % '|'.join(re.escape(x) for x in sorted(names, key=len, reverse=True)))
               if names else None)
    bare = []
    for i, _, raw in doc.units():  # 表外按行、表内按格再按句（<li> / 。；）切；线框 / UED 槽与带 figma / http 链接的句不扫
        if i not in seg_lines or _in_slot(doc.lines, i, '线框') or _in_slot(doc.lines, i, 'UED'):
            continue
        spans = []
        for t in RE_POINTER_END.split(pointer_text(raw)):
            if RE_L25_SKIP.search(t):
                continue
            spans += [(m.start(), m.end(), m.group(0)) for m in RE_L25_BARE.finditer(t)]
            if rx_name is not None:
                spans += [(m.start(), m.end(), m.group(0)) for m in rx_name.finditer(t)]
        last = -1
        for s0, e0, w in sorted(spans):  # 同句内位置可比；跨句不会重叠
            if s0 < last:
                continue  # 同一处被两条正则命中只算一次
            last = e0
            bare.append((i, w))
    bare.sort(key=lambda x: x[0])
    for i, w in bare:
        c.add('FAIL', i, '「%s」' % short(w, 16))
    parts = []
    if bare:
        parts.append('裸名引 %d 处（前 5：%s）' % (len(bare), '；'.join('L%d「%s」' % (i + 1, short(w, 12)) for i, w in bare[:5])))
    elif not segs:
        parts.append('无「### US-R」段')
    for h in secs:
        if any(x['i'] < h['i'] <= x['end'] for x in secs if x is not h):
            continue  # 嵌套的只报外层
        rows = sum(max(0, len(t['grid']) - 1) for t in doc.tables if h['i'] < t['start'] <= h['end'])
        cjk = sum(_cjk_of(doc, i) for i in range(h['i'], h['end'] + 1) if doc.in_body[i])
        c.add('INFO', h['i'], '「%s」默认不建；每行须在 ≥1 模块元素行有本地结论（05 ④）' % short(h['text'], 10))
        parts.append('「%s」%d 表行 · %d 字：默认不建；每行须在 ≥1 模块元素行有本地结论（05 ④）' % (short(h['text'], 10), rows, cjk))
    if bare:
        c.hits_override = len(bare)
    elif c.findings:
        c.hits_override = None
    c.detail = '；'.join(parts)
    return c


def check_l26(doc):
    c = Check('L26')
    parts = []
    for t in doc.tables:
        hd = t['header']
        if not any('原型' in h or '元素' in h for h in hd):
            continue
        cols = [k for k, h in enumerate(hd) if '说明' in h] or [k for k, h in enumerate(hd) if '原型' not in h and '元素' not in h]
        el = find_col(hd, lambda h: '元素' in h)
        for row in t['grid'][1:]:
            for k in cols:
                if k >= len(row['cells']):
                    continue
                cell = row['cells'][k]
                if not cell.get('origin', True) or not RE_REUSE_ROW.search(cell['text']):
                    continue
                items = [strip_tags(m.group(1)) for m in RE_LI.finditer(cell['raw'])]
                if len(items) < cell['text'].count('•'):
                    items = cell['text'].split('•')[1:]
                reuse = sum(1 for x in items if RE_REUSE_ROW.search(x) and not RE_REUSE_CLUE.search(x))  # 带出处的沿用句不计
                if len(items) < 3 or reuse < 2:
                    continue
                name = short(row['cells'][el]['text'], 12) if el is not None and el < len(row['cells']) else ''
                desc = '%s%d 条（含沿用 %d 条）' % ('「%s」' % name if name else 'L%d ' % (cell['line'] + 1), len(items), reuse)
                c.add('WARN', cell['line'], desc)
                parts.append(desc)
    if parts:
        c.detail = '%d 格：%s：沿用的一句引用，别展开' % (len(parts), '、'.join(parts[:5]))
    return c


# ---------------------------------------------------------------- L29–L35（详略 / 悬空规则 / 多实现 / 词汇表 / 状态图对账 / 方案并存 / 裸编号）

def _chap_lines(doc, rx, levels=(1,)):
    s = set()
    for h in doc.find_sections(rx, levels):
        if doc.in_body[h['i']]:
            s |= set(range(h['i'], h['end'] + 1))
    return s


def _history_lines(doc):
    """编写记录 / 版本历史章：历史行照实保留，不按现行规则查。"""
    return _chap_lines(doc, RE_SEC_LOG) | _chap_lines(doc, RE_SEC_HISTORY, (1, 2))


def _scan_units(doc, skip, skip_col=None):
    """units() 的变体：给出 (行号, 可见文本, 取值上下文)。表内按单元格给文本、上下文取整行（同一 <tr> / 管道行），
    表外上下文就是本行；skip 里的行不扫，skip_col(表头) 为真的列整列不扫。"""
    for i, ln, k in doc.body(tables=False):
        if i in skip or k in ('wb', 'math'):
            continue
        t = strip_tags(ln)
        yield i, t, t
    for t in doc.tables:
        if t['start'] in doc.residual or t['start'] in skip:
            continue
        hd = t['header']
        for row in t['grid']:
            ctx = ' '.join(x['text'] for x in row['cells'] if x.get('origin', True))
            for k, cell in enumerate(row['cells']):
                if not cell.get('origin', True) or (skip_col is not None and k < len(hd) and skip_col(hd[k])):
                    continue
                for line, piece in cell['pieces']:
                    if line not in skip:
                        yield line, cell_text(piece), ctx


def has_value(text):
    """取值 = 数字（+ 单位）；US3-R1 / WEB-20339 / v2.9 / UTC+8 / 日期 / 不带单位的节号 5.2 不算。"""
    for m in RE_NUM.finditer(text):
        a, b = m.start(), m.end()
        before = text[a - 1] if a else ''
        if before and ((before.isascii() and before.isalpha()) or before in '.-+_/#:'):
            continue
        if re.match(r'[-/:]\d', text[b:b + 2]):
            continue
        if RE_UNIT_AFTER.match(text, b):
            return True
        after = text[b:b + 1]
        if '.' in m.group(0) or (after.isascii() and after.isalpha()):
            continue
        return True
    return bool(RE_CN_VALUE.search(text))


def check_l29(doc, track_lines):
    c = Check('L29')
    skip = _history_lines(doc) | _chap_lines(doc, RE_SEC_DATA) | _chap_lines(doc, RE_SEC_LOC) | track_lines
    hits, defer = [], 0
    for i, t, _ in _scan_units(doc, skip, skip_col=lambda h: '能力' in h):
        for m in RE_TECH.finditer(t):
            if RE_TECH_DEFER.match(t, m.end()):
                defer += 1  # 「调用顺序研发按现状定」：02 状态表指引的 ✅ 写法
                continue
            hits.append((i, m.group(0)))
    hits.sort(key=lambda x: x[0])
    for i, w in hits[:8]:
        c.add('WARN', i, w)
    parts = []
    if hits:
        c.add('INFO', None, '共 %d 处' % len(hits))
        cnt = Counter(w for _, w in hits)
        parts.append('共 %d 处（%s）：评审会上念不出来的，删常识 / 移技术方案 / 改表' % (
            len(hits), ' '.join('%s×%d' % kv for kv in cnt.most_common())))
        c.hits_override = len(hits)
    if defer:
        c.add('INFO', None, '按现状一句引用 %d 处' % defer)
        parts.append('「…按现状」一句引用 %d 处不计' % defer)
    c.detail = '；'.join(parts)
    return c, len(hits)


def check_l30(doc, track_lines):
    c = Check('L30')
    derived = set()
    for h in doc.headings:
        if h['level'] <= 3 and doc.in_body[h['i']] and RE_SEC_DERIVED.search(h['text']):
            derived |= set(range(h['i'], h['end'] + 1))
    skip = (_history_lines(doc) | _chap_lines(doc, RE_SEC_PENDING, (1, 2)) | _chap_lines(doc, RE_SEC_DATA)
            | _chap_lines(doc, RE_SEC_LOC) | track_lines)
    hdr_of = {line: ' '.join(t['header']) for t in doc.tables for line in t['lines']}
    bad, cnt, info = [], Counter(), Counter()
    for i, t, ctx in _scan_units(doc, skip):
        if doc.kind[i] == 'heading':
            continue  # 标题是节名不是规则（「头像业务规则（由广场定，UC 执行）」）
        found = {}  # 起点 → (原词, 主体 X, 是否单独的「建议」)
        for m in RE_DANGLE_YOU.finditer(t):
            a = m.end()
            if RE_DANGLE_SUBJ_FP.match(t[a:a + 8]):
                continue
            for v in RE_DANGLE_VERB.finditer(t, a, a + 8):
                if v.start() > a + 6:
                    break
                if v.group(0) == '定' and v.start() > a and t[v.start() - 1] in DANGLE_DING_FP:
                    break  # 「由选定的面板 / 由固定英文改为」：「由」引出的是对象，不是对方
                if v.group(0) == '定' and t[v.end():v.end() + 1] in DANGLE_DING_NEXT:
                    continue  # 「由广场定义」：定义 / 定位 / 定时… 不是把取值交给对方
                found.setdefault(m.start(), (t[m.start():v.end()], t[a:v.start()], False))
                break
        for m in RE_DANGLE_WAIT.finditer(t):
            subj = m.group(1)
            if (not subj.strip() and m.group(2) == '确认') or RE_DANGLE_SUBJ_FP.match(subj):
                continue  # 光「待确认」归 L03；「待用户确认」是交互
            found.setdefault(m.start(), (m.group(0), subj, False))
        for m in RE_DANGLE_OTHER.finditer(t):
            subj = '对方' if m.group(0) == '由对方' or RE_SIDE_PARTNER.search(ctx) else ''
            found.setdefault(m.start(), (m.group(0), subj, False))
        if i in derived:
            for m in RE_DANGLE_SUGGEST.finditer(t):
                found.setdefault(m.start(), (m.group(0), '', True))
        for _, (w, subj, suggest) in sorted(found.items()):
            w = re.sub(r'\s+', ' ', w).strip()
            if suggest:
                if not (RE_DANGLE_BASIS.search(ctx) or RE_DANGLE_BASIS.search(hdr_of.get(i, ''))):
                    c.add('INFO', i, '「建议」只记 INFO（给对方的参考写法）')
                    info['「建议」'] += 1
                continue  # 行内 / 表头已带依据、对标、竞品：不记
            side = 'partner' if RE_SIDE_PARTNER.search(subj) else ('ours' if RE_SIDE_OURS.search(subj) else '')
            if RE_DANGLE_ALLOW.search(ctx):
                c.add('INFO', i, '允许（接口形式 / 页面交互 / 接口下发）：%s' % short(w, 12))
                info['允许'] += 1
            elif RE_DANGLE_DELEGATE.search(ctx):
                c.add('INFO', i, '产品下放，核对是否有原话或归属声明：%s' % short(w, 12))
                info['产品下放'] += 1
            elif side == 'ours':
                c.add('INFO', i, '归属声明（我方侧）：%s' % short(w, 12))
                info['归属声明'] += 1
            elif has_value(ctx):
                c.add('INFO', i, '有候选值，核对依据是否写了（竞品 + 日期 / 产品决定）：%s' % short(w, 12))
                info['有取值'] += 1
            elif side == 'partner' and i in derived:
                c.add('FAIL', i, '合作方规则无取值：%s' % short(w, 14))
                bad.append('FAIL')
                cnt[w] += 1
            elif side == 'partner' or i in derived:
                c.add('WARN', i, '%s：%s' % ('合作方规则无取值（派生需求章外）' if side else '主体不明、无取值', short(w, 14)))
                bad.append('WARN')
                cnt[w] += 1
            else:
                c.add('INFO', i, '主体不明：%s' % short(w, 12))
                info['主体不明'] += 1
    nf, nw = bad.count('FAIL'), bad.count('WARN')
    parts = []
    if bad:
        parts.append('FAIL %d · WARN %d：%s' % (nf, nw, ' '.join('「%s」×%d' % kv for kv in cnt.most_common(6))))
    if info:
        parts.append('INFO ' + ' / '.join('%s %d' % kv for kv in info.most_common()))
    if nf:
        parts.append('派生需求章的合作方规则写取值 + 依据（竞品 + 日期 / 产品决定）')
    c.detail = ' · '.join(parts)
    return c, nf


def check_l31(doc, track_lines):
    c = Check('L31')
    skip = (_history_lines(doc) | _chap_lines(doc, RE_SEC_PENDING, (1, 2)) | _chap_lines(doc, RE_SEC_DATA)
            | _chap_lines(doc, RE_SEC_LOC) | track_lines)
    shown = []
    for i, t, _ in _scan_units(doc, skip):
        spans = []
        for rx in (RE_IMPL_IF, RE_IMPL_AS, RE_IMPL_PAIR, RE_IMPL_HEDGE):
            for m in rx.finditer(t):
                if any(m.start() < b and a < m.end() for a, b in spans):
                    continue
                toks = [m.start() + x.start() for x in re.finditer(r'同步|异步', m.group(0))]
                if any(RE_IMPL_FEATURE.search(t[max(0, p - 6):p + 4]) for p in toks):
                    continue  # 同步发布 / 多端同步 / 同步失败…：产品功能，不是调用模式
                spans.append((m.start(), m.end()))
                w = short(m.group(0), 18)
                c.add('FAIL', i, w)
                shown.append(w)
    if shown:
        c.detail = '%d 处：%s' % (len(shown), '；'.join('「%s」' % x for x in shown[:4]))
    return c


def check_l32(doc):
    c = Check('L32')
    n = len(doc.lines)
    vocab_tabs = [t for t in doc.tables if t['start'] not in doc.residual and RE_VOCAB.search(' '.join(t['header']))]
    vocab_heads = [h['i'] for h in doc.headings if doc.in_body[h['i']] and '词汇' in h['text']]
    recs = missing = 0
    for t in doc.tables:
        hd = ' '.join(t['header'])
        is_record = '类型' in hd and ('结论' in hd or ('原因' in hd and re.search(r'记录|处理人', hd)))
        if t['start'] in doc.residual or RE_VOCAB.search(hd) or RE_REC_EXCLUDE.search(hd) or not is_record:
            continue  # 兜底表「异常类型 | 触发原因 | 用户看到 | 处理」不是记录表
        recs += 1
        region = set(range(t['end'] + 1, min(n, t['end'] + 61)))
        outer = [h for h in doc.headings if h['level'] <= 3 and h['i'] < t['start'] <= h['end']]
        if outer:
            sec = max(outer, key=lambda h: h['i'])
            region |= set(range(sec['i'], sec['end'] + 1))
        if not (any(i in region for i in vocab_heads) or any(v['start'] in region for v in vocab_tabs)):
            c.add('WARN', t['start'], '记录表（%s）旁无词汇表' % short(hd, 24))
            missing += 1
    if recs:
        c.detail = '记录表 %d 张 · 词汇表 %d 张' % (recs, len(vocab_tabs))
        if missing:
            c.detail += '：%d 张缺词汇表（类型 / 结论取值 / 原因取值 / 处理人）' % missing
        else:
            c.add('INFO', None, 'facts')
            c.hits_override = None
    elif vocab_tabs:
        c.detail = '无记录表 · 词汇表 %d 张' % len(vocab_tabs)
    return c


def _ac_items(doc):
    """验收章各 US-R 小节的条目行（与 L18 同口径：勾选项优先，没有再数列表项 / 表格行）。"""
    ac = [h for h in doc.find_sections(RE_SEC_AC, (1,)) if doc.in_body[h['i']]]
    if not ac:
        ac = [h for h in doc.find_sections(RE_SEC_AC) if doc.in_body[h['i']] and not RE_SEC_AC_POINTER.search(h['text'])][:1]
    lines, items = set(), {}
    for h in ac:
        lines |= set(range(h['i'], h['end'] + 1))
        for s in doc.headings:
            if not (h['i'] < s['i'] <= h['end']) or not RE_US_R_ID.search(s['text']):
                continue
            rng = [i for i in range(s['i'] + 1, s['end'] + 1) if doc.in_body[i]]
            got = [i for i in rng if RE_CHECKBOX.match(doc.lines[i])]
            if not got:
                got = [i for i in rng if doc.kind[i] == 'list' and RE_LIST.match(doc.lines[i])]
                got += [r['line'] for t in doc.tables if s['i'] < t['start'] and t['end'] <= s['end'] for r in t['grid'][1:]]
            for x in RE_US_R_ID.findall(s['text']):
                items.setdefault('US%s-R%s' % x, set()).update(got)
    return lines, items


def _us_at(doc, idx, skip):
    """图所在 US：最内层包住它的 US-R 标题，没有就取 US 标题。"""
    us = None
    for h in doc.headings:
        if h['i'] >= idx:
            break
        if h['i'] in skip or idx > h['end']:
            continue
        m = RE_US_R_ID.search(h['text'])
        if m:
            us = 'US%s-R%s' % m.groups()
        elif RE_US_HEADING.match(h['text']):
            us = 'US%s' % re.match(r'^\s*US\s*(\d+)', h['text'], re.I).group(1)
    return us


def _state_fences(doc):
    """含 stateDiagram 的 mermaid 源（起草稿 fence / 画板内联源）：[(起始行, 正文行)]。"""
    src = [(f['start'], f['body']) for f in doc.fences if f['lang'] == 'mermaid' and f['start'] not in doc.preamble]
    src += [(w['start'], w['body']) for w in doc.whiteboards
            if w['type'] == 'mermaid' and w['body'] and w['start'] not in doc.preamble]
    return sorted([(s, b) for s, b in src if any('stateDiagram' in ln for ln in b)], key=lambda x: x[0])


def _mm_edge_count(body):
    return sum(len(RE_MM_ARROW.findall(ln.split('%%')[0])) for ln in body if not RE_MM_SKIP.match(ln))


def check_l33(doc):
    c = Check('L33')
    ac_lines, items = _ac_items(doc)
    parts = []
    for start, body in _state_fences(doc):
        edges = _mm_edge_count(body)
        if not edges:
            continue
        us = _us_at(doc, start, ac_lines)
        if us is None:
            c.add('INFO', start, '边 %d（不在 US 内，未对账）' % edges)
            parts.append('L%d 图 边 %d（不在 US 内，未对账）' % (start + 1, edges))
            continue
        got = items.get(us, set()) if '-R' in us else set().union(*[v for k, v in items.items() if k.startswith(us + '-')])
        c.add('INFO', start, '%s 边 %d / 验收 %d' % (us, edges, len(got)))
        if len(got) < edges:
            c.add('WARN', start, '%s 边 %d / 验收 %d：每条边一条验收（同类边可合并为一条，但要点名覆盖的边）' % (us, edges, len(got)))
        parts.append('L%d 图（%s）边 %d / 验收 %d' % (start + 1, us, edges, len(got)))
    has_src = any(f['lang'] == 'mermaid' for f in doc.fences) or any(w['type'] == 'mermaid' and w['body'] for w in doc.whiteboards)
    if parts:
        c.detail = '；'.join(parts)
    elif doc.whiteboards and not has_src:
        c.detail = '画板 %d 个（无 mermaid 源可数）' % len(doc.whiteboards)
    return c


def check_l34(doc):
    c = Check('L34')
    pend = _chap_lines(doc, RE_SEC_PENDING, (1, 2))
    cnt, cnt_p, at, ab, cand = Counter(), Counter(), {}, False, False
    for i, t, _ in _scan_units(doc, _history_lines(doc)):
        if RE_AB_TEST.search(t):
            ab = True
        for m in RE_SCHEME.finditer(t):
            g = {'Ａ': 'A', 'Ｂ': 'B'}.get(m.group(1), m.group(1))
            nxt = t[m.end():m.end() + 1]
            if (g in SCHEME_CN_FP and nxt and nxt in SCHEME_CN_FP[g]) or (g in 'AB' and nxt.isascii() and nxt.isalnum()):
                continue  # 「方案一致 / 方案二期」「方案 A1」不算
            if i in pend:
                cnt_p[g] += 1
            else:
                cnt[g] += 1
                at.setdefault(i, set()).add(g)
                if g in ('B', '二') and RE_SCHEME_CAND.search(t[m.end():m.end() + 12]):
                    cand = True  # 「方案 B（候选 · 供估量）」：02 允许保留另一方案细稿供估量
    order = ('A', 'B', '一', '二')
    facts = ' · '.join('方案%s%s ×%d' % (' ' if g in 'AB' else '', g, cnt[g]) for g in order if cnt[g])
    if any(cnt_p.values()):
        facts += '%s【待确认】章内 %s' % ('；' if facts else '', ' '.join('%s×%d' % (g, cnt_p[g]) for g in order if cnt_p[g]))
    both = (cnt['A'] and cnt['B']) or (cnt['一'] and cnt['二'])
    if both and not ab and not cand:
        for i in sorted(at):
            c.add('WARN', i, '、'.join('方案%s%s' % (' ' if g in 'AB' else '', g) for g in sorted(at[i])))
        c.add('INFO', None, facts)
        c.detail = '%s；【待确认】章外 %d 行：正文按推荐方案写，另一方案进待确认一行' % (facts, len(at))
        c.hits_override = len(at)
    elif facts:
        c.add('INFO', None, facts)
        c.detail = facts + ('（疑为 AB 实验分组，未判）' if both and ab else
                            '（另一方案标了候选 / 供估量，只记 INFO）' if both else '')
    return c


def check_l35(doc):
    c = Check('L35')
    skip = _history_lines(doc) | _chap_lines(doc, RE_SEC_LOC)
    for t in doc.tables:  # 目录式指路「发帖权限…（见 3.3.2）」合法
        outer = [h for h in doc.headings if h['i'] < t['start'] <= h['end']]
        if outer and RE_SEC_INDEX.search(max(outer, key=lambda h: h['i'])['text']):
            skip |= t['lines']
    hits = []
    for i, t, _ in _scan_units(doc, skip):
        for m in RE_BARE_REF.finditer(t):
            if (m.group(2) == '0' and not m.group(1)) or '版本' in t[max(0, m.start() - 4):m.start()]:
                continue  # 「按 0.8 的保证金率」是数值；「版本按 6.2」是版本号
            hits.append((i, re.sub(r'\s+', ' ', m.group(0))))
    parts = []
    if hits:
        hits.sort(key=lambda x: x[0])
        sev = 'WARN' if len(hits) >= 5 else 'INFO'
        for i, w in hits:
            c.add(sev, i, w)
        nums = Counter(re.search(r'\d+(?:\.\d+)+', w).group(0) for _, w in hits)
        parts.append('%d 处（%s）' % (len(hits), ' '.join('%s×%d' % kv for kv in nums.most_common(6)))
                     + ('：引用写规则名 + 一句结论，不写编号（02 规则只住一处）' if sev == 'WARN' else ''))
    refs, n_codes, dangling = _letter_codes(doc)
    if n_codes >= 10:
        c.add('WARN', refs[0][0], '字母编号引用 %d 处' % n_codes)
        top = Counter(code for _, code in refs).most_common(6)
        parts.append('字母编号引用 %d 处（%s）：编号体系进了正文，引用写规则名 + 一句结论' % (
            n_codes, ' '.join('%s×%d' % kv for kv in top)))
    for code, i in dangling:
        c.add('WARN', i, '悬空编号 %s' % code)
    if dangling:
        parts.append('悬空编号 %d 个（%s）：只有引用、标题行与表格首列都没定义' % (
            len(dangling), ' '.join(code for code, _ in dangling[:8])))
    if not parts:
        return c
    c.detail = '；'.join(parts)
    c.hits_override = len(hits) + (n_codes if n_codes >= 10 else 0) + len(dangling)
    return c


def _letter_codes(doc):
    """字母 + 两位数编号（G02 / C01 / A13 / D45）：返回 (正文引用 [(行, 编号)], 引用数, 悬空 [(编号, 首次引用行)])。
    定义 = 出现在标题行或表格首列；引用只数编写记录 / 待确认 / 埋点表以外的正文。Jira 键先剔掉。"""
    def codes(text):
        return [m.group(0) for m in RE_LETTER_CODE.finditer(RE_JIRA_KEY.sub(' ', text))]

    scope_skip = _history_lines(doc) | _chap_lines(doc, RE_SEC_PENDING, (1, 2)) | doc.table_line_set(is_track_table)
    defined, refs = set(), []
    tab_lines = set()
    for t in doc.tables:
        tab_lines |= t['lines']
        for row in t['grid']:
            for k, cell in enumerate(row['cells']):
                if not cell.get('origin', True):
                    continue
                for line, piece in cell['pieces']:
                    found = codes(cell_text(piece))
                    if k == 0:
                        defined.update(found)
                    elif line not in scope_skip and doc.in_body[line] and line not in doc.residual:
                        refs += [(line, x) for x in found]
    for i, ln in enumerate(doc.lines):
        if not doc.in_body[i] or i in tab_lines or i in doc.residual:
            continue
        found = codes(strip_tags(ln))
        if doc.kind[i] == 'heading':
            defined.update(found)
        elif i not in scope_skip and doc.kind[i] not in ('code', 'wb'):
            refs += [(i, x) for x in found]
    refs.sort()
    first = {}
    for i, x in refs:
        first.setdefault(x, i)
    dangling = sorted(((x, i) for x, i in first.items() if x not in defined), key=lambda p: p[1])
    return refs, len(refs), dangling


def _skip_y(doc):
    return _history_lines(doc) | _chap_lines(doc, RE_SEC_LOC) | _chap_lines(doc, RE_SEC_PENDING, (1, 2))


def _party_name(text):
    s, prev = re.sub(r'[\s*`]', '', text), None
    while s != prev:
        prev, s = s, RE_PARTY_SUFFIX.sub('', s)
    return s


def check_l36(doc):
    c = Check('L36')
    skip = _skip_y(doc)
    seen, names = set(), []
    for h in doc.find_sections(RE_SEC_DEPS):
        if not doc.in_body[h['i']] or h['i'] in skip:
            continue
        for t in doc.tables:
            if not (h['i'] < t['start'] <= h['end']) or t['start'] in seen or not t['header']:
                continue
            seen.add(t['start'])
            if not RE_PARTY_HEAD.search(t['header'][0]):
                continue  # 派生需求的「能力 / 事项」表首列不是关联方
            reported = set()
            for row in t['grid'][1:]:
                cell = row['cells'][0] if row['cells'] else None
                if cell is None or not cell.get('origin', True):
                    continue  # rowspan 续行：同一方只报一次
                name = _party_name(cell['text'])
                if RE_SUPPORT_PARTY.match(name) and name not in reported:  # 整格是职能支持方才报（「大数据组」「AB 测试平台」不报）
                    reported.add(name)
                    c.add('WARN', row['line'], '「%s」' % short(cell['text'], 10))
                    names.append(short(cell['text'], 10))
    if names:
        c.detail = '%d 行（%s）：职能支持方不是关联方，埋点 module / 指标校准写在埋点表与指标口径一句即可' % (
            len(names), '、'.join(names[:5]))
    return c, len(names)


def _pure_reuse(text):
    """整格都是沿用声明：每个分句（，；。切开、去标点）都形如「X 不变 / 沿用 X / 继续使用现有 X / 保持现状」，且无取值、无新增 / 改为。"""
    if RE_REUSE_DECL_OK.search(text) or has_value(text):
        return False
    clauses = [x for x in (RE_CLAUSE_PUNCT.sub('', y) for y in RE_CLAUSE_SPLIT.split(text)) if x]
    return bool(clauses) and all(RE_REUSE_CLAUSE.match(x) for x in clauses)


def check_l37(doc):
    c = Check('L37')
    skip = _skip_y(doc)
    seen, warned_all, info, emptied = set(), 0, Counter(), 0
    for h in doc.headings:
        if not doc.in_body[h['i']] or h['i'] in skip:
            continue
        is_global = bool(RE_SEC_GLOBAL.search(h['text']))
        if not (is_global or RE_SEC_CORE.search(h['text'])):
            continue
        tabs = [t for t in doc.tables if h['i'] < t['start'] <= h['end'] and t['start'] not in seen]
        rows = warned = 0
        for t in tabs:
            seen.add(t['start'])
            for row in t['grid'][1:]:
                cells = [x['text'] for x in row['cells'] if x.get('origin', True)]
                if not any(cells):
                    continue
                rows += 1
                rule_cells = [x for x in (cells[1:] if len(cells) > 1 else cells) if x.strip()]
                rule = ' '.join(rule_cells)
                if is_global and rule_cells and all(_pure_reuse(x) for x in rule_cells):
                    c.add('WARN', row['line'], '「%s」沿用即沉默，删行' % short(cells[0], 10))
                    warned += 1
                elif is_global and RE_REUSE_DECL.search(rule):
                    c.add('INFO', row['line'], '「%s」含沿用措辞，确认是否写了本需求的定义' % short(cells[0], 10))
                    info['全局口径'] += 1
                elif not is_global and RE_REUSE_DECL.search(rule) and not RE_REUSE_DECL_OK.search(rule) and not has_value(rule):
                    c.add('INFO', row['line'], '「%s」含沿用措辞，确认是决策还是复述' % short(cells[0], 10))
                    info['核心规则'] += 1
        warned_all += warned
        if is_global:
            prose = [i for i in range(h['i'] + 1, h['end'] + 1)
                     if doc.in_body[i] and doc.kind[i] in ('prose', 'list', 'quote', 'html')]
            if (tabs and warned == rows) or (not tabs and not prose):  # 删完无行只数 WARN 行；只剩表头也算
                c.add('WARN', h['i'], '全局口径删完无行：整节删')
                emptied += 1
    parts = []
    if warned_all:
        parts.append('整格沿用声明 %d 行：沿用即沉默，删行' % warned_all)
    if info:
        parts.append('含沿用措辞 INFO %d 行（%s）' % (sum(info.values()), ' · '.join('%s %d' % kv for kv in info.items())))
    if emptied:
        parts.append('全局口径节删完无行：整节删')
    c.detail = '；'.join(parts)
    return c


def _us_modules(doc, skip):
    """US 小节：## / ### 的 US 标题，排除标题含「验收」与验收章内的；有 US-R 编号的按 US-R 计，否则按 US 计。"""
    ac = set()
    for h in doc.find_sections(RE_SEC_AC, (1,)):
        ac |= set(range(h['i'], h['end'] + 1))
    heads = [h for h in doc.headings if h['level'] in (2, 3) and doc.in_body[h['i']] and h['i'] not in skip
             and h['i'] not in ac and '验收' not in h['text'] and RE_US_HEADING.match(h['text'])]
    return [h for h in heads if RE_US_R_HEAD.match(h['text'])] or heads


def check_l38(doc):
    c = Check('L38')
    skip = _skip_y(doc)
    cores = [h for h in doc.headings if doc.in_body[h['i']] and h['i'] not in skip and RE_SEC_CORE.search(h['text'])]
    if not cores:
        return c
    mods = _us_modules(doc, skip)
    mod_txt = [re.sub(r'\s+', '', ' '.join(strip_tags(doc.lines[i]) for i in range(h['i'], h['end'] + 1) if doc.in_body[i]))
               for h in mods]

    def row_names(a, b):
        out = []
        for t in doc.tables:
            if a < t['start'] <= b:
                out += [(r['line'], r['cells'][0]['text']) for r in t['grid'][1:] if r['cells']]
        return out

    units = []  # (行号, 规则名, 匹配键, 是否小节)
    for h in cores:
        subs = [s for s in doc.headings if h['i'] < s['i'] <= h['end'] and doc.in_body[s['i']]]
        if subs:  # 按规则小节计：小节标题（去「规则 N：」/ 节号）+ 小节内各行首格都算这一节的名字
            top = min(s['level'] for s in subs)
            for s in [x for x in subs if x['level'] == top]:
                name = RE_RULE_PREFIX.sub('', s['text']).strip()
                units.append((s['i'], name, [name] + [x for _, x in row_names(s['i'], s['end'])], True))
        else:  # 没有小节标题：退回按行，首格是纯数字 / 序号的行跳过
            for line, x in row_names(h['i'], h['end']):
                if not RE_ORDINAL_CELL.match(re.sub(r'\s+', '', x)):
                    units.append((line, x, [x], False))
    counted = lonely = 0
    for line, name, keys, is_sub in units:
        keys = [k for k in (re.sub(r'[\s*`「」『』]', '', y)[:12] for y in keys) if len(k) >= 4]  # 规则名 <4 字不计
        if not keys:
            continue
        counted += 1
        n = sum(1 for x in mod_txt if any(k[:4] in x for k in keys))
        if n < 2:
            c.add('INFO', line, '%s「%s」只有 %d 个模块引用' % ('小节' if is_sub else '规则', short(name, 12), n))
            lonely += 1
    c.detail = '核心规则 %d %s · 只有 0–1 个模块引用 %d' % (counted, '小节' if any(u[3] for u in units) else '行', lonely)
    if len(mods) <= 2:
        cross = any(h['i'] <= s0 <= h['end'] for h in cores for s0 in
                    [x for x, _ in _state_fences(doc)] + [w['start'] for w in doc.whiteboards])
        if cross:
            c.add('INFO', cores[0]['i'], '%d 个模块 + 状态图：核对是否跨模块' % len(mods))
            c.detail += '；%d 个模块 + 状态图（stateDiagram / 画板）：核对是否跨模块' % len(mods)
        else:
            c.add('WARN', cores[0]['i'], 'US 模块只有 %d 个：两个模块的需求不需要核心规则节' % len(mods))
            c.detail += '；US 模块只有 %d 个：两个模块的需求不需要核心规则节' % len(mods)
            c.hits_override = 1
    return c


def _front_zone(doc):
    """前置区：第一个 US 起点（验收章外 `##` / `###` 的 US 标题或含「用户故事 N」的标题）之前的正文行，
    去掉任一级的编写记录 / 版本历史、待确认、Quality Gates 章。"""
    ac = set()
    for h in doc.find_sections(RE_SEC_AC, (1,)):
        ac |= set(range(h['i'], h['end'] + 1))
    us1 = next((h['i'] for h in doc.headings if h['level'] in (2, 3) and doc.in_body[h['i']] and h['i'] not in ac
                and RE_US_START.search(h['text'])), None)
    if us1 is None:
        return set(), None
    skip = (_chap_lines(doc, RE_SEC_LOG, (1, 2, 3)) | _chap_lines(doc, RE_SEC_HISTORY, (1, 2, 3))
            | _chap_lines(doc, RE_SEC_PENDING, (1, 2)) | _chap_lines(doc, RE_SEC_GATES, (1, 2)))
    return set(i for i in range(us1) if doc.in_body[i] and i not in skip), us1


def _cjk_of(doc, i):
    return len(RE_CJK.findall(strip_tags(doc.lines[i])))


def check_l39(doc):
    c = Check('L39')
    zone, us1 = _front_zone(doc)
    if us1 is None:
        c.detail = '无 US 起点标题，前置区未计'
        return c, None
    zone = set(i for i in zone if i not in doc.residual and not RE_FILL.search(doc.lines[i]))  # 指引 / 占位行不计
    total = sum(_cjk_of(doc, i) for i in zone)
    heads = [h for h in doc.headings if h['level'] <= 2 and h['i'] in zone]
    segs = []
    for k, h in enumerate(heads):
        nxt = heads[k + 1]['i'] if k + 1 < len(heads) else us1
        n = sum(_cjk_of(doc, i) for i in range(h['i'], nxt) if i in zone)
        if n:
            segs.append((n, short(re.sub(r'^\s*\d+(?:\.\d+)*\s*', '', h['text']), 12), h['i']))
    top = ' · '.join('%s %d' % (t, n) for n, t, _ in sorted(segs, key=lambda x: -x[0])[:6])
    detail = 'US1 之前 %d 字（不含编写记录）：%s；参照：金标 ≈1,300–1,400（不含编写记录）' % (total, top or '—')
    if total > 1500:  # 2.2.0：02 前置区六条 ⑥
        big = max(segs, key=lambda x: x[0]) if segs else None
        c.add('WARN', big[2] if big else None, '前置区 %d 字 >1,500%s' % (total, '：最大块「%s」%d 字' % (big[1], big[0]) if big else ''))
        c.hits_override = 1
        c.detail = '>1,500：先看最大块「%s」%d 字；%s' % (big[1], big[0], detail) if big else '>1,500；' + detail
    else:
        c.add('INFO', None, 'facts')
        c.hits_override = None
        c.detail = detail
    return c, total


def check_l40(doc):
    c = Check('L40')
    zone, us1 = _front_zone(doc)
    if us1 is None:
        return c
    n1 = n2 = n3 = n_ov = n_duty = 0
    for h in doc.headings:
        if h['i'] not in zone or h['level'] not in (2, 3) or re.search(r'需求范围', h['text']):
            continue
        t = h['text']
        if RE_DUTY_HEAD_WARN.search(t):
            c.add('WARN', h['i'], '「%s」：分工不单开节' % short(t, 14))
            n1 += 1
        elif RE_DUTY_OVERVIEW.search(t):
            c.add('INFO', h['i'], '「%s」：相关方合作总览只在产品明说要给合作方讲时画，且不配复述表' % short(t, 14))
            n_ov += 1
        elif RE_DUTY_HEAD_INFO.search(t):
            c.add('INFO', h['i'], '「%s」：职责边界并进关联方表『功能列表』列或文末附录，不在 US 之前单开节' % short(t, 14))
            n_duty += 1
    for t in doc.tables:
        if t['start'] not in zone or not t['header']:
            continue
        hd = ' '.join(t['header'])
        if RE_RECAP_SKIP.search(hd):
            continue  # 关联方类表（含「关联系统 | 负责内容」同义列）不算复述表
        if RE_RECAP_A.search(hd) and RE_RECAP_B.search(hd):
            c.add('WARN', t['start'], '表头「%s」：泳道的文字复述表删' % short(hd, 20))
            n2 += 1
    seen = set()
    for h in doc.find_sections(RE_SEC_DEPS):
        for t in doc.tables:
            if not (h['i'] < t['start'] <= h['end']) or t['start'] in seen or t['start'] not in zone or not t['header']:
                continue
            seen.add(t['start'])
            m = RE_DEPS_EXTRA_COL.search(' '.join(t['header']))
            if RE_PARTY_HEAD.search(t['header'][0]) and m:
                c.add('WARN', t['start'], '关联方表含「%s」列：只保留 house 四列' % m.group(0))
                n3 += 1
    parts = []
    if n1 or n2 or n3:
        parts.append('角色与系统边界节 %d · 泳道复述表 %d · 关联方表多列 %d：分工不写，关联方表四列 + US-R 后端说明' % (n1, n2, n3))
    if n_duty:
        parts.append('分工 / 职责 / 边界 / 交接 %d 节（INFO）：并进关联方表『功能列表』列或文末附录' % n_duty)
    if n_ov:
        parts.append('合作总览 %d 节（INFO）：只在产品明说要给合作方讲时画，且不配复述表' % n_ov)
    c.detail = '；'.join(parts)
    return c


def check_l41(doc):
    c = Check('L41')
    bg = [h for h in doc.find_sections(RE_SEC_BG, (1,)) if doc.in_body[h['i']]]
    if not bg:
        return c
    h = bg[0]
    stop = next((x['i'] for x in doc.headings if h['i'] < x['i'] <= h['end'] and RE_BG_STOP.search(x['text'])), None)
    end = stop - 1 if stop is not None else h['end']
    rng = [i for i in range(h['i'], end + 1) if doc.in_body[i] and i not in doc.residual]  # 【指引】行不计
    text = ' '.join(strip_tags(doc.lines[i]) for i in rng)
    cjk = len(RE_CJK.findall(text))
    tabs = [t for t in doc.tables if h['i'] < t['start'] <= end and t['start'] not in doc.residual]
    ab = bool(RE_AB_TEST.search(text))  # AB 实验的 A / B 组是实验设计，不算未拍板方案
    warn, info = [], []
    if not ab and any(any('方案' in x for x in t['header']) for t in tabs):
        warn.append('方案对比表：不进背景，待确认一行 + 候选细稿作附录')
    elif not ab:
        m = RE_SCHEME_BG.search(text)
        if m:
            info.append('正文提及「%s」' % m.group(0))
    if len(tabs) >= 3:
        warn.append('表 %d 张' % len(tabs))
    elif len(tabs) == 2:
        info.append('表 2 张')
    if cjk > 600:
        warn.append('%d 字 >600' % cjk)
    elif cjk > 400:
        info.append('%d 字 >400' % cjk)
    parts = ['背景章 %d 字 · 表 %d 张' % (cjk, len(tabs))]
    if warn:
        c.add('WARN', h['i'], '、'.join(warn))
        parts.append('WARN：' + '、'.join(warn))
    if info:
        c.add('INFO', h['i'], '、'.join(info))
        parts.append('INFO：' + '、'.join(info))
    if warn or info:
        parts.append('背景 / 价值各 ≤2 句 + 信息表')
    c.detail = '；'.join(parts)
    return c


def check_l42(doc):
    c = Check('L42')
    skip = _skip_y(doc) | _chap_lines(doc, RE_SEC_GATES, (1, 2))
    for h in doc.find_sections(RE_SEC_TARGET):
        if h['i'] in skip or not doc.in_body[h['i']]:
            continue
        t = next((t for t in doc.tables if h['i'] < t['start'] <= h['end']), None)
        if t is not None:
            rows = [r for r in t['grid'][1:] if any(x['text'] for x in r['cells'] if x.get('origin', True))]
            if len(rows) > 3:
                c.add('INFO', t['start'], '目标用户 %d 行 >3' % len(rows))
                c.detail = '目标用户 %d 行 >3：C 端稿只列主要使用者；B 端多角色可以' % len(rows)
        break
    return c


def check_l43(doc):
    c = Check('L43')
    ac_start = min([h['i'] for h in doc.find_sections(RE_SEC_AC, (1,)) if doc.in_body[h['i']]] or [len(doc.lines)])
    skip = (_chap_lines(doc, RE_SEC_LOG, (1, 2, 3)) | _chap_lines(doc, RE_SEC_PENDING, (1, 2))
            | _chap_lines(doc, RE_SEC_GATES, (1, 2)))
    appx = set()
    for h in doc.headings:
        if doc.in_body[h['i']] and '附录' in h['text']:
            appx |= set(range(h['i'], h['end'] + 1))
    names = []
    for h in doc.headings:
        if (h['i'] >= ac_start or not doc.in_body[h['i']] or h['i'] in skip or h['i'] in appx
                or not re.search(r'派生需求', h['text'])):
            continue
        if h['level'] >= 3 and not any(h['i'] < t['start'] <= h['end'] and t['header'] and '事项' in t['header'][0]
                                       for t in doc.tables):
            continue  # 关联方下只有能力表的「### 派生需求」可以留
        c.add('INFO', h['i'], '「%s」在验收之前：事项表与合作方功能描述放文末附录；能力表可留关联方节' % short(h['text'], 12))
        names.append(short(h['text'], 12))
    parts = []
    if names:
        parts.append('%s 在验收之前：事项表与合作方功能描述放文末附录；能力表可留关联方节' % '、'.join('「%s」' % x for x in names))
    if any(doc.in_body[h['i']] and RE_SEC_APPX_PARTNER.search(h['text']) for h in doc.headings):
        cells = []
        for h in doc.find_sections(RE_SEC_DEPS):
            for t in doc.tables:
                if h['i'] < t['start'] <= h['end'] and t['header'] and RE_PARTY_HEAD.search(t['header'][0]):
                    cells += [x['text'] for r in t['grid'][1:] for x in r['cells']]
        if cells and not any('附录' in x for x in cells):
            c.add('INFO', None, '关联方表加『详见附录』指针')
            parts.append('有「附录：合作方交付」但关联方表没写『详见附录』：关联方表加指针')
    c.detail = '；'.join(parts)
    return c


# ---------------------------------------------------------------- L44–L47（空槽 / 后端说明列 / 编写记录列 / 模块地图）

RE_PAREN_ONLY = re.compile(r'^[（(][^（()）]*[）)]$')
RE_SLOT_HEAD = re.compile(r'^(需求逻辑|前端说明|后端说明|兜底逻辑|线框原型图|UED\s*设计稿)\s*[：:]?\s*(.*)$', re.I)
RE_BE_VERB = re.compile(r'返回|提供|下发|给|按|由|不|需|须|取|读|写|校验|计算|保留|过滤|排序|分页|去重|为准')  # 后 / 前 / 时 / 以 / 同 / 沿 单字太宽，不算
RE_BE_FORM = re.compile(r'^\s*字段|字段\s*[`「『]|接口\s*`?\s*/|来源\s*[：:]|由后端|为空')  # 07 §五 6 认可的指针形态，算句子
RE_BE_REF = re.compile(r'PRD|规范|专项|词条')
RE_BE_EMPTY = re.compile(r'^[/／—–\-]?$')
RE_MOD_SEP = re.compile(r'^[：:·・\-—–、.．|｜]+|[：:·・\-—–、.．|｜]+$')
RE_AC_WORD = re.compile(r'(?:功能)?验收(?:标准)?')
RE_MD_LINK_TEXT = re.compile(r'\[([^\]]*)\]\([^)]*\)')
RE_MAP_EXTRA = re.compile(r'研发重点|测试重点')


def _in_us_r(doc, i, ac):
    """该行最近的 ≤3 级标题是验收章外的 US-R 标题（附录、全局口径等不算）。"""
    for h in reversed(doc.headings):
        if h['i'] <= i and h['level'] <= 3:
            return h['i'] not in ac and bool(RE_US_R_HEAD.match(h['text']))
    return False


def _empty_slots(doc):
    """#### 槽标题（需求逻辑 / 前端说明 / 后端说明 / 兜底逻辑 / 线框原型图 / UED设计稿）与 ##### 板块标题，只查 US-R 段内
    （最近的 ≤3 级标题是验收章外的 US-R）：跳过空行、`---` 与 HTML 注释后直接是同级或更高级标题、或到文件尾 → 空槽。
    下级标题算内容（前端说明下挂 ##### 板块是 house 形状）；标题自带「：不涉及…」这类正文的不算空，括注（「需求逻辑（本模块无新增规则）」）
    不算正文；模板残留行算内容（由 L02 报）。"""
    out, n = [], len(doc.lines)
    ac = set()
    for h in doc.find_sections(RE_SEC_AC, (1,)):
        ac |= set(range(h['i'], h['end'] + 1))
    for h in doc.headings:
        if not doc.in_body[h['i']] or h['i'] in doc.residual or h['i'] in ac or not _in_us_r(doc, h['i'], ac):
            continue
        if h['level'] == 4:
            m = RE_SLOT_HEAD.match(h['text'])
            if not m:
                continue
            rest = m.group(2).strip()
            if rest and not RE_PAREN_ONLY.match(rest):
                continue
        elif h['level'] != 5:
            continue
        j = h['i'] + 1
        while j < n and doc.kind[j] in ('blank', 'hr', 'comment'):
            j += 1
        if j >= n:
            out.append(h)
        elif doc.kind[j] == 'heading':
            nxt = next((x for x in doc.headings if x['i'] == j), None)
            if nxt is not None and nxt['level'] <= h['level']:
                out.append(h)
    return out


def _owner_us_r(doc, i):
    for h in reversed(doc.headings):
        if h['i'] < i and h['level'] <= 3:
            m = RE_US_R_ID.search(h['text'])
            return 'US%s-R%s' % m.groups() if m else short(h['text'], 8)
    return ''


def check_l44(doc):
    c = Check('L44')
    empty = _empty_slots(doc)
    for h in empty:
        c.add('FAIL', h['i'], '「%s」空（%s）' % (short(h['text'], 10), _owner_us_r(doc, h['i'])))
    if empty:
        names = Counter(RE_SLOT_HEAD.match(h['text']).group(1) if h['level'] == 4 else '##### 板块' for h in empty)
        c.detail = '%d 个空槽（%s）：%s' % (len(empty), ' · '.join('%s %d' % kv for kv in names.most_common()),
                                        '；'.join('L%d %s（%s）' % (h['i'] + 1, short(h['text'], 10), _owner_us_r(doc, h['i']))
                                                 for h in empty[:12]) + ('…' if len(empty) > 12 else ''))
    return c


def check_l45(doc):
    c = Check('L45')
    skip = _history_lines(doc)
    kinds, nouns, tables = Counter(), [], 0
    for t in doc.tables:
        if t['start'] in doc.residual or t['start'] in skip or not is_element_table(t):
            continue
        col = find_col(t['header'], lambda h: '后端' in h)
        if col is None:
            continue
        tables += 1
        for row in t['grid'][1:]:
            if col >= len(row['cells']) or not row['cells'][col].get('origin', True):
                continue
            cell = row['cells'][col]
            txt = cell['text'].strip()
            if RE_BE_EMPTY.match(txt):
                continue
            verb = RE_BE_VERB.search(txt)
            if (verb and len(RE_CJK.findall(txt)) >= 8) or RE_BE_FORM.search(txt):
                kinds['句子'] += 1
            elif not verb and ('http' in cell['raw'] or RE_BE_REF.search(txt)):
                kinds['仅链接 / 名字'] += 1
                nouns.append((cell['line'], txt))
            elif len(re.sub(r'\s+', '', txt)) <= 15:
                kinds['名词短语'] += 1
                nouns.append((cell['line'], txt))
            else:
                kinds['其它'] += 1
    total = sum(kinds.values())
    if not total:
        if tables:
            c.detail = '%d 张元素表的后端说明列全是 / 或空' % tables
        return c
    bad = kinds['名词短语'] + kinds['仅链接 / 名字']
    stat = '%d 张元素表 %d 格：句子 %d · 名词短语 %d · 仅链接 / 名字 %d%s' % (
        tables, total, kinds['句子'], kinds['名词短语'], kinds['仅链接 / 名字'],
        ' · 其它 %d' % kinds['其它'] if kinds['其它'] else '')
    if bad * 2 > total:
        for i, txt in nouns:
            c.add('WARN', i, short(txt, 16))
        c.hits_override = bad
        noun_only = [x for x in nouns if not RE_BE_REF.search(x[1])][:6]
        c.detail = '%s（名词 + 仅链接 %.0f%% >50%%）；前 6 个名词格：%s' % (
            stat, bad * 100.0 / total, '、'.join('L%d「%s」' % (i + 1, short(x, 12)) for i, x in noun_only) or '—')
    else:
        c.add('INFO', None, 'facts')
        c.hits_override = None
        c.detail = stat
    return c


def check_l46(doc):
    c = Check('L46')
    secs = [h for h in doc.find_sections(RE_SEC_LOG) if doc.in_body[h['i']]]
    secs.sort(key=lambda h: (h['level'] != 1, h['i']))
    if not secs:
        c.detail = '无编写记录章（L01 报）'
        return c
    h = secs[0]
    t = next((t for t in doc.tables if h['i'] < t['start'] <= h['end']), None)
    if t is None:
        c.add('FAIL', h['i'], '编写记录章无表')
        c.detail = '编写记录章无表'
        return c
    hd = t['header']
    joined = ' '.join(hd)
    ok_cm = re.search(r'Commented|评论', joined, re.I)
    ok_cf = re.search(r'Confirmed|确认', joined, re.I)
    if len(hd) != 7 or not (ok_cm and ok_cf):
        why = []
        if len(hd) != 7:
            why.append('%d 列' % len(hd))
        if not ok_cm:
            why.append('缺 Commented')
        if not ok_cf:
            why.append('缺 Confirmed')
        c.add('FAIL', t['start'], '、'.join(why))
        c.detail = '%s；实际列头：%s' % ('、'.join(why), ' / '.join(hd))
    else:
        c.detail = '七列：%s' % ' / '.join(hd)
    return c


def _mod_name(text, ac=False):
    s = RE_MD_LINK_TEXT.sub(r'\1', text)
    s = RE_US_R_ID.sub('', s, count=1)
    s = re.sub(r'\s+', '', s)
    s = RE_MOD_SEP.sub('', s)
    if ac:  # 验收标题：任意位置的「(功能)验收(标准)」去掉，整个包在括号里的去括号（「US1-R2 验收（内容详情页）」）
        s = RE_MOD_SEP.sub('', RE_AC_WORD.sub('', s))
        s = re.sub(r'^[（(](.*)[）)]$', r'\1', s)
        s = RE_MOD_SEP.sub('', s)
    return s


def _first_col_ids(t):
    out = []
    for row in t['grid'][1:]:
        if row['cells'] and row['cells'][0].get('origin', True):
            m = RE_US_R_ID.search(RE_MD_LINK_TEXT.sub(r'\1', row['cells'][0]['text']))
            if m:
                out.append(('US%s-R%s' % m.groups(), row))
    return out


def check_l47(doc):
    c = Check('L47')
    skip = _history_lines(doc)
    ac = set()
    for h in doc.find_sections(RE_SEC_AC, (1,)):
        if doc.in_body[h['i']]:
            ac |= set(range(h['i'], h['end'] + 1))
    cand = [t for t in doc.tables if t['start'] not in ac and t['start'] not in skip and t['start'] not in doc.residual
            and _first_col_ids(t)]
    mt = next((t for t in cand if any(RE_SEC_MODMAP.search(h['text']) and h['i'] < t['start'] <= h['end']
                                      for h in doc.headings)), None)
    if mt is None:  # 没有「模块地图」标题：取功能需求章里第一个 US 标题之前、首列带 US-R 编号的表
        for h in [x for x in doc.find_sections(RE_SEC_FR, (1,)) if doc.in_body[x['i']]]:
            us1 = next((x['i'] for x in doc.headings if h['i'] < x['i'] <= h['end'] and x['level'] in (2, 3)
                        and RE_US_START.search(x['text'])), h['end'] + 1)
            mt = next((t for t in cand if h['i'] < t['start'] < us1), None)
            if mt is not None:
                break
    if mt is None:
        c.detail = '无模块地图'
        return c
    parts = []
    hd = mt['header']
    if RE_MAP_EXTRA.search(' '.join(hd)):
        c.add('WARN', mt['start'], '列头含研发重点 / 测试重点')
        parts.append('列头含「%s」：1.8.13 起三列（模块 / 一句话 / 本次）' % '、'.join(sorted(set(RE_MAP_EXTRA.findall(' '.join(hd))))))
    if len(hd) < 3:
        c.add('WARN', mt['start'], '%d 列 <3' % len(hd))
        parts.append('只有 %d 列：少列（模块 / 一句话 / 本次）' % len(hd))
    fr_heads, ac_names = {}, {}
    for h in doc.headings:
        if not doc.in_body[h['i']] or h['i'] in doc.residual or h['i'] in skip:
            continue
        m = RE_US_R_ID.search(h['text'])
        if not m:
            continue
        key = 'US%s-R%s' % m.groups()
        if h['i'] in ac:
            nm = _mod_name(h['text'], ac=True)
            if nm:
                ac_names.setdefault(key, nm)
        elif h['level'] in (2, 3, 4) and RE_US_R_HEAD.match(h['text']):
            fr_heads.setdefault(key, _mod_name(h['text']))
    for t in doc.tables:  # 验收章是表格形态时，首格以编号开头的行也比
        if t['start'] in ac:
            for key, row in _first_col_ids(t):
                if RE_US_R_HEAD.match(RE_MD_LINK_TEXT.sub(r'\1', row['cells'][0]['text'])):
                    nm = _mod_name(row['cells'][0]['text'], ac=True)
                    if nm:
                        ac_names.setdefault(key, nm)
    diff = []
    for key, row in _first_col_ids(mt):
        mp = _mod_name(row['cells'][0]['text'])
        got = [('地图', mp), ('标题', fr_heads.get(key)), ('验收', ac_names.get(key))]
        got = [(k, v) for k, v in got if v]
        ac_v = ac_names.get(key)
        ac_ok = not ac_v or any(ac_v in v or v in ac_v for k, v in got if k != '验收')  # 验收标题按包含比
        if len(set(v for k, v in got if k != '验收')) > 1 or not ac_ok:
            msg = '%s：%s' % (key, ' / '.join('%s「%s」' % (k, short(v, 14)) for k, v in got))
            c.add('WARN', row['line'], msg)
            diff.append(msg)
    if diff:
        parts.append('模块名不一致 %d 处：%s' % (len(diff), '；'.join(diff[:6])))
    col = find_col(hd, lambda h: '本次' in h)
    if col is not None:
        vals = [r['cells'][col]['text'] for r in mt['grid'][1:] if col < len(r['cells'])]
        if len(vals) >= 4 and len(set(vals)) == 1:
            c.add('INFO', mt['start'], '本次列无区分度')
            parts.append('「本次」列 %d 行同值「%s」：本次列无区分度' % (len(vals), short(vals[0], 12)))
    if c.findings and not any(f[0] == 'WARN' for f in c.findings):
        c.hits_override = None
    c.detail = '；'.join(parts) if parts else '%d 列 · %d 行，模块名一致' % (len(hd), len(mt['grid']) - 1)
    return c



# ---------------------------------------------------------------- L48 / L49（1.8.14 读者视角）

RE_CIRCLED = re.compile('[\u2460-\u2473]')  # ①–⑳
RE_COMPOUND = re.compile(r'[；;。]')
RE_PERIOD = re.compile(r'。')
# 引号与括注整段（判复合前剔除）：「」『』“”"" （）()；最内层先剔，循环到不再变
RE_QUOTED = re.compile(r'「[^「」]*」|『[^『』]*』|“[^“”]*”|"[^"\n]*"|（[^（）]*）|\([^()]*\)')
RE_LIST_BLOCK = re.compile(r'<(ul|ol)\b[^>]*>(?:(?!<(?:ul|ol)\b|</(?:ul|ol)\s*>).)*</\1\s*>', re.I | re.S)
RE_GROUP_LABEL = re.compile(r'^\**[^。；;，,：:]{1,16}\**\s*[：:]\s*\**$')


def _mask_quoted(u):
    """把引号 / 括注整段换成等长空格（保留位置，供按「；」切分时对齐原文）。"""
    prev = None
    while prev != u:
        prev = u
        u = RE_QUOTED.sub(lambda m: ' ' * len(m.group(0)), u)
    return u


def _split_outside(u, rx):
    """按 rx 切 u，但引号 / 括注内的分隔符不切。"""
    m = _mask_quoted(u)
    out, last = [], 0
    for x in rx.finditer(m):
        out.append(u[last:x.start()])
        last = x.end()
    out.append(u[last:])
    return out


def _is_label(u):
    return bool(RE_GROUP_LABEL.match(u.strip()))


def _outside_prose(raw):
    """格内列表外的散文：去掉 <ul>/<ol> 块（含嵌套）后各段去组名「X：」，合起来 ≥4 CJK 算一个单元。"""
    prev = None
    s = raw
    while prev != s:
        prev = s
        s = RE_LIST_BLOCK.sub(' \x01 ', s)
    s = re.sub(r'<(?:ul|ol|li)\b.*', ' \x01 ', s, flags=re.I | re.S)  # 未闭合列表：其后全归列表
    keep = [t for t in (cell_text(p) for p in s.split('\x01')) if t and not _is_label(t)]
    u = ' '.join(keep).strip()
    return u if len(RE_CJK.findall(u)) >= 4 else None


def _bullet_units(raw, pipe=False):
    """元素表一格的判定单元 → [(文本, 判定正则)]。格内有列表：每条 <li>（嵌套 <ul> 里的 li 各算一个，父 li 只算自己那层）+
    列表外散文一个，判「；」「;」「。」；格内无列表：管道表格内有 ①–⑳（07 §六 写法）时按圈号与「；」切、组名单元不算、
    只判「。」；其余（HTML 表 / 无圈号的管道格）整格一个，判「；」「;」「。」。链接本身（锚文本 + URL）先剔掉。"""
    raw = RE_LINKISH.sub(' ', raw)
    if re.search(r'<li\b', raw, re.I):
        units = [(cell_text(m.group(1)), RE_COMPOUND) for m in RE_LI.finditer(raw)]
        prose = _outside_prose(raw)
        if prose:
            units.append((prose, RE_COMPOUND))
    elif pipe and RE_CIRCLED.search(raw):  # 07 §六 降级写法：①–⑳ 衔接规则、组间用「；」衔接
        units = []
        for piece in RE_CIRCLED.split(cell_text(raw)):
            for x in _split_outside(piece, re.compile(r'[；;]')):
                x = x.strip()
                if x and not _is_label(x):
                    units.append((x, RE_PERIOD))
    else:
        units = [(cell_text(raw), RE_COMPOUND)]
    return [(u, rx) for u, rx in units if RE_CJK.search(u)]


def is_compound(u, rx=RE_COMPOUND):
    """先剔掉引号 / 括注整段，再看 rx（默认「；」「;」「。」）之后还有 ≥4 个 CJK = 另起了一句（句尾「。」与只有 ，、： 的不算）。"""
    m = _mask_quoted(u)
    for x in rx.finditer(m):
        if len(RE_CJK.findall(m[x.end():])) >= 4:
            return True
    return False


def is_long_bullet(u):
    """长 bullet 事实（不定级）：可见字 >40 且引号 / 括注外按「，」「,」切出 ≥3 个子句。"""
    if len(re.sub(r'\s+', '', u)) <= 40:
        return False
    return len([x for x in re.split(r'[，,]', _mask_quoted(u)) if x.strip()]) >= 3


def check_l48(doc):
    c = Check('L48')
    skip = _history_lines(doc) | _chap_lines(doc, RE_SEC_DATA) | _chap_lines(doc, RE_SEC_LOC)
    n_units, comp, rows_hit, tables, n_long = 0, [], {}, 0, 0
    for t in doc.tables:
        if t['start'] in doc.residual or t['start'] in skip or not is_element_table(t):
            continue
        tables += 1
        hd = t['header']
        fe = find_col(hd, lambda h: '说明' in h and '后端' not in h)
        be = find_col(hd, lambda h: '后端' in h and '说明' in h)
        el = find_col(hd, lambda h: '元素' in h)
        for row in t['grid'][1:]:
            name = row['cells'][el]['text'] if el is not None and el < len(row['cells']) else ''
            for col in (fe, be):
                if col is None or col >= len(row['cells']) or not row['cells'][col].get('origin', True):
                    continue
                cell = row['cells'][col]
                if col == be and RE_BE_EMPTY.match(cell['text'].strip()):
                    continue
                for u, rx in _bullet_units(cell['raw'], pipe=(t['kind'] == 'pipe')):
                    n_units += 1
                    if is_long_bullet(u):
                        n_long += 1
                    if is_compound(u, rx):
                        comp.append((cell['line'], name, u))
                        rows_hit.setdefault(id(row), []).append((cell['line'], name, u))
    if not n_units:
        if tables:
            c.detail = '%d 张元素表无说明单元' % tables
        return c
    ratio = len(comp) * 100.0 / n_units
    stat = '%d 张元素表 · 复合 bullet %d/%d %.0f%%（命中 %d 行）· 长 bullet %d（>40 字且 ≥3 个「，」子句）' % (
        tables, len(comp), n_units, ratio, len(rows_hit), n_long)
    if n_units >= 30 and ratio >= 35:
        sev = 'FAIL'
    elif n_units >= 30 and ratio >= 15:
        sev = 'WARN'
    else:
        sev = 'INFO'
    if sev == 'INFO':
        c.add('INFO', None, 'facts')
        c.hits_override = None
        c.detail = stat + ('（bullet <30 只给事实）' if n_units < 30 else '')
        if n_units < 30 and ratio >= 35:
            c.detail += '；样本少于 30 条不定级，按 05 ③ 人工核'
        return c
    for row_hits in sorted(rows_hit.values(), key=lambda x: x[0][0]):  # 行内多个只记一次
        i, name, u = row_hits[0]
        c.add(sev, i, '「%s」%d 条：%s' % (short(name, 8), len(row_hits), short(u, 24)))
    c.hits_override = len(comp)
    c.detail = '%s ≥%d%%：前 5 条：%s' % (stat, 35 if sev == 'FAIL' else 15,
                                       '；'.join('L%d「%s」' % (i + 1, short(u, 20)) for i, _, u in comp[:5]))
    return c


def check_l49(doc):
    c = Check('L49')
    ac = set()
    for h in doc.find_sections(RE_SEC_AC, (1,)):
        ac |= set(range(h['i'], h['end'] + 1))
    hits = []
    for k, h in enumerate(doc.headings):
        if h['level'] != 5 or not doc.in_body[h['i']] or h['i'] in doc.residual or h['i'] in ac or not _in_us_r(doc, h['i'], ac):
            continue
        end = doc.headings[k + 1]['i'] - 1 if k + 1 < len(doc.headings) else len(doc.lines) - 1
        tabs = [t for t in doc.tables if h['i'] < t['start'] <= end]
        if len(tabs) != 1 or not is_element_table(tabs[0]) or len(tabs[0]['grid']) - 1 != 1:
            continue
        # 1.8.14 盲审：只给事实（单场证据）——永不 WARN，也不再按图片豁免（弹窗漏行该补行，不是并表）
        hits.append(h)
        c.add('INFO', h['i'], '「%s」只有 1 行（%s）：单行板块：弹窗 / 真板块按 05 ⑤ 补行，非板块并进相邻表（02 板块指引）'
              % (short(h['text'], 10), _owner_us_r(doc, h['i'])))
    if hits:
        c.detail = '%d 个 ##### 板块只有 1 行元素表：%s' % (
            len(hits), '；'.join('L%d %s（%s）' % (h['i'] + 1, short(h['text'], 10), _owner_us_r(doc, h['i'])) for h in hits[:8]))
    return c


# ---------------------------------------------------------------- L50（2.1.0 公司配置出包）
RE_COMPANY_PH = re.compile(r'\{\{\s*company\.([A-Za-z0-9_.*…]*)\s*(?:\}\})?')


def check_l50(doc):
    c = Check('L50')
    hits = []
    for i, ln in enumerate(doc.lines):
        if i in doc.preamble or i in doc.residual:
            continue
        for m in RE_COMPANY_PH.finditer(ln):
            name = 'company.' + m.group(1).rstrip('.')
            hits.append((i, name))
            c.add('FAIL', i, '残留占位 {{%s}}' % name)
    if hits:
        c.detail = '%d 处：%s' % (len(hits), '；'.join('L%d {{%s}}' % (i + 1, n) for i, n in hits[:8])
                                  + (' …+%d' % (len(hits) - 8) if len(hits) > 8 else ''))
    return c


# ---------------------------------------------------------------- L51（2.2.0 前置区六条机械上限）
RE_FRONT_INC = re.compile(r'^\s*(?:\d+(?:\.\d+)*\s*)?(?:本期包含|本次包含)')  # 标题开头；同时含「模块地图」的不算（模块地图就是包含清单）
RE_FUNC_SPLIT = re.compile(r'[、/／;；]')
RE_FRONT_TERMS = re.compile(r'名词解释')
RE_FRONT_OUT = re.compile(r'本期不包含|本次不包含|Out\s*of\s*Scope', re.I)
RE_CIRCLED = re.compile(r'[①-⑳]')


def _ncjk(s):
    return len(RE_CJK.findall(s))


def _list_tops(doc, rng):
    """区间内顶层列表项：markdown 列表（最小缩进的列表符行，续行 / 嵌套并入上一条）+ HTML 行里的 <li>。返回 [[行号, 文本]]。"""
    tops, cur = [], None
    lst = [i for i in rng if doc.kind[i] == 'list' and RE_LIST.match(doc.lines[i])]
    base = min([len(doc.lines[i]) - len(doc.lines[i].lstrip()) for i in lst] or [0])
    for i in rng:
        ln = doc.lines[i]
        if doc.kind[i] == 'list':
            ind = len(ln) - len(ln.lstrip())
            if RE_LIST.match(ln) and ind <= base:
                cur = [i, RE_LIST.sub('', ln, count=1)]
                tops.append(cur)
            elif cur is not None:
                cur[1] += ' ' + ln.strip()
        elif doc.kind[i] == 'html' and re.search(r'<li\b', ln, re.I):
            for x in RE_LI.findall(ln):
                if cell_text(x):
                    tops.append([i, cell_text(x)])
    return tops


def _func_items(raw):
    """关联方「功能列表」格切条：<li> 各一条，列表外 ≥4 汉字的散文另算一条；无列表按 <br> 切。"""
    if re.search(r'<li\b', raw, re.I):
        items = [cell_text(x) for x in RE_LI.findall(raw)]
        rest = re.sub(r'<(ol|ul)\b.*?</\1\s*>', ' ', raw, flags=re.I | re.S)
        rest = cell_text(rest)
        if _ncjk(rest) >= 4:
            items.append(rest)
    else:
        items = [cell_text(x) for x in RE_BR.split(raw)]
    items = [RE_LIST.sub('', x, count=1).strip() for x in items if x.strip()]
    frags = []  # 2.2.0 盲审：顿号 / 斜杠 / 分号拼接的能力按片段计数（链接先剔，免得 URL 里的 / 被切）
    for x in items:
        frags += [y.strip() for y in RE_FUNC_SPLIT.split(RE_LINKISH.sub(' ', x)) if y.strip()]
    return items, frags


def check_l51(doc):
    c = Check('L51')
    zone, us1 = _front_zone(doc)
    if us1 is None:
        c.detail = '无 US 起点标题，前置区未计'
        return c
    heads = [h for h in doc.headings if h['i'] in zone and h['i'] not in doc.residual]
    ok = lambda i: i in zone and i not in doc.residual and not RE_FILL.search(doc.lines[i])

    def sec_tables(h):
        return [t for t in doc.tables if h['i'] < t['start'] <= min(h['end'], us1 - 1) and t['start'] in zone
                and t['start'] not in doc.residual and t['grid']]

    def data_rows(t):
        return [r for r in t['grid'][1:] if any(x['text'] for x in r['cells'] if x.get('origin', True))]

    items, parts = 0, []
    # a 本期包含 + 模块地图并存
    inc = [h for h in heads if RE_FRONT_INC.search(h['text']) and not RE_SEC_MODMAP.search(h['text'])]
    mp = [h for h in heads if RE_SEC_MODMAP.search(h['text'])]
    if inc and mp:
        c.add('FAIL', inc[0]['i'], '「%s」与「%s」并存：留模块地图' % (short(inc[0]['text'], 10), short(mp[0]['text'], 10)))
        items += 1
        parts.append('a 本期包含与模块地图并存')
    # b 名词解释 >3
    for h in [x for x in heads if RE_FRONT_TERMS.search(x['text'])][:1]:
        end = min(h['end'], us1 - 1)
        n_terms = (sum(len(data_rows(t)) for t in sec_tables(h))
                   + len(_list_tops(doc, [i for i in range(h['i'] + 1, end + 1) if ok(i)])))  # 表数据行 + 列表项合计
        if n_terms > 3:
            c.add('FAIL', h['i'], '名词解释 %d 条 >3' % n_terms)
            items += 1
            parts.append('b 名词解释 %d 条 >3' % n_terms)
    # c 本期不包含
    for h in [x for x in heads if RE_FRONT_OUT.search(x['text'])][:1]:
        end = min(h['end'], us1 - 1)
        rng = [i for i in range(h['i'] + 1, end + 1) if ok(i)]
        tops = _list_tops(doc, rng)
        if not tops:
            continue
        sub = []
        if len(tops) > 6:
            c.add('FAIL', tops[0][0], '本期不包含 %d 条 >6' % len(tops))
            sub.append('%d 条 >6' % len(tops))
        longs = [(i, _ncjk(strip_tags(s))) for i, s in tops if _ncjk(strip_tags(s)) > 30]
        if longs:
            for i, n in longs:
                c.add('FAIL', i, '本期不包含一条 %d 字 >30' % n)
            sub.append('%d 条 >30 字（%s）' % (len(longs), '、'.join('L%d %d 字' % (i + 1, n) for i, n in longs[:5])))
        last = max(i for i, _ in tops)
        tail = [i for i in rng if i > last and doc.kind[i] in ('prose', 'html', 'quote')
                and _ncjk(strip_tags(doc.lines[i])) and not re.search(r'<li\b', doc.lines[i], re.I)]
        if tail:
            c.add('FAIL', tail[0], '本期不包含列表后有收尾段落')
            sub.append('列表后有段落（L%d）' % (tail[0] + 1))
        if sub:
            items += len(sub)
            parts.append('c 本期不包含 ' + '、'.join(sub))
    # d 成功指标口径 / 行数
    for h in [x for x in heads if RE_SEC_METRIC.search(x['text'])][:1]:
        tabs = sec_tables(h)  # 2.2.0 盲审：主表 + 护栏表等拆表写法合计
        if not tabs:
            continue
        t = tabs[0]
        rows = [r for x in tabs for r in data_rows(x)]
        sub = []
        longs = []
        for x in tabs:
            col = find_col(x['header'], lambda s: '口径' in s)
            if col is None:
                continue
            longs += [(r['line'], _ncjk(r['cells'][col]['text'])) for r in data_rows(x)
                      if col < len(r['cells']) and _ncjk(r['cells'][col]['text']) > 40]
        if longs:
            for i, n in longs:
                c.add('FAIL', i, '统计口径 %d 字 >40' % n)
            sub.append('口径 %d 格 >40 字（%s）' % (len(longs), '、'.join(str(n) for _, n in longs)))
        if len(rows) > 3:
            c.add('FAIL', t['start'], '指标 %d 行 >3' % len(rows))
            sub.append('指标 %d 行 >3' % len(rows))
        if sub:
            items += len(sub)
            parts.append('d 成功指标 ' + '、'.join(sub))
    # e 关联方功能列表
    bad = []
    for h in [x for x in heads if RE_SEC_DEPS.search(x['text'])][:1]:
        for t in sec_tables(h):
            col = find_col(t['header'], lambda s: '功能' in s)
            if col is None:
                continue
            for r in data_rows(t):
                if col >= len(r['cells']) or not r['cells'][col].get('origin', True):
                    continue
                its, frags = _func_items(r['cells'][col]['raw'])
                over = [x for x in its if _ncjk(x) > 20]
                its = frags  # 计数按片段（列表项再按 、/ ；切）
                if len(its) > 2 or over:
                    who = short(r['cells'][0]['text'], 8) if r['cells'] else '?'
                    c.add('FAIL', r['line'], '「%s」功能列表 %d 条%s' % (who, len(its), '，%d 条 >20 字' % len(over) if over else ''))
                    bad.append('%s %d 条%s' % (who, len(its), '/%d 条超长' % len(over) if over else ''))
    if bad:
        items += 1
        parts.append('e 功能列表超限 %d 方（%s）' % (len(bad), '；'.join(bad[:4])))
    if items:
        c.hits_override = items
        c.detail = '%d 项：%s' % (items, ' · '.join(parts))
    return c


# ---------------------------------------------------------------- L52（2.2.2 组件复用拆写）
L52_OVERLAP = 0.70


def _us_r_element_sets(doc):
    """验收章外每个 US-R 段 → (标题, 「元素」列去空白后的集合；段内没有元素表为 None)，按文档顺序。"""
    ac = set()
    for h in doc.find_sections(RE_SEC_AC, (1,)):
        ac |= set(range(h['i'], h['end'] + 1))
    out = []
    for h in doc.headings:
        if (h['level'] > 3 or not doc.in_body[h['i']] or h['i'] in doc.residual or h['i'] in ac
                or not RE_US_R_HEAD.match(h['text'])):
            continue
        elems, has_table = set(), False
        for t in doc.tables:
            if not (h['i'] < t['start'] <= h['end']) or t['start'] in doc.residual or not is_element_table(t):
                continue
            col = find_col(t['header'], lambda x: '元素' in x)
            if col is None:
                continue
            has_table = True
            for row in t['grid'][1:]:
                if col < len(row['cells']):
                    key = _l52_key(row['cells'][col]['text'])
                    if key:
                        elems.add(key)
        out.append((h, elems if has_table and elems else None))
    return out


def _l52_key(text):
    """元素名归一：NFKC（全角 / 半角括号等）→ 去空白与 markdown 标记 * ` _ ~ → 小写。"""
    return re.sub(r'[\s*`_~]+', '', unicodedata.normalize('NFKC', text or '')).lower()


def check_l52(doc):
    c = Check('L52')
    secs = _us_r_element_sets(doc)
    pairs = []
    for (h1, a), (h2, b) in zip(secs, secs[1:]):
        if not a or not b:
            continue
        common, only_a, only_b = len(a & b), len(a - b), len(b - a)
        rate = common / float(len(a | b))
        near = common >= 4 and only_a <= 1 and only_b <= 1
        if rate >= L52_OVERLAP or near:
            x, y = _us_r_label(h1), _us_r_label(h2)
            pct = int(round(rate * 100))
            note = '%d%%' % pct if not (only_a or only_b) else '%d%%（%s 多 %d 行 / %s 多 %d 行）' % (pct, x, only_a, y, only_b)
            c.add('WARN', h2['i'], '%s 与 %s 元素列重合 %s，疑似同一组件按落点拆写（02 §US-R 切分粒度「例外·组件复用」）'
                  % (x, y, note))
            pairs.append('%s/%s %s' % (x, y, note))
    if pairs:
        c.detail = '%d 对相邻 US-R 元素列疑似同一组件（≥70%% 或各差 ≤1 行）：%s' % (len(pairs), '；'.join(pairs[:8]))
    return c


def _us_r_label(h):
    m = RE_US_R_ID.search(h['text'])
    return 'US%s-R%s' % m.groups() if m else short(h['text'], 8)


def reader_load(doc, cjk):
    """L19 读者负荷事实：US-R 模块段（### US-R 到下一个 ≤3 级标题，验收章内不算）CJK 中位 / 最大、验收章 CJK、埋点章 CJK 与占比。"""
    def cjk_of(a, b):
        return sum(len(RE_CJK.findall(strip_tags(doc.lines[i]))) for i in range(a, b + 1) if doc.in_body[i])
    ac_secs = [h for h in doc.find_sections(RE_SEC_AC, (1,)) if doc.in_body[h['i']]]
    ac = set()
    for h in ac_secs:
        ac |= set(range(h['i'], h['end'] + 1))
    mods = [cjk_of(h['i'], h['end']) for h in doc.headings
            if h['level'] == 3 and doc.in_body[h['i']] and h['i'] not in ac and RE_US_R_HEAD.match(h['text'])]
    data = [h for h in doc.find_sections(RE_SEC_DATA, (1,)) if doc.in_body[h['i']]]
    data.sort(key=lambda h: (not re.search(r'Data\s*Requirements', h['text'], re.I), h['i']))
    track = cjk_of(data[0]['i'], data[0]['end']) if data else 0
    med = None
    if mods:
        srt = sorted(mods)
        m = len(srt) // 2
        med = srt[m] if len(srt) % 2 else int(round((srt[m - 1] + srt[m]) / 2.0))
    return {'module_cjk_median': med, 'module_cjk_max': max(mods) if mods else None,
            'ac_cjk': sum(cjk_of(h['i'], h['end']) for h in ac_secs),
            'tracking_cjk': track, 'tracking_cjk_ratio': round(track * 1.0 / cjk, 3) if cjk else None}


# ---------------------------------------------------------------- 汇总与输出
# ---------------------------------------------------------------- 汇总与输出

def run(text, profile):
    doc = Doc(text)
    track_lines = doc.table_line_set(is_track_table)
    checks = [check_l01(doc, profile), check_l02(doc), check_l03(doc, track_lines), check_l04(doc),
              check_l05(doc), check_l06(doc), check_l07(doc), check_l08(doc), check_l09(doc), check_l10(doc),
              check_l11(doc), check_l12(doc, track_lines), check_l13(doc), check_l14(doc), check_l15(doc)]
    l18, fr = check_l18(doc)
    checks.append(check_l16(doc, len(fr)))
    checks.append(check_l17(doc))
    checks.append(l18)
    cjk = cjk_count(doc)
    load = reader_load(doc, cjk)
    checks.append(check_l19(doc, cjk, len(fr), load))
    checks.append(check_l20(doc))
    l22, ac_stat = check_l22(doc)
    l24, track_prose = check_l24(doc)
    checks += [l22, l24, check_l25(doc), check_l26(doc), check_l27(doc), check_l28(doc)]
    l29, tech_n = check_l29(doc, track_lines)
    l30, dangle_n = check_l30(doc, track_lines)
    checks += [l29, l30, check_l31(doc, track_lines), check_l32(doc), check_l33(doc), check_l34(doc), check_l35(doc)]
    l36, support_n = check_l36(doc)
    checks += [l36, check_l37(doc), check_l38(doc)]
    l39, front_n = check_l39(doc)
    checks += [l39, check_l40(doc), check_l41(doc), check_l42(doc), check_l43(doc)]
    checks += [check_l44(doc), check_l45(doc), check_l46(doc), check_l47(doc), check_l48(doc), check_l49(doc)]
    checks.append(check_l50(doc))
    checks.append(check_l51(doc))
    checks.append(check_l52(doc))
    checks.sort(key=lambda ch: ch.id)
    summary = {s: sum(1 for ch in checks if ch.status == s) for s in ('FAIL', 'WARN', 'INFO', 'OK')}
    summary['cjk_chars'] = cjk
    summary['acceptance_avg'], summary['acceptance_max'] = ac_stat if ac_stat else (None, None)
    summary['tracking_prose_cjk'] = track_prose
    summary['tech_terms'] = tech_n
    summary['dangling_rules'] = dangle_n
    summary['support_parties'] = support_n
    summary['front_cjk'] = front_n
    summary['module_cjk_median'] = load['module_cjk_median']
    summary['module_cjk_max'] = load['module_cjk_max']
    summary['tracking_cjk_ratio'] = load['tracking_cjk_ratio']
    return doc, checks, summary


def md_cell(s):
    return str(s).replace('\n', ' ').replace('|', '\\|')


def fmt_lines(ls):
    if not ls:
        return '—'
    s = ', '.join(str(x) for x in ls[:5])
    return s + (' …+%d' % (len(ls) - 5) if len(ls) > 5 else '')


def dash(v):
    return '—' if v is None else v


def render_table(path, profile, doc, checks, summary):
    out = ['prd_lint · %s · profile=%s · %s' % (path, profile, '导出稿' if doc.is_export else '起草稿'), '',
           '| 编号 | 检查 | 状态 | 命中数 | 位置 | 修法 |', '|---|---|---|---|---|---|']
    for ch in checks:
        name = ch.name + ('：' + ch.detail if ch.detail else '')
        hits = '—' if ch.hits is None else ch.hits
        out.append('| %s | %s | %s | %s | %s | %s |' % (
            ch.id, md_cell(name), ch.status, hits, md_cell(fmt_lines(ch.lines())), md_cell(ch.fix)))
    out.append('')
    out.append('FAIL %d · WARN %d · INFO %d · 正文 CJK 字数 %d · 验收 avg %s / max %s · 埋点表外 %s 字 · 技术词 %d · 悬空规则 %d'
               ' · 支持方入表 %d · US 前 %s 字' % (
                   summary['FAIL'], summary['WARN'], summary['INFO'], summary['cjk_chars'], dash(summary['acceptance_avg']),
                   dash(summary['acceptance_max']), dash(summary['tracking_prose_cjk']), summary['tech_terms'],
                   summary['dangling_rules'], summary['support_parties'], dash(summary['front_cjk'])))
    return '\n'.join(out)


def main(argv=None):
    ap = argparse.ArgumentParser(description='PRD 确定性 lint（只测事实、不做判断；FAIL 必须修，WARN 按 05 判）')
    ap.add_argument('path', help='PRD markdown 文件')
    ap.add_argument('--json', action='store_true', help='输出与表格同构的 JSON')
    ap.add_argument('--profile', choices=('standard', 'light'), default='standard')
    args = ap.parse_args(argv)
    try:
        with open(args.path, 'r', encoding='utf-8', errors='replace') as fh:
            text = fh.read()
    except (IOError, OSError) as e:
        sys.stderr.write('prd_lint: 读不了文件 %s（%s）\n' % (args.path, e))
        return 2
    doc, checks, summary = run(text, args.profile)
    code = 1 if summary['FAIL'] else 0
    if args.json:
        payload = {'file': args.path, 'profile': args.profile, 'doc_kind': 'export' if doc.is_export else 'draft',
                   'checks': [ch.to_dict() for ch in checks], 'summary': summary, 'exit_code': code}
        sys.stdout.write(json.dumps(payload, ensure_ascii=False, indent=2) + '\n')
    else:
        sys.stdout.write(render_table(args.path, args.profile, doc, checks, summary) + '\n')
    return code


if __name__ == '__main__':
    sys.exit(main())
