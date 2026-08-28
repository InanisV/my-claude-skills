# UI 复刻配方（暗色交易所风格 · 从设计稿抠出来的细节）

默认服务 MEXC 风格的暗色 App demo；换产品时整套 token 跟着换，方法不变。
完整可运行参考：`example-mexc-square-v3.html`（本目录）。

## 1. Design Tokens（MEXC 暗色）

```css
:root {
  --bg-0:#000;            /* 页面底色：MEXC 新版设计是纯黑，不是深灰 */
  --bg-1:#101214; --bg-2:#1C2127; --bg-3:#2B3139;
  --line:#1E2329;         /* 卡片分隔用更暗的 #16191D hairline */
  --text-0:#FFF; --text-1:#C7CCD4; --text-2:#848E9C; --text-3:#5E6673;
  --up:#0ECB81; --down:#F6465D;      /* 涨绿跌红（站点默认） */
  --blue:#4A80FF;         /* cashtag / 链接蓝 */
  --fab:#2B5FF1;          /* 主按钮 / FAB 品牌蓝 */
  --warning:#F0B90B; --brand-1:#00C9A7;
  --ai-1:#7E96FF; --ai-grad:linear-gradient(92deg,#7E96FF,#00C9A7);  /* AI 专用 */
}
font-family: -apple-system, BlinkMacSystemFont, "PingFang SC", "Segoe UI",
  "Microsoft YaHei", Roboto, sans-serif;
.num { font-variant-numeric: tabular-nums; }   /* 所有数字 */
```

左栏（演示台）与右栏（产品）视觉分离：左栏底 `#14171A`，右栏画布放射渐变
`radial-gradient(ellipse at top, #14181E 0%, #0B0E11 60%)`。

## 2. 手机壳（375×780）

```html
<div class="phone"><div class="screen" id="screen">
  <div class="notch"></div>
  <div class="statusbar"><span>9:41</span><span class="icons" id="sb-icons"></span></div>
  <div class="page …" id="pg-xxx">…</div>   <!-- 每个页面一个 .page，show() 切换 -->
  <div class="toast" id="toast"></div>
  <div class="ghost" id="ghost"></div>
</div><div class="homebar"></div></div>
```

```css
.phone { width:375px; height:780px; background:#000; border-radius:46px; padding:11px;
  box-shadow:0 24px 70px rgba(0,0,0,.65), 0 0 0 1px #25282E; position:relative; }
.screen { width:100%; height:100%; background:var(--bg-0); border-radius:36px;
  overflow:hidden; position:relative; }
.notch { position:absolute; top:8px; left:50%; transform:translateX(-50%);
  width:108px; height:27px; background:#000; border-radius:15px; z-index:50; }
.page { position:absolute; top:44px; bottom:14px; left:0; right:0;
  overflow-y:auto; display:none; background:var(--bg-0); }
.page.on { display:block; }
.page::-webkit-scrollbar { display:none; }
```

状态栏三件套必须 SVG（emoji 会毁掉真机感）：

```js
$('sb-icons').innerHTML =
  '<svg width="18" height="11" viewBox="0 0 18 11" fill="#fff"><rect x="0" y="7" width="3" height="4" rx="0.8"/><rect x="4.7" y="5" width="3" height="6" rx="0.8"/><rect x="9.4" y="2.5" width="3" height="8.5" rx="0.8"/><rect x="14.1" y="0" width="3" height="11" rx="0.8"/></svg>'
+ '<svg width="16" height="12" viewBox="0 0 16 12" fill="#fff"><path d="M8 10.8 5.8 8.4a3.2 3.2 0 0 1 4.4 0z"/><path d="M8 4.9c1.6 0 3 .6 4.1 1.7L10.9 7.9a4 4 0 0 0-5.8 0L3.9 6.6A5.9 5.9 0 0 1 8 4.9z"/><path d="M8 1c2.7 0 5.2 1 7.1 2.8l-1.2 1.3A8.3 8.3 0 0 0 8 2.9a8.3 8.3 0 0 0-5.9 2.2L.9 3.8A10.2 10.2 0 0 1 8 1z"/></svg>'
+ '<svg width="25" height="12" viewBox="0 0 25 12"><rect x="0.5" y="0.5" width="21" height="11" rx="3.2" stroke="rgba(255,255,255,.45)" fill="none"/><rect x="2.2" y="2.2" width="17.6" height="7.6" rx="2" fill="#fff"/><path d="M23 4v4c1-.3 1.7-1 1.7-2S24 4.3 23 4z" fill="rgba(255,255,255,.45)"/></svg>';
```

## 3. SVG 图标库

统一函数 + `data-ic` 注水（动态渲染的容器记得 `hydrate(container)`）：

```js
function ic(n, s, sw){
  s = s || 22; sw = sw || 1.6;
  const P = { /* name: '<path …/>' —— 完整 30+ 图标见 example v3 的 ic() */ };
  return '<svg width="'+s+'" height="'+s+'" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="'+sw+'" stroke-linecap="round" stroke-linejoin="round">'+(P[n]||'')+'</svg>';
}
```

范例 v3 内置图标（直接抄 P 表）：person / scan / mag / headset / msg / close /
back / redo(分享·循环箭头) / dots / cmt(评论气泡) / thumb(点赞) / pic / coin /
plus / mexc(M logo) / markets / trade / futures / wallet / dl / tg / edit /
info / globe / reply / bell / gift / crown / ingot / uplus / hexa / chute /
rocket / grid4 / chevdown / check。

头像系统（无真实素材时的可信做法）：

```js
const AV = { me:{g:['#2F6D7E','#12333D'], t:'T'}, bb:{g:['#7A2E4C','#251019'], t:'B'},
  ob:'logo' /* 品牌号：白底 + SVG 竖条 logo */, mexc:'mexc' /* 官方：黑底描边 M */ };
// 渐变圆 + 首字母 + 内圈高光 .ring —— 比 emoji 头像可信得多
```

## 4. 组件配方（对照设计稿抠出的规则）

**Feed 卡**：`头像40px ｜ 昵称15.5px 粗 · 相对时间 13px 灰 · ··· 右对齐`；
正文 15.5px，`$TICKER` 用 `tokenize()` 上 `--blue`；单图 246×246 圆角 14；
币种 pill = 深底 `#1C2127` + 小圆 icon + 代码白 + 涨跌幅红绿；
动作行**评论在前**（💬 999+）、点赞次之（👍 231）、分享循环箭头右对齐，
计数 `fmt = n>=1000 ? '999+' : n`。

```js
function tokenize(t){ return t.replace(/\$[A-Z]{2,6}/g, m=>'<span class="tk">'+m+'</span>'); }
```

**详情页**：头部只有图标（← ｜ 分享 ···），无标题文案；作者行 + **白底黑字
"关注"胶囊**（已关注→描边灰）；正文 16.5px `white-space:pre-line`；
翻译链接 `🌐 查看翻译/查看原文`（蓝色，仅手动触发）；绝对时间
`19:40 · 2026/08/13`；免责声明 12px `#3F464F`；评论区作者回复带灰底
`作者` chip、`── 展开 N 条回复`；底部 sticky 回复栏 = 输入胶囊 + 👍 + 💬。

**发布器**：✕ ｜ 发布按钮（无内容灰、有内容 `--fab` 蓝）；正文区 div 模拟
（假光标 `.caret` 闪烁）；输入 `$` 弹全宽币种联想行（icon 圆 + $TICKER 粗 +
全称灰右对齐）；底部工具条 `图片 ｜ 币种 ｜ 剩余字数`；**CSS 假 iOS 键盘**
（建议行 我｜的｜是 + QWERTY 三排 + 123/空格/换行 + 😊🎤 底行）——这块是
发布场景真机感的最大来源。

**个人主页**：← ｜ ✎；大头像 84px；名 22px 粗；简介灰；`已加入 MEXC N 年`
深底 chip；`N 关注  N 粉丝`（数字白粗）；`帖子` 下划线页签；审核状态用
**通栏提示行**（ⓘ + 说明文字），不用角标。

**反馈卡**：官方头像 + `MEXC` + 问题 + 两个描边胶囊选项（点选即提交，无独立
提交钮）+ ✕ 关闭；完成态一行绿色感谢 + 冷却说明。

**分享面板**：底部抽屉几乎全屏；海报 = M logo + 品牌字 + 作者行 + 正文
（可滚动）+ 虚线分隔 + 二维码占位 + 引导文案；渠道行 4 圆钮
`保存 ｜ Telegram(蓝) ｜ X(黑) ｜ 更多`。

**端外落地页**：顶部浏览器地址栏（URL 带 `share_id/utm` 归因参数，
monospace）；只读详情；底部 sticky `打开 App` 条；任何互动 → 登录引导抽屉
（标题 + 两行说明 + 蓝色主按钮 + 灰色"取消，继续浏览"）。

**概念/画饼组件**（二期章）：右上角统一 `2.0 概念预览` 金色小 chip；
投票卡（选项条 + 投票后百分比条填充动画 + `自动结算/不可撤回/计入准确率`
meta 行）；战绩徽章（绿色 `✓ 准确率 N%`）+ 锁仓 chip；Trade Setup 卡
（入场/TP/SL/杠杆四列 + 蓝色"一键复制下单"）；AI 归因卡（`✦ 为什么在动` +
2×2 证据格 + 一句话 + 加自选/交易按钮）。页脚必须有"概念示意 · 非本期
交付范围"声明。

## 5. 动效与反馈

```css
@keyframes drop { from{transform:translate(-50%,-8px);opacity:0} to{transform:translate(-50%,0);opacity:1} }
.flash { animation:cardflash 1.6s ease-out; }          /* 新内容进流高亮 */
@keyframes cardflash { 0%{background:rgba(126,150,255,.16)} 100%{background:transparent} }
.likepop { animation:likepop .4s ease-out; }           /* 点赞计数弹跳 */
@keyframes likepop { 30%{transform:scale(1.35)} 100%{transform:scale(1)} }
.skl { /* 骨架屏 shimmer */ background:linear-gradient(90deg,var(--bg-2) 25%,var(--bg-3) 45%,var(--bg-2) 65%);
  background-size:220% 100%; animation:shimmer 1.3s infinite; }
```

Toast：底部居中深灰胶囊，2.4s 自动消失；「有新内容」pill：顶部下落动画，
单枚不叠加，点击后消失并回顶。

## 6. 左栏（演示台）结构

自上而下：标题（产品名 + `一键演示` 高亮）→ 依据材料一行小字 →
**▶ 主播放钮**（品牌渐变大按钮）+ 暂停/停止 + 倍速 seg → 章节卡网格
（2 列；tag 小字分类，AI 线用渐变字；播完打 ✓）→ **旁白框**（黄底暗框，
min-height 56px，这是字幕位）→ 事件日志（黑底 monospace，10.5px，三色：
`api` 紫蓝 #7E96FF / `agent` 青绿 #00C9A7 / `ops` 黄 #E8CE7A / `ok` 绿；
底部图例）→ 数据依据 foot（虚线分隔，5–6 条口径来源）。

日志时间戳用真实时钟 `HH:MM:SS`，观感即"实时系统"。
