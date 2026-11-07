#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# PRD Authoring Kit · © Noah Zhan (@noah.zhan) · 二次分发/衍生须保留署名，不得标榜为自己原创创作。LICENSE / NOTICE 见根目录。
"""会议逐字稿台账体检 —— 把 04 d5 里能机械化的台账检查打成 FAIL / WARN / INFO 事实表（2.2.1 起）。

执行而非阅读：先落盘逐字稿、建完台账再跑；交付简报的数字行用 summary 产出，不手算。
用法：python3 scripts/meeting_ledger.py check --transcript <meeting-YYYYMMDD-N.txt> --ledger <meeting-YYYYMMDD-N-ledger.md>
                                           [--json] [--min-ratio 500] [--gap-min 5]
      python3 scripts/meeting_ledger.py summary --ledger <meeting-YYYYMMDD-N-ledger.md> [--excluded]
输入：逐字稿 = 原样落盘的文本（带时间戳更好）；台账 = 04 d5 固定八列管道表
  `| # | 时间 | 说话人 | 原话 | 性质 | PRD 位置 | 处理 | 备注 |`。

本脚本只测事实、不做判断；FAIL 必须修，WARN 由模型回逐字稿判（重读那一段 / 补一行 / 确认无话可记），INFO 抄进报告。
- 检查项：
  M01 FAIL 台账表头不等于固定八列（找不到表也算）；台账 0 数据行。
  M02 FAIL 任一行「性质」不在 拍板 / 候选 / 疑问 / 现状 / 行动项 / 无关 内（空也算）。
  M03 FAIL 任一行「处理」不在 已在稿 / 本轮改 / 待确认 / 待核实 / 排除 / 无关 内或为空。
  M04 FAIL 台账行数 < 逐字稿字数 ÷ --min-ratio（默认 500）；逐字稿 < 500 字（空文件 / 落盘失败）。
  M05 WARN 逐字稿时间轴上任意连续 --gap-min 分钟（默认 5）没有台账行 → 报区间；逐字稿无时间戳 → INFO 跳过；
           像时间戳的串 ≥10 处却一个都没认成时间轴 → WARN（标题行格式没认出来）。
  M06 WARN 「本轮改 / 已在稿」行的「PRD 位置」为空。
  M07 WARN 「待核实」行的「备注」为空（没写责任方）。
  M08 INFO 性质 × 处理 计数矩阵。
  M09 WARN 「候选 / 疑问」行的处理是 本轮改 / 排除 / 无关，但备注里没有「产品答复」。
- summary：输出 04 d5 交付简报那一行；`--excluded` 另列排除项（时间 + 原话 + 备注）。台账有 M01–M03 FAIL（含 0 数据行）时照样输出、退出码 1。
- 退出码：有 FAIL → 1；否则 0；参数 / 读文件错误 → 2。--json 输出与表格同构。
- 只用标准库、Python 3.9 兼容；不读网络、不碰飞书。逐字稿与台账属公司会议内容，本脚本不外传、不写任何文件。

口径细节：
- 时间戳 = `HH:MM:SS` 或 `MM:SS`，半角 / 全角冒号都认（可带 [ ] / ( ) / 【 】 包裹）；只认行首的时间戳，或「说话人 + 时间戳」这类
  标题行（去掉时间戳后 ≤30 个非空白字符，如「产品经理（会议主持人） 00:00:10」）里的时间戳——长正文里顺口说的「10:30 开会」不算。
  已知限制：正文行若以「45:00 那个版本…」开头，会被当成行首时间戳（可能拉长时间轴末端），按 WARN 回逐字稿判即可。
- 逐字稿字数 = 去掉时间戳标题行（行首时间戳后 ≤10 个非空白字符的行，或其它带时间戳且去掉后 ≤30 字的行）、行首时间戳与全部空白
  后的字符数（中英文字符各计 1）。
- 台账表 = 表头恰好等于固定八列的第一张管道表；没有就取第一张表头同时含「性质」「处理」的表（都没有就取第一张管道表）；之后
  表头相同的续表并入，其它表（如待确认清单、反向核对表）不计。
- 「性质」「处理」格取值前去掉 * 与反引号（`**拍板**` 按「拍板」算）；行的列数 ≠ 表头列数时 M02 detail 提示转义竖线。
  表头不等于固定八列时，表头里找得到的列按名取，找不到的按位置取。
- 空格判定：去空白后为空，或只有 - / — / – / / / 无 → 视为空。
- 台账「时间」格里可写区间（`00:23:41–00:24:10`），格内所有时间戳都算覆盖点；时间超出逐字稿轴的不计。
- M05 区间 = 逐字稿首个时间戳到末个时间戳；相邻覆盖点（含两端）间隔 ≥ gap-min 分钟即报。
"""

import argparse
import json
import math
import re
import sys
from collections import OrderedDict

HEADER = ['#', '时间', '说话人', '原话', '性质', 'PRD 位置', '处理', '备注']
NATURES = ['拍板', '候选', '疑问', '现状', '行动项', '无关']
ACTIONS = ['已在稿', '本轮改', '待确认', '待核实', '排除', '无关']
EMPTY_MARKS = {'', '-', '—', '–', '/', '无'}
NEED_POS = ('本轮改', '已在稿')
UNSURE = ('候选', '疑问')
ANSWER_NEEDED = ('本轮改', '排除', '无关')
MIN_TRANSCRIPT = 500   # 逐字稿字数下限：低于它多半是空文件 / 落盘失败
HEADER_LINE_MAX = 30  # 非行首时间戳的标题行：去掉时间戳后最多几个非空白字符

FIX = {
    'M01': '按 04 d5 改成固定八列表头：| # | 时间 | 说话人 | 原话 | 性质 | PRD 位置 | 处理 | 备注 |',
    'M02': '按 04 d5 性质六选一；说不准的记「疑问」，别自造词',
    'M03': '按 04 d5 处理六选一，每行必填；候选 / 疑问没定的填「待确认」',
    'M04': '读漏了：回逐字稿按发言重切，一个话题一个说法一行',
    'M05': '回逐字稿重读该区间，补行或确认无话可记',
    'M06': '写 PRD 位置（章 / US-R / 元素表），否则无法回读核对',
    'M07': '备注写责任方（研发 / 设计 / 测试 / 某角色）',
    'M08': '抄进交付简报；数字行用 summary 产出',
    'M09': '候选 / 疑问先在对话里问产品，答复后备注写「产品答复：<原话 ≤20 字>」再改处理',
}

RE_TS = re.compile(r'(?<![\d:：])(\d{1,3})[:：]([0-5]\d)(?:[:：]([0-5]\d))?(?![\d:：])')
RE_TS_HEAD = re.compile(r'^\s*[\[(（【]?\s*(\d{1,3})[:：]([0-5]\d)(?:[:：]([0-5]\d))?\s*[\])）】]?(?![\d:：])')
RE_SEP = re.compile(r'^\s*\|?\s*:?-+:?\s*(?:\|\s*:?-+:?\s*)*\|?\s*$')
RE_WS = re.compile(r'\s+')


# ---------------------------------------------------------------- 结果对象

class Check(object):
    def __init__(self, cid, name, status='OK', hits=None, detail='', where=None, extra=None):
        self.id = cid
        self.name = name
        self.status = status
        self.hits = hits
        self.detail = detail
        self.where = where or []
        self.extra = extra

    def to_dict(self):
        d = OrderedDict([('id', self.id), ('name', self.name), ('status', self.status), ('hits', self.hits),
                         ('detail', self.detail), ('where', self.where), ('fix', FIX.get(self.id, ''))])
        if self.extra is not None:
            d['extra'] = self.extra
        return d


# ---------------------------------------------------------------- 时间戳

def ts_seconds(m):
    a, b, c = m.group(1), m.group(2), m.group(3)
    if c is None:  # MM:SS
        return int(a) * 60 + int(b)
    if int(b) > 59:
        return None
    return int(a) * 3600 + int(b) * 60 + int(c)


def fmt_ts(sec):
    return '%02d:%02d:%02d' % (sec // 3600, (sec % 3600) // 60, sec % 60)


def read_text(path):
    with open(path, 'r', encoding='utf-8-sig', errors='replace') as fh:
        return fh.read()


def parse_transcript(text):
    """返回 (字数, 时间戳秒列表)。"""
    chars = 0
    stamps = []
    for line in text.splitlines():
        m = RE_TS_HEAD.match(line)
        if m:  # 行首时间戳：记时间，正文去掉时间戳再数
            sec = ts_seconds(m)
            if sec is not None:
                stamps.append(sec)
            body = RE_WS.sub('', line[m.end():])
            if len(body) > 10:
                chars += len(body)
            continue  # 去掉时间戳后 ≤10 字 = 时间戳标题行（「00:01:23 说话人 1」），不计字数
        found = list(RE_TS.finditer(line))
        rest = RE_WS.sub('', RE_TS.sub('', line)) if found else ''
        if found and len(rest) <= HEADER_LINE_MAX:  # 「说话人 1  00:01:23」「产品经理（会议主持人） 00:00:10」这类标题行
            for t in found:
                sec = ts_seconds(t)
                if sec is not None:
                    stamps.append(sec)
            continue
        chars += len(RE_WS.sub('', line))  # 正文里顺口说的时间不算时间戳，照常计字
    return chars, stamps


# ---------------------------------------------------------------- 台账

def split_row(line):
    s = line.strip()
    if s.startswith('|'):
        s = s[1:]
    if s.endswith('|') and not s.endswith('\\|'):
        s = s[:-1]
    cells, buf, i = [], [], 0
    while i < len(s):
        ch = s[i]
        if ch == '\\' and i + 1 < len(s) and s[i + 1] == '|':
            buf.append('|')
            i += 2
            continue
        if ch == '|':
            cells.append(''.join(buf).strip())
            buf = []
        else:
            buf.append(ch)
        i += 1
    cells.append(''.join(buf).strip())
    return cells


def norm_head(c):
    return RE_WS.sub(' ', c.replace('*', '').strip())


def find_tables(text):
    """返回 [(表头 cells, 表头行号, [(行号, cells), ...])]。"""
    lines = text.splitlines()
    tables = []
    i = 0
    while i < len(lines):
        if lines[i].lstrip().startswith('|') and i + 1 < len(lines) and RE_SEP.match(lines[i + 1]) \
                and '-' in lines[i + 1]:
            head = [norm_head(c) for c in split_row(lines[i])]
            rows = []
            j = i + 2
            while j < len(lines) and lines[j].lstrip().startswith('|'):
                if not RE_SEP.match(lines[j]):
                    rows.append((j + 1, split_row(lines[j])))
                j += 1
            tables.append((head, i + 1, rows))
            i = j
        else:
            i += 1
    return tables


def is_empty(v):
    return RE_WS.sub('', v) in EMPTY_MARKS


def parse_ledger(text):
    """返回 dict：header, header_line, rows=[{line, cells:{列名: 值}}]，或 header=None（找不到表）。"""
    tables = find_tables(text)
    if not tables:
        return {'header': None, 'header_line': None, 'rows': []}
    main = next((t for t in tables if t[0] == HEADER), None)
    for t in ([] if main else tables):
        if '性质' in t[0] and '处理' in t[0]:
            main = t
            break
    if main is None:
        main = tables[0]
    head = main[0]
    idx = {}
    for k, name in enumerate(HEADER):
        idx[name] = head.index(name) if name in head else (k if k < len(head) else None)
    rows = []
    for t in tables:
        if t[0] != head:
            continue
        for ln, cells in t[2]:
            vals = OrderedDict()
            for name in HEADER:
                k = idx[name]
                v = cells[k].strip() if k is not None and k < len(cells) else ''
                vals[name] = v.replace('*', '').replace('`', '').strip() if name in ('性质', '处理') else v
            rows.append({'line': ln, 'cells': vals, 'ncells': len(cells)})
    return {'header': head, 'header_line': main[1], 'rows': rows}


def counts(rows):
    nat = OrderedDict((n, 0) for n in NATURES)
    act = OrderedDict((a, 0) for a in ACTIONS)
    for r in rows:
        n, a = r['cells']['性质'], r['cells']['处理']
        if n in nat:
            nat[n] += 1
        if a in act:
            act[a] += 1
    return nat, act


def summary_line(rows):
    nat, act = counts(rows)
    return ('台账 %d 行：拍板 %d / 候选 %d / 疑问 %d / 现状 %d / 行动项 %d / 无关 %d ｜ '
            '已在稿 %d / 本轮改 %d / 待确认 %d / 待核实 %d / 排除 %d / 无关 %d') % (
        len(rows), nat['拍板'], nat['候选'], nat['疑问'], nat['现状'], nat['行动项'], nat['无关'],
        act['已在稿'], act['本轮改'], act['待确认'], act['待核实'], act['排除'], act['无关'])


# ---------------------------------------------------------------- 检查

def structural_checks(led):
    """M01–M03：summary 也要跑。"""
    out = []
    head = led['header']
    if head is None:
        out.append(Check('M01', '表头 = 固定八列', 'FAIL', 1, '台账里找不到管道表'))
    elif head != HEADER:
        missing = [h for h in HEADER if h not in head]
        extra = [h for h in head if h not in HEADER]
        det = '实际：| %s |' % ' | '.join(head)
        if missing:
            det += '；缺 %s' % '、'.join(missing)
        if extra:
            det += '；多 %s' % '、'.join(extra)
        if not missing and not extra:
            det += '；列序不对'
        out.append(Check('M01', '表头 = 固定八列', 'FAIL', 1, det, [led['header_line']]))
    else:
        out.append(Check('M01', '表头 = 固定八列', 'OK', 0))
    rows = led['rows']
    if head is not None and not rows:  # 只有表头：落盘 / 建台账没做完
        m01 = out[-1]
        m01.status, m01.hits = 'FAIL', (m01.hits or 0) + 1
        m01.detail = (m01.detail + '；' if m01.detail else '') + '台账 0 数据行'
    ncol = len(head) if head else len(HEADER)
    bad_cols = [r for r in rows if r['ncells'] != ncol]
    col_note = ('；'.join('L%d 列数 %d ≠ %d' % (r['line'], r['ncells'], ncol) for r in bad_cols[:3])
                + ('，原话里的 | 要写成 \\|；' if bad_cols else ''))
    bad_n = [r for r in rows if r['cells']['性质'] not in NATURES]
    out.append(Check('M02', '性质在六个枚举内', 'FAIL' if bad_n else 'OK', len(bad_n),
                     (col_note if bad_n else '') + '；'.join('L%d「%s」' % (r['line'], r['cells']['性质'] or '空') for r in bad_n[:8])
                     + (' …+%d' % (len(bad_n) - 8) if len(bad_n) > 8 else ''),
                     [r['line'] for r in bad_n]))
    bad_a = [r for r in rows if r['cells']['处理'] not in ACTIONS]
    out.append(Check('M03', '处理在六个枚举内且非空', 'FAIL' if bad_a else 'OK', len(bad_a),
                     '；'.join('L%d「%s」' % (r['line'], r['cells']['处理'] or '空') for r in bad_a[:8])
                     + (' …+%d' % (len(bad_a) - 8) if len(bad_a) > 8 else ''),
                     [r['line'] for r in bad_a]))
    return out


def run_check(transcript_text, led, min_ratio, gap_min):
    checks = structural_checks(led)
    rows = led['rows']
    chars, stamps = parse_transcript(transcript_text)
    need = int(math.ceil(chars / float(min_ratio))) if chars else 0
    m04_fail = len(rows) < chars / float(min_ratio)
    det = '台账 %d 行；逐字稿 %d 字 → 至少 %d 行' % (len(rows), chars, need)
    if chars < MIN_TRANSCRIPT:
        m04_fail = True
        det = '逐字稿为空或过短（%d 字 < %d），落盘失败？；' % (chars, MIN_TRANSCRIPT) + det
    checks.append(Check('M04', '台账行数 ≥ 逐字稿字数 ÷ %s' % min_ratio, 'FAIL' if m04_fail else 'OK',
                        1 if m04_fail else 0, det))
    # M05
    ts_like = len(RE_TS.findall(transcript_text))
    if not stamps and ts_like >= 10:
        checks.append(Check('M05', '时间轴空档 ≥ %s 分钟' % gap_min, 'WARN', ts_like,
                            '逐字稿里有 %d 处像时间戳，但没认成时间轴；检查标题行格式' % ts_like))
    elif not stamps:
        checks.append(Check('M05', '时间轴空档 ≥ %s 分钟' % gap_min, 'INFO', None, '无时间戳，跳过 M05'))
    else:
        t0, t1 = min(stamps), max(stamps)
        pts = set()
        no_time = 0
        for r in rows:
            found = False
            for m in RE_TS.finditer(r['cells']['时间']):
                sec = ts_seconds(m)
                if sec is None:
                    continue
                found = True
                if t0 <= sec <= t1:
                    pts.add(sec)
            if not found:
                no_time += 1
        seq = [t0] + sorted(pts) + [t1]
        gaps = []
        lim = gap_min * 60
        for a, b in zip(seq, seq[1:]):
            if b - a >= lim and b > a:
                gaps.append((a, b))
        det = '轴 %s–%s，覆盖点 %d 个' % (fmt_ts(t0), fmt_ts(t1), len(pts))
        if no_time:
            det += '，%d 行时间格没有可解析时间戳' % no_time
        if gaps:
            det += '；空档：' + '、'.join('%s–%s' % (fmt_ts(a), fmt_ts(b)) for a, b in gaps)
        checks.append(Check('M05', '时间轴空档 ≥ %s 分钟' % gap_min, 'WARN' if gaps else 'OK', len(gaps), det,
                            ['%s–%s' % (fmt_ts(a), fmt_ts(b)) for a, b in gaps]))
    m06 = [r for r in rows if r['cells']['处理'] in NEED_POS and is_empty(r['cells']['PRD 位置'])]
    checks.append(Check('M06', '本轮改 / 已在稿 写了 PRD 位置', 'WARN' if m06 else 'OK', len(m06), '',
                        [r['line'] for r in m06]))
    m07 = [r for r in rows if r['cells']['处理'] == '待核实' and is_empty(r['cells']['备注'])]
    checks.append(Check('M07', '待核实 备注写了责任方', 'WARN' if m07 else 'OK', len(m07), '',
                        [r['line'] for r in m07]))
    m09 = [r for r in rows if r['cells']['性质'] in UNSURE and r['cells']['处理'] in ANSWER_NEEDED
           and '产品答复' not in r['cells']['备注']]
    checks.append(Check('M09', '候选 / 疑问改本轮改 / 排除 / 无关 有产品答复', 'WARN' if m09 else 'OK', len(m09), '',
                        [r['line'] for r in m09]))
    matrix = OrderedDict()
    for n in NATURES:
        matrix[n] = OrderedDict((a, 0) for a in ACTIONS)
    for r in rows:
        n, a = r['cells']['性质'], r['cells']['处理']
        if n in matrix and a in matrix[n]:
            matrix[n][a] += 1
    checks.append(Check('M08', '性质 × 处理 计数', 'INFO', len(rows), summary_line(rows), extra=matrix))
    checks.sort(key=lambda c: c.id)
    summ = OrderedDict((s, sum(1 for c in checks if c.status == s)) for s in ('FAIL', 'WARN', 'INFO', 'OK'))
    summ['rows'] = len(rows)
    summ['transcript_chars'] = chars
    summ['transcript_stamps'] = len(stamps)
    summ['line'] = summary_line(rows)
    return checks, summ


# ---------------------------------------------------------------- 输出

def md_cell(s):
    return str(s).replace('\n', ' ').replace('|', '\\|')


def fmt_where(ws):
    if not ws:
        return '—'
    s = ', '.join(('L%d' % x) if isinstance(x, int) else str(x) for x in ws[:5])
    return s + (' …+%d' % (len(ws) - 5) if len(ws) > 5 else '')


def render_check(tpath, lpath, checks, summ):
    out = ['meeting_ledger check · 逐字稿 %s · 台账 %s' % (tpath, lpath), '',
           '| 编号 | 检查 | 状态 | 命中数 | 位置 | 修法 |', '|---|---|---|---|---|---|']
    for c in checks:
        name = c.name + ('：' + c.detail if c.detail else '')
        out.append('| %s | %s | %s | %s | %s | %s |' % (c.id, md_cell(name), c.status, '—' if c.hits is None else c.hits,
                                                     md_cell(fmt_where(c.where)), md_cell(FIX.get(c.id, ''))))
    m08 = [c for c in checks if c.id == 'M08'][0]
    out += ['', '性质 × 处理：', '', '| 性质 \\ 处理 | %s |' % ' | '.join(ACTIONS), '|---|%s' % ('---|' * len(ACTIONS))]
    for n, row in m08.extra.items():
        out.append('| %s | %s |' % (n, ' | '.join(str(v) for v in row.values())))
    out += ['', 'FAIL %d · WARN %d · INFO %d · 台账 %d 行 · 逐字稿 %d 字 / 时间戳 %d 个' % (
        summ['FAIL'], summ['WARN'], summ['INFO'], summ['rows'], summ['transcript_chars'], summ['transcript_stamps']),
        summ['line']]
    return '\n'.join(out)


def cmd_check(args):
    try:
        ttext = read_text(args.transcript)
        ltext = read_text(args.ledger)
    except (IOError, OSError) as e:
        sys.stderr.write('meeting_ledger: 读不了文件（%s）\n' % e)
        return 2
    if not (math.isfinite(args.min_ratio) and math.isfinite(args.gap_min)) or args.min_ratio <= 0 or args.gap_min <= 0:
        sys.stderr.write('meeting_ledger: --min-ratio / --gap-min 必须是 > 0 的有限数\n')
        return 2
    led = parse_ledger(ltext)
    checks, summ = run_check(ttext, led, args.min_ratio, args.gap_min)
    code = 1 if summ['FAIL'] else 0
    if args.json:
        payload = OrderedDict([('transcript', args.transcript), ('ledger', args.ledger),
                               ('checks', [c.to_dict() for c in checks]), ('summary', summ), ('exit_code', code)])
        sys.stdout.write(json.dumps(payload, ensure_ascii=False, indent=2) + '\n')
    else:
        sys.stdout.write(render_check(args.transcript, args.ledger, checks, summ) + '\n')
    return code


def cmd_summary(args):
    try:
        ltext = read_text(args.ledger)
    except (IOError, OSError) as e:
        sys.stderr.write('meeting_ledger: 读不了文件（%s）\n' % e)
        return 2
    led = parse_ledger(ltext)
    fails = [c for c in structural_checks(led) if c.status == 'FAIL']
    out = [summary_line(led['rows'])]
    if args.excluded:
        ex = [r for r in led['rows'] if r['cells']['处理'] == '排除']
        out.append('')
        out.append('排除 %d 条：' % len(ex))
        for r in ex:
            c = r['cells']
            out.append('- %s「%s」→ 排除：%s' % (c['时间'] or '（无时间）', c['原话'], c['备注'] or '（未写原因）'))
    sys.stdout.write('\n'.join(out) + '\n')
    if fails:
        sys.stderr.write('meeting_ledger: 台账有 %s FAIL，数字不可信，先跑 check 修完\n' % ' / '.join(c.id for c in fails))
        return 1
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description='会议逐字稿台账体检（04 d5；只测事实、不做判断；FAIL 必须修，WARN 回逐字稿判）')
    sub = ap.add_subparsers(dest='cmd')
    pc = sub.add_parser('check', help='台账 × 逐字稿 体检（M01–M09）')
    pc.add_argument('--transcript', required=True, help='落盘的逐字稿文本 meeting-<YYYYMMDD>-<序号>.txt')
    pc.add_argument('--ledger', required=True, help='台账 meeting-<YYYYMMDD>-<序号>-ledger.md')
    pc.add_argument('--json', action='store_true', help='输出与表格同构的 JSON')
    pc.add_argument('--min-ratio', type=float, default=500, help='每多少字至少一行台账（默认 500）')
    pc.add_argument('--gap-min', type=float, default=5, help='时间轴空档阈值，分钟（默认 5）')
    ps = sub.add_parser('summary', help='输出交付简报的台账数字行')
    ps.add_argument('--ledger', required=True, help='台账 meeting-<YYYYMMDD>-<序号>-ledger.md')
    ps.add_argument('--excluded', action='store_true', help='另列排除项（时间 + 原话 + 备注）')
    try:
        args = ap.parse_args(argv)
    except SystemExit as e:
        return 2 if e.code else 0
    if args.cmd == 'check':
        return cmd_check(args)
    if args.cmd == 'summary':
        return cmd_summary(args)
    ap.print_usage(sys.stderr)
    return 2


if __name__ == '__main__':
    sys.exit(main())
