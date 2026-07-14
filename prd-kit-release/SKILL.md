---
name: prd-kit-release
description: prd-authoring-kit（PRD 写作助手）的维护与发布 playbook——发 npm/GitHub 版、生成并发布 AI Store 版、改商店文案、两版差异纪律、指南文档同步。当用户（Noah）说「发布 kit / 发新版 / bump 版本 / 更新 store 包 / 改商店描述 / republish / 更新指南文档」等 kit 维护发布类诉求时使用。仅维护者本人用，与 kit 本体（写 PRD 的技能）无关。
---

# prd-authoring-kit 维护与发布 playbook

> 你在帮 Noah（@noah.zhan）维护他的 PRD 写作工具包。**动手前先读本文件到底**；store 差异的唯一权威是 canonical 仓库根的 `STORE-DIFF.md`，本 skill 只带流程与固定标识、不复述差异清单（防漂移）。

## 资产地图（固定标识）

| 资产 | 位置 / 标识 |
|---|---|
| canonical 仓库（npm 组内版，全功能） | `/Users/user/Downloads/prd-authoring-kit`（GitHub `InanisV/prd-kit`，main 分支；作者署名一律 Noah Zhan / noah.zhan@mexc.com，勿用真名） |
| store 差异唯一权威 | canonical 根 `STORE-DIFF.md`（含 决策记录 / 两张差异表 / manifest 定稿 / 待发布队列 / 敏感词扫描命令 / republish 流程） |
| AI Store | `https://ai.cddaxia.com`，商店条目 item_id `6a5597c732063c472d35045c`，CLI=`mexc-ai-store`（token 已在本机配置，绝不回显） |
| 商店指南文档 | wiki `Ay8gwh4iPiuzprkU6xEuAnOUs5c` → 底层 docx `R8QIdm2zvozmPpxasl5uK2xns7g`（lark-cli overwrite 更新） |
| npm 版安装指南文档 | wiki `R6B8w1ToOiXxXlkATMFu72fAskf` → 底层 docx `Lmv2dpReqoAgivxPkM5ulAxgscd` |
| lark-cli 开通（对外指引用这个） | IT 文档 wiki `JrHowKV06iDlafkSD2Au7UqEs6g`；问题找 IT 负责人 **@henry.wang** |
| 正式准入 | **PRD Bot**（@coast.lin 的准入门禁）：会话里发 `/review <PRD 链接>` 纯文本即可，无需分享文档 |
| 署名口径 | coast.lin=审查标准事实归属（文首）；noah.zhan=唯一反馈联系人（文末）；两名字不并排在结尾；**包内**不出现「C 端增长组」，**商店描述**里写「产品部 C 端增长组共建」 |

## 发布 npm / GitHub 版（随时可发）

1. 改 canonical → bump `package.json` 版本（已发布的版本号绝不复用，任何改动即 bump）。
2. `git commit`（消息带 `Co-Authored-By: Claude <型号> <noreply@anthropic.com>`）→ `git push origin main`。
3. **npm publish 由 Noah 手动跑**：`npm publish --access public --otp=<6位码>`（账号 inanisv 开了 2FA；`npm login` 报 ECONNREFUSED 127.0.0.1:7890 = 终端残留死代理 env，`unset http_proxy https_proxy all_proxy` 即好）。
4. **硬顺序**：改动涉及 Kiro steering 时，必须**先 publish 成 npm `latest`**，再让任何工作区拿到新 steering（其第 0 步用时自更新拉 `@latest`，顺序反了会拉旧版反向覆盖）。

## 发布 AI Store 版（⚠️ 两次发布至少间隔一周——每次都要开发手动人审）

小改动先记进 `STORE-DIFF.md` 的「待发布队列」，攒批发布。流程：

1. **staging 从 canonical 重新生成**（先删旧目录再拷——陈旧快照复活过已删文件），照 `STORE-DIFF.md` 两张差异表逐条 apply。
2. **敏感词扫描**：跑 STORE-DIFF 里的 grep 命令（含词边界，防 `modify`→`dify` 假警报），**必须全零**。
3. **manifest**：照 STORE-DIFF「manifest 定稿」块写入；bump `version`、更新 `built_from`。
4. ⚠️ **商店页字段全部由包内文件自动生成**：名称/描述/标签/适配环境 ← `mexc-ai-store.json`；README 摘要 ← `README.md` **文件开头**截取（定稿摘要段放文件最开头、署名注释放文件尾）。**web 表单手填会被下次 update 覆盖，别在表单上改文案。**
5. zip（排除 .DS_Store/__MACOSX）→ `mexc-ai-store packages preview --cwd <staging>`（`risk_findings` 必须 `[]`）→ **向 Noah 确认后** `mexc-ai-store packages update --id 6a5597c732063c472d35045c --cwd <staging> --yes` → 提醒 Noah 找管理员人审。线上旧版在批准前照常可用、拒绝只丢候选。
6. **同步下游**：商店指南文档（R8QI）如涉及则 lark-cli 更新；STORE-DIFF 记账（改一边必记账，凭记忆净化必漂移）；待发布队列清空已发项；memory 有变更也同步。

## store 版红线（提交前自查）

无脚本 · 无 telemetry/使用采集 · 无 `npm`/`npx`/`@larksuite` 字样（lark-cli 开通只指 IT 文档+@henry.wang）· 无 `dify` · 无真实内部人名/Jira 单号 · 语气中性 · 无「C 端增长组」字样（描述除外）。

## 环境纪律（实测教训）

- macOS 无 `timeout` 命令——限时用 `npm_config_fetch_timeout` 等环境变量。
- 交给 agent 终端的采集/静默命令：**单行（分号连接）+ 结尾 `echo`**，否则 Kiro 等终端卡 "Working"。
- lark-cli：`needs_refresh` ≠ 重登；`--content` 以 `@` 开头会被误判 @file，用 stdin；写操作前缀 `LARK_CLI_NO_PROXY=1`。
- `im +chat-list` 列不出 bot 单聊——别设计自动向 bot 发消息的流程。
- 判 lark-cli 写入成功看 `.data.result=="success"`，别只看 `.data` 存在。

## 相关记忆（本机 auto-memory 有更全的演化史）

`prd-authoring-kit` / `ai-store-publish` / `prd-kit-autoupdate-launchd` / `kiro-hooks-deprecated` / `lark-cli-environment`——本 skill 与记忆冲突时，**以 canonical 仓库（git）与 STORE-DIFF.md 为准**，其次本 skill，记忆仅作背景。
