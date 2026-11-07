#!/usr/bin/env bash
# ============================================================================
#  PM AI Kit (pm-ai-kit) — 只读版本检查
#  Author: Noah Zhan (@noah.zhan)  ·  © 原作者保留署名权，见 LICENSE / NOTICE。
#
#  2.1.0 起替代每日自动更新；2.1.1 起以公司配置的版本白名单为准（releases：版本 → 该版本 npm tarball 的
#  sha512，维护者发版后登记）。skill 开场跑一次，输出恰好一行，交给 AI 决定要不要问用户：
#    UPDATE_AVAILABLE <local> <target>   白名单里有比本机新的版本（AI 问一句，用户同意才跑 scripts/update.sh <平台>：
#                                        只下载 tarball、核 sha512、从已校验的本地包安装）
#    UNVERIFIED <local> <remote>         npm 上有新版但公司配置未登记（AI 不提示更新；用户问起才说明「等维护者登记」）
#    UP_TO_DATE <local>                  其余（本机已是白名单最高版本，npm 上也没有更新的 / 查不到 npm）
#    NO_CONFIG <local>                   没有公司配置或配置里没有 releases（静默；配置问询由 company_config.py refresh 负责）
#                                        fail-closed：releases 为空对象，或其中任一条键 / 哈希不合法（get 整段拒绝输出）也是 NO_CONFIG
#    OFFLINE <local>                     本机版本读不出（静默）
#  🔴 本脚本绝不执行 npx、绝不安装任何东西；退出码永远 0。
#  npm 最新版只用于判 UNVERIFIED：缓存 ~/.prd-authoring-kit/.update-check（一行 "<epoch> <remote>"），
#  24h 内不再查 npm；--force 忽略缓存；白名单有新版时根本不查 npm。
#  macOS 没有 timeout 命令，网络等待靠 npm_config_fetch_timeout / fetch_retries 限住（~8s、不重试）。
# ============================================================================
set -u

FORCE=0
[ "${1:-}" = "--force" ] && FORCE=1

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" 2>/dev/null && pwd)"
ROOT="$(dirname "$HERE")"

# 本地版本：安装副本有 VERSION 戳；开发仓没有就读 package.json
LOCAL=""
if [ -f "$ROOT/VERSION" ]; then
  LOCAL="$(head -1 "$ROOT/VERSION" 2>/dev/null | tr -d '[:space:]')"
fi
if [ -z "$LOCAL" ] && [ -f "$ROOT/package.json" ]; then
  LOCAL="$(grep '"version"' "$ROOT/package.json" 2>/dev/null | head -1 | sed -E 's/.*"version": *"([^"]+)".*/\1/')"
fi
[ -n "$LOCAL" ] || LOCAL="unknown"

if [ "$LOCAL" = "unknown" ]; then
  echo "OFFLINE $LOCAL"
  exit 0
fi

# 白名单：公司配置 releases（版本 → sha512）。只认键 x.y.z、值 sha512-… 的条目，sort -V 取最大 → TARGET
APPROVED_JSON="$(python3 "$HERE/company_config.py" get releases 2>/dev/null)" || APPROVED_JSON=""
TARGET=""
if [ -n "$APPROVED_JSON" ]; then
  TARGET="$(printf '%s' "$APPROVED_JSON" | python3 -c 'import json,re,sys;d=json.load(sys.stdin);print("\n".join(k for k,v in d.items() if re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+",k) and isinstance(v,str) and re.fullmatch(r"sha512-[A-Za-z0-9+/]{86}==",v)) if isinstance(d,dict) else "")' 2>/dev/null | sort -V | tail -1)" || TARGET=""
fi
if [ -z "$TARGET" ]; then
  echo "NO_CONFIG $LOCAL"
  exit 0
fi

newer(){ [ "$1" != "$2" ] && [ "$(printf '%s\n%s\n' "$2" "$1" | sort -V | tail -1)" = "$1" ]; }   # $1 比 $2 新？

if newer "$TARGET" "$LOCAL"; then
  echo "UPDATE_AVAILABLE $LOCAL $TARGET"
  exit 0
fi

CACHE_DIR="$HOME/.prd-authoring-kit"
CACHE="$CACHE_DIR/.update-check"
NOW="$(date +%s)"
REMOTE=""

is_ver(){ printf '%s' "$1" | grep -qE '^[0-9]+(\.[0-9]+)+([-+][0-9A-Za-z.-]+)?$'; }

if [ "$FORCE" = 0 ] && [ -f "$CACHE" ]; then
  read -r C_TS C_REMOTE _ < "$CACHE" 2>/dev/null || true
  if [ -n "${C_TS:-}" ] && [ -n "${C_REMOTE:-}" ] && printf '%s' "$C_TS" | grep -qE '^[0-9]+$' \
     && [ $((NOW - C_TS)) -ge 0 ] && [ $((NOW - C_TS)) -lt 86400 ] && is_ver "$C_REMOTE"; then
    REMOTE="$C_REMOTE"
  fi
fi

if [ -z "$REMOTE" ]; then
  REMOTE="$(npm_config_fetch_timeout=8000 npm_config_fetch_retries=0 npm view pm-ai-kit version 2>/dev/null | tail -1 | tr -d '[:space:]')" || REMOTE=""
  if is_ver "$REMOTE"; then
    { mkdir -p "$CACHE_DIR" && printf '%s %s\n' "$NOW" "$REMOTE" > "$CACHE"; } 2>/dev/null || true
  else
    REMOTE=""
  fi
fi

# REMOTE 取不到（离线 / npm 不在）不影响其它判断：按 UP_TO_DATE 静默
if [ -n "$REMOTE" ] && newer "$REMOTE" "$LOCAL"; then
  echo "UNVERIFIED $LOCAL $REMOTE"
else
  echo "UP_TO_DATE $LOCAL"
fi
exit 0
