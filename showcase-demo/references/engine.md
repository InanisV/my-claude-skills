# Autoplay 引擎（战斗验证版）

以下代码块来自已交付的 MEXC 广场 demo v3，可直接搬进新 demo 改名使用。
每段都标注了"为什么这么写"——多数写法背后是一个踩过的坑。

## 1. 步骤模型

一章 = 一个返回步骤数组的函数。每步四个字段，全部可选：

```js
{
  narr: '旁白 HTML（<b>加粗关键词</b>）',   // 更新左栏字幕
  log:  [['日志文本','api'|'agent'|'ops'|'ok']], // 追加事件日志（可多条）
  tap:  'element-id' 或 ()=>el,             // 虚拟手指移过去并"按"它
  do:   ()=>{ ... },                        // 实际执行的动作（改状态+渲染）
  wait: 2400                                 // 本步之后停留 ms（标准速）
}
```

关键认知：**tap 只负责视觉，动作全部放 do 里**。不要真的 dispatch click——
自动播放路径与手动 onclick 路径分离，避免动作被执行两次。

## 2. 运行器（含暂停不丢步的写法）

```js
const AP = {on:false, paused:false, timer:null, queue:[], idx:0, done:null, chLabel:'旁白', master:false};
function T(ms){ return Math.max(50, Math.round(ms * S.speed)); }  // S.speed: 1 或 0.55

function runSteps(steps, onDone){
  clearTimeout(AP.timer);
  AP.queue = steps; AP.idx = 0; AP.on = true; AP.paused = false; AP.done = onDone || null;
  setPlayUI(true); stepNext();
}
function stepNext(){
  if (!AP.on || AP.paused) return;
  if (AP.idx >= AP.queue.length){
    AP.on = false; hideGhost();
    if (AP.done) AP.done(); else setPlayUI(false);
    return;
  }
  const s = AP.queue[AP.idx];              // ← 先取，不先 ++
  if (s.narr) narr(AP.chLabel, s.narr);
  const go = ()=>{
    // 坑：如果在取步骤时就 idx++，用户在虚拟手指飞行途中按暂停，
    // 恢复后这一步的动作会被跳过。所以 idx 在动作真正执行时才前进：
    if (AP.idx < AP.queue.length && AP.queue[AP.idx] === s) AP.idx++;
    if (s.log) s.log.forEach(l=>log(l[0], l[1]));
    if (s.do) s.do();
    AP.timer = setTimeout(stepNext, T(s.wait||1000));
  };
  if (s.tap){
    const el = typeof s.tap==='function' ? s.tap() : $(s.tap);
    if (el && el.scrollIntoView) try{ el.scrollIntoView({behavior:'smooth', block:'nearest'}); }catch(e){}
    setTimeout(()=>ghostTo(el, go), 120);   // 先滚动到位再落指
  } else go();
}
function togglePause(){
  if (!AP.on) return;
  if (!AP.paused){ AP.paused = true; clearTimeout(AP.timer);
    $('btn-pause').innerHTML = '▶ 继续（空格）';
    narr(AP.chLabel, '<b>已暂停</b> — 讲到位了再按空格继续。'); }
  else { AP.paused = false; $('btn-pause').innerHTML = '⏸ 暂停（空格）'; stepNext(); }
}
function stopPlay(){
  AP.on = false; AP.paused = false; AP.master = false;
  clearTimeout(AP.timer); hideGhost(); setPlayUI(false);
}
document.addEventListener('keydown', e=>{
  if (e.code==='Space' && AP.on){ e.preventDefault(); togglePause(); }
});
```

## 3. 虚拟手指（ghost cursor）

```css
.ghost { position:absolute; z-index:80; width:34px; height:34px; border-radius:50%;
  pointer-events:none; background:rgba(255,255,255,.22);
  border:1.5px solid rgba(255,255,255,.75); box-shadow:0 2px 12px rgba(0,0,0,.5);
  opacity:0; transform:translate(-50%,-50%);
  transition:left .5s cubic-bezier(.3,.9,.4,1), top .5s cubic-bezier(.3,.9,.4,1), opacity .25s; }
.ghost.show { opacity:1; }
.ghost.tapping { animation:tapping .38s ease-out; }
@keyframes tapping { 0%{transform:translate(-50%,-50%) scale(1)}
  35%{transform:translate(-50%,-50%) scale(.62)} 100%{transform:translate(-50%,-50%) scale(1)} }
```

```js
function ghostTo(el, cb){
  const g = $('ghost'), scr = $('screen');       // #ghost 挂在手机 .screen 内
  if (!el){ cb && cb(); return; }
  const r = el.getBoundingClientRect(), sr = scr.getBoundingClientRect();
  g.style.left = (r.left - sr.left + r.width/2) + 'px';
  // 高元素（整张卡片）不指中心，指上部 40px 内，视觉上像在点"这条内容"：
  g.style.top  = (r.top - sr.top + Math.min(r.height/2, 40)) + 'px';
  g.classList.add('show');
  AP.timer = setTimeout(()=>{ g.classList.remove('tapping'); void g.offsetWidth;
    g.classList.add('tapping'); cb && cb(); }, T(560));
}
function hideGhost(){ $('ghost').classList.remove('show'); }
```

滑动/下拉手势 = ghost 定点后平移 + 页面位移动画（例：下拉进入某页）：

```js
function pullToSquare(){
  const g = $('ghost'), home = $('pg-home');
  g.style.left = '187px'; g.style.top = '110px'; g.classList.add('show');
  home.style.transition = 'transform .5s ease';
  setTimeout(()=>{ g.style.top = '320px'; home.style.transform = 'translateY(64px)'; }, T(260));
  setTimeout(()=>{ hideGhost(); home.style.transform=''; home.style.transition='';
    show('feed'); renderFeed(); /* + 相应日志 */ }, T(1150));
}
```

## 4. 打字机（发布器实感的关键）

发布器用 `div` 假光标渲染而不是真 textarea——自动播放不需要真输入，
渲染更可控（cashtag 上色、字数联动、$ 触发联想）：

```js
function typeText(full, done){           // 从头打；遇到 '$' 停下弹币种联想
  let i = 0;
  const iv = setInterval(()=>{
    if (!AP.on || AP.paused){ clearInterval(iv); return; }
    i++; S.composer.text = full.slice(0, i); renderEd();
    if (full[i-1]==='$'){ clearInterval(iv); showCoinSug(); return; }
    if (i>=full.length){ clearInterval(iv); done && done(); }
  }, T(60));
}
function typeAppend(rest){               // 选完联想后续打
  let i = 0; const base = S.composer.text;
  const iv = setInterval(()=>{
    if (!AP.on || AP.paused){ clearInterval(iv); return; }
    i++; S.composer.text = base + rest.slice(0, i); renderEd();
    if (i>=rest.length) clearInterval(iv);
  }, T(60));
}
```

包含打字的那一步，`wait ≥ 字符数 × 60 + 600`，否则下一步会追尾。

## 5. 章节调度与重置纪律

```js
const CHAPTERS  = {ENTRY:chENTRY, A:chA, /* … */ FUT:chFUT};
const CH_LABELS = {ENTRY:'章节① · 入口', /* … */};

function playChapter(sc, then){
  document.querySelectorAll('.preset').forEach(x=>x.classList.toggle('on', x.dataset.sc===sc));
  AP.chLabel = CH_LABELS[sc];
  runSteps(CHAPTERS[sc](), ()=>{
    document.querySelector('.preset[data-sc="'+sc+'"]').classList.add('done');
    if (then) then();
    else { setPlayUI(false); narr(AP.chLabel, '本章播放完毕 ✓'); }
  });
}
function playAll(){
  fullReset(); clearLog();
  AP.master = true;
  const order = ['ENTRY','A','B','C','D','E','F','FUT'];
  let i = 0;
  const next = ()=>{
    if (!AP.master) return;                       // 中途 stop 能真正停下
    if (i >= order.length){ AP.master=false; setPlayUI(false); narr('演示完毕','…总结…'); return; }
    playChapter(order[i++], ()=>{ AP.timer = setTimeout(next, T(900)); });
  };
  next();
}
```

重置的两级纪律（保证任何章节可反复单独播放）：

- `fullReset()`：master 开播前调用——清空点赞/关注/翻译/通知/发布态/反馈卡，
  章节卡去掉 on/done 标记。
- **每章第一步的 `do` 里做本章前置重置**：D 章重置 p1 的翻译态/点赞/我的评论，
  E 章若无已发布帖则自动补前置并在日志注明"（前置：自动完成 ③ 的发帖）"。
  这样单章重放永远幂等。

## 6. 常见坑清单

- 定时器全部收进 `AP.timer` / 被 `AP.on` 守卫，切章前 `clearTimeout`——
  否则旧章的延时步骤会"穿越"到新章。
- 翻译态是全局的：Feed 卡、详情、海报、端外要用同一份 `S.trans` 判定显示
  原文还是译文（端外/海报永远显示原文——未登录没有翻译能力）。
- 章节里的元素 id（`tap:'poll-up'`）必须在该步执行时已渲染——动态页面先
  `renderX()` 再 tap，或用 `tap:()=>$('id')` 惰性取。
- `scrollIntoView({block:'center'})` 用于"把镜头对准"要讲的卡片，是旁白的
  配角机位，别省。
- 空格监听要 `preventDefault`，否则页面同时滚动。

## 7. Playwright 验证脚本模板

```js
// verify.mjs — npm i playwright；chromium 用容器预装 /opt/pw-browsers/chromium
import { chromium } from 'playwright';
import fs from 'fs';
fs.mkdirSync('shots', { recursive: true });
const browser = await chromium.launch({ executablePath: '/opt/pw-browsers/chromium' })
  .catch(() => chromium.launch());
const page = await browser.newPage({ viewport: { width: 1460, height: 920 } });
const errors = [];
page.on('console', m => { if (m.type()==='error') errors.push('CONSOLE: '+m.text()); });
page.on('pageerror', e => errors.push('PAGEERROR: '+e.message));
await page.goto('file:///ABS/PATH/demo.html');
await page.waitForTimeout(500);
await page.click('#seg-speed button[data-v="0.55"]');   // 加速档
await page.click('#btn-master');
for (let i = 1; i <= 30; i++) {                          // 每 5s 截一张直到终章
  await page.waitForTimeout(5000);
  await page.screenshot({ path: `shots/f${String(i).padStart(2,'0')}.png` });
  const done = await page.evaluate(() =>
    document.querySelector('#narr').textContent.includes('终章旁白独有词'));
  if (done) { console.log('MASTER DONE ~' + i*5 + 's'); break; }
}
console.log('ERRORS(' + errors.length + '):'); errors.forEach(e=>console.log(' ', e));
await browser.close();
```

跑完之后：把关键帧裁出手机区域拼成大图，**用 Read 看图核对设计还原度**——
零报错只说明代码活着，不说明界面对。弹层/空态等采样截不到的状态，用
`page.evaluate(()=>{ /* 直接构造状态 */ })` 定向截图。
