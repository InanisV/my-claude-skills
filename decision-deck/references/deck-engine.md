# deck 引擎用法

单文件 HTML，examples/deck-template.html。复制一份改内容，不改结构。tokens 和 mexc-infographic/references/design-tokens.md 的 :root 一致，改那边同步改这里。

## 1. 文件结构

```
<section class="slide" data-seconds="60" data-title="目录里显示的短标题">
  <h1 class="slide-title">观点句标题，<em>金色是关键结论</em></h1>
  <div class="band"><span class="on1">一、第一件事</span><span>二、第二件事</span><span>三、第三件事</span></div>
  <div class="visual">…一个视觉…</div>
</section>
```

- 一页一个 section，一个 section 一个 .visual；两个 .visual 就是两页
- 正文页标题下是三段步骤带 `.band`，当前段加 `.on1 / .on2 / .on3`（绿、蓝、金），三步都算的页三段全亮；`.kicker` 只用在封面和附录，正文页不用
- 正文页没有 `.src`，来源和口径写进附录页；`.src` 只允许出现在附录 section 里
- data-seconds 是本页讲多久，T 键计时对照总时长；导出的页脚只留页码
- 页序就是 section 顺序，附录页放最后，加 class `appendix`，data-seconds 写 0
- 概念稿页加 `<span class="wm">概念 · 示意数据</span>`，换成设计稿后改成 `设计稿 · 示意数据`，老板可能转发

## 2. 页面类型

10/23 定稿后常用的九种在前，旧有的在后。一页只放一种类型。

| 类型 | class | 用在 | 四格 |
|---|---|---|---|
| 封面三机 | `.slide.cover` + `.cover-strip`（三个 `.pw` 手机各配 `.lab`） | 一句判断、开场问题、三台手机各配一句预告三步；不放大数 | 结果 |
| 合并页 | `.merge` = `.shots-3`（三个 `.shotcard`）+ `.divider` + `.ours`（手机 + `.tiles`） | 左边三家真机，右边我们的现状加两块大字 | 结果 |
| 三步页 | `.steps3` = 三个 `.col`（`.stephead` + `.pw.m` + `.chip`）夹两个 `.ar` | 三步总览，每步一台手机加时间 chip | 资源 |
| 三栏大手机页 | `.withval` = `.steps3` + `.vals`（三个 `.vt`） | 一个功能的三步流程，右侧三块价值 | 资源 |
| 图加手机页 | `.diag-phone.small` = `img.d` + `.pcol`（手机 + `.pcap.big`），下接 `.valband` | 一张图示加一台手机，底部三块价值 | 原因、风险 |
| 图加价值带页 | `.diag.small` + `.valband` | 一张宽图示（时间线、底座）加底部三块价值 | 原因 |
| 现状页 | `.today` = `.pw` + `.tiles`（`.tile`，红色的加 `.wide`，进行中的加 `.blue`） | 我们今天有什么、缺什么 | 结果 |
| 价值总览页 | `.valcols` = 三个 `.valcol.c1/.c2/.c3`（`h3` + `.lead` + 两个 `.vt`） | 三步各自带来什么，每列一句结论 | 结果 |
| 路线页 | `.rm .tl`（时间轴）+ `.gantt`（`.lab` + `.bar.g/.b/.y`，模块做 `span`） | 三期各一行，错开的色块 | 资源 |
| 架构附录页 | `.legend` + `.arch`（`.ly` = `b` + `.ms` 的 `.m.p1/.p2/.p3`） | 分层 chip，按期配色，不用表 | 附录 |
| 封面大数 | `.slide.cover` + `.bignums` | 只在成果类用，封面不放大数 | 结果 |
| 反差页 | `.paths` 两个 `.path`，新的加 `.new` | 旧路径 vs 新路径，旧做法 vs 新做法 | 原因 |
| 曲线加事件页 | `.curve` = `.chart`（svg 或 img）+ `.events` | 一条曲线，三个编号事件 | 结果、原因 |
| 矩阵页 | `table.matrix`，单元格 `.ok .partial .no .unknown`，我们的列加 `.us` | 功能对比，我们一列全叉 | 风险 |
| 三栏案例页 | `.cols-3` 三个 `.card`，截图放 `.shot` | 三个竞品机制 | 原因 |
| 手机帧页 | `.phone-row` = `.phone` + `.values` | 录屏或设计稿整帧 + 价值清单 | 资源 |
| 选项页 | `.cols-3` 三个 `.card`，倾向的加 `.hot`，`.pros .cons` | A/B/C 各自代价 | 风险、资源 |
| 三卡页 | `.cols-3` 三个 `.card` | 一句能被转述的话下面三条变化 | 结果 |
| 讨论页 | `ol.questions`，可选 `.board` | 三问；讨论型会议 B 键开看板 | 资源 |
| 附录页 | `.links` + `table.plain` | 档案链接、弹药页索引 | |

类型不够用时先问这页是不是两个观点，再考虑加类型。方向类第一次使用没用到反差页、曲线页、选项页、讨论页，它们留给调研类、拍板类和成果类。

### 2.1 价值块和步骤带的写法

- `.vt` 价值块：`<b>` 一句大字（30 像素，不超过 12 字），`<span>` 一句说明（22 像素白字，不超过 16 字）。左边框颜色跟当前步骤：`.v1` 绿、`.v2` 蓝、`.v3` 金
- 价值按老板关心的三件事写：内容从哪来（内容供给跟着交易量走）、用户为什么来（用户为人而来）、交易和收入从哪来（每张卡都是交易入口）
- 步骤带三段文字就是三个口号，全 deck 不改字；封面不放带子
- 手机 `.pw.m` 缩放 0.76，三台加两个箭头占 1068 像素，右侧价值列 440 像素；没有价值列的三步页用 0.82

### 2.2 图示怎么画

- 聚人、分层、时间线这类图示用 SVG 画成 PNG 再放，画法：人物用字母头像不用空心圆，中心人物用星标不用两个字挤在圆里，圈外的人灰色，中心加光晕，标签用 chip 放在图内，字只做标签
- 图示里的标签也是大白话（持仓并公开的人、来看这个币的人），不用巧句
- 一张图示一个意思；图示加手机是最常用的组合，图在左 720 像素，手机在右

## 3. 快捷键

| 键 | 作用 |
|---|---|
| ← → 空格 PageUp PageDown | 翻页，地址栏 #p3 可直接定位 |
| Home End | 首页、末页 |
| G | 目录，点页跳转 |
| F | 全屏，投屏前按 |
| T | 计时开始 / 暂停；超过总时长变红 |
| R | 计时归零 |
| B | 讨论页的观点看板开关（只在讨论型会议用） |
| 点图片 | 放大，Esc 或再点关闭 |

观点看板只存本浏览器的 localStorage，导出是 JSON，会后备份；不在 PDF 里。

## 4. 视觉素材怎么来

- 真机截图：`.shot` 或 `.phone` 里放 `<img>`；文件名带产品、端、日期（fomo_app_20261015.png）。base64 内嵌保持单文件，或同目录相对路径并一起打包
- 录屏裁剪进手机框（竞品走查，不超过 30 秒，静音循环，只放一个动作）：

```
# 从第 12 秒起截 20 秒，缩到 780 宽，去声，H.264，播放器兼容
ffmpeg -ss 12 -t 20 -i 录屏.mp4 -vf "scale=780:-2" -an -c:v libx264 -pix_fmt yuv420p -movflags +faststart clip.mp4
```

```
<div class="phone"><video src="clip.mp4" autoplay muted loop playsinline></video></div>
```

- 设计稿整帧：390×844 原比例，不裁切、不套局部放大；Figma 导出 2 倍
- Claude Design 出的长页（1300 像素以上）：裁上半屏 844 进手机框，不缩放整页；长页的下半部分不在 deck 里出现
- 概念稿：Claude Design 出图后逐项核对（它会自己发明内容），整页加 `.wm` 水印；在真实设计稿的卡位上合成的概念（合约页换一张卡）用 PIL 直接改像素，字体用设计稿同款，标概念稿
- 自绘 SVG 只做占位，有了设计稿就换，不往上加字
- 曲线：数据自己拉（见 proposal-playbook/references/evidence-playbook.md），svg 的 path 用脚本从 CSV 生成，不手画；事件编号圆标的坐标按数据点算，不估
- 广告片级别的视频归 ai-demo-video-workflow，deck 只嵌它的成片

## 5. 导出与检查

```
python scripts/export_deck.py deck.html out/            # PDF + 每页 PNG（2 倍）
python scripts/export_deck.py deck.html out/ --sheet    # 另出 contact.png 接触表，每版自检用
python scripts/export_deck.py deck.html out/ --no-png   # 只要 PDF
python scripts/check_deck.py deck.html                  # 禁词、正文小字、kicker、秒数
python scripts/check_deck.py deck.html --ban 战队 验真   # 追加本项目禁词
```

- 导出时页脚只留页码（deck 名、本页秒数、计时自动隐藏）
- 每版先看接触表再看单页，三栏页、路线页、封面各放大看一次；溢出、折行、压到页脚的页改完再交
- PDF 转发用，Lark 上传 PDF；PNG 贴飞书、给 Yoki 预审（她看图不开 HTML）
- 视频页导出只有首帧，演示用 HTML 全屏，deck 和 mp4 一起打包
- 沙箱里 Chrome 在 /opt/google/chrome/chrome；Mac 上 playwright 自带 chromium，或设 CHROME 环境变量

## 6. PPTX 兜底

只在别人要改稿时出。用 pptx skill 新建 LAYOUT_WIDE，每页 `addImage` 导出的 PNG 全幅铺满，视频页用 `addMedia` 嵌 mp4，讲稿写进 `addNotes`。不逐页重排版，PNG 就是定稿。

## 7. 投屏前检查

- F 全屏后页面四边都在屏内（投影比例不是 16:9 时上下留黑边正常）
- 视频自动播放：Chrome 对静音视频允许自动播放，不静音的不会自动播
- 字体：Mac 用 PingFang，Windows 回落到微软雅黑，标题宽度留 10% 余量
- 页脚计时在投屏上也可见，不想让听众看到就按 R 归零不按 T

## 8. Claude Design prompt 模式

高保真原型让 Claude Design 出，Claude 写 prompt。一份 prompt 的结构：

1. 角色和产品：为哪个 App 的哪组页面，尺寸 390×844，主题色、字体一行写死（tokens 的色值）
2. 产品规则，六到八条：设计必须遵守的事（只出百分比、没有某类标识、两种人共用一个模板），每条一句
3. 页面清单，每页一段：顶部、主体、底部各放什么，用产品词不用设计词，示例数据用示意值和"交易者 A"这类名字
4. 不要做的：标识、金额、配色、营销化、水印
5. 收尾：先出两页让我选方向，再补齐

出来的稿子逐页核对规则，再按本文第 4 节裁进手机框。