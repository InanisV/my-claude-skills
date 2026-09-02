#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""jira-card-kit 执行器：按 plan.json 批量创建 Jira 卡并补挂链接。

零依赖（macOS 自带 python3 即可）。token 解析顺序（先到先得）：
  1) 环境变量 JIRA_PAT（推荐；旧名 JIRA_PERSONAL_TOKEN 同样识别）
  2) ~/.jira-card-kit/token 单行文件（权限 600，由 `setup-token` 写入——本工具是密码框的
     唯一持有者：弹框、取值、落盘、验证全在工具内部，AI 与用户都不必碰终端）
  3) ~/.claude/settings.json 顶层 env 块（**已降级的兼容位**：老配置照读，但每次读到都打 WARN
     催迁移——该文件 AI 因别的任务会整份打开，token 放这里迟早进上下文）
Base URL：环境变量 JIRA_URL → settings.json 的 env.JIRA_URL → 默认 https://jira.mxcb.xyz
🔴 职责分离（硬契约，SKILL.md 顶部同款）：**skill 只做行动规划与需求匹配，本工具是唯一的
   认证与 Jira 通道**。AI 绝对禁止：① 读/写/ls/cat ~/.jira-card-kit/ 下任何文件（token 与
   config 都算，config 的读写走 config-show / config-set）；② 以任何方式直连 Jira API
   （curl/httpie/python 内联 urllib 都算）；③ 在本工具之外构造或传递 Authorization 头。
   token 绝不进对话、也绝不进任何输出：密码框取回的文本在 AppleScript 进程内直写进文件，
   不经 stdout、不经 argv；验证只看 whoami 的结果。

命令：
  setup-token               配置认证：弹系统原生密码框收 token → 进程内直写落盘(600)
                            → 自动接 whoami 验证。本命令 stdout 只有 OK / CANCELLED，
                            token 不进 stdout、不进 argv、不进对话。无 GUI / 非 macOS /
                            osascript 被拦时打印终端引导并 exit 1。
  whoami                    验证认证，打印当前用户
  config-show               打印本机配置 ~/.jira-card-kit/config.json（AI 读配置的唯一入口）
  config-set <键> <值>       只合并指定键写回配置（键支持 a.b 嵌套，如 tracking_assignees.review）；
                            凭据类键一律拒收——token 不进 config
  user-search <关键词>       按名字搜用户（拿 assignee 用的 username）
  beneficiary-options [项目] [--issue <KEY>]
                            实时拉取受益方(cf_16706)的线上选项原文（默认项目 APP），
                            供产品本人从中亲选。本 kit **不内置**受益方枚举——
                            此 skill 全组产品共用、各人受益方不同，写死等于诱导错填。
  epic-candidates [--from KEY1,KEY2] [--keyword "词"…] [--project APP|WEB]
                            **只读**捞 Epic 候选：读主卡/历史关联需求卡（--from）与同族卡
                            （--keyword+--project，JQL 取最近 10 张）实际挂的 Epic，按出现
                            次数排序，每个 Epic GET 一次取名称与状态（已收口的标「不建议」
                            排后），配置里的 last_epic 只作**末位**候选标「上次用的」。
                            输出「Epic 名称 | 卡号 | 依据 | 状态」候选表——**候选不是决定**，
                            仍必须由产品确认；零候选就明说"未找到关联 Epic"，绝不编。
  epic-search --name "名称片段" [--project APP|WEB]
                            按**名称**找 Epic（≤10 条，名称|卡号|状态）——让产品用名字回答，
                            卡号由工具找。多命中一律列出来让他选，不许猜。
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
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request

DEFAULT_JIRA_URL = "https://jira.mxcb.xyz"
KIT_DIR = os.path.expanduser("~/.jira-card-kit")
TOKEN_FILE = os.path.join(KIT_DIR, "token")
CONFIG_FILE = os.path.join(KIT_DIR, "config.json")

# PAT 建 token 页直达（Atlassian 内置 PAT 插件的 profile 标签，2026-08-27 实测可达）
PAT_PAGE_URL = (DEFAULT_JIRA_URL + "/secure/ViewProfile.jspa"
                "?selectedTab=com.atlassian.pats.pats-plugin:jira-user-personal-access-tokens")
# 主路（macOS）：系统原生密码框取 token，AppleScript 文件 API **进程内**直写落盘。
# token 不进 stdout、不进 argv、不进 shell 历史、不进对话——这段脚本唯一的输出是
# "OK"（落盘成功）或 "CANCELLED"（用户点了取消 / 留空）。
# 🔴 本常量是密码框的**唯一持有者**：只由 `setup-token` 在工具内部 subprocess 跑，
#    脚本原文**不再出现在 SKILL.md / README.md**（文档只引用命令名）——这样 AI 没有
#    "照着文档自己拼一段 osascript" 的旁路，取密钥这件事只有工具这一条通道。
# ⚠️ 明令不许改写成 echo / do shell script 拼字符串的形式（那会把 token 暴露进进程表）。
TOKEN_DIALOG_SCRIPT = """osascript <<'APPLESCRIPT'
try
  set tok to text returned of (display dialog "把刚复制的 Jira token 粘贴到这里（输入显示为圆点，不会出现在屏幕或对话里）" with title "Jira Token 配置" default answer "" with hidden answer)
on error number -128
  return "CANCELLED"
end try
if tok is "" then return "CANCELLED"
do shell script "mkdir -p ~/.jira-card-kit"
set p to (POSIX path of (path to home folder)) & ".jira-card-kit/token"
set fh to open for access (POSIX file p) with write permission
set eof fh to 0
write tok to fh as «class utf8»
close access fh
do shell script "chmod 600 " & quoted form of p
return "OK"
APPLESCRIPT"""
# 降级：弹窗失败 / 无 GUI / 非 macOS 时，才让熟悉终端的用户自己跑。
# read -rs = 粘贴时屏幕不回显；变量不进 shell 历史；全程不经过对话。
TOKEN_SETUP_CMD = (
    'mkdir -p ~/.jira-card-kit && read -rs JIRA_TOKEN && '
    'printf \'%s\' "$JIRA_TOKEN" > ~/.jira-card-kit/token && '
    'chmod 600 ~/.jira-card-kit/token && unset JIRA_TOKEN && echo 已保存'
)
# 无 GUI / 非 macOS / osascript 被拦时，setup-token 打印这段（唯一的降级出口）。
TOKEN_TERMINAL_GUIDE = (
    "这台机器弹不出系统密码框（非 macOS / 无 GUI 会话 / osascript 被拦）。"
    "改让**用户自己**在终端跑这一条（粘贴时屏幕不回显、不进 shell 历史、不经过对话）：\n"
    "  " + TOKEN_SETUP_CMD + "\n"
    "  回车后光标停住就是在等他粘贴 token，粘完再回车；Windows 在 WSL / Git Bash 里跑同一条。\n"
    "  他说跑完了 → `python3 scripts/jira_cards.py whoami` 验证。\n"
    "  也可以改用环境变量 JIRA_PAT。（~/.claude/settings.json 的 env 块里的老配置仍能读到，"
    "但那是已废弃的位置、请迁走——别往那儿放新 token。）\n"
    "  🔴 AI 只把这条命令原样给用户，别代跑、别问 token 内容；token 一旦贴进对话就等于泄露。"
)
TOKEN_SETUP_HINT = (
    "找不到 Jira token。跑 `python3 scripts/jira_cards.py setup-token` 完成配置。\n"
    "  引导细节（用户不必碰终端，AI 也永远看不到 token）：\n"
    "  1) 先帮用户打开建 token 的页面：open \"" + PAT_PAGE_URL + "\"\n"
    "  2) 告诉他只做两个动作：点 Create token（名字随便）→ 点复制按钮 → 回来说一句「复制好了」。\n"
    "     ⚠️ 明确告诉他：别把 token 贴给 AI，AI 不需要看到它。\n"
    "  3) 跑 setup-token：工具自己弹系统原生密码框（输入显示为圆点）、把取回的文本进程内直写\n"
    "     " + TOKEN_FILE + "（chmod 600）、再自动接 whoami 验证并报「配置成功，当前用户：XXX」。\n"
    "     它的输出只有 OK / CANCELLED；CANCELLED 就问一句再跑一次，验证没过就让他回页面\n"
    "     重新复制一次再跑一遍——别让他把 token 贴出来看。\n"
    "  4) 无 GUI / 非 macOS / osascript 被拦：setup-token 自己会打印终端引导，照它给的转给用户。\n"
    "  🔴 AI 铁律：密码框归工具持有，**别自己拼 osascript、别自己写这个文件**；"
    "不许读 ~/.jira-card-kit/ 下任何文件、不许在任何输出或报错里回显 token；验证只看 whoami 的结果。\n"
    "  ⚠️ 如果 token 已经贴进过聊天窗口 → 它已进会话记录，去 Jira 把它撤销、重建一个再走上面流程。"
)


SETTINGS_JSON = os.path.expanduser("~/.claude/settings.json")
SETTINGS_JSON_WARN = (
    f"⚠️ 你的 Jira token 存在 {SETTINGS_JSON}——该文件 AI 日常会读写，"
    "存在进入 AI 上下文的风险。请跑 `python3 scripts/jira_cards.py setup-token` "
    "迁到专用文件（~/.jira-card-kit/token，权限 600），并手动从 settings.json 删除 "
    "JIRA_PAT / JIRA_PERSONAL_TOKEN。\n"
    "  🔴 AI：**不要为此去打开 settings.json 确认**——迁移完再跑一次命令，这条 WARN "
    "不再出现即为成功。因别的任务必须改 settings.json 时，用 Edit 定点改目标键，别整份 Read。"
)


def warn_settings_json_token():
    """settings.json 里还留着 PAT 时的统一告警出口（只提示，不打印任何值）。"""
    print(SETTINGS_JSON_WARN, file=sys.stderr)


class NetworkError(RuntimeError):
    """连不上（URLError）。**一路上抛到 main 统一出口**，和 AuthError 同待遇——

    裸 traceback 是"排障模式"的开关：模型看见一屏调用栈就会想再查点什么，禁令写在
    第 41 行也没人读。收口成一句干净的错误行，那句禁令才拦得住。
    """


def network_failure_message(base, reason):
    """URLError（连不上）的统一出口文案。

    401/403 有 auth_failure_message 挡着"顺手去翻密钥文件"，**网络不通那条一直是裸的**——
    实测：VPN 没通导致连不上，AI 在排障压力下整份读了 ~/.claude/settings.json"看看配置对不对"，
    把还躺在兼容位里的 PAT 读进了会话记录。网络问题跟凭据没有任何关系，这里把禁令写死在报错里。
    """
    return (f"连不上 {base}（{reason}）——公司网络/VPN 通吗？\n"
            "🔴 AI 收到本错误：**不要读任何配置文件**（`~/.claude/settings.json`、"
            "`~/.jira-card-kit/` 下的 token / config.json 都不许读、不许 ls、不许 cat）——"
            "**连不上是网络问题，跟凭据配得对不对无关**，翻配置只会把 token 读进会话记录。"
            "也不要改用 curl / 直连接口\"试试是不是网络问题\"。"
            "**把本条报错原样转给用户，让他确认 VPN 后重试**，在他确认之前不要继续建卡。")


def auth_failure_message(code):
    """401/403 的统一出口文案：只指向 setup-token，绝不引导任何人去翻密钥文件。"""
    msg = (f"❌ Jira 认证失败（HTTP {code}）：token 可能已过期或被撤销。"
           "请更新密钥：运行 `python3 scripts/jira_cards.py setup-token` 重新配置"
           "（它会弹窗引导；或你自行更新 ~/.jira-card-kit/token 后重试）。")
    if code == 403:
        msg += "也可能是该操作超出你的 Jira 权限。"
    return msg + ("\n🔴 AI 收到本错误：**原样转告用户去更新 token** 即可——"
                  "禁止去读 / ls / cat ~/.jira-card-kit/ 下的任何文件排查，"
                  "也禁止绕开本工具自己调 Jira 接口试。")

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
EPIC_FIELD = "customfield_10102"          # 史诗链接（裸字符串卡号）：每批必须由产品指定，不许推断
SUBTASK_TYPES = {"子任务", "国际化任务", "UI设计任务", "UI验收任务"}
KNOWN_TYPES = {"故事"} | SUBTASK_TYPES
KNOWN_LINK_TYPES = {"Cloners", "Relates", "Blocks", "Duplicate"}
# summary 前缀 = 房规，恒用**一层全角**【端】（Noah 2026-08-27 拍板；抽样 94 张真卡里两层 0 张）。
# 判定见 check_summary_prefix()：无前缀=ERROR、两层【】=WARN、半角 []=WARN。
SUMMARY_FULL_PREFIX_RE = re.compile(r"^((?:【[^】]*】)+)")
SUMMARY_HALF_PREFIX_RE = re.compile(r"^(?:\[[^\]]*\])+")
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
# ⚠️ cf_11531 的 "不需要 " 尾部那个空格不是笔误，是 Jira 里的真身。
# 🔴 受益方 cf_16706 **刻意不在本表里**：它的选项按团队/人各不相同，写死会诱导错填，
#    一律走 fetch_field_options() 实时拉取线上原文核对（受益方选项里同样出现过连续空格，
#    所以更不能手打——从线上选项逐字复制）。
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
    # customfield_16706（受益方）不列枚举——见上方红线，走线上实时拉取
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


def whitespace_hint(real, typed=None):
    """描述真身值里的空白差异，让人一眼看出该补哪儿的空格。"""
    bits = []
    lead = len(real) - len(real.lstrip())
    trail = len(real) - len(real.rstrip())
    if lead:
        bits.append(f"真身首部有 {lead} 个空格")
    if trail:
        bits.append(f"真身尾部有 {trail} 个空格")
    if "  " in real.strip():
        bits.append("真身中间有连续空格")
    if bits:
        return "、".join(bits)
    if typed is not None:
        return "真身里没有多余空格，是你这边多打了"
    return "空白字符不同"


class HttpError(RuntimeError):
    """带状态码的 API 失败（404 要单独识别：Epic 不存在 ≠ 网络不通）。"""

    def __init__(self, code, message):
        super().__init__(message)
        self.code = code


class AuthError(HttpError):
    """401/403：认证/授权失败。**一路上抛到 main 统一出口**——沿途所有兜底分支都要
    先 `except AuthError: raise` 放它过去，别把它降级成「拉不到选项」「验不了 Epic」
    这类含糊错误，那会诱导 AI 去翻密钥文件排查（正是要禁的旁路）。"""


def die(msg):
    print(f"ERROR: {msg}", file=sys.stderr)
    sys.exit(1)


def read_token_file():
    """读 ~/.jira-card-kit/token（单行）。权限比 600 松只警告不阻断。"""
    if not os.path.exists(TOKEN_FILE):
        return None
    try:
        mode = os.stat(TOKEN_FILE).st_mode & 0o777
        if mode & 0o077:
            print(f"WARN: {TOKEN_FILE} 权限是 {mode:03o}，同机其他账号可读。"
                  f"修一下：chmod 600 {TOKEN_FILE}", file=sys.stderr)
        with open(TOKEN_FILE) as f:
            return f.read().strip() or None
    except OSError as e:
        print(f"WARN: 读不了 {TOKEN_FILE}：{e}", file=sys.stderr)
        return None


_CREDS = {}


def load_credentials():
    """token 顺序：env JIRA_PAT / JIRA_PERSONAL_TOKEN → token 文件 → settings.json（**已降级的兼容位**）。

    settings.json 这条只为不打断老配置的人而保留：**每次真的从那里取到 token 就打一条 WARN**
    催迁移（见 SETTINGS_JSON_WARN）。工具自己读它无害——值不进 stdout、不进 argv；要防的是
    AI 拿 Read / cat 打开那个文件。
    """
    if _CREDS:
        return _CREDS["url"], _CREDS["token"]
    url = os.environ.get("JIRA_URL")
    token = os.environ.get("JIRA_PAT") or os.environ.get("JIRA_PERSONAL_TOKEN")
    if not token:
        token = read_token_file()
    if not (url and token):
        if os.path.exists(SETTINGS_JSON):
            try:
                env = json.load(open(SETTINGS_JSON)).get("env", {})
                url = url or env.get("JIRA_URL")
                if not token:
                    token = env.get("JIRA_PAT") or env.get("JIRA_PERSONAL_TOKEN")
                    if token:
                        warn_settings_json_token()
            except (json.JSONDecodeError, OSError):
                pass
    if not token:
        die(TOKEN_SETUP_HINT)
    _CREDS["url"] = (url or DEFAULT_JIRA_URL).rstrip("/")
    _CREDS["token"] = token
    return _CREDS["url"], _CREDS["token"]


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
        if e.code in (401, 403):
            # 认证/授权失败走专门分支：统一出口只有一句「去 setup-token 更新密钥」，
            # 不把服务端 detail 掺进去（免得 AI 顺着它去猜密钥文件的状态）。
            raise AuthError(e.code, f"HTTP {e.code} {method} {path}") from e
        raise HttpError(e.code, f"HTTP {e.code} {method} {path}: {detail}") from e
    except urllib.error.URLError as e:
        raise NetworkError(network_failure_message(base, e.reason)) from e


# ------------------------------------------------------- 线上选项（受益方专用）
_OPTIONS_CACHE = {}


def paged_values(path, params=None, pages=20):
    """走 Jira 的 startAt/isLast 分页，把 values 全取回来（createmeta 新接口是分页的）。"""
    out, start = [], 0
    for _ in range(pages):
        p = dict(params or {})
        p.update({"startAt": start, "maxResults": 200})
        data = api("GET", path, params=p)
        vals = data.get("values") or []
        out.extend(vals)
        if data.get("isLast") or not vals:
            break
        start += len(vals)
    return out


def split_allowed(meta, field, where):
    """把 allowedValues 拆成 (可选, 已停用)。停用项 Jira 建单不收，不能算命中。"""
    av = meta.get("allowedValues")
    if not av:
        raise RuntimeError(f"{where} 的 {field} 没有 allowedValues（不是下拉字段？）")
    enabled, disabled = [], []
    for a in av:
        v = a.get("value")
        if v is None:
            continue
        (disabled if a.get("disabled") else enabled).append(v)
    if not enabled:
        raise RuntimeError(f"{where} 的 {field} 线上没有任何可选项（全被停用？）")
    return enabled, disabled


def fetch_field_options(project, issuetype="故事", field=BENEFICIARY_FIELD, sample_key=None):
    """实时拉取某项目/类型下某字段的线上允许值原文，返回 (可选, 已停用)。会话内缓存一次。

    主路 = createmeta 分页接口（jira.mxcb.xyz 是 Jira Server 9.12，扁平 createmeta 已下线、
    直接 404 "Issue Does Not Exist"，2026-08-26 实测）：
        /rest/api/2/issue/createmeta/{项目}/issuetypes           → 按名字找类型 id
        /rest/api/2/issue/createmeta/{项目}/issuetypes/{类型id}   → 找字段的 allowedValues
    退路 1 = 老版扁平 createmeta（旧实例）；退路 2 = 给了 sample_key 时读那张卡的 editmeta。
    全失败就抛 RuntimeError——调用方必须转成硬错误，**绝不允许拉不到时放行近似值**。
    """
    ck = (project, issuetype, field)
    if ck in _OPTIONS_CACHE:
        return _OPTIONS_CACHE[ck]
    errs = []
    try:
        types = paged_values(f"/rest/api/2/issue/createmeta/{project}/issuetypes")
        tid = next((t.get("id") for t in types if t.get("name") == issuetype), None)
        if not tid:
            raise RuntimeError(f"项目 {project} 下没有建单类型「{issuetype}」"
                               f"（线上有：{[t.get('name') for t in types]}）")
        metas = paged_values(f"/rest/api/2/issue/createmeta/{project}/issuetypes/{tid}")
        fm = next((x for x in metas if x.get("fieldId") == field), None)
        if not fm:
            raise RuntimeError(f"{project}/{issuetype} 的建单字段里没有 {field}"
                               "（没有该项目的建单权限？字段被移出界面方案？）")
        got = split_allowed(fm, field, f"{project}/{issuetype}")
        _OPTIONS_CACHE[ck] = got
        return got
    except AuthError:
        raise  # 认证失败不是「拉不到选项」，直送统一出口
    except RuntimeError as e:
        errs.append(f"createmeta 分页接口：{e}")
    try:
        data = api("GET", "/rest/api/2/issue/createmeta", params={
            "projectKeys": project,
            "issuetypeNames": issuetype,
            "expand": "projects.issuetypes.fields",
        })
        for p in data.get("projects") or []:
            for it in p.get("issuetypes") or []:
                fm = (it.get("fields") or {}).get(field)
                if fm and fm.get("allowedValues"):
                    got = split_allowed(fm, field, f"{project}/{issuetype}")
                    _OPTIONS_CACHE[ck] = got
                    return got
        raise RuntimeError(f"返回里没有 {field} 的 allowedValues")
    except AuthError:
        raise
    except RuntimeError as e:
        errs.append(f"老版扁平 createmeta：{e}")
    if sample_key:
        try:
            meta = api("GET", f"/rest/api/2/issue/{sample_key}/editmeta")
            fm = (meta.get("fields") or {}).get(field)
            if not fm:
                raise RuntimeError(f"{sample_key} 上没有 {field}（或无编辑权限）")
            got = split_allowed(fm, field, sample_key)
            _OPTIONS_CACHE[ck] = got
            return got
        except AuthError:
            raise
        except RuntimeError as e:
            errs.append(f"editmeta({sample_key}) 兜底：{e}")
    else:
        errs.append("editmeta 兜底未启用（可加 `--issue <同项目同类型的卡号>` 再试）")
    raise RuntimeError("；".join(errs))


def beneficiary_fetch_failure(scope, reason):
    """拉不到线上选项时的统一硬错误文案——只许停下，不许猜。"""
    return (f"{scope} 受益方(cf_16706) 无法核对：{reason}。"
            "本 kit 刻意不内置受益方选项表（全组产品共用、各人受益方不同，写死等于诱导错填），"
            "**拉不到就不放行、不猜近似值**。先连上公司网络/VPN 重跑；"
            "实在拉不到就打开 Jira 建单界面的「业务板块（需求受益方）」下拉、"
            "把选项原文逐字抄进 plan（含其中的空格），并经产品本人确认后再建卡。")


def normalize(s):
    return " ".join(str(s).split())


def check_summary_prefix(summary):
    """房规：summary 恒用**一层全角**【端】前缀（Noah 2026-08-27 拍板）。

    返回 (level, msg)，level ∈ {"error", "warn"}；合规返回 None。
      - 无前缀   → ERROR：kit 自己产的 summary 必带前缀，没有＝手改 plan 时丢了，补回去。
      - 两层【】 → WARN ：房规已定一层，多出来的业务线那层并进需求名或去掉。
      - 半角 []  → WARN ：抽样真卡里通行，不拦建卡；建议换成全角对齐房规。
    """
    m = SUMMARY_FULL_PREFIX_RE.match(summary)
    if m:
        layers = len(re.findall(r"【[^】]*】", m.group(1)))
        if layers > 1:
            return ("warn", f"summary 用了 {layers} 层【】前缀「{summary}」——"
                            "房规已定**一层**（`【端】需求名`，Noah 2026-08-27 拍板）；"
                            "业务线那层并进需求名或去掉。不拦建卡。")
        return None
    if SUMMARY_HALF_PREFIX_RE.match(summary):
        return ("warn", f"summary 前缀是半角 []「{summary}」——房规是全角【端】；"
                        "抽样真卡里半角也通行，不拦建卡，建议换成全角。")
    return ("error", f"summary 没有【端】前缀「{summary}」——房规是一层全角 `【端】需求名`"
                     "（Noah 2026-08-27 拍板）。kit 生成的 summary 必带前缀，"
                     "缺了通常是手改 plan 时丢的：补回去再 validate。")


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


def check_beneficiary_live(plan, errors):
    """受益方必须逐字命中**线上**选项。拉不到 → 报错停下，不放行近似值。"""
    stories = [c for c in plan["cards"] if c.get("issuetype") == "故事" and c.get("project")]
    if not stories:
        return
    per_project = {}
    for proj in sorted({c["project"] for c in stories}):
        try:
            per_project[proj] = fetch_field_options(proj, "故事")
        except AuthError:
            raise
        except RuntimeError as e:
            errors.append(beneficiary_fetch_failure(f"[项目 {proj}]", e))
    for i, c in enumerate(stories):
        got = per_project.get(c["project"])
        if not got:
            continue
        allowed, disabled = got
        tag = c.get("ref") or f"cards[{i}]"
        v = (c.get("fields", {}).get(BENEFICIARY_FIELD) or {}).get("value")
        if v is None:
            continue  # 缺必填由 STORY_REQUIRED_CF 那段报
        if v in allowed:
            continue
        if v in disabled:
            errors.append(f"{tag}: 受益方(cf_16706)「{v}」线上**已停用**（disabled），建单不收。"
                          f"跑 `beneficiary-options {c['project']}` 看现行选项，"
                          "让产品本人重新选一条并逐字填回。")
            continue
        hit = next((a for a in allowed if normalize(a) == normalize(v)), None)
        if hit:
            errors.append(f"{tag}: 受益方(cf_16706) 填「{v}」空格对不上线上真身「{hit}」"
                          f"（{whitespace_hint(hit, v)}）。Jira 按字面匹配，原样 apply 会报 "
                          "Option id 'null' is not valid 并停在这张卡——从线上选项逐字复制。")
        else:
            errors.append(f"{tag}: 受益方(cf_16706) 的「{v}」**不在线上选项里**（已实时拉取 "
                          f"{len(allowed)} 个）。不许近似、不许自造：跑 "
                          f"`beneficiary-options {c['project']}` 拉全量列表，"
                          "让产品本人从中亲选一条，再逐字填回。")


def check_epics_live(plan, errors, warnings):
    """Epic 建卡前必验：卡号不存在(404)就别建。返回 {key: {summary, type}} 供计划表展示。"""
    keys = {}
    for i, c in enumerate(plan["cards"]):
        k = (c.get("fields") or {}).get(EPIC_FIELD)
        if isinstance(k, str) and k.strip():
            keys.setdefault(k.strip(), []).append(c.get("ref") or f"cards[{i}]")
    if not keys:
        warnings.append(f"没有任何卡填史诗链接({EPIC_FIELD})——Epic 是每批必问项："
                        "确认过「这批卡挂哪个 Epic？（给卡号）」且产品明确说不挂，才可以留空。"
                        "（抽样：多数真卡确实不挂 Epic，「不挂」是正常答复，问过就行。）")
        return {}
    info = {}
    for k, refs in keys.items():
        who = "、".join(refs)
        if not re.match(r"^[A-Z][A-Z0-9]+-\d+$", k):
            errors.append(f"史诗链接「{k}」不像 Jira 卡号（{who}）——Epic 要填卡号，形如 XXX-12345；"
                          "Epic 常挂在别的项目下（CONTRACT/SPOT/OPT/WEB…），项目前缀以产品给的为准。")
            continue
        try:
            f = api("GET", f"/rest/api/2/issue/{k}",
                    params={"fields": "summary,issuetype,status"})["fields"]
            info[k] = {"summary": f.get("summary", ""),
                       "type": (f.get("issuetype") or {}).get("name", "?"),
                       "status": (f.get("status") or {}).get("name", "?")}
            if info[k]["type"] not in ("史诗", "Epic"):
                warnings.append(f"史诗链接「{k}」在 Jira 里的类型是「{info[k]['type']}」不是史诗"
                                f"（{who}）——确认这是产品要挂的 Epic 卡号。")
        except AuthError:
            raise
        except HttpError as e:
            if e.code == 404:
                errors.append(f"史诗链接「{k}」在 Jira 里不存在（HTTP 404，{who}）——卡号写错或卡已删。"
                              "**别建卡**：回去问产品「这批卡挂哪个 Epic？（给卡号；不挂也可以）」，"
                              "不许从主卡/历史/需求名推断。")
            else:
                errors.append(f"史诗链接「{k}」验不了（{e}，{who}）——别猜，确认后再建。")
        except RuntimeError as e:
            errors.append(f"史诗链接「{k}」验不了（{e}，{who}）——别猜，确认后再建。")
    return info


def check_link_targets_live(plan, warnings):
    """把 links 里指向**已有 Jira 卡**的 key 解析成卡名，供计划表按「名称」(卡号) 展示。

    🔴 展示纪律：给产品看的每一张 Jira 卡都要带名称，裸卡号他核不动。
    **只影响展示、不改校验强度**：读不回卡名只 WARN，不拦建卡。
    """
    keys = sorted({l.get(side) for l in plan.get("links", []) for side in ("from", "to")
                   if isinstance(l.get(side), str) and ISSUE_KEY_RE.match(l.get(side))})
    names = {}
    for k in keys:
        try:
            names[k] = api("GET", f"/rest/api/2/issue/{k}",
                           params={"fields": "summary"})["fields"].get("summary", "")
        except (AuthError, NetworkError):
            raise
        except (HttpError, RuntimeError) as e:
            names[k] = ""
            warnings.append(f"链接目标「{k}」读不回卡名（{short_err(e)}）——卡号写错的话 apply "
                            "补链接这一步会失败，确认一下；展示给产品时也补上卡名。")
    return names


def check_versions_live(plan, errors, warnings):
    """fixVersions 必须是该项目线上**真实存在**的版本名（占位版本也一样要对得上）。

    Jira 按版本名匹配，写错直接 400 并停在这张卡。版本表拉不到只记 WARN——
    它不像受益方/Epic 那样是成本归属决策，不值得为一次网络抖动拦住整批建卡。
    """
    want = {}
    for i, c in enumerate(plan["cards"]):
        vs = (c.get("fields") or {}).get("fixVersions")
        if not isinstance(vs, list):
            continue
        for v in vs:
            n = (v or {}).get("name") if isinstance(v, dict) else None
            if isinstance(n, str) and n.strip():
                want.setdefault((c.get("project"), n), []).append(c.get("ref") or f"cards[{i}]")
    if not want:
        return
    live = {}
    for proj in sorted({p for p, _ in want if p}):
        try:
            vs = api("GET", f"/rest/api/2/project/{proj}/versions")
            live[proj] = {v["name"]: v for v in vs if v.get("name")}
        except AuthError:
            raise
        except (HttpError, RuntimeError) as e:
            warnings.append(f"[项目 {proj}] 版本表没能拉到（{e}）——这批的 fixVersions 没核对上；"
                            f"apply 若报版本无效就是这里，届时用 "
                            f"`/rest/api/2/project/{proj}/versions` 对一下版本名。")
    for (proj, name), refs in sorted(want.items()):
        table = live.get(proj)
        if table is None:
            continue
        who = "、".join(r for r in refs if r)
        if not table:
            errors.append(f"{who}: 项目 {proj} 线上一个版本都没有，fixVersions 填不了「{name}」"
                          "——WEB 项目没有版本字段，一张都别填（抽样 28/28 空）。")
            continue
        v = table.get(name)
        if v is None:
            hit = next((k for k in table if normalize(k) == normalize(name)), None)
            if hit:
                errors.append(f"{who}: fixVersions「{name}」空格对不上线上真身「{hit}」"
                              f"（{whitespace_hint(hit, name)}）——整条复制线上版本名。")
            else:
                errors.append(f"{who}: fixVersions「{name}」在项目 {proj} 里不存在"
                              f"（线上共 {len(table)} 个版本）。占位是**分端**的：iOS 卡填 iOS_ 那条、"
                              "Android 卡填 安卓_ 那条、Flutter 卡填 Flutter_ 那条；"
                              "已排期就填真实版本号——一律以线上版本名为准。")
            continue
        if v.get("archived"):
            errors.append(f"{who}: fixVersions「{name}」线上**已归档**，建单不收——换成现行版本。")
        elif v.get("released"):
            warnings.append(f"{who}: fixVersions「{name}」线上已标记为已发布（released）——"
                            "新卡挂一个发布过的版本通常不对，确认一下。")


def validate_plan(plan, online=True):
    """返回 (errors, warnings, live)。

    本地房规校验 + 两处**必须联网**的硬核对：受益方逐字命中线上选项、Epic 卡号确实存在；
    这两处联网核对失败一律记 ERROR（不是 warning）——这两个字段错了都是别人替你埋单。
    外加一处软核对：fixVersions 是否为线上真实版本名（拉不到只 WARN，见 check_versions_live）。
    """
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
        if c.get("summary"):
            # 房规＝一层全角【端】（Noah 2026-08-27 拍板）。无前缀拦、两层与半角只提醒。
            hit = check_summary_prefix(c["summary"])
            if hit:
                (errors if hit[0] == "error" else warnings).append(f"{tag}: {hit[1]}")
        fields = c.get("fields", {})
        for cf, allowed in ENUM_ALLOWED.items():
            v = fields.get(cf)
            if not isinstance(v, dict) or "value" not in v:
                continue
            val = v["value"]
            if val in allowed:
                continue
            label = ENUM_LABELS.get(cf, cf)
            # 空白归一后比对：既抓首尾空格，也抓中间的连续空格（真实选项里两种都出现过）
            hit = next((a for a in allowed if normalize(a) == normalize(val)), None)
            if hit:
                errors.append(f"{tag}: {label}({cf}) 填「{val}」空格对不上，真身是「{hit}」"
                              f"（{whitespace_hint(hit, val)}）。Jira 按字面匹配，原样 apply 会报 "
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
    live = {"epics": {}, "links": {}}
    if online:
        check_beneficiary_live(plan, errors)
        live["epics"] = check_epics_live(plan, errors, warnings)
        live["links"] = check_link_targets_live(plan, warnings)
        check_versions_live(plan, errors, warnings)
    return errors, warnings, live


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
    print("- 选项原文来自**线上实时拉取**（本 kit 不内置受益方枚举）；"
          "要看全量候选跑 `beneficiary-options <项目>`。")


def print_epic_check(plan, epics):
    """Epic 每批必问：这里只把线上读回的卡名摆出来给产品对眼，kit 从不替他选。"""
    groups = {}
    for c in plan["cards"]:
        k = (c.get("fields") or {}).get(EPIC_FIELD)
        if isinstance(k, str) and k.strip():
            groups.setdefault(k.strip(), []).append(c.get("ref"))
    print("\n### Epic 确认（每批必须由产品明确点头——候选可以摆，但不许静默填、不许沿用上次不问）")
    if not groups:
        print("- **未挂 Epic** ← 全部卡。只有产品明确说这批不挂 Epic 才可以这样。")
        print("- 还没问过？先跑 `epic-candidates --from <主卡/历史需求卡号> "
              '--keyword "<需求关键词>" --project APP|WEB` 捞带名称的候选，再让产品选。')
        return
    for k, refs in groups.items():
        info = (epics or {}).get(k)
        # 🔴 展示纪律：一律「名称」(卡号)——裸卡号产品核不动，正是漏挂错挂的来源。
        meta = f" · {info['type']}/{info['status']}" if info else " · （未能读回卡名）"
        print(f"- **{name_key((info or {}).get('summary'), k)}**{meta} "
              f"← {', '.join(r for r in refs if r)}")
    print("- 请产品确认：**这批卡就挂这个 Epic 吗？**（换 Epic 就改 plan 后重新 validate；"
          '只说得出名字就跑 `epic-search --name "<名称片段>"` 解析卡号）')


def print_table(plan, live=None):
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
    print_epic_check(plan, (live or {}).get("epics"))
    if plan.get("links"):
        verbs = {"Blocks": "blocks", "Cloners": "clones", "Relates": "relates to", "Duplicate": "duplicates"}
        names = (live or {}).get("links") or {}

        def side_label(l, side):
            """🔴 展示纪律：本批新建卡显示 ref；指向**已有 Jira 卡**的一律「名称」(卡号)。"""
            ref = l.get(f"{side}_ref")
            if ref:
                return ref
            k = l.get(side)
            return name_key(names.get(k), k) if k else "?"

        print("\n| 链接 | from | to |")
        print("|------|------|----|")
        for l in plan["links"]:
            print(f"| {l['type']}({verbs.get(l['type'], '?')}) "
                  f"| {side_label(l, 'from')} | {side_label(l, 'to')} |")


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
    errors, warnings, _live = validate_plan(plan)
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
        except AuthError:
            raise  # 认证挂了不是「这张卡建不了」：停下走统一出口换 token（下面 finally 照常存盘续传）
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
            except AuthError:
                raise
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


# ------------------------------------------------- 认证配置（密码框归工具持有）
def cmd_setup_token():
    """配置认证：弹系统原生密码框收 token → 进程内直写落盘 → 自动接 whoami 验证。

    这条命令的存在意义是**把取密钥这件事整个折进工具**：AI 只需要跑 `setup-token`，
    既不用拼 osascript、也不用碰 ~/.jira-card-kit/ 里的任何文件，更看不到 token 明文。
    输出契约：第一行只会是 `OK` 或 `CANCELLED`（子进程的原始输出一律不回显）。
    """
    if sys.platform != "darwin":
        print(f"当前平台是 {sys.platform}，没有 macOS 原生密码框。", file=sys.stderr)
        die(TOKEN_TERMINAL_GUIDE)
    try:
        proc = subprocess.run(["/bin/sh", "-c", TOKEN_DIALOG_SCRIPT],
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=600)
    except (OSError, subprocess.SubprocessError) as e:
        print(f"密码框没跑起来（{type(e).__name__}）。", file=sys.stderr)
        die(TOKEN_TERMINAL_GUIDE)
    # 🔴 只认这两个字面量，子进程的 stdout/stderr 原文一概不打印——密钥通道上不留回显口子。
    out = (proc.stdout or b"").decode(errors="replace").strip()
    if proc.returncode != 0 or out not in ("OK", "CANCELLED"):
        print(f"密码框没跑起来（osascript 退出码 {proc.returncode}；"
              "常见原因：无 GUI 会话 / 远程终端 / 沙箱拦 osascript / 未授权自动化）。",
              file=sys.stderr)
        die(TOKEN_TERMINAL_GUIDE)
    if out == "CANCELLED":
        print("CANCELLED", flush=True)
        print("（用户点了取消或没填，什么都没写。要配就再跑一次 "
              "`python3 scripts/jira_cards.py setup-token`。）")
        sys.exit(1)

    print("OK", flush=True)
    if not os.path.exists(TOKEN_FILE):
        die(f"密码框回了 OK，但 {TOKEN_FILE} 不在——磁盘权限或 HOME 有问题，修好后重跑 setup-token。")
    try:
        os.chmod(TOKEN_FILE, 0o600)
    except OSError as e:
        print(f"WARN: {TOKEN_FILE} 改权限失败（{e}）——请手动 chmod 600。", file=sys.stderr)
    if os.environ.get("JIRA_PAT") or os.environ.get("JIRA_PERSONAL_TOKEN"):
        print(f"WARN: 环境变量 JIRA_PAT / JIRA_PERSONAL_TOKEN 存在，读取顺序上它优先于刚写的 "
              f"{TOKEN_FILE}；下面这次验证走的是环境变量那个。", file=sys.stderr)
    # 存量凭据清理：settings.json 里那份迁移后**永不再被使用、但依然有效**，且躺在 AI 日常会
    # 整份打开的文件里。只判键在不在（.keys()），值不进任何变量、不进任何输出。
    if os.path.exists(SETTINGS_JSON):
        try:
            env_keys = set((json.load(open(SETTINGS_JSON)).get("env") or {}).keys())
            if {"JIRA_PAT", "JIRA_PERSONAL_TOKEN"} & env_keys:
                print(f"WARN: 你的 Jira PAT 还留在 {SETTINGS_JSON} 的 env 块里——那是 AI 日常会"
                      "整份打开的文件。请手工删掉该键，并去 Jira 把它撤销（Revoke）重建一个，"
                      "再跑一次 setup-token。（AI 不要代读该文件确认，删完重跑本命令、本条 "
                      "WARN 消失即为成功。）", file=sys.stderr)
        except (json.JSONDecodeError, OSError):
            pass
    try:
        me = api("GET", "/rest/api/2/myself")
    except AuthError as e:
        die(f"token 已落盘，但验证没过（HTTP {e.code}）：多半是复制时少了几位，"
            "或页面上那个 token 已经失效/被撤销。让用户回 Jira 页面重新复制一次（或重新 "
            "Create 一个），再跑一遍 `setup-token`。**别让他把 token 贴进对话**。")
    print(f"配置成功，当前用户：{me['displayName']}（{me['name']}）"
          f"{'  ' + me.get('emailAddress', '') if me.get('emailAddress') else ''}")


# ------------------------------------------------- 本机配置（AI 读写的唯一入口）
# config.json 里**永远不放凭据**：这些键一律拒收，免得有人把 token 塞进会被转发的文件。
# ⚠️ `pat` 不加 \b：`_` 是 word 字符，`\bpat\b` 匹配不到 kit **自己的规范变量名** JIRA_PAT /
# jira_pat（2026-08-28 审计实测漏放行）。宁可误伤 `pattern` 这类键——config 里本就不该有。
SECRETISH_KEY_RE = re.compile(
    r"token|secret|password|passwd|credential|cookie|api_?key|pat|bearer|auth", re.I)
CONFIG_REDACTED = "<已屏蔽·凭据不该出现在 config 里，请删掉这个键>"


def load_config():
    if not os.path.exists(CONFIG_FILE):
        return {}
    try:
        data = json.load(open(CONFIG_FILE))
    except json.JSONDecodeError as e:
        die(f"{CONFIG_FILE} 不是合法 JSON（{e}）——请用户自己打开修一下，AI 别去读这个文件。")
    except OSError as e:
        die(f"读不了 {CONFIG_FILE}：{e}")
    if not isinstance(data, dict):
        die(f"{CONFIG_FILE} 顶层必须是对象")
    return data


def redacted(data):
    """输出前抹掉任何凭据形态的键——config 走工具外显，但绝不当凭据的搬运工。"""
    if isinstance(data, dict):
        return {k: (CONFIG_REDACTED if SECRETISH_KEY_RE.search(str(k)) else redacted(v))
                for k, v in data.items()}
    if isinstance(data, list):
        return [redacted(x) for x in data]
    return data


def cmd_config_show():
    """打印本机配置。**AI 读 config 的唯一入口**——禁止直接 cat ~/.jira-card-kit/config.json。"""
    if not os.path.exists(CONFIG_FILE):
        print(f"（还没有 {CONFIG_FILE}——首跑时问用户、再用 "
              "`config-set <键> <值>` 写入即可。）")
        return
    print(json.dumps(redacted(load_config()), ensure_ascii=False, indent=2))


def cmd_config_set(key, value):
    """只合并**指定的那一个键**写回 config.json，其余键原样保留。

    键支持 `a.b` 嵌套（如 `tracking_assignees.review`）。**AI 写 config 的唯一入口**——
    禁止自己读出来改完再整份写回（那既违反「不碰 ~/.jira-card-kit/」，也会把别人的键写丢）。
    """
    if not re.match(r"^[A-Za-z_][A-Za-z0-9_]*(\.[A-Za-z_][A-Za-z0-9_]*)*$", key):
        die(f"键名「{key}」不合法：只允许字母/数字/下划线，嵌套用点，如 tracking_assignees.review")
    parts = key.split(".")
    if any(SECRETISH_KEY_RE.search(p) for p in parts):
        die("🔴 config.json 里不放任何凭据（这个文件会被转发给同事）。"
            "Jira token 只走 `setup-token` 写进单独的 600 文件，别往配置里塞。")
    data = load_config()
    node = data
    for p in parts[:-1]:
        nxt = node.get(p)
        if not isinstance(nxt, dict):
            nxt = {}
            node[p] = nxt
        node = nxt
    old = node.get(parts[-1])
    node[parts[-1]] = value
    try:
        os.makedirs(KIT_DIR, exist_ok=True)
        with open(CONFIG_FILE, "w") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            f.write("\n")
        os.chmod(CONFIG_FILE, 0o600)
    except OSError as e:
        die(f"写不了 {CONFIG_FILE}：{e}")
    print(f"已写入 {CONFIG_FILE}：{key} = {value}"
          + (f"（原值 {old}）" if old is not None and old != value else ""))
    print(json.dumps(redacted(data), ensure_ascii=False, indent=2))


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


def cmd_beneficiary_options(project, sample_key=None):
    """打印受益方(cf_16706)的**线上**选项原文，供产品本人从中亲选。

    kit 不内置枚举：此 skill 全组产品共用、各人受益方不同，任何内置默认值都会诱导错填。
    """
    try:
        opts, disabled = fetch_field_options(project, "故事", sample_key=sample_key)
    except AuthError:
        raise  # 认证失败走统一出口（去 setup-token 换密钥），别降级成「拉不到选项」
    except RuntimeError as e:
        die(beneficiary_fetch_failure(f"[项目 {project}]", e))
    print(f"## 受益方(cf_16706) 线上选项 · 项目 {project} · 共 {len(opts)} 条（实时拉取）")
    for i, o in enumerate(opts, 1):
        flag = "   ⚠️ 含连续/首尾空格，务必整条复制" if normalize(o) != o else ""
        print(f"{i:3d}. {o}{flag}")
    if disabled:
        print(f"\n（另有 {len(disabled)} 条线上已停用、建单不收，故不列出）")
    print("\n🔴 让**产品本人**从上面挑一条（可按前缀分组分批问），选中后逐字复制进 plan；"
          "AI 不许代选、不许按历史高频值给默认、不许从 Epic/需求名/主卡推断。"
          "选定后把确认人写进 plan.meta.beneficiary_confirmed_by、依据写进 beneficiary_rationale。")


# --------------------------------------------- Epic 候选检索（只读，供产品用名字选）
# 🔴 定位：本节的两条命令**只产出候选**，不产出决定。Epic 是每批必问的硬闸——
#    候选可以来自主卡 / 历史关联需求 / 上次用过的值，但**必须由产品明确确认才能填进 plan**；
#    「禁推断」禁的是**静默填**，不是禁止把线索摆出来给他选（2026-09-02 口径统一）。
# 🔴 展示纪律：凡向产品展示 Jira 卡，一律「名称」(卡号)，禁止裸卡号——裸卡号对产品没有信息量。
EPIC_TYPE_NAMES = ("史诗", "Epic")
# 已收口的状态：优先看 statusCategory.key == "done"（与界面语言无关），名字表只作兜底。
CLOSED_STATUS_NAMES = {"已关闭", "关闭", "已完成", "完成", "已解决", "已上线", "废弃",
                       "Closed", "Done", "Resolved"}
PROJECT_KEY_RE = re.compile(r"^[A-Z][A-Z0-9]*$")
ISSUE_KEY_RE = re.compile(r"^[A-Z][A-Z0-9]+-\d+$")
EPIC_PICK_FOOTER = (
    "\n🔴 **这是候选、不是决定**：把上面的「Epic 名称(卡号)」摆给产品选"
    "（有结构化提问工具就列成选项：top 3 候选 + 「换一个（说名字或卡号都行，我来找）」+ 「本批不挂」），"
    "拿到明确答复才能写进 plan.fields.customfield_10102。\n"
    "🔴 **禁止静默填**：不许因为「主卡挂了它 / 上次就是它」就自己填上去；"
    "产品只说得出名字 → 跑 `epic-search --name \"<名称片段>\"` 解析卡号，**多命中就列出来让他选，不许猜**；"
    "产品说「本批不挂」→ 留空，这是多数派答复，别追问。")


def short_err(e):
    """错误摘要：HttpError 只留状态码（服务端 detail 又长又对产品没用），其余原样。"""
    code = getattr(e, "code", None)
    return f"HTTP {code}" if code else str(e)


def jql_quote(s):
    """把任意文本包成 JQL 字符串字面量（转义反斜杠与双引号）。"""
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'


def status_closed(status):
    """Epic 是否已收口（已关闭/已完成/废弃）——这类不该再往上挂新卡，排到候选末尾。"""
    cat = (status or {}).get("statusCategory") or {}
    if cat.get("key") == "done":
        return True
    return (status or {}).get("name") in CLOSED_STATUS_NAMES


_AUTH_PROBED = []


def assert_auth_ok():
    """400 的兜底分诊：拿一次 `/myself` 确认这不是**认证**问题。每进程只探一次。

    🔴 实测（2026-09-02，凭据无效跑 `epic-search`）：**JQL 检索在 token 失效时回的是 400
    不是 401**——服务端先解析 JQL，匿名身份看不到 `issuetype` 那些名字，于是报"值不存在"。
    照 400 处理就会把认证失败降级成「Epic 检索没跑通」这种含糊错误，正是 `AuthError` 统一
    出口要避免的（含糊错误会诱导 AI 去翻密钥文件排查）。所以撞 400 先探一次身份：
    认证坏了直接抛 AuthError 走统一出口，认证没问题才当真正的 JQL 错误往上抛。
    """
    if _AUTH_PROBED:
        return
    api("GET", "/rest/api/2/myself")
    _AUTH_PROBED.append(True)


def search_issues(jql, fields, limit=10):
    """JQL 检索，返回 (issues, total)。只读。"""
    try:
        data = api("GET", "/rest/api/2/search",
                   params={"jql": jql, "maxResults": limit, "fields": ",".join(fields)})
    except HttpError as e:
        if e.code == 400:
            assert_auth_ok()  # 先分诊认证；没问题才让 400 当 JQL 错误继续往上走
        raise
    return data.get("issues", []), data.get("total", 0)


def epic_link_of(fields):
    """cf_10102 在 Jira 里是**裸字符串卡号**；防御地兼容 dict / None 形态。"""
    v = (fields or {}).get(EPIC_FIELD)
    if isinstance(v, dict):
        v = v.get("key") or v.get("value")
    return v.strip() if isinstance(v, str) and v.strip() else ""


def name_key(summary, key):
    """🔴 展示纪律统一出口：「名称」(卡号)。名称读不回来才退化成占位，绝不只给卡号。"""
    return f"「{summary or '（读不到卡名）'}」({key})"


def fetch_epic_info(keys):
    """对每个 Epic **GET 一次**拿 名称/类型/状态。读不到的照样列出来并标明，绝不编卡名。"""
    info = {}
    for k in keys:
        try:
            f = api("GET", f"/rest/api/2/issue/{k}",
                    params={"fields": "summary,issuetype,status"})["fields"]
            info[k] = {"summary": f.get("summary", ""),
                       "type": (f.get("issuetype") or {}).get("name", "?"),
                       "status": (f.get("status") or {}).get("name", "?"),
                       "closed": status_closed(f.get("status"))}
        except (AuthError, NetworkError):
            raise  # 认证/网络走 main 统一出口，别降级成「读不到卡名」
        except (HttpError, RuntimeError) as e:
            info[k] = {"summary": "", "type": "?", "status": f"读不回（{short_err(e)}）",
                       "closed": False}
    return info


def collect_epic_seeds(from_keys, keywords, project, notes):
    """收种子卡：--from 逐张 GET；--keyword 走 JQL 取同族卡最近 10 张。返回 seeds 列表。"""
    seeds = []
    for k in from_keys:
        if not ISSUE_KEY_RE.match(k):
            notes.append(f"--from「{k}」不像 Jira 卡号（形如 XXX-12345），已跳过")
            continue
        try:
            f = api("GET", f"/rest/api/2/issue/{k}",
                    params={"fields": f"summary,{EPIC_FIELD}"})["fields"]
        except (AuthError, NetworkError):
            raise
        except (HttpError, RuntimeError) as e:
            notes.append(f"--from {k} 读不到（{short_err(e)}）——卡号写错或没权限，已跳过")
            continue
        seeds.append({"key": k, "summary": f.get("summary", ""),
                      "epic": epic_link_of(f), "origin": "from"})
    for kw in keywords:
        jql = (f"project = {project} AND summary ~ {jql_quote(kw)} "
               "ORDER BY created DESC")
        try:
            issues, total = search_issues(jql, ["summary", EPIC_FIELD], 10)
        except (AuthError, NetworkError):
            raise
        except (HttpError, RuntimeError) as e:
            notes.append(f"关键词「{kw}」在项目 {project} 搜不了（{short_err(e)}）——换个词或直接问产品")
            continue
        if not issues:
            notes.append(f"关键词「{kw}」在项目 {project} 没搜到同族卡")
            continue
        notes.append(f"关键词「{kw}」@{project}：命中 {total} 张，取最近 {len(issues)} 张")
        for it in issues:
            f = it.get("fields") or {}
            seeds.append({"key": it.get("key", "?"), "summary": f.get("summary", ""),
                          "epic": epic_link_of(f), "origin": "kw"})
    return seeds


def epic_candidate_rank(groups, info, k):
    """候选排序键（模块级纯函数，便于单测）：

    ① 只由 `last_epic` 带出来的（groups 里没有关联卡）**一律排最后**——"上次顺手"不是"这批该挂"；
    ② **已收口的 Epic 再往后压**（哪怕关联卡更多），它们不该再接新卡；
    ③ 其余按关联卡数降序；④ 同数时**主卡(--from)带出来的**优先（主卡是这个需求自己的卡，
       信号比同族历史卡强）；⑤ 再同就按卡号稳定排序。
    """
    g = groups.get(k)
    weight = len(g["from"]) + len(g["kw"]) if g else 0
    return (0 if g else 1, 1 if info[k]["closed"] else 0, -weight,
            0 if (g and g["from"]) else 1, k)


def epic_candidate_why(groups, last, k):
    """候选的「依据」列：说清这个 Epic 是**从哪张卡捞出来的**，产品才判断得了。

    🔴 展示纪律：这里出现的每张卡都走 name_key()，一律「名称」(卡号)。
    """
    g = groups.get(k) or {"from": [], "kw": []}
    bits = []
    for s in g["from"][:2]:
        bits.append("主卡" + name_key(s["summary"], s["key"]) + "挂它")
    if len(g["from"]) > 2:
        bits.append(f"另有 {len(g['from']) - 2} 张给定卡挂它")
    if g["kw"]:
        head = g["kw"][0]
        tail = f" 等 {len(g['kw'])} 张" if len(g["kw"]) > 1 else ""
        bits.append("历史需求" + name_key(head["summary"], head["key"]) + tail + "挂它")
    if k == last:
        bits.append("上次用的（last_epic）")
    return "；".join(bits) or "—"


def cmd_epic_candidates(from_keys, keywords, project):
    """从主卡 / 历史关联需求 / 同族卡里**捞出 Epic 候选**，带名称、依据、状态摆给产品选。

    只读、不写任何东西。首选候选来自**关联需求实际挂的 Epic**；配置里的 `last_epic`
    只作**末位**候选（标「上次用的」）——它是"上次顺手"，不是"这批该挂"。
    """
    notes = []
    seeds = collect_epic_seeds(from_keys, keywords, project, notes)
    groups = {}
    for s in seeds:
        if s["epic"]:
            groups.setdefault(s["epic"], {"from": [], "kw": []})[s["origin"]].append(s)

    last = str(load_config().get("last_epic") or "").strip()
    if last and not ISSUE_KEY_RE.match(last):
        last = ""  # config.example 里的占位符 <上次用过的…> 不当候选
    order = list(groups)
    if last and last not in order:
        order.append(last)

    for n in notes:
        print(f"· {n}")
    hung = sum(1 for s in seeds if s["epic"])
    print(f"\n扫描种子卡 {len(seeds)} 张（--from {len(from_keys)} 张 / 关键词 {len(keywords)} 个），"
          f"其中 {hung} 张挂了 Epic。")

    if not order:
        print("\n## Epic 候选：**未找到关联 Epic**")
        print("- 一张种子卡都没读到（卡号/关键词都没命中），本机 `last_epic` 也没有可用值。"
              if not seeds else
              "- 上面这些种子卡一张都没挂 Epic，本机 `last_epic` 也没有可用值。")
        print("- 🔴 **不编**：直接问产品「这批卡挂哪个 Epic？（说名字或卡号都行，我来找卡号；"
              "不挂也可以）」——抽样里多数真卡本来就不挂 Epic，「不挂」是完全正常的答复。")
        print("- 产品给了名字 → 跑 `epic-search --name \"<名称片段>\"` 把名字解析成卡号。")
        return

    info = fetch_epic_info(order)
    order.sort(key=lambda k: epic_candidate_rank(groups, info, k))
    print(f"\n## Epic 候选（{len(order)} 个 · 按关联卡数排序 · 只读检索）")
    print("\n| # | Epic 名称 | 卡号 | 依据 | 状态 |")
    print("|---|-----------|------|------|------|")
    for i, k in enumerate(order, 1):
        it = info[k]
        st = it["status"] + ("  🔴 已收口，不建议" if it["closed"] else "")
        if it["type"] not in EPIC_TYPE_NAMES and it["type"] != "?":
            st += f"  ⚠️ 类型是「{it['type']}」不是史诗"
        print(f"| {i} | {it['summary'] or '（读不回卡名）'} | {k} "
              f"| {epic_candidate_why(groups, last, k)} | {st} |")
    print(EPIC_PICK_FOOTER)


def cmd_epic_search(name, project=None):
    """按**名称片段**找 Epic，返回 名称|卡号|状态 ≤10 条——让产品用名字回答，卡号由工具找。"""
    types = ", ".join(jql_quote(t) for t in EPIC_TYPE_NAMES)
    # 这台实例的史诗类型名可能是中文「史诗」或英文 Epic：先按 in(...) 试，
    # 400（该实例没有其中某个类型名）就退回逐个试，别让产品为此改问法。
    clauses = [f"issuetype in ({types})"] + [f"issuetype = {jql_quote(t)}" for t in EPIC_TYPE_NAMES]
    issues, total, last_err = None, 0, None
    for c in clauses:
        jql = c + f" AND summary ~ {jql_quote(name)}"
        if project:
            jql = f"project = {project} AND " + jql
        jql += " ORDER BY created DESC"
        try:
            issues, total = search_issues(jql, ["summary", "status"], 10)
            break
        except (AuthError, NetworkError):
            raise
        except HttpError as e:
            if e.code == 400:
                last_err = e
                continue
            raise
    if issues is None:
        die(f"Epic 检索没跑通（{short_err(last_err)}）——名称片段换短一点重试，或请产品直接给卡号。")
    scope = f"项目 {project} " if project else ""
    print(f"## Epic 检索 · {scope}名称含「{name}」· 命中 {total} 条"
          + (f"，列前 {len(issues)} 条" if total > len(issues) else ""))
    if not issues:
        print("\n- **一条都没搜到**。🔴 别猜卡号：换个更短的名称片段再搜；"
              "还搜不到就请产品直接给卡号，或确认这批「不挂 Epic」。")
        return
    print("\n| # | Epic 名称 | 卡号 | 状态 |")
    print("|---|-----------|------|------|")
    for i, it in enumerate(issues, 1):
        f = it.get("fields") or {}
        st = (f.get("status") or {}).get("name", "?")
        if status_closed(f.get("status")):
            st += "  🔴 已收口，不建议"
        print(f"| {i} | {f.get('summary', '')} | {it.get('key', '?')} | {st} |")
    if len(issues) > 1:
        print("\n🔴 **多命中不许猜**：把上面这几条「名称(卡号)」原样列给产品，让他指一条；"
              "他指完才写进 plan。")
    if total > len(issues):
        print(f"🔴 命中 {total} 条、只列了 {len(issues)} 条：**别在没列全的表上替产品选**，"
              "让他把名称片段说得更具体一点再搜一次。")


def cmd_set_beneficiary(value, keys, apply_it):
    """修正受益方。默认 dry-run；--apply 才写入。只碰 cf_16706 这一个字段。"""
    meta = api("GET", f"/rest/api/2/issue/{keys[0]}/editmeta")
    field = meta.get("fields", {}).get(BENEFICIARY_FIELD)
    if not field:
        die(f"{keys[0]} 上没有受益方字段（或无编辑权限）")
    allowed = [x.get("value") for x in field.get("allowedValues", [])]
    if allowed and value not in allowed:
        hit = next((a for a in allowed if a and normalize(a) == normalize(value)), None)
        if hit:
            die(f"「{value}」空格对不上线上真身「{hit}」（{whitespace_hint(hit, value)}）——整条复制线上原文重跑。")
        print(f"ERROR: 「{value}」不在线上允许值里。候选（实时读自 {keys[0]}）：", file=sys.stderr)
        for a in allowed:
            print(f"  {a}", file=sys.stderr)
        die("受益方取值必须与线上允许值逐字一致，且该值须由产品本人确认，不许近似着改")

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
        except AuthError:
            raise
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
        except AuthError:
            raise
        except RuntimeError as e:
            print(f"  {k}: FAILED {e}", file=sys.stderr)


def pop_flag_values(rest, flag):
    """把 rest 里所有 `--flag <值>` 取出来（**可重复**），返回 (值列表, 剩余参数)。"""
    vals, out, i = [], [], 0
    while i < len(rest):
        if rest[i] == flag:
            if i + 1 >= len(rest):
                die(f"{flag} 后面要跟一个值")
            vals.append(rest[i + 1])
            i += 2
        else:
            out.append(rest[i])
            i += 1
    return vals, out


def dispatch(args):
    if not args:
        print(__doc__)
        sys.exit(0)
    cmd = args[0]
    if cmd == "setup-token":
        cmd_setup_token()
    elif cmd == "config-show":
        cmd_config_show()
    elif cmd == "config-set":
        if len(args) < 3:
            die("用法: config-set <键> <值>（键支持 a.b 嵌套，如 tracking_assignees.review）")
        cmd_config_set(args[1], args[2])
    elif cmd == "whoami":
        cmd_whoami()
    elif cmd == "user-search":
        if len(args) < 2:
            die("用法: user-search <关键词>")
        cmd_user_search(args[1])
    elif cmd == "beneficiary-options":
        rest = args[1:]
        sample = None
        if "--issue" in rest:
            i = rest.index("--issue")
            if i + 1 >= len(rest):
                die("--issue 后面要跟一张同项目同类型的卡号（createmeta 拉不到时的兜底）")
            sample = rest[i + 1]
            rest = rest[:i] + rest[i + 2:]
        cmd_beneficiary_options(rest[0] if rest else "APP", sample)
    elif cmd == "epic-candidates":
        froms, rest = pop_flag_values(args[1:], "--from")
        kws, rest = pop_flag_values(rest, "--keyword")
        projs, rest = pop_flag_values(rest, "--project")
        if rest:
            die(f"epic-candidates 不认识的参数：{' '.join(rest)}。"
                '用法: epic-candidates [--from KEY1,KEY2] [--keyword "词"…] [--project APP|WEB]')
        keys = [k.strip().upper() for v in froms for k in v.split(",") if k.strip()]
        if not keys and not kws:
            die('用法: epic-candidates [--from KEY1,KEY2] [--keyword "词"…] [--project APP|WEB]\n'
                "两路可同时给：--from 是主需求卡/背景简报里的历史需求卡号（逗号分隔，可重复给）；"
                "--keyword 是需求关键词/模块名（可重复给，配 --project 取同族卡）。")
        project = (projs[-1] if projs else "APP").upper()
        if kws and not PROJECT_KEY_RE.match(project):
            die(f"--project「{project}」不是项目 key（大写字母数字，如 APP / WEB）")
        if kws and not projs:
            print("· 没给 --project，关键词按默认项目 APP 检索（WEB/H5 需求记得加 --project WEB）")
        cmd_epic_candidates(keys, kws, project)
    elif cmd == "epic-search":
        names, rest = pop_flag_values(args[1:], "--name")
        projs, rest = pop_flag_values(rest, "--project")
        if rest:
            die(f"epic-search 不认识的参数：{' '.join(rest)}。"
                '用法: epic-search --name "名称片段" [--project APP|WEB]')
        if not names:
            die('用法: epic-search --name "名称片段" [--project APP|WEB]\n'
                "（产品只说得出 Epic 名字时用它把名字解析成卡号；Epic 常挂在别的项目下，"
                "**默认不限项目**，别急着加 --project。）")
        project = projs[-1].upper() if projs else None
        if project and not PROJECT_KEY_RE.match(project):
            die(f"--project「{project}」不是项目 key（大写字母数字，如 APP / WEB）")
        cmd_epic_search(names[-1], project)
    elif cmd == "validate":
        if len(args) < 2:
            die("用法: validate <plan.json>")
        plan = load_plan(args[1])
        errors, warnings, live = validate_plan(plan)
        print_table(plan, live)
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
        die(f"未知命令 {cmd}。可用: setup-token / whoami / config-show / config-set / "
            f"user-search / beneficiary-options / epic-candidates / epic-search / "
            f"validate / apply / show-result / set-beneficiary / discard")


def main():
    """认证失败 / 网络不通的统一出口：任何命令、任何调用层次上的 401/403 与 URLError
    都收口成同一句话（不吐 traceback——裸调用栈会把 AI 推进"排障模式"，禁令就白写了）。"""
    try:
        dispatch(sys.argv[1:])
    except AuthError as e:
        print(auth_failure_message(e.code), file=sys.stderr)
        sys.exit(1)
    except NetworkError as e:
        print(str(e), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
