#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# PRD Authoring Kit · © Noah Zhan (@noah.zhan) · 二次分发/衍生须保留署名，不得标榜为自己原创创作。LICENSE / NOTICE 见根目录。
"""需求收集表 / 文案校对登记表 / 通用登记表 登记脚本（流水线 S3 / S4 / S6，规则见 references/13-workflow.md）。

只调用本机已登录的 `lark-cli`，不读写任何密钥、不碰网络以外的东西。
所有写动作都走「plan 预览 → apply --yes」两步：没有 --yes 一律只打印、退出码 2。

另有 `telemetry` 子命令（使用采集，规则见 references/11-usage-telemetry.md §形态 C）：
往「PRD写作kit使用记录」表追加一行「使用时间 | 使用人 | 需求名称 | 平台 | 模式」——
**永远退出码 0、只打印一行状态、失败静默不重试**；`demand-apply` / `copy-review-apply` / `row-apply`
写入成功后各自动记一行（模式 `登记需求` / `登记校对` / `登记实验`），伴生 `jira-card-kit` 的
`apply` 成功后调本命令记 `建卡`。

通用行登记 `row-plan` / `row-apply`（流水线 S6，服务 AB 实验管理表与以后任何登记表）由
`references/12-library-manifest.json` 的 `forms.<key>` 驱动：只继承 `inherit_from_reference`
列出的流程常量、`confirm` 里的产品拍板项缺一不写 plan、`leave_empty` 的格写完回读后显式置 null
（防表默认值回填），成功后按 `telemetry_mode` 记一行使用记录。

Python 3.9 兼容（本机 /usr/bin/python3 是 3.9）。
"""

import argparse
import json
import os
import re
import subprocess
import sys
import time

# ---------------------------------------------------------------- 常量 / 配置

JIRA_BROWSE = "https://jira.mxcb.xyz/browse/"
JIRA_KEY_RE = re.compile(r"^[A-Z][A-Z0-9]+-\d+$")   # 形如 WEB-19856 / APP-37283

# 需求收集表字段名（2026-09 表头；以 `lark-cli base +field-list` 读回为准）
F_NAME = "需求描述"
F_MODULE = "产品模块"
F_PRD = "PRD"
F_JIRA = "Jira单号/链接"
F_PM = "产品经理"
F_PROPOSER = "需求提出方"
F_PRIORITY = "优先级"
F_ITERATION = "迭代版本"
F_PROGRESS = "进展"
F_VALUE = "需求价值"
F_SOURCE_DEPT = "需求来源部门"
F_BRD = "BRD/MRD"
F_NOTE = "备注"

# 查找既有行时投影的列（demand-find 输出表的列顺序）
FIND_COLUMNS = [F_NAME, F_PRD, F_JIRA, F_PROGRESS, F_PM]

# 需求描述是短需求名（≤20 字）：超过 NAME_MAX_LEN 字 demand-plan 标「⚠ 过长」、退出码 2、不写 plan（--allow-long 放行）
NAME_MAX_LEN = 40
NAME_TOO_LONG = "⚠ 过长（需求描述是短名，不是功能清单）"
# demand-plan 预览表首行之前的固定提示
PREVIEW_HINT = "🔴 下面每一格都要先贴给产品看过（含自动填的需求描述 / PRD / Jira），点头后再 demand-apply。"
# 写入后回读 `Jira单号/链接` 不以 `[` 开头时打这一句
JIRA_NOT_LINKED = "⚠ Jira 格未成链"


class LarkError(Exception):
    """lark-cli 调用失败：退出码非零、输出不是 JSON、或 ok=false。"""


class PlanError(Exception):
    """参数 / 校验失败，用户可读的中文错误。"""


# ---------------------------------------------------------------- 配置加载


def _load_json_file(path):
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def load_library():
    """按优先级合并清单：内置 manifest < 用户级覆盖 < 环境变量 PRD_KIT_LIBRARY。

    只有顶层键 `sources` / `forms` 参与覆盖（整键替换，不做深合并）。
    PRD_KIT_LIBRARY 是**测试专用**逃生口，正常回合不要设。
    """
    here = os.path.dirname(os.path.abspath(__file__))
    manifest = os.path.join(here, os.pardir, "references", "12-library-manifest.json")
    manifest = os.path.normpath(manifest)

    lib = {"sources": [], "forms": {}}
    layers = [manifest, os.path.expanduser("~/.prd-authoring-kit/library.json")]
    env_path = os.environ.get("PRD_KIT_LIBRARY")
    if env_path:
        layers.append(os.path.expanduser(env_path))

    found_any = False
    for path in layers:
        if not path or not os.path.isfile(path):
            continue
        found_any = True
        data = _load_json_file(path)
        for key in ("sources", "forms"):
            if key in data:
                lib[key] = data[key]
    if not found_any:
        raise PlanError(
            "找不到清单文件：既没有 %s，也没有 ~/.prd-authoring-kit/library.json。\n"
            "店铺版等无清单环境请按 references/12-context-recall.md §十 手工填表。" % manifest
        )
    return lib


def demand_table(lib):
    """需求收集表坐标 = sources[0] 的 base_token + table_id。"""
    sources = lib.get("sources") or []
    if not sources:
        raise PlanError("清单里 sources 为空，拿不到需求收集表坐标（sources[0]）。")
    src = sources[0]
    base_token = src.get("base_token")
    table_id = src.get("table_id")
    if not base_token or not table_id:
        raise PlanError("清单 sources[0] 缺 base_token / table_id。")
    return base_token, table_id


def copy_review_token(lib):
    """文案登记表 share_token = forms.copy_review.form_token。"""
    form = (lib.get("forms") or {}).get("copy_review") or {}
    token = form.get("form_token")
    if not token:
        raise PlanError(
            "清单里没有 forms.copy_review.form_token。没有该文件的环境（店铺版）请产品给表单链接，"
            "按 references/10-i18n-terms.md §校对登记 手工填。"
        )
    return token


# ---------------------------------------------------------------- lark-cli 封装


def run_lark(args, raw=False):
    """跑一条 lark-cli 命令，返回解析后的 JSON（dict）。

    统一追加 `--format json`；写命令由各调用处自带 `--as user`。
    stdout 里从第一个 `{` 起做 raw_decode，尾部噪声不影响解析。
    退出码非零 / 解析失败 / ok=false → 抛 LarkError，带上 stderr 与 error 全文。
    raw=True 时不校验 ok（给 --dry-run 这类只回请求体的调用留口）。
    """
    cmd = ["lark-cli"] + list(args) + ["--format", "json"]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True)
    except OSError as exc:
        raise LarkError("无法执行 lark-cli（%s）。请确认已安装并在 PATH 里。\n命令：%s" % (exc, " ".join(cmd)))

    stdout = proc.stdout or ""
    stderr = (proc.stderr or "").strip()
    payload = None
    idx = stdout.find("{")
    if idx >= 0:
        try:
            payload, _ = json.JSONDecoder().raw_decode(stdout[idx:])
        except ValueError:
            payload = None

    def _fail(reason):
        detail = []
        detail.append("lark-cli 调用失败：%s" % reason)
        detail.append("命令：%s" % " ".join(cmd))
        detail.append("退出码：%s" % proc.returncode)
        if isinstance(payload, dict) and payload.get("error") is not None:
            detail.append("error：%s" % json.dumps(payload["error"], ensure_ascii=False))
        if stderr:
            detail.append("stderr：%s" % stderr)
        if not stderr and stdout.strip():
            detail.append("stdout：%s" % stdout.strip())
        raise LarkError("\n".join(detail))

    if proc.returncode != 0:
        _fail("退出码非零")
    if payload is None:
        _fail("stdout 里找不到可解析的 JSON")
    if not raw and payload.get("ok") is False:
        _fail("返回 ok=false")
    return payload


# ---------------------------------------------------------------- 取值 / 渲染


def is_empty(value):
    """单元格是否为空（None / 空串 / 空数组 / 空对象都算空）。"""
    if value is None:
        return True
    if isinstance(value, str):
        return value.strip() == ""
    if isinstance(value, (list, dict)):
        return len(value) == 0
    return False


def render(value, width=0):
    """把 lark 单元格值渲染成一行可读文本（预览表 / 回读用）。"""
    if value is None:
        return ""
    if isinstance(value, str):
        text = value
    elif isinstance(value, list):
        parts = []
        for item in value:
            if isinstance(item, dict):
                parts.append(str(item.get("name") or item.get("text") or item.get("id") or ""))
            else:
                parts.append(str(item))
        text = " / ".join(p for p in parts if p)
    elif isinstance(value, dict):
        text = str(value.get("name") or value.get("text") or json.dumps(value, ensure_ascii=False))
    else:
        text = json.dumps(value, ensure_ascii=False)
    text = text.replace("\n", " ⏎ ").replace("|", "丨")
    if width and len(text) > width:
        text = text[: width - 1] + "…"
    return text


def print_table(headers, rows):
    """打印一张 markdown 风格的表（等宽按显示宽度粗算，中文按 2 计）。"""

    def w(s):
        return sum(2 if ord(c) > 0x2E80 else 1 for c in s)

    widths = [w(h) for h in headers]
    for row in rows:
        for i, cell in enumerate(row):
            widths[i] = max(widths[i], w(cell))

    def line(cells):
        out = []
        for i, cell in enumerate(cells):
            out.append(cell + " " * (widths[i] - w(cell)))
        return "| " + " | ".join(out) + " |"

    print(line(headers))
    print("|" + "|".join("-" * (x + 2) for x in widths) + "|")
    for row in rows:
        print(line(row))


def prd_token(url):
    """取 PRD 链接最后一段 token（去掉 query / fragment / 末尾斜杠）。"""
    if not url:
        return ""
    text = url.split("#", 1)[0].split("?", 1)[0].rstrip("/")
    return text.rsplit("/", 1)[-1] if "/" in text else text


# ---------------------------------------------------------------- 表检索


def search_rows(base_token, table_id, keyword, limit=50):
    """`base +record-search`：在 PRD / 需求描述 / Jira单号/链接 三列里按关键词找行。

    实测返回形状（1.0.91）：data.data 是**行矩阵**（每行按 data.fields 的列序），
    行对应的 record_id 在 data.record_id_list（同下标），另有 field_type_list / has_more。
    → 解析时按列名建字典，不要指望返回 record 对象。
    """
    args = [
        "base", "+record-search",
        "--base-token", base_token,
        "--table-id", table_id,
        "--keyword", keyword,
        "--search-field", F_PRD,
        "--search-field", F_NAME,
        "--search-field", F_JIRA,
    ]
    for col in FIND_COLUMNS:
        args += ["--field-id", col]
    args += ["--limit", str(limit), "--as", "user"]

    data = run_lark(args).get("data") or {}
    fields = data.get("fields") or []
    matrix = data.get("data") or []
    rec_ids = data.get("record_id_list") or []
    rows = []
    for i, raw_row in enumerate(matrix):
        cells = {}
        for j, name in enumerate(fields):
            cells[name] = raw_row[j] if j < len(raw_row) else None
        rows.append({"record_id": rec_ids[i] if i < len(rec_ids) else "", "cells": cells})
    return rows, bool(data.get("has_more"))


def find_existing(base_token, table_id, prd_url, name_kw, jira_kw=""):
    """依次用「PRD 链接最后一段 token」→「--name 关键词」→「Jira KEY」找既有行，返回 (rows, 命中的关键词)。"""
    tried = []
    for keyword in [prd_token(prd_url), name_kw, first_jira_key(jira_kw)]:
        if not keyword:
            continue
        tried.append(keyword)
        rows, _ = search_rows(base_token, table_id, keyword)
        if rows:
            return rows, keyword
    return [], (tried[-1] if tried else "")


def get_record(base_token, table_id, record_id):
    """`base +record-get` 读回一整行 → {字段名: 值}。"""
    args = [
        "base", "+record-get",
        "--base-token", base_token,
        "--table-id", table_id,
        "--record-id", record_id,
        "--as", "user",
    ]
    data = run_lark(args).get("data") or {}
    fields = data.get("fields") or []
    matrix = data.get("data") or []
    if not matrix:
        return {}
    row = matrix[0]
    return dict((name, row[i] if i < len(row) else None) for i, name in enumerate(fields))


def check_option(base_token, table_id, field, value, field_id=None):
    """在线校验单选值：必须与某个选项 name **完全相等**（选项会变，脚本不内置枚举）。

    🔴 `--field-id` 优先传真 field id：字段名里带 `%` 之类字符时按名查会被服务端判 param invalid
    （实测「上线初始流量%」= 800004006），按 id 查才回得来选项。
    """
    args = [
        "base", "+field-search-options",
        "--base-token", base_token,
        "--table-id", table_id,
        "--field-id", field_id or field,
        "--keyword", value,
        "--limit", "200",
        "--as", "user",
    ]
    data = run_lark(args).get("data") or {}
    options = [o.get("name", "") for o in (data.get("options") or [])]
    if value in options:
        return value
    hint = "、".join(o for o in options if o) or "（该关键词没搜到任何选项）"
    raise PlanError(
        "「%s」字段没有完全相等的选项：%r。\n包含该关键词的候选：%s\n"
        "（选项随时会变，请照抄上面的选项名，别自己编。）" % (field, value, hint)
    )


# ---------------------------------------------------------------- 字段元信息 / 单元格值

# 系统列与派生列：一律不写（写了服务端也会忽略或报错）
READONLY_TYPES = ("created_by", "created_at", "modified_by", "modified_at", "last_modified_by",
                  "last_modified_time", "auto_number", "formula", "lookup", "button", "barcode")
# 写入形态 = [{"id": "…"}] 的一类字段
ID_TYPES = ("user", "group", "chat", "link", "duplex_link")
NUMBER_TYPES = ("number", "currency", "percent", "rating", "progress")
SELECT_TYPES = ("select", "single_select")
MULTI_SELECT_TYPES = ("multi_select", "multiSelect", "multiselect")


def list_fields(base_token, table_id):
    """`base +field-list` → [{"id","name","type"}…]，保持表里的字段顺序（预览按它排）。"""
    args = ["base", "+field-list", "--base-token", base_token,
            "--table-id", table_id, "--limit", "200", "--as", "user"]
    data = run_lark(args).get("data") or {}
    metas = []
    for field in data.get("fields") or []:
        metas.append({"id": field.get("id") or "", "name": field.get("name") or "",
                      "type": field.get("type") or ""})
    if not metas:
        raise PlanError("`+field-list` 读不到字段（base=%s table=%s）。" % (base_token, table_id))
    return metas


def build_cell(base_token, table_id, meta, raw):
    """把 `--set 字段=值` 的字符串按字段类型转成 lark 单元格值；**值给空串 = 清空（None）**。

    select / multi_select 走在线校验（不等即报候选）；user / group / link 收 open_id（逗号分隔）；
    number 转数字；checkbox 收 true/1/是；其余（text / url / phone / datetime）原样写字符串。
    """
    name, ftype, fid = meta["name"], meta["type"], meta["id"]
    if raw is None or raw.strip() == "":
        return None
    text = raw.strip()
    if ftype in READONLY_TYPES:
        raise PlanError("「%s」是 %s 字段（系统列 / 派生列），不能写。" % (name, ftype))
    if ftype in SELECT_TYPES:
        return [check_option(base_token, table_id, name, text, fid)]
    if ftype in MULTI_SELECT_TYPES:
        parts = [p.strip() for p in text.replace("，", ",").split(",") if p.strip()]
        return [check_option(base_token, table_id, name, p, fid) for p in parts]
    if ftype in ID_TYPES:
        parts = [p.strip() for p in text.replace("，", ",").split(",") if p.strip()]
        return [{"id": p} for p in parts]
    if ftype in NUMBER_TYPES:
        try:
            number = float(text)
        except ValueError:
            raise PlanError("「%s」是数字字段，%r 不是数字。" % (name, raw))
        return int(number) if number == int(number) else number
    if ftype == "checkbox":
        return text.lower() in ("true", "1", "是", "yes", "y")
    return text


def normalize_inherited(value, ftype):
    """参考行继承来的值转成可写形态：user / group / link 只留 id（回读带 name，写回只认 id）。"""
    if ftype in ID_TYPES and isinstance(value, list):
        ids = [{"id": item.get("id")} for item in value if isinstance(item, dict) and item.get("id")]
        return ids or None
    return value


def cell_key(value):
    """把「将写入的值」和「回读值」归一成同一把可比较的钥匙（user 回读带 name、数字可能变 float）。"""
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return "%g" % float(value)
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, list):
        parts = []
        for item in value:
            if isinstance(item, dict):
                parts.append(str(item.get("id") or item.get("name") or item.get("text") or ""))
            else:
                parts.append(str(item))
        return "|".join(parts)
    if isinstance(value, dict):
        return str(value.get("id") or value.get("name") or value.get("text")
                   or json.dumps(value, ensure_ascii=False, sort_keys=True))
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def first_jira_key(jira):
    """`--jira WEB-1,APP-2` → 第一个 KEY（检索关键词用）。"""
    keys = [k.strip() for k in (jira or "").replace("，", ",").split(",") if k.strip()]
    return keys[0] if keys else ""


def jira_link_text(raw):
    """`Jira单号/链接` 写成可点的 Markdown 链接：值形如 `KEY` / `KEY,KEY` → `[KEY](URL)`（多张换行）。

    已是 `[..](..)` 或含 `http` 的原样返回；不是 KEY 形状的其它文本也原样返回（不猜）。
    """
    text = (raw or "").strip()
    if not text or "http" in text or (text.startswith("[") and "](" in text):
        return raw
    keys = [k.strip() for k in text.replace("，", ",").split(",") if k.strip()]
    if not keys or not all(JIRA_KEY_RE.match(k) for k in keys):
        return raw
    return "\n".join("[%s](%s%s)" % (k, JIRA_BROWSE, k) for k in keys)


def jira_cell_linked(value):
    """回读的 `Jira单号/链接` 格是否成链：文本以 `[` 开头（Markdown 链接）。"""
    text = value if isinstance(value, str) else render(value)
    return text.strip().startswith("[")


def record_id_from_url(url):
    """从记录链接的 query 里取 `record=recXXXX`（`+url-resolve` 只回 base_token / block_id）。"""
    query = (url or "").split("?", 1)[-1]
    for part in query.replace("&amp;", "&").split("&"):
        key, _, value = part.partition("=")
        if key.strip() == "record" and value.strip():
            return value.strip().split("#")[0]
    return ""


def resolve_reference(ref, default_base, default_table):
    """`--reference` → (base_token, table_id, record_id)：rec 开头当 record_id，http 走 +url-resolve。"""
    ref = (ref or "").strip()
    if ref.startswith("rec"):
        return default_base, default_table, ref
    if ref.startswith("http"):
        data = run_lark(["base", "+url-resolve", "--url", ref, "--as", "user"]).get("data") or {}
        base_token = data.get("base_token") or default_base
        table_id = data.get("table_id") or data.get("block_id") or default_table
        record_id = data.get("record_id") or record_id_from_url(ref)
        if not record_id:
            raise PlanError(
                "参考行链接里没有 `record=rec…`，`+url-resolve` 也没回 record_id：\n"
                "改用 `--reference <record_id>`（rec 开头）再跑一次。")
        return base_token, table_id, record_id
    raise PlanError("--reference 只认记录链接（http…）或 rec 开头的 record_id，实际给了 %r。" % ref)


def render_fixed(template, me_name):
    """`fixed` 里的占位符：`{whoami.name}` = 登录人姓名；`{whoami.first_lower}` = 姓名首个词小写。"""
    text = str(template)
    first = (me_name or "").replace("·", " ").split(" ")[0]
    return text.replace("{whoami.name}", me_name or "").replace("{whoami.first_lower}", first.lower())


# ---------------------------------------------------------------- whoami


def cmd_whoami(args):
    data = run_lark(["contact", "+get-user", "--as", "user"]).get("data") or {}
    user = data.get("user") or {}
    name = user.get("name") or user.get("en_name") or "?"
    open_id = user.get("open_id") or "?"
    print("%s | %s" % (name, open_id))
    return 0


def whoami_open_id():
    data = run_lark(["contact", "+get-user", "--as", "user"]).get("data") or {}
    user = data.get("user") or {}
    if not user.get("open_id"):
        raise PlanError("拿不到登录本人的 open_id（contact +get-user 返回里没有 data.user.open_id）。")
    return user["open_id"], user.get("name") or ""


# ---------------------------------------------------------------- demand-find


def cmd_demand_find(args):
    lib = load_library()
    base_token, table_id = demand_table(lib)
    if not (args.prd or args.name or args.jira):
        raise PlanError("--prd / --name / --jira 至少给一个（三者都空就没有检索键）。")
    rows, keyword = find_existing(base_token, table_id, args.prd, args.name, args.jira)
    if not rows:
        print("没找到既有行（试过的关键词：%s）。登记时会走 create 新建一行。" % (keyword or "无"))
        return 0
    print("命中 %d 行（关键词：%s）" % (len(rows), keyword))
    headers = ["record_id"] + FIND_COLUMNS
    table = []
    for row in rows:
        table.append([row["record_id"]] + [render(row["cells"].get(c), 40) for c in FIND_COLUMNS])
    print_table(headers, table)
    return 0


# ---------------------------------------------------------------- demand-plan


def cmd_demand_plan(args):
    lib = load_library()
    base_token, table_id = demand_table(lib)

    # ① 登记人默认 = lark-cli 登录本人
    me_id, me_name = whoami_open_id()
    pm = args.pm or me_id
    proposer = args.proposer or me_id

    # ② 单选值在线校验（六项必填里的四个单选 + 可选的来源部门）
    missing = []
    checked = {}
    for flag, field, value in [
        ("--module", F_MODULE, args.module),
        ("--priority", F_PRIORITY, args.priority),
        ("--iteration", F_ITERATION, args.iteration),
        ("--progress", F_PROGRESS, args.progress),
    ]:
        if not value:
            missing.append(flag)
            continue
        checked[field] = check_option(base_token, table_id, field, value)
    if args.source_dept:
        checked[F_SOURCE_DEPT] = check_option(base_token, table_id, F_SOURCE_DEPT, args.source_dept)
    if not args.name:
        missing.append("--name")

    # ③ 找既有行 → 定模式
    existing = {}
    if args.record_id:
        mode, record_id = "update", args.record_id
        existing = get_record(base_token, table_id, record_id)
    else:
        rows, keyword = find_existing(base_token, table_id, args.prd, args.name, args.jira)
        if len(rows) == 1:
            mode, record_id = "update", rows[0]["record_id"]
            existing = get_record(base_token, table_id, record_id)
        elif len(rows) > 1:
            print("命中 %d 行（关键词：%s），无法自动判定要更新哪一行。" % (len(rows), keyword))
            headers = ["record_id"] + FIND_COLUMNS
            print_table(headers, [[r["record_id"]] + [render(r["cells"].get(c), 40) for c in FIND_COLUMNS] for r in rows])
            print("\n请挑一行，用 --record-id <rec…> 再跑一次；确实是新需求就换更精确的 --name 关键词。")
            return 2
        else:
            mode, record_id = "create", None

    # ④ 组装字段（写入形态见 lark-base cell-value：select = 选项名数组、user = [{"id": open_id}]、链接列 = 纯 URL 字符串）
    fields = {}
    source = {}

    def put(field, value, origin):
        if value is None or value == "":
            return
        fields[field] = value
        source[field] = origin

    put(F_NAME, args.name, "参数")
    put(F_PRD, args.prd, "参数")
    for field in (F_MODULE, F_PRIORITY, F_ITERATION, F_PROGRESS, F_SOURCE_DEPT):
        if field in checked:
            put(field, [checked[field]], "参数")
    if args.jira:
        keys = [k.strip() for k in args.jira.replace("，", ",").split(",") if k.strip()]
        put(F_JIRA, "\n".join("[%s](%s%s)" % (k, JIRA_BROWSE, k) for k in keys), "参数")
    put(F_VALUE, args.value, "参数")
    put(F_BRD, args.brd, "参数")
    put(F_NOTE, args.note, "参数")
    put(F_PM, [{"id": pm}], "参数" if args.pm else "默认=本人")
    put(F_PROPOSER, [{"id": proposer}], "参数" if args.proposer else "默认=本人")

    # ⑤ 预览表：必填缺失的格打「？」；update 模式下既有非空格标「既有行保留」；需求描述超长标「⚠ 过长」
    too_long = len(args.name) > NAME_MAX_LEN and not args.allow_long
    print("登记预览（模式：%s%s；登记人：%s）" % (
        mode, "，record_id=%s" % record_id if record_id else "", me_name))
    print(PREVIEW_HINT)
    order = [F_NAME, F_MODULE, F_PRD, F_JIRA, F_PM, F_PROPOSER, F_PRIORITY,
             F_ITERATION, F_PROGRESS, F_VALUE, F_SOURCE_DEPT, F_BRD, F_NOTE]
    required = {F_NAME: "--name", F_MODULE: "--module",
                F_PRIORITY: "--priority", F_ITERATION: "--iteration", F_PROGRESS: "--progress"}
    table = []
    for field in order:
        if field == F_NAME and too_long:
            table.append([field, render(fields[field], 90), NAME_TOO_LONG])
        elif field in fields:
            keep = mode == "update" and not is_empty(existing.get(field))
            if keep:
                table.append([field, render(existing.get(field), 90), "既有行保留（apply 默认不覆盖，--overwrite 才盖）"])
            else:
                table.append([field, render(fields[field], 90), source[field]])
        elif field in required:
            table.append([field, "？", "缺 %s" % required[field]])
        else:
            table.append([field, "—", "未给（不写）"])
    print_table(["字段", "将写入的值", "来源"], table)

    if missing:
        print("\n必填参数缺失：%s —— 预览里对应格已打「？」，不写 plan。" % "、".join(missing))
    if too_long:
        print("\n需求描述 %d 字 > %d —— 预览里该格已标「⚠ 过长」，不写 plan"
              "（需求描述是 ≤20 字的短需求名；确需长名加 --allow-long）。" % (len(args.name), NAME_MAX_LEN))
    if missing or too_long:
        return 2

    plan = {"mode": mode, "record_id": record_id, "base_token": base_token,
            "table_id": table_id, "fields": fields,
            "telemetry": {"requirement": args.requirement or args.name,
                          "platform": args.platform}}
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(plan, fh, ensure_ascii=False, indent=2)
        fh.write("\n")
    print("\nplan 已写入：%s" % args.out)
    print("确认无误后：python3 %s demand-apply %s --yes" % (os.path.basename(__file__), args.out))
    return 0


# ---------------------------------------------------------------- demand-apply


def cmd_demand_apply(args):
    plan = _load_json_file(args.plan)
    base_token = plan["base_token"]
    table_id = plan["table_id"]
    mode = plan["mode"]
    fields = plan.get("fields") or {}
    record_id = plan.get("record_id")

    written = fields
    if mode == "create":
        payload = json.dumps({"create_records": [fields]}, ensure_ascii=False)
        cmd = ["base", "+record-batch-create", "--base-token", base_token,
               "--table-id", table_id, "--json", payload, "--as", "user"]
    elif mode == "update":
        if not record_id:
            print("plan 里 mode=update 却没有 record_id，拒绝执行。")
            return 1
        current = get_record(base_token, table_id, record_id)
        subset = {}
        skipped = []
        for field, value in fields.items():
            if args.overwrite or is_empty(current.get(field)):
                subset[field] = value
            else:
                skipped.append(field)
        if skipped:
            print("既有行这些格非空、跳过不覆盖（要盖加 --overwrite）：%s" % "、".join(skipped))
        if not subset:
            print("既有行该填的格都已有值，无需写入。record_id=%s" % record_id)
            return 0
        written = subset
        payload = json.dumps(subset, ensure_ascii=False)
        cmd = ["base", "+record-upsert", "--base-token", base_token, "--table-id", table_id,
               "--record-id", record_id, "--json", payload, "--as", "user"]
    else:
        print("plan 里 mode 只能是 create / update，实际是 %r。" % mode)
        return 1

    if not args.yes:
        print("将执行（加 --yes 才真跑）：")
        print("  lark-cli " + " ".join(cmd) + " --format json")
        return 2

    result = run_lark(cmd).get("data") or {}
    if mode == "create":
        record_id = _first_created_id(result) or record_id
        if not record_id:
            print("已创建，但返回里没拿到 record_id，原样打印：%s" % json.dumps(result, ensure_ascii=False)[:800])
            return 0

    final = get_record(base_token, table_id, record_id)
    print("写入成功（%s）。record_id = %s" % (mode, record_id))
    print_table(["字段", "回读值"], [[k, render(v, 60)] for k, v in final.items() if not is_empty(v)])
    if F_JIRA in written and not jira_cell_linked(final.get(F_JIRA)):
        print("%s（回读：%s）" % (JIRA_NOT_LINKED, render(final.get(F_JIRA), 60)))
    if mode == "create":
        print_table_defaults(base_token, table_id, fields, final)
    telemetry_after(plan, "登记需求", fields.get(F_NAME) or "")
    return 0


def print_table_defaults(base_token, table_id, planned, final):
    """新建行回读后：把**不在 plan 里却回读非空**的格打成一行（= 表默认值回填）。不自动清。"""
    skip = set()
    try:
        for meta in list_fields(base_token, table_id):
            if meta["type"] in READONLY_TYPES:
                skip.add(meta["name"])
    except (LarkError, PlanError):
        pass
    extras = [(name, render(value, 30)) for name, value in final.items()
              if name not in planned and name not in skip and not is_empty(value)]
    if not extras:
        return
    print("表默认值回填：%s（要清空就 demand-update %s --set 字段= ）" % (
        " ".join("%s=%s" % (n, v) for n, v in extras),
        "<record_id>"))


def _first_created_id(result):
    """从 +record-batch-create 返回里挖第一个 record_id（不同版本外层键不一，做几层兜底）。"""
    for key in ("records", "record_id_list", "items", "data"):
        value = result.get(key)
        if isinstance(value, list) and value:
            head = value[0]
            if isinstance(head, str):
                return head
            if isinstance(head, dict) and head.get("record_id"):
                return head["record_id"]
    if isinstance(result.get("record"), dict):
        return result["record"].get("record_id")
    return None


# ---------------------------------------------------------------- demand-update


def cmd_demand_update(args):
    """改需求收集表的某几格（产品当场改优先级 / 迭代版本 / 进展，或事后补 PRD 链接）。

    不整行重写：只动 `--set` 点名的格；值给空串 = 清空；写后 `+record-get` 回读打印。
    """
    lib = load_library()
    base_token, table_id = demand_table(lib)
    metas = list_fields(base_token, table_id)
    by_name = dict((m["name"], m) for m in metas)

    current = get_record(base_token, table_id, args.record_id)
    if not current:
        raise PlanError("record_id=%s 在需求收集表里读不到（先用 demand-find 确认行号）。" % args.record_id)

    pairs = args.set or []
    if not pairs:
        raise PlanError("至少要给一个 `--set 字段=值`（值留空 = 清空该格）。")
    changes = {}
    for item in pairs:
        name, sep, raw = item.partition("=")
        name = name.strip()
        if not sep:
            raise PlanError("--set 要写成「字段=值」，实际给了 %r。" % item)
        if name not in by_name:
            raise PlanError("需求收集表里没有字段「%s」。现有字段：%s" % (
                name, "、".join(m["name"] for m in metas)))
        if name == F_JIRA:
            raw = jira_link_text(raw)
        changes[name] = build_cell(base_token, table_id, by_name[name], raw)

    print("将改的格（record_id=%s）" % args.record_id)
    print_table(["字段", "现值", "改为"],
                [[name, render(current.get(name), 90),
                  "（清空）" if value is None else render(value, 90)]
                 for name, value in changes.items()])
    if not args.yes:
        print("\n加 --yes 才真写（本命令只动上面这几格，不整行重写）。")
        return 2

    payload = json.dumps({"update_records": {args.record_id: changes}}, ensure_ascii=False)
    run_lark(["base", "+record-batch-update", "--base-token", base_token, "--table-id", table_id,
              "--json", payload, "--as", "user"])
    final = get_record(base_token, table_id, args.record_id)
    print("\n写入成功。回读改后值：")
    print_table(["字段", "回读值"], [[name, render(final.get(name), 60)] for name in changes])
    if changes.get(F_JIRA) is not None and not jira_cell_linked(final.get(F_JIRA)):
        print("%s（回读：%s）" % (JIRA_NOT_LINKED, render(final.get(F_JIRA), 60)))
    stale = [name for name, value in changes.items()
             if cell_key(final.get(name)) != cell_key(value)]
    if stale:
        print("🔴 回读与将写入的值对不上：%s —— 不重试，请到表里人工核对。" % "、".join(stale))
        return 1
    return 0


# ---------------------------------------------------------------- 通用行登记 row-plan / row-apply


def pick_form(lib, key):
    """取 manifest `forms.<key>`，并确认它是 base_table 形态、坐标齐全。"""
    forms = lib.get("forms") or {}
    form = forms.get(key)
    if not isinstance(form, dict):
        raise PlanError("清单 forms 里没有「%s」。现有：%s" % (
            key, "、".join(k for k in forms if not k.startswith("_")) or "（空）"))
    if form.get("kind") != "base_table":
        raise PlanError("forms.%s 的 kind 是 %r，不是 base_table —— row-plan 只服务 Base 表登记。"
                        % (key, form.get("kind")))
    if not form.get("base_token") or not form.get("table_id"):
        raise PlanError("forms.%s 缺 base_token / table_id。" % key)
    return form


def preview_order(form, metas):
    """预览行序：from_prd → 参考行继承 → 产品拍板 → 固定 → 其余 → 留空·他人填（最后一组）。

    🔴 不按 `+field-list` 的返回序：实测同一张表两次调用字段顺序不同，预览会跟着抖。
    """
    leave_empty = list(form.get("leave_empty") or [])
    order = []
    groups = [list(form.get("from_prd") or []),
              list(form.get("inherit_from_reference") or []),
              list(form.get("confirm") or []),
              list((form.get("fixed") or {}).keys()),
              [m["name"] for m in metas]]
    for group in groups:
        for name in group:
            if name not in order and name not in leave_empty:
                order.append(name)
    return order + [n for n in leave_empty if n not in order]


def default_requirement(form, metas, values):
    """采集用需求名的兜底：manifest `from_prd` 里第一个有值的格 → 表里第一个有值的格。"""
    for name in list(form.get("from_prd") or []) + [m["name"] for m in metas]:
        if not is_empty(values.get(name)):
            return render(values.get(name))
    return ""


def cmd_row_plan(args):
    """manifest 驱动的通用行登记预览（S6 AB 实验表等）。

    值的叠加顺序：参考行继承（只限 `inherit_from_reference`）→ `--set` → `fixed`；
    `leave_empty` 一律不写；`confirm` 里任一格为空 → 打「？」、退出码 2、不写 plan。
    """
    lib = load_library()
    form = pick_form(lib, args.form)
    base_token, table_id = form["base_token"], form["table_id"]

    metas = list_fields(base_token, table_id)
    by_name = dict((m["name"], m) for m in metas)
    _, me_name = whoami_open_id()

    inherit = list(form.get("inherit_from_reference") or [])
    confirm = list(form.get("confirm") or [])
    leave_empty = list(form.get("leave_empty") or [])
    fixed = form.get("fixed") or {}

    values, origin = {}, {}

    # ① 参考行：**只继承 inherit_from_reference 列出的字段**，其它一律不抄
    ref_desc = "未给 --reference"
    if args.reference:
        ref_base, ref_table, ref_rid = resolve_reference(args.reference, base_token, table_id)
        ref_row = get_record(ref_base, ref_table, ref_rid)
        if not ref_row:
            raise PlanError("参考行读不到：base=%s table=%s record=%s" % (ref_base, ref_table, ref_rid))
        ref_desc = ref_rid
        for name in inherit:
            if name not in by_name:
                raise PlanError("manifest inherit_from_reference 里的「%s」不在表字段里。现有：%s"
                                % (name, "、".join(m["name"] for m in metas)))
            value = normalize_inherited(ref_row.get(name), by_name[name]["type"])
            if not is_empty(value):
                values[name] = value
                origin[name] = "参考行继承"
    elif inherit:
        print("提示：没给 --reference，流程常量（%s）只能靠 --set 手填。" % "、".join(inherit))

    # ② --set（产品拍板项与 PRD 抄来的内容都走这里）
    for item in (args.set or []):
        name, sep, raw = item.partition("=")
        name = name.strip()
        if not sep:
            raise PlanError("--set 要写成「字段=值」，实际给了 %r。" % item)
        if name not in by_name:
            raise PlanError("「%s」表里没有这个字段。现有字段：%s" % (
                name, "、".join(m["name"] for m in metas)))
        cell = build_cell(base_token, table_id, by_name[name], raw)
        if cell is None:
            values.pop(name, None)
            origin.pop(name, None)
        else:
            values[name] = cell
            origin[name] = "参数"

    # ③ fixed（占位符 {whoami.name} / {whoami.first_lower}）
    for name, template in fixed.items():
        if name not in by_name:
            raise PlanError("manifest fixed 里的「%s」不在表字段里。" % name)
        cell = build_cell(base_token, table_id, by_name[name], render_fixed(template, me_name))
        if cell is None:
            values.pop(name, None)
            origin.pop(name, None)
        else:
            values[name] = cell
            origin[name] = "固定"

    # ④ leave_empty：约定留空，写的时候一格都不带
    for name in leave_empty:
        values.pop(name, None)
        origin.pop(name, None)

    # ⑤ 预览（按 manifest 的语义分组排；🔴 别按 +field-list 的返回序——实测同一张表两次调用顺序不同）
    print("登记预览（form=%s · %s；参考行：%s；登记人：%s）" % (
        args.form, form.get("name") or "", ref_desc, me_name))
    rows = []
    for name in preview_order(form, metas):
        meta = by_name.get(name)
        if not meta or meta["type"] in READONLY_TYPES:
            continue
        if name in values:
            rows.append([name, render(values[name], 90), origin.get(name, "参数")])
        elif name in leave_empty:
            rows.append([name, "", "留空·他人填"])
        elif name in confirm:
            rows.append([name, "？", "缺产品拍板（--set \"%s\"=…）" % name])
        else:
            rows.append([name, "—", "未给（不写）"])
    print_table(["字段", "值", "来源"], rows)
    if form.get("rule"):
        print("\n规则：%s" % form["rule"])

    missing = [name for name in confirm if is_empty(values.get(name))]
    if missing:
        print("\n产品必须拍板的字段还缺：%s —— 预览里已打「？」，不写 plan。" % "、".join(missing))
        return 2

    plan = {"form": args.form, "base_token": base_token, "table_id": table_id,
            "fields": values, "leave_empty": leave_empty,
            "telemetry": {"requirement": args.requirement or default_requirement(form, metas, values),
                          "platform": args.platform,
                          "mode": form.get("telemetry_mode") or "登记实验"}}
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(plan, fh, ensure_ascii=False, indent=2)
        fh.write("\n")
    print("\nplan 已写入：%s" % args.out)
    print("确认无误后：python3 %s row-apply %s --yes" % (os.path.basename(__file__), args.out))
    return 0


def cmd_row_apply(args):
    """按 plan 建一行 → 回读 → 清表默认值 → 逐格 diff → 记一行使用记录。"""
    plan = _load_json_file(args.plan)
    base_token = plan["base_token"]
    table_id = plan["table_id"]
    fields = plan.get("fields") or {}
    leave_empty = plan.get("leave_empty") or []

    payload = json.dumps({"create_records": [fields]}, ensure_ascii=False)
    cmd = ["base", "+record-batch-create", "--base-token", base_token,
           "--table-id", table_id, "--json", payload, "--as", "user"]
    if not args.yes:
        print("将执行（加 --yes 才真跑）：")
        print("  lark-cli " + " ".join(cmd) + " --format json")
        return 2

    result = run_lark(cmd).get("data") or {}
    record_id = _first_created_id(result)
    if not record_id:
        print("已创建，但返回里没拿到 record_id，原样打印：%s"
              % json.dumps(result, ensure_ascii=False)[:800])
        return 1
    final = get_record(base_token, table_id, record_id)
    print("写入成功（create）。record_id = %s" % record_id)

    # 🔴 防表默认值：约定留空的格被表默认值填上 → 显式置 null → 再回读验空
    dirty = dict((name, None) for name in leave_empty if not is_empty(final.get(name)))
    if dirty:
        before = ["%s=%s" % (name, render(final.get(name), 20)) for name in dirty]
        update = json.dumps({"update_records": {record_id: dirty}}, ensure_ascii=False)
        run_lark(["base", "+record-batch-update", "--base-token", base_token,
                  "--table-id", table_id, "--json", update, "--as", "user"])
        final = get_record(base_token, table_id, record_id)
        still = [name for name in dirty if not is_empty(final.get(name))]
        print("已清表默认值：%s" % " ".join(before))
        if still:
            print("🔴 置 null 后回读仍非空：%s —— 不重试，请到表里人工清。" % "、".join(still))

    print_table(["字段", "回读值"], [[k, render(v, 60)] for k, v in final.items() if not is_empty(v)])

    mismatch = [[name, render(value, 40), render(final.get(name), 40)]
                for name, value in fields.items()
                if cell_key(final.get(name)) != cell_key(value)]
    if mismatch:
        print("🔴 逐格 diff 对不上（不重试，请人工核对）：")
        print_table(["字段", "将写入", "回读"], mismatch)
    else:
        print("逐格 diff：%d 格全部一致。" % len(fields))

    mode = ((plan.get("telemetry") or {}).get("mode")) or "登记实验"
    telemetry_after(plan, mode, "")
    return 0


# ---------------------------------------------------------------- 文案校对登记表


def form_questions(share_token):
    data = run_lark(["base", "+form-detail", "--share-token", share_token, "--as", "user"]).get("data") or {}
    questions = data.get("questions") or []
    if not questions:
        raise PlanError("表单 %s 读不到题目（data.questions 为空）。" % share_token)
    return questions


def pick_question(questions, title, contains=None):
    """按题目标题定位一道题：先精确等于，再按 contains 子串兜底（表单标题带括号说明、会改）。"""
    for q in questions:
        if q.get("title") == title:
            return q
    needle = contains or title
    for q in questions:
        if needle in (q.get("title") or ""):
            return q
    raise PlanError("表单里找不到题目「%s」。现有题目：%s" % (
        title, "、".join(q.get("title", "") for q in questions)))


def option_names(question):
    return [o.get("name", "") for o in (question.get("options") or []) if o.get("name")]


def match_prefix(question, prefixes, label):
    names = option_names(question)
    for prefix in prefixes:
        for name in names:
            if name.startswith(prefix):
                return name
    raise PlanError("「%s」没有以 %s 开头的选项。现有选项：%s" % (
        label, " / ".join(repr(p) for p in prefixes), "、".join(names)))


def match_exact(question, value, label):
    names = option_names(question)
    if value in names:
        return value
    near = [n for n in names if value in n] or names
    raise PlanError("「%s」没有完全相等的选项：%r。候选：%s" % (label, value, "、".join(near)))


def match_priority(question, value):
    """优先级：取选项名首个空格 / 全角括号 / 半角括号之前的 token，与参数完全相等（P1 ≠ P1+）。"""
    names = option_names(question)
    for name in names:
        head = name
        for sep in (" ", "（", "("):
            idx = head.find(sep)
            if idx >= 0:
                head = head[:idx]
        if head.strip() == value:
            return name
    raise PlanError("优先级 %r 匹配不到表单选项。现有选项：%s" % (value, "、".join(names)))


def cmd_copy_review_plan(args):
    lib = load_library()
    share_token = copy_review_token(lib)
    questions = form_questions(share_token)

    q_type = pick_question(questions, "文案设计类型")
    q_priority = pick_question(questions, "优先级")
    q_visibility = pick_question(questions, "内容上线后可见范围")
    q_edit = pick_question(questions, "是否已开放文档编辑权限")
    q_line = pick_question(questions, "产品线")
    q_name = pick_question(questions, "需求名称")
    q_doc = pick_question(questions, "需要处理的文档链接")
    q_note = pick_question(questions, "备注", contains="备注")

    type_key = args.type.replace(" ", "")
    if type_key == "文案设计":
        type_value = match_prefix(q_type, ["文案设计 (", "文案设计("], "文案设计类型")
    elif type_key == "仅英文文案校对":
        type_value = match_prefix(q_type, ["仅英文文案校对"], "文案设计类型")
    elif type_key == "AI批量":
        type_value = match_prefix(q_type, ["AI 批量文案校对", "AI批量文案校对"], "文案设计类型")
    else:
        raise PlanError("--type 只能是 文案设计 | 仅英文文案校对 | AI批量，实际给了 %r。" % args.type)

    # 🔴 单选值先按**字符串**写；若日后真提交报类型错，改成单元素数组（["选项名"]）。
    fields = {}
    fields[q_name["title"]] = args.name
    fields[q_type["title"]] = type_value
    fields[q_priority["title"]] = match_priority(q_priority, args.priority)
    fields[q_doc["title"]] = args.doc_url
    fields[q_edit["title"]] = match_exact(q_edit, args.edit_open, "是否已开放文档编辑权限")
    fields[q_visibility["title"]] = match_prefix(q_visibility, [args.visibility], "内容上线后可见范围")
    fields[q_line["title"]] = match_exact(q_line, args.product_line, "产品线")
    fields[q_note["title"]] = args.note

    if type_key == "AI批量":
        if not args.ai_req:
            raise PlanError("--type AI批量 必须同时给 --ai-req（表单里「AI 批量文案校对要求」是条件必填项）。")
    if args.ai_req:
        q_ai = pick_question(questions, "AI 批量文案校对要求", contains="批量文案校对要求")
        fields[q_ai["title"]] = args.ai_req

    print("文案校对登记预览（share_token=%s）" % share_token)
    print_table(["字段", "值"], [[k, render(v, 60)] for k, v in fields.items()])

    plan = {"share_token": share_token, "fields": fields,
            "telemetry": {"requirement": args.requirement or strip_copy_review_suffix(args.name),
                          "platform": args.platform}}
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(plan, fh, ensure_ascii=False, indent=2)
        fh.write("\n")
    print("\nplan 已写入：%s" % args.out)

    payload = json.dumps({"fields": fields}, ensure_ascii=False)
    dry = run_lark(["base", "+form-submit", "--share-token", share_token,
                    "--json", payload, "--dry-run", "--as", "user"], raw=True)
    print("\n--dry-run 请求体（未提交）：")
    print(json.dumps(dry.get("data") or dry, ensure_ascii=False, indent=2))
    print("\n确认无误后：python3 %s copy-review-apply %s --yes" % (os.path.basename(__file__), args.out))
    return 0


def cmd_copy_review_apply(args):
    plan = _load_json_file(args.plan)
    share_token = plan["share_token"]
    payload = json.dumps({"fields": plan.get("fields") or {}}, ensure_ascii=False)
    cmd = ["base", "+form-submit", "--share-token", share_token, "--json", payload, "--yes", "--as", "user"]
    if not args.yes:
        print("将执行（加 --yes 才真跑）：")
        print("  lark-cli " + " ".join(cmd) + " --format json")
        return 2
    try:
        result = run_lark(cmd)
    except LarkError as exc:
        print("提交失败，错误全文如下（尤其看「必填字段缺失」点了哪个字段名）：", file=sys.stderr)
        print(str(exc), file=sys.stderr)
        print("\n不重试、不猜填：把缺的字段名补进 plan 再跑。", file=sys.stderr)
        return 1
    print("提交成功。回执：")
    print(json.dumps(result.get("data") or result, ensure_ascii=False, indent=2))
    fallback = ""
    for key, value in (plan.get("fields") or {}).items():
        if "需求名称" in key and isinstance(value, str):
            fallback = strip_copy_review_suffix(value)
            break
    telemetry_after(plan, "登记校对", fallback)
    return 0


# ---------------------------------------------------------------- 使用采集（telemetry）

# 公司「PRD写作kit使用记录」表 · 明细页；固定 5 列 A–E：使用时间 | 使用人 | 需求名称 | 平台 | 模式。
# 🔴 契约全文见 references/11-usage-telemetry.md（行号唯一来源 = csv-get 的 data.current_region
#    尾部行号 N，写到 A<N+1>；取不到 N 就不写，禁止 fallback 到固定行；只在 auth status ok 时记；
#    失败静默、不重试、不回读）。PRD_KIT_TELEMETRY=<spreadsheet_token>:<sheet_id> 是**测试专用**
#    逃生口（正常回合绝不要设，设了就写不进公司表）。
TELEMETRY_SPREADSHEET = "LFvMsXyKAhvW8Utprn4ugtPgs0f"
TELEMETRY_SHEET_ID = "bf6df9"
TELEMETRY_MODES = ("写", "升级", "自检", "建卡", "demo", "登记需求", "登记校对", "登记实验")
TELEMETRY_PLATFORMS = ("claude", "codex", "kiro", "gemini", "antigravity")
TELEMETRY_MANUAL = "——按 references/11-usage-telemetry.md 形态 A/B 手动补一行"


def telemetry_target():
    """表坐标：默认公司表；PRD_KIT_TELEMETRY=<token>:<sheet_id> 可整体顶掉（测试专用）。"""
    env = (os.environ.get("PRD_KIT_TELEMETRY") or "").strip()
    if ":" in env:
        token, _, sheet_id = env.partition(":")
        if token.strip() and sheet_id.strip():
            return token.strip(), sheet_id.strip()
    return TELEMETRY_SPREADSHEET, TELEMETRY_SHEET_ID


def telemetry_run(args):
    """跑一条 lark-cli，**永不抛**：返回 (ok, stdout)。采集是尽力而为的附赠品。"""
    try:
        proc = subprocess.run(["lark-cli"] + list(args), capture_output=True, text=True, timeout=60)
    except Exception:
        return False, ""
    return proc.returncode == 0, proc.stdout or ""


def telemetry_json(text):
    """从 stdout 第一个 `{` 起 raw_decode，尾部噪声不影响解析；失败返回 {}。"""
    idx = (text or "").find("{")
    if idx < 0:
        return {}
    try:
        payload, _ = json.JSONDecoder().raw_decode(text[idx:])
    except ValueError:
        return {}
    return payload if isinstance(payload, dict) else {}


def telemetry_clean(value):
    """五个格通用清洗：英文逗号 / 引号换成中文，换行压成空格（列契约 = 固定 5 列，不许溢出）。"""
    text = "" if value is None else str(value)
    return text.replace(",", "，").replace('"', "”").replace("\r", " ").replace("\n", " ").strip()


def telemetry_region_row(payload):
    """`data.current_region`（形如 "A1:A87"）的尾部行号 N；取不到返回 None。"""
    region = str((payload.get("data") or {}).get("current_region") or "")
    digits = "".join(c for c in region.split(":")[-1] if c.isdigit())
    return int(digits) if digits else None


def telemetry_appended_row(text):
    """旧集 `+append` 回执里挖追加到的行号（拿不到就 None——服务端定位，本就不需要）。"""
    import re as _re
    m = _re.search(r'"(?:updatedRange|updated_range|tableRange|table_range)"\s*:\s*"([^"]+)"', text or "")
    if not m:
        return None
    digits = "".join(c for c in m.group(1).split(":")[-1] if c.isdigit())
    return int(digits) if digits else None


def telemetry_write(requirement, platform, mode):
    """按 `11 §写入契约` 往使用记录表追加一行，返回**一行**状态文本（永不抛、绝不重试）。"""
    if not platform:
        return "使用记录：未写入（缺 --platform）" + TELEMETRY_MANUAL

    ok, out = telemetry_run(["auth", "status"])
    if not ok:
        return "使用记录：未写入（未登录）" + TELEMETRY_MANUAL
    user = ((telemetry_json(out).get("identities") or {}).get("user") or {}).get("userName") or "使用者"

    # 版本探测：新集有 +csv-put，旧集（≤1.0.46）只有 +append，两套都没有就放弃
    _, helptext = telemetry_run(["sheets", "--help"])
    has_csv = "+csv-put" in (helptext or "")
    has_append = "+append" in (helptext or "")
    if not has_csv and not has_append:
        return "使用记录：未写入（本机 sheets 命令集不支持）" + TELEMETRY_MANUAL

    token, sheet_id = telemetry_target()
    row = [telemetry_clean(v) for v in
           (time.strftime("%Y-%m-%d %H:%M"), user, requirement, platform, mode)]

    if has_csv:
        ok, out = telemetry_run(["sheets", "+csv-get", "--spreadsheet-token", token,
                                 "--sheet-id", sheet_id, "--range", "A1:A100000", "--format", "json"])
        last = telemetry_region_row(telemetry_json(out)) if ok else None
        if not last:
            # 🔴 防覆盖护栏：行号取不到就整体跳过，禁止 fallback 到 A2 之类固定行
            return "使用记录：未写入（取不到行号）" + TELEMETRY_MANUAL
        target = last + 1
        csv_text = ",".join('"%s"' % cell for cell in row)
        ok, _ = telemetry_run(["sheets", "+csv-put", "--spreadsheet-token", token,
                               "--sheet-id", sheet_id, "--start-cell", "A%d" % target,
                               "--csv", csv_text, "--format", "json"])
        if not ok:
            return "使用记录：未写入（写入失败）" + TELEMETRY_MANUAL
        return "使用记录：已写入 第%d行（%s · %s）" % (target, row[4], row[2])

    # 旧集 CLI：`+append` 由服务端定位追加点，不需要也拿不到行号（防覆盖天然满足）
    ok, out = telemetry_run(["sheets", "+append", "--spreadsheet-token", token,
                             "--sheet-id", sheet_id, "--range", "A1:E1",
                             "--values", json.dumps([row], ensure_ascii=False), "--format", "json"])
    if not ok:
        return "使用记录：未写入（写入失败）" + TELEMETRY_MANUAL
    appended = telemetry_appended_row(out)
    if appended:
        return "使用记录：已写入 第%d行（%s · %s）" % (appended, row[4], row[2])
    return "使用记录：已写入（服务端追加 · %s · %s）" % (row[4], row[2])


def telemetry_line(requirement, platform, mode):
    """telemetry_write 的防弹外壳：任何异常都退成一行「未写入」，绝不影响主交付。"""
    try:
        return telemetry_write(requirement, platform, mode)
    except Exception:
        return "使用记录：未写入（写入失败）" + TELEMETRY_MANUAL


def telemetry_after(plan, mode, fallback_requirement=""):
    """*-apply 成功后的自动采集：需求名 / 平台取 plan 的 telemetry 块（plan-* 时写入）。"""
    tel = plan.get("telemetry") or {}
    requirement = tel.get("requirement") or fallback_requirement
    print(telemetry_line(requirement, tel.get("platform") or "", mode))


def strip_copy_review_suffix(name):
    """copy-review 的采集需求名默认值：`--name` 去掉「词条文案设计与校对」后缀。"""
    suffix = "词条文案设计与校对"
    text = (name or "").strip()
    if text.endswith(suffix):
        text = text[: -len(suffix)].strip()
    return text


def cmd_telemetry(args):
    """使用采集：追加一行使用记录。**永远退出码 0、只打印一行状态**，不在对话里多说。"""
    print(telemetry_line(args.requirement, args.platform, args.mode))
    return 0


# ---------------------------------------------------------------- CLI


def build_parser():
    parser = argparse.ArgumentParser(
        prog="register.py",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description="需求收集表 / 文案校对登记表 / 通用登记表 登记脚本（流水线 S3 / S4 / S6）。只调本机 lark-cli，不碰密钥。\n"
                    "另有 telemetry 子命令（使用采集，见 references/11-usage-telemetry.md §形态 C）：\n"
                    "  python3 register.py telemetry --requirement \"<需求名>\" --platform <平台> --mode <模式>\n"
                    "  永远退出码 0、只打印一行「使用记录：已写入 第N行 / 未写入（原因）」；\n"
                    "  demand-apply / copy-review-apply / row-apply 写入成功后各自动记一行\n"
                    "  （登记需求 / 登记校对 / 登记实验）。",
        epilog="表格 / 表单坐标来自 references/12-library-manifest.json（sources[0] / forms.copy_review）；\n"
               "通用登记表（S6 AB 实验表等）坐标与规则来自 forms.<key>（kind=base_table）；\n"
               "用户级覆盖 ~/.prd-authoring-kit/library.json；测试用 PRD_KIT_LIBRARY=<json 路径> 顶掉两者。",
    )
    sub = parser.add_subparsers(dest="command")

    p = sub.add_parser("whoami", help="打印 lark-cli 登录人「姓名 | open_id」（登记人默认值）")
    p.set_defaults(func=cmd_whoami)

    p = sub.add_parser("demand-find", help="需求收集表里找既有行（防重复登记）",
                       description="关键词依次试：PRD 链接最后一段 token → --name → Jira KEY；\n"
                                   "在 PRD / 需求描述 / Jira单号/链接 三列里搜。\n"
                                   "--prd / --name / --jira 至少给一个（先建卡后写 PRD 时用 --jira / --name 查）。",
                       formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--prd", default="", help="PRD 飞书链接（可选）")
    p.add_argument("--name", default="", help="需求名关键词（PRD token 没命中时的第二次尝试）")
    p.add_argument("--jira", default="", help="Jira KEY（如 WEB-20139；多张用逗号分隔，取第一张当关键词）")
    p.set_defaults(func=cmd_demand_find)

    p = sub.add_parser(
        "demand-plan", help="出需求收集表登记预览 + 写 plan json（不写表）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description="五项必填：--name --module --priority --iteration --progress；**--prd 可选**。\n"
                    "先建卡后写 PRD 的需求照常登记：--prd 留空 → PRD 格留空，匹配既有行靠 --name / --jira，\n"
                    "PRD 事后用 `demand-update <record_id> --set PRD=<url> --yes` 补。\n"
                    "单选值在线校验（+field-search-options，必须与选项名完全相等；选项会变，脚本不内置枚举）。\n"
                    "既有行恰好 1 条 → update；多条 → 要 --record-id；0 条 → create。\n"
                    "字段映射：需求描述=--name / 产品模块=--module / PRD=--prd（纯 URL 字符串）/ "
                    "Jira单号/链接=--jira（写成 [KEY](https://jira.mxcb.xyz/browse/KEY)，多张换行）/ "
                    "产品经理=--pm、需求提出方=--proposer（user 字段写 [{\"id\":\"ou_…\"}]，默认本人）/ "
                    "优先级=--priority、迭代版本=--iteration、进展=--progress、需求来源部门=--source-dept"
                    "（select 字段写单元素数组 [\"选项名\"]）/ 需求价值=--value / BRD/MRD=--brd / 备注=--note。")
    p.add_argument("--prd", default="", help="PRD 飞书链接（可选；先建卡后写 PRD 时留空，事后 demand-update 补）")
    p.add_argument("--name", default="", help="【必填】需求描述：短需求名 ≤20 字（默认取 PRD 文档标题去掉【端】前缀与「PRD」字样；不是功能清单、不是一段话）")
    p.add_argument("--allow-long", action="store_true",
                   help="需求描述超过 40 字也写 plan（默认：预览标「⚠ 过长」、退出码 2、不写 plan）")
    p.add_argument("--module", default="", help="【必填】产品模块选项名（如 App / Web/H5）")
    p.add_argument("--priority", default="", help="【必填】优先级选项名（产品定，别默认 P1）")
    p.add_argument("--iteration", default="", help="【必填】迭代版本选项名（产品定，别默认「需求池」）")
    p.add_argument("--progress", default="", help="【必填】进展选项名（刚登记 = 「0. 未开始」，产品从线上选项里点）")
    p.add_argument("--jira", default="", help="Jira KEY，多张用逗号分隔（WEB-19856,APP-37283）")
    p.add_argument("--value", default="", help="需求价值一句话")
    p.add_argument("--source-dept", default="", help="需求来源部门选项名")
    p.add_argument("--brd", default="", help="BRD/MRD 链接")
    p.add_argument("--note", default="", help="备注")
    p.add_argument("--proposer", default="", help="需求提出方 open_id（默认 = lark-cli 登录本人）")
    p.add_argument("--pm", default="", help="产品经理 open_id（默认 = lark-cli 登录本人）")
    p.add_argument("--record-id", default="", help="强制更新该行（命中多行时必给）")
    p.add_argument("--requirement", default="", help="采集用需求名（默认 = --name；跨技能去重键，见 11 §需求名）")
    p.add_argument("--platform", default=os.environ.get("PRD_KIT_PLATFORM", ""),
                   help="采集用平台 claude|codex|kiro|gemini|antigravity（默认读环境变量 PRD_KIT_PLATFORM）")
    p.add_argument("--out", default="./demand-plan.json", help="plan 输出路径（默认 ./demand-plan.json）")
    p.set_defaults(func=cmd_demand_plan)

    p = sub.add_parser("demand-apply", help="按 plan 写需求收集表（要 --yes）",
                       description="create → +record-batch-create；update → 先 +record-get 读回、"
                                   "只填当前为空的字段（--overwrite 才覆盖非空），再 +record-upsert；写完自动回读打印。\n"
                                   "写入成功后自动记一行使用记录（模式 登记需求，需求名 / 平台取 plan 的 telemetry 块）。")
    p.add_argument("plan", help="demand-plan 产出的 plan json")
    p.add_argument("--yes", action="store_true", help="确认执行；不给只打印将执行的命令并以退出码 2 结束")
    p.add_argument("--overwrite", action="store_true", help="既有行非空格也覆盖（默认只补空格）")
    p.set_defaults(func=cmd_demand_apply)

    p = sub.add_parser(
        "demand-update", help="改需求收集表的某几格（不整行重写；要 --yes）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description="按字段类型自动转写入形态：文本 / 链接直接写；单选在线校验（同 demand-plan，不等则报候选）；\n"
                    "数字转数字；`产品经理` / `需求提出方` 收 open_id（多人逗号分隔）。\n"
                    "**值留空 = 清空该格**（`--set 备注=`）。无 --yes 只打印将改的格并以退出码 2 结束；\n"
                    "写后 `+record-get` 回读并打印改后值。典型用法：产品当场改优先级 / 迭代版本 / 进展，\n"
                    "或先建卡后写 PRD 时事后补 `--set PRD=<url>`。")
    p.add_argument("record_id", help="要改的行 record_id（先用 demand-find 查）")
    p.add_argument("--set", action="append", default=None, metavar="字段=值",
                   help="要改的格，可重复；值留空 = 清空该格")
    p.add_argument("--yes", action="store_true", help="确认执行；不给只打印将改的格并以退出码 2 结束")
    p.set_defaults(func=cmd_demand_update)

    p = sub.add_parser(
        "row-plan", help="通用行登记预览 + 写 plan json（manifest forms.<key> 驱动，如 S6 AB 实验表）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description="manifest `forms.<key>`（kind=base_table）驱动，服务 AB 实验管理表与以后任何登记表：\n"
                    "  inherit_from_reference —— **只有这些字段**从 --reference 指的参考行继承，其它一律不抄；\n"
                    "  confirm —— 必须由产品拍板，没给值就打「？」、退出码 2、不写 plan；\n"
                    "  fixed —— 固定值，支持 {whoami.name} / {whoami.first_lower}（登录人姓名首个词小写）；\n"
                    "  leave_empty —— 约定留空（apply 后被表默认值填上会清成 null）；\n"
                    "  rule —— 一句人话，预览时原样打出；telemetry_mode —— apply 成功后记的模式。\n"
                    "叠加顺序：参考行继承 → --set → fixed；单选值在线校验（+field-search-options，不等则报候选）。")
    p.add_argument("--form", required=True, help="manifest forms 的键（如 ab_experiment）")
    p.add_argument("--reference", default="", help="参考行：记录链接（带 ?record=rec…）或 record_id")
    p.add_argument("--set", action="append", default=None, metavar="字段=值",
                   help="要写的格，可重复；值留空 = 不写该格")
    p.add_argument("--requirement", default="",
                   help="采集用需求名（默认 = manifest from_prd 里第一个有值的格；见 11 §需求名）")
    p.add_argument("--platform", default=os.environ.get("PRD_KIT_PLATFORM", ""),
                   help="采集用平台 claude|codex|kiro|gemini|antigravity（默认读环境变量 PRD_KIT_PLATFORM）")
    p.add_argument("--out", default="./row-plan.json", help="plan 输出路径（默认 ./row-plan.json）")
    p.set_defaults(func=cmd_row_plan)

    p = sub.add_parser("row-apply", help="按 plan 往登记表建一行（要 --yes）",
                       formatter_class=argparse.RawDescriptionHelpFormatter,
                       description="+record-batch-create → +record-get 回读 → **leave_empty 里回读非空的格\n"
                                   "（= 表默认值回填）+record-batch-update 置 null → 再回读验空** → 逐格 diff 打印。\n"
                                   "成功后自动记一行使用记录（模式取 plan 的 telemetry.mode = manifest telemetry_mode）。")
    p.add_argument("plan", help="row-plan 产出的 plan json")
    p.add_argument("--yes", action="store_true", help="确认执行；不给只打印将执行的命令并以退出码 2 结束")
    p.set_defaults(func=cmd_row_apply)

    p = sub.add_parser(
        "copy-review-plan", help="出文案校对登记表预览 + 写 plan json + 跑一次 --dry-run（不提交）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description="字段映射：需求名称=--name / 文案设计类型=--type（前缀匹配选项）/ 优先级=--priority"
                    "（取选项名首个空格·全角括号·半角括号之前的 token 完全相等，P1 ≠ P1+）/ "
                    "需要处理的文档链接=--doc-url / 是否已开放文档编辑权限=--edit-open / "
                    "内容上线后可见范围=--visibility（前缀匹配 对外 / 仅内部）/ 产品线=--product-line（完全相等）/ "
                    "备注（题目全名带括号说明）=--note / AI 批量文案校对要求=--ai-req（--type AI批量 时必填）。\n"
                    "🔴 单选值先按字符串写；若日后真提交报类型错，改成单元素数组 [\"选项名\"]。")
    p.add_argument("--doc-url", required=True, help="需要处理的文档链接（词条表 sheet 或 PRD）")
    p.add_argument("--name", required=True, help="需求名称，如「<PRD 名>词条文案设计与校对」")
    p.add_argument("--type", required=True, help="文案设计 | 仅英文文案校对 | AI批量")
    p.add_argument("--priority", required=True, help="P0 | P1+ | P1 | P2 | P3（必须先问产品）")
    p.add_argument("--product-line", required=True, help="产品线选项名（如 App产品 / Web产品-AI）")
    p.add_argument("--visibility", required=True, help="对外 | 仅内部")
    p.add_argument("--edit-open", required=True, help="是 | 否（文档是否已开放编辑权限）")
    p.add_argument("--note", required=True, help="备注：本轮新增/改动行号或条数 + 特殊要求 + PRD 链接")
    p.add_argument("--ai-req", default="", help="AI 批量文案校对要求（--type AI批量 时必填）")
    p.add_argument("--requirement", default="",
                   help="采集用需求名（默认 = --name 去掉「词条文案设计与校对」后缀；见 11 §需求名）")
    p.add_argument("--platform", default=os.environ.get("PRD_KIT_PLATFORM", ""),
                   help="采集用平台 claude|codex|kiro|gemini|antigravity（默认读环境变量 PRD_KIT_PLATFORM）")
    p.add_argument("--out", default="./copy-review-plan.json", help="plan 输出路径（默认 ./copy-review-plan.json）")
    p.set_defaults(func=cmd_copy_review_plan)

    p = sub.add_parser("copy-review-apply", help="按 plan 提交文案校对登记表（要 --yes）",
                       description="失败时把错误全文打印（尤其「必填字段缺失」的字段名）并退出码 1，不重试、不猜填。\n"
                                   "提交成功后自动记一行使用记录（模式 登记校对，需求名 / 平台取 plan 的 telemetry 块）。")
    p.add_argument("plan", help="copy-review-plan 产出的 plan json")
    p.add_argument("--yes", action="store_true", help="确认提交；不给只打印将执行的命令并以退出码 2 结束")
    p.set_defaults(func=cmd_copy_review_apply)

    p = sub.add_parser(
        "telemetry", help="使用采集：往使用记录表追加一行（永远退出码 0，只打印一行状态）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description="按 references/11-usage-telemetry.md §写入契约 追加一行\n"
                    "「使用时间 | 使用人 | 需求名称 | 平台 | 模式」（固定 5 列 A–E，时间不带秒）：\n"
                    "行号唯一来源 = +csv-get 的 data.current_region 尾部行号 N → 写 A<N+1>；取不到就不写\n"
                    "（🔴 禁止 fallback 到固定行）；旧集 CLI（只有 +append）走服务端追加；\n"
                    "只在 lark-cli auth status ok 时记，使用人 = identities.user.userName（取不到写「使用者」）。\n"
                    "🔴 失败静默、不重试、不回读、不在对话里多说；看到「未写入」才按 11 形态 A / B 手动补一行。\n"
                    "建卡 / 登记需求 / 登记校对 / 登记实验 四种由 jira_cards.py apply、register.py *-apply 成功后自动调用。")
    p.add_argument("--requirement", required=True, help="需求名称（跨技能统一去重键，取法见 11 §需求名）")
    p.add_argument("--platform", default="", choices=list(TELEMETRY_PLATFORMS),
                   help="平台：claude|codex|kiro|gemini|antigravity（不给 = 未写入（缺 --platform））")
    p.add_argument("--mode", required=True, choices=list(TELEMETRY_MODES),
                   help="模式：写|升级|自检|建卡|demo|登记需求|登记校对|登记实验")
    p.set_defaults(func=cmd_telemetry)

    return parser


def main(argv):
    parser = build_parser()
    args = parser.parse_args(argv)
    if not getattr(args, "func", None):
        parser.print_help()
        return 2
    try:
        return args.func(args)
    except (LarkError, PlanError) as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
