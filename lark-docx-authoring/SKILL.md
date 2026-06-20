---
name: lark-docx-authoring
description: >-
  Author and surgically edit Feishu/Lark cloud documents (docx) with the
  lark-cli command line — both high-fidelity creation from scratch and,
  especially, incremental BLOCK-LEVEL patching of existing docs that already
  contain hand-added content (pasted screenshots, @mentions, embedded tables,
  diagrams) which must not be destroyed. Use this whenever you create, rewrite,
  or make targeted edits to a Lark/Feishu doc via lark-cli (docs +create /
  +fetch / +update / +media-insert): adding/replacing/deleting blocks, editing
  table cells or rows, inserting or swapping images, fixing heading numbering or
  ordered lists, or converting a Markdown/PRD into native Lark blocks. It encodes
  the traps that bite every time — whole-doc re-import wiping screenshots, broken
  image-token reuse, heading numbers that don't render, tables losing cell
  structure, block ids changing under you — and the verified way around each.
  Complements the stock lark-doc skill with the hard-won patch mechanics.
---

# Lark docx authoring & block-level patching (lark-cli)

This is a field guide for operating on Feishu/Lark **docx** documents through
`lark-cli`. It assumes the base `lark-doc` / `lark-shared` skills handle auth,
scopes and the raw command reference. What this skill adds is the part that is
not obvious and that destroys work when you get it wrong: **surgically editing a
live document without nuking the manual content already in it**, and producing
native-block docs that look hand-made rather than dumped.

Two modes:
- **Create** a new doc (or rebuild one you own) from Markdown/PRD → see
  [references/create-and-diagrams.md](references/create-and-diagrams.md).
- **Patch** an existing doc with targeted block edits → most of this guide.

## Golden rules (read once, they prevent the expensive mistakes)

1. **Re-dump before every editing session.** Humans (and other agents) hand-edit
   these docs between your runs — they delete modules, paste screenshots, change
   `rowspan`, renumber. Block ids and structure from a previous session are
   stale. Never reuse an old id map; fetch fresh every time.
2. **Never whole-doc re-import (`overwrite`, or delete-all-then-recreate) when
   the doc holds irreplaceable manual content** — pasted screenshots, `@mentions`,
   embedded sheets/bitables, whiteboards. Re-import regenerates those from your
   text and silently drops them. Patch the specific blocks instead.
3. **Locate by a real id map, never by guessing.** Dump with ids, build a
   `text → block_id` map, and address exactly the blocks you mean.
4. **Verify by round-trip.** After writing, fetch again and grep for the change
   AND for the things that must still be there (image count, mention names,
   module count). "The command returned success" is not verification.
5. **On any failure, stop and report — do not fall back to re-import.** Preserve
   the dump and emit a precise manual-patch list. A wiped screenshot is worse
   than an unfinished edit.

## Environment quickstart

- The binary is **`lark-cli`** (not `lark`/`larkdocs`). All docx commands take
  `--api-version v2`.
- **Pass content via stdin**, not inline, for anything non-trivial:
  `--content - < /tmp/chunk.xml`. The `@file` / `--file` forms only accept a
  **relative path inside the current directory** — absolute paths error out, so
  either `cd` first or use stdin.
- If a proxy is set (`HTTPS_PROXY`), large writes (long tables, media upload) can
  break mid-stream with `unexpected EOF`. Prefix **writes** with
  `LARK_CLI_NO_PROXY=1` to go direct. Reads are fine either way.
- Default content format is **XML** (DocxXML), which is what you want for
  fidelity (tables with cell sub-blocks, `<checkbox>`, callouts, colored spans).
  Only use `--doc-format markdown` when the user hands you a `.md` to import
  wholesale.

## Step 1 — dump and map

```bash
lark-cli docs +fetch --api-version v2 --doc <id|url> --detail with-ids \
  | jq -r '.data.document.content' | sed 's/></>\n</g' > /tmp/dump.xml
```

The `sed` splits one tag per line so you can read and grep it. Then orient:

```bash
grep -n '<h[2-5] \|<table id\|<img id\|<cite ' /tmp/dump.xml   # structure + landmines
grep -c '<img ' /tmp/dump.xml                                  # image baseline to preserve
```

Read the regions you will touch (don't trust memory of "what the doc looks
like"). Note every `<img>` and `<cite>` — those are the blocks you must route
around. See [references/block-operations.md](references/block-operations.md) for
how ids work and how to read partial scopes cheaply.

## Step 2 — pick the mechanism per change

The right tool depends on what you're changing. This table is the core of the
skill:

| You want to… | Mechanism | Notes / ref |
|---|---|---|
| Change wording inside one paragraph / list item | `block_replace` that `<p>`/`<li>` | ids are on the `<p>`/`<li>`, not the `<td>` |
| Add a bullet to an existing list | `block_insert_after` the `<li>` above it with `<ul><li>…</li></ul>` | merges into the same list |
| Replace a whole table cell's contents | `block_replace` the cell's first block with the full new content (1→many works), then `block_delete` the leftover old blocks | see [tables](references/tables-images-mentions.md) |
| Rename a heading / fix its number | `block_replace` the heading with **the number in the text** (`<h5>3. Foo</h5>`) | heading `seq=` does NOT render — [numbering](references/numbering-lists-escaping.md) |
| Add/delete a **table row**, or change `rowspan`, in a table **with images** | **park → rebuild → return** (move imgs out, rebuild table, move imgs back) | the one genuinely hard case — [tables](references/tables-images-mentions.md) |
| Swap an image in place | `media-insert` new file → `block_move_after` under the right anchor → `block_delete` old image | never `<img src="oldtoken">` — it's broken |
| Replace a whole section (several sub-blocks, no images) | `block_delete` the old blocks, then `block_insert_after` a stable anchor with the new multi-block content | anchor on something you're NOT changing |
| Fix an ordered list that renders "1, 1, 1" | `block_replace` the first `<li>` with ALL items as `<li seq="auto">…</li>`, delete the leftovers | [numbering](references/numbering-lists-escaping.md) |

## The landmines (each has burned a real session)

- **`block_replace` changes the block's id**, and it can expand **one block into
  many**. Consequence: if you need to `block_insert_after` a block AND
  `block_replace` it, do the **insert first** (the anchor id dies after the
  replace). After replacing a heading, don't reuse its old id for a `section`
  fetch.
- **`<tr>` and `<td>` have no block ids.** Only the cell *contents*
  (`<p>/<ul>/<li>/<img>`) are addressable; the `<ul>` container has no id either,
  so list edits happen at the `<li>` level. You therefore **cannot add or remove
  a table row by id** — that needs a rebuild.
- **Re-referencing an image by token is broken.** Writing `<img src="<existing
  token>">` does NOT reattach the picture; lark substitutes a junk 512×512
  placeholder under a new token. So you can never rebuild a table that contains a
  screenshot by re-emitting its `<img src>`. Move the real image block instead —
  `block_move_after` preserves the image's identity (token + href).
- **Heading numbers via `seq=` don't render.** `<h5 seq="1">` is stored but shows
  no visible "1." — so a doc mixing `seq` headings and text-numbered headings
  looks inconsistent. Put the number in the heading **text**. (Ordered *lists*,
  `<ol><li seq="auto">`, DO render — different element, different rule.)
- **Recreating an `@mention` (`<cite type="user" user-id=…>`) by id is
  unverified and risky** (same family as image-token reuse). Don't rebuild a
  table that contains a mention; edit only the non-mention cells, or park/return.
- **Escape `&`, `<`, `>` in text** as `&amp; &lt; &gt;` (tags themselves are not
  escaped). Fetched content comes back still-escaped, so grep for `&gt;` when you
  verify, not `>`.

## Step 3 — verify, then report honestly

Re-fetch and check, at minimum: the change landed; image count == baseline;
every `@mention` user-name still present; section/module count unchanged (unless
you intended otherwise); the doc tail has no stray `(Note: … generated by AI …)`
watermark. Then report what changed, what you verified, and — explicitly — any
change you could NOT do safely (e.g. a row that would have required risking a
mention), handed off as a manual-patch item with exact content. The task is not
"make the edits", it's "make the edits without destroying anything."

## References

- [references/block-operations.md](references/block-operations.md) — the 8
  update commands, id lifecycle, partial-read scopes, sequencing rules, the
  delete-order rule for nested lists.
- [references/tables-images-mentions.md](references/tables-images-mentions.md) —
  cell structure, `rowspan`, the **park → rebuild → return** procedure, image
  insertion/swap, why token reuse fails, protecting mentions.
- [references/numbering-lists-escaping.md](references/numbering-lists-escaping.md)
  — heading numbers vs ordered-list numbers, the "1,1,1" fix, escaping & grep.
- [references/create-and-diagrams.md](references/create-and-diagrams.md) —
  building a doc from scratch in native blocks (chunked create), and rendering
  HTML→PNG diagrams to embed.
