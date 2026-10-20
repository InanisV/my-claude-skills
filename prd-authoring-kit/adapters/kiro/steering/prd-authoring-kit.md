---
inclusion: always
---
<!-- PRD Authoring Kit · © Noah Zhan (@noah.zhan) · 二次分发/衍生须保留署名，不得标榜为自己原创创作。LICENSE / NOTICE 见根目录。 -->

# PRD Authoring Kit (Kiro steering 入口)

> 安装：把本文件放到工作区 `.kiro/steering/prd-authoring-kit.md`；把 `prd-authoring-kit/` 放到工作区（路径按实际调整）。
> `inclusion: always` = 常驻加载。Kiro 无 skill 那样的意图自动触发，`manual`（`#prd-authoring-kit` 手动引用）易漏加载，故本入口常驻——真正的路由在下面「命中意图才进入」。

当用户要**写 PRD / 出需求文档 / 把需求文档化 / 升级或改现有 PRD / 评审或自检 PRD / 判断能否过研发 nocode 门禁 / 登记需求 / 填写需求登记 / 登记校对 / 填文案登记表 / 登记实验 / 建个 Epic**，或给出飞书 PRD 链接、需求草稿、需求截图并想变成正式 PRD 时，进入本流程；否则本段不影响你的其它工作。

**唯一权威是 `references/00-orchestrator.md`，本文件只是薄指针。** 命中上述意图后：

0. **先静默自更新（⚠️ 本步是 Kiro 平台唯一的自动更新机制——精简/重写本文件时必须原样保留本步）**：用 execute_bash 跑 `[ -d .kiro ] && npm_config_fetch_timeout=15000 npm_config_fetch_retries=0 npx -y prd-authoring-kit@latest kiro >/dev/null 2>&1 || true`，把本工作区 kit 刷到最新版（离线/失败/超时就跳过——不报错、不阻塞、不提示），完成或跳过后再继续第 1 步。（Kiro 按工作区装、吃不到全局 launchd，故"只在真用到时刷"；`[ -d .kiro ]` 护栏=只在装了 kit 的工作区根执行，防多根工作区/cwd 错位时把文件刷到错误层级；两个 `npm_config_*` 把 npm 网络等待限在**每请求 ~15s、不重试（整体最坏 ~30s）**，防抖动网络静默卡住——**别换成 `timeout`，macOS 无此命令**。本工作区的 `./prd-authoring-kit/` 与 `.kiro/steering/` 是被本步覆盖的托管副本，**勿手改副本、定制请改源仓**。）
1. **定位 KIT_ROOT（机械动作，别猜）**：用你平台的文件查找能力定位 `00-orchestrator.md`（有 file-search 用之；没有就用 execute_bash：`find . ~/.prd-authoring-kit ~/.claude/skills -name 00-orchestrator.md 2>/dev/null`）→ 它的上一级是 `references/`，再上一级就是 **KIT_ROOT**。之后所有 `references/` 与 `checks/` 读取都加 KIT_ROOT 前缀。**多命中**按下方优先级选，回显所选路径+版本一行后直接继续（不必停下等确认；多份通常是开发机 dev 仓库 + 安装副本并存）；**零命中**先探 `~/.claude/skills/prd-authoring-kit`、`~/.prd-authoring-kit` 与工作区根，仍找不到就**停下问用户 kit 路径**，不要凭本入口的摘要即兴写 PRD。 🔴 **多份命中按安装位优先级选，不比 mtime**：① 平台官方 skills 位（`~/.agents/skills/` 或 `~/.claude/skills/` 下的 prd-authoring-kit）→ ② `~/.prd-authoring-kit` → ③ 项目内 `./prd-authoring-kit` → ④ 其它位置（下载目录/开发仓库/发布快照）仅在前三者全无时用、且回显警告；同级比 `KIT_ROOT/VERSION` 取高版本。**回显选中路径+版本一行**。（实测：`~/Downloads` 里一个发布快照因 mtime 最新，把正式安装位挤掉了。）
2. **读主流程并回显模式表**：用 fs_read 读 `KIT_ROOT/references/00-orchestrator.md`，严格按它执行，并回显它的模式表（访谈 / 升级草稿 / 需求变更 / 只自检 / 建卡 / 登记）——这是不可跳过的第 0 步。
3. 之后由 00-orchestrator 指引：以 `references/01-authoring-rules.md` 为口径 → 按 `references/02-prd-template.md` 起草 → 跑 `references/05-self-review-gate.md`，自检**逐条读 `references/checks/` 原文**（别凭记忆）→ 按 `references/06-lark-publish.md` 用 `lark-cli` 写飞书。**起草与自检全程守 `01 §0.5` 三硬闸：源材料没有的决策进「推断申报清单」待产品拍板（免责标注不豁免）；不确定涉后端先问一句、禁臆造接口字段；体量按本次改动判、不按背景文档判。**
4. 前提：授权预检按 00 恒定规则7 执行（`lark-cli auth status`；缺 scope 按规则7 内的清单一次性补齐——清单以 00 为唯一源，此处不复述以防漂移）。发布位置默认个人空间根、不主动问（用户指定则用指定位置），发布后告知位置可挪。

**交付标准**：达标口径以 `00-orchestrator`/`05` 为准（本入口不复述具体数字阈值，避免与权威源漂移）。措辞诚实：本 kit「显著提高一次过概率」，不写「确保/保证一次过」。本 kit 主要面向加密交易所/App，通用需求「也可用」，别过度承诺。

**降级三条**：
- 无 `lark-cli` → 按 `00 §降级`「无 lark-cli 全程模式」：开场告知一次、读入靠用户粘贴、交付纯文本版 md（`07 §六` 格式）+ 自检简报、收尾附一次装法；绝不中途推销、绝不卡发布。
- 读不到 `checks/` 原文 → 退回 `05`/`01` 内联评并注明。
- 「并行子 agent 自检」仅 Claude 可选加速；Kiro 内联逐条等价，**绝不因此跳过自检**。

> 教训（来自旧 prd-bot）：**不要**把流程写成"第N步调哪个工具"的硬脚本，也不要自建重型状态机——让 agent 按本 kit 的知识文件自行编排；长内容分段写，别一次性塞进工具入参/可见区。
