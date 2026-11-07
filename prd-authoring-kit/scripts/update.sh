#!/usr/bin/env bash
# ============================================================================
#  PM AI Kit (pm-ai-kit) — 校验后安装（2.1.1 起唯一的更新路径）
#  Author: Noah Zhan (@noah.zhan)  ·  © 原作者保留署名权，见 LICENSE / NOTICE。
#
#  用法：bash scripts/update.sh <claude|codex|gemini|kiro|antigravity> [版本] [--allow-downgrade]（不支持 all：会在当前目录生成 Kiro 副本）
#  1b. 目标版本低于本机 → DOWNGRADE_REFUSED <本机> <目标>，退出 2（显式 --allow-downgrade 才放行）
#
#  威胁模型：只走 `npx -y pm-ai-kit@latest` 的话，谁拿到 npm 发布权谁就能让点头更新的同事执行任意代码。
#  所以版本要先在公司配置文档（飞书，只有维护者能编辑）的 releases 里登记「版本 → npm tarball 的 sha512」，
#  本脚本只装登记过且哈希一致的版本——攻击者得同时拿下 npm 账号和维护者的飞书账号。
#    1. 读配置 releases；版本缺省 = 白名单里最大版本；给了版本但没登记 → NOT_APPROVED <版本>，退出 2
#    2. npm pack 只下载 tarball 到临时目录（不执行任何包内代码）→ 失败 DOWNLOAD_FAILED，退出 2
#    3. 算 sha512 与白名单比对 → 不一致 HASH_MISMATCH <版本>，删除下载，退出 3
#    4. 一致 → 解包，跑包内 install.sh <平台>（位置无关；kiro 按当前目录装，所以本脚本不 cd）
#       成功 UPDATED <版本>，退出 0；install 失败透传其退出码
#  🔴 全程不调用 npx。没有公司配置 → NO_CONFIG，退出 2（先导入公司配置）。
# ============================================================================
set -u

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" 2>/dev/null && pwd)"
PKG="pm-ai-kit"
PLATFORM="${1:-}"
WANT="${2:-}"

case "$PLATFORM" in
  claude|codex|gemini|kiro|antigravity) ;;
  all) echo "用法: 请按平台逐个更新（all 会在当前目录生成 Kiro 工作区副本）：bash scripts/update.sh <claude|codex|gemini|kiro|antigravity> [版本]" >&2; exit 2 ;;
  *) echo "用法: bash scripts/update.sh <claude|codex|gemini|kiro|antigravity> [版本] [--allow-downgrade]" >&2; exit 2 ;;
esac
ALLOW_DOWNGRADE=0; [ "${3:-}" = "--allow-downgrade" ] && ALLOW_DOWNGRADE=1
# 本机版本（安装副本 VERSION / 开发仓 package.json），用于拒绝降级
ROOT="$(dirname "$HERE")"; LOCAL=""
[ -f "$ROOT/VERSION" ] && LOCAL="$(head -1 "$ROOT/VERSION" 2>/dev/null | tr -d '[:space:]')"
[ -z "$LOCAL" ] && [ -f "$ROOT/package.json" ] && LOCAL="$(grep '"version"' "$ROOT/package.json" 2>/dev/null | head -1 | sed -E 's/.*"version": *"([^"]+)".*/\1/')"
command -v python3 >/dev/null 2>&1 || { echo "需要 python3（macOS 自带）。" >&2; exit 2; }

# 1. 白名单：只认键 x.y.z、值 sha512-<86 位 base64>== 的条目，每行 "<版本> <哈希>"
APPROVED_JSON="$(python3 "$HERE/company_config.py" get releases 2>/dev/null)" || APPROVED_JSON=""
LIST=""
if [ -n "$APPROVED_JSON" ]; then
  LIST="$(printf '%s' "$APPROVED_JSON" | python3 -c 'import json,re,sys;d=json.load(sys.stdin);print("\n".join(k+" "+v for k,v in d.items() if re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+",k) and isinstance(v,str) and re.fullmatch(r"sha512-[A-Za-z0-9+/]{86}==",v)) if isinstance(d,dict) else "")' 2>/dev/null)" || LIST=""
fi
if [ -z "$LIST" ]; then
  echo "NO_CONFIG"
  echo "没有公司配置，或配置里没有登记任何版本（releases）。先导入公司配置：python3 $HERE/company_config.py import <飞书配置文档链接> --yes" >&2
  exit 2
fi

if [ -z "$WANT" ]; then
  VER="$(printf '%s\n' "$LIST" | awk '{print $1}' | sort -V | tail -1)"
else
  VER="$WANT"
fi
EXPECTED="$(printf '%s\n' "$LIST" | awk -v v="$VER" '$1 == v {print $2; exit}')"
if [ -z "$VER" ] || [ -z "$EXPECTED" ]; then
  echo "NOT_APPROVED $VER"
  echo "版本 $VER 不在公司配置的白名单里（未登记哈希），不安装。已登记：$(printf '%s\n' "$LIST" | awk '{print $1}' | sort -V | tr '\n' ' ')" >&2
  exit 2
fi

# 1b. 拒绝降级（登记过的老版本可能没有本脚本 / 没有安全修复），显式 --allow-downgrade 才放行
if [ -n "$LOCAL" ] && [ "$VER" != "$LOCAL" ] && [ "$(printf '%s\n%s\n' "$LOCAL" "$VER" | sort -V | tail -1)" = "$LOCAL" ] && [ "$ALLOW_DOWNGRADE" = 0 ]; then
  echo "DOWNGRADE_REFUSED $LOCAL $VER"
  echo "目标版本 $VER 低于本机 $LOCAL，不降级；确实要降请加第三个参数 --allow-downgrade。" >&2
  exit 2
fi

# 2. 只下载 tarball（npm pack 对 registry 包不跑任何生命周期脚本；--ignore-scripts 再加一道）
TMP="$(mktemp -d 2>/dev/null)" || { echo "DOWNLOAD_FAILED"; echo "建不了临时目录。" >&2; exit 2; }
[ -n "$TMP" ] && [ -d "$TMP" ] || { echo "DOWNLOAD_FAILED"; echo "建不了临时目录。" >&2; exit 2; }
trap 'rm -rf "$TMP"' EXIT
TGZ="$TMP/$PKG-$VER.tgz"
if ! ( cd "$TMP" && npm_config_fetch_timeout=30000 npm_config_fetch_retries=1 npm pack "$PKG@$VER" --pack-destination "$TMP" --ignore-scripts --silent >/dev/null 2>"$TMP/npm.err" ) \
   || [ ! -f "$TGZ" ]; then
  echo "DOWNLOAD_FAILED"
  echo "下载 $PKG@$VER 失败（离线 / npm 不在 / registry 不可达）：$(head -1 "$TMP/npm.err" 2>/dev/null)" >&2
  exit 2
fi

# 3. 核哈希
ACTUAL="$(python3 -c 'import hashlib,base64,sys;print("sha512-"+base64.b64encode(hashlib.sha512(open(sys.argv[1],"rb").read()).digest()).decode())' "$TGZ" 2>/dev/null)" || ACTUAL=""
if [ -z "$ACTUAL" ] || [ "$ACTUAL" != "$EXPECTED" ]; then
  rm -rf "$TMP"
  echo "HASH_MISMATCH $VER"
  echo "🔴 下载到的包与公司配置登记的哈希不一致，可能被替换，已终止并删除下载；请立刻告诉维护者。" >&2
  echo "   （版本 $VER；没有安装任何东西。不要改用 npx 重试。）" >&2
  exit 3
fi

# 4. 从已校验的本地包安装（不 cd：kiro 按调用者当前目录装）
if ! tar xzf "$TGZ" -C "$TMP" 2>/dev/null || [ ! -f "$TMP/package/install.sh" ]; then
  echo "DOWNLOAD_FAILED"
  echo "解包失败或包内缺 install.sh。" >&2
  exit 2
fi
bash "$TMP/package/install.sh" "$PLATFORM"
RC=$?
if [ "$RC" -ne 0 ]; then
  echo "install.sh 失败（exit $RC），未完成更新。" >&2
  exit "$RC"
fi
echo "UPDATED $VER"
exit 0
