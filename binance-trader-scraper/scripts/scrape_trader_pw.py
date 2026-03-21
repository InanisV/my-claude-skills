#!/usr/bin/env python3
"""
Binance Lead Trader Scraper (Playwright version)

Uses a headless browser to bypass Binance WAF and intercept API responses.

Usage:
  python3 scrape_trader_pw.py <portfolioId> [--output path.json] [--time-range 7D|30D|90D]

Example:
  python3 scrape_trader_pw.py 4754358958843953153
  python3 scrape_trader_pw.py 4754358958843953153 --output trader.json --time-range 30D
"""

import asyncio
import json
import sys
import os

async def main():
    # Parse args
    args = sys.argv[1:]
    if not args or args[0] in ('-h', '--help'):
        print(__doc__)
        sys.exit(0)

    portfolio_id = args[0]
    output_path = None
    time_range = "7D"

    i = 1
    while i < len(args):
        if args[i] == "--output" and i + 1 < len(args):
            output_path = args[i + 1]
            i += 2
        elif args[i] == "--time-range" and i + 1 < len(args):
            time_range = args[i + 1]
            i += 2
        else:
            i += 1

    url = f"https://www.binance.com/en/copy-trading/lead-details/{portfolio_id}?timeRange={time_range}"

    try:
        from playwright.async_api import async_playwright
    except ImportError:
        print("[ERROR] Playwright not installed. Run: pip install playwright --break-system-packages && playwright install chromium", file=sys.stderr)
        sys.exit(1)

    captured = {}

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
            viewport={"width": 1920, "height": 1080},
            locale="en-US",
        )
        page = await context.new_page()

        # Intercept all bapi responses
        async def on_response(response):
            u = response.url
            keywords = ["portfolio", "leaderboard", "copy-trade", "position",
                       "performance", "detail", "lead-data", "chart-data"]
            if any(kw in u for kw in keywords) and ("bapi" in u or "gateway" in u):
                try:
                    body = await response.json()
                    ep = u.split("binance.com")[-1].split("?")[0]
                    captured[ep] = body
                    print(f"  [CAPTURED] {response.status} {ep}", file=sys.stderr)
                except Exception:
                    pass

        page.on("response", on_response)

        print(f"[*] Loading {url}", file=sys.stderr)
        try:
            await page.goto(url, wait_until="networkidle", timeout=30000)
        except Exception as e:
            print(f"[WARN] {e}", file=sys.stderr)

        # Scroll to trigger lazy loading
        await asyncio.sleep(2)
        await page.evaluate("window.scrollTo(0, document.body.scrollHeight / 2)")
        await asyncio.sleep(1)
        await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        await asyncio.sleep(2)

        # Extract page text as fallback
        page_text = await page.evaluate("document.body?.innerText?.slice(0, 8000) || ''")

        await browser.close()

    # Build structured output
    result = {
        "portfolioId": portfolio_id,
        "timeRange": time_range,
        "timestamp": __import__('datetime').datetime.utcnow().isoformat() + "Z",
        "apiResponses": captured,
        "pageTextFallback": page_text if not captured else None,
    }

    # Extract key data
    for ep, resp in captured.items():
        if "detail" in ep and resp.get("data"):
            d = resp["data"]
            result["traderInfo"] = {
                "nickname": d.get("nickname"),
                "status": d.get("status"),
                "marginBalance": d.get("marginBalance"),
                "aumAmount": d.get("aumAmount"),
                "currentCopyCount": d.get("currentCopyCount"),
                "maxCopyCount": d.get("maxCopyCount"),
                "totalCopyCount": d.get("totalCopyCount"),
                "profitSharingRate": d.get("profitSharingRate"),
                "copierPnl": d.get("copierPnl"),
                "sharpRatio": d.get("sharpRatio"),
                "badgeName": d.get("badgeName"),
                "description": d.get("description"),
            }

        if "positions" in ep and resp.get("data"):
            positions = resp["data"]
            if isinstance(positions, list):
                active = [p for p in positions if float(p.get("positionAmount", 0)) != 0]
                result["activePositions"] = active

        if "chart-data" in ep and resp.get("data"):
            result["roiChart"] = resp["data"]

        if "performance/coin" in ep and resp.get("data"):
            result["tradingCoins"] = resp["data"]

    output = json.dumps(result, indent=2, ensure_ascii=False)

    if output_path:
        with open(output_path, "w") as f:
            f.write(output)
        print(f"[OK] Saved to {output_path}", file=sys.stderr)

    print(output)
    print(f"\n[OK] Captured {len(captured)} API endpoints", file=sys.stderr)

asyncio.run(main())
