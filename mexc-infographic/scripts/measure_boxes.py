"""量框：在展开后的静态原型 HTML 里，取指定元素相对帧的百分比坐标。
用法：python3 measure_boxes.py static.html "帧标签文字" "元素文字1" "元素文字2" ...
输出 JSON，可直接喂给方案页的 box() 函数。"""
import asyncio, json, sys
from playwright.async_api import async_playwright

async def main(html, label, texts):
    async with async_playwright() as p:
        b = await p.chromium.launch(headless=True, args=['--no-sandbox'])
        ctx = await b.new_context(viewport={'width': 1600, 'height': 1000}, device_scale_factor=2)
        page = await ctx.new_page()
        await page.goto('file://' + html, wait_until='networkidle'); await page.wait_for_timeout(800)
        fr = page.locator(f"xpath=//div[normalize-space(text())='{label}']/following-sibling::div[1]").first
        fb = await fr.bounding_box()
        def rel(bb): return {'l': (bb['x']-fb['x'])/fb['width']*100, 't': (bb['y']-fb['y'])/fb['height']*100,
                             'w': bb['width']/fb['width']*100, 'h': bb['height']/fb['height']*100}
        out = {}
        for t in texts:
            loc = fr.get_by_text(t, exact=True).first
            if await loc.count():
                out[t] = rel(await loc.bounding_box())
        print(json.dumps(out, ensure_ascii=False, indent=1))
        await b.close()

if __name__ == '__main__':
    asyncio.run(main(sys.argv[1], sys.argv[2], sys.argv[3:]))
