# Creating docs from scratch & embedding rendered diagrams

For building a new doc (or rebuilding one you fully own) in native blocks, and
for the HTML→PNG diagram trick used to fake a Lark whiteboard when the whiteboard
write API isn't available.

## High-fidelity create: chunked, XML, stdin

A one-shot `--content` with the whole document tends to hit size/parameter
limits and is hard to debug. Build the doc as a chain instead:

1. **Create the first chunk** (title + opening section) — this makes the doc and
   sets the title (taken from `<title>` in the content):
   ```bash
   LARK_CLI_NO_PROXY=1 lark-cli docs +create --api-version v2 \
     --content - < /tmp/c1.xml | jq -r '.data.document.url, .data.document.document_id'
   ```
2. **Append the rest**, one chunk per `block_insert_after --block-id -1` (a.k.a.
   `append`), chained with `&&` so order can't scramble:
   ```bash
   for i in 2 3 4 5 6 7; do
     LARK_CLI_NO_PROXY=1 lark-cli docs +update --api-version v2 --doc <id> \
       --command append --content - < /tmp/c$i.xml \
       | jq -c '{c:'"$i"', r:.data.result}' || break
   done
   ```

Each chunk is one `/tmp/cN.xml` file (stdin avoids all quoting issues). Chunks of
~3–4 KB each are comfortable; a ~25 KB doc in ~8 chunks goes through clean.

### Native blocks that make it look hand-made

Use the DocxXML element for the job — this is the difference between "looks like
a markdown dump" and "looks like a PRD someone wrote":

- `<table>` with `<colgroup><col width>`, `<th background-color="light-gray">`,
  and **cells that contain sub-blocks** — `<td><p><b>展示规则</b></p><ul><li>…
  </li></ul><p><b>交互</b></p><ul>…</ul></td>` gives the multi-line, bolded,
  bulleted cell look real PRDs use.
- `<checkbox done="false">Yes</checkbox>` — real check boxes (e.g. Quality Gates),
  not "[ ]" text.
- `<callout emoji="💡" background-color="light-yellow">…</callout>` — front-load
  conclusions / warnings.
- `<ol><li seq="auto">…</li></ol>` for true numbered lists (see
  numbering-lists-escaping.md).
- Section headings: number in the text (`<h5>1. …</h5>`), not via `seq`.

Escaping rules and the stdin pattern are the same as for patching.

## Markdown whole-file import (only when handed a .md)

If the user gives you a finished `.md` to import as-is:

```bash
LARK_CLI_NO_PROXY=1 lark-cli docs +create --api-version v2 \
  --doc-format markdown --content - < /tmp/doc.md
```

This preserves table cell `<br>` line breaks, bold, and `• / ◦` prefixes well.
Caveat: a markdown ordered list whose items are separated by a table gets its
numbering reset to 1 per fragment — if fixed numbering matters, put numbers in
the heading text rather than relying on `1.` list syntax.

## HTML → PNG diagrams (stand-in for a whiteboard)

When you need a flow/scenario diagram and the whiteboard write API isn't
available, render an HTML mockup to PNG and embed it as an image.

- **No Playwright / PIL needed**, and the Mac PingFang font path that's often
  quoted (`/System/Library/Fonts/PingFang.ttc`) may not exist — use headless
  Chrome with a CSS `font-family:"PingFang SC"` and it renders Chinese perfectly:

  ```bash
  "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
    --headless=new --disable-gpu --hide-scrollbars \
    --force-device-scale-factor=2 --window-size=1456,800 \
    --screenshot=/tmp/diagram.png "file:///tmp/diagram.html"
  ```

  `--force-device-scale-factor=2` gives a crisp 2× PNG. The command may be judged
  long-running and pushed to the background — read its output file to confirm the
  PNG was written.

- **Look at the PNG before uploading** (open/inspect it). Then insert + position
  per tables-images-mentions.md. To replace an existing diagram, swap by
  `media-insert` → `block_move_after` under the heading → `block_delete` the old
  image.

- Keep the source `.html` and the `.png` around and tell the user where they are,
  so a label tweak is a re-render rather than a rebuild.
