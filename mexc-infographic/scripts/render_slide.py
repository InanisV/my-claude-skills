import asyncio, sys
from playwright.async_api import async_playwright
async def main(src,dst):
    async with async_playwright() as p:
        b=await p.chromium.launch(headless=True,args=['--no-sandbox'])
        ctx=await b.new_context(viewport={'width':1920,'height':1080},device_scale_factor=2)
        page=await ctx.new_page(); await page.goto('file://'+src,wait_until='networkidle'); await page.wait_for_timeout(500)
        await page.screenshot(path=dst,clip={'x':0,'y':0,'width':1920,'height':1080}); print(dst)
        await b.close()
asyncio.run(main(sys.argv[1],sys.argv[2]))
