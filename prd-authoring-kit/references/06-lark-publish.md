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

- 放指定位置：`--parent-token <wiki节点token或文件夹token>`（问产品要目标位置；默认建个人空间根）。
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

- 回给产品：飞书 URL + `05-self-review-gate.md` 自检简报 + 一句"改了哪几处/补了哪几块"清单（迭代时尤其要给，让产品知道人工内容没动）。
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
