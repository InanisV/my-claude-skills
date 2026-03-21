#!/usr/bin/env node

/**
 * Binance Lead Trader Scraper
 *
 * Fetches position data, performance history, and trader info
 * from Binance copy trading / futures leaderboard.
 *
 * Since Binance blocks direct API calls from non-browser contexts,
 * this script supports two modes:
 *
 * 1. Cookie mode: Pass cookies from a logged-in Binance session
 * 2. CDP intercept mode: Intercept API responses from Chrome via cdp.mjs
 *
 * Usage:
 *   node scrape_trader.mjs <command> <encryptedUid> [options]
 *
 * Commands:
 *   positions       - Current open positions
 *   performance     - ROI/PnL performance data
 *   info            - Basic trader info (name, followers, etc.)
 *   all             - Fetch everything and combine
 *
 * Options:
 *   --cookies "<str>"   - Full cookie string from Binance browser session
 *   --csrftoken "<str>" - CSRF token from Binance cookies
 *   --output <path>     - Write output to JSON file
 *   --trade-type <type> - PERPETUAL (default) or DELIVERY
 */

import * as fs from 'node:fs';

// ─── Config ───────────────────────────────────────────────────────────────────

const BASE_URL = 'https://www.binance.com';

// Binance frequently changes these paths. If one fails, update based on
// Network tab observation from Chrome DevTools on a live Binance page.
const ENDPOINTS = {
  // Leaderboard endpoints
  info: '/bapi/futures/v1/public/future/leaderboard/getOtherLeaderboardBaseInfo',
  performance: '/bapi/futures/v1/public/future/leaderboard/getOtherPerformance',
  positions_v1: '/bapi/futures/v1/public/future/leaderboard/getOtherPosition',
  positions_v2: '/bapi/futures/v2/private/future/leaderboard/getOtherPosition',
  // Copy trading endpoints
  ct_detail: '/bapi/copy-trading/v1/public/future/copy-trade/lead-portfolio/detail',
  ct_positions: '/bapi/copy-trading/v1/public/future/copy-trade/lead-portfolio/positions',
  ct_performance: '/bapi/copy-trading/v1/public/future/copy-trade/lead-portfolio/performance',
};

function buildHeaders(cookies, csrftoken) {
  const headers = {
    'Accept': '*/*',
    'Accept-Language': 'en-US,en;q=0.9,zh-CN;q=0.8,zh;q=0.7',
    'Content-Type': 'application/json',
    'Origin': 'https://www.binance.com',
    'Referer': 'https://www.binance.com/',
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
    'clienttype': 'web',
    'lang': 'en',
    'fvideo-id': '',
    'bnc-uuid': '',
  };
  if (cookies) headers['Cookie'] = cookies;
  if (csrftoken) headers['csrftoken'] = csrftoken;
  return headers;
}

// ─── Helpers ──────────────────────────────────────────────────────────────────

function parseArgs(argv) {
  const args = argv.slice(2);
  const result = {
    command: args[0],
    encryptedUid: args[1],
    cookies: '',
    csrftoken: '',
    output: '',
    tradeType: 'PERPETUAL',
  };

  for (let i = 2; i < args.length; i++) {
    switch (args[i]) {
      case '--cookies':   result.cookies = args[++i] || ''; break;
      case '--csrftoken': result.csrftoken = args[++i] || ''; break;
      case '--output':    result.output = args[++i] || ''; break;
      case '--trade-type': result.tradeType = args[++i] || 'PERPETUAL'; break;
    }
  }

  // Try to extract csrftoken from cookies if not provided separately
  if (!result.csrftoken && result.cookies) {
    const m = result.cookies.match(/csrftoken=([^;]+)/);
    if (m) result.csrftoken = m[1];
  }

  return result;
}

async function apiCall(endpoint, body, cookies, csrftoken) {
  const url = `${BASE_URL}${endpoint}`;
  const headers = buildHeaders(cookies, csrftoken);

  try {
    const resp = await fetch(url, {
      method: 'POST',
      headers,
      body: JSON.stringify(body),
    });

    const text = await resp.text();

    if (!resp.ok) {
      // Check if it's HTML (WAF block) vs JSON error
      if (text.startsWith('<')) {
        return { _error: true, status: resp.status, message: `Blocked by WAF (${resp.status}). Need valid cookies.` };
      }
      try {
        return { _error: true, status: resp.status, ...JSON.parse(text) };
      } catch {
        return { _error: true, status: resp.status, message: text.slice(0, 200) };
      }
    }

    return JSON.parse(text);
  } catch (err) {
    return { _error: true, message: err.message };
  }
}

async function tryEndpoints(endpoints, body, cookies, csrftoken) {
  for (const ep of endpoints) {
    const result = await apiCall(ep, body, cookies, csrftoken);
    if (!result._error && (result.data !== undefined || result.success)) {
      return { endpoint: ep, result };
    }
    console.error(`  [${result.status || 'ERR'}] ${ep}: ${result.message || JSON.stringify(result).slice(0, 100)}`);
  }
  return null;
}

// ─── Commands ─────────────────────────────────────────────────────────────────

async function fetchInfo(uid, cookies, csrftoken) {
  console.error(`[*] Fetching trader info for ${uid}...`);
  const r = await tryEndpoints(
    [ENDPOINTS.info, ENDPOINTS.ct_detail],
    { encryptedUid: uid, portfolioId: uid },
    cookies, csrftoken
  );

  if (r?.result?.data) {
    const d = r.result.data;
    console.error(`[OK] Got info from ${r.endpoint}`);
    return {
      nickName: d.nickName,
      encryptedUid: d.encryptedUid || uid,
      followerCount: d.followerCount,
      twitterUrl: d.twitterUrl || null,
      positionShared: d.positionShared,
      pnl: d.pnl,
      roi: d.roi,
      rank: d.rank,
      marginBalance: d.marginBalance,
      copierCount: d.copierCount,
    };
  }

  console.error(`[FAIL] Could not fetch trader info.`);
  return null;
}

async function fetchPerformance(uid, cookies, csrftoken, tradeType) {
  console.error(`[*] Fetching performance for ${uid}...`);
  const r = await tryEndpoints(
    [ENDPOINTS.performance, ENDPOINTS.ct_performance],
    { encryptedUid: uid, tradeType, portfolioId: uid },
    cookies, csrftoken
  );

  if (r?.result?.data) {
    console.error(`[OK] Got performance from ${r.endpoint}`);
    return r.result.data;
  }

  console.error(`[FAIL] Could not fetch performance data.`);
  return null;
}

async function fetchPositions(uid, cookies, csrftoken, tradeType) {
  console.error(`[*] Fetching positions for ${uid}...`);
  const r = await tryEndpoints(
    [ENDPOINTS.positions_v1, ENDPOINTS.positions_v2, ENDPOINTS.ct_positions],
    { encryptedUid: uid, tradeType, portfolioId: uid },
    cookies, csrftoken
  );

  if (r?.result?.data) {
    const raw = r.result.data.otherPositionRetList || r.result.data;
    console.error(`[OK] Got ${Array.isArray(raw) ? raw.length : '?'} positions from ${r.endpoint}`);

    if (Array.isArray(raw)) {
      return raw.map(p => ({
        symbol: p.symbol,
        entryPrice: p.entryPrice,
        markPrice: p.markPrice,
        pnl: p.pnl,
        roe: p.roe,
        amount: p.amount,
        leverage: p.leverage,
        direction: parseFloat(p.amount) > 0 ? 'LONG' : 'SHORT',
        updateTimeStamp: p.updateTimeStamp,
      }));
    }
    return raw;
  }

  console.error(`[FAIL] Could not fetch positions. Endpoints may require cookies or have changed.`);
  return null;
}

async function fetchAll(uid, cookies, csrftoken, tradeType) {
  const [info, performance, positions] = await Promise.all([
    fetchInfo(uid, cookies, csrftoken),
    fetchPerformance(uid, cookies, csrftoken, tradeType),
    fetchPositions(uid, cookies, csrftoken, tradeType),
  ]);

  return {
    timestamp: new Date().toISOString(),
    encryptedUid: uid,
    traderInfo: info,
    performance,
    positions,
  };
}

// ─── Main ─────────────────────────────────────────────────────────────────────

const args = parseArgs(process.argv);

if (!args.command || !args.encryptedUid) {
  console.log(`
Binance Lead Trader Scraper

Usage:
  node scrape_trader.mjs <command> <encryptedUid> [options]

Commands:
  info             Trader base info (name, followers)
  performance      ROI and PnL data
  positions        Current open positions
  all              All data combined

Options:
  --cookies "<str>"      Binance session cookies (from browser)
  --csrftoken "<str>"    CSRF token
  --output <path>        Write JSON to file
  --trade-type <type>    PERPETUAL (default) or DELIVERY

Examples:
  node scrape_trader.mjs all ABCXYZ123 --cookies "csrftoken=xxx; p20t=xxx"
  node scrape_trader.mjs positions ABCXYZ123 --output positions.json

Note: Binance blocks direct API calls without browser cookies.
      Use chrome-cdp skill to extract cookies from an open Binance tab:
        node cdp.mjs eval <tabId> "document.cookie"
  `);
  process.exit(1);
}

let result;

switch (args.command) {
  case 'info':
    result = await fetchInfo(args.encryptedUid, args.cookies, args.csrftoken);
    break;
  case 'performance':
    result = await fetchPerformance(args.encryptedUid, args.cookies, args.csrftoken, args.tradeType);
    break;
  case 'positions':
    result = await fetchPositions(args.encryptedUid, args.cookies, args.csrftoken, args.tradeType);
    break;
  case 'all':
    result = await fetchAll(args.encryptedUid, args.cookies, args.csrftoken, args.tradeType);
    break;
  default:
    console.error(`Unknown command: ${args.command}`);
    process.exit(1);
}

const output = JSON.stringify(result, null, 2);

if (args.output) {
  fs.writeFileSync(args.output, output, 'utf-8');
  console.error(`[OK] Written to ${args.output}`);
}

// Always output to stdout
console.log(output);
