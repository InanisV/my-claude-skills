---
name: dify-workflow-architect
description: 设计 Dify AI 工作流的系统化方法论 - 帮助 Tom 从产品需求出发，设计 LLM + Code 协作的多节点工作流。覆盖文档处理类需求（PRD/合同/会议纪要 → 结构化产出，如埋点表/任务卡/用户故事）、跨平台集成（Lark/飞书/Notion API、Web Hook）、错误处理与兜底、迭代式版本管理、PM 与开发协作的最佳实践。触发时机（宁可多触发也不要漏触发）：- 用户说"做个 Dify 工作流"、"AI 工作流"、"自动化处理 X 文档"、"PRD 转 X"、"自动生成 Y 表" - 用户在迭代现有 Dify 工作流（修改节点、调整 prompt、加新分支）- 用户讨论 LLM + Code 配对、节点架构、工作流分层 - 用户对接 Lark/飞书/Notion/Jira 等外部平台到 Dify - 用户讨论 Dify workflow yml / DSL / 节点输入输出 - 用户问"这个工作流怎么设计"、"流程跑不通"、"plugin 报错" 不要用于：单纯写 LLM prompt（用 prompt-engineering 类 skill），简单的一次性 LLM 调用脚本，数据科学项目（用 alpha-lab），文档创作（用 ealy-pitch 等）。
---

# Dify AI 工作流设计方法论

## 核心理念

**工作流 ≠ 一个大 LLM 干所有事**。AI 工作流的本质是 **LLM 和 Code 分工流水线**：
- **LLM 负责语义、不确定性、灵活泛化**
- **Code 负责结构、确定性、模板渲染**

LLM 强迫做 Code 的事 → 输出格式不稳定、字段对不齐、容易漏字段。
Code 强迫做 LLM 的事 → 关键词检测会误命中（如 "tab" 包含 "ab"），泛化能力差。

工作流设计的第一性原则是 **职责正确分工**。

---

## 第一原则：LLM vs Code 分工

### LLM 适合做
- **语义抽取**：从自然语言中识别"卡片"、"按钮"、"模块"
- **边界判断**：同时具备多种特征时判断倾向（如 "这是 Element 还是 Resource？"）
- **灵活泛化**：不同 PRD 写法下识别相同语义（不依赖关键词）
- **多对多映射**：把抽取出的对象匹配到标准事件类型
- **质量检查**：识别"需人工确认"的边界情况，写入 review_reason

### Code 适合做
- **JSON 解析**：包含 `strip_code_fences()` 和 `repair_json_string()`（LLM 输出经常带 markdown fence、未转义引号）
- **字段值映射**：lookup table（如 STANDARD_SCHEMA、PUBLIC_PARAM_POOL）
- **模板渲染**：markdown 表格、JSON 字符串、HTML 等结构化输出
- **校验/去重/合并/排序**：例如同模块的多个 click 事件合并
- **元信息追加**：时间戳、jira_id、用户标识用于追溯

### ❌ 反模式（这些都踩过坑）
- ❌ Code 用关键词检测做语义判断 → 用 LLM 输出布尔字段或模块名列表
- ❌ LLM 输出 markdown 表格 → 让 LLM 输出 JSON，Code 渲染表格
- ❌ 把业务规则硬编码到 LLM prompt 里（"如果 X 含 'banner' 就 ..."）→ LLM 用语义判断输出结构化数据，Code 用 schema 做 lookup
- ❌ LLM 重复上游已经说过的话 → 用相似度去重 (`_merge_review_reasons`)
- ❌ Code 节点 INPUT VARIABLES 用整个 File 类型 → 用 File 的子字段（`prd.name`）

---

## 第二原则：分层架构（E-R-D-R 模式）

复杂文档处理工作流可以分为 4 层，每层 **LLM + Code 配对**：

```
Extract → Reason → Decorate → Render
（抽取）  （推理）  （丰富）   （渲染）
```

**Extract 层**：LLM 抽取语义对象 + Code 解析 JSON
- 例：LLM_02 从 PRD 抽取 UI 元素 → Code_02 解析

**Reason 层**：LLM 做归类/匹配 + Code 验证补充
- 例：LLM_03 把元素映射到标准事件 + 识别 AB 实验范围 + 推荐公参 → Code_03B 解析 + 合并

**Decorate 层**：Code 整合标准库 + 元信息追加
- 例：Code_03B 把 LLM 推荐的公参 + 标准 schema 字段去重合并

**Render 层**：Code 按模板渲染最终输出
- 例：Code_04 把事件列表按模板渲染成 9 列 markdown 表格

这种分层让每个 LLM 节点的 prompt 短而精确（一个 LLM 只做一件事），便于单独迭代。

---

## 第三原则：多输入分支模式

支持多种输入源（PDF、URL、文本）的工作流，用 **If/Else + Variable Aggregator** 实现：

```
Start (多种输入字段都 optional)
  ↓
Code: input_router  ← 判断走哪条路径，输出 source_mode
  ↓
If/Else (source_mode == "lark"?)
  ├ true  → Path A: Lark API 读取
  └ false → Path B: Doc Extractor 读 PDF
  ↓
Variable Aggregator  ← 合流，下游统一接收 text
  ↓
... 核心链路 ...
```

让下游链路对输入源完全无感知。同样的模式可用于**输出分支**（如成功/失败/不同模式合并到 Send Message）。

**关键技巧**：Variable Aggregator 支持多组聚合（msg_content + msg_type），让多个并列输出变量一次合流。

---

## 第四原则：错误处理与兜底

### 节点级
关键 IO 节点（HTTP 调用、外部插件、API）必须开 **Fail Branch**：
- Write Document → fail branch
- HTTP Request → fail branch
- 第三方 plugin → fail branch

### 工作流级
失败时仍提供**可手动复制的兜底产物**：
- 写文档失败 → 发消息提示用户去运行记录看 markdown 手动粘贴
- API 调用失败 → 在最终输出里加 ⚠️ 标记

### 用户反馈
失败消息要清晰，包含：
- 失败原因（人类可读）
- 下一步建议
- 常见原因 checklist

---

## 第五原则：版本管理 + 迭代式开发

工作流不要一次大改：

- **版本命名**：v1 / v2 / v3 文件名（`code_03b_v5.py`，`llm_03_prompt_v5.txt`）
- **每次只改少量节点**：每改完做端到端测试再继续
- **部署指南记录步骤**：把改动幅度表格化（修改/新增/删除）
- **保留历史版本**：outputs/ 里所有旧版都保留，方便回滚对比

每改完一版都做 **mock 数据端到端测试**：
```python
# 用 Python 模拟整条链路
mock_events = [...]
mock_llm_output = json.dumps({...})
r1 = code_03b_main(...)
r2 = code_04_main(...)
assert ...
```

不要等部署到 Dify 才测——本地测试更快。

---

## 与 PM/PO 协作的最佳实践

### 1. 先列开放问题让用户拍板，不要替用户决定
模板：
> 我有 N 个需要你拍板的问题（A/B/C），分别是 ...，我倾向 X，原因是 ...，你的看法？

避免：
- "我已经做了 X 方案" → 用户可能想要 Y
- "你说怎么做" → 用户不知道选项

### 2. 边界情况显式说明，不掩饰平台/插件限制
模板：
> Write Document 只支持"document end"，无法精准插入到某个 H1 区块下。实务上影响：[case 1 OK，case 2 有副作用]。如果接受这个限制：[方案 A]。彻底解决需要：[方案 B，工作量翻倍]。

### 3. 测试 case 表格化，让用户对照验收
列出 N 个 case 覆盖所有路径组合（输入组合、成功/失败、边界条件），形如：

| Case | 输入 | 期望行为 |

### 4. 部署指南"具体到几次点击"
不是"加一个节点"，而是：
- 在哪个位置加什么类型节点
- 命名什么
- INPUT VARIABLES 选哪些字段（来自哪个上游节点的哪个输出）
- CODE 粘贴什么
- OUTPUT VARIABLES 声明什么
- 连哪条线（含 success / fail branch）

### 5. 关键决策点显式记录
设计决策不只是写代码，要文字总结"为什么这么做"。例如：
- "公参推荐用【公参推荐】前缀标记，让人工核对" → 因为运行时具体值无法预知
- "新增 5 个活动字段默认不带" → 避免每行都出现"【待确认】"造成噪声

---

## 跨平台集成的坑（Lark / 飞书）

### 权限申请要分档
- **核心必备**：当前工作流非用不可的（4-5 个）
- **高频扩展**：未来工作流大概率会用的（4-5 个）
- **中风险**：场景明确但敏感的（im:chat 创建群等，3-4 个）
- **明确不申请**：审批、考勤、邮件等无关权限（向安全部门表态）

按"核心必备 → 高频扩展 → 中风险"分批申请，比一次性大单更容易过审。

### 官方插件不一定可靠
真实踩坑：`langgenius/lark_document` 0.0.4 有已知 bug（issue #1310），Pydantic 验证错误，maintainer 标记 "Closed as not planned" **不打算修**。

**兜底方案**：HTTP Request 节点直连 Open API（自己管 tenant_access_token），稳定但工作量大。

### 几个具体坑
1. **sys.user_id ≠ 平台 user_id**：Dify 系统变量是内部 UUID（如 `c4dd032f-cb10-...`），不是 Lark open_id。给用户发消息要用 email 作 receive_id_type
2. **Send Message 的 content 是 JSON 字符串**：不是普通 text。要发 post 富文本，content 字段要传 `json.dumps({"zh_cn": {"title": ..., "content": [[...]]}})`
3. **Code 节点不接受 File 类型变量**：File 是 object，只能选其子字段（`prd.name` 等 string 字段）
4. **Write 类节点位置限制**：例如 Write Document 只支持 "document end"，无法精准插入到某个区块
5. **plugin 版本号 + provider_id**：直接写 yml 很容易写错，不如 UI 操作 + 给 Code 节点代码 + 给文字指南

---

## 检查清单（开始 Dify 工作流设计前对照）

- [ ] 输入有哪些来源？每种来源的格式？是否需要支持多输入？
- [ ] 核心处理是结构化任务还是语义任务？分别用 Code 还是 LLM？
- [ ] LLM 输出格式定了吗？（推荐 JSON，由 Code 解析）
- [ ] 每个 LLM 都配了 Code 解析吗？JSON repair 函数加了吗？
- [ ] 错误处理覆盖了关键 IO 节点吗？（Fail Branch）
- [ ] 失败兜底输出是什么？用户怎么知道失败并恢复？
- [ ] 用户怎么知道工作流跑完了？（消息通知/界面展示/邮件）
- [ ] 跨平台集成的权限申请按"核心 / 扩展 / 不申请"三档梳理了吗？
- [ ] 跨平台插件是否有已知 bug？是否有 HTTP Request 兜底方案？
- [ ] 部署指南"具体到几次点击"了吗？
- [ ] 测试 case 列出来了吗？覆盖所有路径组合？
- [ ] 版本号是否清晰？v1/v2/v3 文件名？
- [ ] 本地 mock 数据端到端测试做了吗？

---

## 设计反模式 - 这些写出来就回炉

| 反模式 | 正确做法 |
|--------|---------|
| 一个巨型 LLM prompt 干所有事 | E-R-D-R 分层，每层一个小 LLM |
| LLM 输出 markdown 表格 | LLM 输出 JSON，Code 渲染表格 |
| Code 用关键词检测做语义判断 | LLM 输出布尔字段或对象名列表 |
| 业务规则硬编码到 prompt 里 | LLM 做语义判断，Code 做 lookup table |
| 直接生成 yml 让用户 import | UI 操作指南 + Code 节点代码（避开 plugin 版本号问题）|
| 一次大改所有节点 | v1/v2/v3 版本管理，每次改 1-2 个节点 |
| 平台限制隐瞒不告诉用户 | 显式说明限制 + 提供 Plan B 让用户选 |
| 关键决策不让用户拍板 | 列 3 个方案 + 说明倾向 + 等用户选 |

---

## 触发后的工作流程

被触发后按这个顺序展开：

1. **理解用户的核心需求**：是新建工作流还是迭代？输入是什么？输出是什么？
2. **检查已有上下文**：是否有 PRD/截图/yml 文件可参考？已存在节点结构？
3. **列开放问题让用户拍板**：方案 A/B/C + 倾向 + 理由
4. **设计节点拓扑**：分层 + 多输入分支 + 错误处理 + 用户反馈
5. **写关键 Code 节点代码**：每个 Code 节点附输入输出变量声明、注释、本地测试
6. **写 LLM prompt**：用 v1/v2/v3 文件名，包含 JSON 输出 schema 严格要求
7. **写部署指南**：Step 1/2/3... 具体到 INPUT VARIABLES 选什么字段
8. **写测试 case 表格**：覆盖所有路径组合
9. **本地 mock 端到端测试**：Python 模拟跑通
10. **跨平台集成附 Plan B 兜底**：如插件有问题怎么办

---

## 现实案例：PRD → 埋点需求表（v1 → v6 演进）

完整案例覆盖：
- 11 个节点的设计演变
- LLM_02（元素抽取）+ LLM_03（标准事件匹配）的拆分
- 公参池 113 字段的推荐机制
- AB 实验范围识别（从关键词检测 → LLM 输出模块名列表）
- 层级 module_name（"为你推荐-币种卡片" 形式）解决合并误判
- review_reason 上下游去重（bigram Jaccard 相似度）
- Lark 集成（PDF/URL 双模式 + 写回 + 消息通知）的完整踩坑

详细演变记录可以问 Tom 调出对应 session 的 transcript。
