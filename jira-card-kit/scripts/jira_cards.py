#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""jira-card-kit 执行器：按 plan.json 批量创建 Jira 卡并补挂链接。

零依赖（macOS 自带 python3 即可）。凭据解析顺序：
  1) 环境变量 JIRA_URL / JIRA_PERSONAL_TOKEN
  2) ~/.claude/settings.json 顶层 env 块（团队标准存放位置）

命令：
  whoami                    验证认证，打印当前用户
  user-search <关键词>       按名字搜用户（拿 assignee 用的 username）
  validate <plan.json>      校验计划并打印建单计划表（不创建任何东西）
  apply <plan.json>         执行创建；结果写 <plan>.result.json；中断后重跑自动续传
  show-result <plan.json>   重新打印上次 apply 的结果清单
  discard <key...> --reason "去向说明" [--apply]
                            把卡转为「废弃」并留评论（团队惯例：不删卡，废弃留痕）。
                            默认只预览；--reason 必填，防止无声废弃。
  set-beneficiary <值> <key...> [--apply]
                            修正已建卡的受益方(cf_16706)。默认只预览 before→after，
                            加 --apply 才写入。这是本工具唯一的改卡能力（受益方错填
                            是组织级高频问题，必须能纠正）；其它字段一律请到界面改。

plan.json 结构见 examples/。链接方向语义：from 对 to 施加 type 的 outward 动作
（"android clones ios" / "AIL-140 blocks ios_story"）。
"""
import json
import os
import re
import ssl
import sys
import urllib.error
import urllib.parse
import urllib.request

DEFAULT_JIRA_URL = "https://jira.mxcb.xyz"

# ---- 房规校验表（来自 2026-08 createmeta 实测，见 references/02-field-model.md） ----
STORY_REQUIRED_CF = {
    "APP": ["customfield_11506", "customfield_16301", "customfield_11530",
            "customfield_15401", "customfield_11531", "customfield_12506",
            "customfield_17100", "customfield_16706"],
    "WEB": ["customfield_11319", "customfield_16706", "customfield_11519",
            "customfield_11530", "customfield_17200", "customfield_15401",
            "customfield_16301", "customfield_15700", "customfield_12902"],
}
BENEFICIARY_FIELD = "customfield_16706"  # 业务板块（需求受益方）：成本归属，定额消费，错填=让别人埋单
SUBTASK_TYPES = {"子任务", "国际化任务", "UI设计任务", "UI验收任务"}
KNOWN_TYPES = {"故事"} | SUBTASK_TYPES
KNOWN_LINK_TYPES = {"Cloners", "Relates", "Blocks", "Duplicate"}
SUMMARY_RE = re.compile(r"^(?:【[^】]+】)+.+")
# 机器人负责的字段，plan 里出现即报错（PMO/autotask/testting 会自动填）
BOT_FIELDS = {
    "customfield_10400": "开发者(PMO自动填)",
    "customfield_10500": "测试负责人(PMO自动填)",
    "customfield_11402": "UI负责人(autotask自动填)",
    "customfield_11941": "期望设计完成(autotask自动填)",
    "customfield_16102": "排优日期(autotask自动填)",
    "customfield_12604": "前端工作量(testting自动填)",
    "customfield_16404": "前端AI提效人天(testting自动填)",
}

# ---- 选项值真身表（2026-08-24 editmeta 全量比对 APP-38357 / WEB-19342）----
# Jira 按字面文本匹配选项，差一个空格就报 Option id 'null' is not valid 并让 apply 停在第一张卡。
# ⚠️ 下面两处的空格不是笔误，是 Jira 里的真身：
#     cf_11531 的 "不需要 " 尾部有 1 个空格；cf_16706 的 "前台  - SEO - Jackie" 中间是 2 个空格。
ENUM_ALLOWED = {
    "customfield_11506": ["无需依赖", "依赖已交付", "依赖未交付"],
    "customfield_16301": ["是", "否"],
    "customfield_11530": ["是", "否"],
    "customfield_15401": ["是", "否"],
    "customfield_11531": ["不需要 ", "需要且英文文案已校对", "需要但英文文案暂未校对"],
    "customfield_12506": ["是", "否"],
    "customfield_17100": ["需要（业务产品选填）", "不需要（业务产品选填）", "已审核（APP产品选填）"],
    "customfield_11319": ["业务需求", "支撑需求", "客服需求", "技术需求", "质量需求",
                          "跨团队配合需求", "公司平台需求（含流动性，财务&OSS，平台风控，数据平台）"],
    "customfield_12002": ["待确认", "该需求是原生需求", "该需求是派生需求"],
    "customfield_11519": ["前端", "后端", "前后端", "配置变更"],
    "customfield_17200": ["是", "否"],
    "customfield_15700": ["是", "否"],
    "customfield_12902": ["无需SEO", "需SEO判断", "有公开落地页"],
    "customfield_16706": [
        "现货业务（交易/Dex+）- Marvin", "合约业务（交易/活动/跟单）- Jess", "理财 - Jackie",
        "AI - Ealy", "前台 - 直客 - App - Jackie", "前台 - 直客 - Web - Jackie",
        "前台  - SEO - Jackie", "前台 - 付费 - Jackie", "前台 - 代理 - Jackie",
        "前台 - 国家增长 - Jackie", "产品 - Ealy", "中台 - 现货活动 - Marvin",
        "中台 - 活动中台 - Jackie", "中台 - 营销中心 / 运营中台 - Jackie",
        "中台 - 内容中心 / 国际化流程 - Quinn", "中台 - UJ - Jackie",
        "后台 - 数据产品 - Jackie", "后台 - 消息产品 - Jackie", "后台 - 风控 - Marvin",
        "后台 - 合规中心 - Marvin", "后台 - KYC - Marvin", "后台 - 财务 / 薪酬 / EHR - Marvin",
        "后台 - 薪酬 / EHR - Marvin", "后台 - 财务 - Marvin", "后台 - 客服 - Ealy",
        "后台 - 技术底盘 - Ealy", "GoPerp/合规站建设 - Luke", "OTC - Sato", "P2P - Sato",
        "钱包 - Leo", "平面/设计/文案 - Quinn", "市场部 - Yvonne", "预测市场 - Roger Z",
        "战略需求 - 需立项 & 增长委员会投票", "其它",
    ],
}
ENUM_LABELS = {
    "customfield_11506": "依赖交付情况", "customfield_16301": "是否需要埋点",
    "customfield_11530": "是否需要UI", "customfield_15401": "是否涉及新页面",
    "customfield_11531": "是否需要国际化", "customfield_12506": "是否涉及响应式",
    "customfield_17100": "是否需要APP端产品介入", "customfield_11319": "需求类别",
    "customfield_12002": "是否为原生需求", "customfield_11519": "需求归属端",
    "customfield_17200": "是否是合规站", "customfield_15700": "是否涉及运营配置",
    "customfield_12902": "是否需要SEO", "customfield_16706": "业务板块（受益方）",
}


def whitespace_hint(real):
    """描述真身值里的空白差异，让人一眼看出该补哪儿的空格。"""
    bits = []
    lead = len(real) - len(real.lstrip())
    trail = len(real) - len(real.rstrip())
    if lead:
        bits.append(f"首部 {lead} 个空格")
    if trail:
        bits.append(f"尾部 {trail} 个空格")
    if "  " in real.strip():
        bits.append("中间有连续空格")
    return "、".join(bits) or "空白字符不同"


def die(msg):
    print(f"ERROR: {msg}", file=sys.stderr)
    sys.exit(1)


def load_credentials():
    url = os.environ.get("JIRA_URL")
    token = os.environ.get("JIRA_PERSONAL_TOKEN")
    if not (url and token):
        settings = os.path.expanduser("~/.claude/settings.json")
        if os.path.exists(settings):
            try:
                env = json.load(open(settings)).get("env", {})
                url = url or env.get("JIRA_URL")
                token = token or env.get("JIRA_PERSONAL_TOKEN")
            except (json.JSONDecodeError, OSError):
                pass
    if not token:
        die("找不到 JIRA_PERSONAL_TOKEN。请设置环境变量，或写入 ~/.claude/settings.json 的 env 块"
            "（配置方法见团队文档《Atlassian(Jira) MCP Setup》）。")
    return (url or DEFAULT_JIRA_URL).rstrip("/"), token


def api(method, path, payload=None, params=None):
    base, token = load_credentials()
    url = base + path
    if params:
        url += "?" + urllib.parse.urlencode(params)
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(url, data=data, method=method, headers={
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    })
    ctx = ssl.create_default_context()
    try:
        with urllib.request.urlopen(req, timeout=60, context=ctx) as resp:
            body = resp.read().decode()
            return json.loads(body) if body.strip() else {}
    except urllib.error.HTTPError as e:
        detail = e.read().decode(errors="replace")[:800]
        raise RuntimeError(f"HTTP {e.code} {method} {path}: {detail}") from e


# ---------------------------------------------------------------- validate
def load_plan(path):
    if not os.path.exists(path):
        die(f"计划文件不存在: {path}")
    try:
        plan = json.load(open(path))
    except json.JSONDecodeError as e:
        die(f"计划文件不是合法 JSON: {e}")
    if not isinstance(plan.get("cards"), list) or not plan["cards"]:
        die("plan.cards 必须是非空数组")
    return plan


def validate_plan(plan):
    """返回 (errors, warnings)。只做本地房规校验，不打网络。"""
    errors, warnings = [], []
    refs = {}
    for i, c in enumerate(plan["cards"]):
        tag = c.get("ref") or f"cards[{i}]"
        if not c.get("ref"):
            errors.append(f"{tag}: 缺 ref")
        elif c["ref"] in refs:
            errors.append(f"{tag}: ref 重复")
        refs[c.get("ref")] = c
        for k in ("project", "issuetype", "summary"):
            if not c.get(k):
                errors.append(f"{tag}: 缺 {k}")
        if c.get("issuetype") and c["issuetype"] not in KNOWN_TYPES:
            errors.append(f"{tag}: 未知 issuetype「{c['issuetype']}」(支持: {sorted(KNOWN_TYPES)})")
        if c.get("summary") and not SUMMARY_RE.match(c["summary"]):
            errors.append(f"{tag}: summary 不符合「【端/类型】【业务线】需求名」格式: {c['summary']}")
        fields = c.get("fields", {})
        for cf, allowed in ENUM_ALLOWED.items():
            v = fields.get(cf)
            if not isinstance(v, dict) or "value" not in v:
                continue
            val = v["value"]
            if val in allowed:
                continue
            label = ENUM_LABELS.get(cf, cf)
            # 空白归一后比对：既抓首尾空格，也抓中间的连续空格（如 cf_16706 的「前台  - SEO」）
            norm = " ".join(str(val).split())
            hit = next((a for a in allowed if " ".join(a.split()) == norm), None)
            if hit:
                errors.append(f"{tag}: {label}({cf}) 填「{val}」空格对不上，真身是「{hit}」"
                              f"（{whitespace_hint(hit)}）。Jira 按字面匹配，原样 apply 会报 "
                              "Option id 'null' is not valid 并停在这张卡。")
            else:
                warnings.append(f"{tag}: {label}({cf}) 的「{val}」不在 kit 已知允许值里"
                                "（kit 表为 2026-08-24 快照，Jira 可能新增了选项）；"
                                "apply 以 Jira 为准，建议先查 editmeta 的 allowedValues 核对。")
        if c.get("issuetype") == "故事":
            need = STORY_REQUIRED_CF.get(c.get("project"), [])
            missing = [cf for cf in need if cf not in fields]
            if c.get("project") not in STORY_REQUIRED_CF:
                errors.append(f"{tag}: v1 只支持项目 APP / WEB，收到「{c.get('project')}」")
            if missing:
                errors.append(f"{tag}: 故事缺必填字段 {missing}")
            if not fields.get("description"):
                warnings.append(f"{tag}: description 为空——房规是贴 PRD lark 链接")
        if c.get("issuetype") in SUBTASK_TYPES:
            parent = c.get("parent_ref") or fields.get("parent", {}).get("key")
            if not parent:
                errors.append(f"{tag}: 子任务类必须有 parent_ref（或 fields.parent.key）")
            elif c.get("parent_ref"):
                pi = next((j for j, x in enumerate(plan["cards"]) if x.get("ref") == c["parent_ref"]), None)
                if pi is None:
                    errors.append(f"{tag}: parent_ref「{c['parent_ref']}」不在 cards 里")
                elif pi >= i:
                    errors.append(f"{tag}: 父卡「{c['parent_ref']}」必须排在子任务前面")
        for cf, why in BOT_FIELDS.items():
            if cf in fields:
                errors.append(f"{tag}: 字段 {cf} 是{why}，plan 里不允许出现")
    has_story = any(c.get("issuetype") == "故事" for c in plan["cards"])
    if has_story:
        meta = plan.get("meta") or {}
        if not meta.get("beneficiary_confirmed_by"):
            errors.append("plan.meta.beneficiary_confirmed_by 未填——受益方(cf_16706)是成本归属决策，"
                          "**必须由产品本人亲口确认后才能写**。AI 不得代为判断、推断或照抄主卡/历史卡。"
                          "先问用户「这个需求做成后收益归谁」，拿到明确答复再填确认人。")
        if not meta.get("beneficiary_rationale"):
            errors.append("plan.meta.beneficiary_rationale 未填——写明用户给出的判定依据（原话浓缩），供复核。")
    for i, l in enumerate(plan.get("links", [])):
        tag = f"links[{i}]"
        if l.get("type") not in KNOWN_LINK_TYPES:
            errors.append(f"{tag}: 未知链接类型「{l.get('type')}」")
        for side in ("from", "to"):
            ref, key = l.get(f"{side}_ref"), l.get(side)
            if not ref and not key:
                errors.append(f"{tag}: 缺 {side}_ref 或 {side}")
            if ref and ref not in refs:
                errors.append(f"{tag}: {side}_ref「{ref}」不在 cards 里")
            if key and not re.match(r"^[A-Z][A-Z0-9]+-\d+$", key):
                errors.append(f"{tag}: {side}「{key}」不像 Jira key")
    return errors, warnings


def brief_fields(c):
    out = []
    f = c.get("fields", {})
    if f.get(BENEFICIARY_FIELD):
        out.append(f"受益方={f[BENEFICIARY_FIELD].get('value')}")
    if f.get("assignee"):
        out.append(f"assignee={f['assignee'].get('name')}")
    if f.get("priority"):
        out.append(f"{f['priority'].get('name')}")
    if f.get("components"):
        out.append("/".join(x["name"] for x in f["components"]))
    if f.get("fixVersions"):
        out.append("/".join(x["name"] for x in f["fixVersions"]))
    if f.get("customfield_10102"):
        out.append(f"epic={f['customfield_10102']}")
    return ", ".join(out)


def print_beneficiary_check(plan):
    """受益方是成本归属决策，最容易错填且季末要回溯审计，单独拎出来让用户复核。"""
    stories = [c for c in plan["cards"] if c.get("issuetype") == "故事"]
    if not stories:
        return
    groups = {}
    for c in stories:
        v = (c.get("fields", {}).get(BENEFICIARY_FIELD) or {}).get("value", "<未填>")
        groups.setdefault(v, []).append(c.get("ref"))
    print("\n### 受益方确认（谁收益填谁——记的是团队人力账，季末回溯审计）")
    for v, refs in groups.items():
        print(f"- **{v}** ← {', '.join(refs)}")
    meta = plan.get("meta") or {}
    by, rationale = meta.get("beneficiary_confirmed_by"), meta.get("beneficiary_rationale")
    print(f"- 由 **{by}** 亲自确认" if by else "- 确认人：**缺失**——受益方必须产品本人确认，AI 不得代填")
    print(f"- 判定依据：{rationale}" if rationale else "- 判定依据：**缺失**")
    print("- 房规：谁收益填谁。产品自提需求说服业务方埋单→挂业务方，说服不了→只能挂产品线。"
          "不许照抄主卡或历史卡（主卡自己也可能填错）。")


def print_table(plan):
    print("\n## 建单计划")
    if plan.get("meta"):
        m = plan["meta"]
        print(f"需求：{m.get('requirement', '?')}    PRD：{m.get('prd', '-')}")
    print("\n| # | ref | 项目 | 类型 | summary | 挂载 | 关键字段 |")
    print("|---|-----|------|------|---------|------|----------|")
    for i, c in enumerate(plan["cards"], 1):
        parent = c.get("parent_ref") or c.get("fields", {}).get("parent", {}).get("key") or "-"
        print(f"| {i} | {c.get('ref')} | {c.get('project')} | {c.get('issuetype')} "
              f"| {c.get('summary')} | {parent} | {brief_fields(c)} |")
    print_beneficiary_check(plan)
    if plan.get("links"):
        verbs = {"Blocks": "blocks", "Cloners": "clones", "Relates": "relates to", "Duplicate": "duplicates"}
        print("\n| 链接 | from | to |")
        print("|------|------|----|")
        for l in plan["links"]:
            print(f"| {l['type']}({verbs.get(l['type'], '?')}) "
                  f"| {l.get('from_ref') or l.get('from')} | {l.get('to_ref') or l.get('to')} |")


# ---------------------------------------------------------------- apply
def result_path(plan_path):
    return re.sub(r"\.json$", "", plan_path) + ".result.json"


def build_payload(card):
    fields = dict(card.get("fields", {}))
    fields["project"] = {"key": card["project"]}
    fields["summary"] = card["summary"]
    fields["issuetype"] = {"name": card["issuetype"]}
    return {"fields": fields}


def apply_plan(plan_path):
    plan = load_plan(plan_path)
    errors, warnings = validate_plan(plan)
    for w in warnings:
        print(f"WARN: {w}")
    if errors:
        for e in errors:
            print(f"ERROR: {e}", file=sys.stderr)
        die("计划未通过校验，未创建任何卡")

    rpath = result_path(plan_path)
    result = {"created": {}, "links_done": []}
    if os.path.exists(rpath):
        result = json.load(open(rpath))
        if result.get("created"):
            print(f"发现上次结果 {rpath}，续传模式：已建 {list(result['created'])} 将跳过")

    base, _ = load_credentials()
    failed = None
    for card in plan["cards"]:
        ref = card["ref"]
        if ref in result["created"]:
            continue
        payload = build_payload(card)
        if card.get("parent_ref"):
            pkey = result["created"].get(card["parent_ref"], {}).get("key")
            if not pkey:
                print(f"SKIP {ref}: 父卡 {card['parent_ref']} 未创建成功")
                continue
            payload["fields"]["parent"] = {"key": pkey}
        try:
            resp = api("POST", "/rest/api/2/issue", payload)
            result["created"][ref] = {"key": resp["key"], "summary": card["summary"]}
            print(f"CREATED {resp['key']}  {card['summary']}")
        except RuntimeError as e:
            failed = (ref, str(e))
            print(f"FAILED {ref}: {e}", file=sys.stderr)
            break
        finally:
            json.dump(result, open(rpath, "w"), ensure_ascii=False, indent=1)

    if failed is None:
        for i, l in enumerate(plan.get("links", [])):
            if i in result["links_done"]:
                continue
            def side_key(side):
                if l.get(f"{side}_ref"):
                    return result["created"].get(l[f"{side}_ref"], {}).get("key")
                return l.get(side)
            fk, tk = side_key("from"), side_key("to")
            if not (fk and tk):
                print(f"SKIP link[{i}]: 端点未创建 ({fk} -> {tk})")
                continue
            try:
                # 语义：fk 对 tk 施加 outward 动作（fk clones/blocks tk）
                # Server 实测：链接记录 {inwardIssue: X, outwardIssue: Y} 表示 X 施动 Y
                api("POST", "/rest/api/2/issueLink", {
                    "type": {"name": l["type"]},
                    "inwardIssue": {"key": fk},
                    "outwardIssue": {"key": tk},
                })
                result["links_done"].append(i)
                print(f"LINKED {fk} -{l['type']}-> {tk}")
            except RuntimeError as e:
                print(f"FAILED link[{i}] {fk}->{tk}: {e}", file=sys.stderr)
            finally:
                json.dump(result, open(rpath, "w"), ensure_ascii=False, indent=1)

    print_result(plan_path)
    if failed:
        die(f"卡「{failed[0]}」创建失败，后续卡未创建。已建的卡见上表（不会自动删除）。"
            f"修正 plan 后重跑 apply 会自动续传。")


def print_result(plan_path):
    rpath = result_path(plan_path)
    if not os.path.exists(rpath):
        die(f"没有结果文件 {rpath}（还没 apply 过）")
    result = json.load(open(rpath))
    base, _ = load_credentials()
    print("\n## 已创建的卡")
    for ref, info in result["created"].items():
        print(f"- {info['key']}  {info['summary']}\n  {base}/browse/{info['key']}")
    print(f"\n(链接已建 {len(result.get('links_done', []))} 条)")


# ---------------------------------------------------------------- misc cmds
def cmd_whoami():
    me = api("GET", "/rest/api/2/myself")
    print(f"{me['displayName']} ({me['name']})  {me.get('emailAddress','')}  active={me['active']}")


def cmd_user_search(query):
    users = api("GET", "/rest/api/2/user/search", params={"username": query, "maxResults": 10})
    if not users:
        print(f"没搜到「{query}」")
    for u in users:
        print(f"{u['name']:20s} {u['displayName']:20s} {u.get('emailAddress','')}")


def cmd_set_beneficiary(value, keys, apply_it):
    """修正受益方。默认 dry-run；--apply 才写入。只碰 cf_16706 这一个字段。"""
    meta = api("GET", f"/rest/api/2/issue/{keys[0]}/editmeta")
    field = meta.get("fields", {}).get(BENEFICIARY_FIELD)
    if not field:
        die(f"{keys[0]} 上没有受益方字段（或无编辑权限）")
    allowed = [x.get("value") for x in field.get("allowedValues", [])]
    if allowed and value not in allowed:
        print(f"ERROR: 「{value}」不在允许值里。候选：", file=sys.stderr)
        for a in allowed:
            print(f"  {a}", file=sys.stderr)
        die("受益方取值必须与允许值逐字一致")

    print(f"## 受益方修正 → 「{value}」{'（执行）' if apply_it else '（预览，加 --apply 才写入）'}")
    todo = []
    for k in keys:
        f = api("GET", f"/rest/api/2/issue/{k}", params={"fields": f"summary,{BENEFICIARY_FIELD}"})["fields"]
        cur = (f.get(BENEFICIARY_FIELD) or {}).get("value", "<空>")
        mark = "已是目标值，跳过" if cur == value else f"{cur} → {value}"
        print(f"  {k:12s} {mark:34s} {f['summary'][:38]}")
        if cur != value:
            todo.append(k)
    if not todo:
        print("\n全部已是目标值，无需修改。")
        return
    if not apply_it:
        print(f"\n待改 {len(todo)} 张。确认无误后加 --apply 重跑。")
        return
    print()
    for k in todo:
        try:
            api("PUT", f"/rest/api/2/issue/{k}", {"fields": {BENEFICIARY_FIELD: {"value": value}}})
            back = api("GET", f"/rest/api/2/issue/{k}", params={"fields": BENEFICIARY_FIELD})["fields"]
            got = (back.get(BENEFICIARY_FIELD) or {}).get("value")
            print(f"  {k}: 已改，读回={got}" + ("" if got == value else "  ⚠️ 与目标不符!"))
        except RuntimeError as e:
            print(f"  {k}: FAILED {e}", file=sys.stderr)


def cmd_discard(keys, reason, apply_it):
    """把卡转为「废弃」并留评论说明去向。团队惯例：不删卡，废弃留痕可回溯。"""
    print(f"## 废弃 {len(keys)} 张卡{'（执行）' if apply_it else '（预览，加 --apply 才写入）'}")
    print(f"评论内容：{reason}")
    todo = []
    for k in keys:
        f = api("GET", f"/rest/api/2/issue/{k}", params={"fields": "summary,status"})["fields"]
        st = f["status"]["name"]
        if st == "废弃":
            print(f"  {k:12s} 已是废弃，跳过        {f['summary'][:38]}")
            continue
        trans = api("GET", f"/rest/api/2/issue/{k}/transitions")["transitions"]
        t = next((x for x in trans if x["to"]["name"] == "废弃"), None)
        if not t:
            print(f"  {k:12s} 无废弃流转! 可用: {[x['to']['name'] for x in trans]}")
            continue
        print(f"  {k:12s} {st} → 废弃{'':10s}{f['summary'][:38]}")
        todo.append((k, t["id"]))
    if not todo:
        print("\n没有需要废弃的卡。")
        return
    if not apply_it:
        print(f"\n待废弃 {len(todo)} 张。确认后加 --apply 重跑。")
        return
    print()
    for k, tid in todo:
        try:
            api("POST", f"/rest/api/2/issue/{k}/comment", {"body": reason})
            api("POST", f"/rest/api/2/issue/{k}/transitions", {"transition": {"id": tid}})
            st = api("GET", f"/rest/api/2/issue/{k}", params={"fields": "status"})["fields"]["status"]["name"]
            print(f"  {k}: 已评论+废弃，读回状态={st}")
        except RuntimeError as e:
            print(f"  {k}: FAILED {e}", file=sys.stderr)


def main():
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        sys.exit(0)
    cmd = args[0]
    if cmd == "whoami":
        cmd_whoami()
    elif cmd == "user-search":
        if len(args) < 2:
            die("用法: user-search <关键词>")
        cmd_user_search(args[1])
    elif cmd == "validate":
        if len(args) < 2:
            die("用法: validate <plan.json>")
        plan = load_plan(args[1])
        errors, warnings = validate_plan(plan)
        print_table(plan)
        for w in warnings:
            print(f"WARN: {w}")
        for e in errors:
            print(f"ERROR: {e}", file=sys.stderr)
        if errors:
            sys.exit(1)
        print("\n校验通过 ✓（尚未创建，确认后执行 apply）")
    elif cmd == "apply":
        if len(args) < 2:
            die("用法: apply <plan.json>")
        apply_plan(args[1])
    elif cmd == "show-result":
        if len(args) < 2:
            die("用法: show-result <plan.json>")
        print_result(args[1])
    elif cmd == "discard":
        rest = args[1:]
        reason = None
        if "--reason" in rest:
            i = rest.index("--reason")
            if i + 1 >= len(rest):
                die("--reason 后面要跟说明文字")
            reason = rest[i + 1]
            rest = rest[:i] + rest[i + 2:]
        keys = [a for a in rest if a != "--apply"]
        if not keys:
            die('用法: discard <issue-key...> --reason "去向说明" [--apply]')
        if not reason:
            die("必须给 --reason：废弃要留评论说明去向，不允许无声废弃")
        cmd_discard(keys, reason, "--apply" in args)
    elif cmd == "set-beneficiary":
        rest = [a for a in args[1:] if a != "--apply"]
        if len(rest) < 2:
            die("用法: set-beneficiary <受益方值> <issue-key...> [--apply]")
        cmd_set_beneficiary(rest[0], rest[1:], "--apply" in args)
    else:
        die(f"未知命令 {cmd}。可用: whoami / user-search / validate / apply / show-result / "
            f"set-beneficiary / discard")


if __name__ == "__main__":
    main()
