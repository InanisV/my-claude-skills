# deck 引擎用法

单文件 HTML，examples/deck-template.html。复制一份改内容，不改结构。tokens 和 mexc-infographic/references/design-tokens.md 的 :root 一致，改那边同步改这里。

## 1. 文件结构

```
<section class="slide" data-seconds="60" data-title="目录里显示的短标题">
  <div class="kicker">段落标签（PART 1 · 别人为什么赢）</div>
  <h1 class="slide-title">观点句标题，<em>金色是关键结论</em></h1>
  <div class="visual">…一个视觉…</div>
  <div class="src">来源或口径一行小字（可省）</div>
</section>
```

- 一页一个 section，一个 section 一个 .visual；两个 .visual 就是两页
- data-seconds 是本页讲多久，页脚显示，目录汇总，T 键计时对照总时长
- 页序就是 section 顺序，附录页放最后，data-seconds 写 0
- 概念稿页加 `<span class="wm">概念 · 示意数据</span>`，老板可能转发

## 2. 九种页面类型

| 类型 | class | 用在 | 四格 |
|---|---|---|---|
| 封面 | `.slide.cover` + `.bignums` | 一句判断、开场问题、三个大数 | 结果 |
| 反差页 | `.paths` 两个 `.path`，新的加 `.new` | 旧路径 vs 新路径，旧做法 vs 新做法 | 原因 |
| 曲线加事件页 | `.curve` = `.chart`（svg 或 img）+ `.events` | 一条曲线，三个编号事件 | 结果、原因 |
| 矩阵页 | `table.matrix`，单元格 `.ok .partial .no .unknown`，我们的列加 `.us` | 功能对比，我们一列全叉 | 风险 |
| 三栏案例页 | `.cols-3` 三个 `.card`，截图放 `.shot` | 三个竞品机制 | 原因 |
| 手机帧页 | `.phone-row` = `.phone` + `.values` | 录屏或设计稿整帧 + 价值清单 | 资源 |
| 选项页 | `.cols-3` 三个 `.card`，倾向的加 `.hot`，`.pros .cons` | A/B/C 各自代价 | 风险、资源 |
| 三卡页 | `.cols-3` 三个 `.card` | 一句能被转述的话下面三条变化 | 结果 |
| 讨论页 | `ol.questions`，可选 `.board` | 三问；讨论型会议 B 键开看板 | 资源 |
| 附录页 | `.links` + `table.plain` | 档案链接、弹药页索引 | |

一页只放一种类型。类型不够用时先问这页是不是两个观点，再考虑加类型。第一次真实使用后把没用到的类型删掉。

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
- 概念稿：Claude Design 出图后逐项核对（它会自己发明内容），整页加 `.wm` 水印
- 曲线：数据自己拉（见 proposal-playbook/references/evidence-playbook.md），svg 的 path 用脚本从 CSV 生成，不手画；事件编号圆标的坐标按数据点算，不估
- 广告片级别的视频归 ai-demo-video-workflow，deck 只嵌它的成片

## 5. 导出

```
python scripts/export_deck.py deck.html out/          # PDF + 每页 PNG（2 倍）
python scripts/export_deck.py deck.html out/ --no-png  # 只要 PDF
```

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
