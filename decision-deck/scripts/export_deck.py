#!/usr/bin/env python3
"""
把 decision-deck 的 HTML deck 导出成 PDF（转发用）和每页 PNG（贴飞书、给 Yoki 预审）。

用法：
  python export_deck.py deck.html out_dir            # PDF + 每页 PNG（2 倍）
  python export_deck.py deck.html out_dir --no-pdf   # 只出 PNG
  python export_deck.py deck.html out_dir --no-png   # 只出 PDF

依赖：playwright（python）。沙箱里 Chrome 在 /opt/google/chrome/chrome；本机 Mac 不传 executable_path，
用 playwright 自带的 chromium 即可（CHROME 环境变量可覆盖）。
视频页导出时只能得到首帧，deck 和视频文件一起打包给需要演示的人。
"""
import asyncio, os, sys
from playwright.async_api import async_playwright

W, H = 1920, 1080


async def main(src: str, out_dir: str, want_pdf: bool, want_png: bool):
    src = os.path.abspath(src)
    os.makedirs(out_dir, exist_ok=True)
    stem = os.path.splitext(os.path.basename(src))[0]
    exe = os.environ.get("CHROME") or ("/opt/google/chrome/chrome" if os.path.exists("/opt/google/chrome/chrome") else None)
    async with async_playwright() as p:
        kw = {"headless": True, "args": ["--no-sandbox", "--disable-setuid-sandbox"]}
        if exe:
            kw["executable_path"] = exe
        browser = await p.chromium.launch(**kw)
        ctx = await browser.new_context(viewport={"width": W, "height": H}, device_scale_factor=2)
        page = await ctx.new_page()
        await page.goto("file://" + src, wait_until="networkidle")
        await page.wait_for_timeout(400)
        await page.add_style_tag(content="#help{display:none}")
        n = await page.evaluate("document.querySelectorAll('.slide').length")
        print(f"{n} 页")

        if want_png:
            for i in range(n):
                await page.evaluate(f"goTo({i})")
                await page.wait_for_timeout(150)
                path = os.path.join(out_dir, f"{stem}_p{i+1:02d}.png")
                await page.screenshot(path=path, clip={"x": 0, "y": 0, "width": W, "height": H})
                print(path)

        if want_pdf:
            await page.emulate_media(media="print")
            await page.evaluate("document.getElementById('stage').style.transform='none'")
            pdf = os.path.join(out_dir, f"{stem}.pdf")
            await page.pdf(path=pdf, width=f"{W}px", height=f"{H}px", print_background=True, prefer_css_page_size=True)
            print(pdf)
        await browser.close()


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)
    asyncio.run(main(sys.argv[1], sys.argv[2], "--no-pdf" not in sys.argv, "--no-png" not in sys.argv))
