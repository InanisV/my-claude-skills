#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
data-request-kit 执行器 —— 数分需求表单（Data Request Form）的机械活儿都在这里：

  contract               读线上表单契约（字段标题/类型/必填/选项），对照本地快照报漂移
  whoami                 当前 lark-cli 用户（= 默认需求发起人）
  user <姓名>            按姓名找 open_id / 单聊 chat_id
  chat <人名|ou_|oc_>    把和某人的单聊按时间正序压平打印（图片消息附下载命令）
  precedent              需求池先例：发起人历史单（推默认值）+ 关键词相似单（含被取消的）
  validate <spec.json>   按 spec 生成提交 payload，本地 + 线上契约双重校验，打印草稿表
  submit <spec.json>     提交；默认 dry-run，--yes 才真提交；提交后回查 record_id
  probe <字段标题> <候选…> 安全探测被权限锁住字段的合法选项名（结构上不可能误提交）

零依赖：python3 标准库 + lark-cli。所有网络请求都经 lark-cli，本脚本不接触任何凭据。
可用环境变量覆盖：LARK_CLI（可执行文件路径）、DR_SHARE_TOKEN、DR_BASE_TOKEN、DR_TABLE_ID。
"""
import argparse
import datetime as _dt
import difflib
import json
import os
import re
import shutil
import subprocess
import sys

# ---------------------------------------------------------------------------
# 配置：数分需求表单的坐标。2.1 起不随公开包分发：环境变量 DR_SHARE_TOKEN / DR_BASE_TOKEN / DR_TABLE_ID
# → 公司配置 ~/.prd-authoring-kit/library.json 的 forms.data_request（`npx pm-ai-kit config <飞书配置文档链接>` 导入）
# → 都没有就报错指路。坐标是资源定位符不是凭据，但不回显进对话。
# ---------------------------------------------------------------------------
def _load_company_config():
    """主 kit `scripts/company_config.py` 的 load_company_config；找不到模块 / 读失败 → None。
    依次试：skills 根同级 `prd-authoring-kit/scripts`、仓库根 `scripts`、~/.prd-authoring-kit、~/.claude/skills、~/.agents/skills。"""
    here = os.path.dirname(os.path.realpath(__file__))
    kit = os.path.dirname(here); siblings = os.path.dirname(kit); repo = os.path.dirname(siblings)
    for d in (os.path.join(siblings, "prd-authoring-kit", "scripts"), os.path.join(repo, "scripts"),
              os.path.expanduser("~/.prd-authoring-kit/scripts"),
              os.path.expanduser("~/.claude/skills/prd-authoring-kit/scripts"),
              os.path.expanduser("~/.agents/skills/prd-authoring-kit/scripts")):
        if os.path.isfile(os.path.join(d, "company_config.py")):
            if d not in sys.path:
                sys.path.insert(0, d)
            break
    try:
        from company_config import load_company_config
        cfg = load_company_config()
    except Exception:
        return None
    return cfg if isinstance(cfg, dict) else None


def _form_coords():
    env = (os.environ.get("DR_SHARE_TOKEN"), os.environ.get("DR_BASE_TOKEN"), os.environ.get("DR_TABLE_ID"))
    if all(env):
        return env
    f = ((_load_company_config() or {}).get("forms") or {}).get("data_request") or {}
    vals = (env[0] or f.get("share_token"), env[1] or f.get("base_token"), env[2] or f.get("table_id"))
    if all(vals) and all(re.fullmatch(r"[A-Za-z0-9_-]{1,64}", str(v)) for v in vals):
        return tuple(str(v) for v in vals)
    sys.stderr.write("ERROR: 没有数分需求表单坐标：跑一次 npx pm-ai-kit config <飞书配置文档链接>（链接在群公告），"
                     "或设环境变量 DR_SHARE_TOKEN / DR_BASE_TOKEN / DR_TABLE_ID。\n")
    sys.exit(2)


SHARE_TOKEN, BASE_TOKEN, TABLE_ID = _form_coords()

# spec 键 -> 表单字段 id。字段 id 稳定，标题会被人改；提交时用线上契约里的当前标题。
FIELD_IDS = {
    "title": "fldbI4wJwY",          # 需求标题 Summary
    "background": "fld8NmczHW",     # 需求背景 Background
    "goal_category": "fldj3vLBAv",  # 需求目标分类（被字段权限锁住）
    "goals": "fldR4Fk78B",          # 需求要达成的目标 Goals
    "description": "fldoFjdKhY",    # 需求描述 Description
    "priority": "fldMmaRIo1",       # 需求优先级 Priority
    "type": "fldBhWIowq",           # 需求类型 Requirement Type
    "requester": "fldLMvAnOu",      # 需求发起人 Requestor
    "business_line": "fldOLY8apP",  # 业务线 Business Line
    "analysts": "flds2jDgn4",       # 数分对接人 Data Analysis（多人）
    "expected_date": "fldZ8OSZqj",  # 预期交付时间 Expected delivery time
    "delivery_form": "fldYyg2Hkr",  # 交付形态（被字段权限锁住）
    "attachments": "fldxg6qyC2",    # 附件 Attachments
}
SPEC_LABELS = {
    "title": "需求标题", "background": "需求背景", "goal_category": "需求目标分类",
    "goals": "需求目标", "description": "需求描述", "priority": "优先级", "type": "需求类型",
    "requester": "需求发起人", "business_line": "业务线", "analysts": "数分对接人",
    "expected_date": "预期交付时间", "delivery_form": "交付形态", "attachments": "附件",
}

# 被 Base 字段权限锁住、API 读不到选项的字段：最后一次人工核验到的选项名。
# 线上可能已改；不完整的标 complete=False。提交报 option not found 就用 probe 重新探。
LOCKED_KNOWN_OPTIONS = {
    "fldj3vLBAv": {"verified": "2026-08-27", "complete": True,
                   "options": ["工作汇报", "定期监控", "长期专项", "短期分析", "探索性分析"]},
    "fldYyg2Hkr": {"verified": "2026-09-02", "complete": True,
                   "options": ["看板", "报告（含落地建议）", "模板", "表格"]},
}

# 需求池里用来核验 / 找先例的表字段名（表字段名 ≠ 表单问题标题）
TBL = {
    "title": "需求标题", "type": "需求类型", "line": "业务线", "analysts": "数分对接人",
    "priority": "优先级", "submitted": "提交时间", "status": "状态", "requester": "需求发起人",
    "background": "需求背景", "goals": "需求目标", "description": "需求描述",
    "expected": "预期交付时间",
}

ERROR_HINTS = [
    ("unknown field name", "提交 payload 的 key 必须是「表单问题标题全称」（不是字段 id、也不是表字段名）。"
                           "脚本按字段 id 映射到线上标题，出现这个说明契约漂移了：先跑 contract 看。"),
    ("expected option name string", "单选字段要传纯字符串，不是数组（这和 +record-batch-create 的规范相反）。"),
    ("unsupported datetime format", "日期必须是 yyyy-MM-dd HH:mm:ss，脚本已自动补 00:00:00；检查 spec 的 expected_date。"),
    ("must required", "有必填项没填。spec 里对应的键为空，或线上新增了必填字段（用 spec.extra 补）。"),
    ("not found in field options", "选项名不存在。注意首尾空格（如「发奖需求 Award Request 」末尾有空格）和中英文全称；"
                                    "被锁字段用 probe 重新探。"),
    ("missing_scope", "缺 scope。按 lark-shared 的 device-code 流程补授权，别自己猜命令。"),
    ("needs_refresh", "用户 token 需要刷新，通常下一次调用自动刷新，重试一次即可。"),
]


class CliError(Exception):
    pass


def die(msg, code=1):
    print("❌ " + msg, file=sys.stderr)
    sys.exit(code)


# ---------------------------------------------------------------------------
# lark-cli 调用
# ---------------------------------------------------------------------------
def lark_cli():
    cands = [
        os.environ.get("LARK_CLI"),
        shutil.which("lark-cli"),
        os.path.expanduser("~/.npm-global/lib/node_modules/@larksuite/cli/bin/lark-cli"),
        "/usr/local/lib/node_modules/@larksuite/cli/bin/lark-cli",
        "/opt/homebrew/lib/node_modules/@larksuite/cli/bin/lark-cli",
    ]
    for c in cands:
        # PATH 里的 shim 可能是指向 scripts/run.js 的死软链；isfile 会跟随软链，坏链返回 False
        if c and os.path.isfile(c) and os.access(c, os.X_OK):
            return c
    try:
        root = subprocess.run(["npm", "root", "-g"], capture_output=True, text=True, timeout=20).stdout.strip()
        p = os.path.join(root, "@larksuite/cli/bin/lark-cli")
        if os.path.isfile(p):
            return p
    except Exception:
        pass
    die("找不到 lark-cli。修复：npm i -g @larksuite/cli@latest ；或设置 LARK_CLI=<可执行文件路径>")


def run(args, identity=True, timeout=180):
    cmd = [lark_cli()] + list(args)
    if identity:
        cmd += ["--as", "user"]
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        raise CliError("lark-cli 超时：" + " ".join(args[:3]))
    # 成功时 JSON 在 stdout；API 报错（exit=1）时 JSON 在 stderr —— 两边都找
    out = p.stdout or ""
    if "{" not in out:
        out = p.stderr or ""
    i = out.find("{")
    if i < 0:
        raise CliError("lark-cli 没有 JSON 输出（exit=%s）：%s" % (p.returncode, (p.stdout or p.stderr)[:500]))
    try:
        return json.loads(out[i:])
    except json.JSONDecodeError:
        # 输出里可能夹着 warning 行；取最后一个顶层 JSON
        dec = json.JSONDecoder()
        pos = i
        last = None
        while pos < len(out):
            try:
                obj, end = dec.raw_decode(out, pos)
                last = obj
                pos = end
            except json.JSONDecodeError:
                pos = out.find("{", pos + 1)
                if pos < 0:
                    break
        if last is None:
            raise CliError("lark-cli 输出不是 JSON：" + out[:500])
        return last


def explain(err):
    msg = json.dumps(err, ensure_ascii=False) if not isinstance(err, str) else err
    hints = [h for k, h in ERROR_HINTS if k in msg]
    return msg + ("\n   ↳ " + "\n   ↳ ".join(hints) if hints else "")


def ok_or_die(res, what):
    if not res.get("ok"):
        die("%s 失败：%s" % (what, explain(res.get("error", res))))
    return res


# ---------------------------------------------------------------------------
# contract / whoami / user
# ---------------------------------------------------------------------------
def fetch_contract():
    res = ok_or_die(run(["base", "+form-detail", "--share-token", SHARE_TOKEN]), "读取表单契约")
    data = res["data"]
    data.setdefault("questions", [])
    return data


def cmd_contract(a):
    c = fetch_contract()
    print("表单：%s   base_token=%s   快照日期：2026-08-27（线上为准）" % (c.get("name"), c.get("base_token")))
    print()
    print("| 字段 id | 表单问题标题（提交 key） | 类型 | 必填 | 选项 / 备注 |")
    print("|---|---|---|---|---|")
    known_ids = set(FIELD_IDS.values())
    for q in c["questions"]:
        t = q.get("type")
        note = ""
        if t == "select":
            note = " / ".join(o["name"] for o in q.get("options", []))
            if q.get("multiple"):
                note = "[多选] " + note
        elif t == "user":
            note = "多人" if q.get("multiple") else "单人"
        elif t == "datetime":
            note = "写 yyyy-MM-dd（脚本补 00:00:00）"
        elif t == "not_support":
            k = LOCKED_KNOWN_OPTIONS.get(q["id"])
            note = ("🔒 权限锁字段，API 读不到选项；已知：%s（%s 核验%s）" %
                    (" / ".join(k["options"]), k["verified"], "" if k["complete"] else "，可能不全")) if k \
                else "🔒 权限锁字段，选项未知 → 用 probe 探或问用户"
        drift = "" if q["id"] in known_ids else "  ⚠️ 脚本不认识的新字段（用 spec.extra 填）"
        print("| %s | %s | %s | %s | %s%s |" % (q["id"], q.get("title"), t, "是" if q.get("required") else "否", note, drift))
    live_ids = {q["id"] for q in c["questions"]}
    gone = [k for k, v in FIELD_IDS.items() if v not in live_ids]
    if gone:
        print("\n⚠️ 本地快照里有、线上已没有的字段：%s（spec 里这些键会被忽略）" % ", ".join(gone))
    new_required = [q for q in c["questions"] if q["id"] not in known_ids and q.get("required")]
    if new_required:
        print("\n⚠️ 线上新增必填字段，spec 必须用 extra 补：%s" % ", ".join(q["title"] for q in new_required))
    if a.json:
        print(json.dumps(c, ensure_ascii=False, indent=2))


def whoami():
    res = run(["auth", "status"], identity=False)
    u = (res.get("identities") or {}).get("user") or {}
    if not u.get("openId"):
        die("lark-cli 没有可用的用户身份：" + json.dumps(u, ensure_ascii=False)[:300])
    return u["openId"], u.get("userName", "")


def cmd_whoami(a):
    oid, name = whoami()
    print("%s  %s" % (oid, name))
    print("（默认需求发起人；lark-cli 可执行文件：%s）" % lark_cli())


def search_user(query):
    res = ok_or_die(run(["contact", "+search-user", "--query", query]), "通讯录搜索")
    return res["data"].get("users", [])


def cmd_user(a):
    users = search_user(a.name)
    if not users:
        print("没找到：" + a.name)
        return
    for u in users:
        print("%s | %s | %s | 单聊 chat_id=%s | 聊过=%s" % (
            u.get("open_id"), u.get("localized_name"), u.get("department"),
            u.get("p2p_chat_id") or "-", u.get("has_chatted")))


# ---------------------------------------------------------------------------
# chat
# ---------------------------------------------------------------------------
def _local_iso(date_str, end=False):
    d = _dt.datetime.strptime(date_str, "%Y-%m-%d")
    if end:
        d = d + _dt.timedelta(days=1) - _dt.timedelta(seconds=1)
    return d.astimezone().isoformat()


def cmd_chat(a):
    who = a.who
    args = ["im", "+chat-messages-list", "--order", "desc", "--page-all", "--page-limit", str(a.pages),
            "--page-size", "50", "--no-reactions", "--format", "json"]
    if who.startswith("oc_"):
        args += ["--chat-id", who]
    elif who.startswith("ou_"):
        args += ["--user-id", who]
    else:
        users = search_user(who)
        if len(users) != 1:
            print("「%s」匹配到 %d 个人，请用 open_id 或 chat_id 指定：" % (who, len(users)))
            for u in users:
                print("  %s | %s | %s | chat=%s" % (u.get("open_id"), u.get("localized_name"),
                                                    u.get("department"), u.get("p2p_chat_id") or "-"))
            sys.exit(2)
        u = users[0]
        if u.get("p2p_chat_id"):
            args += ["--chat-id", u["p2p_chat_id"]]
        else:
            args += ["--user-id", u["open_id"]]
        print("# 对象：%s（%s）" % (u.get("localized_name"), u.get("department")))
    if a.since:
        args += ["--start", _local_iso(a.since)]
    if a.until:
        args += ["--end", _local_iso(a.until, end=True)]
    res = ok_or_die(run(args), "拉聊天记录")
    msgs = res["data"].get("messages", [])
    msgs.sort(key=lambda m: (m.get("create_time") or "", m.get("message_position") or ""))
    print("# 共 %d 条（时间正序；has_more=%s，不够就加 --pages 或 --since）" % (len(msgs), res["data"].get("has_more")))
    for m in msgs:
        s = (m.get("sender") or {}).get("name") or (m.get("sender") or {}).get("id") or "system"
        ty = m.get("msg_type")
        c = (m.get("content") or "").replace("\n", " / ")
        line = "%s | %s | %s" % (m.get("create_time"), s, c if ty == "text" else "[%s] %s" % (ty, c))
        if ty in ("image", "file", "video", "audio"):
            key = c[c.find(":") + 1:].strip(" ]") if ":" in c else ""
            line += ("\n      ↳ 下载后用 Read 看：lark-cli im +messages-resources-download --message-id %s --file-key %s --type %s --as user"
                     % (m.get("message_id"), key, ty))
        print(line)


# ---------------------------------------------------------------------------
# precedent
# ---------------------------------------------------------------------------
def _matrix(res):
    d = res.get("data", {})
    rows = d.get("data") or []
    ids = d.get("field_id_list") or []
    return rows, ids


def _cell(v):
    if isinstance(v, list):
        return ", ".join((x.get("name") or x.get("id")) if isinstance(x, dict) else str(x) for x in v)
    return "" if v is None else str(v)


def cmd_precedent(a):
    rid = a.requester
    if not rid and not a.no_requester:
        rid, _ = whoami()
    fields = [TBL["title"], TBL["type"], TBL["line"], TBL["analysts"], TBL["priority"],
              TBL["submitted"], TBL["status"], TBL["expected"]]
    if a.full:
        fields += [TBL["background"], TBL["goals"], TBL["description"]]
    if rid:
        flt = {"logic": "and", "conditions": [[TBL["requester"], "contains", [{"id": rid}]]]}
        args = ["base", "+record-list", "--base-token", BASE_TOKEN, "--table-id", TABLE_ID,
                "--filter-json", json.dumps(flt, ensure_ascii=False),
                "--sort-json", json.dumps([{"field": TBL["submitted"], "desc": True}]),
                "--limit", str(a.limit), "--format", "json"]
        for f in fields:
            args += ["--field-id", f]
        res = ok_or_die(run(args), "读发起人先例")
        rows, _ = _matrix(res)
        print("## 发起人 %s 最近 %d 条（共取 %d）" % (rid, a.limit, len(rows)))
        _print_rows(rows, fields)
        _print_defaults(rows, fields)
    if a.keyword:
        args = ["base", "+record-search", "--base-token", BASE_TOKEN, "--table-id", TABLE_ID,
                "--keyword", a.keyword, "--search-field", TBL["title"], "--search-field", TBL["description"],
                "--limit", str(a.limit), "--format", "json"]
        for f in fields + [TBL["requester"]]:
            args += ["--field-id", f]
        res = ok_or_die(run(args), "关键词搜先例")
        rows, _ = _matrix(res)
        print("\n## 关键词「%s」相关（所有人，%d 条）" % (a.keyword, len(rows)))
        _print_rows(rows, fields + [TBL["requester"]])
        bad = [r for r in rows if any(s in _cell(r[fields.index(TBL["status"])]) for s in ("取消", "暂停", "不通过"))]
        if bad:
            print("\n⚠️ 有 %d 条同主题历史单被取消/暂停/评审不通过 —— 提新单前先弄清楚为什么（口径没对齐？重复？），别只当作参考格式。" % len(bad))


def _print_rows(rows, fields):
    if not rows:
        print("（无）")
        return
    print("| " + " | ".join(fields) + " |")
    print("|" + "---|" * len(fields))
    for r in rows:
        print("| " + " | ".join(_cell(v).replace("\n", " / ")[:160] for v in r) + " |")


def _print_defaults(rows, fields):
    if not rows:
        return
    from collections import Counter
    out = []
    for name in (TBL["line"], TBL["analysts"], TBL["priority"], TBL["type"]):
        idx = fields.index(name)
        cnt = Counter(_cell(r[idx]) for r in rows if _cell(r[idx]))
        if cnt:
            top, n = cnt.most_common(1)[0]
            out.append("%s=%s（%d/%d）" % (name, top, n, len(rows)))
    print("\n先例默认值候选（这是「这个人过去怎么填」，不是「这次该怎么填」，必须进确认轮）：\n  " + "；".join(out))


# ---------------------------------------------------------------------------
# validate / submit
# ---------------------------------------------------------------------------
def load_spec(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def match_option(val, names):
    if val in names:
        return val
    sv = str(val).strip()
    for n in names:
        if n.strip() == sv:
            return n
    # 允许只写中文前缀（「取数需求」→「取数需求 Ad-hoc Data Request」），但必须唯一
    pref = [n for n in names if n.strip().startswith(sv) or sv.startswith(n.strip())]
    if len(pref) == 1:
        return pref[0]
    return None


def suggest(val, names):
    s = difflib.get_close_matches(str(val), names, n=2, cutoff=0.3)
    return ("（你是不是想写：%s）" % " / ".join(s)) if s else ""


def norm_user(v):
    if isinstance(v, dict):
        v = v.get("id") or v.get("open_id")
    v = str(v or "").strip()
    if not v.startswith("ou_"):
        raise ValueError("人员字段要 open_id（ou_ 开头），用 `dr.py user <姓名>` 查：%r" % v)
    return v


def user_label(v):
    if isinstance(v, dict) and v.get("name"):
        return "%s(%s)" % (v["name"], (v.get("id") or v.get("open_id") or "")[:10] + "…")
    return str(v)


def norm_dt(v):
    v = str(v).strip().replace("/", "-")
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            d = _dt.datetime.strptime(v, fmt)
            return d.strftime("%Y-%m-%d %H:%M:%S"), d
        except ValueError:
            continue
    raise ValueError("日期写 YYYY-MM-DD：%r" % v)


def build_payload(spec, contract, allow_unknown=False):
    q_by_id = {q["id"]: q for q in contract["questions"]}
    fields, attachments, problems, warnings, rows = {}, {}, [], [], []
    covered = set()
    if not spec.get("requester"):
        oid, uname = whoami()
        spec["requester"] = {"id": oid, "name": uname}
        warnings.append("requester 未填，已用当前 lark-cli 用户 %s" % uname)
    for key, fid in FIELD_IDS.items():
        q = q_by_id.get(fid)
        val = spec.get(key)
        empty = val in (None, "", [], {})
        if q is None:
            if not empty:
                warnings.append("字段 %s（%s）已不在线上表单，忽略其值" % (SPEC_LABELS[key], fid))
            continue
        covered.add(fid)
        title, qtype, required = q.get("title"), q.get("type"), q.get("required", False)
        if empty:
            if required:
                problems.append("必填缺失：%s（spec 键 %s）" % (title, key))
            continue
        try:
            if key == "attachments":
                attachments[title] = [str(x) for x in (val if isinstance(val, list) else [val])]
                rows.append((SPEC_LABELS[key], ", ".join(attachments[title])))
                continue
            if qtype == "text":
                fields[title] = str(val).strip()
            elif qtype == "select":
                names = [o["name"] for o in q.get("options", [])]
                if q.get("multiple"):
                    vals = val if isinstance(val, list) else [val]
                    ms = [match_option(x, names) for x in vals]
                    if None in ms:
                        problems.append("%s：选项不存在 %s。可选：%s" % (title, [x for x, m in zip(vals, ms) if m is None], names))
                        continue
                    fields[title] = ms
                    warnings.append("%s 是多选，form-submit 对多选的值形状未实测（按数组传）" % title)
                else:
                    m = match_option(val, names)
                    if m is None:
                        problems.append("%s：选项「%s」不存在。可选：%s %s" % (title, val, names, suggest(val, names)))
                        continue
                    fields[title] = m  # 单选 = 纯字符串（form-submit 与 record-create 规范不同）
            elif qtype == "user":
                vals = val if isinstance(val, list) else [val]
                ids = [norm_user(x) for x in vals]
                if q.get("multiple") is False and len(ids) > 1:
                    problems.append("%s 只能填一个人" % title)
                    continue
                fields[title] = [{"id": i} for i in ids]
                rows.append((SPEC_LABELS[key], ", ".join(user_label(x) for x in vals)))
                continue
            elif qtype == "datetime":
                s, d = norm_dt(val)
                fields[title] = s
                if d.date() < _dt.date.today():
                    warnings.append("%s 早于今天（%s）——补单可以，否则检查是不是算错了「下周几」" % (title, s[:10]))
                rows.append((SPEC_LABELS[key], "%s（%s）" % (s[:10], "周" + "一二三四五六日"[d.weekday()])))
                continue
            elif qtype == "not_support":
                known = LOCKED_KNOWN_OPTIONS.get(fid)
                sval = str(val).strip()
                if known and sval not in known["options"]:
                    msg = "%s：「%s」不在已知选项 %s（%s 核验%s）" % (
                        title, sval, known["options"], known["verified"], "" if known["complete"] else "，列表可能不全")
                    if allow_unknown:
                        warnings.append(msg + "；已按 --allow-unknown-option 放行，若提交报 option not found 再 probe")
                    else:
                        problems.append(msg + "；确认后加 --allow-unknown-option，或先 `dr.py probe`")
                        continue
                fields[title] = sval
            else:
                fields[title] = val
        except ValueError as e:
            problems.append("%s：%s" % (title, e))
            continue
        rows.append((SPEC_LABELS[key], fields[title]))
    for k, v in (spec.get("extra") or {}).items():
        q = q_by_id.get(k) or next((q for q in contract["questions"] if q.get("title") == k), None)
        if q is None:
            problems.append("extra 字段「%s」不在线上表单" % k)
        else:
            covered.add(q["id"])
            fields[q["title"]] = v
            rows.append(("extra:" + q["title"], v))
    for q in contract["questions"]:
        if q.get("required") and q["id"] not in covered:
            problems.append("线上必填字段未覆盖：%s（id %s）—— 用 spec.extra 补" % (q.get("title"), q["id"]))
    return fields, attachments, problems, warnings, rows


def print_draft(rows, spec):
    ev = spec.get("evidence") or {}
    print("\n## 草稿（提交前给用户看的就是这张表）\n")
    print("| 字段 | 值 | 依据 |")
    print("|---|---|---|")
    label2key = {v: k for k, v in SPEC_LABELS.items()}
    for label, v in rows:
        key = label2key.get(label, label)
        val = str(v).replace("\n", "<br>")
        print("| %s | %s | %s |" % (label, val, ev.get(key, "")))
    missing_ev = [SPEC_LABELS[k] for k in ("type", "priority", "business_line", "analysts", "expected_date")
                  if spec.get(k) not in (None, "", []) and not ev.get(k)]
    if missing_ev:
        print("\n⚠️ 这些字段没写依据（evidence），确认轮里请说明是原话 / 先例 / 推断：" + "、".join(missing_ev))


def do_validate(path, allow_unknown):
    spec = load_spec(path)
    contract = fetch_contract()
    fields, attachments, problems, warnings, rows = build_payload(spec, contract, allow_unknown)
    print_draft(rows, spec)
    for w in warnings:
        print("⚠️ " + w)
    if problems:
        print("\n校验不通过：")
        for p in problems:
            print("  ❌ " + p)
        sys.exit(1)
    print("\n✅ 校验通过（本地规则 + 线上契约）")
    return spec, fields, attachments


def cmd_validate(a):
    spec, fields, attachments = do_validate(a.spec, a.allow_unknown_option)
    payload = {"fields": fields}
    if attachments:
        payload["attachments"] = attachments
    print("\n## payload\n" + json.dumps(payload, ensure_ascii=False, indent=2))


def cmd_submit(a):
    spec, fields, attachments = do_validate(a.spec, a.allow_unknown_option)
    payload = {"fields": fields}
    args = ["base", "+form-submit", "--share-token", SHARE_TOKEN]
    if attachments:
        payload["attachments"] = attachments
        args += ["--base-token", BASE_TOKEN]
    args += ["--json", json.dumps(payload, ensure_ascii=False)]
    if not a.yes:
        res = run(args + ["--dry-run"])
        print("\n## dry-run（没有提交）——确认无误后加 --yes 真提交")
        print(json.dumps(res.get("data", res), ensure_ascii=False, indent=2)[:3000])
        return
    res = run(args + ["--yes"])
    if not res.get("ok"):
        die("提交失败：" + explain(res.get("error", res)))
    print("\n✅ 表单已提交（can_submit_again=%s），回查需求池…" % res.get("data", {}).get("can_submit_again"))
    rec = verify(spec["title"], norm_user(spec["requester"]))
    if rec:
        print("record_id=%s  状态=%s  提交时间=%s  数分对接人=%s" % (rec["record_id"], rec["status"], rec["submitted"], rec["analysts"]))
        print("\n汇报时把 record_id、状态、预期交付时间一起给用户；后续通知数分/需求方要经用户同意再发。")
    else:
        print("⚠️ 提交返回 ok 但回查没找到同标题的记录（可能索引延迟）。稍后用 `dr.py precedent --keyword \"%s\"` 再查一次。" % spec["title"])


def verify(title, requester_id):
    flt = {"logic": "and", "conditions": [[TBL["title"], "==", title],
                                          [TBL["requester"], "contains", [{"id": requester_id}]]]}
    fields = [TBL["title"], TBL["status"], TBL["submitted"], TBL["analysts"]]
    args = ["base", "+record-list", "--base-token", BASE_TOKEN, "--table-id", TABLE_ID,
            "--filter-json", json.dumps(flt, ensure_ascii=False),
            "--sort-json", json.dumps([{"field": TBL["submitted"], "desc": True}]), "--limit", "3"]
    for f in fields:
        args += ["--field-id", f]
    # markdown 输出带 _record_id 列；json 矩阵不带，所以这里解析 markdown
    p = subprocess.run([lark_cli()] + args + ["--as", "user"], capture_output=True, text=True, timeout=120)
    for line in (p.stdout or "").splitlines():
        if line.startswith("| rec"):
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if len(cells) >= 5:
                return {"record_id": cells[0], "status": cells[2], "submitted": cells[3], "analysts": cells[4]}
    return None


# ---------------------------------------------------------------------------
# probe：安全探测被锁字段的选项名
# ---------------------------------------------------------------------------
def cmd_probe(a):
    contract = fetch_contract()
    qs = contract["questions"]
    target = next((q for q in qs if q.get("title") == a.field or q.get("id") == a.field), None)
    if target is None:
        die("表单里没有字段「%s」，先跑 contract 看标题" % a.field)
    # 找一个「必填、且不是目标字段」的字段故意留空：校验顺序是「选项名转换」先于「必填检查」，
    # 所以候选合法时只会报 must required，结构上不可能真的提交成功。
    required_others = [q for q in qs if q.get("required") and q["id"] != target["id"] and q.get("type") != "attachment"]
    if not required_others:
        die("表单没有第二个必填字段可以留空，无法保证探测不会真提交，拒绝执行")
    locked_others = [q for q in required_others if q.get("type") == "not_support"]
    omit = (locked_others or required_others)[0]
    me, _ = whoami()
    base = {}
    for q in qs:
        if not q.get("required") or q["id"] in (target["id"], omit["id"]) or q.get("type") == "attachment":
            continue
        t = q.get("type")
        if t == "text":
            base[q["title"]] = "probe"
        elif t == "select":
            base[q["title"]] = q["options"][0]["name"]
        elif t == "user":
            base[q["title"]] = [{"id": me}]
        elif t == "datetime":
            base[q["title"]] = _dt.date.today().strftime("%Y-%m-%d 00:00:00")
        elif t == "not_support":
            k = LOCKED_KNOWN_OPTIONS.get(q["id"])
            if not k:
                die("必填锁字段「%s」没有已知选项，无法构造探测请求" % q["title"])
            base[q["title"]] = k["options"][0]
    print("留空的必填字段：%s（保证不会真提交）" % omit["title"])

    def one(val):
        payload = dict(base)
        payload[target["title"]] = val
        res = run(["base", "+form-submit", "--share-token", SHARE_TOKEN, "--json",
                   json.dumps({"fields": payload}, ensure_ascii=False), "--yes"])
        if res.get("ok"):
            return "‼️ 意外提交成功——立刻去需求池查标题为 probe 的记录并处理"
        msg = (res.get("error") or {}).get("message", "")
        if "not found in field options" in msg and target["title"] in msg:
            return "❌ 不是合法选项"
        if "must required" in msg:
            return "✅ 合法选项（被留空的必填项挡下，未提交）"
        return "❓ " + msg[:160]

    sanity = one("__dr_probe_invalid__")
    if not sanity.startswith("❌"):
        die("探测预言机失灵（无效值没有报 not found）：%s。停止探测。" % sanity)
    for v in a.candidates:
        print("%s => %s" % (v, one(v)))


# ---------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = ap.add_subparsers(dest="cmd", required=True)
    p = sp.add_parser("contract", help="读线上表单契约");
    p.add_argument("--json", action="store_true", help="附带原始 JSON");
    p.set_defaults(fn=cmd_contract)
    sp.add_parser("whoami", help="当前用户").set_defaults(fn=cmd_whoami)
    p = sp.add_parser("user", help="按姓名找人");
    p.add_argument("name");
    p.set_defaults(fn=cmd_user)
    p = sp.add_parser("chat", help="压平打印单聊")
    p.add_argument("who", help="姓名 / ou_ open_id / oc_ chat_id")
    p.add_argument("--pages", type=int, default=2, help="拉几页（每页 50 条），默认 2")
    p.add_argument("--since", help="起始日期 YYYY-MM-DD（本机时区）")
    p.add_argument("--until", help="结束日期 YYYY-MM-DD（含当天）")
    p.set_defaults(fn=cmd_chat)
    p = sp.add_parser("precedent", help="需求池先例")
    p.add_argument("--requester", help="发起人 open_id，默认当前用户")
    p.add_argument("--keyword", help="同主题关键词（搜所有人的标题+描述）")
    p.add_argument("--no-requester", action="store_true", help="只搜关键词，不列发起人历史")
    p.add_argument("--limit", type=int, default=15)
    p.add_argument("--full", action="store_true", help="附带背景/目标/描述全文")
    p.set_defaults(fn=cmd_precedent)
    p = sp.add_parser("validate", help="校验 spec 并打印草稿表")
    p.add_argument("spec")
    p.add_argument("--allow-unknown-option", action="store_true")
    p.set_defaults(fn=cmd_validate)
    p = sp.add_parser("submit", help="提交（默认 dry-run）")
    p.add_argument("spec")
    p.add_argument("--yes", action="store_true", help="真提交（只在用户确认草稿后）")
    p.add_argument("--allow-unknown-option", action="store_true")
    p.set_defaults(fn=cmd_submit)
    p = sp.add_parser("probe", help="安全探测锁字段选项")
    p.add_argument("field", help="字段标题或 id")
    p.add_argument("candidates", nargs="+")
    p.set_defaults(fn=cmd_probe)
    a = ap.parse_args()
    try:
        a.fn(a)
    except CliError as e:
        die(str(e))


if __name__ == "__main__":
    main()
