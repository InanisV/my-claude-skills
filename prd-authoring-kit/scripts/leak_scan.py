#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# PRD Authoring Kit · © Noah Zhan (@noah.zhan) · 二次分发/衍生须保留署名，不得标榜为自己原创创作。LICENSE / NOTICE 见根目录。
"""发版闸：扫公开包内容里的公司内部标识符（pm-ai-kit 2.1.0 起，prd-kit-release 流程调用）。

扫描范围 = 根 package.json 的 `files` 列表（目录递归 + 单文件），外加 npm 必带的 package.json；
只扫文本文件（md/json/py/sh/js/txt/html/csv/yaml/yml，及无扩展名的 UTF-8 文本如 LICENSE/NOTICE），
跳过二进制。

规则（命中打印 `路径:行号:规则名:命中片段`）：
  internal_host        公司内网域名 / Jira 域名 / 飞书租户子域（只存 SHA-256，不在公开包里写明文——扫描器自己不能泄露它要拦的东西）
  lark_url_token       larksuite.com/<base|sheets|docx|docs|wiki|share/base/form|file>/<token>
  lark_prefixed_token  shr / shtcn / doxcn / wikcn / bascn / tbl / vew / blk / fld … 前缀的飞书 token
  lark_base_token      27 位、同时含大小写字母与数字的 app_token
  wiki_space_id        19 位 7 开头的 snowflake
  sheet_id             `--sheet-id ` / `sheet_id=` / `sheet_id:` / `"sheet_id": "` 后紧跟的 6 位 [a-z0-9]
                       （`--sheet-id string` 这类 --help 原文的参数类型词不算）

内联豁免：行内含 `leak-scan: allow` 的行跳过（预期为零处）。
退出码：有命中 → 1，末行 `LEAK_SCAN: N hits`；无命中 → 0，末行 `LEAK_SCAN: clean`。`--json` 输出结构化结果。
零依赖（仅标准库）。
"""

import argparse
import hashlib
import json
import os
import re
import sys

TEXT_EXT = {".md", ".json", ".py", ".sh", ".js", ".txt", ".html", ".csv", ".yaml", ".yml"}
SKIP_NAMES = {".DS_Store"}
SKIP_DIRS = {"node_modules", "__pycache__", ".git"}
ALLOW_MARK = "leak-scan: allow"
SHEET_ID_STOPWORDS = {"string"}   # `--sheet-id string`（lark-cli --help 原文的参数类型），不是坐标

# internal_host：内网域名两段式片段（如 <二级>.<顶级>、jira.<二级>）的 sha256(小写)。新增：
#   python3 -c "import hashlib;print(hashlib.sha256('<片段>'.encode()).hexdigest())"
INTERNAL_HOST_SHA256 = {
    "699c9d6e58700aeceb380827eaac9f7e8c3dd13d09b1ddd878ec43aa17dbec7d",
    "d57ed052a311f18b6ffdbba9dc49deed71229b83069065a73267d85a0a512523",
    "b2de0952c805be0c0bc6543cd46924e506f613364e7d6ee222481008b6df5245",   # 公司飞书租户子域.larksuite
    "ec345efcab9e51cac82db1bedd96ecc7eaeb68fa8f456881317385256c0b417d",   # 埋点平台域名
    "68cc4ad0c68c615689f41d9046c222cf1d69df248a6c7a018b985feedd95cdb3",   # 埋点平台域名
}
HOSTLIKE = re.compile(r"(?<![A-Za-z0-9_-])[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+")


def _internal_host_hits(line):
    """在形如 a.b.c 的片段里找任一连续 ≥2 段、哈希命中 INTERNAL_HOST_SHA256 的子串 → [(start, end, 片段)]。"""
    out = []
    for m in HOSTLIKE.finditer(line):
        labels = m.group(0).split(".")
        offs, pos = [], m.start()
        for lab in labels:
            offs.append(pos)
            pos += len(lab) + 1
        i = 0
        while i < len(labels):          # 自左向右、不重叠（与正则 finditer 同语义：jira.<二级>.<顶级> 只报一次）
            nxt = i + 1
            for j in range(i + 2, len(labels) + 1):
                frag = ".".join(labels[i:j])
                if hashlib.sha256(frag.lower().encode("utf-8")).hexdigest() in INTERNAL_HOST_SHA256:
                    out.append((offs[i], offs[i] + len(frag), frag))
                    nxt = j
                    break
            i = nxt
    return out


RULES = [
    ("internal_host", None),   # 见 _internal_host_hits
    ("lark_url_token", re.compile(r"larksuite\.com/(?:base|sheets|docx|docs|wiki|share/base/form|file)/[A-Za-z0-9_-]{10,}")),
    ("lark_prefixed_token", re.compile(r"\b(?:shr|shtcn|shtus|doxcn|doxus|wikcn|wikus|basus|bascn|tbl|vew|blk|fld)[A-Za-z0-9]{8,}\b")),
    ("lark_base_token", re.compile(r"\b[A-Za-z0-9]{27}\b")),
    ("wiki_space_id", re.compile(r"\b7[0-9]{18}\b")),
    ("sheet_id", re.compile(r"(?:--sheet-id |sheet_id[=:]|\"sheet_id\"\s*:\s*\")([a-z0-9]{6})(?![A-Za-z0-9])")),
]


def _base_token_ok(s):
    return any(c.isupper() for c in s) and any(c.islower() for c in s) and any(c.isdigit() for c in s)


def iter_files(root):
    pkg_path = os.path.join(root, "package.json")
    try:
        with open(pkg_path, "r", encoding="utf-8") as fh:
            entries = json.load(fh).get("files") or []
    except (OSError, ValueError) as exc:
        raise SystemExit("leak_scan: 读不了 %s（%s）" % (pkg_path, exc))
    seen = set()
    targets = ["package.json"] + [e for e in entries if isinstance(e, str)]
    for entry in targets:
        p = os.path.join(root, entry)
        if os.path.isdir(p):
            for dirpath, dirnames, filenames in os.walk(p):
                dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS)
                for fn in sorted(filenames):
                    fp = os.path.join(dirpath, fn)
                    if fp not in seen:
                        seen.add(fp)
                        yield fp
        elif os.path.isfile(p) and p not in seen:
            seen.add(p)
            yield p


def read_text(path):
    name = os.path.basename(path)
    if name in SKIP_NAMES:
        return None
    ext = os.path.splitext(name)[1].lower()
    if ext and ext not in TEXT_EXT:
        return None
    try:
        with open(path, "rb") as fh:
            raw = fh.read()
    except OSError:
        return None
    if b"\x00" in raw:
        return None
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return None if not ext else raw.decode("utf-8", "replace")


def scan_text(text):
    hits = []
    for lineno, line in enumerate(text.splitlines(), 1):
        if ALLOW_MARK in line:
            continue
        spans = []
        for rule, rx in RULES:
            if rx is None:
                found = _internal_host_hits(line)
            elif rule == "sheet_id":
                found = [(m.start(1), m.end(1), m.group(1)) for m in rx.finditer(line)]
            else:
                found = [(m.start(), m.end(), m.group(0)) for m in rx.finditer(line)]
            for s, e, frag in found:
                if rule == "lark_base_token" and not _base_token_ok(frag):
                    continue
                if rule == "sheet_id" and frag in SHEET_ID_STOPWORDS:
                    continue
                if any(a <= s and e <= b for a, b in spans):   # 已被更具体的规则报过
                    continue
                spans.append((s, e))
                hits.append((lineno, rule, frag))
    return hits


def main(argv=None):
    ap = argparse.ArgumentParser(prog="leak_scan.py", description="发版闸：扫公开包里的公司内部标识符。")
    ap.add_argument("--root", default=None, help="包根目录（默认 = 本脚本上一级）")
    ap.add_argument("--json", action="store_true", help="输出结构化 JSON")
    args = ap.parse_args(argv)
    root = os.path.abspath(args.root or os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir))

    results, nfiles = [], 0
    for fp in iter_files(root):
        text = read_text(fp)
        if text is None:
            continue
        nfiles += 1
        rel = os.path.relpath(fp, root)
        for lineno, rule, frag in scan_text(text):
            results.append({"path": rel, "line": lineno, "rule": rule, "match": frag})

    if args.json:
        print(json.dumps({"root": root, "files_scanned": nfiles, "hits": results, "count": len(results)},
                         ensure_ascii=False, indent=2))
    else:
        for h in results:
            print("%s:%d:%s:%s" % (h["path"], h["line"], h["rule"], h["match"]))
        print("LEAK_SCAN: %d hits" % len(results) if results else "LEAK_SCAN: clean")
    return 1 if results else 0


if __name__ == "__main__":
    sys.exit(main())
