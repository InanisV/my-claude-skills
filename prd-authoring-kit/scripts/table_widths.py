#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# PRD Authoring Kit · © Noah Zhan (@noah.zhan) · 二次分发/衍生须保留署名，不得标榜为自己原创创作。LICENSE / NOTICE 见根目录。
"""表格列宽体检 —— 发布后核对每张表的列宽方案是否与 house 一致、列宽与内容是否匹配。

用法：python3 scripts/table_widths.py <fetched.xml | fetched.json | PRD.md>
输入：`lark-cli docs +fetch --detail full --doc-format xml` 的输出（可直接是 JSON 包裹：以 `{` 开头时递归找第一个含 `<table`
的字符串字段），或含 HTML `<table>` 的 markdown 导出稿（管道表没有列宽，只计数不体检）。

- 逐表取 `<colgroup><col width>`、表头文本、行数；按逻辑列（处理 rowspan / colspan）统计每列最长格的字符数（去空白折叠）。
- 分组：表头含 原型 & 元素 & 说明 → 元素四列表；含 Version / 版本 & Author / 作者 → 编写记录；10 列且含 事件名称 → 埋点；
  2 列且表头是 项 | 定义、口径 | 规则、事项 | 口径 → 二列口径；其余 2 列 → 其它二列表（只看一致性）；其余 → 其它（按表头签名再分）。
- 续表：飞书把长表拆成多张时，紧跟在后、同标题前文、同列宽、无 <thead> / <th>、首行不像表头（不含本组表头关键词，且不是一排
  ≤8 字无数字的短词）的表并回上一张。
- 问题：与 HOUSE 不符、同组多方案（非本组主方案）、宽 ≥200 且最长 ≤12 字、宽 ≤150 且最长 ≥60 字（正文 <2 行的表不比）、无 colgroup。
- 退出码：元素四列表方案数 >1，或元素 / 编写记录 / 埋点表有不等于 HOUSE 的 → 1；二列口径不等于 HOUSE 只报不退；否则 0；
  读文件 / 参数错误 → 2。
- 只用标准库、Python 3.9 兼容；不读网络。
"""

import json
import re
import sys
from collections import Counter, OrderedDict
from html.parser import HTMLParser

HOUSE = {
    '元素四列表': [80, 140, 328, 325],
    '编写记录': [54, 72, 230, 84, 84, 84, 90],
    '二列口径': [150, 545],
    '埋点': [210, 170, 145, 230, 140, 130, 74, 235, 210, 185],
}
GROUP_ORDER = ['元素四列表', '编写记录', '埋点', '二列口径', '其它二列表']
EXIT_GROUPS = ('元素四列表', '编写记录', '埋点')  # 只有这三组不等于 HOUSE 才退出 1；二列口径只报不退
TWO_COL_HEADS = (('项', '定义'), ('口径', '规则'), ('事项', '口径'))
GROUP_KEYS = {'元素四列表': ('元素',), '编写记录': ('Version', '版本'), '埋点': ('事件名称',)}
RE_MD_HEADING = re.compile(r'^ {0,3}(#{1,6})\s+(.*?)\s*#*\s*$')
RE_PIPE_SEP = re.compile(r'^\s*\|?\s*:?-+:?\s*(?:\|\s*:?-+:?\s*)*\|?\s*$')


def find_table_string(obj):
    if isinstance(obj, str):
        return obj if '<table' in obj else None
    if isinstance(obj, dict):
        obj = list(obj.values())
    if isinstance(obj, list):
        for v in obj:
            got = find_table_string(v)
            if got is not None:
                return got
    return None


def load(path):
    with open(path, 'r', encoding='utf-8', errors='replace') as fh:
        text = fh.read()
    if text.lstrip().startswith('{'):
        try:
            got = find_table_string(json.loads(text))
        except ValueError:
            got = None
        if got is None:
            raise ValueError('JSON 里没有含 <table 的字符串字段')
        text = got
    pipe = 0
    out = []
    lines = text.split('\n')
    for k, ln in enumerate(lines):  # markdown 标题转成 <hN>，管道表只计数
        m = RE_MD_HEADING.match(ln)
        if m and not ln.lstrip().startswith('<'):
            n = len(m.group(1))
            out.append('<h%d>%s</h%d>' % (n, m.group(2).replace('<', '&lt;'), n))
            continue
        if RE_PIPE_SEP.match(ln) and ln.strip().startswith('|') and k > 0 and lines[k - 1].strip().startswith('|'):
            pipe += 1
        out.append(ln)
    return '\n'.join(out), pipe


class TableParser(HTMLParser):
    def __init__(self):
        HTMLParser.__init__(self, convert_charrefs=True)
        self.tables, self.stack = [], []
        self.heading, self.h_buf, self.in_h = '', [], False

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if re.match(r'^h[1-6]$', tag) and not self.stack:
            self.in_h, self.h_buf = True, []
        elif tag == 'table':
            self.stack.append({'title': self.heading, 'widths': [], 'colgroup': False, 'rows': [],
                               'row': None, 'cell': None, 'thead': False})
        elif not self.stack:
            return
        t = self.stack[-1] if self.stack else None
        if t is None:
            return
        if tag == 'colgroup':
            t['colgroup'] = True
        elif tag == 'thead':
            t['thead'] = True
        elif tag == 'col':
            w = re.match(r'\d+', a.get('width') or '')
            t['widths'].append(int(w.group(0)) if w else None)
        elif tag == 'tr':
            t['row'] = []
        elif tag in ('td', 'th'):
            if tag == 'th':
                t['thead'] = True
            def num(k):
                m = re.match(r'\d+', a.get(k) or '1')
                return max(1, int(m.group(0))) if m else 1
            t['cell'] = {'text': [], 'rowspan': num('rowspan'), 'colspan': num('colspan')}
        elif tag in ('br', 'p', 'li') and t['cell'] is not None:
            t['cell']['text'].append(' ')

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)

    def handle_endtag(self, tag):
        if re.match(r'^h[1-6]$', tag) and self.in_h:
            self.in_h = False
            self.heading = re.sub(r'\s+', ' ', ''.join(self.h_buf)).strip()
            return
        if not self.stack:
            return
        t = self.stack[-1]
        if tag in ('td', 'th') and t['cell'] is not None:
            if t['row'] is None:
                t['row'] = []
            t['row'].append(t['cell'])
            t['cell'] = None
        elif tag == 'tr' and t['row'] is not None:
            t['rows'].append(t['row'])
            t['row'] = None
        elif tag == 'table':
            self.tables.append(self.stack.pop())

    def handle_data(self, data):
        if self.in_h:
            self.h_buf.append(data)
        if self.stack and self.stack[-1]['cell'] is not None:
            self.stack[-1]['cell']['text'].append(data)


def norm(s):
    return re.sub(r'\s+', ' ', ''.join(s)).strip()


def layout(t, cont=False):
    """把行展开到逻辑列：rowspan 占位的列跳过；返回 (表头文本列表, 每列最长字数, 逻辑列数)。cont=续表（无表头行）。"""
    pending = {}  # 列号 → 还要占用的行数
    grid = []
    for row in t['rows']:
        out, col, queue = {}, 0, list(row)
        while queue:
            while pending.get(col, 0) > 0:
                pending[col] -= 1
                col += 1
            c = queue.pop(0)
            txt = norm(c['text'])
            for k in range(c['colspan']):
                out[col] = txt if k == 0 else ''
                if c['rowspan'] > 1:
                    pending[col] = c['rowspan'] - 1
                col += 1
        for k in list(pending):  # 行尾被占的列也要消耗一行
            if k >= col and pending[k] > 0:
                pending[k] -= 1
        grid.append(out)
    ncol = max([max(r) + 1 for r in grid if r] + [len(t['widths'])] + [0])
    header = [grid[0].get(k, '') for k in range(ncol)] if grid else []
    maxc = [max([len(r.get(k, '').replace(' ', '')) for r in grid[0 if cont else 1:]] + [0]) for k in range(ncol)]
    return header, maxc, ncol


def looks_like_header(cells, group):
    """首行像表头：含本组表头关键词，或每格都是 ≤8 字、不含数字的短词（续表首行是数据，通常带编号 / 日期 / 长句）。"""
    joined = ' '.join(cells)
    if any(k in joined for k in GROUP_KEYS.get(group, ())):
        return True
    vals = [x for x in cells if x]
    return bool(vals) and all(len(x) <= 8 and not re.search(r'\d', x) for x in vals)


def group_of(header, ncol):
    hd = ' '.join(header)
    if '原型' in hd and '元素' in hd and '说明' in hd:
        return '元素四列表'
    if re.search(r'Version|版本', hd, re.I) and re.search(r'Author|作者', hd, re.I):
        return '编写记录'
    if ncol == 10 and '事件名称' in hd:
        return '埋点'
    if ncol == 2:
        pair = tuple(re.sub(r'\s+', '', h) for h in header[:2])
        return '二列口径' if pair in TWO_COL_HEADS else '其它二列表'
    return '其它：' + ' / '.join(h[:8] for h in header)


def fmt_w(ws):
    return '/'.join('?' if w is None else str(w) for w in ws) if ws else '—'


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) != 1 or argv[0] in ('-h', '--help'):
        sys.stderr.write('用法：python3 table_widths.py <fetched.xml | fetched.json | PRD.md>\n')
        return 2
    try:
        text, pipe = load(argv[0])
    except (IOError, OSError, ValueError) as e:
        sys.stderr.write('table_widths: 读不了 %s（%s）\n' % (argv[0], e))
        return 2
    p = TableParser()
    p.feed(text)
    p.close()
    rows = []
    for k, t in enumerate(p.tables):
        header, maxc, ncol = layout(t)
        prev = rows[-1] if rows else None
        cont = (prev is not None and not t['thead'] and t['title'] == prev['title'] and t['widths']
                and t['widths'] == prev['widths'] and ncol == prev['ncol'] and not looks_like_header(header, prev['group']))
        if cont:  # 飞书把长表拆成多张无表头的续表：沿用上一张的表头与分组，全部行都算内容
            _, maxc, ncol = layout(t, cont=True)
            header = prev['header']
        rows.append({'id': 'T%02d' % (k + 1), 'title': t['title'], 'widths': t['widths'], 'colgroup': t['colgroup'] and bool(t['widths']),
                     'header': header, 'maxc': maxc, 'ncol': ncol, 'nrow': len(t['rows']), 'cont': bool(cont),
                     'group': prev['group'] if cont else group_of(header, ncol)})
    groups = OrderedDict()
    for g in GROUP_ORDER:
        groups[g] = []
    for r in rows:
        groups.setdefault(r['group'], []).append(r)
    bad_exit = False
    out = ['# 表格列宽体检 · %s' % argv[0], '',
           '共 %d 张 HTML 表%s。HOUSE：%s。' % (len(rows), '（另有管道表 %d 张，无列宽未计）' % pipe if pipe else '',
                                        '；'.join('%s %s' % (g, fmt_w(w)) for g, w in HOUSE.items())), '',
           '## 分组', '', '| 组 | 表数 | 方案数 | 各方案 × 张数 | 等于 HOUSE |', '|---|---|---|---|---|']
    major = {}
    for g, items in groups.items():
        if not items:
            continue
        schemes = Counter(tuple(r['widths']) for r in items)
        major[g] = schemes.most_common(1)[0][0]
        house = HOUSE.get(g)
        if house is None:
            eq = '（无 HOUSE，只看一致性）' if len(schemes) > 1 and g == '其它二列表' else '（无 HOUSE）'
        else:
            n_eq = sum(1 for r in items if r['widths'] == house)
            eq = '全部 = HOUSE' if n_eq == len(items) else '%d / %d = HOUSE' % (n_eq, len(items))
            if n_eq != len(items) and g in EXIT_GROUPS:
                bad_exit = True
            elif n_eq != len(items):
                eq += '（只报不退）'
        if g == '元素四列表' and len(schemes) > 1:
            bad_exit = True
        n_cont = sum(1 for r in items if r['cont'])
        out.append('| %s | %s | %d | %s | %s |' % (g.replace('|', '\\|'),
                                                 '%d（含续表 %d）' % (len(items), n_cont) if n_cont else str(len(items)), len(schemes),
                                                 '；'.join('%s × %d' % (fmt_w(list(s)), n) for s, n in schemes.most_common()),
                                                 eq))
    out += ['', '## 逐表', '', '| 表 | 标题前文 | 组 | 行数 | 列宽 | 每列 maxchars | 问题 |', '|---|---|---|---|---|---|---|']
    for r in rows:
        probs = []
        house = HOUSE.get(r['group'])
        if not r['colgroup']:
            probs.append('无 colgroup')
        elif house is not None and r['widths'] != house:
            probs.append('与 HOUSE 不符')
        if len([1 for x in groups[r['group']]]) > 1 and len(set(tuple(x['widths']) for x in groups[r['group']])) > 1 \
                and tuple(r['widths']) != major[r['group']]:
            probs.append('同组多方案')
        if r['colgroup'] and len(r['widths']) != r['ncol']:
            probs.append('col %d 个 ≠ 逻辑列 %d' % (len(r['widths']), r['ncol']))
        body_rows = r['nrow'] if r['cont'] else r['nrow'] - 1
        for k, w in enumerate(r['widths'] if body_rows >= 2 else []):  # 正文 <2 行的表不比宽度与内容
            if w is None or k >= len(r['maxc']):
                continue
            m = r['maxc'][k]
            if w >= 200 and m <= 12:
                probs.append('列%d 宽 %d 只 %d 字' % (k + 1, w, m))
            if w <= 150 and m >= 60:
                probs.append('列%d 宽 %d 却 %d 字' % (k + 1, w, m))
        title = (r['title'] or '—')[:16].replace('|', '\\|')
        grp = (r['group'] if not r['group'].startswith('其它：') else '其它') + ('（续表）' if r['cont'] else '')
        out.append('| %s | %s | %s | %d | %s | %s | %s |' % (r['id'], title, grp, r['nrow'], fmt_w(r['widths']),
                                                          '/'.join(str(x) for x in r['maxc']), '；'.join(probs) or '—'))
    out += ['', '退出码 %d（%s）' % (1 if bad_exit else 0,
                                 '元素四列表多方案，或元素 / 编写记录 / 埋点表有不等于 HOUSE 的' if bad_exit
                                 else '元素四列表单一方案，元素 / 编写记录 / 埋点表全部 = HOUSE（二列表只报不退）')]
    sys.stdout.write('\n'.join(out) + '\n')
    return 1 if bad_exit else 0


if __name__ == '__main__':
    sys.exit(main())
