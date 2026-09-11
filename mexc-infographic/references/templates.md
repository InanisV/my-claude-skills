# 组件模板：直接复用的 CSS 和 HTML

配方里用到的组件，样式已经被接受过，直接抄。全局变量和基础样式用 `design-tokens.md`，这里只放增量。
页面宽 820px，字体栈同 design-tokens。

---

## 1. 各方意见表（一方一行）

```css
table{width:100%;table-layout:fixed;border-collapse:separate;border-spacing:0;background:var(--bg-elevated);border-radius:10px;overflow:hidden}
th{text-align:left;padding:8px 12px;font-size:11px;font-weight:600;color:var(--text-secondary);letter-spacing:1px;border-bottom:1px solid var(--divider)}
td{padding:9px 12px;vertical-align:top;border-bottom:1px solid var(--divider);font-size:12.5px;line-height:1.55}
tr:last-child td{border-bottom:none}
td.who{font-weight:700}      td.who span{display:block;font-size:11px;color:var(--text-tertiary);font-weight:500}
td.pick{font-weight:700}     td.pick span{display:block;font-size:11px;color:var(--text-secondary);font-weight:500}
td.say{color:var(--text-secondary)}  td.say b{color:var(--text-primary);font-weight:600}
```

```html
<table>
  <thead><tr><th style="width:118px">相关方</th><th style="width:150px">倾向</th><th>原话要点</th></tr></thead>
  <tbody>
    <tr><td class="who">品牌<span>负责人名</span></td><td class="pick">A<span>备选 B</span></td><td class="say">原话要点，两层意见两层都写</td></tr>
  </tbody>
</table>
```

`table-layout: fixed` 时列宽必须写在第一行的 `th` 上，写在 `td` 上不生效。

---

## 2. 候选行（一亮点一硬伤，建议项高亮）

```css
.cand{display:grid;grid-template-columns:150px 1fr 1fr;gap:10px;align-items:center;padding:8px 0;border-top:1px solid var(--divider);font-size:12.5px}
.cand:first-child{border-top:none;padding-top:2px}
.cand .nm{font-size:15px;font-weight:800}
.cand .nm span{color:var(--text-tertiary);font-weight:500;font-size:11px;margin-right:3px}
.cand .pro::before{content:'✓ ';color:var(--color-up);font-weight:800}
.cand .con::before{content:'✗ ';color:var(--color-down);font-weight:800}
.cand .con{color:var(--text-secondary)}
.cand.rec{background:var(--color-up-bg);border-radius:10px;padding:8px 10px;margin:4px -10px 0;border-top:none}
.cand.rec .con{color:var(--text-primary)}
```

```html
<div class="cand rec"><div class="nm"><span>前缀</span>A</div><div class="pro">一句亮点</div><div class="con">同品类同名：X</div></div>
<div class="cand"><div class="nm"><span>前缀</span>B</div><div class="pro">一句亮点</div><div class="con">站内同名：Y</div></div>
```

---

## 3. 建议排序（三行）

```css
.rank{display:grid;grid-template-columns:28px 130px 1fr;align-items:center;gap:10px;padding:7px 0;border-top:1px solid var(--divider);font-size:13px}
.rank:nth-of-type(2){border-top:none}
.rank .no{width:22px;height:22px;border-radius:50%;background:var(--color-up-bg);color:var(--color-up);font-weight:800;font-size:12px;display:flex;align-items:center;justify-content:center}
.rank .nm{font-weight:800;font-size:15px}
.rank .why{color:var(--text-secondary)}
```

```html
<div class="rank"><span class="no">1</span><span class="nm">A</span><span class="why">一句决定性理由</span></div>
```

---

## 4. 维度矩阵（主管版，无建议）

```css
th.opt{font-size:17px;font-weight:800;color:var(--text-primary)}
th.opt span{color:var(--text-tertiary);font-weight:500;font-size:12px;margin-right:4px}
th.dim,td.dim{width:104px}
td.dim{font-size:11px;font-weight:700;color:var(--brand-light)}
td.hl{background:rgba(0,184,122,0.10);box-shadow:inset 3px 0 0 var(--color-up)}
td.hl::before{content:"亮点";display:inline-block;font-size:10px;font-weight:700;color:var(--color-up);background:rgba(0,184,122,0.16);border-radius:9999px;padding:0 7px;margin-right:6px;vertical-align:middle}
```

行是维度（词义与认知、区分度、撞名、现状占位），列是候选，每格一句事实，每列最多一个 `hl`。

---

## 5. 首选卡 / KPI 卡

```css
.picks{display:grid;grid-template-columns:repeat(3,1fr);gap:10px}
.pick{background:var(--bg-elevated);border-radius:10px;padding:12px 14px}
.pick .nm{font-size:15px;font-weight:800}
.pick .cnt{font-size:30px;font-weight:800;line-height:1.1;margin:2px 0}
.pick .who{font-size:11.5px;color:var(--text-secondary)}
```

---

## 6. 排行条形

```css
.bar{display:grid;grid-template-columns:78px 1fr 30px;align-items:center;gap:8px;padding:3px 0;font-size:12px}
.bar .nm{font-weight:700}
.bar .tr{height:12px;background:rgba(234,236,239,0.06);border-radius:6px;overflow:hidden}
.bar .fl{height:100%;border-radius:6px;background:var(--brand-primary)}
.bar.top .fl{background:linear-gradient(90deg,#F0B90B,#F8D33A)}
.bar.ours .fl{background:var(--color-up)}
.bar .c{text-align:right;color:var(--text-secondary);font-variant-numeric:tabular-nums}
```

第一名金色，我们的候选绿色，其余蓝色。宽度按第一名 100% 换算。

---

## 7. 主题原声

```css
.theme{border-top:1px solid var(--divider);padding:8px 0}
.theme .k{font-size:12px;font-weight:700;margin-bottom:2px}
.theme .k span{display:inline-block;padding:1px 7px;border-radius:9999px;font-size:10px;font-weight:600;margin-left:6px}
.theme .q{font-size:11.5px;color:var(--text-secondary);font-style:italic}
.theme .q b{color:var(--text-tertiary);font-style:normal;font-weight:500}
```

每个主题两句原声，每句后面跟 `@用户名`，原文语言不翻译。

---

## 8. 黄色 callout（撞名、前提条件）

```css
.callout{margin-top:10px;background:var(--color-warning-bg);border-left:3px solid var(--color-warning);border-radius:8px;padding:9px 12px;font-size:12px;line-height:1.6}
.callout b{color:var(--color-warning)}
```

---

## 9. 环形图（票数加角色）

用 SVG 圆环，`stroke-dasharray` 分段，中心大数字是票数，下面按角色列名字，颜色按角色统一，页脚图例。
分段之间留 2.5 单位间隙。三张并排，每张 140px。

---

## 10. 三帧并排（伴讲图的「几种做法」）

```css
.frames{display:grid;grid-template-columns:repeat(3,1fr);gap:12px}
.tile{border-radius:var(--radius-md);overflow:hidden;border:1px solid var(--border-card);background:#000;position:relative}
.tile img{display:block;width:100%;object-fit:cover;object-position:left top}
.tile.star{border-color:rgba(240,185,11,.7);box-shadow:0 0 0 2px rgba(240,185,11,.35)}
.tile .ph{position:absolute;right:6px;top:6px;font-size:10px;font-weight:800;padding:2px 7px;border-radius:9999px;background:var(--color-warning);color:#0B0E11}
.cap{font-size:12px;color:var(--text-secondary);margin-top:6px;text-align:center}
```

建议的那帧加 `star` 和「先上」标签，图下一行图注。

---

## 11. 节奏胶囊条

```css
.rhythm{display:flex;gap:8px;align-items:center;flex-wrap:wrap}
.rhythm .cap{padding:4px 12px;border-radius:9999px;font-size:12px;font-weight:700;background:var(--bg-elevated);color:var(--text-primary)}
.rhythm .cap.now{background:var(--brand-bg);color:var(--brand-light)}
.rhythm .arrow{color:var(--text-tertiary)}
```

「1.0 已有 · 1.5 下一版 · 2.0 后续」写成一行，不写段落。

---

## 12. 渲染脚本

```python
import asyncio
from playwright.async_api import async_playwright
async def main(src, out):
    async with async_playwright() as p:
        b = await p.chromium.launch(headless=True, executable_path='/opt/google/chrome/chrome', args=['--no-sandbox','--disable-setuid-sandbox'])
        ctx = await b.new_context(viewport={'width':820,'height':600}, device_scale_factor=2)
        pg = await ctx.new_page()
        await pg.goto('file://'+src, wait_until='networkidle')
        await pg.locator('.page').screenshot(path=out)
        await b.close()
```

改 HTML 用脚本替换并 `assert old in s`。每次渲染后 `view` 整图，再裁一段看细节。交付 PNG 二倍图加 HTML。
