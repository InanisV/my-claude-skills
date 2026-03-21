---
name: binance-trader-scraper
description: >
  Scrape Binance copy trading lead trader (带单员) detail pages for position data,
  performance history, and trade records. Works via Playwright headless browser to
  bypass Binance WAF. Use when the user mentions "Binance", "带单员", "copy trading",
  "leaderboard", "trader positions", or wants to extract data from a Binance trader
  profile page.
---

# Binance Lead Trader Scraper

Scrape position data, performance, and trade records from Binance copy trading lead trader (带单员) detail pages.

## Overview

Binance blocks direct server-side API calls with WAF. This skill uses **Playwright** (headless Chromium) to load the page like a real browser and intercept all API responses, which is the most reliable method.

## Prerequisites

Install once (in the VM):
```bash
pip install playwright --break-system-packages
playwright install chromium
```

## Primary Workflow: Playwright Scraper (Recommended)

### Quick Usage

```bash
# Basic: scrape a trader by portfolioId (from their URL)
python3 SKILL_DIR/scripts/scrape_trader_pw.py <portfolioId>

# With output file and time range
python3 SKILL_DIR/scripts/scrape_trader_pw.py <portfolioId> --output result.json --time-range 30D
```

The `portfolioId` is the number in the URL:
```
https://www.binance.com/en/copy-trading/lead-details/4754358958843953153
                                                      ^^^^^^^^^^^^^^^^^
                                                      this is the portfolioId
```

### What it captures

The Playwright script loads the full page and intercepts these Binance internal API responses:

| Data | Endpoint |
|------|----------|
| Trader info (name, AUM, followers, etc.) | `/bapi/futures/v1/friendly/future/copy-trade/lead-portfolio/detail` |
| Current positions | `/bapi/futures/v1/friendly/future/copy-trade/lead-data/positions` |
| ROI chart data | `/bapi/futures/v1/public/future/copy-trade/lead-portfolio/chart-data` |
| Trading coin distribution | `/bapi/futures/v1/public/future/copy-trade/lead-portfolio/performance/coin` |

### Output

Structured JSON with:
- `traderInfo` — nickname, status, margin balance, AUM, copy count, profit sharing rate, sharpe ratio, badge
- `activePositions` — symbol, direction, leverage, entry price, mark price, unrealized PnL
- `roiChart` — daily ROI values for the selected time range
- `tradingCoins` — asset distribution by volume

## Alternative: Node.js API Script (requires cookies)

If Playwright is not available, use the Node.js script with browser cookies:

```bash
node SKILL_DIR/scripts/scrape_trader.mjs all <encryptedUid> --cookies "<cookie_string>"
```

This requires extracting cookies from a logged-in Binance browser session.

## Alternative: Chrome CDP (for live page scraping)

If the user has the page open in Chrome with remote debugging:

```bash
# Connect and extract data from open page
node CDP_SKILL_DIR/scripts/cdp.mjs eval <targetId> "document.body.innerText"
```

## Troubleshooting

- **Playwright not installed**: Run `pip install playwright --break-system-packages && playwright install chromium`
- **Empty positions**: Trader may not be sharing positions, or has no open positions currently
- **Page loads but no API data captured**: Binance may have changed page structure. Try increasing wait time or check if page redirects
- **Endpoint paths changed**: Binance frequently updates internal API paths. The Playwright approach handles this automatically by intercepting whatever endpoints the page actually calls
