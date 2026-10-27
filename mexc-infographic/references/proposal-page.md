# 方案页（1920×1080 单屏）完整做法
> 2026-10-27 起：方案页的金色强调改为品牌蓝（Yoki："黄色抹茶蓝嘛，看起来像币安"）。下面代码里的 #F0B90B、var(--gold)
> 一律换成 #2B6AFF；价值大字改白字，编号圆标蓝实底；推荐胶囊、箭头、聚光灯细线都改蓝。完整的配色与高亮规则见 SKILL.md Step 3.5。


两个通过验收的成品在 `examples/`：`proposal-page_广场1.5.html`（入口 → 页面 → 回流）、
`proposal-page_学FOMO.html`（竞品小列 + 生命周期三帧）。新图从它们改，别从零写。

## 1. 版式常量

```
画布      1920 × 1080，padding 左右 80
顶部      tag(15px) / h1(42px, 一句话, <em> 金色) / sub(16px 灰) ；右上三个胶囊 15px
帧        宽 FW=320（三帧）或 330-340（两帧+竞品列），高 FH = FW*844/390，顶 FY=200
三帧 x    80 / 800 / 1520（FW=320）。帧间留 180-200px 给箭头和标签
帧标签    帧上方 36px，18px 粗，前面小胶囊（入口一 / 开仓后 / 二期三期），推荐加金色胶囊
价值清单  帧下 16px 起，每条 = 24px 圆编号 + 18px 黄字 + 14px 灰字，行距 7px
左下      14px 一行：覆盖规则 / 底线
右下      12px 脚注：界面为产品原型截图，非设计定稿；数据为示例
```

## 2. 颜色

```
黄 #F0B90B   框（内容）、编号、跳转箭头、价值大字
绿 #00B87A   框（交易/回流）、绿编号、回流虚线箭头、"所以"胶囊
蓝 #2B6AFF   二期/三期胶囊
灰 #848E9C   说明字、累积类箭头（虚线）
底 #0B0E11 / 卡 #181B22 / 边 rgba(234,236,239,.08)
```

## 3. 关键 CSS（可整段复制）

```css
.slide{width:1920px;height:1080px;position:relative;overflow:hidden}
.fr{position:absolute;width:320px;top:200px}
.fr .im{position:relative;width:320px;height:693px;border-radius:22px;overflow:hidden;border:1px solid var(--bd);background:#000}
.fr .im.c{border:2px solid rgba(0,184,122,.75)}          /* 核心页 */
.fr .im img{display:block;width:100%;height:100%}
.hb{position:absolute;border:3px solid;border-radius:8px;box-shadow:0 0 0 2px rgba(0,0,0,.6)}
.nb{position:absolute;width:28px;height:28px;border-radius:50%;color:#0B0E11;font-size:15px;font-weight:800;
    display:flex;align-items:center;justify-content:center;box-shadow:0 0 0 3px rgba(0,0,0,.7)}
.vals{position:absolute;top:709px;left:-10px;width:380px;display:flex;flex-direction:column;gap:7px}
.v{display:flex;align-items:flex-start;gap:8px;line-height:1.3}
.v .k{width:24px;height:24px;border-radius:50%;background:var(--gold);color:#0B0E11;font-size:13px;font-weight:800;
      display:flex;align-items:center;justify-content:center;flex:none;margin-top:2px}
.v b{font-size:18px;font-weight:800;color:var(--gold)}  .v b.g{color:var(--green)}
.v span{font-size:14px;color:var(--t2)}
svg.ov{position:absolute;left:0;top:0;width:1920px;height:1080px;pointer-events:none}
.alab{position:absolute;font-size:15px;font-weight:800;color:var(--gold);background:rgba(11,14,17,.92);
      padding:4px 10px;border-radius:999px;border:1px solid rgba(240,185,11,.4);white-space:nowrap}
.alab.g{color:var(--green);border-color:rgba(0,184,122,.4)}
```

框和编号写法（百分比相对帧）：

```python
def box(l,t,w,h,color='#F0B90B',num=None,numpos='tl'):
    b=f'<div class="hb" style="left:{l:.2f}%;top:{t:.2f}%;width:{w:.2f}%;height:{h:.2f}%;border-color:{color}">'
    if num:
        pos={'tl':'left:-14px;top:-14px','tr':'right:-14px;top:-14px',
             'bl':'left:-14px;bottom:-14px','br':'right:-14px;bottom:-14px'}[numpos]
        b+=f'<span class="nb" style="{pos};background:{color}">{num}</span>'
    return b+'</div>'
```

编号别压住元素里的文字：框的角落哪边空就放哪边（tl / tr / bl / br 都试过）。

## 4. 原型帧：从 Claude Design 导出的 HTML 里取整帧

Claude Design 的 HTML 引 `./support.js`，用 `<sc-for list="{{ boards }}" as="b">` 和
`<sc-if value="{{ showX }}">` 模板，数据在 `<script type="text/x-dc">` 里。没有 support.js
直接截图会出现 `{{ b.name }}` 和空白 K 线。先展开：

```python
import re
s=open('proto.html',encoding='utf-8').read()
# 1) 从 x-dc 脚本里把列表数据抠出来（对象字面量 → dict），K 线蜡烛按脚本里的伪随机复算
# 2) 展开 sc-if：value 为真的保留 body，否则删
def expand_if(t,ctx):
    def rep(m):
        expr=m.group(1).strip(); body=m.group(2); val=ctx.get(expr)
        if val is None and '.' in expr:
            a,b=expr.split('.',1); val=ctx.get(a,{}).get(b) if isinstance(ctx.get(a),dict) else None
        return body if val else ''
    return re.sub(r'<sc-if value="\{\{\s*([^}]+?)\s*\}\}"[^>]*>(.*?)</sc-if>',rep,t,flags=re.S)
# 3) 展开 sc-for：对每个 item 复制 body，替换 {{ alias.field }}
def expand_for(t,lists):
    def rep(m):
        lname,alias,body=m.group(1),m.group(2),m.group(3); out=[]
        for it in lists[lname]:
            b=expand_if(body,{alias:it})
            b=re.sub(r'\{\{\s*'+alias+r'\.(\w+)\s*\}\}',lambda mm:str(it.get(mm.group(1),'')),b)
            out.append(b)
        return ''.join(out)
    return re.sub(r'<sc-for list="\{\{\s*(\w+)\s*\}\}" as="(\w+)"[^>]*>(.*?)</sc-for>',rep,t,flags=re.S)
# 4) 删掉 <script src="./support.js">，检查 re.findall(r'\{\{[^}]+\}\}',out) 为空
```

被砍掉的模块（投票条、"看多 62%"）在这份静态 HTML 里删，再截图。

一帧一截（帧上方有 14px 白色标签文字）：

```python
fr=page.locator(f"xpath=//div[normalize-space(text())='{label}']/following-sibling::div[1]").first
await fr.screenshot(path='b1.png')      # viewport 1600 宽，deviceScaleFactor 2 → 780×1688
```

手绘补帧（原型没画的页面）：同一套样式写一个 390×844 的 `.frame`，Playwright 截 `.frame`。
黑底 #000、圆角 32、顶栏 56px、44px 圆头像、17px 正文、深灰胶囊、56px 蓝色悬浮钮。

## 5. 量框：框和箭头的坐标都从 DOM 来

```python
fb=await fr.bounding_box()
def rel(bb): return {'l':(bb['x']-fb['x'])/fb['width']*100,'t':(bb['y']-fb['y'])/fb['height']*100,
                     'w':bb['width']/fb['width']*100,'h':bb['height']/fb['height']*100}
tab  = rel(await fr.get_by_text('圈子',exact=True).first.bounding_box())
card = rel(await fr.locator("xpath=.//*[contains(normalize-space(text()),'AI 摘要')]/ancestor::div[2]").first.bounding_box())
btn  = rel(await fr.get_by_text('交易',exact=True).first.bounding_box())
```

- 文字元素外扩 1-2%，卡片元素直接用容器盒子
- 列表区用首行顶到末行底
- `ancestor::div[N]` 的 N 要试：div[1] 常常只是标题行，div[2] 才是卡片
- 量完先渲染一次看框有没有压字，再定编号位置

## 5b. 聚光灯高亮（替代粗框）

每帧的 `.im` 里，img 之后插一个 SVG 遮罩：整帧盖 rgba(0,0,0,.42)，要讲的区域挖洞；
框本身只留 1.5px 细线。老板看到的是"这几块亮着"，不是"图上全是框"。

```python
def frame(img, boxes):   # boxes: [(l,t,w,h,color,num,numpos), ...]  百分比
    holes=''.join(f'<rect x="{l}%" y="{t}%" width="{w}%" height="{h}%" rx="8" fill="black"/>' for (l,t,w,h,*_) in boxes)
    mid='m'+uuid.uuid4().hex[:6]
    dim=f'<svg class="dim"><defs><mask id="{mid}"><rect width="100%" height="100%" fill="white"/>{holes}</mask></defs>'         f'<rect width="100%" height="100%" fill="rgba(0,0,0,.42)" mask="url(#{mid})"/></svg>'
    return f'<div class="im"><img src="{img}">{dim}{"".join(box(*b) for b in boxes)}</div>'
```
```css
.dim{position:absolute;left:0;top:0;width:100%;height:100%;pointer-events:none}
.hb{position:absolute;border:1.5px solid;border-radius:8px;pointer-events:none;opacity:.9}
```
mask 的 id 每帧唯一，否则多帧共用一个 mask 会互相盖掉。

## 5c. 三种页的版式常量

- 决策页（单行）：1800×1080，参考帧 230 宽、方案帧 300 宽、目的页 230 宽，`≈` 和 `→` 用 30-38px 粗体符号，帧下胶囊区固定高度让各列底对齐
- 群投票版：1800×1640，上半"已定"区三帧 190 宽，下半 A/B 各 290 宽配两侧参考 210 宽，优缺点两栏各两条
- 系统页（矩阵）：1920×1080，grid `96px 1fr 1.35fr 1fr`，行标签竖排；表头三色渐变（绿/金/蓝）；AI 行背景 rgba(240,185,11,.05) 边框 .35；帧 118×255；结果卡 32px 大字；闭环箭头是绝对定位的 SVG 虚线，从最后一列表头绕到第一列表头，标签压在线中间

## 6. 箭头

SVG 覆盖层，贝塞尔曲线，端点取元素边缘：

```python
xL=LX+FW*(tab_l+tab_w)/100+4;  yL=FY+FH*(tab_t+tab_h/2)/100        # 起点：入口元素右边缘中点
xC=CX-8;                        yC=FY+FH*0.5                          # 终点：目的帧左边缘中点
f'<path d="M{xL},{yL} C {xL+170},{yL} {xC-170},{yC} {xC},{yC}" stroke="#F0B90B" stroke-width="5" fill="none" marker-end="url(#ah)"/>'
```

- 跳转：黄实线 5px；回流/交易：绿虚线 `stroke-dasharray="14 10"`；累积/后续：灰虚线 4px
- 每条箭头一个胶囊标签 `.alab`，写"点 X → Y"，≤ 10 字，放在曲线中点附近，别压帧
- 两条箭头进同一帧时错开 40px

## 7. 价值清单怎么写

编号 = 帧上的框。每条两行：

```
① 按标的找讨论                      ← 18px 黄字，用户得到什么，≤ 12 字
   「圈子」页签进列表，币和美股一套     ← 14px 灰字，为什么 / 业务得到什么
```

交易/回流那条用绿编号绿字。推荐方案的优势用 ✓ 编号 + 白字一句。
一帧 2-3 条，多了删灰字，不删黄字。

## 8. 渲染

```bash
python3 scripts/render_slide.py page.html page.png    # 1920×1080 视口，2 倍，输出 3840×2160
```

预览用 PIL 缩到 1600 宽看整体，再裁局部看框准不准。每改一次至少看一次局部。
