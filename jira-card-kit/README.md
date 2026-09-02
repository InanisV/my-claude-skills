# jira-card-kit

把产品需求按 MEXC 房规拆成 Jira 卡并批量创建的 AI skill。**随 `prd-authoring-kit` 作为伴生 skill 分发（分发合并、触发分离）**：一个 npm 包装进来，装完仍是独立 skill 目录、独立触发词，两边互不稀释。**写 PRD 与建卡不分先后**，一个需求两件事都要做，做完哪件都会顺口提另一件。

**能建什么（v1）**：APP 双端标准包（iOS/Android 故事 + UI设计任务 + 国际化任务 + Cloners/Relates 链接）、WEB/H5 故事、跨端 Blocks 依赖链接。
**刻意不做**：删卡、改已有卡、建机器人负责的卡和字段（开发/测试任务、埋点子任务、负责人、排期字段——系统自动生成）。

## 安装

1. **配 token**（一次性，**你不需要碰终端**）：

   跟 AI 说一句「帮我配 Jira token」——**AI 会带你跑 `setup-token`**，你只做三个动作：

   | 谁做 | 做什么 |
   |------|-------|
   | **AI** | 帮你打开建 token 的页面（`https://jira.mxcb.xyz` → Profile → **Personal Access Tokens**） |
   | **你** | ① 点 **Create token**（名字随便，比如 `jira-card-kit`）→ ② **点复制按钮**把 token 复制走 → ③ 回来说一句"复制好了" |
   | **AI** | 跑 `python3 scripts/jira_cards.py setup-token`——工具自己弹出系统密码框（标题「Jira Token 配置」） |
   | **你** | ④ 把 token **粘进那个框**（输入显示为圆点）→ 点「好」 |
   | **AI** | 工具自动接验证，报一句"配置成功，当前用户：XXX" |

   密码框、落盘、验证**全在工具内部**：token 进程内直接写进 `~/.jira-card-kit/token`（权限 600），**不显示在屏幕上、不进对话、不进 shell 历史、不进进程表**；AI 从头到尾只看得到 `OK` / `CANCELLED` 和验证结果。**AI 不会、也不允许读 `~/.jira-card-kit/` 下的任何文件**（连配置也得经 `config-show` / `config-set`）——见 `SKILL.md` 顶部的「职责分离契约」。

   🔴 **永远别把 token 贴进和 AI 的对话里**——贴了就等于进了会话记录，去 Jira 撤销（Revoke）重建一个再跑一遍 `setup-token`。`config.json` 里也**不放** token（那个文件可能被你转发给同事）。

   token 过期或被撤销时，任何命令都会打出「❌ Jira 认证失败（HTTP 401）…运行 `setup-token` 重新配置」——照它说的重跑一遍就行。

   <details><summary>如果你熟悉终端，也可以自己跑这条（无 GUI / 非 macOS 时的退路，`setup-token` 会自动把它打给你）</summary>

   ```bash
   mkdir -p ~/.jira-card-kit && read -rs JIRA_TOKEN && printf '%s' "$JIRA_TOKEN" > ~/.jira-card-kit/token && chmod 600 ~/.jira-card-kit/token && unset JIRA_TOKEN && echo 已保存
   ```

   回车后光标停住就是在等你粘贴 token，粘完再回车；粘贴时屏幕不回显、不进 shell 历史。
   Windows 在 WSL / Git Bash 里跑同一条，见 `SKILL.md` 的降级链。
   </details>

   其它可用位置（读取顺序）：环境变量 `JIRA_PAT` → 上面这个 token 文件。不要用 Cloud 风格的 `JIRA_USERNAME`/`JIRA_API_TOKEN`。

   ⚠️ **`~/.claude/settings.json` 的 `env` 块是已废弃的位置——放在那儿的老 token 仍然读得到（不打断你），但请尽快迁走**：`settings.json` 是 AI 因加 permission / 设 env / 配 hook 等**与 Jira 完全无关的日常任务**会整份打开的文件，token 躺在那里迟早会进 AI 上下文。迁移：跑一次 `setup-token`（落到上面那个 600 文件）→ **手工删掉** `settings.json` 里的 `JIRA_PAT` / `JIRA_PERSONAL_TOKEN` 键 → 去 Jira 把那个 token **撤销（Revoke）重建**（它已经在那个文件里躺过，按已泄露处理）。工具每次从那里读到 token 都会打一条 WARN 提醒你，迁完就不再出现。

2. **装 skill**：在 `prd-authoring-kit` 仓库根跑 `./install.sh claude`（或 `codex`）——伴生 skill 自动落到 `~/.claude/skills/jira-card-kit/`（Codex 为 `~/.agents/skills/jira-card-kit/`），Claude Code 热加载无需重启。伴生安装当前只支持 Claude Code / Codex；其它平台把本目录整份拷进它的 skills 位即可。

   **（可选）配埋点两件套经办人**：`cp config.example.json ~/.jira-card-kit/config.json` 后**你自己**按团队实际填；不配也行——kit 首跑会问一次，再由它自己用 `config-set` 写进去（AI 只经工具读写这个文件，不会直接编辑它）。

3. **验证**（`setup-token` 已经自动验过一次，这条是想手动再确认时用）：

```bash
python3 ~/.claude/skills/jira-card-kit/scripts/jira_cards.py whoami
```

## 使用

对 AI 说「把这个 PRD 建成 jira 单：<lark链接>」或「帮我建 XX 需求的 jira 卡」。AI 会：读 PRD 提取字段 → 一次性问齐缺口（设计师、端范围等）→ 出建单计划表 → **你确认后**才创建 → 返回全部卡链接。

> **建卡也计入使用统计（仅组内 npm 版）**：`apply` 成功建出卡后，AI 会按主 kit 的 `references/11-usage-telemetry.md` 往「PRD写作kit使用记录」表追加**一行**（时间 / 使用人 / 需求名 / 平台 / 模式=建卡），用于统计 AI 对需求的覆盖率（按需求名去重，与写 PRD、做 demo 共用同一个需求名）。**只记这五列，不记卡号、卡内容、PRD 正文或链接**；失败静默、不打扰你；本机没装 prd-authoring-kit 就不记。

会**每批单独问你**两件事，且不给默认值、不替你推断：**受益方**（cf_16706，从 Jira 实时拉的选项里由你亲选；填错是别人替你的需求埋单）和 **Epic**（挂哪张史诗卡）。

Epic 这一问从 **v1.6.3 起改成用名字问**：AI 先跑 `epic-candidates` 去读**你的主卡和历史关联需求实际挂的 Epic**，给你一张 **`Epic 名称 | 卡号 | 依据 | 状态`** 的候选表让你挑（已关闭/已完成的会标「不建议」），你也可以直接**说 Epic 的名字**，工具用 `epic-search` 帮你找卡号。**凡是给你看的 Jira 卡都会带卡名**——计划表、确认问句、汇报三处都一样，不再甩给你一串裸卡号。

手动跑执行器也可以：

```bash
python3 scripts/jira_cards.py setup-token          # 配/换 Jira token（弹系统密码框，自动验证）
python3 scripts/jira_cards.py whoami               # 验证连通
python3 scripts/jira_cards.py beneficiary-options APP   # 实时拉受益方线上选项（供产品亲选）
python3 scripts/jira_cards.py epic-candidates --from <主卡卡号> --keyword "<需求关键词>" --project APP   # 捞 Epic 候选（名称+依据+状态）
python3 scripts/jira_cards.py epic-search --name "<Epic 名称片段>"   # 按名称找 Epic 卡号
python3 scripts/jira_cards.py validate plan.json   # 校验+预览，不创建
python3 scripts/jira_cards.py apply plan.json      # 创建（失败自动续传）
python3 scripts/jira_cards.py user-search 关键词    # 查 assignee username
python3 scripts/jira_cards.py config-show          # 看本机配置
python3 scripts/jira_cards.py config-set product_role app   # 改本机配置（只合并这一个键）
```

受益方填错了要纠正（本工具唯一的改卡能力，默认只预览；值必须逐字来自线上选项，且经产品本人确认）：

```bash
python3 scripts/jira_cards.py set-beneficiary "<线上选项原文>" WEB-19174 WEB-19181 --apply
```

## 目录

- `SKILL.md` — AI 工作流入口
- `references/01-card-model.md` — 标准包结构、机器人边界、summary 规范
- `references/02-field-model.md` — 字段 ID/允许值/payload 形状（2026-08 createmeta 实测）
- `references/03-workflow.md` — PRD 提取映射、提问纪律、Epic 名称化提问四步、汇报格式
- `references/04-field-survey.md` — **7 位产品 97 张真卡的字段实证抽样**（哪些默认值是全组房规、哪些只是作者个人习惯）
- `scripts/jira_cards.py` — 零依赖执行器
- `examples/` — APP 双端包与 WEB 故事的 plan 示例
- `config.example.json` — 本机配置样例（身份 `product_role`、埋点两件套经办人、上次用的 Epic（只作末位候选）；实际文件放 `~/.jira-card-kit/config.json`，由你手工填或由 kit 用 `config-set` 写。**不放 token**——token 单独一个 600 权限的文件，免得转发配置时把凭据一起发出去）

## 已知边界

- **职责硬分离（安全侧要求，2026-08-28）**：skill 只做行动规划与需求匹配，`scripts/jira_cards.py` 是**唯一的认证与 Jira 通道**。AI 被明令禁止：读/写/`ls`/`cat` `~/.jira-card-kit/` 下任何文件（token 与 config 都算）、以任何方式直连 Jira API（curl/httpie/内联 urllib）、在工具之外构造或传递 `Authorization` 头。密码框只由 `setup-token` 持有，文档里**不留脚本原文**（免得 AI 照着自己跑一遍绕过工具）。契约全文见 `SKILL.md` 顶部。
- 字段模型是 2026-08 快照；Jira 管理员改配置后需重跑 createmeta 校对（见 02 头部说明）。**受益方 cf_16706 例外：不做快照，每次实时拉**（全组共用、各人不同，内置枚举=诱导错填）；拉不到就停下不建卡，不放行近似值。
- 默认值经 **2026-08-27 抽样 7 位产品 97 张真卡**反查过一轮（`references/04-field-survey.md`）：优先级、版本、`是否需要APP端产品介入`、国际化默认、summary 前缀这 5 项原是作者个人习惯，已降级为「默认展示 + 计划表里一起确认」或按身份取值；其余默认值被 7 人抽样坐实。**如果你发现某个默认值和你们团队的习惯不符，以你们的习惯为准，直接在计划表里改。**
- 其中 4 项已于 **2026-08-27 由 Noah 拍板定稿**（见 `references/04-field-survey.md` 的「四项拍板」表）：**summary＝一层全角`【端】需求名`**（无前缀会被 `validate` 拦下，两层/半角只提醒）；**版本不主动问**、APP 默认分端占位、WEB 不填；`是否需要APP端产品介入` 按 `product_role` 身份取值；Epic 校验强度维持现状。
- 需要能连公司网络：`validate`/`apply` 会联网核对受益方选项和 Epic 卡号，离线跑不通（刻意没有 offline 开关）。
- 仅支持自托管 jira.mxcb.xyz（Server 9.12，PAT Bearer 认证），不适配 Jira Cloud。createmeta 走该版本的分页接口（`/issue/createmeta/{项目}/issuetypes[/{类型id}]`；老的扁平 createmeta 在这台实例上已下线）。
