#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# PRD Authoring Kit · © Noah Zhan (@noah.zhan) · 二次分发/衍生须保留署名，不得标榜为自己原创创作。LICENSE / NOTICE 见根目录。
"""公司配置的唯一读写入口（pm-ai-kit 2.1.0 起）。

公开 npm 包里只留配置的「形状」（schema 与占位）；公司的真值——飞书表格坐标（base_token /
table_id / form_token / spreadsheet_token / sheet_id / wiki space id）、Jira 地址、模板里引用的
公司文档链接——放在一份只有公司租户能打开的飞书文档里，同事第一次用时导入到本机：

    ~/.prd-authoring-kit/library.json      （_schema_version = 1）

子命令：
  import <飞书文档链接 | 本地 .json> [--yes]
                                     导入（飞书链接走 `lark-cli docs +fetch`，取正文第一个 ```json 代码块；
                                     飞书链接不带 --yes 只打印来源摘要 + CONFIRM_REQUIRED、不落盘）
  refresh [--force]                  开场静默刷新：输出 NO_CONFIG / LOCAL / FRESH / REFRESHED / STALE <原因>，退出码永远 0
  show                               摘要：来源链接、拉取时间、各段有无与条数（不打印任何 token）
  get <键路径>                       点号取值（如 telemetry.spreadsheet_token、jira.url、sources.0.base_token）；
                                     缺键 → 空输出、退出 2。AI 填命令占位 / 替换模板 {{company.*}} 只走这里

其它脚本复用：`from company_config import load_company_config`（返回 dict 或 None，绝不抛异常）。
测试逃生口：环境变量 PRD_KIT_COMPANY_CONFIG=<json 路径> 顶掉默认路径（所有子命令与 load_company_config 都认）。

🔴 token 是资源定位符不是凭据（没有公司租户的飞书登录态打不开），但**不回显到对话 / PRD / 报告**：
   `import` / `refresh` / `show` 永不打印 token 值；`get` 的输出只用于填命令参数，别转述给用户。
本脚本只读飞书文档、只写上面那一个本地文件（及其 .bak-* 备份），不下载、不执行任何代码。
🔴 值白名单校验（validate）：配置每 24h 从飞书文档静默刷新、值会被 AI 填进单行命令——import / refresh
   落盘前逐键校验（token 类只许 [A-Za-z0-9_-]、URL 只许 https、cite 只许单个 <cite> 块、其余字符串禁
   shell 元字符），任一违规整份拒收、旧文件不动；get 输出前再按同规则校验一遍（违规 → stderr、stdout 空、退出 3）。
本机补充项：sources / wiki_spaces 里标 "local": true 的条目与顶层 asked，import / refresh 覆盖时原样保留
   （追加在远端条目之后，按 id 去重、远端优先）。
🔴 来源锁定（2.1.1）：配置文档决定同事的登记写进哪张表、允许安装哪个版本（releases 白名单），所以来源本身要核。
   import <飞书链接> 拉正文并校验通过后，再用 `lark-cli drive metas batch_query` 取文档标题 / 所有者 /
   最近编辑者，打印给人核对；不带 --yes 到此为止（最后一行 CONFIRM_REQUIRED），带 --yes 才落盘并写入
   source_owner = 所有者 open_id（取不到元数据 → 提示无法核验、仍可 --yes，但不写 source_owner）。
   refresh 每次先核元数据：取不到 / 所有者与 source_owner 不同 / 最近编辑者不是所有者 → STALE、旧文件不动；
   本地还没有 source_owner（2.1.0 存量）且本次核验通过 → 回填所有者（先到先信）。
   竞态收紧：refresh 与 import --yes 拉完正文后再核一次元数据，两次所有者 / 最近编辑者任一不一致 → 不落盘。
   source_owner 只认 drive 元数据，文档正文或本地 json 里自带的一律丢弃。
零依赖（仅标准库）。
"""

import argparse
import datetime as _dt
import json
import os
import re
import shutil
import subprocess
import sys

SCHEMA_VERSION = 1
FRESH_SECONDS = 24 * 3600
ENV_PATH = "PRD_KIT_COMPANY_CONFIG"
DEFAULT_PATH = os.path.join("~", ".prd-authoring-kit", "library.json")
SECTIONS = ("sources", "forms", "wiki_spaces", "telemetry", "tracking", "jira", "links")


class ConfigError(Exception):
    """用户可读的中文错误（不含任何 token 值）。"""


# ---------------------------------------------------------------- 路径 / 读取


def config_path():
    env = (os.environ.get(ENV_PATH) or "").strip()
    return os.path.abspath(os.path.expanduser(env or DEFAULT_PATH))


def _read_json(path):
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def load_company_config():
    """读本机公司配置；没有 / 读不出 / 形状不对一律返回 None（调用方按「无配置」处理）。"""
    try:
        path = config_path()
        if not os.path.isfile(path):
            return None
        data = _read_json(path)
        return data if isinstance(data, dict) else None
    except Exception:
        return None


# ---------------------------------------------------------------- 解析 / 校验


def _first_fenced_string(obj):
    """在 lark-cli 的 JSON 信封里递归找第一个含 ``` 的字符串值（不猜字段名）。"""
    if isinstance(obj, str):
        return obj if "```" in obj else None
    if isinstance(obj, dict):
        for v in obj.values():
            hit = _first_fenced_string(v)
            if hit is not None:
                return hit
    elif isinstance(obj, list):
        for v in obj:
            hit = _first_fenced_string(v)
            if hit is not None:
                return hit
    return None


def _markdown_body(stdout):
    try:
        envelope = json.loads(stdout)
    except ValueError:
        return stdout
    body = _first_fenced_string(envelope)
    return body if body is not None else ""


def _extract_json_block(markdown):
    m = re.search(r"```json\s*\n(.*?)\n```", markdown, re.DOTALL)
    if not m:
        m = re.search(r"```[^\n]*\n(.*?)\n```", markdown, re.DOTALL)
    if not m:
        raise ConfigError("文档里没有 ```json 代码块")
    return m.group(1)


def _parse_config_text(text, origin):
    try:
        data = json.loads(text)
    except ValueError as exc:
        # JSONDecodeError 的消息只含位置，不含内容片段
        raise ConfigError("%s 不是合法 JSON：%s" % (origin, exc))
    return _validate(data, origin)


def _validate(data, origin):
    if not isinstance(data, dict):
        raise ConfigError("%s 顶层不是 JSON 对象" % origin)
    ver = data.get("_schema_version")
    if ver != SCHEMA_VERSION:
        raise ConfigError("%s 的 _schema_version 是 %r，本版 kit 只认 %d（请核对配置文档或升级 kit）"
                          % (origin, ver, SCHEMA_VERSION))
    return data


# ---------------------------------------------------------------- 值白名单校验（F2）

STRICT_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
WIKI_ID_RE = re.compile(r"^[0-9]{10,25}$")
URL_RE = re.compile(r"^https://[A-Za-z0-9.-]+(:[0-9]{2,5})?(/[A-Za-z0-9._~%/?=&#:+-]*)?$")
CITE_RE = re.compile(r'^<cite( [a-z-]+="[A-Za-z0-9 _:./?=&%()（）\-\u4e00-\u9fff]*")*></cite>( (https://\S+))?$')
FORBIDDEN_CHARS = ("`", "$", ";", "|", "&", "<", ">", "\\", "\n", "\r")
MAX_STR = 2000
MAX_DEPTH = 6
CITE_KEYS = ("paradigm_dict", "ui_guide", "translation_guide")
RELEASE_VER_RE = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+$")   # 不用 \d：Python 的 \d 认全角数字
RELEASE_HASH_RE = re.compile(r"^sha512-[A-Za-z0-9+/]{86}==$")
OWNER_RE = re.compile(r"^ou_[a-f0-9]{32}$")


class ConfigRejected(ConfigError):
    """值校验不通过：path = 点号键路径，reason = 原因（都不含值本身）。"""

    def __init__(self, path, reason):
        ConfigError.__init__(self, "%s：%s" % (path, reason))
        self.path = path
        self.reason = reason


def _key_kind(parts):
    """按键路径（str 键 / int 下标）判规则：strict / wiki_id / url / cite / other。"""
    n = len(parts)
    p0 = parts[0] if n else None
    last = parts[-1] if n else None
    if n == 3 and p0 == "sources" and isinstance(parts[1], int):
        if last in ("base_token", "table_id"):
            return "strict"
        if last == "url":
            return "url"
    if n == 3 and p0 == "forms" and isinstance(parts[1], str):
        if last in ("form_token", "share_token", "base_token", "table_id"):
            return "strict"
        if last == "url":
            return "url"
    if n == 3 and p0 == "wiki_spaces" and isinstance(parts[1], int) and last == "id":
        return "wiki_id"
    if n == 2 and p0 == "telemetry" and last in ("spreadsheet_token", "sheet_id"):
        return "strict"
    if n == 2 and p0 == "tracking":
        if last in ("base_token", "table_id"):
            return "strict"
        if last == "platform_url":
            return "url"
    if n == 2 and p0 == "jira" and last == "url":
        return "url"
    if n == 1 and p0 == "source_url":
        return "url"
    if n == 2 and p0 == "links" and isinstance(last, str):
        if last.endswith("_url"):
            return "url"
        if last in CITE_KEYS:
            return "cite"
    if n == 2 and p0 == "releases" and isinstance(last, str):
        return "release_hash"
    if n == 1 and p0 == "source_owner":
        return "owner_id"
    return "other"


def _fmt_path(parts):
    return ".".join(str(p) for p in parts) or "(根)"


def _has_forbidden(s):
    return any(c in s for c in FORBIDDEN_CHARS)


def _check_string(s, kind):
    """返回违规原因（不含值）或 None。空串 = 未配置，放行（get 对空串本来就退出 2）。"""
    if len(s) > MAX_STR:
        return "超过 %d 字符" % MAX_STR
    if kind == "release_hash":
        return None if RELEASE_HASH_RE.fullmatch(s) else "只许 sha512-<86 位 base64>==（npm dist.integrity 形态）"
    if s == "":
        return None
    if kind == "strict":
        return None if STRICT_RE.fullmatch(s) else "只许字母数字 _ -（1–64 位）"
    if kind == "wiki_id":
        return None if WIKI_ID_RE.fullmatch(s) else "只许 10–25 位数字"
    if kind == "owner_id":
        return None if OWNER_RE.fullmatch(s) else "只许 ou_ + 32 位十六进制"
    if kind == "url":
        if re.search(r"\s", s) or not URL_RE.fullmatch(s):
            return "不是合规的 https 链接（只许 https://主机[:端口]/路径，不含空白与 shell 元字符）"
        return None
    if kind == "cite":
        m = CITE_RE.fullmatch(s)
        if not m or s.count("<cite") != 1:
            return "只许单个 <cite …></cite> 块（可跟一个 https 链接）"
        tail = m.group(3)
        if tail and not URL_RE.fullmatch(tail):
            return "cite 后的链接不是合规的 https 链接"
        return None
    if _has_forbidden(s):
        return "含禁止字符（` $ ; | & < > \\ 或换行）"
    return None


def _violations(value, parts, depth):
    """递归校验；depth = 当前容器嵌套层数（根对象 = 1）。返回 [(path, reason)]，只报第一处即可。"""
    kind = _key_kind(parts)
    if parts == ["releases"]:
        if not isinstance(value, dict):
            return [("releases", "应为对象（版本 → sha512）")]
        for k in value:
            if not isinstance(k, str) or not RELEASE_VER_RE.fullmatch(k):
                return [("releases", "键名只许 x.y.z 版本号")]
    if isinstance(value, (dict, list)):
        if kind != "other":
            return [(_fmt_path(parts), "应为字符串")]
        if depth > MAX_DEPTH:
            return [(_fmt_path(parts), "嵌套超过 %d 层" % MAX_DEPTH)]
        items = value.items() if isinstance(value, dict) else enumerate(value)
        for k, v in items:
            if isinstance(k, str):
                reason = _check_string(k, "other")
                if reason:
                    return [(_fmt_path(parts + [k]), "键名" + reason)]
            hit = _violations(v, parts + [k], depth + 1)
            if hit:
                return hit
        return []
    if isinstance(value, str):
        reason = _check_string(value, kind)
        return [(_fmt_path(parts), reason)] if reason else []
    if kind in ("release_hash", "owner_id"):
        return [(_fmt_path(parts), "应为字符串")]
    return []  # 数字 / 布尔 / null 放行


def validate(cfg):
    """整份配置的值白名单校验；任一违规抛 ConfigRejected（只含键路径与原因，不含值）。"""
    hit = _violations(cfg, [], 1)
    if hit:
        raise ConfigRejected(*hit[0])


def _merge_local(data, old):
    """把旧文件里的本机补充项带到新配置：sources / wiki_spaces 中 local=true 的条目（追加在远端之后，
    按 id 去重、远端优先）与顶层 asked。"""
    if not isinstance(old, dict):
        return data
    for key in ("sources", "wiki_spaces"):
        olds = old.get(key)
        if not isinstance(olds, list):
            continue
        locals_ = [x for x in olds if isinstance(x, dict) and x.get("local") is True]
        if not locals_:
            continue
        remote = data.get(key)
        if remote is None:
            remote = []
        if not isinstance(remote, list):
            continue
        seen = set(x.get("id") for x in remote if isinstance(x, dict) and x.get("id") is not None)
        merged = list(remote)
        for x in locals_:
            xid = x.get("id")
            if xid is not None and xid in seen:
                continue
            if xid is not None:
                seen.add(xid)
            merged.append(x)
        data[key] = merged
    if "asked" in old and "asked" not in data:
        data["asked"] = old["asked"]
    return data


def _is_url(s):
    return bool(re.match(r"^https?://", s.strip(), re.IGNORECASE))


def _fetch_lark_doc(url):
    exe = shutil.which("lark-cli")
    if not exe:
        raise ConfigError("找不到 lark-cli，先装并登录（lark-cli auth status）")
    try:
        proc = subprocess.run(
            [exe, "docs", "+fetch", "--doc", url, "--doc-format", "markdown", "--as", "user"],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=90,
        )
    except subprocess.TimeoutExpired:
        raise ConfigError("lark-cli 读文档超时（90s）")
    except OSError as exc:
        raise ConfigError("lark-cli 调用失败：%s" % exc)
    out = proc.stdout.decode("utf-8", "replace")
    if proc.returncode != 0:
        err = (proc.stderr.decode("utf-8", "replace").strip().splitlines() or [""])[0][:160]
        raise ConfigError("lark-cli 读文档失败（exit %d）%s" % (proc.returncode, ("：" + err) if err else ""))
    body = _markdown_body(out)
    if not body:
        raise ConfigError("文档里没有 ```json 代码块（或读到的正文为空，检查链接与权限）")
    return _parse_config_text(_extract_json_block(body), "配置文档")


# ---------------------------------------------------------------- 来源锁定（2.1.1）

# 只认规范化后的链接（_canonical_url 产出）：https://<飞书域名>/docx|wiki|docs/<token>，无 ? 无 #
DOCX_PATH_RE = re.compile(r"^https://[^/]+/docx/([A-Za-z0-9]+)$")
WIKI_PATH_RE = re.compile(r"^https://[^/]+/(?:wiki|docs)/([A-Za-z0-9]+)$")
LARK_HOST_RE = re.compile(r"^[a-z0-9-]+(?:\.[a-z0-9-]+)*\.(?:larksuite\.com|feishu\.cn|larkoffice\.com)$")
LARK_PATH_RE = re.compile(r"^/(docx|wiki|docs)/([A-Za-z0-9]{10,})/?$")


def _canonical_url(url):
    """把用户贴的链接规范化成 https://<host>/<docx|wiki|docs>/<token>：丢掉 ?query 与 #fragment，
    主机必须是飞书域名，路径必须恰好是一种文档类型 + token。元数据核验与正文读取都只用这个规范化链接，
    保证核的和读的是同一份文档（盲审 A3：`…/wiki/EVIL?from=/docx/LEGIT` 这类链接会被拒）。"""
    from urllib.parse import urlsplit
    try:
        u = urlsplit((url or "").strip())
    except ValueError:
        raise ConfigError("配置文档链接解析失败")
    host = (u.hostname or "").lower()
    if u.scheme.lower() != "https" or not LARK_HOST_RE.fullmatch(host):
        raise ConfigError("配置文档链接只接受 https://<飞书域名>/docx/<token> 或 /wiki/<token>")
    m = LARK_PATH_RE.fullmatch(u.path or "")
    if not m:
        raise ConfigError("配置文档链接路径不对：只接受 /docx/<token> 或 /wiki/<token>，不要带 ? 和 # 参数")
    return "https://%s/%s/%s" % (host, m.group(1), m.group(2))
META_DOC_TYPES = ("docx", "doc", "sheet", "bitable", "wiki", "file", "mindnote", "slides")


def _run_lark_json(argv, timeout=30):
    """跑一条只读 lark-cli，返回 JSON dict；找不到 / 超时 / 非零退出 / 非 JSON / ok=false / code≠0 → None（绝不抛）。"""
    exe = shutil.which("lark-cli")
    if not exe:
        return None
    try:
        proc = subprocess.run([exe] + list(argv), stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout)
    except (subprocess.TimeoutExpired, OSError):
        return None
    if proc.returncode != 0:
        return None
    try:
        payload = json.loads(proc.stdout.decode("utf-8", "replace"))
    except ValueError:
        return None
    if not isinstance(payload, dict) or payload.get("ok") is False or payload.get("code") not in (None, 0):
        return None
    return payload


def _find_dict_with(obj, key, depth=0):
    """递归找第一个含 key 的 dict（各命令的 JSON 信封层数不同，不猜外层字段名）。"""
    if depth > 8:
        return None
    if isinstance(obj, dict):
        if key in obj:
            return obj
        children = list(obj.values())
    elif isinstance(obj, list):
        children = obj
    else:
        return None
    for v in children:
        hit = _find_dict_with(v, key, depth + 1)
        if hit is not None:
            return hit
    return None


def _clean(s):
    """API 回来的标题 / 姓名只用于给人看：去控制字符、截 200 字。"""
    return re.sub(r"[\x00-\x1f\x7f]+", " ", str(s or "")).strip()[:200]


def _doc_token(url):
    """链接 → (token, doc_type)：/docx/<token> 直接取；/wiki/<token> 先 drive +inspect 取底层 token 与类型。拿不到 → None。"""
    try:
        url = _canonical_url(url)
    except ConfigError:
        return None
    m = DOCX_PATH_RE.fullmatch(url)
    if m:
        return m.group(1), "docx"
    if WIKI_PATH_RE.fullmatch(url):
        payload = _run_lark_json(["drive", "+inspect", "--url", url, "--as", "user"])
        node = _find_dict_with(payload, "token") if payload else None
        if node:
            tok, typ = str(node.get("token") or ""), str(node.get("type") or "")
            if STRICT_RE.fullmatch(tok) and typ in META_DOC_TYPES:
                return tok, typ
    return None


def _doc_meta(url):
    """配置文档元数据 → {title, owner_id, latest_modify_user}；命令失败 / 字段缺 / 形状不对 → None。"""
    try:
        tt = _doc_token(url)
        if not tt:
            return None
        req = {"request_docs": [{"doc_token": tt[0], "doc_type": tt[1]}], "with_url": False}
        payload = _run_lark_json(["drive", "metas", "batch_query", "--data", json.dumps(req),
                                  "--user-id-type", "open_id", "--as", "user"])
        holder = _find_dict_with(payload, "metas") if payload else None
        metas = holder.get("metas") if holder else None
        if not isinstance(metas, list) or not metas or not isinstance(metas[0], dict):
            return None
        owner = str(metas[0].get("owner_id") or "")
        editor = str(metas[0].get("latest_modify_user") or "")
        if not OWNER_RE.fullmatch(owner) or not STRICT_RE.fullmatch(editor):
            return None
        return {"title": _clean(metas[0].get("title")), "owner_id": owner, "latest_modify_user": editor}
    except Exception:
        return None


def _user_label(open_id, cache):
    """open_id → 姓名（lark-cli contact +get-user）；解析失败就用 open_id 本身。"""
    if open_id not in cache:
        name = ""
        if OWNER_RE.fullmatch(open_id):
            payload = _run_lark_json(["contact", "+get-user", "--user-id", open_id, "--as", "user"])
            data = payload.get("data") if payload else None
            user = data.get("user") if isinstance(data, dict) else None
            if isinstance(user, dict):
                name = _clean(user.get("name") or user.get("en_name"))
        cache[open_id] = name or open_id
    return cache[open_id]


def _meta_changed(a, b):
    """两次元数据的所有者 / 最近编辑者是否不一致（任一为 None 也算不一致）。"""
    if a is None or b is None:
        return True
    return a["owner_id"] != b["owner_id"] or a["latest_modify_user"] != b["latest_modify_user"]


def _print_meta(meta):
    """import 时给人核对的来源摘要（不含任何 token）。"""
    if meta is None:
        print("⚠ 无法核验文档所有者（lark-cli 权限或网络）")
        return
    cache = {}
    print("文档：《%s》" % (meta["title"] or "（无标题）"))
    print("所有者：%s" % _user_label(meta["owner_id"], cache))
    print("最近编辑：%s" % _user_label(meta["latest_modify_user"], cache))
    if meta["latest_modify_user"] != meta["owner_id"]:
        print("⚠ 最近编辑者不是所有者")


def _load_source(src):
    """src = 飞书链接 或 本地 json 路径 → (config dict, source_url or None)。"""
    src = (src or "").strip()
    if not src:
        raise ConfigError("缺少参数：飞书配置文档链接 或 本地 json 路径")
    if _is_url(src):
        src = _canonical_url(src)                    # 核验与读取共用同一规范化链接
        return _fetch_lark_doc(src), src
    path = os.path.abspath(os.path.expanduser(src))
    if not os.path.isfile(path):
        raise ConfigError("找不到文件：%s（飞书链接请以 https:// 开头）" % src)
    try:
        with open(path, "r", encoding="utf-8") as fh:
            text = fh.read()
    except OSError as exc:
        raise ConfigError("读不了文件 %s：%s" % (src, exc))
    return _parse_config_text(text, os.path.basename(path)), None


# ---------------------------------------------------------------- 写入


def _now_iso():
    return _dt.datetime.now(_dt.timezone.utc).astimezone().isoformat(timespec="seconds")


def _strip_meta(d):
    return {k: v for k, v in d.items() if k != "fetched_at"}


def _write_config(data, source_url, backup=True):
    """原子写入；已存在则先备份为 library.json.bak-<时间>。
    backup=False（refresh 用）时：仅当内容（除 fetched_at 外）有变化才备份，免得每天堆一个相同的备份。"""
    path = config_path()
    data = dict(data)
    if source_url:
        data["source_url"] = source_url
    data["fetched_at"] = _now_iso()
    validate(data)                                   # 远端内容先过白名单（违规不落盘）
    old = load_company_config() if os.path.isfile(path) else None
    data = _merge_local(data, old)
    try:
        validate(data)                               # 带过来的本机补充项也过一遍
    except ConfigRejected as exc:
        raise ConfigRejected(exc.path, "本机补充项" + exc.reason)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if os.path.isfile(path):
        need_backup = backup
        if not backup:
            need_backup = old is None or _strip_meta(old) != _strip_meta(data)
        if need_backup:
            bak = "%s.bak-%s" % (path, _dt.datetime.now().strftime("%Y%m%d%H%M%S"))
            shutil.copy2(path, bak)
    tmp = path + ".tmp-%d" % os.getpid()
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2)
        fh.write("\n")
    try:
        os.chmod(tmp, 0o600)
    except OSError:
        pass
    os.replace(tmp, path)
    return data


def _count(data, key):
    v = data.get(key)
    if isinstance(v, (list, dict)):
        return len(v)
    return 0


def _mark(data, key):
    v = data.get(key)
    return "✓" if isinstance(v, dict) and any(str(x).strip() for x in v.values()) else "–"


def _summary(data):
    return "sources %d 个 / forms %d 个 / telemetry %s / tracking %s / jira %s / links %d 个" % (
        _count(data, "sources"), _count(data, "forms"), _mark(data, "telemetry"),
        _mark(data, "tracking"), _mark(data, "jira"), _count(data, "links"))


# ---------------------------------------------------------------- 子命令


def cmd_import(args):
    try:
        data, url = _load_source(args.source)
        data = dict(data)
        data.pop("source_owner", None)               # 所有者只认 drive 元数据，不认正文 / 本地文件里自带的
        if not url:
            data.pop("source_url", None)             # 本地 json 导入 = 本地配置：不带 source_url，不会按未核验的链接自动刷新
        if url:
            validate(data)                           # 正文先过白名单，再核来源
            meta = _doc_meta(url)
            _print_meta(meta)
            if not args.yes:
                print("核对是这份文档后，加 --yes 再跑一次才会写入（本机副本：python3 <KIT_ROOT>/scripts/company_config.py import <链接> --yes；终端首次：npx pm-ai-kit@<版本> config <链接> --yes）。")
                print("CONFIRM_REQUIRED")
                return 0
            if meta is not None:
                if _meta_changed(meta, _doc_meta(url)):  # 竞态收紧：落盘前再核一次
                    print("导入失败：配置文档在核验期间被改动（所有者或最近编辑者前后不一致），未写入；稍后重跑并重新核对。",
                          file=sys.stderr)
                    return 1
                data["source_owner"] = meta["owner_id"]
        data = _write_config(data, url, backup=True)
    except ConfigRejected as exc:
        print("配置被拒：%s：%s" % (exc.path, exc.reason), file=sys.stderr)
        return 1
    except ConfigError as exc:
        print("导入失败：%s" % exc, file=sys.stderr)
        return 1
    except OSError as exc:
        print("导入失败：写不了 %s（%s）" % (config_path(), exc.strerror or exc), file=sys.stderr)
        return 1
    print("已导入公司配置：%s" % _summary(data))
    return 0


def _age_seconds(fetched_at):
    try:
        t = _dt.datetime.fromisoformat(str(fetched_at))
    except (TypeError, ValueError):
        return None
    if t.tzinfo is None:
        t = t.replace(tzinfo=_dt.datetime.now().astimezone().tzinfo)
    return (_dt.datetime.now(_dt.timezone.utc) - t).total_seconds()


def cmd_refresh(args):
    try:
        path = config_path()
        if not os.path.isfile(path):
            print("NO_CONFIG")
            return 0
        current = load_company_config()
        if current is None:
            print("STALE 本地配置文件读不出（不是合法 JSON 对象），重跑一次 config <链接>")
            return 0
        url = str(current.get("source_url") or "").strip()
        if not url:
            print("LOCAL")
            return 0
        age = _age_seconds(current.get("fetched_at"))
        if not args.force and age is not None and 0 <= age < FRESH_SECONDS:
            print("FRESH")
            return 0
        try:
            if not _is_url(url):
                raise ConfigError("source_url 不是 http(s) 链接")
            url = _canonical_url(url)
            meta = _doc_meta(url)                    # 来源锁定：先核元数据，过了才拉正文
            stored = str(current.get("source_owner") or "").strip()
            if meta is None:
                print("STALE 无法核验配置文档所有者")
                return 0
            if stored and meta["owner_id"] != stored:
                print("STALE 配置文档所有者已变更")
                return 0
            if meta["latest_modify_user"] != meta["owner_id"]:
                print("STALE 配置文档被非所有者编辑")
                return 0
            data = dict(_fetch_lark_doc(url))
            if _meta_changed(meta, _doc_meta(url)):  # 竞态收紧：拉完正文再核一次
                print("STALE 配置文档在核验期间被改动")
                return 0
            data.pop("source_owner", None)
            # source_owner 已有则保持；2.1.0 存量没有 → 本次核验通过（最近编辑者 = 所有者）即回填（先到先信）
            data["source_owner"] = stored or meta["owner_id"]
            _write_config(data, url, backup=False)
        except ConfigRejected as exc:
            print("STALE 配置校验失败：%s" % exc.path)
            return 0
        except ConfigError as exc:
            print("STALE %s" % exc)
            return 0
        except OSError as exc:
            print("STALE 写不了本地配置（%s）" % (exc.strerror or exc))
            return 0
        print("REFRESHED")
        return 0
    except Exception as exc:  # 开场静默步骤：任何意外都不许炸
        print("STALE 刷新时出错（%s）" % type(exc).__name__)
        return 0


def cmd_show(args):
    path = config_path()
    if not os.path.isfile(path):
        print("还没有公司配置（%s 不存在）。导入：npx pm-ai-kit config <飞书配置文档链接>" % path)
        return 0
    data = load_company_config()
    if data is None:
        print("公司配置文件读不出（%s 不是合法 JSON 对象）。重新导入：npx pm-ai-kit config <链接>" % path)
        return 0
    print("公司配置：%s" % path)
    print("  _schema_version：%s" % data.get("_schema_version"))
    print("  来源：%s" % (data.get("source_url") or "本地文件（无 source_url，不自动刷新）"))
    print("  拉取时间：%s" % (data.get("fetched_at") or "–"))
    print("  sources：%d 个" % _count(data, "sources"))
    print("  forms：%d 个%s" % (_count(data, "forms"),
                              ("（" + "、".join(sorted(data["forms"])) + "）") if isinstance(data.get("forms"), dict) and data["forms"] else ""))
    print("  wiki_spaces：%d 个" % _count(data, "wiki_spaces"))
    for key in ("telemetry", "tracking", "jira"):
        print("  %s：%s" % (key, "已配置" if _mark(data, key) == "✓" else "–"))
    print("  links：%d 个%s" % (_count(data, "links"),
                              ("（" + "、".join(sorted(data["links"])) + "）") if isinstance(data.get("links"), dict) and data["links"] else ""))
    return 0


def _lookup(data, dotted):
    cur = data
    for part in dotted.split("."):
        if part == "":
            return None
        if isinstance(cur, dict):
            if part not in cur:
                return None
            cur = cur[part]
        elif isinstance(cur, list):
            if not re.match(r"^\d+$", part) or int(part) >= len(cur):
                return None
            cur = cur[int(part)]
        else:
            return None
    return cur


def _path_parts(data, dotted):
    """点号路径 → 校验用的键路径（列表下标转 int，供 _key_kind 判规则）。"""
    parts, cur = [], data
    for part in dotted.split("."):
        if isinstance(cur, list) and re.match(r"^\d+$", part) and int(part) < len(cur):
            parts.append(int(part))
            cur = cur[int(part)]
        else:
            parts.append(part)
            cur = cur.get(part) if isinstance(cur, dict) else None
    return parts


def cmd_get(args):
    data = load_company_config()
    if data is None:
        return 2
    val = _lookup(data, args.key)
    if val is None or val == "":
        return 2
    hit = _violations(val, _path_parts(data, args.key), args.key.count(".") + 2)
    if hit:                                          # 双保险：本地文件被手改也不放出危险值
        print("拒绝输出：%s：%s（本地配置被改过？重跑 npx pm-ai-kit config <链接>）" % hit[0], file=sys.stderr)
        return 3
    if isinstance(val, str):
        print(val)
    else:
        print(json.dumps(val, ensure_ascii=False, separators=(",", ":")))
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(
        prog="company_config.py",
        description="pm-ai-kit 公司配置（~/.prd-authoring-kit/library.json）的唯一读写入口；不打印 token 值。",
        epilog="测试用 PRD_KIT_COMPANY_CONFIG=<json 路径> 顶掉默认路径。",
    )
    sub = ap.add_subparsers(dest="cmd")
    p = sub.add_parser("import", help="导入：飞书配置文档链接 或 本地 json 路径")
    p.add_argument("source")
    p.add_argument("--yes", action="store_true", help="飞书链接：核对来源摘要后确认写入（不带只打印摘要 + CONFIRM_REQUIRED）")
    p.set_defaults(func=cmd_import)
    p = sub.add_parser("refresh", help="开场静默刷新（24h 缓存；退出码永远 0）")
    p.add_argument("--force", action="store_true", help="忽略 24h 缓存，立即重拉")
    p.set_defaults(func=cmd_refresh)
    p = sub.add_parser("show", help="摘要（不打印 token）")
    p.set_defaults(func=cmd_show)
    p = sub.add_parser("get", help="点号路径取值；缺键空输出、退出 2")
    p.add_argument("key")
    p.set_defaults(func=cmd_get)
    args = ap.parse_args(argv)
    if not getattr(args, "func", None):
        ap.print_help()
        return 1
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
