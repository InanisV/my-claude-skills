#!/usr/bin/env python3
"""
交付前检查 proposal-deck 的 HTML：正文页不能有小字和 kicker，文本层不能有禁词，秒数要在场合时长内。

用法：
  python check_deck.py deck.html                      # 默认禁词表
  python check_deck.py deck.html --ban 战队 验真       # 追加本项目禁词
  python check_deck.py deck.html --minutes 10         # 场合时长，默认 10 分钟，秒数超过 90% 报警

检查项：
  1. 禁词：本 skill 第 7 节的通用禁词，加 --ban 追加的项目禁词（别的团队的词、项目名、内部行话）
  2. 正文页（非 cover、非 appendix 的 section）里的 .src、.kicker、.values li 里的 <span> 说明
  3. 每页 data-seconds 加总，和场合时长的 90% 比
  4. 中文分号、破折号
文本层 = 去掉 base64 图片后的 HTML；检查不替代人眼看接触表。
"""
import re, sys

DEFAULT_BAN = ["赋能", "综上", "旨在", "值得注意", "综上所述", "确保", "拍板", "——", "；",
               "老板", "差异化", "一句话：", "Social Trading", "People First"]


def strip_images(html: str) -> str:
    return "".join(re.split(r"data:image/[a-z]+;base64,[A-Za-z0-9+/=]+", html))


def main(path: str, extra_ban, minutes: float):
    html = open(path, encoding="utf-8").read()
    txt = strip_images(html)
    # 只看 <body> 里的 section，不看 <style> 和 <script>
    body = txt.split("<body")[1] if "<body" in txt else txt
    body = re.sub(r"<script.*?</script>", "", body, flags=re.S)
    problems = 0

    bans = DEFAULT_BAN + list(extra_ban)
    visible = re.sub(r"<[^>]+>", " ", body)
    for w in bans:
        c = visible.count(w)
        if c:
            print(f"禁词  {w!r} × {c}")
            problems += c

    secs = re.split(r"(?=<section class=\"slide)", body)[1:]
    total = 0
    for sec in secs:
        m = re.search(r'data-title="([^"]*)"', sec)
        title = m.group(1) if m else "?"
        cls = re.search(r'<section class="([^"]*)"', sec).group(1)
        sm = re.search(r'data-seconds="(\d+)"', sec)
        total += int(sm.group(1)) if sm else 0
        is_body = ("cover" not in cls) and ("appendix" not in cls)
        if is_body:
            if 'class="src"' in sec:
                print(f"正文小字  {title}：有 .src 来源行，移到附录"); problems += 1
            if 'class="kicker"' in sec:
                print(f"正文小字  {title}：有 .kicker，正文页用步骤带 .band"); problems += 1
            if re.search(r'<li>.*?<span class="n[^"]*">.*?</span>.*?<span>[^<]+</span>', sec, flags=re.S):
                print(f"正文小字  {title}：.values 里还有说明 span，老板不看，删掉或改成 .vt 的 22 像素白字"); problems += 1
            if 'class="band"' not in sec:
                print(f"主线  {title}：没有步骤带 .band（三步 deck 的正文页都要有；不是三步 deck 可忽略）")
    limit = minutes * 60 * 0.9
    flag = "超时" if total > limit else "ok"
    print(f"秒数  正文加附录共 {total} 秒，场合 {minutes} 分钟的 90% 是 {int(limit)} 秒：{flag}")
    if total > limit:
        problems += 1
    print(f"共 {len(secs)} 页，问题 {problems} 处")
    return problems


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__); sys.exit(1)
    args = sys.argv[2:]
    extra = []
    minutes = 10.0
    if "--ban" in args:
        i = args.index("--ban")
        j = i + 1
        while j < len(args) and not args[j].startswith("--"):
            extra.append(args[j]); j += 1
    if "--minutes" in args:
        minutes = float(args[args.index("--minutes") + 1])
    sys.exit(1 if main(sys.argv[1], extra, minutes) else 0)
