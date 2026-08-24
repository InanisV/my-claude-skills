# 字段模型与 payload 形状（2026-08 createmeta 实测）

plan.json 里 `fields` 直接写 Jira REST 原生 payload。形状规则：

| 字段类型 | 形状 | 例 |
|---------|------|----|
| 单选/下拉 | `{"value": "选项文本"}` | `"customfield_16301": {"value": "是"}` |
| 人员 | `{"name": "username"}` | `"assignee": {"name": "noah.zhan"}`（username 用 `user-search` 查，不是显示名） |
| 组件/版本 | `[{"name": "..."}]` | `"components": [{"name": "iOS-公共模块-首页"}]` |
| 史诗链接 | 裸字符串 | `"customfield_10102": "APP-24564"` |
| 优先级 | `{"name": "P1+"}` | 允许值 P0/P1+/P1/P2/P3/P4 |
| description | 裸字符串（wiki 标记） | 见下方 description 规范 |

## APP 故事（issuetype=故事，主卡；Android 卡复制后仅换 3 处）

**必填 8 个选择题**（不填 API 直接报错）：

| 字段 | id | 允许值 | 默认答案（可被 PRD/用户覆盖） |
|------|----|--------|------------------------------|
| 依赖交付情况 | customfield_11506 | 无需依赖 / 依赖已交付 / 依赖未交付 | 无需依赖；有后端/AIL 依赖时=依赖未交付 |
| 是否需要埋点 | customfield_16301 | 是 / 否 | 看 PRD 埋点章节 |
| 是否需要UI | customfield_11530 | 是 / 否 | 有视觉改动=是 |
| 是否涉及新页面 | customfield_15401 | 是 / 否 | 看 PRD |
| 是否需要国际化 | customfield_11531 | `不需要␣`（⚠️**尾部有一个空格**，见下方）/ 需要且英文文案已校对 / 需要但英文文案暂未校对 | 有文案=需要且英文文案已校对 |
| 是否涉及响应式 | customfield_12506 | 是 / 否 | 否（APP 需求几乎恒否） |
| 是否需要APP端产品介入 | customfield_17100 | 需要（业务产品选填）/ 不需要（业务产品选填）/ 已审核（APP产品选填） | 已审核（本人即 APP 产品时）|
| 业务板块（需求受益方）| customfield_16706 | 35 选项 | **无默认值，每次必须判断**，见下方红线 |

### ⚠️ 选项值必须与 allowedValues **逐字一致**（含首尾空格）

Jira 按字面文本匹配选项，差一个空格就报 `HTTP 400 {"errors":{"<cf>":"Option id 'null' is not valid"}}`，**apply 停在第一张卡**（好在不会建出半张卡，修完重跑即可）。已实测确认的两个坑：

| 字段 | 看起来是 | 真身（逐字） | 备注 |
|------|---------|-------------|------|
| 是否需要国际化 cf_11531 | `不需要` | `不需要 ` | 尾部 1 个空格。2026-08-24 建 APP-39165/39166 时踩到 |
| 业务板块（受益方）cf_16706 | `前台 - SEO - Jackie` | `前台  - SEO - Jackie` | 「前台」后面是 **2 个空格**（同组其余选项都是 1 个） |

其余 APP/WEB 必填项的选项值均已于 2026-08-24 用 editmeta 全量比对，无空格异常。**新增/拿不准的选项值一律先查真身**：

```bash
# 读一张同项目同类型的已有卡，拿该字段的 allowedValues 原文（repr 能看出空格）
python3 - <<'EOF'
import json,os,urllib.request
env=json.load(open(os.path.expanduser("~/.claude/settings.json")))["env"]
r=urllib.request.Request(env["JIRA_URL"].rstrip('/')+"/rest/api/2/issue/APP-38357/editmeta",
                         headers={"Authorization":"Bearer "+env["JIRA_PERSONAL_TOKEN"]})
m=json.load(urllib.request.urlopen(r))["fields"]
for a in m["customfield_11531"]["allowedValues"]: print(repr(a["value"]))
EOF
```

执行器已内置这道软校验：plan 里的值 strip 后能匹配、原样匹配不上时，`validate` 会直接指出「首尾有空格」，不用等 apply 报 400。

### 🔴 红线：受益方（customfield_16706）不许想当然

组织纪律（leader Yoki 2026-08 全员强调，此前已出现大面积错填）：**谁收益填谁**。这个字段决定人力成本记在哪个团队账上，是**定额消费**——季末会回溯审计"这些人力都花在哪了"，填错等于让别人替你的需求埋单。

**这是本 kit 唯一的硬闸：必须由使用 kit 的产品本人亲口确认，AI 才能代写。** 产品没明确回答就停下来问，不许自己推断着往下走；`plan.meta.beneficiary_confirmed_by` 和 `beneficiary_rationale` 缺任一项，validate 报 ERROR、apply 建不了卡。这两个字段只能在拿到用户明确答复后填，**不许 AI 自己编一个确认人绕过闸门**。

判定顺序：

1. **这个需求做成后，业务价值归谁？** 归某条业务线（合约/现货/理财/钱包/预测市场…）就填那条线。
2. **产品自提的需求**：能说服业务方为它埋单（业务方认可这是他们要的、愿意计入其配额）→ 挂业务方；说服不了 → **只能挂产品线**（`产品 - Ealy` 等），消耗产品自己的定额。
3. 拆分单/关联卡：**不许直接照抄主卡**。主卡的值只是线索，必须单独向用户确认——真实案例：广场主卡 WEB-18813 填的是 `产品 - Ealy`，而正确答案是 `AI - Ealy`，照抄就把同一个错误复制了 7 遍（2026-08-13，事后用 `set-beneficiary` 批量纠正）。

禁止事项：

- ❌ 不许用"历史上最常填的值"当默认值（本 kit 曾犯此错）
- ❌ 不许从需求名/所属项目/Epic 想当然推断（例：挂在 AI Epic 下 ≠ 受益方就是 AI 线）
- ❌ 不许照抄相似卡而不做判断
- ✅ 判不准就问用户，并把判定依据写进 `plan.meta.beneficiary_rationale`（validate 会检查；依据会随计划表展示给用户复核）

**房规常填**（非必填但每卡都带）：

| 字段 | id | 值 |
|------|----|----|
| description | — | PRD lark 链接（见规范）|
| 史诗链接 | customfield_10102 | 问用户，近期默认 `APP-24564`（AI智能推荐专项）|
| Priority | priority | 默认 P1+（历史 452/598）|
| 需求类别 | customfield_11319 | 恒 `业务需求` |
| 是否为原生需求 | customfield_12002 | APP 原生卡=`该需求是原生需求`；H5 嵌 APP 的派生卡=`该需求是派生需求` |
| Component/s | components | 端×模块，见组件表 |
| Fix Version/s | fixVersions | 建卡占位：`iOS_待评审 & 待排期` / `安卓_待评审 & 待排期` / `Flutter_待评审 & 待排期` |

**Android 卡与 iOS 卡的差异**：summary【iOS】→【Android】；components iOS-xxx → 安卓-xxx；fixVersions iOS_ → 安卓_。其余字段原样复制。

**别填**（机器人管，执行器黑名单）：开发者(cf_10400)、测试负责人(cf_10500)、UI负责人(cf_11402)、期望设计完成(cf_11941)、排优日期(cf_16102)、工作量(cf_12604/16404)、assignee（故事卡的 assignee 由 autotask 填）。

## 组件表（APP，43 个允许值节选常用）

| 业务线 | iOS | Android | Flutter |
|--------|-----|---------|---------|
| AI/首页/广场 | iOS-公共模块-首页 | 安卓-公共模块-首页 | — |
| 合约 | iOS-交易模块-合约 | 安卓-交易模块-合约 | Flutter-交易模块-合约 |
| 现货 | iOS-交易模块-现货 | 安卓-交易模块-现货 | Flutter-交易模块-现货 |
| 行情 | iOS-交易模块-行情 | 安卓-交易模块-行情 | — |
| K线 | iOS-公共模块-k线 | 安卓-公共模块-k线 | — |
| 资产 | iOS-资产模块-资产 | 安卓-资产模块-资产* | Flutter-资产模块-资产 |
| 个人中心 | iOS-公共模块-个人中心 | 安卓-公共模块-个人中心 | — |
| 其他（红包/H5/推送等）| iOS-公共模块-其他（红包/H5/消息推送/小组件/商店管理）| 安卓-公共模块-其他（红包/H5/消息推送/小组件/商店管理）| — |

\* `安卓-资产模块-资产` **在允许值表中是存在的**（2026-08-24 editmeta 复核，此前本表记为「不存在」有误）。但安卓侧资产已迁 Flutter，实际该用哪个组件按需求落在哪套代码上定，拿不准就问研发/用户。组件名必须与允许值逐字一致。

## 子任务：UI设计任务 / 国际化任务（挂 iOS 主卡）

| 卡 | 必填 | 房规填法 |
|----|------|---------|
| UI设计任务 | summary/project/issuetype/parent | summary=【UI设计】【业务线】需求名；`assignee`+`任务执行人(customfield_10812)` 都=设计师 username；priority 同主卡 |
| 国际化任务 | 同上 | summary=【国际化】【业务线】需求名；`assignee`=建卡人自己（whoami 的 name）；priority 同主卡 |

parent 由执行器用 `parent_ref` 自动回填，plan 里不用写 fields.parent。

## WEB/H5 故事（issuetype=故事，project=WEB）

**必填 9 个**：业务板块受益方(cf_16706)、是否需要UI(cf_11530)、是否涉及新页面(cf_15401)、是否需要埋点(cf_16301)，外加 WEB 特有：

| 字段 | id | 允许值 | 默认 |
|------|----|--------|------|
| 需求类别 | customfield_11319 | 业务需求/支撑需求/客服需求/技术需求… | 业务需求 |
| 需求归属端 | customfield_11519 | 前端 / 后端 / 前后端 / 配置变更 | 前端 |
| 是否是合规站 | customfield_17200 | 是 / 否 | 否 |
| 是否涉及运营配置 | customfield_15700 | 是 / 否 | 看 PRD 有无后台配置 |
| 是否需要SEO | customfield_12902 | 无需SEO / 需SEO判断 / 有公开落地页 | 无需SEO |

常填：description=PRD 链接、史诗链接、priority、是否为原生需求（H5 嵌 APP=`该需求是派生需求`）。组件：首页业务 / 基建 / 性能（就这 3 个）。**不填 fixVersions**（WEB 建单界面没这字段）。UI/国际化/埋点子任务全部自动生成，一个都不建。

## description 规范（wiki 标记，不是 markdown）

单 PRD：直接贴裸链接。多 PRD（大需求）用带标题链接、一行一个：

```
PRD 总则：[实时交易广场 · PRD 总则|https://l7jipx1bfq.larksuite.com/wiki/xxx]
后台部分：[【广场】MEXC广场 1.0后台 PRD|https://l7jipx1bfq.larksuite.com/wiki/yyy]
APP/H5 部分：[【H5】MEXC广场 1.0|https://l7jipx1bfq.larksuite.com/wiki/zzz]
```
