# Tables, images, and @mentions — the irreplaceable-content cases

This is where whole-doc re-import destroys work. Read this before touching any
table that has a screenshot or a mention in it.

## How a Lark table is stored

```
<table id="…">
  <colgroup><col width="123"/>…</colgroup>     # widths; no id
  <thead><tr><th vertical-align="top"><p id="…">原型</p></th>…</tr></thead>
  <tbody>
    <tr>                                         # no id
      <td rowspan="4" vertical-align="top">      # no id
        <img id="…" src="<token>" href="…"/>     # ids only on contents
      </td>
      <td vertical-align="top"><p id="…">策略信息区</p><img id="…" …/></td>
      <td vertical-align="top"><p id="…"><b>展示规则</b></p><ul>…</ul></td>
    </tr>
    …
  </tbody>
</table>
```

Key facts:
- Only `<p>/<ul>/<li>/<img>` inside cells have ids. The `<table>` itself has an
  id; `<tr>`, `<td>`, `<col>` do not.
- A spanning first column is a single `<td rowspan="N">` in the first row; the
  later rows simply omit that `<td>`. Adding/removing a row therefore means the
  `rowspan` number has to change — which is a structural edit you can't do by
  addressing contents.

So: **cell text/bullet edits = easy** (address the `<p>/<li>`). **Row add/delete
or rowspan change = hard**, and if the table has images, it's the park→return
procedure below.

## Images: insert, swap, and why token reuse is fatal

Insert a local image (one step does create-block + upload + bind; lands at **doc
end**):

```bash
LARK_CLI_NO_PROXY=1 lark-cli docs +media-insert --doc <id> \
  --file ./pic.png --align center        # relative path only; cd into its dir
```

Then position it: `block_move_after --block-id <anchor> --src-block-ids <newimg>`.

**Swap an image in place** = insert new at end → `block_move_after` it under the
right heading/anchor → `block_delete` the old image block.

**Never** try to "reuse" an existing image by emitting `<img src="<token>">` in
new block content. Verified failure: lark ignores the token and inserts a junk
512×512 `test.jpg` placeholder under a different token. The real picture is gone.
The only safe way to relocate an existing image is `block_move_after`, which
preserves its identity (same token, same href) — confirmed by moving an image out
of and back into table cells with the token unchanged.

## The park → rebuild → return procedure

Use when you must change row structure / `rowspan` in a table that contains
images (the only way to do it without losing the screenshots).

1. **Park** every image in the table out to a stable spot outside it (e.g. right
   after the section heading), preserving identity:
   ```bash
   block_move_after --block-id <section-heading> \
     --src-block-ids img1,img2,img3,img4
   ```
2. **Rebuild** the now image-free table with `block_replace <table-id>`, writing
   the full new structure (correct `rowspan`, new/removed rows). Where each image
   belongs, leave a **uniquely-named placeholder paragraph** as a return anchor,
   e.g. `<td rowspan="5"><p>ZZP-ORIGIN</p></td>`, and for inline images put the
   cell's text `<p>` (e.g. `<p>策略信息区</p>`) which already serves as anchor.
3. **Fetch** the rebuilt table with ids; find each placeholder/anchor `<p>` id by
   its unique text.
4. **Return** each image with `block_move_after <anchor-p-id> --src-block-ids
   <img>`. A rowspan/origin image goes after its placeholder; an inline image
   goes after its cell's name paragraph (restoring "name then picture").
5. **Delete** the placeholder paragraphs (`block_delete`) so cells match the
   original (image only, no stray empty line).
6. **Verify**: image count back to baseline, every original `src` token present,
   `rowspan` correct, no `ZZP-…` markers left.

This is fiddly but fully deterministic, and it's the difference between a clean
edit and emailing the user "sorry, re-paste your 9 screenshots."

## Protecting @mentions

`@person` is `<cite type="user" user-id="ou_…" user-name="…">`. Recreating one
from its id is **unverified and in the same risk family as image-token reuse** —
assume it can break. So:
- Do **not** `block_replace` a whole table (or a section) that contains a
  `<cite>`. Edit only the cells that don't hold the mention.
- If a change genuinely requires restructuring the row a mention sits in, treat
  the mention like an image: park it with `block_move_after`, rebuild, move it
  back — or, if it's optional, hand it to the user as a manual step and say why.

## Embedded sheets / bitables / whiteboards

`<sheet>`, `<bitable>`, `<whiteboard>` blocks are live resources referenced by
token. Same rule: never regenerate them from text. Move, don't rebuild. To edit
their *contents*, switch to the corresponding skill (lark-sheets / lark-base /
lark-whiteboard) using the token from the dump.
