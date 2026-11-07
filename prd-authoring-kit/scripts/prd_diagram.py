#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# PRD Authoring Kit · © Noah Zhan (@noah.zhan) · 二次分发/衍生须保留署名，不得标榜为自己原创创作。LICENSE / NOTICE 见根目录。
"""PRD 画板生成器：AI 只写内容 spec（JSON），样式 / 尺寸 / 坐标全由本脚本按 references/14-diagram-style.md 写死。

三种图：swimlane（相关方 / 系统泳道）、flow（流程）、state（状态）。spec 范例见 references/examples/diagrams/。

子命令：
  lint    <spec.json>                         校验 schema、密度上限、文本长度；违规逐条打印，退出码 2
  dsl     <spec.json> [-o out.json]           生成 @larksuite/whiteboard-cli 的 DSL（version 2）
  render  <spec.json> --png <out.png>         本地渲染 PNG 预览（目检用）
  publish <spec.json> --whiteboard-token <T>  覆盖写入文档里的空画板块，打印 PUBLISHED <T>
  verify  --whiteboard-token <T> --out <dir>  导出云端画板预览图，打印落盘路径

零第三方依赖（python3 标准库）；render / publish 需要本机有 node（npx），publish / verify 需要已登录的 lark-cli。
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time

WB_CLI = "@larksuite/whiteboard-cli@0.2.13"   # 写死精确版本：不用 ^ / latest

# 样式常量：与 references/14-diagram-style.md 一致，改一处必改另一处。
STYLE = {
    # 色板（三色纪律）
    "ink": "#1F2329",          # 标题 / 正文 / 状态框描边
    "grey": "#646A73",         # 副标题 / 连线标签 / 脚注
    "line": "#7F8A9C",         # 连线
    "edge": "#B8C2CC",         # 普通方框描边
    "band_border": "#E1E5EA",  # 泳道带描边 / 条件标签框描边
    "band_fill": "#F5F7FA",    # 泳道带底
    "white": "#FFFFFF",
    "blue": "#2B6AFF",         # 唯一强调色：泳道色条 / 步骤编号 / 起点圆点
    "human_fill": "#FFF4E0", "human_border": "#D9A441",      # 人工介入
    "visible_fill": "#E8F3EC", "visible_border": "#4C9A6A",  # 用户可见结果
    # 字号
    "fs_title": 20, "fs_subtitle": 13, "fs_lane": 14, "fs_lane_sub": 12, "fs_box": 13,
    "fs_num": 11, "fs_label": 12, "fs_legend": 12, "fs_note": 12, "fs_state": 15,
    # 几何
    "pad": 40, "header_h": 72,
    "lane_h": 112, "lane_gap": 12, "lane_radius": 8, "strip_w": 4, "lane_name_w": 140,
    "step_w": 160, "step_h": 56, "step_radius": 8, "col_w": 208,          # 列宽 = 框宽 160 + 间距 48
    "state_w": 168, "state_h": 48, "state_border": 1.5,
    "decision_w": 120, "decision_h": 72, "terminal_w": 120, "terminal_h": 40,
    "dot": 12, "line_w": 1.5, "row_gap": 56, "min_col_gap": 64,
    # 文本上限（视觉宽度单位：汉字 = 1，ASCII ≈ 0.55）
    "box_total": 14, "box_line1": 9, "box_line": 10, "label_max": 12, "note_lines": 3, "note_len": 60,
    "lane_name_max": 8, "lane_sub_max": 10, "subtitle_max": 40, "title_max": 24,
    "decision_line": 7, "state_line": 9, "terminal_line": 7,
    # 密度上限（07 §五 10）
    "max_lanes": 5, "max_per_lane": 7, "max_boxes": 16, "max_nodes": 12, "max_edges": 20,
}
S = STYLE

LEGEND_TEXT = {
    "swimlane": {"solid": "请求 / 操作", "dashed": "结论 / 事件"},
    "flow": {"solid": "请求 / 操作", "dashed": "结论 / 事件"},
    "state": {"solid": "状态变化", "dashed": "状态不变的处理"},
}
SEM = {"human": ("human_fill", "human_border", "人工介入"), "visible": ("visible_fill", "visible_border", "用户可见结果")}


# ---------------------------------------------------------------- 文本度量

def _wide(c):
    o = ord(c)
    return o >= 0x2E80 or 0xFF00 <= o <= 0xFFEF


def units(s):
    return sum(1.0 if _wide(c) else 0.55 for c in s)


def text_px(s, fs):
    return max((units(line) for line in s.split("\n")), default=0) * fs


BREAK_AFTER = set("，、。；：）)」/ -·的后时")
BREAK_BEFORE = set("并和与及或再且（(「")  # 在连词前断行，少切开双字词（如「数据」）


def wrap_box(text, line1=None, line=None):
    """方框正文自动折成 ≤2 行；显式 \\n 原样尊重。返回行列表。"""
    line1 = line1 or S["box_line1"]
    line = line or S["box_line"]
    if "\n" in text:
        return text.split("\n")
    if units(text) <= line1:
        return [text]
    total = units(text)
    best, best_score = None, None
    for i in range(1, len(text)):
        a, b = text[:i], text[i:]
        if a[-1].isascii() and a[-1].isalnum() and b[0].isascii() and b[0].isalnum():
            continue  # 不切英文单词 / 数字
        if units(a) > line1 or units(b) > line:
            continue
        score = abs(units(a) - total / 2) - (1.5 if a[-1] in BREAK_AFTER or b[0] in BREAK_BEFORE else 0)
        if best_score is None or score < best_score:
            best, best_score = i, score
    if best is None:
        return [text]  # 放不下；lint 会报
    return [text[:best].rstrip(), text[best:].lstrip()]


# ---------------------------------------------------------------- lint

def _load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _col_key(n):
    m = re.match(r"^(\d+)", str(n))
    return int(m.group(1)) if m else None


def lint_spec(spec):
    errs = []
    t = spec.get("type")
    if t not in ("swimlane", "flow", "state"):
        return ["type 必须是 swimlane / flow / state"]
    title = spec.get("title")
    if not title or not isinstance(title, str):
        errs.append("缺 title（每张图一个标题）")
    elif units(title) > S["title_max"]:
        errs.append(f"title 过长（{units(title):.0f} > {S['title_max']}）")
    sub = spec.get("subtitle", "")
    if sub and ("\n" in sub or units(sub) > S["subtitle_max"]):
        errs.append(f"subtitle 只许 1 行、≤{S['subtitle_max']} 字（写这张图回答什么）")
    notes = spec.get("notes", []) or []
    if len(notes) > S["note_lines"]:
        errs.append(f"notes ≤{S['note_lines']} 行（现 {len(notes)}）")
    for x in notes:
        if "\n" in x or units(x) > S["note_len"]:
            errs.append(f"note 每行 ≤{S['note_len']} 字且不换行：{x[:20]}…")
    for k in ("fill", "color", "fillColor", "borderColor", "x", "y", "width", "height"):
        if re.search(r'"%s"\s*:' % k, json.dumps(spec, ensure_ascii=False)):
            errs.append(f"spec 里出现样式 / 坐标字段「{k}」：样式由脚本写死，spec 只写内容")
    edge_key = "transitions" if t == "state" else "edges"
    edges = spec.get(edge_key, []) or []

    def chk_label(e, where):
        lab = e.get("label", "")
        if lab and ("\n" in lab or units(lab) > S["label_max"]):
            errs.append(f"{where} 标签 ≤{S['label_max']} 字且不换行：{lab}")
        if e.get("style", "solid") not in ("solid", "dashed"):
            errs.append(f"{where} style 只能 solid / dashed")

    if t == "swimlane":
        lanes = spec.get("lanes", []) or []
        steps = spec.get("steps", []) or []
        lane_ids = [l.get("id") for l in lanes]
        if not lanes:
            errs.append("lanes 为空")
        if len(lanes) > S["max_lanes"]:
            errs.append(f"泳道 {len(lanes)} 条 > {S['max_lanes']}：拆图")
        if len(set(lane_ids)) != len(lane_ids):
            errs.append("lane id 重复")
        for l in lanes:
            if units(l.get("name", "")) > S["lane_name_max"] or not l.get("name"):
                errs.append(f"泳道名必填且 ≤{S['lane_name_max']} 字：{l.get('name')}")
            if units(l.get("sub", "")) > S["lane_sub_max"]:
                errs.append(f"泳道系统名 ≤{S['lane_sub_max']} 字：{l.get('sub')}")
        if len(steps) > S["max_boxes"]:
            errs.append(f"全图 {len(steps)} 框 > {S['max_boxes']}：拆图")
        seen, cells = set(), set()
        for s_ in steps:
            n = s_.get("n")
            where = f"步骤 {n}"
            if n is None or _col_key(n) is None:
                errs.append(f"{where}：n 必须是数字或「5a」式编号")
                continue
            if str(n) in seen:
                errs.append(f"{where}：编号重复")
            seen.add(str(n))
            if s_.get("lane") not in lane_ids:
                errs.append(f"{where}：lane「{s_.get('lane')}」不在 lanes 里")
            cell = (s_.get("lane"), _col_key(n))
            if cell in cells:
                errs.append(f"{where}：同一泳道同一列已有步骤（5a / 5b 只能落在不同泳道）")
            cells.add(cell)
            if s_.get("kind", "normal") not in ("normal", "human", "visible"):
                errs.append(f"{where}：kind 只能 normal / human / visible")
            errs.extend(_box_text_errs(s_.get("text", ""), where))
        for lid in lane_ids:
            c = sum(1 for s_ in steps if s_.get("lane") == lid)
            if c > S["max_per_lane"]:
                errs.append(f"泳道 {lid} {c} 框 > {S['max_per_lane']}：拆图")
            if c == 0:
                errs.append(f"泳道 {lid} 没有步骤：泳道只画有动作的参与方")
        for e in edges:
            where = f"连线 {e.get('from')}→{e.get('to')}"
            if str(e.get("from")) not in seen or str(e.get("to")) not in seen:
                errs.append(f"{where}：端点不是已有步骤编号")
            if str(e.get("from")) == str(e.get("to")):
                errs.append(f"{where}：泳道图不画自环")
            chk_label(e, where)
    else:
        nodes = spec.get("states" if t == "state" else "nodes", []) or []
        ids = [n.get("id") for n in nodes]
        if not nodes:
            errs.append("nodes / states 为空")
        if len(set(ids)) != len(ids):
            errs.append("节点 id 重复")
        if len(nodes) > S["max_nodes"]:
            errs.append(f"节点 {len(nodes)} > {S['max_nodes']}：拆图")
        for n in nodes:
            where = f"节点 {n.get('id')}"
            if t == "flow":
                shape = n.get("shape", "box")
                if shape not in ("box", "decision", "start", "end"):
                    errs.append(f"{where}：shape 只能 box / decision / start / end")
                if n.get("kind", "normal") not in ("normal", "human", "visible"):
                    errs.append(f"{where}：kind 只能 normal / human / visible")
                lim = {"box": None, "decision": S["decision_line"], "start": S["terminal_line"],
                       "end": S["terminal_line"]}.get(shape)
                if lim is None:
                    errs.extend(_box_text_errs(n.get("text", ""), where, numbered=False))
                else:
                    errs.extend(_short_text_errs(n.get("text", ""), where, lim, 2 if shape == "decision" else 1))
            else:
                errs.extend(_short_text_errs(n.get("text", ""), where, S["state_line"], 1))
        if t == "state":
            if spec.get("initial") not in ids:
                errs.append("initial 必须是某个 state 的 id")
        for e in edges:
            where = f"连线 {e.get('from')}→{e.get('to')}"
            if e.get("from") not in ids or e.get("to") not in ids:
                errs.append(f"{where}：端点 id 不存在")
            if t == "state" and e.get("by", "system") not in ("system", "human"):
                errs.append(f"{where}：by 只能 system / human")
            chk_label(e, where)
    if len(edges) > S["max_edges"]:
        errs.append(f"连线 {len(edges)} > {S['max_edges']}：拆图")
    # 往返写成两条单向边即可；脚本从不产出双向箭头
    return errs


def _box_text_errs(text, where, numbered=True):
    if not text:
        return [f"{where}：text 必填"]
    errs = []
    flat = text.replace("\n", "")
    if units(flat) > S["box_total"]:
        errs.append(f"{where}：方框 ≤{S['box_total']} 字（现 {units(flat):.0f}）——缩短或拆步：{flat}")
        return errs
    lines = wrap_box(text, S["box_line1"] if numbered else S["box_line"], S["box_line"])
    if len(lines) > 2:
        errs.append(f"{where}：方框 ≤2 行")
    for i, ln in enumerate(lines):
        lim = S["box_line1"] if (i == 0 and numbered) else S["box_line"]
        if units(ln) > lim:
            errs.append(f"{where}：第 {i + 1} 行 {units(ln):.0f} 字 > {lim}（方框宽 160 放不下）：{ln}")
    return errs


def _short_text_errs(text, where, per_line, max_lines):
    if not text:
        return [f"{where}：text 必填"]
    lines = text.split("\n") if "\n" in text else wrap_box(text, per_line, per_line)
    errs = []
    if len(lines) > max_lines:
        errs.append(f"{where}：≤{max_lines} 行、每行 ≤{per_line} 字：{text}")
    for ln in lines:
        if units(ln) > per_line:
            errs.append(f"{where}：每行 ≤{per_line} 字：{ln}")
    return errs


# ---------------------------------------------------------------- DSL 积木

def _rich(runs):
    return [dict(r) for r in runs]


def _textnode(nid, x, y, w, h, runs, align="left", valign="middle"):
    return {"type": "text", "id": nid, "x": round(x), "y": round(y), "width": round(w), "height": round(h),
            "text": _rich(runs), "textAlign": align, "verticalAlign": valign}


def _run(content, fs, color, bold=False):
    r = {"content": content, "fontSize": fs, "color": color}
    if bold:
        r["bold"] = True
    return r


def _rect(nid, x, y, w, h, fill, border, bw=1, radius=8, text=None, shape="rect", dash=None):
    n = {"type": shape, "id": nid, "x": round(x), "y": round(y), "width": round(w), "height": round(h),
         "fillColor": fill, "borderColor": border, "borderWidth": bw}
    if shape == "rect":
        n["borderRadius"] = radius
    if dash:
        n["borderDash"] = dash
    if text is not None:
        n["text"] = _rich(text)
        n["textAlign"] = "center"
        n["verticalAlign"] = "middle"
    return n


def _conn(frm, to, style="solid", fa=None, ta=None, waypoints=None, arrow=True):
    c = {"from": frm, "to": to, "lineShape": "rightAngle", "lineColor": S["line"], "lineWidth": S["line_w"],
         "lineStyle": style, "startArrow": "none", "endArrow": "arrow" if arrow else "none"}
    if fa:
        c["fromAnchor"] = fa
    if ta:
        c["toAnchor"] = ta
    if waypoints:
        c["waypoints"] = [{"x": round(p[0]), "y": round(p[1])} for p in waypoints]
        c["lineShape"] = "polyline"
    return {"type": "connector", "connector": c}


def _kind_colors(kind):
    if kind in SEM:
        f, b, _ = SEM[kind]
        return S[f], S[b]
    return S["white"], S["edge"]


def _header(nodes, spec, width, used):
    """标题 + 副标题 + 图例；返回表头高度。图例与标题撞车时下移成独立一行。"""
    p = S["pad"]
    legend = _legend_items(spec["type"], used)
    leg_w = sum(i[2] for i in legend) + max(0, len(legend) - 1) * 20
    title_w = text_px(spec["title"], S["fs_title"]) + 8
    header_h = S["header_h"]
    if legend and title_w + leg_w + 32 > width - 2 * p:
        lx, ly = p, p + (56 if spec.get("subtitle") else 36)
        header_h += 28
    else:
        lx, ly = width - p - leg_w, p + 4
    nodes.append(_textnode("title", p, p, max(title_w, 200), 28,
                           [_run(spec["title"], S["fs_title"], S["ink"], True)]))
    if spec.get("subtitle"):
        nodes.append(_textnode("subtitle", p, p + 32, max(text_px(spec["subtitle"], S["fs_subtitle"]) + 8, 200), 20,
                               [_run(spec["subtitle"], S["fs_subtitle"], S["grey"])]))
    x = lx
    for key, label, w in legend:
        cy = ly + 10
        if key in ("solid", "dashed"):
            nodes.append(_conn({"x": x, "y": cy}, {"x": x + 24, "y": cy}, key))
            nodes[-1]["connector"]["lineShape"] = "straight"
        else:
            f, b = _kind_colors(key)
            nodes.append(_rect(f"legend_{key}", x, cy - 7, 22, 14, f, b, 1, 3))
        nodes.append(_textnode(f"legend_t_{key}", x + 30, ly, w - 30, 20,
                               [_run(label, S["fs_legend"], S["ink"])]))
        x += w + 20
    return header_h


def _legend_items(t, used):
    out = []
    for key in ("solid", "dashed", "human", "visible"):
        if key not in used:
            continue
        label = LEGEND_TEXT[t][key] if key in ("solid", "dashed") else SEM[key][2]
        if key in ("solid", "dashed"):
            label = ("实线：" if key == "solid" else "虚线：") + label
        out.append((key, label, 30 + text_px(label, S["fs_legend"]) + 6))
    return out


def _notes(nodes, spec, y, width):
    notes = spec.get("notes", []) or []
    for i, s_ in enumerate(notes):
        nodes.append(_textnode(f"note_{i}", S["pad"], y + i * 20, width - 2 * S["pad"], 20,
                               [_run(s_, S["fs_note"], S["grey"])]))
    return y + len(notes) * 20


def _canvas(nodes, width, height):
    """白底画布放最底层（数组最前），保证预览与画板里都是白底、四周留 40 内边距。"""
    nodes.insert(0, {"type": "rect", "id": "canvas", "x": 0, "y": 0, "width": round(width), "height": round(height),
                     "fillColor": S["white"], "borderColor": S["white"], "borderWidth": 0, "borderRadius": 0})


# ---------------------------------------------------------------- 泳道

# ---------------------------------------------------------------- 正交布线（泳道图）
# whiteboard-cli 的自动避障会把分支线绕出画布、穿过图例（盲审复现），所以泳道图的每条连线都由脚本在
# 「列间通道 × 泳道内上下留白走廊」的网格上枚举候选折线、打分择优：不穿框、不出画布、不与已布的线共线重叠，
# 交叉少、拐弯少、同一来源的出线尽量从不同边出。

def _segs(pts):
    return [(pts[k], pts[k + 1]) for k in range(len(pts) - 1)]


def _clean(pts):
    out = []
    for q in pts:
        q = (round(q[0], 1), round(q[1], 1))
        if out and abs(out[-1][0] - q[0]) < 0.5 and abs(out[-1][1] - q[1]) < 0.5:
            continue
        out.append(q)
    merged = []
    for q in out:  # 合并共线的相邻段；反向折返判为非法
        if len(merged) >= 2:
            a, b = merged[-2], merged[-1]
            same_x = abs(a[0] - b[0]) < 0.5 and abs(b[0] - q[0]) < 0.5
            same_y = abs(a[1] - b[1]) < 0.5 and abs(b[1] - q[1]) < 0.5
            if same_x or same_y:
                if (b[0] - a[0]) * (q[0] - b[0]) < 0 or (b[1] - a[1]) * (q[1] - b[1]) < 0:
                    return None
                merged[-1] = q
                continue
        merged.append(q)
    for a, b in _segs(merged):
        if abs(a[0] - b[0]) > 0.5 and abs(a[1] - b[1]) > 0.5:
            return None  # 只允许横竖段
    return merged if len(merged) >= 2 else None


def _seg_hits_rect(a, b, r, m=0.0):
    x0, y0, x1, y1 = r[0] - m, r[1] - m, r[2] + m, r[3] + m
    sx0, sx1 = sorted((a[0], b[0]))
    sy0, sy1 = sorted((a[1], b[1]))
    return sx1 > x0 and sx0 < x1 and sy1 > y0 and sy0 < y1


def _cross(s, t):
    (a, b), (c, d) = s, t
    sv, tv = abs(a[0] - b[0]) < 0.5, abs(c[0] - d[0]) < 0.5
    if sv == tv:
        return False
    if sv:
        a, b, c, d = c, d, a, b  # 令 s 为横段
    x0, x1 = sorted((a[0], b[0]))
    y0, y1 = sorted((c[1], d[1]))
    return x0 + 0.5 < c[0] < x1 - 0.5 and y0 + 0.5 < a[1] < y1 - 0.5


def _overlap(s, t, gap=5):
    (a, b), (c, d) = s, t
    if abs(a[0] - b[0]) < 0.5 and abs(c[0] - d[0]) < 0.5 and abs(a[0] - c[0]) < gap:
        lo, hi = max(min(a[1], b[1]), min(c[1], d[1])), min(max(a[1], b[1]), max(c[1], d[1]))
        return hi - lo > -12  # 共线且重叠或首尾相距 <12：看起来像一根线穿过去，判非法
    if abs(a[1] - b[1]) < 0.5 and abs(c[1] - d[1]) < 0.5 and abs(a[1] - c[1]) < gap:
        lo, hi = max(min(a[0], b[0]), min(c[0], d[0])), min(max(a[0], b[0]), max(c[0], d[0]))
        return hi - lo > -12
    return False


def _route_swimlane(boxes, order, edges, channels, corridors, bounds, rigid=()):
    """boxes: key -> (x0,y0,x1,y1)；返回 {edge_idx: (pts, exit_side, dx_or_dy, entry_side, d)}。"""
    placed, out = [], {}
    used_exit, used_entry = {}, {}
    bx0, by0, bx1, by1 = bounds

    def ends(key, side, d):
        x0, y0, x1, y1 = boxes[key]
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        if key in rigid and d:  # 菱形：偏移点落在斜边上
            kx = abs(d) / ((y1 - y0) / 2) * ((x1 - x0) / 2)
            ky = abs(d) / ((x1 - x0) / 2) * ((y1 - y0) / 2)
            return {"right": (x1 - kx, cy + d), "left": (x0 + kx, cy + d),
                    "top": (cx + d, y0 + ky), "bottom": (cx + d, y1 - ky)}[side]
        return {"right": (x1, cy + d), "left": (x0, cy + d), "top": (cx + d, y0), "bottom": (cx + d, y1)}[side]

    def core(key):  # 菱形的「实心」部分：只拿中间一半当自身障碍
        x0, y0, x1, y1 = boxes[key]
        if key not in rigid:
            return boxes[key]
        qx, qy = (x1 - x0) / 4, (y1 - y0) / 4
        return (x0 + qx, y0 + qy, x1 - qx, y1 - qy)

    for i in order:
        ka, kb = edges[i]
        A, B = boxes[ka], boxes[kb]
        cands = []
        exits = [(s, d) for s in ("right", "left") for d in (0, -12, 12)] + \
                [(s, d) for s in ("top", "bottom") for d in (0, 28, -28)]
        entries = [("left", d) for d in (0, -12, 12)] + [(s, d) for s in ("top", "bottom") for d in (0, 28, -28)]
        if ka in rigid:  # 菱形出线只从四个顶点出（分支一眼看清）
            exits = [x for x in exits if x[1] == 0]
        for es, ed in exits:
            P0 = ends(ka, es, ed)
            horiz = es in ("left", "right")
            if horiz:
                near = [c for c in channels if (c >= A[2] if es == "right" else c <= A[0])]
                xs1 = [c + o for c in sorted(near, key=lambda c: abs(c - P0[0]))[:2] for o in (0, -8, 8)]
            else:
                xs1 = [P0[0]]
            for ns, nd in entries:
                P9 = ends(kb, ns, nd)
                if ns == "left":
                    near = [c for c in channels if c <= B[0]]
                    xs2 = [c + o for c in sorted(near, key=lambda c: abs(c - B[0]))[:2] for o in (0, -8, 8)]
                for x1 in xs1:
                    first = [P0, (x1, P0[1])] if horiz else [P0]
                    if ns == "left":
                        cands.append((first + [(x1, P9[1]), P9], es, ed))  # 一折 / 两折直达
                        for yc in corridors:
                            for x2 in xs2:
                                cands.append((first + [(x1, yc), (x2, yc), (x2, P9[1]), P9], es, ed))
                    else:
                        ys = [yc for yc in corridors if (yc < B[1] if ns == "top" else yc > B[3])]
                        for yc in ys:
                            cands.append((first + [(x1, yc), (P9[0], yc), P9], es, ed))
        best = None
        for item in cands:
            pts, es, ed = item
            # 末点所在边
            P9 = pts[-1]
            ns = "left" if abs(P9[0] - B[0]) < 0.5 else ("top" if abs(P9[1] - B[1]) < 0.5 else "bottom")
            cl = _clean(pts)
            if not cl:
                continue
            ss = _segs(cl)
            bad = False
            for (p, q) in ss:
                if not (bx0 <= p[0] <= bx1 and bx0 <= q[0] <= bx1 and by0 <= p[1] <= by1 and by0 <= q[1] <= by1):
                    bad = True
                    break
                for k, r in boxes.items():
                    if k in (ka, kb):
                        r = core(k)
                    if _seg_hits_rect(p, q, r, 1 if k in (ka, kb) else 6) and not (
                            k in (ka, kb) and not _seg_hits_rect(p, q, r, -1)):
                        bad = True
                        break
                if bad:
                    break
                if any(_overlap((p, q), t) for t in placed):
                    bad = True
                    break
            if bad:
                continue
            # 第一段必须朝外、最后一段必须从外进入
            if _seg_hits_rect(*ss[0], core(ka), -1) or _seg_hits_rect(*ss[-1], core(kb), -1):
                continue
            length = sum(abs(p[0] - q[0]) + abs(p[1] - q[1]) for p, q in ss)
            crosses = sum(1 for s in ss for t in placed if _cross(s, t))
            score = length / 40 + (len(ss) - 1) * 4 + crosses * 30
            score += 40 * used_exit.get((ka, es), 0) + 25 * used_entry.get((ka, es), 0)
            score += 8 * used_entry.get((kb, ns), 0) + 25 * used_exit.get((kb, ns), 0)
            score += (abs(ed) > 0) * 2 + (abs(P9[1] - (B[1] + B[3]) / 2) > 0.5 and ns == "left") * 2
            if es != "right" and B[0] > A[2]:
                score += 6  # 正向边默认右出（横向推进），右边被占才上 / 下出
            if best is None or score < best[0]:
                best = (score, cl, es, ns)
        if best is None:
            continue
        _, cl, es, ns = best
        placed.extend(_segs(cl))
        used_exit[(ka, es)] = used_exit.get((ka, es), 0) + 1
        used_entry[(kb, ns)] = used_entry.get((kb, ns), 0) + 1
        out[i] = (cl, es, ns)
    return out, placed


def _place_label(lab, pts, boxes, placed_segs, labels, bounds, band_edges, chip=False):
    """标签贴在本线某段的中点旁；不压框 / 其它标签 / 线，出不去就加白底压在线上。"""
    w, h = (text_px(lab, S["fs_label"]) + 16, 22) if chip else (text_px(lab, S["fs_label"]) + 8, 18)
    segs = _segs(pts)
    order = sorted(range(len(segs)), key=lambda k: -(abs(segs[k][0][0] - segs[k][1][0]) +
                                                     abs(segs[k][0][1] - segs[k][1][1])))
    best = None
    for rank_, k in enumerate(order):
        (a, b) = segs[k]
        L = abs(a[0] - b[0]) + abs(a[1] - b[1])
        spots = []
        for t_, pen in ((0.5, 0), (0.3, 2), (0.7, 2)):
            mx, my = a[0] + (b[0] - a[0]) * t_, a[1] + (b[1] - a[1]) * t_
            if abs(a[1] - b[1]) < 0.5:  # 横段：上 / 下
                spots += [(mx - w / 2, my - h - 3, pen), (mx - w / 2, my + 3, pen + 1),
                          # 两框之间的短横段：标签抬到框顶以上（框高 56，半高 28）
                          (mx - w / 2, my - S["step_h"] / 2 - h - 4, pen + 3)]
            else:  # 竖段：右 / 左
                spots += [(mx + 5, my - h / 2, pen), (mx - 5 - w, my - h / 2, pen + 1)]
        for sx, sy, pen in spots:
            r = (sx, sy, sx + w, sy + h)
            if r[0] < bounds[0] or r[2] > bounds[2] or r[1] < bounds[1] or r[3] > bounds[3]:
                continue
            if any(_seg_hits_rect((r[0], r[1]), (r[2], r[3]), bx, 2) for bx in boxes.values()):
                continue
            if any(_seg_hits_rect((r[0], r[1]), (r[2], r[3]), lb, 2) for lb in labels):
                continue
            hits = sum(1 for s in placed_segs if _seg_hits_rect(s[0], s[1], r, 1))
            edge_cross = sum(1 for y in band_edges if r[1] < y < r[3])
            score = hits * 50 + edge_cross * 15 + rank_ * 3 + pen + (0 if L >= w * 0.6 else 8)
            if best is None or score < best[0]:
                best = (score, r, hits)
    if best is None:  # 兜底：白底压在最长段中点
        a, b = segs[order[0]]
        mx, my = (a[0] + b[0]) / 2, (a[1] + b[1]) / 2
        return (mx - w / 2, my - h / 2, mx + w / 2, my + h / 2), True
    return best[1], best[2] > 0


def _is_center(pt, r, side):
    cx, cy = (r[0] + r[2]) / 2, (r[1] + r[3]) / 2
    return {"right": abs(pt[1] - cy) < 0.6, "left": abs(pt[1] - cy) < 0.6,
            "top": abs(pt[0] - cx) < 0.6, "bottom": abs(pt[0] - cx) < 0.6}[side]


def dsl_swimlane(spec):
    p = S["pad"]
    lanes = spec["lanes"]
    steps = sorted(spec["steps"], key=lambda s_: (_col_key(s_["n"]), str(s_["n"])))
    cols = sorted({_col_key(s_["n"]) for s_ in steps})
    col_index = {c: i for i, c in enumerate(cols)}
    lane_index = {l["id"]: i for i, l in enumerate(lanes)}
    band_w = S["lane_name_w"] + len(cols) * S["col_w"]
    width = band_w + 2 * p
    used = {e.get("style", "solid") for e in spec.get("edges", [])}
    used |= {s_.get("kind") for s_ in steps if s_.get("kind") in SEM}
    nodes, edges_out = [], []
    header_h = _header(nodes, spec, width, used)
    top = p + header_h
    pos = {}
    for i, l in enumerate(lanes):
        ly = top + i * (S["lane_h"] + S["lane_gap"])
        nodes.append(_rect(f"lane_{l['id']}", p, ly, band_w, S["lane_h"], S["band_fill"], S["band_border"], 1,
                           S["lane_radius"]))
        nodes.append(_rect(f"strip_{l['id']}", p, ly, S["strip_w"], S["lane_h"], S["blue"], S["blue"], 0, 2))
        runs = [_run(l["name"], S["fs_lane"], S["ink"], True)]
        if l.get("sub"):
            runs[0]["content"] += "\n"
            runs.append(_run(l["sub"], S["fs_lane_sub"], S["grey"]))
        nodes.append(_textnode(f"lane_t_{l['id']}", p + 16, ly, S["lane_name_w"] - 16, S["lane_h"], runs))
    body_x = p + S["lane_name_w"]
    off = (S["col_w"] - S["step_w"]) / 2
    for s_ in steps:
        ci, li = col_index[_col_key(s_["n"])], lane_index[s_["lane"]]
        x = body_x + ci * S["col_w"] + off
        y = top + li * (S["lane_h"] + S["lane_gap"]) + (S["lane_h"] - S["step_h"]) / 2
        lines = wrap_box(s_["text"])
        runs = [_run(f"{s_['n']}  ", S["fs_num"], S["blue"], True), _run("\n".join(lines), S["fs_box"], S["ink"])]
        fill, border = _kind_colors(s_.get("kind"))
        sid = f"s{s_['n']}"
        nodes.append(_rect(sid, x, y, S["step_w"], S["step_h"], fill, border, 1, S["step_radius"], runs))
        pos[str(s_["n"])] = (x, y, ci, li)
    lanes_bottom = top + len(lanes) * S["lane_h"] + (len(lanes) - 1) * S["lane_gap"]
    boxes = {str(k): (v[0], v[1], v[0] + S["step_w"], v[1] + S["step_h"]) for k, v in pos.items()}
    for i, l in enumerate(lanes):  # 泳道名文字也是障碍
        ly = top + i * (S["lane_h"] + S["lane_gap"])
        boxes[f"_lane{i}"] = (p + 16, ly + 36, p + 16 + max(text_px(l["name"], S["fs_lane"]),
                                                             text_px(l.get("sub", ""), S["fs_lane_sub"])), ly + 76)
    channels = [body_x + c * S["col_w"] for c in range(len(cols) + 1)]
    corridors = []
    band_edges = []
    for i in range(len(lanes)):
        ly = top + i * (S["lane_h"] + S["lane_gap"])
        corridors += [ly + 10, ly + 18, ly + S["lane_h"] - 18, ly + S["lane_h"] - 10]
        band_edges += [ly, ly + S["lane_h"]]
    edges = spec.get("edges", [])
    pairs = [(str(e["from"]), str(e["to"])) for e in edges]

    def prio(i):
        a, b = pos[pairs[i][0]], pos[pairs[i][1]]
        fwd = b[2] > a[2]
        return (0 if (fwd and a[3] == b[3] and b[2] == a[2] + 1) else (1 if fwd else 2), abs(b[3] - a[3]),
                b[2] - a[2], i)

    order = sorted(range(len(edges)), key=prio)
    bounds = (body_x - 12, top + 2, p + band_w - 2, lanes_bottom - 2)
    routes, all_segs = _route_swimlane(boxes, order, pairs, channels, corridors, bounds)
    labels = []
    for i, e in enumerate(edges):
        if i not in routes:
            continue
        pts, es, ns = routes[i]
        style = e.get("style", "solid")
        fid, tid = f"s{e['from']}", f"s{e['to']}"
        A, B = boxes[pairs[i][0]], boxes[pairs[i][1]]
        src = (fid, es) if _is_center(pts[0], A, es) else None
        dst = (tid, ns) if _is_center(pts[-1], B, ns) else None
        if len(pts) == 2 and src and dst:
            c = _conn(fid, tid, style, es, ns)
            c["connector"]["lineShape"] = "straight"
            edges_out.append(c)
        else:
            edges_out.extend(_seg_chain(pts, style, src, dst))
        lab = e.get("label", "")
        if lab:
            r, onto_line = _place_label(lab, pts, boxes, all_segs, labels, (body_x, top, p + band_w, lanes_bottom),
                                        band_edges)
            labels.append(r)
            if onto_line:  # 实在避不开线：白底压线
                nodes.append(_rect(_lid("labbox"), r[0], r[1], r[2] - r[0], r[3] - r[1], S["white"], S["white"], 0, 3))
            nodes.append(_textnode(_lid("lab"), r[0], r[1], r[2] - r[0], r[3] - r[1],
                                   [_run(lab, S["fs_label"], S["grey"])], "center"))
    bottom = _notes(nodes, spec, lanes_bottom + 16, width) if spec.get("notes") else lanes_bottom
    _canvas(nodes, width, bottom + p)
    lab_nodes = [n for n in nodes if str(n.get("id", "")).startswith(("lab_", "labbox_"))]
    rest = [n for n in nodes if n not in lab_nodes]
    return {"version": 2, "nodes": rest + edges_out + lab_nodes}


_LID = [0]


def _lid(prefix):
    _LID[0] += 1
    return f"{prefix}_{_LID[0]}"



# ---------------------------------------------------------------- 流程 / 状态（脚本自排：分层 + 行对齐）

def _layered(node_ids, edges, first):
    """返回 rank[id], row[id], back_edges(set of idx)。首条出边沿用同一行，其余出边往下一行。"""
    out = {n: [] for n in node_ids}
    for i, (a, b) in enumerate(edges):
        out[a].append((i, b))
    indeg = {n: 0 for n in node_ids}
    for a, b in edges:
        indeg[b] += 1
    roots = [first] if first else []
    roots += [n for n in node_ids if indeg[n] == 0 and n not in roots]
    roots += [n for n in node_ids if n not in roots]
    color, back = {}, set()

    def dfs(u):
        color[u] = 1
        for i, v in out[u]:
            if color.get(v) == 1:
                back.add(i)
            elif v not in color:
                dfs(v)
        color[u] = 2

    for r in roots:
        if r not in color:
            dfs(r)
    rank = {n: 0 for n in node_ids}
    order = []
    seen = set()

    def topo(u):
        seen.add(u)
        for i, v in out[u]:
            if i not in back and v not in seen and a_not_self(i):
                topo(v)
        order.append(u)

    def a_not_self(i):
        return edges[i][0] != edges[i][1]

    for r in roots:
        if r not in seen:
            topo(r)
    for u in reversed(order):
        for i, v in out[u]:
            if i not in back and edges[i][0] != edges[i][1]:
                rank[v] = max(rank[v], rank[u] + 1)
    row, taken = {}, set()

    def place(n, pref):
        r = max(pref, 0)
        while (rank[n], r) in taken:
            r += 1
        row[n] = r
        taken.add((rank[n], r))

    queue = []
    for r in roots:
        if r not in row and indeg[r] == 0 or r == first:
            if r not in row:
                place(r, 0 if not row else max(row.values()) + 1)
                queue.append(r)
    while queue or len(row) < len(node_ids):
        if not queue:
            n = next(x for x in node_ids if x not in row)
            place(n, 0)
            queue.append(n)
        u = queue.pop(0)
        k = 0
        for i, v in out[u]:
            if i in back or v in row:
                continue
            place(v, row[u] + k)
            k += 1
            queue.append(v)
    return rank, row, back


def _size(t, n):
    if t == "state":
        return S["state_w"], S["state_h"]
    shape = n.get("shape", "box")
    if shape == "decision":
        return S["decision_w"], S["decision_h"]
    if shape in ("start", "end"):
        return S["terminal_w"], S["terminal_h"]
    return S["step_w"], S["step_h"]


def _seg_chain(pts, style, src=None, dst=None):
    """正交折线拆成首尾相接的直线段（straight 不参与自动避障，走向完全由脚本决定）。
    whiteboard-cli 会把 waypoints 夹在两端点包围盒内，绕行无法用 waypoints 表达，所以统一拆段。
    src / dst = (节点 id, 锚点)：首段 / 末段挂在节点上（拖动节点时连线跟随），否则用坐标。"""
    out = []
    n = len(pts) - 1
    for k in range(n):
        a = {"x": round(pts[k][0]), "y": round(pts[k][1])}
        b = {"x": round(pts[k + 1][0]), "y": round(pts[k + 1][1])}
        fa = ta = None
        if k == 0 and src:
            a, fa = src
        if k == n - 1 and dst:
            b, ta = dst
        c = _conn(a, b, style, fa, ta, arrow=(k == n - 1))
        c["connector"]["lineShape"] = "straight"
        out.append(c)
    return out


def dsl_graph(spec):
    t = spec["type"]
    p = S["pad"]
    nodes_spec = spec["states"] if t == "state" else spec["nodes"]
    edges_spec = spec["transitions"] if t == "state" else spec["edges"]
    ids = [n["id"] for n in nodes_spec]
    first = spec.get("initial") if t == "state" else next(
        (n["id"] for n in nodes_spec if n.get("shape") == "start"), ids[0])
    pairs = [(e["from"], e["to"]) for e in edges_spec]
    rank, row, back = _layered(ids, pairs, first)
    nrank = max(rank.values()) + 1
    nrow = max(row.values()) + 1
    # 标签尺寸决定列间距：带标签的横向边要能完整放下标签（框）+ 两端箭头
    lab_w = [text_px(e.get("label", ""), S["fs_label"]) + 16 for e in edges_spec if e.get("label")]
    col_gap = max(S["min_col_gap"], (max(lab_w) + 48) if lab_w else 0)
    col_w = [0] * nrank
    for n in nodes_spec:
        col_w[rank[n["id"]]] = max(col_w[rank[n["id"]]], _size(t, n)[0])
    row_h = max(_size(t, n)[1] for n in nodes_spec)
    used = {e.get("style", "solid") for e in edges_spec}
    if t == "state":
        used |= {"human" for e in edges_spec if e.get("by") == "human"}
    else:
        used |= {n.get("kind") for n in nodes_spec if n.get("kind") in SEM}
    left = p + (64 if t == "state" else 40)  # 左侧留起点圆点 / 回边入口通道
    xs, x = [], left
    for w in col_w:
        xs.append(x)
        x += w + col_gap
    width = max(x - col_gap + p + 40, 640)
    nodes, conns = [], []
    header_h = _header(nodes, spec, width, used)
    margin = 48  # 图上下各留一条走廊（回边 / 自环）
    top = p + header_h + margin
    geo = {}
    for n in nodes_spec:
        w, h = _size(t, n)
        cx = xs[rank[n["id"]]] + col_w[rank[n["id"]]] / 2
        cy = top + row[n["id"]] * (row_h + S["row_gap"]) + row_h / 2
        x0, y0 = cx - w / 2, cy - h / 2
        geo[n["id"]] = (x0, y0, w, h)
        nid = f"n_{n['id']}"
        if t == "state":
            txt = [_run(n["text"], S["fs_state"], S["ink"], True)]
            if n.get("final"):
                nodes.append(_rect(nid, x0, y0, w, h, S["white"], S["ink"], S["state_border"], 10))
                nodes.append(_rect(f"{nid}_in", x0 + 4, y0 + 4, w - 8, h - 8, S["white"], S["ink"], 1, 6, txt))
            else:
                nodes.append(_rect(nid, x0, y0, w, h, S["white"], S["ink"], S["state_border"], 8, txt))
        else:
            shape = n.get("shape", "box")
            if shape == "decision":
                nodes.append(_rect(nid, x0, y0, w, h, S["white"], S["edge"], 1, 0,
                                   [_run(n["text"], S["fs_box"], S["ink"])], shape="diamond"))
            elif shape in ("start", "end"):
                nodes.append(_rect(nid, x0, y0, w, h, S["white"], S["ink"], S["state_border"], h / 2,
                                   [_run(n["text"], S["fs_box"], S["ink"], True)]))
            else:
                fill, border = _kind_colors(n.get("kind"))
                nodes.append(_rect(nid, x0, y0, w, h, fill, border, 1, S["step_radius"],
                                   [_run("\n".join(wrap_box(n["text"], S["box_line"], S["box_line"])),
                                         S["fs_box"], S["ink"])]))
    rows_top = top
    rows_bottom = top + nrow * row_h + (nrow - 1) * S["row_gap"]
    if t == "state":
        ix, iy, iw, ih = geo[spec["initial"]]
        d = S["dot"]
        nodes.append({"type": "ellipse", "id": "n__start", "x": round(ix - 44), "y": round(iy + ih / 2 - d / 2),
                      "width": d, "height": d, "fillColor": S["blue"], "borderColor": S["blue"], "borderWidth": 0})
        conns.append(_conn("n__start", f"n_{spec['initial']}", "solid", "right", "left"))
    # ---- 布线：与泳道图同一套候选折线择优（不穿框、不共线、少交叉、同源出线分边）
    boxes = {k: (g[0], g[1], g[0] + g[2], g[1] + g[3]) for k, g in geo.items()}
    if t == "state":
        boxes["__dot"] = (ix - 44, iy + ih / 2 - 6, ix - 44 + S["dot"], iy + ih / 2 + 6)
    rigid = {n["id"] for n in nodes_spec if n.get("shape") in ("decision",)}  # 菱形只能从顶点出入
    channels = [xs[0] - col_gap / 2] + [xs[r] + col_w[r] + col_gap / 2 for r in range(nrank)]
    corridors = [rows_top - 24, rows_top - 34]
    for r in range(nrow - 1):
        yb = top + (r + 1) * row_h + r * S["row_gap"]
        corridors += [yb + S["row_gap"] / 2 - 8, yb + S["row_gap"] / 2, yb + S["row_gap"] / 2 + 8]
    corridors += [rows_bottom + 24, rows_bottom + 34]
    bounds = (p + 8, rows_top - margin + 6, width - p - 8, rows_bottom + margin - 6)
    selfloops = [i for i, (a, b) in enumerate(pairs) if a == b]
    normal = [i for i in range(len(pairs)) if i not in selfloops]

    def prio(i):
        a, b = pairs[i]
        fwd = i not in back
        return (0 if fwd and row[a] == row[b] and rank[b] == rank[a] + 1 else (1 if fwd else 2),
                abs(row[b] - row[a]), rank[b] - rank[a], i)

    order = sorted(normal, key=prio)
    routes, all_segs = _route_swimlane(boxes, order, pairs, channels, corridors, bounds, rigid)
    labels = []
    # 自环：右上角出、绕到框上方回到顶边（固定形状）
    for i in selfloops:
        x0, y0, w, h = geo[pairs[i][0]]
        pts = [(x0 + w, y0 + 14), (x0 + w + 20, y0 + 14), (x0 + w + 20, y0 - 22), (x0 + w - 36, y0 - 22),
               (x0 + w - 36, y0)]
        routes[i] = (pts, "right", "top")
        all_segs.extend(_segs(pts))
    for i, e in enumerate(edges_spec):
        if i not in routes:
            continue
        pts, es, ns = routes[i]
        a, b = pairs[i]
        style = e.get("style", "solid")
        fid, tid = f"n_{a}", f"n_{b}"
        src = (fid, es) if a != b and _is_center(pts[0], boxes[a], es) else None
        dst = (tid, ns) if a != b and _is_center(pts[-1], boxes[b], ns) else None
        if len(pts) == 2 and src and dst:
            c = _conn(fid, tid, style, es, ns)
            c["connector"]["lineShape"] = "straight"
            conns.append(c)
        else:
            conns.extend(_seg_chain(pts, style, src, dst))
        lab = e.get("label", "")
        if not lab:
            continue
        human = t == "state" and e.get("by") == "human"
        chip = t == "state"
        r, onto = _place_label(lab, pts, boxes, all_segs, labels, bounds, [], chip=chip)
        labels.append(r)
        if chip:
            fill, border = (S["human_fill"], S["human_border"]) if human else (S["white"], S["band_border"])
            nodes.append(_rect(_lid("labbox"), r[0], r[1], r[2] - r[0], r[3] - r[1], fill, border, 1, 4))
        elif onto:
            nodes.append(_rect(_lid("labbox"), r[0], r[1], r[2] - r[0], r[3] - r[1], S["white"], S["white"], 0, 3))
        nodes.append(_textnode(_lid("lab"), r[0], r[1], r[2] - r[0], r[3] - r[1],
                               [_run(lab, S["fs_label"], S["grey"])], "center"))
    bottom = rows_bottom + margin - 16
    bottom = _notes(nodes, spec, bottom + 8, width) if spec.get("notes") else bottom
    _canvas(nodes, width, bottom + p)
    # 标签画在连线之上（数组越靠后层级越高）
    lab_nodes = [n for n in nodes if str(n.get("id", "")).startswith(("lab_", "labbox_"))]
    rest = [n for n in nodes if n not in lab_nodes]
    return {"version": 2, "nodes": rest + conns + lab_nodes}


def build_dsl(spec):
    _LID[0] = 0
    if spec["type"] == "swimlane":
        return dsl_swimlane(spec)
    return dsl_graph(spec)


# ---------------------------------------------------------------- 子命令

def _need_lint(spec, path):
    errs = lint_spec(spec)
    if errs:
        for e in errs:
            print(f"LINT {path}: {e}")
        sys.exit(2)


def _npx():
    npx = shutil.which("npx")
    if not npx:
        print("本机没有 node/npm，无法渲染预览；可先 `publish` 再用 `verify` 看云端预览")
        sys.exit(1)
    return npx


def cmd_lint(a):
    spec = _load(a.spec)
    errs = lint_spec(spec)
    for e in errs:
        print(f"LINT {a.spec}: {e}")
    if errs:
        sys.exit(2)
    print(f"LINT_OK {a.spec}")


def cmd_dsl(a):
    spec = _load(a.spec)
    _need_lint(spec, a.spec)
    out = json.dumps(build_dsl(spec), ensure_ascii=False, indent=1)
    if a.o:
        with open(a.o, "w", encoding="utf-8") as f:
            f.write(out)
        print(f"DSL {a.o}")
    else:
        print(out)


def _write_tmp_dsl(spec):
    fd, path = tempfile.mkstemp(prefix="prd_diagram_", suffix=".json")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(build_dsl(spec), f, ensure_ascii=False)
    return path


def cmd_render(a):
    spec = _load(a.spec)
    _need_lint(spec, a.spec)
    npx = _npx()
    dsl = _write_tmp_dsl(spec)
    try:
        png = os.path.abspath(a.png)
        os.makedirs(os.path.dirname(png) or ".", exist_ok=True)
        r = subprocess.run([npx, "-y", WB_CLI, "-i", dsl, "-o", png], capture_output=True, text=True)
        if r.returncode != 0:
            print(_first_err(r.stderr or r.stdout))
            sys.exit(1)
        print(f"RENDERED {png}")
    finally:
        os.unlink(dsl)


def _first_err(s):
    for ln in (s or "").splitlines():
        if ln.strip() and not ln.startswith("npm warn"):
            return ln.strip()
    return "unknown error"


def cmd_publish(a):
    spec = _load(a.spec)
    _need_lint(spec, a.spec)
    npx = _npx()
    if not shutil.which("lark-cli"):
        print("本机没有 lark-cli，无法发布")
        sys.exit(1)
    dsl = _write_tmp_dsl(spec)
    try:
        conv = subprocess.run([npx, "-y", WB_CLI, "-i", dsl, "--to", "openapi", "--format", "json"],
                              capture_output=True, text=True)
        if conv.returncode != 0 or not conv.stdout.strip():
            print(_first_err(conv.stderr or conv.stdout))
            sys.exit(1)
        name = re.sub(r"[^A-Za-z0-9_-]", "", os.path.splitext(os.path.basename(a.spec))[0]) or "diagram"
        idem = f"{int(time.time())}-{name}"
        cmd = ["lark-cli", "whiteboard", "+update", "--whiteboard-token", a.whiteboard_token, "--source", "-",
               "--input_format", "raw", "--overwrite", "--idempotent-token", idem, "--as", a.as_]
        r = subprocess.run(cmd, input=conv.stdout, capture_output=True, text=True)
        ok = r.returncode == 0
        try:
            j = json.loads(r.stdout)
            ok = ok and (j.get("ok", True) is not False) and not j.get("error")
        except ValueError:
            pass
        if not ok:
            print(_first_err(r.stderr or r.stdout))
            sys.exit(1)
        print(f"PUBLISHED {a.whiteboard_token}")
    finally:
        os.unlink(dsl)


def cmd_verify(a):
    if not shutil.which("lark-cli"):
        print("本机没有 lark-cli，无法导出预览")
        sys.exit(1)
    out_dir = os.path.abspath(a.out)
    os.makedirs(out_dir, exist_ok=True)
    os.chdir(out_dir)  # --output 必须是相对当前目录、不带扩展名的路径
    name = a.name or f"wb_{a.whiteboard_token[:10]}"
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,40}", name):
        print("--name 只允许 [A-Za-z0-9_-]{1,40}（不带扩展名、不含路径）")
        sys.exit(2)
    r = subprocess.run(["lark-cli", "whiteboard", "+query", "--whiteboard-token", a.whiteboard_token,
                        "--output_as", "image", "--output", f"./{name}", "--overwrite", "--as", a.as_],
                       capture_output=True, text=True)
    hits = [f for f in os.listdir(out_dir) if f.startswith(name + ".")]
    if r.returncode != 0 or not hits:
        print(_first_err(r.stderr or r.stdout))
        sys.exit(1)
    print(f"VERIFY {os.path.join(out_dir, sorted(hits)[0])}")


def main(argv=None):
    ap = argparse.ArgumentParser(
        prog="prd_diagram.py",
        description="PRD 画板生成器：AI 只写 spec（内容），样式按 references/14-diagram-style.md 写死。",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="流程：lint → render 目检 → 文档放空画板块拿 token → publish → verify。spec 范例：references/examples/diagrams/")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("lint", help="校验 spec：schema + 密度上限 + 文本长度；违规退出码 2")
    p.add_argument("spec")
    p.set_defaults(fn=cmd_lint)
    p = sub.add_parser("dsl", help="生成 whiteboard-cli DSL JSON（默认打印到 stdout）")
    p.add_argument("spec")
    p.add_argument("-o", help="写到文件")
    p.set_defaults(fn=cmd_dsl)
    p = sub.add_parser("render", help=f"本地渲染 PNG 预览（npx -y {WB_CLI}）")
    p.add_argument("spec")
    p.add_argument("--png", required=True)
    p.set_defaults(fn=cmd_render)
    p = sub.add_parser("publish", help="覆盖写入指定画板（lark-cli whiteboard +update --input_format raw）")
    p.add_argument("spec")
    p.add_argument("--whiteboard-token", required=True)
    p.add_argument("--as", dest="as_", default="user", choices=["user", "bot"])
    p.set_defaults(fn=cmd_publish)
    p = sub.add_parser("verify", help="导出云端画板预览图（lark-cli whiteboard +query --output_as image）")
    p.add_argument("--whiteboard-token", required=True)
    p.add_argument("--out", required=True, help="落盘目录")
    p.add_argument("--name", help="文件名，只允许 [A-Za-z0-9_-]{1,40}（不带扩展名），默认 wb_<token 前 10 位>")
    p.add_argument("--as", dest="as_", default="user", choices=["user", "bot"])
    p.set_defaults(fn=cmd_verify)
    a = ap.parse_args(argv)
    a.fn(a)


if __name__ == "__main__":
    main()
