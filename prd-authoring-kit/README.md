<!-- PRD Authoring Kit · © Noah Zhan (@noah.zhan) · 二次分发/衍生须保留署名，不得标榜为自己原创创作。LICENSE / NOTICE 见根目录。 -->
# PRD Authoring Kit

> 门禁检查基线：2026-07-08；门禁升级后需同步更新 `references/checks/`（18 条原文）与 `references/01-authoring-rules.md` / `05-self-review-gate.md`。
>
> **可信度锚点**：本 kit 的 `references/checks/` 是门禁 18 条原文镜像（归属审查方产品作者 **@coast.lin**），基线 2026-07-08；`examples/` 的 PASS 是按 kit 口径自检 PASS，非真门禁背书。

陪产品把需求变成一份 **能显著提高一次通过研发 nocode 工作流准入门禁概率** 的飞书 PRD。跨 AI 应用可用（Claude Code / Kiro / Codex / Gemini / Antigravity），同一套核心知识，各平台只是不同入口。

## 它解决什么

研发的 nocode AI 工作流对 PRD 有 18 条抠字眼的准入检查：有 P0 判 🔴 有条件通过（修完才可推进），综合分 <60 直接不通过。人工照着写费时费力。本 kit 让 AI：
1. 和产品对话把需求聊清（或把粗稿/旧 PRD 结构化）；
2. 按飞书 house 风格 + 补齐门禁最爱扣分的缺口（成功指标 / 验收标准 / 本期不含 / 数据来源 / 幂等 / 埋点）起草；
3. **发布前用门禁的原始 18 条检查自检**到达交付标准（见下）；
4. 用 `lark-cli` 写进飞书，回链接 + 自检简报。

> 定位诚实说明：本 kit **主要面向加密交易所/App 类产品**（交易/行情/资金/推送场景的域规则最厚）；通用需求**也可用**，但不做过度承诺。自检的作用是**显著提高一次过门禁的概率**，不是「确保/保证一次过」。

## 目录

```
prd-authoring-kit/
├─ SKILL.md                       # Claude Code / Codex 官方 skills 入口（自动触发）
├─ README.md
├─ references/                    # ← 核心知识唯一一份都在这里
│  ├─ 00-orchestrator.md          # 主流程（唯一权威，所有平台都读它）
│  ├─ 01-authoring-rules.md       # 18 条门禁的“正面写法”（大脑）
│  ├─ 02-prd-template.md          # house 风格 + 补齐 nocode 缺口的模板（锚）
│  ├─ 03-interview-playbook.md    # 访谈采集
│  ├─ 04-upgrade-draft.md         # 升级现有草稿/旧 PRD
│  ├─ 05-self-review-gate.md      # 发布前自检门禁
│  ├─ 06-lark-publish.md          # lark-cli 写飞书
│  ├─ 07-format-conventions.md    # 飞书 house 格式约定（标题/US-R/元素表等）
│  ├─ 08-logic-review.md          # 逻辑内审六维（第二道门判据）
│  ├─ 09-tracking-gen.md          # 埋点生成，表直接写进 PRD（子 Sheet 默认不建）（⚠ 公参表 token 硬编码在其 §1，表迁移需同步改；05 的闭环矩阵复用它的对象清单，勿单独剥离）
│  ├─ 10-i18n-terms.md            # 国际化词条提取
│  ├─ 11-usage-telemetry.md       # 收尾使用采集（⚠ 采集表 token 硬编码在内，表迁移需同步改；重打包勿漏，漏了采集静默停摆）
│  ├─ 12-context-recall.md        # 背景自采集：写之前先查历史需求库（问人之前先问库）→ 背景简报 → 访谈只问增量
│  ├─ 12-library-manifest.json    # 历史需求库清单（各源 token/字段映射/模块词表；用户级覆盖放 ~/.prd-authoring-kit/library.json）
│  ├─ scenario-rules.md           # 业务场景规则库（附加检查）
│  ├─ checks/                     # 18 条门禁检查原文（自检逐条读）
│  ├─ checks-logic/               # 逻辑内审镜像（第二道门原文判据）
│  ├─ examples/                   # 交付级样例（已过全部 18 条的 PASS 稿）
│  └─ templates/                  # 对接产品的通用前/后端参考模板
├─ adapters/                      # 各平台薄指针（不含核心逻辑，只指回 references/）
│  ├─ codex/AGENTS.md
│  ├─ gemini/GEMINI.md
│  └─ kiro/steering/prd-authoring-kit.md
└─ companions/                    # 伴生 skill（随本包分发，装成各自独立的 skill 目录）
   ├─ jira-card-kit/              # 建卡/拆单（SKILL.md + references/ + scripts/ 自成一包）
   └─ showcase-demo/              # PRD/设计稿 → 可交互演示 demo（SKILL.md + references/ 自成一包）
```

## 前置：装 lark-cli

发布到飞书需要一个已登录的 `lark-cli`。按顺序做完这 4 步：

1. **装 lark-cli**：`npm i -g <对应包名>` 全局安装。
   - **公司内申请与安装以 IT 文档为准**：https://l7jipx1bfq.larksuite.com/wiki/JrHowKV06iDlafkSD2Au7UqEs6g ；遇到问题找 IT 负责人 **@henry.wang**。
   - 命令名是 **`lark-cli`**，不是 `lark`（别把二者搞混）。
   - 没有 `npm`？先装 [Node.js](https://nodejs.org/)（自带 npm），再回来跑上面的命令。
2. **`lark-cli config init`**：初始化应用配置。
   - 在 Agent / 团队环境里若被 refuse（拒绝写默认配置），改用 `lark-cli config bind` 绑定到当前环境。
3. **`lark-cli auth login`**：设备码（device-flow）授权。
   - 终端会**停住并给出一个链接 / 二维码**；用飞书扫码授权后终端**自动继续**——这是**正常**流程，不是卡死，别手动中断。
4. **`lark-cli doctor`**：体检。
   - **每一项 `status=pass` 即视为通过**；顶部若有 `update`（版本升级）提示可忽略，不影响使用。

> **没有 lark-cli 也能用**（很多同事没申请，kit 对这部分用户全程可用）：进入「无 lark-cli 全程模式」——写/升级/自检三模式照常，读飞书稿改为你全选复制粘贴给它，交付一份可直接粘进飞书的纯文本 PRD（md 文件）+ 自检简报，结尾附一次装法。装好 lark-cli 的增益=一键发布成飞书文档 + 贴链接就能读稿原地升级。

## 安装（一条命令）

用自带的轻量安装器，不用手动复制：

```bash
# 在 kit 目录下
./install.sh claude       # → ~/.claude/skills/（自动触发）
./install.sh codex        # → ~/.agents/skills/（Codex 官方 skills，自动触发）+ 旧位 ~/.prd-authoring-kit/ 兼容双写（AGENTS 片段照旧生成）
./install.sh gemini       # 核心 → ~/.prd-authoring-kit/ + 生成 GEMINI 片段
./install.sh kiro         # steering → 当前工作区 .kiro/steering/（inclusion:always 常驻入口）
./install.sh antigravity  # → ~/.gemini/antigravity/builtin/skills/（重启后 Skills 面板可见）
./install.sh all          # 以上全部
```
发布到 npm 后也可：`npx prd-authoring-kit <claude|codex|gemini|kiro|antigravity|all>`。

- **Claude Code（主推）**：`./install.sh claude` → 新会话说「帮我写个 PRD / 升级这份 PRD / 自检这份 PRD」即自动触发。
- **Codex**：`./install.sh codex` → 装进 Codex **官方 skills 位** `~/.agents/skills/prd-authoring-kit`（手动等价：`mkdir -p ~/.agents/skills && cp -R <本包> ~/.agents/skills/prd-authoring-kit`）。Codex 2025-12 起原生支持 skills：**自动发现、按 description 自动触发、全局生效**，**不必再往 AGENTS.md 并加载句**；显式呼出用 `$prd-authoring-kit`；装完/更新后**完全重启 Codex** 生效。（旧接法 `~/.prd-authoring-kit` + AGENTS.md 加载句仍双写兼容，已并句的用户不用动。）
- **Gemini**：装完按提示把**一句加载器**并入你的 `GEMINI.md`（安装器会打印那句话）——**只并这一句、别整份拷**：这样日后自动更新只刷 `~/.prd-authoring-kit/` 里的完整片段，你并入的那句永不过时。（旧版整份并入的用户：建议换成这一句，否则你并入的内容不吃自动更新、会慢慢过时。）
- **Cursor 等还没有 skills 机制的平台**：走旧法——`./install.sh codex` 装好核心后，把安装器打印的那**一句加载器**并入**项目根的 `AGENTS.md`**（或该平台等价的常驻上下文文件），同样**只并这一句**。新版 Cursor 若已支持 `.agents/skills` 目录（与 Codex 同标准），可同 Codex 装法——**以你的 Cursor 版本实测为准**。
- **Kiro**：在项目工作区跑 `./install.sh kiro`。**Kiro 的更新机制=steering 第 0 步「用时自更新」**（每次写 PRD 时静默把本项目 kit 刷到最新），**无需也不要设 autoupdate**。
- **Antigravity**：⚠ IDE 升级可能整个清空 `builtin/skills/`——发现 skill 不触发了，重跑 `./install.sh antigravity` 即恢复（幂等）；建议顺手设 autoupdate 兜底。

**每日自动更新（launchd/cron）**：`./install.sh autoupdate <claude|codex|gemini|antigravity>`——**分平台任务、多平台各设各的互不顶替**（v1.4.6 前是单任务、后设会顶掉先设的，升级后首次设置会自动迁移）。Kiro 不在列表内（用时自更新已覆盖）。关闭全部：`./install.sh autoupdate-off`。

> ⚠️ **开之前知情一下这是什么**：它在你机器上装一个每天 10:00 + 每次登录触发的任务，用 `npx -y` 拉取 **`prd-authoring-kit@latest`** 并**以你的身份执行该版本的安装脚本**——即「自动信任本包日后发布的任意新版本」。这对组内包是常规做法（同事零迁移拿到修复），但它确实是一条无人值守的远程代码执行通道：**能接受再开**，不接受就别设，改成需要时手动跑一次 `npx prd-authoring-kit@latest <平台>`，效果一样、只是不自动。

**校验**：`ls ~/.claude/skills/prd-authoring-kit/SKILL.md`；开新会话问它「你是谁」，答「PRD 写作助手 + 写/升级/自检 三模式」即成功。

## 📦 本包同时携带伴生 skill：jira-card-kit（建卡/拆单）、showcase-demo（演示 demo）

- **jira-card-kit**：把需求拆成 Jira 卡并批量创建（APP 双端标准包 / WEB 故事 / 跨端依赖）。
- **showcase-demo**：把 PRD / 设计稿 / 对话结论变成一键自动播放的单文件 HTML 可交互演示 demo。

**装 `claude` / `codex` 时自动落位**，无需另外下载安装：

| 平台 | 主 skill | 伴生 skill |
|---|---|---|
| Claude Code | `~/.claude/skills/prd-authoring-kit/` | `~/.claude/skills/jira-card-kit/`、`~/.claude/skills/showcase-demo/` |
| Codex | `~/.agents/skills/prd-authoring-kit/` | `~/.agents/skills/jira-card-kit/`、`~/.agents/skills/showcase-demo/` |

**分发合并、触发分离**：一个 npm 包带下来，装完是**三个独立 skill 目录、各自的触发词**——说「写个 PRD」进 PRD 写作助手，说「建 jira 单 / 拆卡」进 jira-card-kit，说「做个 demo」进 showcase-demo，互不稀释。（Gemini / Kiro 无同款 skills 机制，暂不安装伴生；主 skill 不受影响。）

🔴 **写 PRD 与建卡两件事不分先后、互相衔接**：一个需求两件都要做，先做哪件都行——
- 没 PRD 也能直接建卡（口头描述就够，绝不会让你"先去写 PRD"）；PRD 还没写时「需求Jira单」格填占位「待建卡」，建完回填；
- 会话里已有 PRD 链接 → 建卡时自动填进卡描述，不用你再贴一遍；
- 做完一件，另一件**只提一句**（「Jira 卡建了吗？」/「PRD 写了吗？」），不追问、不推销；对方另一半没装就整句省略。

**要拿去讲的时候**：写完 PRD 要演示，直接说「做个 demo」即进 showcase-demo（偶发需求，不主动追问、不打断写 PRD 的节奏）。

jira-card-kit 的用法、Jira token 配置与边界见 `companions/jira-card-kit/README.md`；showcase-demo 的方法论与素材见 `companions/showcase-demo/SKILL.md`；**要改它们就改 `companions/` 下的源文件**（那是 canonical），别改安装副本。

> **改一处全平台生效**：各 adapter（AGENTS.md / GEMINI.md / kiro steering）都是**薄指针**——只负责「命中意图 → 去读 `references/00-orchestrator.md` 并严格照办」，不复制任何规则/模板/检查逻辑。核心知识**只有一份，全在 `references/`**；改规则、改模板、改门禁口径只改 `references/` 里对应文件，各平台同时生效。
>
> **安装副本是托管产物**：`~/.claude/skills/…`、`~/.prd-authoring-kit/…`、工作区 `./prd-authoring-kit/` 等安装点会被自动更新**先清后拷**地覆盖——**勿在安装副本上做本地定制**，要改改本源仓（改完各平台自动更新带走）。
>
> 非 Claude 平台**定位 kit 的机械动作**：用你平台的文件查找能力定位 `00-orchestrator.md`（有 glob/file-search 工具用之；否则用 shell：`find . ~/.claude/skills ~/.prd-authoring-kit -name 00-orchestrator.md 2>/dev/null`）→ 它的上一级目录就是 `references/`，再上一级就是 KIT_ROOT；所有 `references/…` 与 `references/checks/…` 的读取都加 KIT_ROOT 前缀。找不到就**停下问用户 kit 路径**，不要凭摘要即兴写 PRD。

## 用法（三种模式）

| 你说 | 它做 |
|---|---|
| “帮我写个 PRD / 我有个需求” | 对话访谈 → 起草 → 自检 → 发飞书 |
| “升级/改这份 PRD”（附链接或草稿） | 结构化 → 补门禁缺口 → 自检 → 迭代更新飞书 |
| “自检/评一下这份 PRD” | 只跑 18 条检查 → 给分 + 缺口，不必发布 |

> **第 0 步不可跳过**：任何模式动手前，先读 `references/00-orchestrator.md` 并回显它的三模式表——这是硬要求，不是脚注。
>
> **正式准入 = PRD Bot**（@coast.lin 的准入门禁产品）：kit 自检是写作侧逻辑内审；发布后在 PRD Bot 会话发送 `/review <链接>`（纯文本官方格式）即得官方评审——报告贴回来，kit 帮你按清单补缺口（`06 §提审`）。

## 交付标准（摘录，权威以 `references/00`、`05` 为准）

**门禁判定栏**（P0/P1，按 18 条 checks 原文）永不静默放行；② kit 加严（第二道门/幂等有效性等）：**结构性断点默认阻塞发布、可用户知情放行**（资金安全默认应修）；细节项仅建议。

- **标准档**：门禁 `P0=0 且 P1=0` + 第二道门（逻辑内审六维 A状态/F边界/B闭环/C分支/E跨模块自洽/T可测性）**无结构性断点**（默认，资金/状态机结构缺陷可知情放行）。
- **轻量档**（1 个 US-R，且不新增/改动 发奖·行情取数·主动推送链路；涉资金但纯入口/文案/展示位、不碰发奖逻辑亦可，幂等段落须完整）：门禁 `P0=0` + 成功指标有判定口径 + 每个 US-R 有验收；**禁止编造任何指标**。
- P0 绝不放行。`score` 在 kit 侧仅信息性参考、**kit 硬线仍是 P0=0（标准档另加 P1=0）**；但真门禁按四维 30/30/20/20 加权出分并以分定档：<60 不通过、60–79 🟡、≥80 🟢，确认硬互斥 1 个封顶 79 / 2+ 封顶 74。

门禁「可量化性」维度是 house 稿最易失分处，成功指标 + 每个 US-R 验收标准是最快补分点。

## 设计取舍（为什么这么做）

对标对接产品的旧 prd-bot（28 工具 MCP 状态机 + 1500 字截断绕行 + 硬脚本 steering，难用），本 kit 反其道：**知识 + 模板 + 流程都是纯文件，让各平台 agent 自己编排，直接调 lark-cli**。轻、可移植、改一处全平台生效。

---

## 定位与署名

- **只做「撰写」，与「审查/准入」互补**：研发团队的 nocode 审查/准入门禁（prd-review skill 及其 18 条检查体系）是 **@coast.lin 的产品**；本 kit 是流水线的**撰写**这一半，**建在他那套门禁之上**（`references/checks/` 就是那 18 条检查的镜像，归属 @coast.lin）——目标是**让全组更容易过他的门禁**，不绕过、不替代、不抢功。撰写（本 kit，Noah Zhan）+ 审查（@coast.lin 的门禁）= 完整流水线。
- **署名 / 二次创作边界**：本 kit 作者 **Noah Zhan (@noah.zhan)**。欢迎使用、改造、内部分发，但请遵守 [LICENSE](LICENSE) 与 [NOTICE](NOTICE)：**保留各文件署名头与本 README 署名，衍生须明确标注"基于 Noah Zhan 的 PRD Authoring Kit 改编"，不得把本 kit 的结构与方法论（最小充分 / 不臆造 / house 粒度 / 对话确认 / 把准入检查反写成写作规则）标榜为自己的原创。** git 历史即先创作证据。

> 作者信息（`Noah Zhan (@noah.zhan)`、仓库 URL）在 `LICENSE`/`NOTICE`/`package.json`/各文件头，按需自行核对替换。
