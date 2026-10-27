#!/usr/bin/env python3
"""出图前的版式自检：溢出、图标居中、副标题是否撑出卡片。
用法: python3 check_layout.py page.html [--containers ".ce,.card"] [--icons ".qc,.wn,.hi"]
退出码 0 = 干净，1 = 有问题（问题逐条打印）。
2026-10-27 加：图标跑到圆圈左上角这个坑在同一天踩了两次，原因都是写了一条 `.xx span{display:block}`
之类的宽规则，把放图标的 span 也压成了 block。量一下比肉眼看可靠。"""
import asyncio, sys, argparse
from playwright.async_api import async_playwright

ap=argparse.ArgumentParser()
ap.add_argument('html'); ap.add_argument('--containers',default='.ce,.card,.lane,.mc,.ph,.rw,.act,.base')
ap.add_argument('--icons',default='.qc,.wn,.hi,.wi,.ii,.li,.cn,.ai')
ap.add_argument('--chrome',default='/opt/google/chrome/chrome')
a=ap.parse_args()

JS='''(args)=>{const out=[];
 for(const c of document.querySelectorAll(args.containers)){const r=c.getBoundingClientRect(); if(!r.width) continue;
  for(const e of c.querySelectorAll('*')){const q=e.getBoundingClientRect(); if(!q.width) continue;
   if(q.right>r.right+1||q.bottom>r.bottom+1||q.left<r.left-1) out.push('溢出 '+(c.id||c.className)+' > '+(e.className||e.tagName)+' '+(e.textContent||'').trim().slice(0,12)+' ('+Math.round(q.right-r.right)+','+Math.round(q.bottom-r.bottom)+')');}}
 for(const c of document.querySelectorAll(args.icons)){const s=c.querySelector('svg'); if(!s) continue; const a=c.getBoundingClientRect(), i=s.getBoundingClientRect();
  const dx=Math.round((i.left+i.width/2)-(a.left+a.width/2)), dy=Math.round((i.top+i.height/2)-(a.top+a.height/2));
  if(Math.abs(dx)>1||Math.abs(dy)>1) out.push('图标没居中 '+c.className+' 偏 ('+dx+','+dy+')');}
 for(const e of document.querySelectorAll('*')){if(e.children.length) continue; const cs=getComputedStyle(e); if(cs.whiteSpace!=='nowrap') continue; if(e.scrollWidth>e.clientWidth+1) out.push('文字被裁 '+(e.className||e.tagName)+' '+(e.textContent||'').trim().slice(0,14)+' +'+(e.scrollWidth-e.clientWidth)+'px');}
 return out;}'''

async def main():
    async with async_playwright() as p:
        b=await p.chromium.launch(headless=True,executable_path=a.chrome,args=['--no-sandbox'])
        pg=await b.new_page(viewport={'width':1920,'height':1080})
        await pg.goto('file://'+a.html if not a.html.startswith('file://') else a.html)
        await pg.evaluate('document.fonts.ready'); await pg.wait_for_timeout(400)
        issues=await pg.evaluate(JS,{'containers':a.containers,'icons':a.icons})
        await b.close()
    print('\n'.join(issues) if issues else '版式检查：干净')
    sys.exit(1 if issues else 0)
asyncio.run(main())
