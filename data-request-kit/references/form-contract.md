# 数分需求表单契约（快照 2026-08-27，线上为准）

表单：数分需求表单 Data Request Form
坐标（share_token → base / 表「需求池」，约 9.6k 条，全公司共用）住公司配置 `~/.prd-authoring-kit/library.json` 的 `forms.data_request`（`npx pm-ai-kit config <飞书配置文档链接>` 导入；2.1 起不随公开包分发）。
换表单改配置文档即可；测试可用环境变量 `DR_SHARE_TOKEN / DR_BASE_TOKEN / DR_TABLE_ID` 顶掉。任何时候以 `python3 scripts/dr.py contract` 的线上结果为准，本文是快照。

## 字段

| 字段 id | 表单问题标题（提交 key） | 需求池表字段名 | 类型 | 必填 | 值格式 / 选项 |
|---|---|---|---|---|---|
| fldbI4wJwY | 需求标题 Summary | 需求标题 | text | 是 | 字符串 |
| fld8NmczHW | 需求背景 Background | 需求背景 | text | 是 | 字符串，可换行 |
| fldj3vLBAv | 需求目标分类 | （API 读不到） | 🔒 单选 | 是 | 工作汇报 / 定期监控 / 长期专项 / 短期分析 / 探索性分析（用户从下拉里念的，2026-08-27） |
| fldR4Fk78B | 需求要达成的目标 Goals | 需求目标 | text | 是 | 表单提示语：需要体现需求的目标，定义数据产出的意义以及需要数分提供的策略建议方案及后续可能的业务落地动作 |
| fldoFjdKhY | 需求描述 Description | 需求描述 | text | 是 | 字符串，可换行 |
| fldMmaRIo1 | 需求优先级 Priority | 优先级 | 单选 | 是 | P0 / P1 / P2 |
| fldBhWIowq | 需求类型 Requirement Type | 需求类型 | 单选 | 是 | 取数需求 Ad-hoc Data Request / 分析需求 Analysis Request / 看板需求 Dashboard Request / 「发奖需求 Award Request 」(末尾有空格) / 其他 Others / 数分表变更 |
| fldLMvAnOu | 需求发起人 Requestor | 需求发起人 | 人员（单） | 是 | `[{"id":"ou_…"}]` |
| fldOLY8apP | 业务线 Business Line | 业务线 | 单选 | 是 | 现货 Spot / 合约 Contract / 中台运营 Middle Platform Operation / 国家增长 Regional Growth / 直客增长 Direct User Growth / 付费 Paid / 人人代理 User Affiliate / SEO / 客服 Customer Service / 市场 Marketing / 法币 Fiat / 产品 Product / UIUX / 其他 Others / 数分 / 现货美股 Spot US Stocks |
| flds2jDgn4 | 数分对接人 Data Analysis | 数分对接人 | 人员（多） | 是 | `[{"id":"ou_…"}, …]` |
| fldZ8OSZqj | 预期交付时间 Expected delivery time | 预期交付时间 | 日期 | 是 | `yyyy-MM-dd HH:mm:ss`；spec 只写 `YYYY-MM-DD`，脚本补 `00:00:00` |
| fldYyg2Hkr | 交付形态 | （API 读不到） | 🔒 单选 | 是 | 看板 / 报告（含落地建议） / 模板 / 表格（用户从下拉念的 + probe 核验，2026-09-02）。注意全称含全角括号，「报告」「模版」都不认 |
| fldxg6qyC2 | 附件 Attachments | 附件 | 附件 | 否 | spec.attachments 本地路径数组；脚本会带 `--base-token` 让 lark-cli 上传 |

## 值格式的四条规矩（都是实测报错踩出来的）

1. **key 用表单问题标题全称。** 传字段 id → `unknown field name: "fld8NmczHW"`；传需求池表字段名 → 大部分能过，但会在带英文后缀的字段（「数分对接人 Data Analysis」「需求要达成的目标 Goals」）报 unknown field name。校验是逐字段、顺序不定，所以报错只会露出一个，修完可能再露下一个——脚本按字段 id 映射到线上标题，一次到位。
2. **单选 = 纯字符串。** 传数组 → `expected option name string, got []interface {}`。`+record-batch-create` 的 CellValue 规范反而要求数组，两套规范别混。
3. **日期 = `yyyy-MM-dd HH:mm:ss`。** 只到 `HH:mm` → `unsupported datetime format`。服务端按 UTC 解释，回读显示 `2026-09-04T08:00:00.000+08:00`，日期本身正确；表单展示格式是 `yyyy/MM/dd`。
4. **校验顺序：选项名转换 → 必填检查。** 这是 probe 安全的根据。

## 🔒 被字段权限锁住的两个字段

「需求目标分类」「交付形态」在 Base 里设了字段级权限：`+field-list` 显示 "No access to field"，原生 `bitable/v1 …/fields` 返回 `type: 403, property: null`，`+field-search-options` 报 not support，`+record-list` 会把这两列静默丢掉（连别人填过什么都看不到）。**但 form-submit 按名字写得进去，且它们都是必填**——所以必须知道确切选项名。

拿选项名的三条路：
- 让用户打开表单看下拉，把选项原样念给你（最快、最准）。
- `python3 scripts/dr.py probe <字段标题> <候选…>`：脚本故意把**另一个**必填字段留空，候选合法时服务端只会回 `submit data[fldXXX] must required`，结构上不可能落库；跑前先用一个必然无效的值验证"预言机"在工作。每个候选是一次失败的提交调用，无副作用；但盲猜命中率低（2026-08-27 猜了 20 个中文常见值全 miss），适合验证而不是发现。
- 历史记录：读不到，此路不通。

脚本里的 `LOCKED_KNOWN_OPTIONS` 是最后一次核验结果，提交报 `option "X" not found in field options` 就说明线上改了，按上面重新拿。

## 错误对照

| 报错里含 | 原因 | 处理 |
|---|---|---|
| `unknown field name` | key 不是表单问题标题 | 跑 `contract`，让脚本重新映射；别手拼 payload |
| `expected option name string` | 单选传了数组 | 传字符串 |
| `unsupported datetime format` | 日期格式 | `yyyy-MM-dd HH:mm:ss` |
| `submit data[fldXXX] must required` | 必填缺失 | 看 spec 哪个键空了；线上新增必填用 `extra` |
| `option "X" not found in field options` | 选项名不对 | 全称、注意末尾空格；锁字段按上节重新拿 |
| `missing_scope` | 缺授权 | 走 lark-shared 的 device-code 流程；不要为搜消息/搜文档去申请宽 scope |
| `needs_refresh` | 用户 token 待刷新 | 下一次调用自动刷新，重试一次 |
| 提交 `ok:true` 但回查无记录 | 索引延迟 | 稍后 `precedent --keyword <标题>` 再查 |

错误码 800004006 = 参数校验类（前五行），800004025 = 必填缺失。

## 回查与状态

提交成功的返回只有 `{"can_submit_again": true}`，没有 record_id。脚本用「需求标题 == 标题 且 需求发起人 contains 当前用户」在需求池回查，取 markdown 输出的 `_record_id` 列（`--format json` 的矩阵不带 record_id）。

「状态」字段的选项：需求业务审核 / 未启动 / 进行中 / 数仓接数中 / 智齿开发中 / 待验收 / 已交付 / 取消 / 暂停 / leader评审不通过。新单落地是「未启动」——这不是失败。数分标「已交付」后，`交付天数`、`delay天数` 由公式按预期交付时间算，所以补单的预期交付时间不要按惯性往后推。

## 先例的可见范围

需求池开着 Base 高级权限：按行过滤后，API 只能看到当前用户有权看的记录（2026-09 实测：全池约 9.7k 条，产品线账号只看得到 462 条，全是「业务线=产品 Product」）。所以 `precedent` 搜不到 ≠ 没人提过——数分自己在「数分」业务线下建的表变更单、别的业务线的同主题单都看不见。判断"是否重复"时把这句写进确认轮："我只能看到产品线的单，数分那边有没有已经在做的？"

## 需求池里还能读到的字段（先例挖掘用）

状态、提交时间、创建人、创建人.部门、当日交付需求、备注、满意度、完成时间、交付天数、delay天数、预期交付时间。
读取：`+record-list --filter-json … --format json` 返回矩阵 `data.data` + `field_id_list`；人员字段回读为 `[{"id","name"}]`，单选回读为 `["选项"]`。人员过滤要写 `["需求发起人","contains",[{"id":"ou_…"}]]`，写名字会报 "The user filter value is invalid"。
