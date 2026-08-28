<!-- PRD Authoring Kit · © Noah Zhan (@noah.zhan) · 二次分发/衍生须保留署名，不得标榜为自己原创创作。LICENSE / NOTICE 见根目录。 -->
# Lark Publish —— 用 lark-cli 把 PRD 写进飞书

> 🔴 **凭据不进上下文（本文件所有排查步骤的总闸）**：任何排查、分诊、验证步骤都**不得让 AI 执行会打印凭据值的形态**——`env` / `printenv` 裸跑、`echo $XXX`、`curl -v` / `-i` / `--trace*`（会把请求头连 token 打到 stderr）、任何 `--show-secret` 类 flag 都算。要定位「哪个变量在抢占」只取**变量名**（`env | cut -d= -f1 | grep …`）；确实需要看值 → 请**用户自己**在终端看、只把结论告诉 AI。**排查手段失败时一律降级交付，不许升级调试强度**。
>
> **无 lark-cli 环境：本文件整体不适用**——交付走 `00 §降级`「无 lark-cli 全程模式」（`07 §六` 格式），不要在此尝试安装或登录。
>
> 前提：`lark-cli` 已登录且 scope 齐全。**授权预检（工作流开始时一次做完，别等发布才发现缺 scope 打断体验）**：`lark-cli auth status`。**`needs_refresh` 不用重登**（下次 API 调用自动刷新，别据此重新扫码）；**仅当 status 明确失效或确实缺 scope** 时，才 **一次性请求本工作流全部所需 domain**（**仅适用于「从未登录 / 明确失效」的首次授权**；**已登录用户走下面「撞错才补」，别重跑完整 login**）：`lark-cli auth login --domain docs,sheets,base,drive,wiki,contact`（覆盖 建/改 docx、写使用统计 Sheet、读公参 Base、@作者/@对接人 解析——此清单即全部所需，勿加用不到的 scope）；子表挂 PRD 子页还需细粒度 scope `space:document:move`（`--scope "space:document:move"` 增量申请，**仅产品要求另建子表时**）。
> 🔴 **怎么判「确实缺 scope」——scope 机械核对（`status: ok` ≠ scope 齐，别只看 ok 就放行）**：`lark-cli auth status` 的输出里 `identities.user.scope` 是一整串**已授予**的 scope，照它逐个核对本流程的关键 scope——**最少核两个**：`docx:document:create`（建文档）与 `sheets:spreadsheet:write_only`（使用统计；埋点子表已默认不建、仅产品要求时才用到）。一条判定：
> ```bash
> lark-cli auth status 2>/dev/null | grep -c "sheets:spreadsheet"   # 0 = 缺，≥1 = 有
> ```
> ⚠️ **Codex 例外：管道不放行**——上面这条带 `| grep` 的判定在 Codex 沙箱下必失败；改成裸跑 `lark-cli auth status`，由你自己在输出的 `scope` 串里核这两个 scope（见下方 §Codex 沙箱适配）。
> 🔴 **核对的前提 = status 输出确有 `identities.user.scope` 字段**（老版 CLI 没有该字段——此时 grep 必为 0，**不得据此判缺、不得触发授权**；改按下面「撞错才补」处理，或让用户先 `lark-cli update`）。
> **字段在、且为 0 = 确实缺 → 当场按下面「授权最小打扰纪律」增量补该 domain/scope**（开场用户就在场，别拖到发布或收尾才发现）。实测漏症：同事登录时 domain 少给了 `sheets`，于是**文档发得出去、写表静默 403**，使用统计表里查无此人。⚠️ 这不违反 `11` 的「绝不为采集扫码」——**开场统一预检服务的是整个工作流**，禁的是收尾时单独为采集拉用户扫码。
> AI agent 走：`lark-cli auth login --domain … --no-wait --json` 拿 `verification_url`+`device_code` → `lark-cli auth qrcode "<url>" --output qr.png` 给用户扫码 → 授权后 `lark-cli auth login --device-code <code>` 完成。**注意 `docx` 不是合法 domain（并入 `docs`）。**
> ⚠️ **`device_code` 是短时凭据**（按 OAuth 设备流，用户授权后凭它即可兑换 access token）：只在本回合内用于紧接着那一次 `--device-code` 兑换，**禁止写进任何文档 / 报告 / 交付简报 / 提交**，兑换完即视为作废。有人在终端旁时优先用阻塞式 `lark-cli auth login`（不产出 `device_code`）。
>
> 🔴 **授权最小打扰纪律（已登录用户绝不轻易重授权）**——同事装好 CLI、按公司流程授权过一次，转头又被 kit 要一次 = 体验灾难；合规环境是**浏览器链接确认**，每次打扰成本更高：
> - `auth status` ok（`tokenStatus` valid）= **已登录**，**默认整个工作流不发起任何 `auth login`**；`needs_refresh` 绝不重登（API 调用会自动刷新）。
> - **撞错才补，缺啥补啥**：实际调用报 `missing_scope` 时，只增量申请**报错点名的那一个** scope/domain（`--scope "<缺的>"` 或对应最小 domain）。🔴 **禁止因"想一次拿全套"对已登录用户重跑完整 login**——公司 IT 流程用 `lark-cli auth login --recommend`（**推荐 scope 集**），与本工作流的 domain 清单**本来就可能不重合，不重合不是重登的理由**。
> - **一次会话至多一次授权交互**；发起前必须一句话讲清：**缺哪个权限、这次用来做什么、确认一次以后不会再要**。
> - 采集（`11`）相关的 `sheets` 缺失**永远不单独发起授权**（失败静默，铁律不变）；只有**开场统一预检**或**产品要求的埋点子表**等**用户可见功能**撞缺时，才顺带补。
>
> 🔴 **Codex 沙箱适配（命令形态）——Codex 平台专属：lark-cli 命令一律「单条裸跑」**：沙箱放行规则（用户在 `~/.codex/rules/default.rules` 配的 `prefix_rule`，见下方错误分诊「keychain」首判行）只匹配 **argv 首 token 为 `lark-cli` 的裸命令**；以下形态**全部不匹配、必落回沙箱撞 keychain 报错**（实测定案）：
> - ① **env 赋值 / `env` 命令前缀**：`LARK_CLI_NO_PROXY=1 lark-cli …`、`env -u HTTPS_PROXY … lark-cli …`（首 token 是变量赋值或 `env`，不是 `lark-cli`）；
> - ② **管道**：`lark-cli … | grep`、`| jq`、`| python3`；
> - ③ **分号复合**：`A; B; C`；④ **`&&` 串联**：`cmd1 && cmd2`。
>
> **改法**：
> - **每条 lark-cli 独立裸跑**，一条一跑、不拼接。
> - **管道后处理改为你（AI）直接读上一条的完整输出自己判**——输出你本来就看得到，不需要 `grep`/`jq`/`python3` 代劳（本文件 §前提「scope 机械核对」的一条判定、`11` 的采集长命令，在 Codex 下都按此改）。
> - **代理直连需求**（原 env 前缀，见下方错误分诊 EOF 行）在 Codex 下**先不带前缀裸跑，真撞代理 EOF / connection reset 再处置**（🔴 别试图用 rules 放行 env 前缀形态——`pattern = ["LARK_CLI_NO_PROXY=1", "lark-cli"]` 已实测**无效**，env 赋值形态无论如何写 pattern 都不被匹配）。
> - **Kiro / Claude / Gemini 等其他平台维持既有纪律不变**——Kiro 的单行分号 + 结尾 `echo` 是**终端检测需要**，**勿因本条把它改掉**（`11` 两种形态并存，按平台选）。
>
> **富文本/XML/flag 以 CLI 自带、版本匹配的技能为准**（不同 CLI 版本 flag 有差异，别凭本文件或记忆硬拼；**连命令名本身都会随版本变**——`sheets` 的 `+csv-*` 新集 vs `+append` 旧集就是实例，见 `11 §版本探测总则`，那里的采集命令同样受本条约束）：
> - `lark-cli skills read lark-doc references/lark-doc-create.md`
> - `lark-cli skills read lark-doc references/lark-doc-xml.md`（写 DocxXML 前必读）
> - `lark-cli skills read lark-doc references/lark-doc-update.md`（block 级改动前必读）
> - 深度增改（换图/表格改行/@人保护）另见 `anthropic-skills:lark-docx-authoring` skill（**仅 Claude Code 可加载**；其它平台不要尝试调用，直接按本文件红线执行 park→rebuild→return + round-trip 校验，细节读 `lark-cli skills read lark-doc references/lark-doc-update.md`）。
> **提交前先 `--dry-run`** 看命令是否成形，再实跑。

## 步骤 0 · 发布前净化（必做，别把半成品发出去）

要删掉：① 顶部"使用方式/图例/轻量路径"说明块；② `> 【指引` 行；③ 内联 `**[nocode必填]**`/`**[is_fund时必填]**` 等标记；④ `<!--…-->` 注释；⑤ `## PRD Quality Gates` 整节；⑥ 残留 `（填写：…）` 占位符（有就是没写完）。下面这段一次做完①-⑤并红灯校验⑥：

```bash
# 从首个 H1 标题起保留正文(丢掉顶部说明块) → 删指引行/注释/内联[必填]标记 → 删 Quality Gates 到文末
awk '/^# /{p=1} p' draft.md \
 | sed -E '/^> 【指引/d; /<!--/,/-->/d; s/ ?\*\*\[(nocode必填[^]]*|is_fund时必填|必填[^]]*)\]\*\*//g' \
 | sed '/^## PRD Quality Gates/,$d' > /tmp/prd_clean.md
# 红灯校验(用 if 而非 &&，避免 set -e 下 grep 无命中返回1 误终止脚本)
if grep -q '（填写：' /tmp/prd_clean.md; then echo "❌ 还有占位符没填，回去补"; exit 1; fi
if grep -qE 'PRD Quality Gates|^> 【指引' /tmp/prd_clean.md; then echo "❌ 指引/Quality Gates 残留"; exit 1; fi
```

> 无法运行此脚本（如 PowerShell/无 awk sed 的环境）→ 按 ①-⑥ 清单**直接编辑文件逐项删除**，删完逐项搜索 `（填写：`、`> 【指引`、`PRD Quality Gates` 确认零命中，效果等价。

## 步骤 1（默认）· 新建文档，Markdown 导入

最稳的一次成型。用 **stdin** 传正文（避免 @file 绝对路径的坑）：

```bash
lark-cli docs +create --title "【AI】xxx PRD" --doc-format markdown --content - < /tmp/prd_clean.md
# 返回 JSON 含 url / document_id
```

- 放指定位置：`--parent-token <wiki节点token或文件夹token>`（**用户指定了位置才传；默认建个人空间根，不主动问**——发布后在交付简报里告知位置、可按需 `drive +move` 挪，见 `00 §恒定规则 10`）。
- markdown 表格→飞书表格；标题层级、列表保留；**```mermaid fence 自动转成原生可编辑画板、fence 不残留**——所以 md 里照写 fence，**别在 fence 之外再贴一份 mermaid 源码或加「mermaid 文本供 XX 读取」说明**（实测用户点名是噪音）。
- 截图、@人、Figma bookmark、bitable 等富块 markdown 表达不了——先建文字版，再按步骤 2/3 补，或让产品在飞书手动贴。
- 版本差异：本环境 `docs +create` 无 `--api-version` 参数、默认即新版；若你的 CLI 版本 docs 命令报需要 `--api-version v2`，按 `lark-cli skills read lark-doc` 的提示加。

### 元素表富块写法（格内列表，实测）

markdown 里**内嵌 HTML `<table>`**，其单元格内的 `<ul><li>` / `<ol><li>`（含嵌套）经 `docs +create --doc-format markdown` 导入会 round-trip 成**真正的飞书项目符号/编号块**；而管道表格里 `<br>`+连字符只是假列表。元素表等需要格内列表的表**优先用内嵌 HTML 表格写法**（示例见 `02` 元素表、规范见 `07 §五`），不必为格内列表升级到 XML。

> 🔴 **埋点表按属性逐 `<tr>` 展开，别塌成一事件一行**：block_replace/insert 一张埋点表（XML）时，每个属性一个 `<tr>`、续行事件级列写空 `<td><p></p></td>`；`<tr>` 数 = 1 表头 + 属性总数（见 `09 §5`）。XML 手写路径最易把多属性分号挤进一格（markdown 导入不会），落地前按行数自查。

## 步骤 2（可选，高保真）· DocxXML 富块 / 插图

需要 house 风格 4 列元素表(rowspan)、@对接人、bookmark 时用默认 `--doc-format xml`。**写 XML 前先读** `lark-cli skills read lark-doc references/lark-doc-xml.md`。

**插图用 `+media-insert`（4 步编排 + 自动回滚），别用 `<img src="token">`：**
```bash
lark-cli docs +media-insert --doc <id> --file ./pic.png            # --file 用相对路径；默认追加到文末
# 定位到某段后：--selection-with-ellipsis "锚点文字片段"（可加 --before）
```
> 🔴 **禁止在新 block 里写 `<img src="<旧token>">` 复用图片**——会被换成 512×512 占位垃圾图、真图丢失。图片重定位只能靠 `block_move_after`。

**给已有文档补画板（block 级 patch 场景）**：先插入一个空画板块拿 block_token，再 `lark-cli whiteboard +update --input_format mermaid` 直接灌 mermaid（实测可靠；核验用 `whiteboard +query` 导图目检，须传 `--output` 目录）。**发布后核验**：fetch 回读 grep 无 ```mermaid 裸代码块、无「mermaid 文本供」说明句残留——有就删（逻辑已在文字规则里，代码块不留）。

> 建议：正文先用步骤1 markdown 建好，再对少数富块位置用步骤3 局部升级，别一上来全 XML。

### 元素表「原型」格贴图（设计稿截图，实测编排）

元素表首列「原型」默认是占位文字。**本机具备截图能力时**，把该 US-R 的 UED 链接指向的 frame 截图贴进这一格，PRD 一眼可读；不具备就维持占位——**这是加分项，不是发布前置条件**；🔴 **执行时机 = 主交付发布之后的独立环节**（见下方「接管询问硬闸」）。🔴 **位置口径：图只贴表内那一格**——一张图用 `rowspan` 合并、覆盖它对应的多个元素行；**禁止另建文末「原型图」章节把截图堆在一起**（实测：堆文末的后果是元素表连「原型」列都没了，读者读规则时看不到图）。见 `02` 元素表指引。

**截图来源（四级串，有啥用啥、全没有就占位）**——每级都**尽力而为**：能用就用，任一步异常即**静默降级**到下一级，不重试轰炸、不为了截图打断产品。**文档定位上 computer use 是主路（人人可用）；执行顺序上先试免接管来源（②③，可用则零打扰出图），不可用才走 ①（需接管用户电脑，先问）。**

- **主路 ① computer use 浏览器自动化（2026-07-30 端到端实测通，零配置）**——默认浏览器（macOS）；浏览器人人有、平时就登着 Figma，登录态白拿。前置条件两个：该机浏览器**登录过 Figma**；系统「辅助功能」权限**已授予宿主终端/应用**。没授权 → 提示用户去「系统设置 → 隐私与安全性 → 辅助功能」勾一次；用户拒绝或觉得麻烦 → **不纠缠，直接降 ④**。🔴 **动手前必过下方「接管询问硬闸」**。
  1. `open "<UED 链接>"`——**系统默认浏览器**打开 PRD 里的 UED 链接（原样用，链接自带 fileKey + node-id 会直接定位到目标 frame）；同事日常浏览器都登着 Figma，**登录态白拿**。（已实测）
  2. 默认浏览器是 Chrome → AppleScript 遍历 `windows`/`tabs`，🔴 **按 `fileKey` 精确匹配**再激活该 tab 并前置窗口。**禁止 `figma.com` / `figma.com/design` 这类宽泛匹配**——实测会命中同事开着的**另一个设计稿** tab（设计/产品同事浏览器里常年开一堆 Figma）。非 Chrome（Safari 等）→ 依赖第 1 步 `open` 后 tab 自然前置。（已实测）
  3. 🔴 **发键 / 点击前铁律：先截屏确认前台就是目标文件视图，决不盲发**——实测「activate 应用 ≠ 激活正确 tab」，盲发按键会打进无关网页。做法：pyobjc Quartz（`CGWindowListCopyWindowInfo`）拿浏览器窗口 bounds → `screencapture -x -R x,y,w,h shot.png` 区域截屏目检；**`-l` 窗口模式对 Chrome/Electron 不可靠，一律用 `-R` + bounds**。（已实测）
  4. **主路 · 原生导出（2026-07-30 端到端实测通）**：先 `shift+1`（zoom to fit）让 frame 标题可见并截屏 → CGEvent **点击 frame 标题**选中整个 frame（Esc 上浮在 view 模式实测不生效，点标题最稳；坐标从截图目测换算）→ 截屏确认右侧 Properties 出现「# <frame名>」→ 走**右侧面板 Export 区块**：无导出设置的 frame 点区块 **+** 号添加（默认 1x PNG；设计师预设过的直接有）→ 点「**Export <frame名>**」按钮 → 浏览器把**原生分辨率 PNG** 下到 `~/Downloads`（文件名 = frame 名；同名自动加 (1)），`mv` 到工作目录再走下面的插入编排。⚠️ **别走 `cmd+shift+E` 模态**——对无导出设置的 frame 它显示「0 of 0 selected」是死路（实测）。落盘前后 `ls ~/Downloads` 差集抓新文件名。
  5. **降级 · 屏摄（已实测通）**：不发键、或导出任一步异常 → 直接对当前视图 `screencapture -R` 截浏览器窗口 → pyobjc Quartz CGImage 按**画布区**裁剪（去掉左右面板 / 顶栏）→ 中等质量示意图（26% fit 视图下细节偏糊、布局可读；先 zoom 再截更清）。
  6. **全程节制**：会把浏览器前置几秒，动作**连贯一次做完**；任何一步异常即停并降级，**不重试轰炸、不打扰用户登录**（遇登录墙就当没能力，降 ④）。
  > ⚠️ 走**系统默认浏览器**，别用 in-app 浏览器面板（如 Claude Browser pane）：实测其下载不落盘、原生 Export 不可用，且有登录墙。
- **①b Figma 桌面 app 变体（备选，仅装了 app 的机器；第 3–5 步与 ① 完全相同，不复述；同属接管路，动手前一样过接管询问硬闸）**：`open -a Figma "<UED 链接>"`。🔴 **冷启动会吞 deep link**——`pgrep -x Figma` 无进程时先 `open -a Figma` 拉起、`sleep` 几秒后**把带 URL 的 open 重发一次**即可。app 内同样 `cmd+shift+E` 导出（view 权限也允许 Export）。

**免接管加速（执行时先静默试，成了就不必接管电脑）：**

- **② Figma MCP**（仅 Claude 平台且已连 Figma）：已连接则**一次调用出图、零打扰**——`get_screenshot(fileKey, nodeId)`，参数从 PRD 的 UED 链接解析（`https://…/design/<fileKey>/…?node-id=<a-b>` → `fileKey` 照抄、`nodeId` 把 `a-b` 写成 `"a:b"`）。返回**短时有效 URL**，立刻 `curl -o proto.png "<url>"` 落地。⚠️ View seat 有调用配额（**本机实测会耗尽**）；报 quota / 权限即降级 ③，别重试。
- **③ FIGMA_TOKEN REST（env 有才用，opt-in；质量最高，没配就直接往下降，别停下来要人配）**：
  ```bash
  curl -s -H "X-Figma-Token: $FIGMA_TOKEN" \
    "https://api.figma.com/v1/images/<fileKey>?ids=<a:b>&format=png&scale=2"
  # 响应 .images["<a:b>"] 即图片 URL，再 curl -o proto.png "<该 URL>" 下载
  ```
  两个参数解析同 ②；本级也不可用 → 才轮到接管路 ①（先过硬闸），仍不行则 ④。**此路待首用验证**（PoC 未实测）——第一次跑完人工比一眼下载图与设计稿是否同一 frame。token 生成：Figma → Settings → Personal access tokens。🔴 **token 只从环境变量读：禁止回显到对话、禁止写进任何文档 / 报告 / 提交；禁止给 `curl` 加 `-v` / `-i` / `--trace*` / `--trace-ascii` 等会打印请求头的 flag（`X-Figma-Token: <值>` 会原文进 stderr、直接落进上下文）；禁止 `echo` / `printenv` 该变量**。**本路失败一律静默降级到 ④——不调试、不重试、不加 flag 排查**（这条比逐个 flag 点名更硬：整条调试分支从流程里删掉）。
- **④ 占位降级**：以上都不可用 / 都失败（含用户不同意接管）→「原型」格维持写「见 UED 设计稿」：**静默降级、绝不阻塞发布、不重试轰炸**，也别借机追问用户去配 token / 装 app / 开权限。

**接管询问硬闸（computer use 路 ①/①b 动手前必过）**——本闸是 `00 §恒定规则 10 提问纪律`「不可逆或高侵入操作必问」的落地：

1. **时机**：仅在主交付（lark 文档）已发布之后，作为独立补图环节——**绝不在写作/发布中途插入接管**。
2. **必问**（话术示例）：「文档已发布 ✅。检测到 UED 设计稿链接，我可以自动截图补进『原型』格（需要**接管你的键鼠约 1-2 分钟**，期间请勿操作电脑——正好起来休息一下？）要补吗？」**得到明确同意才开始**；用户拒绝 / 不回应则跳过，不追问。
3. **执行中**：每步截屏除确认目标页面外，同时检测**用户是否在操作**（前台被切走 / 出现无关窗口 / 鼠标位置异动）——发现即**立即暂停**并告知「检测到你在用电脑，我先停了，空出来说『继续』」（**实测两次撞上用户操作，此为硬教训**）。
4. **收尾**：完成或放弃后明确告知「电脑还你了」+ 成果 / 结果。

> 边界澄清：接管询问是**每次操作的确认**，与「④ 占位降级不追问配置」不冲突——后者禁的是借机推销 token / 权限配置。

**插入编排（五步，已实测通）**——`media-insert` 锚点指向 td 内文本时，图会落在**表格后面**，td 内直插不可行，所以必须"先插后搬"：

1. `cd` 到图片所在目录（`--file` 只认相对路径，红线见上方插图段）。
2. `lark-cli docs +media-insert --doc <id> --file ./proto.png` 上传（图先落文末 / 锚点后，正常现象）。
3. `lark-cli docs +fetch --doc "<url>" --detail full --doc-format xml` → 拿**目标 td 内那个 `<p>` 的 block id** + **新 img 块 id**（空 td 自身没有 id，只能取内部 p，见步骤 3 红线）。
4. `lark-cli docs +update --doc "<url>" --command block_move_after --block-id <td内p的id> --src-block-ids <img块id>` → img 搬进格内。
5. 回读确认 img 落在 `<td>` 内，再把该格占位文本（「见 UED 设计稿」等）用 `block_replace` 清成空段或一句简短说明。

**节制**：一个 US-R **至多 1-2 张**（就截链接指向的那个 frame 整图），**别逐元素截**；配额耗尽 / 下载失败**不重试**。既有红线不变（定义见上方插图段与步骤 3，此处不复述）：`--file` 相对路径、禁 `<img src="<旧token>">` 复用、改完跑 round-trip img 数校验。同一张 PNG 复用到埋点表「截图」列的规则见 `09 §5`。

## 步骤 3 · 迭代更新已有文档（保护人工内容，别整篇覆盖）

同一篇改版**禁止整篇 re-import**——会抹掉原稿手工的截图/@/画板/bitable。用 block 级 patch：

```bash
lark-cli docs +fetch --doc "<url>" --detail with-ids --doc-format xml   # 拿 block id
lark-cli docs +update --doc "<url>" --command block_replace --block-id <id> --content - < newblock.md --doc-format markdown
lark-cli docs +update --doc "<url>" --command append --content - < more.md --doc-format markdown
```

🔴 **红线（含图/@的表最易翻车）：**
- 含 `<img>` 或 `@cite` 的单元格/表格：**只能改不含图/@的单元格文本**；要增删行或改 rowspan，用 **park→rebuild→return**（先 `block_move_after` 把图/@搬到表外占位 → `block_replace` 重建表 → 搬回 → 删占位）。`<tr>/<td>` 没有 block id，无法按 id 增删行。
- **block id 生命周期**：`block_replace` 会生成**新 id**（1 块可能变多块），替换标题后要重新 `+fetch --scope outline` 拿新 id 再继续。
- 空 td 没有 id：`--detail full` 拿到内部空段落 block id 再 `block_replace` 精准填。
- XML 正文里 `&` `<` `>` 需转义；校验时按转义形态 grep。
- 有序编号：飞书 `seq=` 自动编号有时不渲染 → 把 `1./2.` 直接写进标题/正文文本。
- **含样式文本（红字/底色/评审标记）的块，禁用 markdown 路径 `block_replace`**——markdown 不携带颜色，替换会**静默抹掉整块样式**（实测差点销毁上一轮评审红字）。改前先在 XML 里 grep `span`/`color` 探样式；有样式就走 XML 路径（span 保样式），或只 `str_replace` 内联改文字。

🔴 **改后必做 round-trip 校验**（"命令返回成功"≠改对）：
```bash
# 改前记基线（img 形态兼容裸标签与转义两种）
BEFORE=$(lark-cli docs +fetch --doc "<url>" --doc-format xml | grep -cE '<img |&lt;img ')
# … 执行你的 block 改动 …
AFTER=$(lark-cli docs +fetch --doc "<url>" --doc-format xml | grep -cE '<img |&lt;img ')
[ "$AFTER" -ge "$BEFORE" ] || echo "❌ 图片数 $BEFORE→$AFTER，人工内容可能被抹，别继续"
# 再核对：每个 @人 user-name 仍在、模块/小节数不变、文末无残留 AI 水印/占位
```
> ⚠️ **Codex 例外（管道/`$()` 不放行，见 §Codex 沙箱适配）**：改前改后各**裸跑一次** `lark-cli docs +fetch --doc "<url>" --doc-format xml`，**由你自己数输出里的 `<img` / `&lt;img` 条数**做同样的对比——**校验本身一次都不能省**，只是换形态。

**迭代改稿标红惯例**：block patch 新增/修改的文本标红色（XML text style，语法读 `lark-doc-xml.md`；markdown 路径的 `block_replace` 表达不了颜色，则在交付简报里列「本轮改动清单」替代），交付时告知产品「红色为本轮改动，评审确认后转黑」；新一轮修改开始时，按产品指示把上一轮红字转黑。首发稿全黑、不标色。

## 步骤 4 · 收尾

- 回给产品：飞书 URL + `05-self-review-gate.md` 自检简报 + 一句"改了哪几处/补了哪几块"清单（迭代时尤其要给，让产品知道人工内容没动）+ **发布位置**一句（默认个人空间根；「要挪到 wiki / 指定文件夹说一声，我用 `drive +move` 挪」）。
- 🔴 **建卡确认提问（强制，产品 2026-08-26 定——一个需求 PRD 和 Jira 卡两件事都要做，此问是需求闭环硬闸，不适用规则 10 的「能不问就不问」）**：本会话**没建过 Jira 卡、且用户没说过不建** → 交付简报后**必须提问**：「这个需求的 Jira 卡建了吗？要我现在拆卡吗？（PRD 链接我直接带过去）」——**有结构化提问工具就用**（Claude Code 用 AskUserQuestion，选项：现在建卡 / 已建好（贴卡号我回填） / 本需求不建卡），**没有的平台以这个问句结束回合等答复**，不许把它降级成一句可跳过的顺带话。免问仅两种：本会话已建过 / 用户已明确说不建。🔴 提问在**对话里**，绝不写进 PRD 正文（`01 §0.5`）；收尾采集（`11`）在提问**前**执行完。🔴 **本机没装 jira-card-kit**（`~/.claude/skills/jira-card-kit` 与 `~/.agents/skills/jira-card-kit` 都不存在）→ **不问，静默省略**。
- **收尾采集**：🔴 **文档发布成功的当轮立即记，不等"会话最终回复"**（`00` 规则 8 2026-08 改：按动作判、不按回合判——拿到文档链接的下一个动作就是采集，再回复用户；发布后被 建卡 / 补图 / 拉群 等支线打断也不影响，那时已经记过了）。按 `11` 记一条使用（失败静默）——这是收尾清单的正式一步，平台形态见 `11`（Codex=形态 B 分步裸跑）。
- 回复之后才轮到**原型图补图环节**（独立、非必做；见上方元素表『原型』格贴图小节的**接管询问硬闸**）。
- 大内容一次 create 报"内容过大/解析错"：先建带标题空壳，拿 url 后分段 `docs +update --command append` 兜底；不要预防性拆分。
- **失败即停，绝不降级为整篇 overwrite**（会毁人工内容）。

## 埋点子表（**可选，默认不做**；方法见 `09-tracking-gen.md §6`）

🔴 **默认不建**（2026-08 产品定）：**埋点表直接写在 PRD 里、以 PRD 为准**，发布流程到此为止，不建表、不贴链接、不留占位行。**仅当产品明确要求单独表时**才走下面三步：
1. **新建 sheet**：用 `lark-sheets`（先 `lark-cli skills read lark-sheets` 拿准命令），标题 `<PRD名>-埋点表`，建在 PRD 同文件夹或个人空间。
2. **写入** 10 列埋点表（触发时机 / 事件名英文 / 事件名 / 说明 / 属性英文 / 属性说明 / 是否必传(是/否) / 属性值 / 截图 / 备注），格式细则见 `09 §5`（`module` 值写中文）。
3. **挂成 PRD 子页 + 回填链接**：`lark-cli drive +move --file-token <sheet_token> --type sheet --folder-token <PRD docx token>`（需 `space:document:move`）；失败退回同文件夹。再把 sheet 链接写回 PRD `Data Requirements` 章节（`docs +update --command block_replace`），并保证与 PRD 内表逐行一致。

## 错误分诊（PM 友好话术）

| 你会看到类似 | 一句人话 + 傻瓜动作 |
|---|---|
| `keychain entry not found: lark-cli/appsecret:…`（error type=config） | "钥匙串里找不到该 app 的密钥——🔴 **这不是登录问题，反复 `auth login` 没用**。**首判：Agent 沙箱拦截（Codex 实测定案，最常见）**——同机另一些会话正常、且本会话 `security find-generic-password -s lark-cli` 报 `SecKeychainSearchCreateFromAttributes: parameters not valid` / `not found` = **本会话的沙箱拦了 Keychain API**（Codex 默认 `workspace-write` 沙箱按会话生效；lark-cli 每条命令都要读钥匙串里的 app secret，所以条条失败、重新授权也没用）。修复（精确放行，不整体关沙箱）——🔴 **这条改的是 Codex 的沙箱放行规则，属安全配置：AI 不得代改**。把规则**原样给用户**，由**他本人**写进 `~/.codex/rules/default.rules`（没有就新建）并**完全重启 Codex** 生效；改完让他回一句「配好了」你再重试。**AI 不许自己写 `~/.codex/rules/` 下任何文件，也不许用其它方式绕开沙箱。** 规则原文：`prefix_rule(pattern = ["lark-cli"], decision = "allow", justification = "lark-cli reads app secret from macOS Keychain; sandbox blocks Keychain API")`。生效后 lark-cli 自动在沙箱外执行，其余命令沙箱照旧。⚠️ 转达时带一句：`prefix_rule` 按 argv 首 token 匹配，放行后**任何** PATH 上叫 `lark-cli` 的可执行文件都会在沙箱外运行——配之前先 `which lark-cli` 确认指向 IT 装的那个。⚠️ **rules 只放行「裸命令」**——配好后 kit 侧按 §Codex 沙箱适配 用**裸跑形态**调用；若 AI 仍用 env 前缀 / 管道 / 分号复合形态，会**继续报同一个错**，那不是 rules 没生效。次判：**同机不同会话 `auth status` 一好一坏 = 多凭据源解析漂移**（lark-cli 按 env 自动探测 Agent 凭据源：`OPENCLAW_HOME`/`HERMES_HOME`/`LARK_CHANNEL`；另有 workspace/profile 概念）——在好、坏两个会话各跑 `env \| cut -d= -f1 \| grep -iE 'OPENCLAW\|HERMES\|LARK'` + `pwd` 对比，找出坏会话解析到的 app 与来源（🔴 **`cut -d= -f1` 不能省**——诊断只需要「哪个变量在抢占」这个**变量名**，一个值都不需要；裸跑 `env \| grep …LARK` 会把 `LARK_*` 形态的密钥类变量**连值**打进 AI 上下文。另：`lark-cli config show` 的输出是否含 appSecret **尚未核实**，AI 别代跑——需要看它就请**用户自己**在终端跑、只回报 app 名称），再按「哪个 app 是 IT 给你申请的正主」修：残留 env/绑定抢占 → 清掉即可；**正主 app 密钥真缺** → 重走 IT 配置流程（`lark-cli config init --new` 链接发管理员配密钥 → `auth login --recommend` → `config default-as user`）。⚠️ **禁用 `config keychain-downgrade`**（密钥落盘违安全要求）；⚠️ **`config remove` 会清全部 token 与配置**，定位清楚前禁用。" |
| 未登录 / 登录态失效 | "飞书没登录或过期了。现在扫码登录（终端跑 `lark-cli auth login`），还是本次先用纯文本模式？"——不便重登就按 `00 §降级` 纯文本交付，**别卡住等扫码** |
| 权限不足 / 读不到 doc | "我没这份文档权限。在飞书里把它（或目标文件夹）分享给你自己，或换个有权限的位置。" |
| scope 不足报错 | "CLI 版本旧了。跑 `lark-cli update` 升级后重试，别急着授权宽 scope。"——升级后仍报缺，按 §前提「**授权最小打扰纪律**」**只补报错点名的那一个** scope/domain，别对已登录用户重跑完整 login |
| 大写入/上传报 EOF、connection reset | "多是代理问题（不是文档问题）。写/上传命令直连重试：给命令加前缀 `env -u HTTPS_PROXY -u HTTP_PROXY -u https_proxy -u http_proxy`（细节见 lark-cli 自带文档；`lark-docx-authoring` skill 仅 Claude Code 可用）。读操作不受影响。🔴 **Codex 例外**：env 前缀在 Codex 沙箱下不被放行（见 §Codex 沙箱适配）——先**裸跑重试**，仍 EOF 再请用户在 rules 里配 env-token 变体、或自己在沙箱外手动跑一次。" |
| wiki 链接读不出 | "wiki 一般能直读；不行就打开 wiki 文档，用地址栏出现的 docx 链接给我。" |
| 网络瞬态超时 | "网络抖了一下，稍等重试；查下 VPN/代理。" |
| 增量授权返回"新授予 scopes：空" | "这个 scope 被公司管理员禁用了，扫码也给不了。别反复重试——改走降级路径（如手动在飞书 UI 操作），或找管理员开。" |

## 提审 · PRD Bot 官方内审（发布后的正式准入入口）

> 本 kit 的自检只是**写作侧逻辑内审**；**正式准入以 PRD Bot（@coast.lin 的准入门禁产品）的评审为准**。发布完成后主动提醒产品提审——**提审动作由产品自己完成（约 1 分钟），本 kit 不代发**（实测 `im +chat-list` 列不出应用/bot 单聊会话，自动化不可靠，勿尝试代发消息）：

1. 飞书里搜「**PRD Bot**」打开对话（应用/BOT）。
2. 在会话里发送 `/review <PRD 文档链接>`（**纯文本即可，官方支持的触发格式；无需提前分享文档**）。
3. bot 回「PRD 审查完成」报告（分数/结论/摘要）；产品把报告贴回来，kit 按 `04`/`05` 帮忙按评审意见补齐缺口。
