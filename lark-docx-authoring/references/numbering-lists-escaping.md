# Numbering, ordered lists, and escaping

Small rules with outsized impact on whether a doc looks right.

## Heading numbers: put them in the TEXT, not in `seq`

Lark renders a visible auto-number for **ordered list items**, not for
**headings**. `<h5 seq="1" seq-level="auto">Foo</h5>` is accepted and round-trips
(you'll read the `seq` back), but **no "1." shows in the document**. A doc that
mixes one `seq` heading with text-numbered siblings looks broken — one heading
silently loses its number.

So for section/module headings that need to read "1. … / 2. … / 3. …", bake the
number into the text:

```xml
<h5>1. Smart Picks 一级tab入口</h5>
<h5>2. Live 瀑布流容器</h5>
<h5>3. AI 策略动态卡片</h5>
```

Text numbers are also **immune to the reset bug** below: nothing a renderer does
can turn a literal "2." into "1.". The cost is they don't auto-renumber when you
insert a module — but for PRD-style fixed numbering that's usually what you want,
and it's predictable. If you ever do want true native auto-numbering on headings,
test it in the actual doc first and confirm the number renders before relying on
it — don't assume.

## Ordered lists DO render — and how to avoid "1, 1, 1"

A real ordered list `<ol><li>…</li></ol>` renders native numbers. The reliable
way to get 1, 2, 3 is to give **every** item `seq="auto"`:

```xml
<ol><li seq="auto">first</li><li seq="auto">second</li></ol>
```

On fetch this reads back as the first item `seq="1"` and the rest with no `seq`
(implicit continuation) — that's correct and renders 1, 2, 3.

**The trap:** `block_replace` on a *single* `<li>` writes it back as `seq="1"`.
If you edit two items in a list separately, you can end up with two `seq="1"`
items → the list renders "1, 1". Fix it in one shot using 1→many:

```bash
# replace the FIRST item with the entire corrected list, then delete the strays
block_replace --block-id <first-li> \
  --content '<li seq="auto">item one</li><li seq="auto">item two</li>'
block_delete --block-id <old-second-li>
```

First item becomes `seq="1"`, second continues to 2. Verify it's **one `<ol>`**
with the right count, not two lists each restarting at 1.

## Escaping and verifying

In text content, escape `&` → `&amp;`, `<` → `&lt;`, `>` → `&gt;`. **Tags
themselves are never escaped** — only the text between them. Example:

```xml
<p>A &amp; B：1 &lt; 2，优先级 高 &gt; 低</p>
```

Fetched content comes back **still escaped**. So when you grep your dump to verify
a change, search for the escaped form:

```bash
grep -o '优先级 高 &gt; 低' /tmp/dump.xml     # NOT '高 > 低' — that won't match
```

This bites most often with comparison/priority text (`A > B > C`) inside table
cells.

## Full-width vs half-width punctuation

Chinese PRDs use full-width quotes `""`, parens `（）`, colon `：`. Preserve
exactly what the source/house style uses — these are often UI strings or term
entries where the exact glyph matters. When in doubt, match the surrounding
cells rather than normalizing to ASCII.
