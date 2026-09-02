#!/bin/bash
# 竞品App版本晨查：iTunes Lookup API，一次输出五家竞品+MEXC参照的版本/发版日期/更新要点
# 用法: bash competitor_lookup.sh  （无参数；macOS自带工具即可，勿依赖jq）
set -u
APPS="Bitget:1442778704 Bybit:1488296980 Binance:1436799971 OKX:1327268470 Gate:1294998195 MEXC(参照):1605393003"
for pair in $APPS; do
  name="${pair%%:*}"; id="${pair##*:}"
  # Binance 美区不上架，统一走 sg 区（版本跨区一致，8/31 实测）
  curl -s "https://itunes.apple.com/lookup?id=${id}&country=sg" | python3 -c "
import json,sys,datetime
try:
    r=json.load(sys.stdin)['results'][0]
    d=r.get('currentVersionReleaseDate','')[:10]
    days=''
    if d:
        delta=(datetime.date.today()-datetime.date.fromisoformat(d)).days
        days=f'（{delta}天前）'
    notes=(r.get('releaseNotes') or '').replace(chr(10),' ')[:120]
    print(f\"$name | {r.get('version')} | {d}{days} | {notes}\")
except Exception as e:
    print(f'$name | ERR {e}')
"
done
echo "---"
echo "提示：notes为套话（修复问题/性能优化）就如实写「无实质信息」；有实质功能的竞品建议真机走查。"
