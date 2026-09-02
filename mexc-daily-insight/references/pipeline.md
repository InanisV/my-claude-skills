# 数据源与采集管线（全部经 8/31 实测）

依赖：lark-cli（已授权 user 身份）、curl、python3（macOS 自带即可，勿假设有 jq）。

## 1. 当日数据卡（每天 ~10:31 推送）

来源群：「增长产品每日数据洞察」`oc_05225706566b8377cd3fb4756bad1a17`，Datawind 机器人卡片含两图（注册DAU＋UJ 核心链路）。

```bash
# 找当日卡片消息，提取 message_id 与两个 img_key（在卡片 content 的 img_key:img_v3_... 处）
lark-cli im +chat-messages-list --chat-id oc_05225706566b8377cd3fb4756bad1a17 --start <今日日期> --order asc --no-reactions --as user
# 下载两图后用视觉读图提取指标
lark-cli im +messages-resources-download --message-id om_xxx --file-key img_v3_xxx --type image --output ./dau.png --as user
```

读图要点：核心指标区（整体/拉新/留存/召回 DAU 及环比、7日留存率）、DAU 拆解 14 天走势、分间隔留存率（同时看 30 天趋势图防高基数误读）、UJ 表（W 周均+近4日：注册转化率、KYC/注册、FTD/KYC、EFTD 等）。**分群×渠道渗透率对比**（push/email 触达 ÷ 分群 DAU）是比单点环比更强的诊断工具。

## 2. 竞品版本晨查

跑 `scripts/competitor_lookup.sh`（iTunes Lookup API，跨区一致）。App ids：Bitget 1442778704 / Bybit 1488296980 / Binance 1436799971（美区不上架，用 sg/gb）/ OKX 1327268470 / Gate 1294998195；参照自查 MEXC 1605393003。发版日期与版本号只认 API 返回；notes 是套话就如实写「无实质信息」。语言支持核查可用 lookup 返回的 `languageCodesISO2A`（注意：元数据可能超报 App 内实际列表）。

## 3. 用户声音增量（只扫近 24–48h）

- Google Play：`play.google.com` 详情页 batchexecute 按语言池拉 newest（无法按国家拆分，按语言池统计）
- iOS：`https://itunes.apple.com/<区>/rss/customerreviews/page=1/id=1605393003/sortby=mostrecent/json`（每 storefront 最多约 500 条，无日期筛选）
- Reddit：官方域被封，用 redlib 镜像（redlib.privacyredirect.com）看 r/MEXC_official 及马来/菲律宾等区域版块 new；评论级检索受限，提及量系统性低估
- Trustpilot：`trustpilot.com/review/www.mexc.com?sort=recency`（用「体验日期」不用发布日期，两者差 5–25 天）
- 已知缺口：X 原生声量、中文社区（即刻/知识星球是 Yoki 点名信源，尚未接入）
- 大规模深扫（多路子代理并行）只在周一补库时做，日常只做增量

## 4. 洞察登记表（Yoki 要求，洞察须落表并导向落地）

表：wiki `RRovwEEp3iLbi7k6TOhuohJDs3e` sheet `azRDmv`。列：研究人/研究方向/研究类型/核心问题/当前阶段/（空列F）/预计产出时间/备注/I列=假设验证专用（写假设全文）。研究类型枚举：数据驱动/假设验证/竞品分析/用户洞察。行2「张三」为示例行。

```bash
# ⚠️ 写前必须重拉最新——此表多人高频并发编辑，行号小时级漂移，曾发生竞态覆盖同事行的事故
lark-cli sheets +csv-get --url "https://l7jipx1bfq.larksuite.com/wiki/RRovwEEp3iLbi7k6TOhuohJDs3e" --sheet-id azRDmv
# 确认目标空行后写入（--cells 恒为二维数组），写完必须回读校验
lark-cli sheets +cells-set --url "<同上>" --sheet-id azRDmv --range A<n>:I<n> --cells - <<'JSON'
[[{"value":"noah"},{"value":"研究方向"},{"value":"假设验证"},{"value":"核心问题"},{"value":"当前阶段"},{"value":""},{"value":"M.DD"},{"value":"备注：文档+证据+行动"},{"value":"假设全文"}]]
JSON
```

写入与更新一律先经值班人确认。假设 fail 时更新「当前阶段」为 fail 并注明依据——fail 是合法结局。

## 5. 群消息发送

值班人自己粘贴到「C端增长组」`oc_9c8ff06152c0dd3303ce42bc6ed9e61f`（用户身份无发消息 scope；bot 代发不显示为本人，仅在值班人明确要求时用）。发送时间：规范是早 10 点前，组内实际先例最晚 20:50，尽量早。

## 6. 连续剧机制

- 当日主打若是「假设＋数据请求」，次日必须跟进：数据回来→给「成立/证伪」结论与下一步；没回来→一句进展。
- 竞品重大动作可拆日发（当日播报事实，次日配用户声音深挖）。
- 交办类（QA 排查、复查商店负面率）记入库存并标复查日期。

## 7. 每周节奏

周一：深扫补库（可用多路子代理并行：Reddit/商店/评分舆情/竞品动作）＋《竞品/数据动向周报》归属上周值班人（确认交接）。周五（值班末日）：向下一棒交接（点名下一位+登记表状态清点+库存移交）。
