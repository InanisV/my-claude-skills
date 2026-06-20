# Block operations: ids, scopes, the 8 commands, sequencing

All editing goes through `lark-cli docs +update --api-version v2 --doc <id>
--command <cmd> …`. This file is the mechanics you need to wield them safely.

## Reading: dump cheaply, not the whole doc every time

Full dump with ids (the canonical map):

```bash
lark-cli docs +fetch --api-version v2 --doc <id> --detail with-ids \
  | jq -r '.data.document.content' | sed 's/></>\n</g' > /tmp/dump.xml
```

`--detail` levels: `simple` (read/summarize), `with-ids` (you need ids to edit),
`full` (ids + style attrs). For editing, use `with-ids`.

For a big doc, read just the part you'll touch with `--scope`:
- `--scope outline --max-depth 3` — table of contents (heading ids).
- `--scope section --start-block-id <heading-id>` — one section, auto-expanded to
  the next same/higher heading. **Note:** if you just renamed that heading with
  `block_replace`, its id changed — re-fetch the outline to get the new id, or a
  section fetch on the dead id returns empty.
- `--scope range --start-block-id A --end-block-id B` — explicit span (`-1` = to
  end).
- `--scope keyword --keyword "foo|bar"` — locate by text (tables come back
  "thinned": header + matching rows only, wrapped in `<excerpt>` — that's a
  slice, not the whole block).

## The id lifecycle (the rule that trips everyone)

- Every block carries an `id` (e.g. `<p id="doxus…">`). Containers `<ul>`,
  `<ol>`, `<tr>`, `<td>`, `<thead>`, `<tbody>`, `<colgroup>` do **not** have ids.
  So you address list items by their `<li>` id, paragraphs by `<p>` id, and you
  **cannot** address a row or a cell directly.
- **`block_replace` assigns a NEW id** to the replaced block (the old id is gone)
  and can **expand one block into several** (replace one `<p>` with
  `<p>A</p><p>B</p>` → two paragraphs). Verified, and very useful.
- Therefore: **insert before you replace.** If you must both
  `block_insert_after X` and `block_replace X`, run the insert first — after the
  replace, `X` no longer exists as an anchor.
- After replacing a heading, fetch a fresh outline before using that heading as a
  scope anchor.

## The 8 commands

| Command | Use | Key args |
|---|---|---|
| `str_replace` | inline text find/replace; replacement may be rich text; empty `--content` deletes the match | `--pattern --content` (XML mode = inline only) |
| `block_insert_after` | insert new content after a block; content may be **multiple blocks**; `--block-id -1` = end (same as `append`) | `--block-id --content` |
| `block_replace` | replace a block (1→many ok; new id) | `--block-id --content` |
| `block_delete` | delete block(s); comma-separated batch | `--block-id` |
| `block_move_after` | move existing block(s) after an anchor — **preserves identity (token/href/mention)** | `--block-id <anchor> --src-block-ids a,b` |
| `block_copy_insert_after` | copy block(s) after an anchor | `--block-id --src-block-ids` |
| `append` | add to doc end | `--content` |
| `overwrite` | wipe + rewrite whole doc — **avoid on docs with manual content** | `--content` |

## Editing lists

- Add an item: `block_insert_after` the `<li>` above it with
  `<ul><li>new</li></ul>`. Lark merges consecutive same-type list items into one
  list, so it joins the existing `<ul>` rather than starting a new one. Verify
  after — occasionally you want to check it didn't split.
- Replace an item: `block_replace` that `<li>` with `<li>new</li>`. It stays in
  place in the same list.
- Rewrite a multi-item run: `block_replace` the first `<li>` with the whole new
  set (`<li>a</li><li>b</li><li>c</li>`), then `block_delete` the now-redundant
  old `<li>`s.

## Deleting nested lists: leaves before parents

If you delete a `<li>` that has a nested `<ul>` of children, delete the **child
leaves first, then the parent**. This avoids "block not found" errors from a
cascade deleting a child you then try to delete again. Build the comma-batch in
leaf→parent order.

## Replacing a whole cell's contents (no images in the cell)

A table cell is several blocks (`<p><b>展示规则</b></p><ul>…</ul><p><b>交互
</b></p><ul>…</ul>`). To swap all of it:

1. `block_replace` the cell's **first** block with the entire new content
   (multi-block — 1→many).
2. `block_delete` every **other** old block that was in that cell (the old list
   items, the old sub-headers, the old second list), leaf→parent order.

Result: the cell holds only the new content, in order, and you never touched the
`<td>` (which you couldn't address anyway). If the cell contains an `<img>`,
this is unsafe — use the table procedure instead.

## Multi-block content via stdin

Write the new fragment to a file and pipe it; this dodges all shell-quoting pain
and lets the fragment be as large as you like:

```bash
LARK_CLI_NO_PROXY=1 lark-cli docs +update --api-version v2 --doc <id> \
  --command block_insert_after --block-id <anchor> --content - < /tmp/frag.xml
```

Chain multiple writes with `&&` (or a loop that breaks on non-zero exit) so a
mid-stream failure doesn't leave blocks half-applied in the wrong order.
