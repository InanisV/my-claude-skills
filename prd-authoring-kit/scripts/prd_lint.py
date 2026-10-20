#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# PRD Authoring Kit · © Noah Zhan (@noah.zhan) · 二次分发/衍生须保留署名，不得标榜为自己原创创作。LICENSE / NOTICE 见根目录。
"""PRD 确定性 lint —— 把 05 步骤 0 里能机械化的检查打成 FAIL / WARN / INFO 事实表。

执行而非阅读：`python3 scripts/prd_lint.py <md>`
用法：python3 scripts/prd_lint.py <PRD.md> [--json] [--profile standard|light]
输入：kit 起草稿 `PRD-<需求名>.md`，或 `lark-cli docs +fetch --doc-format markdown` 导出的正文。

本脚本只测事实、不做判断；WARN 要模型按 05 判，FAIL 必须修；每条 FAIL 的修法指回 kit 节。
- FAIL = 确定性规则命中，必须修；WARN = 启发式命中，模型按 05 逐条判；INFO = 只给事实，抄进报告；OK = 未命中。
- 退出码：有 FAIL → 1；否则 0；参数 / 读文件错误 → 2。--json 输出与表格同构。
- `--profile light`：L01 只要求 功能需求 / 验收标准 / Data Requirements 三章，其余检查不变。
- 只用标准库、Python 3.9 兼容；不读网络、不碰飞书 / Jira。

口径细节（与 kit 规则对齐，免得误伤）：
- 稿型自动判定：首个非空行是 `<title>` 或全文含 `<whiteboard token=` → 导出稿；否则起草稿。起草稿里第一个 `# ` 之前的说明块
  （06 净化会丢掉）不参与检查；起草稿里的 ```mermaid fence 是画板载体（导入自动转），L02 只把引用块 / 缩进内的 fence 与
  「mermaid 文本供 / 源码」说明句算残留；导出稿里所有 mermaid 代码块都算残留。
- 已是模板残留的行（`> 【指引` 行、`Kit 自查清单` 节）只由 L02 报，其余检查跳过，免得一处残留报五遍。
- L03：「见待确认 #N」这类编号引用、埋点表里的【待确认】标注不算裸挂。
- L09：反引号内容含 `=` / `×` / `÷` 视为公式（05 ⑥b 豁免）。
- L10：「显著 / 交互效应…」与 LaTeX 只扫成功指标节（05 ③：别扩到全文）。
- L13：链接 URL（`[文字](url)`、href / src / path 属性、`<img>`、`![](路径)`）里的坐标与路径不算——07 §三 允许坐标只活在链接里，
  图片载体不是正文文字。
- 读者负荷（05 步骤 4 体量预算）：L19 正文 >12000 CJK → WARN；L22 只数验收章 `- [ ]` 那一行的 CJK（续行不计）；L23 数编写记录章
  表格数据行（「版本历史」章不算）；L24 数埋点章非表格行（含章标题）的 CJK，链接本身（锚文本 + URL）与画板源码不计、同行其余文字照计。
- L25：同义词合并计段（登录/登录失效、切账号/切换账号、前后台/回前台/切后台、系统返回/返回手势、断网——对应全局口径表的行）；
  段 = `### US-R` 标题到下一个 US-R / 二级 / 一级标题，验收章里的 US-R 不算段。
- L26：说明格带沿用词、bullet ≥3，且 ≥2 条 bullet 讲沿用才报——金标里一条「复用现有组件」夹在新行为中间，正是该有的一句引用。
"""

import argparse
import bisect
import html
import json
import re
import sys
from collections import Counter

# ---------------------------------------------------------------- 常量与正则

SEV_RANK = {'FAIL': 3, 'WARN': 2, 'INFO': 1}

FIX = {
    'L01': '按 02 模板补齐具名章；验收标准须 # 顶级独立成章',
    'L02': '按 06 §净化：删指引行、填完占位、删自查清单与裸 mermaid',
    'L03': '按 05 步骤0 ⑭ 分诊：问掉 / 自决 / 写成「由 X 新增提供 Y（待联调）」',
    'L04': '按 01 §0.5 删自律动词句，只写系统做什么',
    'L05': '按 05 步骤0 ⑫ 拆成列表或小表（段≤3 行、≤1 个「；」）',
    'L06': '按 05 步骤0 ⑮ 每处补出处（PRD / 接口 / 线上页），补不出进推断申报',
    'L07': '按 02 原型格口径 / 06 ②：原型格只放图、一格一图，缺图写进简报',
    'L08': '按 09 §5：module 填由数分定值、页面描述单值、jira_id 只一个',
    'L09': '按 07 §二 / 05 ⑥a⑥b：UI 文案用中文「」，去反引号与英文引号',
    'L10': '按 02 成功指标指引 / 05 四把闸：从简 1 行，口径写分子分母周期',
    'L11': '按 02 复述上限：定义处 1 + 验收 1，其余删或写「见 X」',
    'L12': '按 10 §双向闭环：正文「」词条与词条表互相补齐，删未用词条',
    'L13': '按 07 §三：删屏号 / node-id / 本机路径，设计稿用截图或带锚文本链接',
    'L14': '按 07 §三：删 AI 味词，列表项去句尾「；」，→ 改编号步骤',
    'L15': '按 07 §四 用词表：计量单位全文定一种',
    'L16': '按 07 §五 第 10 条：一图 ≤12 节点、每泳道 ≤7 框，超了拆图',
    'L17': '按 05 步骤0 ⑨d：US 角色改业务真人，机制降为占位或删',
    'L18': '按 02 验收指引：每 US-R 一节、一行只验一件事、≤8 行',
    'L19': '超金标 1.4×：回 01 §0.5 决策点测试删常识、改规则表，不是删字',
    'L20': '按 07 §三 自造缩略语：展开成完整句或紧跟一个例子',
    'L22': '按 02 验收指引：每条 ≤60 字只写判定，构造步骤归 QA',
    'L24': '按 09 §6：表外只留平台链接与口径小表，分析方法不进 PRD',
    'L27': '按 01 §0.5：正面陈述一句一事，否定只留决策',
    'L28': '按 02 需求逻辑指引：段落改规则表 条件|行为|用户看到',
    'L25': '按 02 全局口径节：平台规则只写一处，US-R 内写「见全局口径」',
    'L26': '按 02 规则细则指引 / 05 ⑬：沿用行为一句引用，别展开',
}

NAMES = {
    'L01': '章节骨架', 'L02': '模板残留', 'L03': '待确认', 'L04': 'AI 自律动词', 'L05': '表外散文',
    'L06': '沿用 / 复用出处', 'L07': '原型格', 'L08': '埋点表', 'L09': 'UI 文案形态', 'L10': '成功指标',
    'L11': '复述', 'L12': '词条差集', 'L13': '机器坐标 / 本机路径', 'L14': '措辞与排版', 'L15': '计量单位混用',
    'L16': '图密度', 'L17': 'US 角色红线', 'L18': '验收', 'L19': '体量', 'L20': '自造缩略语',
    'L22': '验收条长度', 'L24': '埋点章表外文字', 'L27': '否定句密度', 'L28': '需求逻辑散文', 'L25': '平台规则跨 US-R 复读', 'L26': '沿用行为展开',
}

RE_HEADING = re.compile(r'^ {0,3}(#{1,6})\s+(.*?)\s*#*\s*$')
RE_FENCE_OPEN = re.compile(r'^(\s*(?:>\s*)*)(`{3,}|~{3,})\s*([A-Za-z0-9_+-]*)\s*$')
RE_FENCE_CLOSE = re.compile(r'^\s*(`{3,}|~{3,})\s*$')
RE_QUOTE_PREFIX = re.compile(r'^\s*(?:>\s*)+')
RE_PIPE_ROW = re.compile(r'^\s*(?:>\s*)*\|')
RE_PIPE_SEP = re.compile(r'^\s*\|?\s*:?-+:?\s*(?:\|\s*:?-+:?\s*)*\|?\s*$')
RE_PIPE_SPLIT = re.compile(r'(?<!\\)\|')
RE_HR = re.compile(r'^\s*(?:(?:-\s*){3,}|(?:\*\s*){3,}|(?:_\s*){3,})$')
RE_LIST = re.compile(r'^\s*(?:[-*+]|\d{1,3}[.)]|\d{1,3}、)\s+')
RE_LIST_NUM = re.compile(r'^\s*(\d{1,3})[.)、]\s+')
RE_CHECKBOX = re.compile(r'^\s*[-*+]\s+\[[ xX]\]')
RE_TAG = re.compile(r'<[^>]+>')
RE_BR = re.compile(r'<br\s*/?>', re.I)
RE_TR = re.compile(r'<tr\b[^>]*>', re.I)
RE_TR_END = re.compile(r'</tr\s*>', re.I)
RE_CELL_OPEN = re.compile(r'<(td|th)\b([^>]*)>', re.I)
RE_CELL_CLOSE_TAIL = re.compile(r'</t[dh]\s*>\s*$', re.I)
RE_ROWSPAN = re.compile(r'rowspan\s*=\s*["\']?(\d+)', re.I)
RE_COLSPAN = re.compile(r'colspan\s*=\s*["\']?(\d+)', re.I)
RE_LI = re.compile(r'<li\b[^>]*>(.*?)(?=<li\b|</li>|<ul\b|<ol\b|</ul>|</ol>|$)', re.I | re.S)
RE_IMG = re.compile(r'<img\b|!\[', re.I)
RE_CJK = re.compile(r'[一-鿿]')
RE_US_R_ID = re.compile(r'US\s*(\d+)\s*[-‐‑–—－]\s*R\s*(\d+)', re.I)
RE_US_HEADING = re.compile(r'^\s*US\s*\d+', re.I)

# L01
RE_SEC_LOG = re.compile(r'编写记录')
RE_SEC_BG = re.compile(r'Background|背景')
RE_SEC_METRIC = re.compile(r'成功指标')
RE_SEC_SCOPE = re.compile(r'需求范围')
RE_SEC_DEPS = re.compile(r'需求关联方|关联方与依赖')
RE_SEC_FR = re.compile(r'(?<!非)功能需求|核心功能')
RE_SEC_US_ONLY = re.compile(r'User\s*Stories', re.I)
RE_SEC_AC = re.compile(r'验收标准')
RE_SEC_AC_POINTER = re.compile(r'见.{0,8}验收标准')
RE_SEC_DATA = re.compile(r'Data\s*Requirements|数据与埋点|数据需求|埋点', re.I)
RE_SEC_LOC = re.compile(r'Localisation|Localization|本地化', re.I)
RE_NO_TRACKING = re.compile(r'无需埋点|无埋点|不需要埋点|不涉及埋点')
RE_SEC_PENDING = re.compile(r'待确认')
RE_SEC_KIT = re.compile(r'Kit\s*自查清单')

# L02
RE_FILL = re.compile(r'[（(]填写[：:]')
RE_GUIDE = re.compile(r'【指引')
RE_MERMAID_PROSE = re.compile(r'mermaid\s*(?:文本|源码|代码)\s*供|以下为\s*mermaid|mermaid\s*源码', re.I)

# L03
RE_PENDING = re.compile(r'待确认|待定|待对齐|待补|上线前对齐|后续确认|\bTBD\b')
RE_PENDING_REF = re.compile(r'(?:见|详见|参见)?\s*【?待确认】?\s*(?:#|＃|第)\s*\d+\s*条?')
RE_PENDING_OK_A = re.compile(r'由.{1,20}提供')
RE_PENDING_OK_B = re.compile(r'待联调')

# L04
RE_SELF = re.compile(r'不宣称|不声称|不虚报|不伪称|不冒充|不补造|宣称|虚报|伪称|补造')
RE_SELF_SOFT = re.compile(r'不猜测|不盲目|不静默')  # 否定本身可能就是规则（「不静默补发」）→ WARN 交模型判

# L06
RE_REUSE = re.compile(r'沿用|复用|现有|既有')
RE_REUSE_CLUE = re.compile(r'http|「|US\d|[A-Z]{2,}-\d+|接口|见')

# L09
RE_CODE_SPAN = re.compile(r'(`+)(.+?)\1')
RE_CODE_TAG = re.compile(r'<code>(.*?)</code>', re.I | re.S)
RE_CN_QUOTE = re.compile(r'「([^「」\n]{1,80})」')
RE_TWO_LATIN = re.compile(r'[A-Za-z]{2,}\s+[A-Za-z]{2,}')
RE_FORMULA = re.compile(r'=|×|÷')

# L10
RE_METRIC_ANALYSIS = re.compile(r'显著|交互效应|主效应|合并.{0,4}组|分别比较|样本量|检验.{0,6}(?:效应|假设|显著)')
RE_LATEX = re.compile(r'\\frac|(?<!\\)\$[^$]+?(?<!\\)\$')
RE_METRIC_KOU = re.compile(r'分母|分子|周期|/|÷')
RE_METRIC_SWITCH = re.compile(r'覆盖率.{0,6}100%|全部|所有.{0,4}100%')

# L13
RE_MD_IMAGE = re.compile(r'!\[[^\]]*\]\([^)]*\)')
RE_MD_LINK = re.compile(r'\[([^\]]*)\]\([^)]*\)')
RE_IMG_TAG = re.compile(r'<img\b[^>]*>', re.I)
RE_URL_ATTR = re.compile(r'\b(?:href|src|path|url)\s*=\s*(?:"[^"]*"|\'[^\']*\')', re.I)
RE_COORD = re.compile(r'node-id=|(?<![\d:.\-/])\d{2,4}:\d{4,7}(?![\d:])|/Users/|figma\.com/(?:file|design)/', re.I)
RE_PNG = re.compile(r'[^\s"\'()<>「」\[\]，。；、]*\.png\b', re.I)

# L14
RE_AI_WORDS = re.compile(r'值得注意的是|需要指出|综上所述|旨在|赋能|助力|一站式|无缝')
RE_ROUTE_LINE = re.compile(r'^\s*(?:>\s*)*读者路由')

# L15
RE_MS = re.compile(r'毫秒')
RE_SEC = re.compile(r'\d\s*秒')
RE_CODEPOINT = re.compile(r'码点')
RE_CODEUNIT = re.compile(r'码元')
RE_UTF16 = re.compile(r'UTF-?16', re.I)
RE_UNI_CP = re.compile(r'Unicode\s*码点', re.I)

# L16
RE_DIAGRAM_WORD = re.compile(r'画板|流程图|泳道|脑图|mindnote|<whiteboard', re.I)
RE_MM_SKIP = re.compile(r'^\s*(?:%%|classDef\b|class\b|style\b|linkStyle\b|click\b|direction\b|accTitle\b|accDescr\b|title\b|note\b)', re.I)
RE_MM_HEADER = re.compile(r'^\s*(flowchart|graph|stateDiagram(?:-v2)?|sequenceDiagram|classDiagram|erDiagram|journey|gantt|pie|mindmap|timeline|gitGraph|quadrantChart|block-beta)\b', re.I)
RE_MM_EDGE = re.compile(r'<?(?:-{2,}|={2,}|-\.+-|~{3,})[>ox]?')
RE_MM_EDGE_SPLIT = re.compile(r'\s*<?(?:-{2,}|={2,}|-\.+-|~{3,})[>ox]?\s*')
RE_MM_PIPE_LABEL = re.compile(r'\|[^|]*\|')
RE_MM_DASH_LABEL = re.compile(r'(?<![-.=])--(?![->])\s*[^-\n]*?\s*-->')
RE_MM_EQ_LABEL = re.compile(r'(?<![-.=])==(?![=>])\s*[^=\n]*?\s*==>')
RE_MM_DOT_LABEL = re.compile(r'(?<![-.])-\.(?![-.>])\s*[^.\n]*?\s*\.->')
RE_MM_QUOTED = re.compile(r'"[^"]*"')
RE_MM_SHAPES = [re.compile(p) for p in (
    r'\(\[[^\]]*\]\)', r'\[\[[^\]]*\]\]', r'\[\([^)]*\)\]', r'\(\(\([^)]*\)\)\)', r'\(\([^)]*\)\)',
    r'\{\{[^}]*\}\}', r'\[/[^\]]*[/\\]\]', r'\[\\[^\]]*[/\\]\]', r'\[[^\]]*\]', r'\([^)]*\)', r'\{[^}]*\}',
    r'(?<=[A-Za-z0-9_])>[^\]\n]*\]')]
RE_MM_ID = re.compile(r'^([A-Za-z0-9_一-鿿][\w一-鿿.-]*)')
RE_MM_SUBGRAPH = re.compile(r'^\s*subgraph\b\s*(.*)$', re.I)
RE_MM_END = re.compile(r'^\s*end\s*;?\s*$', re.I)
RE_MM_STATE_DECL = re.compile(r'^\s*state\s+(?:""\s+as\s+)?([\w一-鿿]+)', re.I)
RE_MM_SEQ_PART = re.compile(r'^\s*(?:participant|actor)\s+(.+?)(?:\s+as\s+.*)?\s*$', re.I)
RE_MM_SEQ_MSG = re.compile(r'^\s*([^\s:>+-][^:>]*?)\s*(?:-{1,2}>>|-{1,2}>|-{1,2}x|-{1,2}\))\s*[+-]?\s*([^:]+?)\s*:')
MM_KEYWORDS = {'end', 'subgraph', 'flowchart', 'graph', 'direction', 'td', 'tb', 'lr', 'rl', 'bt', 'state'}

# L17
RE_US_ROLE = re.compile(r'作为[^，,]{0,12}(研发|开发|系统|服务|接口|后端|前端)')

# L20
RE_ABBR_SUFFIX = re.compile(r'[号态序位]')
ABBR_BOUNDARY = set('的地得了着过在是和与及或并且而则若按为把被将从对向给让使由于以等每各该本此其这那个条张次种即均都也还就才只仅不没未无非可能会要需应已再又时')
ABBR_NEXT_WORD = set('位置 号码 态度 态势 序列 序幕 位于 位移 号召 号称'.split())
ABBR_UI_STATE = ('登录态', '加载态', '选中态', '禁用态', '默认态', '点击态', '展开态', '收起态', '空态', '失败态', '成功态',
                 '进行中态', '提交中态', '加载中态', '置灰态', '高亮态', '可用态', '编辑态', '预览态', '只读态', '激活态',
                 '异常态', '断网态', '错误态', '正常态', '初始态', '完成态', '审核中态')
ABBR_COMMON = set((
    '状态 形态 空态 动态 常态 姿态 心态 生态 业态 事态 终态 初态 稳态 静态 时态 表态 失态 液态 固态 体态 神态 样态 '
    '编号 序号 账号 信号 符号 型号 括号 问号 引号 逗号 句号 卡号 单号 口号 称号 记号 暗号 等号 加号 减号 冒号 分号 '
    '叹号 顿号 井号 星号 字号 年号 代号 名号 批号 挂号 '
    '排序 顺序 程序 次序 秩序 工序 时序 倒序 正序 升序 降序 有序 无序 乱序 词序 语序 '
    '单位 占位 槽位 到位 首位 末位 尾位 点位 岗位 部位 地位 方位 价位 仓位 档位 席位 数位 职位 定位 就位 归位 '
    '上位 下位 高位 低位 空位 展位 站位 卡位 坑位 机位 各位 每位 两位 几位 个位 十位 百位 千位 '
    '资源位 运营位 广告位 推荐位 小数位 千分位 百分位 分位 省略号 正负号 负号 正号 手机号 订单号 版本号'
).split())

# L23–L26
RE_SEC_HISTORY = re.compile(r'版本历史')
RE_SEC_GLOBAL = re.compile(r'全局口径')
RE_LINKISH = re.compile(r'!?\[[^\]]*\]\([^)]*\)|<a\b[^>]*>.*?</a\s*>|https?://[^\s<>()「」]+', re.I)
RE_US_R_HEAD = re.compile(r'^\s*US\s*\d+\s*[-‐‑–—－]\s*R\s*\d+', re.I)
PLATFORM_TERMS = (('登录', '登录失效'), ('切账号', '切换账号'), ('前后台', '回前台', '切后台'), ('断网',),
                  ('系统返回', '返回手势'))
RE_REUSE_ROW = re.compile(r'沿用|MVP|现有')


# ---------------------------------------------------------------- 文档模型


def _in_ued_slot(lines, i):
    """最近的 #### 小节标题含 UED → 该行属于 UED 设计稿槽（模板允许写「待补」）。"""
    j = i
    while j >= 0:
        s = lines[j].strip()
        if s.startswith('#### '):
            return 'UED' in s.upper()
        if s.startswith('### ') or s.startswith('## ') or s.startswith('# '):
            return False
        j -= 1
    return False

def strip_tags(s):
    s = RE_BR.sub(' ', s)
    s = RE_TAG.sub(' ', s)
    return html.unescape(s)


def cell_text(raw):
    s = RE_BR.sub(' ', raw)
    s = re.sub(r'<li\b[^>]*>', ' ', s, flags=re.I)
    s = RE_TAG.sub(' ', s)
    s = html.unescape(s)
    return re.sub(r'\s+', ' ', s).strip()


def split_pipe(line):
    s = RE_QUOTE_PREFIX.sub('', line).strip()
    if s.startswith('|'):
        s = s[1:]
    if s.endswith('|') and not s.endswith('\\|'):
        s = s[:-1]
    return [c.strip() for c in RE_PIPE_SPLIT.split(s)]


class Doc(object):
    def __init__(self, text):
        text = text.replace('\r\n', '\n').replace('\r', '\n')
        if text.startswith('\ufeff'):
            text = text[1:]
        self.lines = text.split('\n')
        n = len(self.lines)
        self.kind = [None] * n
        self.fences = []
        self.whiteboards = []
        self.html_regions = []
        self._classify()
        self._headings()
        self._kind_of_doc()
        self._tables()
        self._residual()

    # -- 行类型
    def _classify(self):
        lines, kind = self.lines, self.kind
        fence = None
        for i, ln in enumerate(lines):
            if fence is not None:
                kind[i] = 'code'
                body = RE_QUOTE_PREFIX.sub('', ln) if fence['quoted'] else ln
                m = RE_FENCE_CLOSE.match(body)
                if m and m.group(1)[0] == fence['char'] and len(m.group(1)) >= fence['len']:
                    fence['end'] = i
                    self.fences.append(fence)
                    fence = None
                else:
                    fence['body'].append(body)
                continue
            m = RE_FENCE_OPEN.match(ln)
            if m:
                prefix = m.group(1)
                fence = {'start': i, 'end': None, 'char': m.group(2)[0], 'len': len(m.group(2)),
                         'lang': m.group(3).lower(), 'quoted': '>' in prefix,
                         'indent': len(prefix.replace('>', '').expandtabs(4)), 'body': []}
                kind[i] = 'code'
        if fence is not None:
            fence['end'] = len(lines) - 1
            self.fences.append(fence)

        depth, tstart, in_comment, wb, in_math = 0, None, False, None, False
        # 只认真正的标签（反引号里的 `<table>` 不算），且后文要有收尾标签——否则一处字面量会吞掉全文
        tag_low = [RE_CODE_SPAN.sub(' ', ln).lower() if kind[i] != 'code' else '' for i, ln in enumerate(lines)]
        last_table_close = max([i for i, x in enumerate(tag_low) if '</table' in x] or [-1])
        last_comment_close = max([i for i, x in enumerate(tag_low) if '-->' in x] or [-1])
        for i, ln in enumerate(lines):
            if kind[i] == 'code':
                continue
            low = tag_low[i]
            s = ln.strip()
            if in_comment:
                kind[i] = 'comment'
                if '-->' in ln:
                    in_comment = False
                continue
            if s.startswith('<!--'):
                kind[i] = 'comment'
                if '-->' not in s[4:] and last_comment_close > i:
                    in_comment = True
                continue
            if depth > 0 or (re.search(r'<table\b[^>]*>', low) and last_table_close >= i):
                if depth == 0:
                    tstart = i
                depth += low.count('<table') - low.count('</table')
                kind[i] = 'htable'
                if depth <= 0:
                    self.html_regions.append((tstart, i))
                    depth = 0
                continue
            if wb is not None:
                if not s or RE_HEADING.match(ln):
                    self.whiteboards.append(wb)
                    wb = None
                else:
                    kind[i] = 'wb'
                    if '</whiteboard' in ln.lower():
                        wb['body'].append(re.sub(r'</whiteboard\s*>.*$', '', ln, flags=re.I))
                        self.whiteboards.append(wb)
                        wb = None
                    else:
                        wb['body'].append(ln)
                    continue
            if re.search(r'<whiteboard\b', low):
                kind[i] = 'wb'
                tag = re.search(r'<whiteboard\b[^>]*>', ln, re.I)
                attrs = tag.group(0) if tag else ln
                wtype = re.search(r'type\s*=\s*"([^"]*)"', attrs)
                item = {'start': i, 'type': (wtype.group(1).lower() if wtype else ''),
                        'token': 'token=' in attrs, 'body': []}
                rest = ln[tag.end():] if tag else ''
                closed = attrs.rstrip().endswith('/>') or '</whiteboard' in low
                if rest.strip():
                    item['body'].append(re.sub(r'</whiteboard\s*>.*$', '', rest, flags=re.I))
                if closed or item['token']:
                    self.whiteboards.append(item)
                else:
                    wb = item
                continue
            if in_math or s.startswith('$$'):
                kind[i] = 'math'
                if ln.count('$$') % 2 == 1:
                    in_math = not in_math
                continue
        if depth > 0 and tstart is not None:
            self.html_regions.append((tstart, len(lines) - 1))
        if wb is not None:
            self.whiteboards.append(wb)

        last = None
        for i, ln in enumerate(lines):
            if kind[i] is not None:
                last = kind[i]
                continue
            s = ln.strip()
            if not s:
                kind[i] = 'blank'
                continue
            if RE_HEADING.match(ln) and not ln.lstrip().startswith('>'):
                k = 'heading'
            elif RE_PIPE_ROW.match(ln):
                k = 'ptable'
            elif RE_HR.match(ln):
                k = 'hr'
            elif ln.lstrip().startswith('>'):
                k = 'quote'
            elif RE_LIST.match(ln):
                k = 'list'
            elif last == 'list' and len(ln) - len(ln.lstrip(' \t')) >= 2:
                k = 'list'
            elif s.startswith('<'):
                k = 'html'
            else:
                k = 'prose'
            kind[i] = k
            last = k

    # -- 标题与节
    def _headings(self):
        self.headings = []
        for i, ln in enumerate(self.lines):
            if self.kind[i] != 'heading':
                continue
            m = RE_HEADING.match(ln)
            text = re.sub(r'[*`]', '', m.group(2)).strip()
            self.headings.append({'i': i, 'level': len(m.group(1)), 'text': text})
        n = len(self.lines)
        for k, h in enumerate(self.headings):
            end = n - 1
            for h2 in self.headings[k + 1:]:
                if h2['level'] <= h['level']:
                    end = h2['i'] - 1
                    break
            h['end'] = end
        self.first_h1 = next((h['i'] for h in self.headings if h['level'] == 1), None)

    def find_sections(self, regex, levels=None):
        return [h for h in self.headings if (levels is None or h['level'] in levels) and regex.search(h['text'])]

    def _kind_of_doc(self):
        first = next((ln.strip() for ln in self.lines if ln.strip()), '')
        joined = '\n'.join(self.lines)
        basis = []
        if first.lower().startswith('<title'):
            basis.append('首行 <title>')
        if re.search(r'<whiteboard\b[^>]*token=', joined, re.I):
            basis.append('画板 token')
        if re.search(r'<img\b[^>]*\bmime=', joined, re.I):
            basis.append('图片 mime')
        self.export_basis = basis
        self.is_export = bool(basis)
        n = len(self.lines)
        self.preamble = set()
        if not self.is_export and self.first_h1 is not None:
            self.preamble = set(range(0, self.first_h1))
        self.in_body = [self.kind[i] not in ('code', 'comment') and i not in self.preamble for i in range(n)]

    # -- 表格
    def _tables(self):
        self.tables = []
        lines, kind = self.lines, self.kind
        i, n = 0, len(lines)
        while i < n:
            if kind[i] == 'ptable' and self.in_body[i]:
                j = i
                while j + 1 < n and kind[j + 1] == 'ptable':
                    j += 1
                rows = []
                for r in range(i, j + 1):
                    if RE_PIPE_SEP.match(RE_QUOTE_PREFIX.sub('', lines[r])):
                        continue
                    cells = [{'raw': c, 'text': cell_text(c), 'line': r, 'origin': True, 'pieces': [(r, c)]}
                             for c in split_pipe(lines[r])]
                    rows.append({'line': r, 'cells': cells})
                if rows:
                    self.tables.append({'kind': 'pipe', 'start': i, 'end': j, 'grid': rows})
                i = j + 1
                continue
            i += 1
        for (a, b) in self.html_regions:
            if not self.in_body[a]:
                continue
            self.tables.append({'kind': 'html', 'start': a, 'end': b, 'grid': self._parse_html_table(a, b)})
        self.tables.sort(key=lambda t: t['start'])
        for t in self.tables:
            t['header'] = [c['text'] for c in t['grid'][0]['cells']] if t['grid'] else []
            t['lines'] = set(range(t['start'], t['end'] + 1))

    def _parse_html_table(self, a, b):
        region = self.lines[a:b + 1]
        text = '\n'.join(region)
        starts, pos = [], 0
        for ln in region:
            starts.append(pos)
            pos += len(ln) + 1

        def line_of(p):
            return a + bisect.bisect_right(starts, p) - 1

        trs = [m.start() for m in RE_TR.finditer(text)]
        raw_rows = []
        for k, p in enumerate(trs):
            seg = text[p:trs[k + 1] if k + 1 < len(trs) else len(text)]
            m_end = RE_TR_END.search(seg)
            if m_end:
                seg = seg[:m_end.start()]
            opens = list(RE_CELL_OPEN.finditer(seg))
            cells = []
            for j, m in enumerate(opens):
                full = seg[m.end():opens[j + 1].start() if j + 1 < len(opens) else len(seg)]
                first_line = line_of(p + m.end())
                pieces = [(first_line + k, piece) for k, piece in enumerate(full.split('\n')) if piece.strip()]
                raw = RE_CELL_CLOSE_TAIL.sub('', full.strip())
                rs = RE_ROWSPAN.search(m.group(2))
                cs = RE_COLSPAN.search(m.group(2))
                cells.append({'raw': raw, 'text': cell_text(raw), 'line': line_of(p + m.start()), 'pieces': pieces,
                              'rowspan': max(1, int(rs.group(1))) if rs else 1,
                              'colspan': max(1, int(cs.group(1))) if cs else 1})
            raw_rows.append({'line': line_of(p), 'cells': cells})
        grid, pending = [], {}
        for r in raw_rows:
            out, col, queue = [], 0, list(r['cells'])
            while queue or col in pending:
                if col in pending:
                    left, c = pending[col]
                    out.append(dict(c, origin=False))
                    if left <= 1:
                        del pending[col]
                    else:
                        pending[col] = (left - 1, c)
                    col += 1
                    continue
                c = queue.pop(0)
                for k in range(c['colspan']):
                    out.append(dict(c, origin=(k == 0)))
                    if c['rowspan'] > 1:
                        pending[col] = (c['rowspan'] - 1, c)
                    col += 1
            grid.append({'line': r['line'], 'cells': out})
        return grid

    # -- 模板残留行（只由 L02 报）
    def _residual(self):
        self.residual = set()
        for h in self.find_sections(RE_SEC_KIT):
            self.residual.update(range(h['i'], h['end'] + 1))
        for i, ln in enumerate(self.lines):
            if self.kind[i] != 'code' and re.match(r'^\s*>\s*【指引', ln):
                self.residual.add(i)

    # -- 便捷迭代
    def body(self, residual=False, tables=True, kinds=None):
        for i, ln in enumerate(self.lines):
            if not self.in_body[i]:
                continue
            if not residual and i in self.residual:
                continue
            k = self.kind[i]
            if not tables and k in ('ptable', 'htable'):
                continue
            if kinds is not None and k not in kinds:
                continue
            yield i, ln, k

    def units(self, residual=False):
        """表外按行、表内按单元格给出 (行号, 可见文本, 原文)——导出稿常把整张 HTML 表压在一行里。"""
        for i, ln, k in self.body(residual=residual, tables=False):
            yield i, strip_tags(ln), ln
        for t in self.tables:
            if not residual and t['start'] in self.residual:
                continue
            for row in t['grid']:
                for cell in row['cells']:
                    if cell.get('origin', True):
                        for line, piece in cell['pieces']:
                            yield line, cell_text(piece), piece

    def table_line_set(self, pred):
        s = set()
        for t in self.tables:
            if pred(t):
                s |= t['lines']
        return s

    def us_r_ids_outside(self, exclude):
        ids = []
        for h in self.headings:
            if h['i'] in exclude or not self.in_body[h['i']] or h['i'] in self.residual:
                continue
            m = re.match(r'^\s*US\s*(\d+)\s*[-‐‑–—－]\s*R\s*(\d+)', h['text'], re.I)
            if m:
                key = 'US%s-R%s' % (m.group(1), m.group(2))
                if key not in ids:
                    ids.append(key)
        return ids


# ---------------------------------------------------------------- 检查结果

class Check(object):
    def __init__(self, cid):
        self.id = cid
        self.name = NAMES[cid]
        self.fix = FIX[cid]
        self.findings = []
        self.detail = ''
        self.hits_override = 'auto'

    def add(self, sev, idx, msg=''):
        self.findings.append((sev, None if idx is None else idx + 1, msg))

    @property
    def status(self):
        best = 0
        for sev, _, _ in self.findings:
            best = max(best, SEV_RANK[sev])
        return {3: 'FAIL', 2: 'WARN', 1: 'INFO', 0: 'OK'}[best]

    @property
    def hits(self):
        if self.hits_override != 'auto':
            return self.hits_override
        hard = [f for f in self.findings if f[0] in ('FAIL', 'WARN')]
        return len(hard) if hard else len(self.findings)

    def lines(self):
        st = self.status
        first = sorted(set(f[1] for f in self.findings if f[1] is not None and f[0] == st))
        rest = sorted(set(f[1] for f in self.findings if f[1] is not None) - set(first))
        return first + rest

    def to_dict(self):
        return {'id': self.id, 'name': self.name, 'status': self.status, 'hits': self.hits,
                'lines': self.lines(), 'detail': self.detail, 'fix': self.fix,
                'findings': [{'severity': s, 'line': l, 'message': m} for s, l, m in self.findings]}


def short(s, n=18):
    s = re.sub(r'\s+', ' ', s).strip()
    return s if len(s) <= n else s[:n] + '…'


def vis(ln):
    return strip_tags(ln)


# ---------------------------------------------------------------- 各检查

def check_l01(doc, profile):
    c = Check('L01')
    items = [
        ('编写记录', RE_SEC_LOG, (1,)), ('背景', RE_SEC_BG, (1,)), ('成功指标', RE_SEC_METRIC, (1, 2)),
        ('需求范围与边界', RE_SEC_SCOPE, (1,)), ('需求关联方与依赖', RE_SEC_DEPS, (1, 2)),
        ('功能需求', RE_SEC_FR, (1,)), ('验收标准', RE_SEC_AC, (1,)), ('Data Requirements', RE_SEC_DATA, (1,)),
    ]
    if profile == 'light':
        items = [it for it in items if it[0] in ('功能需求', '验收标准', 'Data Requirements')]
    parts = []
    for name, rx, levels in items:
        hits = [h for h in doc.find_sections(rx, levels) if doc.in_body[h['i']]]
        if hits:
            parts.append('%s 有' % name)
            continue
        if name == '验收标准':
            deeper = [h for h in doc.find_sections(RE_SEC_AC) if h['level'] > 1 and doc.in_body[h['i']]
                      and not RE_SEC_AC_POINTER.search(h['text'])]
            if deeper:
                c.add('FAIL', deeper[0]['i'], '验收标准非顶级（%s）' % ('#' * deeper[0]['level']))
                parts.append('验收标准 非顶级')
                continue
        if name == '功能需求' and [h for h in doc.find_sections(RE_SEC_US_ONLY, (1,)) if doc.in_body[h['i']]]:
            c.add('INFO', None, '功能需求章名只有 User Stories')
            parts.append('功能需求 无（章名只有 User Stories）')
            continue
        c.add('INFO', None, '%s 无' % name)
        parts.append('%s 无' % name)
    c.detail = ' · '.join(parts)
    c.hits_override = sum(1 for p in parts if not p.endswith(' 有'))
    return c


def check_l02(doc):
    c = Check('L02')
    cnt = Counter()
    for i, ln, k in doc.body(residual=True):
        for _ in RE_FILL.finditer(ln):
            c.add('FAIL', i, '（填写：')
            cnt['（填写：'] += 1
        if RE_GUIDE.search(ln):
            c.add('FAIL', i, '【指引')
            cnt['【指引'] += len(RE_GUIDE.findall(ln))
        if k == 'heading' and RE_SEC_KIT.search(ln):
            c.add('FAIL', i, 'Kit 自查清单')
            cnt['Kit 自查清单'] += 1
        if k != 'heading' and RE_MERMAID_PROSE.search(ln):
            c.add('FAIL', i, 'mermaid 说明句')
            cnt['mermaid 说明句'] += 1
    total_mm = 0
    for f in doc.fences:
        if f['lang'] != 'mermaid' or f['start'] in doc.preamble:
            continue
        total_mm += 1
        if doc.is_export or f['quoted'] or f['indent'] >= 2:
            c.add('FAIL', f['start'], '裸 mermaid')
            cnt['裸 mermaid'] += 1
    kind = ('导出稿（%s）' % '、'.join(doc.export_basis)) if doc.is_export else '起草稿'
    parts = ['%s %d' % (k, cnt[k]) for k in ('（填写：', '【指引', 'Kit 自查清单', '裸 mermaid', 'mermaid 说明句') if cnt[k]]
    note = '判为%s' % kind
    if not doc.is_export and total_mm:
        note += '，mermaid fence %d 个是画板载体不计' % total_mm
    c.detail = ('；'.join(parts) + '（%s）' % note) if parts else note
    return c


def check_l03(doc, track_lines):
    c = Check('L03')
    secs = [h for h in doc.find_sections(RE_SEC_PENDING, (1,)) if doc.in_body[h['i']]]
    if not secs:
        secs = [h for h in doc.headings if '【待确认】' in h['text'] and doc.in_body[h['i']]]
    sec_lines = set()
    detail = []
    for h in secs[:1]:
        sec_lines = set(range(h['i'], h['end'] + 1))
        nums, bullets, rows = [], 0, 0
        for i in range(h['i'] + 1, h['end'] + 1):
            if not doc.in_body[i]:
                continue
            ln = doc.lines[i]
            k = doc.kind[i]
            if k == 'list' and len(ln) - len(ln.lstrip(' \t')) < 2 and RE_LIST.match(ln):
                m = RE_LIST_NUM.match(ln)
                if m:
                    nums.append(int(m.group(1)))
                else:
                    bullets += 1
        for t in doc.tables:
            if t['start'] > h['i'] and t['end'] <= h['end']:
                rows += max(0, len(t['grid']) - 1)
        total = len(nums) + bullets + rows
        detail.append('【待确认】章 %d 条' % total)
        if total > 5:
            c.add('FAIL', h['i'], '待确认 %d 条 >5' % total)
        if bullets:
            c.add('WARN', h['i'], '未编号 %d 条' % bullets)
            detail.append('未编号 %d' % bullets)
        if nums and nums != list(range(1, len(nums) + 1)):
            c.add('WARN', h['i'], '编号不连续 %s' % nums)
            detail.append('编号不连续 %s' % ','.join(str(x) for x in nums))
    bare = 0
    for i, txt, raw in doc.units():
        if i in sec_lines or i in track_lines:
            continue
        t = RE_PENDING_REF.sub(' ', txt)
        m = RE_PENDING.search(t)
        if not m:
            continue
        if '待补' in t and _in_ued_slot(doc.lines, i):
            continue  # UED 设计稿槽允许写「待补」（02 模板占位），不算裸挂
        if RE_PENDING_OK_A.search(t) and RE_PENDING_OK_B.search(t):
            continue
        c.add('FAIL', i, m.group(0))
        bare += 1
    detail.append('章外裸挂 %d 行' % bare)
    c.detail = '；'.join(detail)
    return c


def check_l04(doc):
    c = Check('L04')
    cnt = Counter()
    for i, ln, k in doc.body():
        for m in RE_SELF.finditer(vis(ln)):
            c.add('FAIL', i, m.group(0))
        for m in RE_SELF_SOFT.finditer(vis(ln)):
            c.add('WARN', i, m.group(0))
            cnt[m.group(0)] += 1
    c.detail = ' '.join('%s×%d' % kv for kv in cnt.most_common(6))
    return c


def check_l05(doc):
    c = Check('L05')
    runs, cur = [], []
    for i in range(len(doc.lines)):
        if doc.in_body[i] and i not in doc.residual and doc.kind[i] == 'prose':
            cur.append(i)
        else:
            if cur:
                runs.append(cur)
            cur = []
    if cur:
        runs.append(cur)
    long_n = semi_n = 0
    for run in runs:
        joined = ''.join(vis(doc.lines[i]) for i in run)
        why = []
        if len(run) >= 4:
            why.append('%d 行' % len(run))
            long_n += 1
        if joined.count('；') >= 2:
            why.append('%d 个「；」' % joined.count('；'))
            semi_n += 1
        if why:
            c.add('WARN', run[0], '、'.join(why))
    if c.findings:
        c.detail = '%d 段（≥4 行 %d · ≥2 个「；」%d）' % (len(c.findings), long_n, semi_n)
    return c


def check_l06(doc):
    c = Check('L06')
    cnt = Counter()
    for i, t, raw in doc.units():
        found = RE_REUSE.findall(t)
        if not found:
            continue
        if RE_REUSE_CLUE.search(raw) or RE_REUSE_CLUE.search(t):
            continue
        c.add('WARN', i, short(t, 24))
        for w in found:
            cnt[w] += 1
    if c.findings:
        c.detail = '%d 行无出处（%s）' % (len(c.findings), ' '.join('%s×%d' % kv for kv in cnt.most_common()))
    return c


def find_col(header, pred):
    for k, h in enumerate(header):
        if pred(h):
            return k
    return None


def check_l07(doc):
    c = Check('L07')
    text_n = two_n = tables = 0
    for t in doc.tables:
        col = find_col(t['header'], lambda h: '原型' in h)
        if col is None:
            continue
        tables += 1
        for row in t['grid'][1:]:
            if col >= len(row['cells']):
                continue
            cell = row['cells'][col]
            if not cell.get('origin', True):
                continue
            imgs = len(RE_IMG.findall(cell['raw']))
            if imgs >= 2:
                c.add('FAIL', cell['line'], '同格 %d 张图' % imgs)
                two_n += 1
            elif imgs == 0:
                c.add('WARN', cell['line'], short(cell['text']) or '空')
                text_n += 1
    if tables:
        c.detail = '%d 张含原型列的表：无图格 %d · 同格多图 %d' % (tables, text_n, two_n)
    return c


def is_track_table(t):
    return find_col(t['header'], lambda h: '事件属性英文' in h) is not None


def norm_key(s):
    return re.sub(r'[`\s]', '', s or '').strip()


def check_l08(doc):
    c = Check('L08')
    parts = []
    jira_vals = {}
    groups_total = groups_missing = shot_empty = shot_placeholder = 0
    # 公共属性可在埋点表前一行声明一次（09 §5）：「公共属性：jira_id=WEB-123…」→ 表内不再逐事件要 jira_id 行
    declared_jira, declared_line = None, None
    for i, ln in enumerate(doc.lines):
        if '公共属性' in ln:
            m = re.search(r'jira_id\s*[=＝:：]\s*([A-Z][A-Z0-9]+-\d+)', ln)
            if m:
                declared_jira, declared_line = m.group(1), i
                break
    for t in doc.tables:
        if not is_track_table(t):
            continue
        hd = t['header']
        ev = find_col(hd, lambda h: '事件名称英文' in h or ('事件名' in h and '英文' in h))
        at = find_col(hd, lambda h: '事件属性英文' in h)
        va = find_col(hd, lambda h: '属性值' in h)
        sh = find_col(hd, lambda h: '截图' in h)

        def cell(row, k):
            if k is None or k >= len(row['cells']):
                return None
            return row['cells'][k]

        group = None
        groups = []
        for row in t['grid'][1:]:
            evc = cell(row, ev)
            evname = norm_key(evc['text']) if evc else ''
            if evname:
                group = {'name': evname, 'line': row['line'], 'jira': False, 'row': row}
                groups.append(group)
            attr = norm_key(cell(row, at)['text']) if cell(row, at) else ''
            valc = cell(row, va)
            val = valc['text'] if valc else ''
            if attr == 'module' and '数分定值' not in val:
                c.add('FAIL', row['line'], 'module=%s' % (short(val, 10) or '空'))
            if attr == 'page_description' and re.search(r'/|、|或', val):
                c.add('FAIL', row['line'], 'page_description 多值')
            if attr == 'jira_id':
                v = norm_key(val)
                jira_vals.setdefault(v, row['line'])
                if group is not None:
                    group['jira'] = True
        for g in groups:
            groups_total += 1
            if declared_jira:
                g['jira'] = True
            if not g['name'].startswith('$') and not g['jira']:
                c.add('WARN', g['line'], '%s 缺 jira_id' % short(g['name'], 26))
                groups_missing += 1
            sc = cell(g['row'], sh)
            if sc is not None:
                st = sc['text'].strip()
                if st in ('', '/', '-', '--', '—'):
                    shot_empty += 1
                    c.add('INFO', g['line'], '截图空')
                elif not RE_IMG.search(sc['raw']):
                    shot_placeholder += 1
    if declared_jira:
        jira_vals.setdefault(declared_jira, declared_line)
        parts.append('公共属性声明 jira_id=%s' % declared_jira)
    if len(jira_vals) > 1:
        first = min(jira_vals.values())
        c.add('FAIL', first, 'jira_id %d 个值' % len(jira_vals))
        parts.append('jira_id %d 个值（%s）' % (len(jira_vals), ' / '.join(sorted(jira_vals))))
    nfail_module = sum(1 for f in c.findings if f[2].startswith('module='))
    nfail_pd = sum(1 for f in c.findings if f[2].startswith('page_description'))
    if groups_total:
        parts.insert(0, '事件 %d 条' % groups_total)
        if nfail_module:
            parts.append('module 未写由数分定值 %d' % nfail_module)
        if nfail_pd:
            parts.append('page_description 多值 %d' % nfail_pd)
        if groups_missing:
            parts.append('缺 jira_id %d' % groups_missing)
        parts.append('截图空 %d（另有无图占位 %d）' % (shot_empty, shot_placeholder))
    if not groups_total:
        secs = [h for h in doc.find_sections(RE_SEC_DATA, (1,)) if doc.in_body[h['i']]]
        if secs:
            h = secs[0]
            sec_txt = ' '.join(vis(doc.lines[i]) for i in range(h['i'], h['end'] + 1) if doc.in_body[i])
            sec_tabs = [t for t in doc.tables if h['i'] < t['start'] <= h['end']]
            if RE_NO_TRACKING.search(sec_txt):
                parts.append('声明无需埋点')
            elif sec_tabs:
                c.add('INFO', sec_tabs[0]['start'], '埋点表表头非 09 §5 十列')
                parts.append('埋点表表头非 09 §5 十列（无「事件属性英文」列），未检')
            else:
                c.add('INFO', h['i'], '未找到埋点表')
                parts.append('Data Requirements 里未找到埋点表')
    c.detail = '；'.join(parts)
    return c


def pair_quotes(s, q='"'):
    pos = [m.start() for m in re.finditer(re.escape(q), s)]
    for k in range(0, len(pos) - 1, 2):
        yield s[pos[k] + 1:pos[k + 1]], pos[k]


def check_l09(doc):
    c = Check('L09')
    cnt = Counter()
    for i, ln, k in doc.body():
        for m in RE_CODE_SPAN.finditer(ln.replace('\\`', '\x00')):
            inner = m.group(2).strip()
            if inner and RE_CJK.match(inner) and not RE_FORMULA.search(inner):
                c.add('FAIL', i, '`%s`' % short(inner, 10))
                cnt['反引号中文'] += 1
        for m in RE_CODE_TAG.finditer(ln):
            inner = strip_tags(m.group(1)).strip()
            if inner and RE_CJK.match(inner) and not RE_FORMULA.search(inner):
                c.add('FAIL', i, '<code>%s' % short(inner, 10))
                cnt['反引号中文'] += 1
        t = vis(ln)
        for m in RE_CN_QUOTE.finditer(t):
            if RE_TWO_LATIN.search(m.group(1)):
                c.add('WARN', i, '「%s」' % short(m.group(1), 12))
                cnt['「」内英文'] += 1
        for inner, _ in pair_quotes(t):
            if inner and RE_CJK.match(inner):
                c.add('WARN', i, '"%s"' % short(inner, 10))
                cnt['英文引号包中文'] += 1
    c.detail = ' · '.join('%s %d' % (k, cnt[k]) for k in ('反引号中文', '「」内英文', '英文引号包中文') if cnt[k])
    return c


def check_l10(doc):
    c = Check('L10')
    secs = [h for h in doc.find_sections(RE_SEC_METRIC, (1, 2)) if doc.in_body[h['i']]]
    if not secs:
        secs = [h for h in doc.find_sections(RE_SEC_METRIC) if doc.in_body[h['i']]]
    ranges = []
    for h in secs:
        ranges.append((h['i'] + 1, h['end'], h['i']))
    if not ranges:
        fallback = [i for i, ln, k in doc.body() if k != 'heading' and '成功指标' in ln]
        ranges = [(i, i, i) for i in fallback]
        if not ranges:
            c.add('INFO', None, '未找到成功指标节')
            c.detail = '未找到成功指标节'
            return c
    parts = []
    data_rows = 0
    for (a, b, hi) in ranges:
        tabs = [t for t in doc.tables if t['start'] >= a and t['end'] <= b and t['start'] not in doc.residual]
        for t in tabs:
            rows = t['grid'][1:]
            data_rows += len(rows)
            kou = find_col(t['header'], lambda h: '口径' in h)
            name_col = find_col(t['header'], lambda h: '指标' in h)
            name_col = 0 if name_col is None else name_col
            tgt_col = find_col(t['header'], lambda h: '目标' in h)
            if kou is None:
                c.add('WARN', t['start'], '指标表无口径列')
            for row in rows:
                cells = row['cells']
                if kou is not None and kou < len(cells) and not RE_METRIC_KOU.search(cells[kou]['text']):
                    c.add('WARN', row['line'], '口径缺分子/分母/周期')
                probe = ' '.join(cells[k]['text'] for k in (name_col, tgt_col) if k is not None and k < len(cells))
                if RE_METRIC_SWITCH.search(probe):
                    c.add('WARN', row['line'], '开关型不是指标')
        if not tabs:
            txt = ' '.join(vis(doc.lines[i]) for i in range(a, b + 1) if doc.in_body[i] and i not in doc.residual)
            if txt.strip() and not RE_METRIC_KOU.search(txt):
                c.add('WARN', a if a <= b else hi, '口径缺分子/分母/周期')
            if RE_METRIC_SWITCH.search(txt):
                c.add('WARN', a if a <= b else hi, '开关型不是指标')
        for i in range(a, b + 1):
            if not doc.in_body[i] or i in doc.residual:
                continue
            ln = doc.lines[i]
            for m in RE_METRIC_ANALYSIS.finditer(vis(ln)):
                c.add('FAIL', i, '分析方案词「%s」' % m.group(0))
            if RE_LATEX.search(ln):
                c.add('INFO', i, 'LaTeX')  # 07 §五 第 8 条：比率公式一律 LaTeX，这是 house 写法，只记事实
                if re.search(r'[＝=]\s*[^\n|]{1,30}[/／÷][^\n|]{1,30}', ln) and not RE_LATEX.search(ln):
                    c.add('WARN', i, '文字式分子分母句，按 07 §五 第 8 条转 LaTeX')
    if data_rows > 2:
        c.add('WARN', ranges[0][2], '指标 %d 行，从简' % data_rows)
    parts.append('指标行 %d' % data_rows)
    for label in ('分析方案词', 'LaTeX', '口径缺', '开关型', '从简', '无口径列'):
        n = sum(1 for f in c.findings if label in f[2])
        if n:
            parts.append('%s %d' % (label, n))
    c.detail = ' · '.join(parts)
    return c


def norm_sentence(s):
    s = strip_tags(s)
    s = RE_QUOTE_PREFIX.sub('', s)
    s = re.sub(r'^\s*(?:[-*+]\s+(?:\[[ xX]\]\s*)?|\d{1,3}[.)、]\s*)', '', s)
    s = re.sub(r'[*_`\s]', '', s)
    return s.strip('，,。.；;：:！!？?、）)」』"\'（(「『')


def check_l11(doc):
    c = Check('L11')
    seen = Counter()
    first = {}
    for i, ln, k in doc.body(tables=False):
        if k in ('heading', 'hr', 'math', 'wb', 'html', 'blank'):
            continue
        for seg in re.split(r'[。；]|<br\s*/?>', ln):
            s = norm_sentence(seg)
            if len(s) >= 12:
                seen[s] += 1
                first.setdefault(s, i)
    rep = [(s, n) for s, n in seen.items() if n >= 3]
    rep.sort(key=lambda x: (-x[1], first[x[0]]))
    for s, n in rep:
        c.add('WARN', first[s], '%s×%d' % (short(s, 16), n))
    if rep:
        c.detail = '%d 条：%s' % (len(rep), '；'.join('「%s」×%d' % (short(s, 16), n) for s, n in rep[:5]))
    return c


def check_l12(doc, track_lines):
    c = Check('L12')
    loc_lines = set()
    for h in doc.find_sections(RE_SEC_LOC, (1,)):
        loc_lines |= set(range(h['i'], h['end'] + 1))
    A, A_line = [], {}
    for i, ln, k in doc.body():
        if i in loc_lines or i in track_lines:
            continue
        for m in RE_CN_QUOTE.finditer(vis(ln)):
            term = m.group(1).strip()
            if term and term not in A_line:
                A.append(term)
                A_line[term] = i
    B, B_line = [], {}
    for t in doc.tables:
        if t['start'] not in loc_lines:
            continue
        for row in t['grid'][1:]:
            if not row['cells']:
                continue
            term = re.sub(r'^[「`"\s]+|[」`"\s]+$', '', row['cells'][0]['text']).strip()
            if term and term not in B_line:
                B.append(term)
                B_line[term] = row['line']
    if not loc_lines:
        if A:
            c.add('WARN', None, '无 Localisation 节')
            c.detail = '无 Localisation 节，正文「」词条 %d 个' % len(A)
        return c
    a_b = [x for x in A if x not in B_line]
    b_a = [x for x in B if x not in A_line]
    for x in a_b:
        c.add('WARN', A_line[x], 'A−B「%s」' % short(x, 12))
    for x in b_a:
        c.add('WARN', B_line[x], 'B−A「%s」' % short(x, 12))
    c.detail = 'A−B %d：%s；B−A %d：%s' % (
        len(a_b), ''.join('「%s」' % short(x, 12) for x in a_b[:20]) or '—',
        len(b_a), ''.join('「%s」' % short(x, 12) for x in b_a[:20]) or '—')
    return c


def l13_scrub(ln):
    s = RE_MD_IMAGE.sub(' ', ln)
    s = RE_MD_LINK.sub(lambda m: '[%s]' % m.group(1), s)
    s = RE_IMG_TAG.sub(' ', s)
    return RE_URL_ATTR.sub(' ', s)


def check_l13(doc):
    c = Check('L13')
    cnt = Counter()
    for i, ln, k in doc.body():
        s = l13_scrub(ln)
        for m in RE_COORD.finditer(s):
            w = m.group(0)
            label = 'node-id' if w.lower().startswith('node-id') else ('/Users/' if w.lower() == '/users/' else (
                'figma 链接' if 'figma' in w.lower() else '屏号'))
            c.add('FAIL', i, label)
            cnt[label] += 1
        for m in RE_PNG.finditer(s):
            tok = m.group(0)
            if '://' in tok or not tok[:-4]:
                continue
            c.add('FAIL', i, short(tok, 20))
            cnt['.png 路径'] += 1
    c.detail = ' · '.join('%s %d' % kv for kv in cnt.most_common())
    return c


def check_l14(doc):
    c = Check('L14')
    cnt = Counter()
    for i, ln, k in doc.body():
        t = vis(ln)
        for m in RE_AI_WORDS.finditer(t):
            c.add('WARN', i, m.group(0))
            cnt['AI 味词'] += 1
        if k == 'list' and RE_LIST.match(ln) and t.rstrip().endswith('；'):
            c.add('WARN', i, '列表项句尾「；」')
            cnt['句尾「；」'] += 1
        if '<li' in ln.lower():
            for m in RE_LI.finditer(ln):
                if strip_tags(m.group(1)).strip().endswith('；'):
                    c.add('WARN', i, '列表项句尾「；」')
                    cnt['句尾「；」'] += 1
        if k not in ('ptable', 'htable') and '→' in t and not RE_ROUTE_LINE.match(ln):
            n = t.count('→')
            c.add('WARN', i, '→×%d' % n)
            cnt['表外 →'] += n
    c.detail = ' · '.join('%s %d' % (k, cnt[k]) for k in ('AI 味词', '句尾「；」', '表外 →') if cnt[k])
    return c


def check_l15(doc):
    c = Check('L15')
    pos = {}
    for i, ln, k in doc.body():
        t = vis(ln)
        for key, rx in (('码点', RE_CODEPOINT), ('码元', RE_CODEUNIT), ('毫秒', RE_MS), ('秒', RE_SEC),
                        ('UTF-16', RE_UTF16), ('Unicode 码点', RE_UNI_CP)):
            if rx.search(t):
                pos.setdefault(key, []).append(i)
    parts = []
    for a, b in (('码点', '码元'), ('毫秒', '秒'), ('UTF-16', 'Unicode 码点')):
        if a in pos and b in pos:
            for i in (pos[a][:2] + pos[b][:2]):
                c.add('WARN', i, '%s / %s' % (a, b))
            parts.append('%s×%d 与 %s×%d 混用' % (a, len(pos[a]), b, len(pos[b])))
    c.detail = '；'.join(parts)
    return c


def mm_nodes(body_lines):
    """返回 (节点集合, {子图名: 节点数})；只数边两端与独立声明的节点。"""
    head = ''
    for ln in body_lines:
        if ln.strip() and not ln.strip().startswith('%%'):
            head = ln
            break
    mh = RE_MM_HEADER.match(head)
    dtype = mh.group(1).lower() if mh else ''
    nodes, owner, stack = [], {}, []

    def see(node):
        if not node or node.lower() in MM_KEYWORDS:
            return
        if node not in owner:
            nodes.append(node)
            owner[node] = stack[-1] if stack else None

    if dtype == 'sequencediagram':
        for ln in body_lines:
            m = RE_MM_SEQ_PART.match(ln)
            if m:
                see(m.group(1).strip())
                continue
            m = RE_MM_SEQ_MSG.match(ln)
            if m:
                see(m.group(1).strip())
                see(m.group(2).strip())
        return nodes, {}
    sub_count = Counter()
    for raw in body_lines:
        ln = raw.split('%%')[0]
        if not ln.strip() or RE_MM_HEADER.match(ln) or RE_MM_SKIP.match(ln):
            continue
        msg = RE_MM_SUBGRAPH.match(ln)
        if msg:
            name = re.sub(r'\[.*$', '', msg.group(1)).strip().strip('"') or ('subgraph%d' % len(sub_count))
            stack.append(name)
            sub_count[name] += 0
            continue
        if RE_MM_END.match(ln):
            if stack:
                stack.pop()
            continue
        s = ln.replace('[*]', ' STARTEND ')
        sd = RE_MM_STATE_DECL.match(s)
        if sd:
            see(sd.group(1))
            continue
        s = RE_MM_QUOTED.sub('""', s)
        s = re.sub(r':::[\w-]+', '', s)
        for rx in RE_MM_SHAPES:
            s = rx.sub('', s)
        s = RE_MM_PIPE_LABEL.sub(' ', s)
        s = RE_MM_DASH_LABEL.sub(' --> ', s)
        s = RE_MM_EQ_LABEL.sub(' ==> ', s)
        s = RE_MM_DOT_LABEL.sub(' -.-> ', s)
        if dtype.startswith('state'):
            s = s.split(':')[0]
        if RE_MM_EDGE.search(s):
            for tok in RE_MM_EDGE_SPLIT.split(s):
                for part in tok.split('&'):
                    m = RE_MM_ID.match(part.strip())
                    if m:
                        see(m.group(1))
        else:
            m = re.match(r'^\s*([A-Za-z0-9_一-鿿][\w一-鿿-]*)\s*;?\s*$', s)
            if m:
                see(m.group(1))
    for node in nodes:
        if owner[node] is not None:
            sub_count[owner[node]] += 1
    return nodes, dict(sub_count)


def check_l16(doc, n_us_r):
    c = Check('L16')
    sources = []
    for f in doc.fences:
        if f['lang'] == 'mermaid' and f['start'] not in doc.preamble:
            sources.append((f['start'], f['body']))
    for w in doc.whiteboards:
        if w['type'] == 'mermaid' and w['body'] and w['start'] not in doc.preamble:
            sources.append((w['start'], w['body']))
    sources.sort(key=lambda x: x[0])
    parts = []
    for start, body in sources:
        nodes, subs = mm_nodes(body)
        desc = '%d 节点' % len(nodes)
        if len(nodes) > 12:
            c.add('FAIL', start, '%d 节点 >12' % len(nodes))
        for name, n in sorted(subs.items()):
            if n > 7:
                c.add('FAIL', start, '泳道「%s」%d 节点 >7' % (short(name, 10), n))
        if subs:
            desc += '（泳道最多 %d）' % max(subs.values())
        parts.append('L%d 图 %s' % (start + 1, desc))
    if not sources and not doc.whiteboards:
        has_word = any(RE_DIAGRAM_WORD.search(ln) for i, ln, k in doc.body(residual=False))
        if not has_word and n_us_r >= 2:
            c.add('WARN', None, '缺导览图')
            parts.append('缺导览图（%d 个 US-R、无图）' % n_us_r)
    elif not sources:
        parts.append('画板 %d 个（无 mermaid 源可数）' % len(doc.whiteboards))
    c.detail = '；'.join(parts)
    return c


def check_l17(doc):
    c = Check('L17')
    for h in doc.headings:
        if h['level'] < 2 or not doc.in_body[h['i']] or h['i'] in doc.residual:
            continue
        if RE_US_HEADING.match(h['text']):
            m = RE_US_ROLE.search(h['text'])
            if m:
                c.add('FAIL', h['i'], short(m.group(0), 16))
    if c.findings:
        c.detail = '；'.join('L%d「%s」' % (f[1], f[2]) for f in c.findings[:5])
    return c


def check_l18(doc):
    c = Check('L18')
    ac = [h for h in doc.find_sections(RE_SEC_AC, (1,)) if doc.in_body[h['i']]]
    if not ac:  # 非顶级的验收章由 L01 报 FAIL，这里照样读它的 US-R 小节
        ac = [h for h in doc.find_sections(RE_SEC_AC) if doc.in_body[h['i']] and not RE_SEC_AC_POINTER.search(h['text'])][:1]
    ac_lines = set()
    ac_ids = []
    counts = []
    for h in ac:
        ac_lines |= set(range(h['i'], h['end'] + 1))
        subs = [s for s in doc.headings if h['i'] < s['i'] <= h['end'] and RE_US_R_ID.search(s['text'])]
        for s in subs:
            ids = ['US%s-R%s' % m for m in RE_US_R_ID.findall(s['text'])]
            for x in ids:
                if x not in ac_ids:
                    ac_ids.append(x)
            items = []
            fallback = []
            for i in range(s['i'] + 1, s['end'] + 1):
                if not doc.in_body[i]:
                    continue
                ln = doc.lines[i]
                if RE_CHECKBOX.match(ln):
                    items.append(i)
                elif doc.kind[i] == 'list' and RE_LIST.match(ln):
                    fallback.append(i)
            if not items:
                items = fallback
                for t in doc.tables:
                    if s['i'] < t['start'] and t['end'] <= s['end']:
                        items += [r['line'] for r in t['grid'][1:]]
            label = '/'.join(ids)
            counts.append('%s %d' % (label, len(items)))
            if not items:
                c.add('FAIL', s['i'], '%s 无验收' % label)
            elif len(items) > 8:
                c.add('WARN', s['i'], '%s %d 行 >8' % (label, len(items)))
            for i in items:
                t = vis(doc.lines[i])
                if t.count('；') >= 2 or t.count('且') >= 2:
                    c.add('WARN', i, '一行只验一件事')
    fr = doc.us_r_ids_outside(ac_lines)
    missing = [x for x in fr if x not in ac_ids]
    for x in missing:
        hh = next((h for h in doc.headings if h['i'] not in ac_lines and RE_US_R_ID.search(h['text'])
                   and 'US%s-R%s' % RE_US_R_ID.search(h['text']).groups() == x), None)
        c.add('FAIL', hh['i'] if hh else None, '%s 缺验收小节' % x)
    parts = []
    if not ac:
        parts.append('无验收标准章')
    if counts:
        parts.append('各节勾选项：' + ' · '.join(counts))
    if missing:
        parts.append('缺验收小节：' + ' '.join(missing))
    one = sum(1 for f in c.findings if f[2] == '一行只验一件事')
    if one:
        parts.append('一行多事 %d' % one)
    c.detail = '；'.join(parts)
    return c, fr


def cjk_count(doc):
    n = 0
    for i, ln, k in doc.body(residual=True):
        n += len(RE_CJK.findall(strip_tags(ln)))
    return n


def check_l19(doc, cjk, n_us_r):
    c = Check('L19')
    n_tables = len(doc.tables)
    n_img = sum(len(RE_IMG.findall(ln)) for i, ln, k in doc.body(residual=True))
    c.add('INFO', None, 'facts')
    c.detail = '正文 CJK %d 字 · 表 %d · 图 %d · US-R %d' % (cjk, n_tables, n_img, n_us_r)
    c.hits_override = None
    if cjk > 12000:
        c.add('WARN', None, '超金标 1.4×（12k）——体量是症状：回 01 §0.5 决策点测试逐条删常识、需求逻辑改规则表，不是删字')
        c.detail += ' · >12000：超金标 1.4×，回 01 §0.5 决策点测试 / 02 规则表，不是删字'
        c.hits_override = 1
    return c


def check_l20(doc):
    c = Check('L20')
    full = '\n'.join(strip_tags(ln) for i, ln, k in doc.body())
    out = []
    seen = set()
    for i, ln, k in doc.body():
        t = strip_tags(ln)
        t = RE_CN_QUOTE.sub(' ', t)
        t = re.sub(r'"[^"\n]*"|“[^”\n]*”|『[^』\n]*』|`[^`\n]*`', ' ', t)
        for m in RE_ABBR_SUFFIX.finditer(t):
            j = m.start()
            if j < 1 or not RE_CJK.match(t[j - 1]) or t[j - 1:j + 1] in ABBR_COMMON or t[j:j + 2] in ABBR_NEXT_WORD:
                continue
            st = j
            while st - 1 >= 0 and j - (st - 1) <= 3 and RE_CJK.match(t[st - 1]) and t[st - 1] not in ABBR_BOUNDARY:
                st -= 1
            word = t[st:j + 1]
            if len(word) - 1 < 2 or word in seen or word[-3:] in ABBR_COMMON or word[-2:] in ABBR_COMMON:
                continue
            if any(word.endswith(x) for x in ABBR_UI_STATE):
                continue
            seen.add(word)
            if full.count(word) == 1:
                out.append((word, i))
    for word, i in out[:10]:
        c.add('INFO', i, word)
    if out:
        c.detail = '%d 个候选（供人判）：%s' % (len(out), ' '.join(w for w, _ in out[:10]))
    return c


def check_l22(doc):
    c = Check('L22')
    ac = [h for h in doc.find_sections(RE_SEC_AC, (1,)) if doc.in_body[h['i']]]
    if not ac:  # 与 L18 同口径：非顶级的验收章照样读
        ac = [h for h in doc.find_sections(RE_SEC_AC) if doc.in_body[h['i']] and not RE_SEC_AC_POINTER.search(h['text'])][:1]
    sizes = []
    for h in ac:
        for i in range(h['i'] + 1, h['end'] + 1):
            if not doc.in_body[i] or i in doc.residual or not RE_CHECKBOX.match(doc.lines[i]):
                continue
            n = len(RE_CJK.findall(vis(doc.lines[i])))
            sizes.append(n)
            if n > 120:
                c.add('FAIL', i, '%d 字 >120' % n)
            elif n > 60:
                c.add('WARN', i, '%d 字 >60' % n)
    if not sizes:
        c.detail = '验收章无「- [ ]」勾选项' if ac else '无验收标准章'
        return c, None
    avg, top = int(float(sum(sizes)) / len(sizes) + 0.5), max(sizes)
    over = sum(1 for n in sizes if n > 60)
    c.add('INFO', None, 'avg %d / max %d' % (avg, top))
    c.detail = '验收 %d 条 · avg %d / max %d' % (len(sizes), avg, top)
    if over:
        c.detail += ' · >60 %d 条（其中 >120 %d 条）' % (over, sum(1 for n in sizes if n > 120))
    c.hits_override = over or None
    return c, (avg, top)


def check_l23(doc):
    c = Check('L23')
    secs = [h for h in doc.find_sections(RE_SEC_LOG, (1,)) if doc.in_body[h['i']] and not RE_SEC_HISTORY.search(h['text'])]
    if not secs:
        secs = [h for h in doc.find_sections(RE_SEC_LOG) if doc.in_body[h['i']] and not RE_SEC_HISTORY.search(h['text'])]
    if not secs:
        c.detail = '无编写记录章'
        return c, None
    h = secs[0]
    tabs = [t for t in doc.tables if h['i'] < t['start'] <= h['end']]
    rows = sum(1 for t in tabs for r in t['grid'][1:] if any(x['text'] for x in r['cells']))
    if rows > 5:
        c.add('WARN', tabs[0]['start'], '%d 行 >5' % rows)
        c.detail = '编写记录 %d 行 >5：顶部只留 5 行，其余搬「版本历史」' % rows
    else:
        c.add('INFO', None, '%d 行' % rows)
        c.detail = '编写记录 %d 行' % rows + ('' if tabs else '（章内无表格）')
        c.hits_override = None
    return c, rows

RE_NEG = re.compile(r'(^|[，,；;（(\s])(不|禁止|忽略|无需|不得|不再|不自动|不允许|别)')


def _rule_sentences(doc):
    """规则句 = 元素表 / 兜底表 / 规则表格内的分句 + 需求逻辑槽内的正文分句（不含标题、不含验收章）。"""
    out = []
    for t in doc.tables:
        hd = ' '.join(h for h in t['header'])
        if not re.search(r'说明|行为|规则|兜底|口径', hd):
            continue
        for r in t['grid'][1:]:
            for cell in r['cells']:
                txt = cell['text']
                for s in re.split(r'[。；;\n]|• ', txt):
                    if len(RE_CJK.findall(s)) >= 6:
                        out.append((r['line'], s))
    for i, ln, k in doc.body():
        if k != 'prose' or not _in_slot(doc.lines, i, '需求逻辑'):
            continue
        for s in re.split(r'[。；;]', strip_tags(ln)):
            if len(RE_CJK.findall(s)) >= 6:
                out.append((i, s))
    return out


def _in_slot(lines, i, key):
    j = i
    while j >= 0:
        s = lines[j].strip()
        if s.startswith('#### '):
            return key in s
        if s.startswith('### ') or s.startswith('## ') or s.startswith('# '):
            return False
        j -= 1
    return False


def check_l27(doc):
    c = Check('L27')
    sents = _rule_sentences(doc)
    if not sents:
        c.detail = '无规则句'
        return c
    neg = [(i, s) for i, s in sents if RE_NEG.search(s)]
    share = len(neg) / float(len(sents))
    c.detail = '规则句 %d · 否定句 %d（%.0f%%）' % (len(sents), len(neg), share * 100)
    if len(sents) >= 20 and share > 0.5:
        for i, s in neg[:5]:
            c.add('WARN', i, short(s, 24))
        c.hits_override = len(neg)
        c.detail += '：否定堆叠，按 01 §0.5 改正面陈述、否定只留决策'
    else:
        c.add('INFO', None, 'facts')
        c.hits_override = None
    return c


def check_l28(doc):
    c = Check('L28')
    slots = []
    for i, ln in enumerate(doc.lines):
        if ln.strip().startswith('#### ') and '需求逻辑' in ln:
            j = i + 1
            while j < len(doc.lines) and not re.match(r'^#{1,4} ', doc.lines[j]):
                j += 1
            prose = [k for k in range(i + 1, j) if doc.in_body[k] and doc.kind[k] == 'prose' and len(RE_CJK.findall(doc.lines[k])) >= 6]
            slots.append((i, len(prose)))
    if not slots:
        c.detail = '无需求逻辑槽'
        return c
    heavy = [(i, n) for i, n in slots if n > 8]
    c.detail = '需求逻辑槽 %d 个 · 表外正文行 max %d' % (len(slots), max(n for _, n in slots))
    if heavy:
        for i, n in heavy:
            c.add('WARN', i, '表外正文 %d 行' % n)
        c.detail += '：段落改规则表（02 需求逻辑指引）'
    else:
        c.add('INFO', None, 'facts')
        c.hits_override = None
    return c


def check_l24(doc):
    c = Check('L24')
    secs = [h for h in doc.find_sections(RE_SEC_DATA, (1,)) if doc.in_body[h['i']]]
    secs.sort(key=lambda h: (not re.search(r'Data\s*Requirements', h['text'], re.I), h['i']))
    if not secs:
        c.detail = '无 Data Requirements 章'
        return c, None
    h = secs[0]
    total, per = 0, []
    for i in range(h['i'], h['end'] + 1):
        if not doc.in_body[i] or i in doc.residual or doc.kind[i] not in ('heading', 'prose', 'list', 'quote', 'html'):
            continue
        n = len(RE_CJK.findall(strip_tags(RE_LINKISH.sub(' ', doc.lines[i]))))
        if n:
            total += n
            per.append((n, i))
    per.sort(key=lambda x: (-x[0], x[1]))
    longest = '、'.join('L%d %d 字' % (i + 1, n) for n, i in per[:3])
    if total > 800:
        c.add('FAIL', h['i'], '表外 %d 字 >800：分析方法不进 PRD' % total)
        c.detail = '表外 %d 字 >800：分析方法不进 PRD（最长 %s）' % (total, longest)
    elif total > 400:
        c.add('WARN', h['i'], '表外 %d 字 >400' % total)
        c.detail = '表外 %d 字 >400（最长 %s）' % (total, longest)
    else:
        c.add('INFO', None, '表外 %d 字' % total)
        c.detail = '表外 %d 字' % total
        c.hits_override = None
    return c, total


def check_l25(doc):
    c = Check('L25')
    ac_lines = set()
    for h in doc.find_sections(RE_SEC_AC, (1,)):
        ac_lines |= set(range(h['i'], h['end'] + 1))
    heads = doc.headings
    segs = []
    for k, h in enumerate(heads):
        if (h['level'] != 3 or not RE_US_R_HEAD.match(h['text']) or not doc.in_body[h['i']]
                or h['i'] in doc.residual or h['i'] in ac_lines):
            continue
        end = len(doc.lines) - 1
        for h2 in heads[k + 1:]:
            if h2['level'] <= 2 or RE_US_R_HEAD.match(h2['text']):
                end = h2['i'] - 1
                break
        segs.append([(i, vis(doc.lines[i])) for i in range(h['i'], end + 1)
                     if doc.in_body[i] and i not in doc.residual and doc.kind[i] != 'wb'])
    if not segs:
        c.detail = '无「### US-R」段'
        return c
    has_global = any(RE_SEC_GLOBAL.search(h['text']) for h in heads if doc.in_body[h['i']] and h['i'] not in doc.residual)
    need = 4 if has_global else 3
    counts, bad = [], []
    for words in PLATFORM_TERMS:
        label = '/'.join(words)
        at = []
        for seg in segs:
            hit = next((i for i, t in seg if any(w in t for w in words)), None)
            if hit is not None:
                at.append(hit)
        counts.append((label, len(at)))
        if len(at) >= need:
            bad.append(label)
            for i in at:
                c.add('WARN', i, '「%s」%d 段 ≥%d' % (label, len(at), need))
    shown = ' · '.join('%s %d' % kv for kv in sorted(counts, key=lambda kv: -kv[1]) if kv[1]) or '均 0'
    basis = 'US-R %d 段 · 阈值 ≥%d%s' % (len(segs), need, '（已有全局口径节）' if has_global else '')
    if bad:
        c.detail = '%s≥%d 段：收进全局口径；%s：%s' % ('、'.join('「%s」' % x for x in bad), need, basis, shown)
        c.hits_override = len(bad)
    else:
        c.add('INFO', None, shown)
        c.detail = '%s：%s' % (basis, shown)
        c.hits_override = None
    return c


def check_l26(doc):
    c = Check('L26')
    parts = []
    for t in doc.tables:
        hd = t['header']
        if not any('原型' in h or '元素' in h for h in hd):
            continue
        cols = [k for k, h in enumerate(hd) if '说明' in h] or [k for k, h in enumerate(hd) if '原型' not in h and '元素' not in h]
        el = find_col(hd, lambda h: '元素' in h)
        for row in t['grid'][1:]:
            for k in cols:
                if k >= len(row['cells']):
                    continue
                cell = row['cells'][k]
                if not cell.get('origin', True) or not RE_REUSE_ROW.search(cell['text']):
                    continue
                items = [strip_tags(m.group(1)) for m in RE_LI.finditer(cell['raw'])]
                if len(items) < cell['text'].count('•'):
                    items = cell['text'].split('•')[1:]
                reuse = sum(1 for x in items if RE_REUSE_ROW.search(x))
                if len(items) < 3 or reuse < 2:
                    continue
                name = short(row['cells'][el]['text'], 12) if el is not None and el < len(row['cells']) else ''
                desc = '%s%d 条（含沿用 %d 条）' % ('「%s」' % name if name else 'L%d ' % (cell['line'] + 1), len(items), reuse)
                c.add('WARN', cell['line'], desc)
                parts.append(desc)
    if parts:
        c.detail = '%d 格：%s：沿用的一句引用，别展开' % (len(parts), '、'.join(parts[:5]))
    return c


# ---------------------------------------------------------------- 汇总与输出

def run(text, profile):
    doc = Doc(text)
    track_lines = doc.table_line_set(is_track_table)
    checks = [check_l01(doc, profile), check_l02(doc), check_l03(doc, track_lines), check_l04(doc),
              check_l05(doc), check_l06(doc), check_l07(doc), check_l08(doc), check_l09(doc), check_l10(doc),
              check_l11(doc), check_l12(doc, track_lines), check_l13(doc), check_l14(doc), check_l15(doc)]
    l18, fr = check_l18(doc)
    checks.append(check_l16(doc, len(fr)))
    checks.append(check_l17(doc))
    checks.append(l18)
    cjk = cjk_count(doc)
    checks.append(check_l19(doc, cjk, len(fr)))
    checks.append(check_l20(doc))
    l22, ac_stat = check_l22(doc)
    l24, track_prose = check_l24(doc)
    checks += [l22, l24, check_l25(doc), check_l26(doc), check_l27(doc), check_l28(doc)]
    checks.sort(key=lambda ch: ch.id)
    summary = {s: sum(1 for ch in checks if ch.status == s) for s in ('FAIL', 'WARN', 'INFO', 'OK')}
    summary['cjk_chars'] = cjk
    summary['acceptance_avg'], summary['acceptance_max'] = ac_stat if ac_stat else (None, None)
    summary['tracking_prose_cjk'] = track_prose
    return doc, checks, summary


def md_cell(s):
    return str(s).replace('\n', ' ').replace('|', '\\|')


def fmt_lines(ls):
    if not ls:
        return '—'
    s = ', '.join(str(x) for x in ls[:5])
    return s + (' …+%d' % (len(ls) - 5) if len(ls) > 5 else '')


def dash(v):
    return '—' if v is None else v


def render_table(path, profile, doc, checks, summary):
    out = ['prd_lint · %s · profile=%s · %s' % (path, profile, '导出稿' if doc.is_export else '起草稿'), '',
           '| 编号 | 检查 | 状态 | 命中数 | 位置 | 修法 |', '|---|---|---|---|---|---|']
    for ch in checks:
        name = ch.name + ('：' + ch.detail if ch.detail else '')
        hits = '—' if ch.hits is None else ch.hits
        out.append('| %s | %s | %s | %s | %s | %s |' % (
            ch.id, md_cell(name), ch.status, hits, md_cell(fmt_lines(ch.lines())), md_cell(ch.fix)))
    out.append('')
    out.append('FAIL %d · WARN %d · INFO %d · 正文 CJK 字数 %d · 验收 avg %s / max %s · 埋点表外 %s 字' % (
        summary['FAIL'], summary['WARN'], summary['INFO'], summary['cjk_chars'], dash(summary['acceptance_avg']),
        dash(summary['acceptance_max']), dash(summary['tracking_prose_cjk'])))
    return '\n'.join(out)


def main(argv=None):
    ap = argparse.ArgumentParser(description='PRD 确定性 lint（只测事实、不做判断；FAIL 必须修，WARN 按 05 判）')
    ap.add_argument('path', help='PRD markdown 文件')
    ap.add_argument('--json', action='store_true', help='输出与表格同构的 JSON')
    ap.add_argument('--profile', choices=('standard', 'light'), default='standard')
    args = ap.parse_args(argv)
    try:
        with open(args.path, 'r', encoding='utf-8', errors='replace') as fh:
            text = fh.read()
    except (IOError, OSError) as e:
        sys.stderr.write('prd_lint: 读不了文件 %s（%s）\n' % (args.path, e))
        return 2
    doc, checks, summary = run(text, args.profile)
    code = 1 if summary['FAIL'] else 0
    if args.json:
        payload = {'file': args.path, 'profile': args.profile, 'doc_kind': 'export' if doc.is_export else 'draft',
                   'checks': [ch.to_dict() for ch in checks], 'summary': summary, 'exit_code': code}
        sys.stdout.write(json.dumps(payload, ensure_ascii=False, indent=2) + '\n')
    else:
        sys.stdout.write(render_table(args.path, args.profile, doc, checks, summary) + '\n')
    return code


if __name__ == '__main__':
    sys.exit(main())
