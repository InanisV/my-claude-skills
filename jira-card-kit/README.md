# jira-card-kit

把产品需求按 MEXC 房规拆成 Jira 卡并批量创建的 AI skill。独立可用；规划中会合并进 prd-authoring-kit。

**能建什么（v1）**：APP 双端标准包（iOS/Android 故事 + UI设计任务 + 国际化任务 + Cloners/Relates 链接）、WEB/H5 故事、跨端 Blocks 依赖链接。
**刻意不做**：删卡、改已有卡、建机器人负责的卡和字段（开发/测试任务、埋点子任务、负责人、排期字段——系统自动生成）。

## 安装

1. **配 token**（一次性）：在 https://jira.mxcb.xyz 的 Profile → Personal Access Tokens 创建 PAT，写入 `~/.claude/settings.json`：

```json
{
  "env": {
    "JIRA_URL": "https://jira.mxcb.xyz/",
    "JIRA_PERSONAL_TOKEN": "<你的PAT>"
  }
}
```

只合并 `env` 对象，别覆盖文件里其他配置；也不要用 Cloud 风格的 `JIRA_USERNAME`/`JIRA_API_TOKEN`。其他客户端（Cursor/Kiro）设同名环境变量即可。详见团队文档《Atlassian(Jira) MCP Setup》。

2. **装 skill**：把本目录复制到 `~/.claude/skills/jira-card-kit/`（Claude Code 热加载，无需重启）。

3. **验证**：

```bash
python3 ~/.claude/skills/jira-card-kit/scripts/jira_cards.py whoami
```

## 使用

对 AI 说「把这个 PRD 建成 jira 单：<lark链接>」或「帮我建 XX 需求的 jira 卡」。AI 会：读 PRD 提取字段 → 一次性问齐缺口（设计师、Epic 等）→ 出建单计划表 → **你确认后**才创建 → 返回全部卡链接。

手动跑执行器也可以：

```bash
python3 scripts/jira_cards.py validate plan.json   # 校验+预览，不创建
python3 scripts/jira_cards.py apply plan.json      # 创建（失败自动续传）
python3 scripts/jira_cards.py user-search 关键词    # 查 assignee username
```

受益方填错了要纠正（本工具唯一的改卡能力，默认只预览）：

```bash
python3 scripts/jira_cards.py set-beneficiary "AI - Ealy" WEB-19174 WEB-19181 --apply
```

## 目录

- `SKILL.md` — AI 工作流入口
- `references/01-card-model.md` — 标准包结构、机器人边界、summary 规范
- `references/02-field-model.md` — 字段 ID/允许值/payload 形状（2026-08 createmeta 实测）
- `references/03-workflow.md` — PRD 提取映射、提问纪律、汇报格式
- `scripts/jira_cards.py` — 零依赖执行器
- `examples/` — APP 双端包与 WEB 故事的 plan 示例

## 已知边界

- 字段模型是 2026-08 快照；Jira 管理员改配置后需重跑 createmeta 校对（见 02 头部说明）。
- 仅支持自托管 jira.mxcb.xyz（Server 9.12，PAT Bearer 认证），不适配 Jira Cloud。
