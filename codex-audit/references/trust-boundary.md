# Trust-Boundary Rules

The codex-audit skill enforces these rules in `scripts/codex_audit.py`
(L1, L2) plus convention for L3. The user can read the script source
to verify each rule is hard-coded.

## Three layers, three trust profiles

| Layer | Reviewer | Executor | Auto-fix loop | Trust profile |
|---|---|---|---|---|
| **L1** | codex (gpt-5.5) | Claude (Cowork sandbox) | ❌ | Claude orchestrates the audit but doesn't see codex output until after `.raw.txt` is written verbatim. sha256 verification possible. |
| **L2** | codex (gpt-5.5) | Claude Code (Mac) | ✅ multi-round | Same audit verbatim guarantee, plus every fix commit by Claude Code is re-audited before the loop exits. Tom sees the full git history. |
| **L3** | codex (gpt-5.5) | Tom (no Claude middleware) | ❌ | Strongest. Claude doesn't see the audit until Tom pastes verbatim into the repo. No script involvement. |

**The reviewer is identical in all three layers.** What differs is
the executor and the level of automation.

## Rule 1 — VERBATIM landing (L1, L2)

Codex's stdout is captured as RAW BYTES (no decode/strip/normalize)
and written byte-identical to a `<output>.raw.txt` sibling file. The
`response_sha256` in metadata is the sha256 of those bytes.

The `.md` audit file is a derived view (codex output + metadata
header). The trust source is the `.raw.txt` file, NOT the `.md`.

**L3** has no `.raw.txt` — Tom's transfer IS the trust step.

**Verification**:
```bash
sha256sum CODEX_AUDIT_X.md.raw.txt
# Compare against response_sha256 in metadata header of CODEX_AUDIT_X.md
```

## Rule 2 — Metadata is git-tracked (L1, L2)

Every `codex_audit.py` invocation appends one JSONL line to a
`CODEX_AUDIT_LOG.jsonl` file in the same directory as the audit.
Fields:

| Field | Description |
|---|---|
| `ts_utc` | ISO 8601 timestamp |
| `git_head` | `git rev-parse HEAD` at invocation time |
| `prompt_path` | Relative to repo root |
| `prompt_sha256` | sha256 of prompt file bytes |
| `audit_path` | Relative to repo root |
| `raw_audit_path` | Relative to repo root, `.raw.txt` |
| `response_sha256` | sha256 of `.raw.txt` bytes |
| `model` | e.g. `gpt-5.5` |
| `reasoning_effort` | `none`/`minimal`/`low`/`medium`/`high`/`xhigh` |
| `codex_version` | from codex stderr banner |
| `duration_s` | end-to-end time |
| `tokens_used` | parsed from codex stderr when reported; `null` otherwise |
| `exit_code_codex` | codex CLI exit code |
| `verdict_extracted` | `PASS`/`PASS WITH FOLLOWUPS`/`CONDITIONAL`/`FAIL`/`AMBIGUOUS`/`UNKNOWN` |
| `checked_verdicts` | list of all `[x]` matches found |
| `ambiguity_reason` | populated if multiple checkboxes |
| `has_p01_findings` | bool |

`git log -p docs/r89_X/CODEX_AUDIT_LOG.jsonl` shows the full audit
history across BOTH L1 and L2 (with `git_head` revealing whether the
audit was run from sandbox or Mac).

**L3** has no JSONL entry — manual transfer. Tom relies on the
audit file's content alone.

## Rule 3 — Verdict-driven exit code (L1, L2)

Determined by parsed verdict, NOT by Claude's preference:

```
PASS                                    → exit 0
PASS WITH FOLLOWUPS, no P0/P1 finding   → exit 0
PASS WITH FOLLOWUPS + P0/P1 finding     → exit 1
CONDITIONAL                             → exit 2
FAIL                                    → exit 2
Verdict unparseable                     → exit 3
Invocation error (paths, args)          → exit 4
Network / auth failure                  → exit 5
AMBIGUOUS (multiple [x])                → exit 6
Internal 30-min timeout (Mac L2)        → exit 7
```

**L1** halts on any non-zero exit. **L2** iterates on exit 1 / 2
(auto-fix loop) and halts on exit 3 / 5 / 6 / 7 (need human judgment).
**L3** has no exit code — Tom interprets verdict.

## Rule 4 — No auto-retry on transient failure (L1, L2)

A failed codex invocation (exit 5: network/auth, exit 7: internal
timeout) does NOT auto-retry
in L1 or L2's outer loop. The failure is logged + user decides.
Prevents auto-retry from masking quota / auth issues.

The L2 auto-fix loop iterates on REVIEW failures (exit 1, 2 — codex
found issues, Claude Code fixes), NOT on INVOCATION failures
(exit 3-7).

## Rule 5 — User's manual override

To disable the entire pipeline, uninstall the skill via Cowork UI.
Workflow reverts to manual transfer (L3-equivalent for every audit).

Per-call overrides:
- "skip codex this time" → Claude does not invoke
- "I'll run codex myself" → Claude pauses for Tom to provide audit
  (effectively L3 ad-hoc)
- "use L3" / "我自己审" → forces L3
- "use L2" / "上 Claude Code 跑" → forces L2 (cross-cutting / depth)
- "use L1" / "沙箱跑" → forces L1 (Claude commits to sandbox attempt
  even if borderline)

## Rule 6 — L2 auto-fix loop bounds

Claude Code's L2 loop has guards:

- **Max rounds**: 5 iterations. After 5 unsuccessful rounds, loop
  halts and reports to Tom.
- **Re-audit after fix**: every fix commit must be re-audited
  before the loop can exit. No "fix and trust me" — codex must
  re-pass.
- **Trust source preserved**: each round writes a fresh `.raw.txt`,
  appends to `_LOG.jsonl`. After the loop, Tom can inspect the
  full sequence.
- **Halt cases NOT iterated**: exit 3 (parse), 5 (auth/network),
  6 (ambiguity), 7 (internal timeout) → halt regardless of round
  count, since iterating won't help.
- **Token budget visibility**: each round logs duration_s and
  codex_version; the L2 summary message reports total
  duration + token usage estimate.

## Rule 7 — L3 verbatim transfer responsibility

For L3, Tom is responsible for VERBATIM transfer:

- Copy codex's full markdown response — no summarization
- No edits to fix typos or reformat
- Paste into the audit file path Claude designated
- Verify the verdict line matches what codex actually said

If Tom paraphrases or shortens, the audit loses its
independent-review character. Claude cannot detect this — the
trust boundary in L3 is Tom's discipline.

## Rule 8 — Auditing the audit pipeline = always L3

When the audit subject IS the audit pipeline (`codex_audit.py`,
SKILL.md, the trust boundary rules themselves), Claude MUST NOT
self-trigger L1 or L2. Reason: Claude shouldn't review its own
scaffolding via Claude-orchestrated tooling.

If the user asks Claude to audit `scripts/codex_audit.py` content
or this skill's contents, Claude's first action is: surface the L3
template + reasoning, do NOT auto-invoke L1.

## Verifying P0/P1 detection (Rule 3 specifics)

`has_p01_findings` only triggers on finding-header contexts:
- `### P0` or `### P1` (markdown heading)
- `- **P0** ...` or `- **P1** ...` (bold list bullet)
- `- P0:` or `- P1 -` (dash-separated bullet)

It does NOT trigger on prose like "no P0/P1 issues" or
"previously P0 (now closed)".

## Verifying verdict ambiguity (Rule 3 specifics)

The script finds ALL `[x]` verdict checkboxes in the audit. If
exactly one → that's the verdict. If more than one → AMBIGUOUS,
regardless of which appeared first. This guards against codex
accidentally marking multiple boxes (rare but observed).

## Two-file output explained (L1, L2)

Each L1/L2 audit produces TWO files:

```
docs/r89_X/CODEX_AUDIT_X.md         # human-readable, has metadata header
docs/r89_X/CODEX_AUDIT_X.md.raw.txt # codex stdout byte-identical
```

`response_sha256` covers `.raw.txt` only. Tom verifies by hashing
`.raw.txt` and comparing.

L3 produces only the `.md` file (Tom-pasted), no `.raw.txt`.

## Quick reference: when to escalate layers

```
L1 → L2:  L1 returned exit 124 (sandbox timeout)
          OR audit prompt is > 80 lines / cross-cutting
          OR Tom asks for xhigh + auto-fix loop
          OR audit covers > 200-line diff

L1/L2 → L3: subject is the audit pipeline itself
            OR Tom suspects bias from Claude
            OR pre-deploy gate / production-bound critical change
            OR Tom explicitly says "L3" / "我自己审"

L2 → L3:  L2 loop hit max rounds (5) without exit 0
          OR L2 returned exit 6 (ambiguous) and Tom wants
          a clean re-audit
```
