---
name: jira-card-kit
description: 把产品需求（PRD 链接或口头描述）按 MEXC 房规拆成 Jira 卡并批量创建：APP 标准包（默认一张【Flutter】故事 + UI设计任务 + 国际化任务；原生 iOS/Android 双端 + Cloners/Relates 链接可选，切双端判据见 03 §2）、WEB/H5 故事、跨端 Blocks 依赖。当用户说「建 jira 单 / 建卡 / 拆单 / 把这个 PRD 建成 jira / 提测拆卡 / 开发排期建单」，或给出 PRD 链接并要求进 Jira 时使用。只建卡不删卡；创建前必出计划表经用户确认。
---

# jira-card-kit（MEXC Jira 建单）

把一个需求变成一组符合房规的 Jira 卡。**铁律：先出建单计划表 → 用户明确确认 → 才执行创建；绝不静默建卡，绝不删卡，绝不碰机器人管的字段。**

## 🔴 展示纪律（贯穿全流程，三处同款）

**凡向产品展示 Jira 卡——Epic、主卡、关联卡、Relates/Blocks 目标——一律写「名称」(卡号)，禁止裸卡号。**

裸 `XXX-12345` 对产品是一串乱码，他没法判断对不对；`「<线上读回的 Epic 名称>」(XXX-12345)` 他一眼就知道对不对。三处一个都不许省：**① 计划表**（`validate` 已按此渲染「Epic 确认」区块与链接表）、**② 确认问句**（AskUserQuestion 的选项文案 / 无该工具时的文字清单）、**③ 汇报**（建完卡贴群那份）。

卡名一律**从线上读回来**（`epic-candidates` / `epic-search` / `validate` 都会读）；读不回就写「（读不到卡名）」并说明读不回——**绝不编卡名、绝不拿需求名冒充卡名**。

执行器：`scripts/jira_cards.py`（零依赖）。token 读取顺序：环境变量 `JIRA_PAT`（旧名 `JIRA_PERSONAL_TOKEN` 同样识别）→ `~/.jira-card-kit/token` 文件（权限 600，由 `setup-token` 写入）→ `~/.claude/settings.json` 的 `env` 块（**已降级的兼容位，只为不打断老配置**：读到就打 WARN 催迁移，别再往那儿放新 token；AI 禁止打开该文件，见下方禁令①）。

## 🔴 职责分离契约（先读这条，它管住下面所有步骤）

**skill = 行动规划与需求匹配；`scripts/jira_cards.py` = 唯一的认证与 Jira 通道。**
你（AI）负责判断"这个需求该建哪几张卡、该问哪些问题、该跑哪条命令"；凡是**取密钥、存密钥、带着密钥说话**的事一律交给工具——你不需要、也不允许看到密钥。

### 四重禁令（AI 绝对禁止 · 无例外、无"就这一次"）

1. **禁止读 / 写 / `ls` / `cat` `~/.jira-card-kit/` 目录下的任何文件**——`token` 和 `config.json` **都算**。
   配置的读写也经工具：读用 `config-show`、写用 `config-set <键> <值>`（只合并那一个键）；工具跑不动就**引导用户自己去改那个文件**，不许你代劳。
   **也禁止以排查 jira 为目的读 `~/.claude/settings.json`**——那是老配置的兼容位，可能还躺着一份有效 PAT，而它恰恰是你因**别的**任务（加 permission / 设 env / 配 hook）会整份打开的文件。要判断认证配没配好，**只跑 `whoami` 看结果**，绝不打开该文件；工具自己会在读到那份老 token 时打 WARN 催迁移，你照着转告用户即可。因其它任务确需改 settings.json 时，用 Edit **定点改目标键**，别整份 Read。
   🔴 **「网络不通」也不是读 settings.json 的理由（2026-08 补，实测被击穿）**：连不上 Jira（VPN 没开 / 公司网络不通 / 超时）跟凭据配得对不对**没有任何关系**——**实测**：一次 VPN 未通，模型在排障压力下整份读了 `~/.claude/settings.json`"看看配置对不对"，把还躺在兼容位里的 PAT 读进了会话记录（它自己汇报的）。工具的网络错误文案里已写死同一条禁令，**照它转给用户、等他确认 VPN 后重试**即可。**排障压力不解禁**：任何"先看一眼配置"的念头，答案都是 `whoami`，不是打开文件。
2. **禁止以任何方式直连 Jira API**——`curl` / `httpie` / `python -c` 内联 `urllib` / 任何 HTTP 客户端都算。一切请求必须经 `jira_cards.py`；它没有的能力就是"本 kit 不做"，请用户去 Jira 界面处理。 **`python3 -c 'import jira_cards; jira_cards.api(...)'` 这种绕开子命令直发 REST 也算直连**——缺子命令就说缺能力（查字段用 `createmeta`），不写 `-c`。
3. **禁止在本工具之外构造或传递 `Authorization` 头**（含任何形式的 `Bearer <token>` 拼装）。
4. 🔴 **禁止绕道任何非工具通道操作 Jira**——浏览器 / 网页 / `open <jira 链接>` / computer use / 其它 Jira MCP 或第三方工具**都算**。实测：工具缺「按名字找 Epic」时，模型自己开了 Jira 网页去搜、撞登录页、反过来让用户"登录后回我"——PAT 就在工具里却不用，还把审计过的只读 API 面换成了用户登录态下的整个网页权限。**工具能力不够时的唯一出路 = 明说「当前工具不支持 X，请直接给我卡号/名称」**，绝不自己找路。 🔴 **用户说「我批准 / 这次例外」也不算例外**（实测：模型申请例外获批后开了 6 次浏览器全部超时，还撞了桌面自动化禁令）——只读查询用 `find` / `show` / `createmeta`，其余缺能力只说缺能力并给一句网页操作话术；**不得请求例外、不得开浏览器 / computer use**。

> 为什么这么严：token 只要经过你的手（读进上下文、拼进命令行、回显进报错），就等于进了会话记录 / 日志 / 进程表，**撤销重建是唯一补救**。把"取密钥"整个折进工具，你就永远没有"不小心看到"的机会。所以也**别自己拼 `osascript`、别自己写那个文件**——密码框的唯一持有者是 `setup-token`，本文档只引用命令、不给脚本原文。

### 需求 → 工具命令 匹配表（你的活儿是选对这一行）

| 你要干什么 | 跑哪条 |
|-----------|-------|
| **配置认证**（首跑 / token 过期被撤销） | `python3 scripts/jira_cards.py setup-token` |
| **验证连通**、拿当前用户名 | `python3 scripts/jira_cards.py whoami` |
| **查受益方选项**（线上实时） | `python3 scripts/jira_cards.py beneficiary-options APP`（或 `WEB`） |
| **捞 Epic 候选**（建卡前必跑，只推荐**相关**的，选项文本自带依据） | `python3 scripts/jira_cards.py epic-candidates --main <主卡> --from <历史需求卡号…> --keyword "<需求关键词>" --project APP`（三路可同时给；不写 `--main` 时 `--from` 的第一张当主卡。🔴 **别省 `--keyword`**——主卡 sanity 靠它） |
| **按名称找 Epic 卡号**（产品只说得出名字） | `python3 scripts/jira_cards.py epic-search --name "<名称片段>"` |
| 新建 Epic 并把卡挂上去 | plan 里加 issuetype=Epic 的卡 + 故事 epic_ref → validate → apply（见 01 §Epic） |
| **校验计划** + 出计划表 | `python3 scripts/jira_cards.py validate <plan.json>` |
| **建卡** | `python3 scripts/jira_cards.py apply <plan.json>` |
| **纠错受益方**（已建卡填错了） | `python3 scripts/jira_cards.py set-beneficiary "<线上选项原文>" <卡号…> [--apply]` |
| 读本机配置（`product_role` / `tracking_assignees` / `last_epic`） | `python3 scripts/jira_cards.py config-show` |
| 写本机配置（只合并一个键） | `python3 scripts/jira_cards.py config-set <键> <值>` |
| 查 assignee 的 username | `python3 scripts/jira_cards.py user-search <关键词>` |
| 废弃自动化多长出来的卡（评论留痕、不删卡） | `python3 scripts/jira_cards.py discard <卡号…> --reason "去向说明" [--apply]` |
| **查某需求的卡建了没**（只读） | `python3 scripts/jira_cards.py find --keyword <需求词> --project <项目>` |
| **看某张卡的子任务 / 谁在做**（只读；含 修复版本 / 预期交付日期） | `python3 scripts/jira_cards.py show <KEY>` |
| **apply 报某字段 400、想看允许值**（只读） | `python3 scripts/jira_cards.py createmeta --project <项目> --issuetype 故事` |

**表里没有的需求＝本 kit 不做**（删卡、改其它字段、改状态…）：请用户去 Jira 界面处理，**不要**自己找别的路子实现——"别的路子"**逐个点名**：`curl`/`httpie`/内联 `urllib`、**浏览器或网页**、computer use、其它 Jira MCP/第三方工具。工具缺的能力**只能**说出来（「当前工具不支持 X，请直接给我卡号/名称」），不能绕。

### token 铁律（并入本契约，不再另立一节）

1. **绝不让用户把 token 发进对话**（贴进聊天窗 = 永久落进会话记录/日志，等于泄露）。
   **用户真贴了 → 立刻告诉他：这个 token 已经进入会话记录，去 Jira 把它撤销（Revoke）、重建一个**，再走下面的流程；别装作没看见、更别拿它去调接口。
2. **token 只经工具的 `setup-token` 进文件**：工具内部弹系统原生密码框（输入显示为圆点），取回的文本进程内直写落盘并 `chmod 600`——不进 stdout、不进 argv、不进 shell 历史、不进对话。**你能看到的只有 `OK` / `CANCELLED`。**
3. 不要把 token 写进 `config.json`（那个文件会被转发给同事）；`config-set` 也会拒收凭据类键。
4. 🔴 **AI 严禁以任何方式读取 token 明文**：不许读那个 token 文件（`cat`/`head`/`echo` 一律禁止）、不许从系统任何中转区取用它、不许在任何输出或报错里回显它。**验证只看 `whoami` / `setup-token` 的结果**，不看 token 本身。

### 认证失败（HTTP 401 / 403）怎么办

工具会打出统一那句：`❌ Jira 认证失败（HTTP 4xx）：token 可能已过期或被撤销。请更新密钥：运行 python3 scripts/jira_cards.py setup-token 重新配置…`

🔴 **收到它你只做一件事：把它原样转告用户、请他更新 token**（他愿意就直接跑 `setup-token` 带他配一遍）。
**禁止**去读 / `ls` / `cat` `~/.jira-card-kit/` 下任何文件"看看 token 还在不在、是不是空的、是不是权限不对"；**禁止**改用 `curl` 直连 Jira"试试是不是网络问题"——这两条正是四重禁令要挡的旁路。403 还可能是**该操作超出他的 Jira 权限**（不是 token 坏了），一并说给他听。

### 首跑没有 token 时的配置流程（macOS 主路 · 用户全程不碰终端）

用户里很多人不会用终端。**主路是 AI 帮他开页面、他只做"点创建 + 复制 + 粘进弹窗"三个动作，弹框与落盘由工具自己完成——AI 只负责跑那一条命令。**

**第 1 步 · AI 直接帮他打开建 token 的页面**（不要只给链接让他自己找）：

```bash
open "$(python3 scripts/jira_cards.py pat-page)"
```

（2026-08-27 实测可达：这台实例装的是 Atlassian 内置 PAT 插件，这个 URL 直接落在 Personal Access Tokens 标签页；没登录会先跳登录页，登完自动回到该页。打不开就退一步打开去掉 `?selectedTab=…` 的同一地址（`<Jira 地址>/secure/ViewProfile.jspa`）让他点 **Personal Access Tokens** 标签。）

**第 2 步 · 告诉用户只做两件事**（原样说给他听）：

> 页面上点 **Create token**（名字随便填，比如 `jira-card-kit`）→ 生成后**点复制按钮把 token 复制走**（这个值只显示这一次，别关页面前先复制）→ 回来跟我说一声"复制好了"。
> **别把它贴给我**，我不需要看到它。

**第 3 步 · 用户说"复制好了"后，AI 跑这一条**（**只有这一条**——密码框在工具内部弹，AI 不碰、也不需要知道它长什么样）：

```bash
python3 scripts/jira_cards.py setup-token
```

它会：弹系统原生密码框（标题「Jira Token 配置」，输入显示为圆点）→ 取回的文本**进程内直写** `~/.jira-card-kit/token` 并 `chmod 600` → **自动接 `whoami` 验证**。按它的输出分支：

- **`OK` + 「配置成功，当前用户：XXX」** → 配好了，直接继续建卡（验证工具已经替你做完，**别再单独跑一次 `whoami`**）。
- **`CANCELLED`** → 用户点了取消或没填，什么都没写。问一句「刚才那个框取消了，再来一次？」，重跑本步。
- **「token 已落盘，但验证没过（HTTP 401）」** → **不是让用户把 token 贴出来**，而是：「这个 token 好像不对（可能粘的时候少了几位，或者页面上那个已经失效了）。回到那个页面重新复制一次（或重新 Create 一个），我再跑一遍。」然后重跑本步。
- **「这台机器弹不出系统密码框…」** → 工具已经把终端降级引导一并打出来了，**照它给的原样转给用户**（别自己另编一套、别代跑）。

🔴 这条命令的 stdout 只会是 `OK` / `CANCELLED`——**token 不进 stdout、不进 argv、不进对话**。密码框归工具持有：**别自己拼 `osascript`、别自己写那个文件**（见职责分离契约的四重禁令）。

### 降级链（工具自己会退，你只负责照着转达）

| 情况 | 怎么做 |
|------|-------|
| **弹窗跑不起来**（无 GUI / 远程会话 / Codex 沙箱拦 `osascript`）| `setup-token` 会自己打印终端降级引导（`read -rs` 那条）并 exit 1——**把它原样给用户，让他自己在终端跑**，措辞是「如果你熟悉终端，跑一下这条」。别把它当默认、更别你代跑。 |
| **Windows / Linux** | 同上：`setup-token` 判平台后直接打印同一条终端引导（Windows 在 WSL / Git Bash 里跑）。 |
| 用户已经把 token 贴进对话 | 按 token 铁律 1 处理：**先让他去 Jira 撤销重建**，再走主路 |

> Codex 注记：脚本调用在 Codex 下**单条裸跑**（沿用 lark-cli 铁律，别串管道/别包在复合命令里）。token 走普通文件，**不依赖系统钥匙串**——Codex 沙箱禁钥匙串是老坑，别往那儿引。

## 流程（按序执行，每步首次进入时读对应参考）

开场顺带跑 `python3 ../prd-authoring-kit/scripts/register.py demand-mine --daily`（路径相对本 skill 目录；每天首次一次）：输出 SKIP、0 行、没有 lark-cli、或主 kit 未安装（文件不存在）都静默跳过；有行就按 `../prd-authoring-kit/references/13-workflow.md §七` 出建议表，🔴 写回逐行确认。

0. **状态核查（用户问「卡建了没 / 子任务建了没 / 派给谁了 / 有没有漏建」时先做，别直接建）**：`python3 scripts/jira_cards.py find --keyword <需求词> --project <项目>` → 命中的卡 `show <KEY>` 看子任务与经办人；再让主 kit 查需求收集表的 Jira 列（`python3 ../prd-authoring-kit/scripts/register.py demand-find --name <关键词>`）；聊天记录只是旁证（配方见主 kit `references/13-workflow.md §五`）。🔴 **查不到 ≠ 没建**——结论里明说「Jira 里按关键词没查到、需求表里没有登记」，让产品确认后再建；禁止凭聊天断言、禁止为了"确认"去开网页。
1. **认证自检**：`python3 scripts/jira_cards.py whoami`。
   - 报「找不到 Jira token」→ 按上面「首跑配置流程」带用户配（**AI 开页面 + 跑 `setup-token`，用户只点创建、复制、粘贴；绝不收 token、绝不回显 token**），不要继续。
   - 报「❌ Jira 认证失败（HTTP 401/403）」→ 按契约里的「认证失败怎么办」：**原样转告用户去更新 token**（或直接跑 `setup-token` 带他重配），**别去翻 `~/.jira-card-kit/`、别改用 curl 试**，也不要继续建卡。
   - 报「连不上 <Jira 地址>（…）——公司网络/VPN 通吗？」→ **网络问题，不是凭据问题**：把这条**原样转告用户，请他确认 VPN 后重试**；**禁止**为此读任何配置文件（`~/.claude/settings.json`、`~/.jira-card-kit/` 都不许），**禁止**改用 curl 直连"试试"（见四重禁令①的网络补充条）。用户没确认之前不要继续建卡。
2. **收集需求信息**（🔴 **与 PRD 先后不限**：写 PRD 和建卡是同一个需求的两件事、**不分先后**——**开场不设任何前置，绝不要求用户"先去写 PRD"**；PRD 后补时把链接回填进卡描述即可）：
   - 输入是 lark PRD 链接且 `lark-cli` 可用 → 读 PRD 提取字段答案（提取映射见 [references/03-workflow.md](references/03-workflow.md)）；
   - 无 PRD → 按 03-workflow 的问题清单向用户收集，**口头需求描述就够建卡**。
   - 读 [references/01-card-model.md](references/01-card-model.md) 确定这个需求该建哪几张卡（标准包结构、机器人边界——很多卡和字段系统会自动生成，别重复建）。
3. **一次性补齐提问——先分级再问**（实测：把"设计师姓名"和"Epic 卡号"包装成「还差两个信息」并规定回复格式，产品当场批注"设计师不是阻塞项""卡号你自己搜"）： **零候选的新专项**：多问两样「Epic 叫什么 / （WEB）预期上线日期」，进 plan 的 Epic 卡（`references/03-workflow.md §2` 第 2 题）。 🔴 **分块呈现**：阻塞两问（受益方 / Epic）一块，登记三项（优先级 / 迭代版本 / 进展）另一块，正文别把混合问卷统称「这三个」（实测产品反问「这三个要确认的是什么」）。**受益方答的是简称**（如「Jackie-直客」）→ `beneficiary-options <项目> --match "<简称>"`，命中多条就列给产品点，**不得自选、更不得同回合 apply**。 **纯子任务批次**（本批只在已有主卡下建子任务、不建故事）：受益方 / Epic 两问**不适用、不问**（端范围本就不问）（这些是故事卡的字段），只确认父卡（按展示纪律写成「名称」(卡号)）与子任务类型；`validate` 对这种批次不报 Epic 警告。
   - 🔴 **查得到的别问**：Jira 里能查到的（卡号↔名称、版本名、字段选项、主卡信息）一律工具自己查（`epic-search` / `epic-candidates` / `beneficiary-options` / `user-search`），**不问人**；
   - 🔴 **推断得出来的也别问（v1.6.6 新增，产品实测点名）**：**是否需要UI(cf_11530) / 是否涉及新页面(cf_15401) / 是否需要埋点(cf_16301) / 依赖交付情况(cf_11506)** 这四项**一律自己判**，判据见 [references/03-workflow.md](references/03-workflow.md) §1 提取表。产品原话——"**新页面应该要自己判断，埋点只要有新的页面和 UI 改动，默认应该是要的**"。判完把值和**一句依据**写进 `plan.meta.inference_notes`（`ui` / `new_page` / `tracking` / `dependency` 四个键），`validate` 会连同依据渲染进计划表让产品扫一眼、要改直接说——**它们是可选项，不新增提问回合、不阻塞建卡**（缺依据只 WARN）。
     🔴 **和主 kit `references/09-tracking-gen.md`「埋点写前先问要不要」不打架**：那条管的是**写 PRD 时**的产品决策（这个需求要不要做埋点）；这条管的是**建卡时**把已定的结论填进字段——**有 PRD 就读 PRD 的结论**（Data Requirements 埋点表非空=是、明写「本需求无需埋点」=否），**没 PRD 才按页面/UI 改动推断**。一个是决定要不要做，一个是把已定的结论落进卡，两件事。
   - 🔴 **阻塞项只有两种**：受益方确认、Epic 确认——这两件必须产品拍板才能建卡（端范围默认 Flutter 单卡，不问；切双端判据见 03 §2）；
   - **其余全是可选项**（UI 设计师人选、业务线标签、跨端依赖细节、上面那四个推断项…）：有就填、没有按房规默认或按判据推断（**UI设计任务 assignee 留空后补**——七人真卡实证 APP 卡建卡时 assignee 本就为空），**绝不当阻塞项、绝不要求"明确回复先不建"**；
   - 能给默认值的都带默认值，禁止挤牙膏式追问。
   ⚠️ **默认值不等于恒定值**（2026-08-27 抽样 7 位产品 97 张真卡，见 [references/04-field-survey.md](references/04-field-survey.md)）：**优先级、版本(fixVersions)、是否需要国际化、组件**这四项各人写法不一致，原先 kit 写死是把作者个人习惯当房规——现在做法是**照常带默认值，但在第 5 步的计划表里显示出来跟其它项一起确认**（并入同一轮，别新增提问回合）。
   🔴 **首跑问一次、之后读 config 不再问**：先 `python3 scripts/jira_cards.py config-show` 看有没有 `product_role`（**这是读配置的唯一入口，别 cat 那个文件**）；没有就问**「你是 APP 产品线的，还是业务产品？」**→ 决定 `是否需要APP端产品介入`(cf_17100) 填 `已审核（APP产品选填）` 还是 `不需要（业务产品选填）`（抽样证明这跟需求内容无关、只跟填卡人身份有关）。拿到答复后用 **`python3 scripts/jira_cards.py config-set product_role app`**（或 `business`）写进去——工具只合并这一个键，别自己读出来改完再整份写回。
   🔴 **两个例外是硬闸，没有默认值、每批必问、不许推断**：
   - **受益方 customfield_16706**：它决定人力成本记在哪个团队账上（定额消费、季末回溯审计），组织明令"谁收益填谁、不要想当然"，**填错等于让别人替你的需求埋单**。**必须由使用本 kit 的产品本人亲口确认，AI 才能代写**——不许给默认值、不许从 Epic/项目名/需求名推断、不许照抄主卡或相似卡（主卡自己也可能填错）。流程：**先 `python3 scripts/jira_cards.py beneficiary-options APP`（或 WEB）实时拉线上选项**（本 kit 不内置受益方枚举——此 skill 全组产品共用、各人受益方不同，写死等于诱导错填）→ **把选项摆出来让产品亲选**（有 AskUserQuestion 这类结构化提问工具就列成选项让他点；选项多按前缀分组分批问；没有该工具就列清单、以问句收口等答复）→ 选中项**逐字**填进卡，确认人填 `plan.meta.beneficiary_confirmed_by`、依据填 `beneficiary_rationale`；**两者缺一 validate 直接报错、建不了卡**。线上选项拉不到 → **停下**，让用户从 Jira 建单界面把选项原文逐字抄来，**绝不放行近似值、绝不猜**。判定规则见 [references/02-field-model.md](references/02-field-model.md) 红线节。
   - **Epic（史诗链接 customfield_10102）**：各产品挂的 Epic 不同，kit **不写死任何卡号**。建卡前必问，但**别空着手问、更别把一堆不相关的扔上来**——按下面四步走：
     **① 先捞候选（相关性优先）**：`python3 scripts/jira_cards.py epic-candidates --main <主卡卡号> --from <历史需求卡号…> --keyword "<需求关键词/模块名>" --project APP|WEB`（只读；三路可同时给，不写 `--main` 时 `--from` 的第一张当主卡）。`--from` 喂**背景简报里历史关联需求的 Jira 单号**（会话里有 prd-authoring-kit 的背景简报就直接把那一行的单号喂进来，见主 kit `references/12-context-recall.md`）；`--keyword` 按端选 project 取同族卡。
       🔴 **候选来源只有两级、且按级排序**：**①历史关联需求挂的 Epic**（`--keyword` 同族卡 + `--from` 的历史卡）→ **②主卡挂的 Epic**。**`last_epic`「上次用的」不再是候选**（v1.6.6，产品原话："**epic 就应该参考相关的历史需求的，而不是把历史使用的 epic 一股脑扔上来**"），只在①②全空时工具提一句"上次用的是「X」，但与本需求查不到关联，不建议直接沿用"。
       🔴 **主卡也要过 sanity**：主卡卡名与需求关键词**零重合** → 工具打出"主卡「XXX」看起来不是本需求的，确认卡号？"，并把**只由它带出来的** Epic 降到末位标注。**撞到这句就回头找产品核卡号，别拿那个 Epic 往下走**（`--from` 里混进上一轮的别的需求卡号是实测踩过的坑）。**所以 `--keyword` 别省**——没有它就没有 sanity 判据。
     **② 名称化提问（硬闸：每批必问），形态跟着候选走**：
       - **单强候选**（工具打出「单强候选 · 推荐形态」：关联卡 ≥2 张且无同级竞争）→ **不平铺**，就问「**建议挂「X」(卡号)——依据…**，**就它** / **换一个**（说名字或卡号都行，我来找）/ **不挂**」；
       - **多候选** → 才列表，把工具输出里**每条整行原样**当选项文案。
       🔴 **选项文本 = 「Epic 名称」(卡号)——依据**（形如：`「<Epic 名称>」(APP-xxxxx)——历史需求「<历史需求名>」等 3 张挂它`）：**依据在选项文本里，不许拆去另一列、不许只留名称**——产品判断"这个 Epic 是不是本需求的"靠的就是这半句。有 AskUserQuestion 这类结构化工具就照这个文案列选项，没有的平台在正文列同款文字清单、以问句收口等答复。🔴 **禁止只甩卡号问「上次是 XXX-1234，还挂它吗？」**，也**禁止把工具已经降级/折叠的候选重新平铺上来**。
     **③ 产品答名字 → 工具找卡号**：`python3 scripts/jira_cards.py epic-search --name "<名称片段>"`，返回 名称|卡号|状态 ≤10 条。**多命中就把「名称（卡号）」全列出来让他指一条，不许猜**；零命中就请他换个更短的片段、或直接给卡号。
     **④ 硬闸不变**：每批必确认、**禁止沿用不问**、`validate` 仍会拿卡号去线上 GET 验一次，不存在（404）直接拦住不建卡。**推荐形态只是省掉"在一堆不相关候选里挑"，没有产品那句「就它」照样不许填。**⚠️ **Epic 常挂在别的项目下**（抽样里 APP 卡挂的都是 CONTRACT/SPOT/OPT 等业务项目的史诗），别只认 `APP-` 前缀；**且多数真卡本来就不挂 Epic，用户答"不挂"是正常答复，别追问**。
     🔴 **候选 ≠ 决定（口径统一，别再打架）**：候选**可以**来自主卡 / 历史关联需求——把**相关**线索摆出来让产品选正是本轮要做的事；**禁的是"静默填"**（没问就填、照抄主卡、沿用上次不问），以及**"不相关也摆上来"**。零候选时明说「未找到相关 Epic」并回到 ② 问他，**不编卡号**。
4. **生成 plan.json**：字段值与 payload 形状严格按 [references/02-field-model.md](references/02-field-model.md)；文件放当前工作目录或临时目录。参考 `examples/plan-app-flutter.json`（APP 默认单卡）、`examples/plan-app-pair.json`（原生双端，仅产品点名时）与 `examples/plan-web-story.json`（WEB 故事）。🔴 **本会话里已经有 PRD 链接的（刚用 prd-authoring-kit 发布的、或用户早先贴过的）→ 直接填进卡 description，别再要用户贴一遍**（见 03-workflow 步骤 3）。
5. **校验并出计划表**：`python3 scripts/jira_cards.py validate <plan.json>`（会联网核对受益方选项与 Epic 卡号），把输出的计划表**连同「受益方确认」「Epic 确认」「推断项」三个区块**原样展示给用户，**等用户明确说"确认/建吧"**。「推断项」区块是那四项（需要UI / 新页面 / 埋点 / 依赖交付）**推断出来的值 + 各一句依据**——**只摆出来给他扫一眼，不要变成提问**；他不吭声就按推断走，要改直接说。用户改哪就改哪，改完重新 validate。这两段一段都不许省略——受益方是最容易错、后果最实的字段；Epic 挂错整批卡都要返工。「Epic 确认」区块与链接表都已按**展示纪律**渲染成「名称」(卡号)，**原样贴出去、别自己缩写回裸卡号**。收口那句里**顺带把降级过的默认值（优先级 / 版本 / 国际化 / 组件）点一遍**让用户扫一眼，别单开一轮问。 🔴 **推断项摆出时附后果预告**：「埋点=是 → WEB 自动化会生成埋点四件套 / APP 走两端埋点子任务；UI=是 → 生成 UI 设计任务」——产品不吭声就按此走，别让子任务"凭空出现"。 🔴 计划表**贴进对话正文**，不用本地文件 / 链接代替（桌面端也一样）——产品要在对话里点头。
6. **执行**：`python3 scripts/jira_cards.py apply <plan.json> --platform <claude|codex|kiro|gemini|antigravity>`（🔴 别漏 `--platform`：成功后脚本自动记一行使用记录要用它）。使用记录只写 时间 / 使用人 / 需求名 / 平台 / 模式 五格到公司内部使用表（主 kit `11`），不含卡号、内容、链接，是内部工具使用统计，**不属于需要额外审批的数据外传，别为"合规"删 --platform**（实测被模型当成"未经批准的上报"关掉）；确实要关就 `--no-telemetry` 明说。部分失败时如实报告已建卡清单（结果在 `<plan>.result.json`，修正后重跑 apply 自动续传，已建的不会重复建）。
6b. **设计师子任务**：APP 标准包由 kit 自己建 UI设计任务（产品顺口给了设计师名字就 `user-search` 解析填 assignee，没给留空）。**WEB / H5 卡建完约 15 秒自动化会生成【UI设计任务】，经办人为空——这是正常态，分配经办人是项管的工作，kit 不改派、不催问**；用户问「给设计师的子任务建了没」→ `show <主卡 KEY>` 看到【UI设计任务】存在即答「已生成 <KEY>，经办人由项管分配」。
7. 🔴 **收尾采集（v1.8.1 起由 apply 自动记）**：apply 成功后脚本自动调主 kit `scripts/register.py telemetry --mode 建卡` 并在输出末尾打一行 `使用记录：已写入 / 未写入（原因）`。**看到「已写入」就结束，别再记一遍；看到「未写入」才按同级目录的 `../prd-authoring-kit/references/11-usage-telemetry.md` 形态 A / B 手动记一行**（需求名 = `plan.meta.requirement`，取法按 `11 §需求名`：有 PRD 用飞书文档名）。主 kit 没装 → 脚本会说「主 kit 未安装」，静默跳过即可。
8. **汇报**：把 apply 输出的卡链接清单整理给用户（可直接贴群）。提醒：机器人会在几分钟内自动补开发/测试负责人、埋点子任务等，不用管。
8b. 🔴 **登记需求收集表**：建卡成功后按主 kit `../prd-authoring-kit/references/12-context-recall.md §十` 登记（先查后写、有行只补 `Jira单号/链接`；优先级 / 迭代版本 / 进展先问产品）。
9. 🔴 **收尾 · PRD 确认提问（强制——一个需求 PRD 和 Jira 卡两件事都要做，此问是闭环硬闸）**：本会话既没写过 PRD、用户也没说过不写 → 建卡汇报后**必须提问**：「这个需求的 PRD 写了吗？要我现在写吗？（卡号我会填进 PRD 的『需求Jira单』格）」——**有结构化提问工具就用**（Claude Code 用 AskUserQuestion，选项：现在写 / 已有 PRD（给链接我补卡描述） / 不用写），**没有的平台以问句结束回合等答复**，不许降级成顺带一句。免问仅两种：已写过 / 用户已明确说不写。🔴 **本机没装 prd-authoring-kit**（`~/.claude/skills/prd-authoring-kit` 与 `~/.agents/skills/prd-authoring-kit` 都不存在）→ **不问，静默省略**。

## 边界

- 支持：**新建 Epic（v1.8，一批一张，WEB 必填预期交付日期）**、APP 标准包（默认 Flutter 单卡；原生双端可选；含 APP 协作卡，见 01）、WEB/H5 故事、连到已有卡的 Blocks/Relates 链接（`cards` 可为空、只补链接）。**只读查询 `find` / `show` / `createmeta`。**🔴 **不做、但必须明说的**（别装作能做、别静默跳过）：**改已建卡字段**（网页 Edit / Bulk Change）、**AIL / OSS / OPT / GJH 等项目的故事卡**——计划表里单列「缺口：需在 Jira 网页手建」，别硬建；**在这些项目已有的主卡下建子任务可以**（`parent` 给已有卡号，脚本只限制故事卡的项目，实测 AIL-151 一次建成）。
- 只创建，不删卡、不改状态、不改其它字段。**唯一的改卡能力是 `set-beneficiary`**（受益方错填是组织级高频问题，必须能纠正；默认只预览，加 `--apply` 才写入）。用户要删卡或改别的字段 → 请他自己在 Jira 界面处理。
- 【新页面】子任务不在建卡标准包里（历史数据 23/28 是开发排期后才补建的）；用户明确要求时才作为独立子任务加进 plan。
