<!-- PRD Authoring Kit · © Noah Zhan (@noah.zhan) · 二次分发/衍生须保留署名，不得标榜为自己原创创作。LICENSE / NOTICE 见根目录。 -->
# Lark Publish —— 用 lark-cli 把 PRD 写进飞书

> **无 lark-cli 环境：本文件整体不适用**——交付走 `00 §降级`「无 lark-cli 全程模式」（`07 §六` 格式），不要在此尝试安装或登录。
>
> 前提：`lark-cli` 已登录且 scope 齐全。**授权预检（工作流开始时一次做完，别等发布才发现缺 scope 打断体验）**：`lark-cli auth status`。**`needs_refresh` 不用重登**（下次 API 调用自动刷新，别据此重新扫码）；**仅当 status 明确失效或确实缺 scope** 时，才 **一次性请求本工作流全部所需 domain**：`lark-cli auth login --domain docs,sheets,base,drive,wiki,contact`（覆盖 建/改 docx、建埋点 Sheet、读公参 Base、@对接人 解析——此清单即全部所需，勿加用不到的 scope）；子表挂 PRD 子页还需细粒度 scope `space:document:move`（`--scope "space:document:move"` 增量申请，仅挂子表时）。
> AI agent 走：`lark-cli auth login --domain … --no-wait --json` 拿 `verification_url`+`device_code` → `lark-cli auth qrcode "<url>" --output qr.png` 给用户扫码 → 授权后 `lark-cli auth login --device-code <code>` 完成。**注意 `docx` 不是合法 domain（并入 `docs`）。**
> **富文本/XML/flag 以 CLI 自带、版本匹配的技能为准**（不同 CLI 版本 flag 有差异，别凭本文件或记忆硬拼）：
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

元素表首列「原型」默认是占位文字。**本机具备截图能力时**，把该 US-R 的 UED 链接指向的 frame 截图贴进这一格，PRD 一眼可读；不具备就维持占位——**这是加分项，不是发布前置条件**；🔴 **执行时机 = 主交付发布之后的独立环节**（见下方「接管询问硬闸」）。

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
  两个参数解析同 ②；本级也不可用 → 才轮到接管路 ①（先过硬闸），仍不行则 ④。**此路待首用验证**（PoC 未实测）——第一次跑完人工比一眼下载图与设计稿是否同一 frame。token 生成：Figma → Settings → Personal access tokens。🔴 **token 只从环境变量读：禁止回显到对话、禁止写进任何文档 / 报告 / 提交**。
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

🔴 **红线（含图/@的表最易出错）：**
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

**迭代改稿标红惯例**：block patch 新增/修改的文本标红色（XML text style，语法读 `lark-doc-xml.md`；markdown 路径的 `block_replace` 表达不了颜色，则在交付简报里列「本轮改动清单」替代），交付时告知产品「红色为本轮改动，评审确认后转黑」；新一轮修改开始时，按产品指示把上一轮红字转黑。首发稿全黑、不标色。

## 步骤 4 · 收尾

- 回给产品：飞书 URL + `05-self-review-gate.md` 自检简报 + 一句"改了哪几处/补了哪几块"清单（迭代时尤其要给，让产品知道人工内容没动）+ **发布位置**一句（默认个人空间根；「要挪到 wiki / 指定文件夹说一声，我用 `drive +move` 挪」）。
- 回复之后才轮到**原型图补图环节**（独立、非必做；见上方元素表『原型』格贴图小节的**接管询问硬闸**）。
- 大内容一次 create 报"内容过大/解析错"：先建带标题空壳，拿 url 后分段 `docs +update --command append` 兜底；不要预防性拆分。
- **失败即停，绝不降级为整篇 overwrite**（会毁人工内容）。

## 埋点子表（有埋点时；方法见 `09-tracking-gen.md`）

用 `lark-sheets`（先 `lark-cli skills read lark-sheets` 拿准命令）新建一个 Lark 电子表格承载完整埋点表：
1. **新建 sheet**：标题 `<PRD名>-埋点表`，建在 PRD 同文件夹或个人空间。
2. **写入** 10 列埋点表（触发时机 / 事件名英文 / 事件名 / 说明 / 属性英文 / 属性说明 / 是否必传(是/否) / 属性值 / 截图 / 备注），格式细则见 `09 §5`。
3. **挂成 PRD 子页**：`lark-cli drive +move --file-token <sheet_token> --type sheet --folder-token <PRD docx token>`（需 `space:document:move`）；失败退回同文件夹。
3. **回填链接**：把 sheet 链接写回 PRD `Data Requirements` 章节"完整埋点表：见 Lark Sheet …"那一行（`docs +update --command block_replace` 改该行）。
PRD 内仍保留一份埋点表（满足结构扫描 + tracking_* 检查）；子表供研发/数据落地、可持续维护。

## 错误分诊（PM 友好话术）

| 你会看到类似 | 一句人话 + 明确操作步骤 |
|---|---|
| 未登录 / 登录态失效 | "飞书没登录或过期了。现在扫码登录（终端跑 `lark-cli auth login`），还是本次先用纯文本模式？"——不便重登就按 `00 §降级` 纯文本交付，**别卡住等扫码** |
| 权限不足 / 读不到 doc | "我没这份文档权限。在飞书里把它（或目标文件夹）分享给你自己，或换个有权限的位置。" |
| scope 不足报错 | "CLI 版本旧了。跑 `lark-cli update` 升级后重试，别急着授权宽 scope。" |
| 大写入/上传报 EOF、connection reset | "多是代理问题（不是文档问题）。写/上传命令直连重试：给命令加前缀 `env -u HTTPS_PROXY -u HTTP_PROXY -u https_proxy -u http_proxy`（细节见 lark-cli 自带文档；`lark-docx-authoring` skill 仅 Claude Code 可用）。读操作不受影响。" |
| wiki 链接读不出 | "wiki 一般能直读；不行就打开 wiki 文档，用地址栏出现的 docx 链接给我。" |
| 网络瞬态超时 | "网络抖了一下，稍等重试；查下 VPN/代理。" |
| 增量授权返回"新授予 scopes：空" | "这个 scope 被公司管理员禁用了，扫码也给不了。别反复重试——改走降级路径（如手动在飞书 UI 操作），或找管理员开。" |

## 提审 · PRD Bot 官方内审（发布后的正式准入入口）

> 本 kit 的自检只是**写作侧逻辑内审**；**正式准入以 PRD Bot（@coast.lin 的准入门禁产品）的评审为准**。发布完成后主动提醒产品提审——**提审动作由产品自己完成（约 1 分钟），本 kit 不代发**（实测 `im +chat-list` 列不出应用/bot 单聊会话，自动化不可靠，勿尝试代发消息）：

1. 飞书里搜「**PRD Bot**」打开对话（应用/BOT）。
2. 在会话里发送 `/review <PRD 文档链接>`（**纯文本即可，官方支持的触发格式；无需提前分享文档**）。
3. bot 回「PRD 审查完成」报告（分数/结论/摘要）；产品把报告贴回来，kit 按 `04`/`05` 帮忙按评审意见补齐缺口。
