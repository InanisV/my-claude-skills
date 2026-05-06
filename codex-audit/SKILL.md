---
name: codex-audit
description: >
  Three-layer Codex CLI audit pipeline. Trigger when the user says
  "audit with codex", "let codex review", "走一轮 codex", "审一下";
  when a CODEX_REVIEW_PROMPT_*.md file is freshly committed and pending
  review; when Claude lands a milestone implementation commit that
  closes a design plan and the next step expects independent
  verification. The skill picks Layer 1 (sandbox-driven, Claude
  self-runs, ~30s budget) for small focused commits, Layer 2 (Claude
  Code on Mac, multi-round audit + auto-fix loop, no time limit) for
  cross-cutting / large / failed-L1 audits, and Layer 3 (user runs
  audit directly with no Claude middleware) for trust-critical
  audits like pre-deploy gates or audits of the audit pipeline
  itself. All three layers use the SAME codex CLI as reviewer
  (gpt-5.5) — only the executor and the trust boundary depth differ.
  For multi-step implementations, group steps into phases (2-3 steps
  per phase) and run ONE L2 audit per phase, NOT per step — see
  "Phase-grouped audit cadence" below.
metadata:
  version: "0.5.0"
  author: "Tom Zhang"
---

# codex-audit — three-layer Codex CLI audit pipeline

## What this skill does

Provides three layers of Codex CLI audit. The reviewer (gpt-5.5) is
the same in every layer — what changes is the executor and the
trust boundary depth.

| Layer | Executor | Auto-fix loop | Tom's work | Trust boundary |
|---|---|---|---|---|
| **L1** | Claude (Cowork sandbox) | ❌ (45s budget) | 0 | Claude writes prompt + reads audit + decides fix |
| **L2** | Claude Code (Mac) | ✅ multi-round | copy 1 command | Claude Code writes fix, but every fix is re-audited by codex before exit |
| **L3** | Tom (no Claude middleware) | ❌ (Tom decides each round) | copy prompt + paste audit | strongest — Claude doesn't touch audit pipeline OR fix process |

The trust boundary is enforced by the bundled Python script
(`scripts/codex_audit.py`) for L1 and L2. L3 doesn't need the
script — it's pure manual transfer.

## When to use

Trigger when ANY of these match:

- **Explicit user request**: "audit with codex", "审一下", "let codex
  review", "走一轮 codex".
- **A `CODEX_REVIEW_PROMPT_*.md` file exists** in the repo that hasn't
  been audited yet (no matching `CODEX_AUDIT_*.md` next to it, or
  the audit predates the prompt).
- **Implementation milestone closure**: Claude just landed a commit
  that closes a step in a multi-step design plan, and the workflow
  expects independent verification before the next step.
- **Phase boundary**: Claude just committed the LAST step of a phase
  in a multi-step implementation (see "Phase-grouped audit cadence"
  below — phase boundary is where L2 fires, NOT step boundary).

DO NOT trigger when:

- The prompt file doesn't exist yet — write the prompt first.
- The repo has uncommitted changes that the audit needs to
  evaluate — commit first.
- The user explicitly says "skip codex this time" — fall back to
  manual mode.

## Layer decision (Claude's choice at audit time)

Use **L1** when ALL of:

- Commit diff ≤ ~200 lines across ≤ 2 files.
- Prompt file ≤ ~80 lines.
- Audit asks 1-3 specific verifiable questions, not open-ended
  cross-cutting analysis.
- `medium` or `high` reasoning is sufficient (no `xhigh` needed).
- No need to grep the entire repo — codex reads commit's changed
  files plus 1-2 referenced files.

Use **L2** when ANY of:

- L1 already timed out (sandbox killed bash at 45s) — escalate
  automatically.
- Cross-cutting audit (covers many commits / multi-file diff > 200
  lines).
- **Phase-grouped implementation audit** (covers multiple steps
  with a producer/consumer relationship — see "Phase-grouped
  audit cadence" below).
- Design document audit (prompt file ≥ 80 lines, deep correctness
  reasoning).
- The user wants `xhigh` reasoning explicitly.
- The audit is expected to find issues that Claude can fix
  autonomously and re-audit (e.g. "audit until PASS, with auto
  fix-and-retry"). L2 is the only layer that supports the
  auto-fix loop.

Use **L3** when ANY of:

- The audit is of the audit pipeline itself (auditing
  `codex_audit.py` or this SKILL.md — Claude shouldn't review its
  own scaffolding).
- Final pre-deployment gate (production-bound critical change with
  $1k capital at stake — extra paranoia warranted).
- The user explicitly says "I want to audit this myself" / "no
  Claude middleware" / "走 L3" / "我自己审".
- Suspicion that Claude (any layer) might bias the result.

**Default**: try L1 first if borderline. If L1 times out, surface
the L2 fallback command (template in §"L2 invocation"). L3 is for
explicit cases — Claude does NOT propose L3 unprompted unless
auditing the audit pipeline.

## Phase-grouped audit cadence (multi-step implementations)

For any implementation that takes ≥ 4 ordered steps to complete,
**DO NOT run one audit per step**. Group steps into phases
(typically 2-3 steps per phase) and run **one L2 audit per phase**.

### Why

Tom's verbatim feedback during R89.8 Batch C.1:

> 这样是不是拆的有点太碎了？L2 应该是大的模块，不然我要一直复制还是在来回传话

Per-step audits = 6 copy-paste cycles for a 6-step implementation.
Phase-grouped = 3 cycles AND each audit also verifies producer/consumer
integration that no per-step audit could catch alone.

### Phase composition

A phase typically groups producer + immediate consumer, library +
caller, or refactor + new module that uses it. Within a phase,
Claude commits each step + runs the regression suite + does silent
self-review. **The phase boundary is where L2 fires.**

R89.8 C.1's grouping (worked well — 3 phases for 6 steps):

| Phase | Layer | Steps |
|---|---|---|
| A | panel data | 1 (build_listing_dates) + 2 (build_features kwargs) |
| B | v30 builder | 3 (r63 split) + 3.5 (windowing) + 4 (build_v30_live) |
| C | cron integration | 5 (auto_refresh_funding) + 6 (wrapper switch) |

### Per-phase workflow (Claude does this WITHOUT Tom)

For each step inside a phase:

1. Implement step + write unit tests.
2. Run regression suite (`pytest tests/scripts/`, not just the new file).
3. Self-review the diff + smoke test if relevant.
4. Run `git-cleanup` skill (project rule: review before every commit).
5. Commit with `feat(<scope>): step N — <one-liner>`.

At phase boundary (last step committed, all tests green):

6. Write `CODEX_REVIEW_PROMPT_<topic>_phase_<X>.md` (template in
   `references/phase-grouped-audits.md`).
7. Commit the prompt so it's pinned to repo state.
8. Surface the L2 paste template to Tom.
9. Tom runs L2 on Mac with auto-fix loop.

### Phase-audit prompt requirements

The prompt MUST:

- List ALL commits the audit covers (`git show <sha>` for each).
- Reference any prior-phase audit as **baseline** ("treat as PASSed,
  don't re-audit deeply").
- Have a **deeper-review section per step** with file:line citations.
- Have a **phase-level integration section** with producer/consumer
  contract questions that neither standalone step audit could
  verify alone.
- Mark "explicitly NOT in scope" for cross-cutting concerns
  deferred to a later phase or P2 follow-up tracker.
- End with the standard verdict scale.

Full template + R89.8 C.1 worked example: see
`references/phase-grouped-audits.md`.

### Per-step audits still make sense when

- Steps are independent (no producer/consumer dependency).
- The implementation is small (≤ 3 steps total).
- L1 is feasible per step (single commit, ≤ 80-line prompt — Claude
  self-runs in sandbox, no Tom involvement per step).

## Splitting changes into L1-friendly commits

To maximize L1 coverage when L2 isn't warranted, structure work so
each commit is a single auditable unit:

- ✅ One function/class implementation + its unit tests.
- ✅ One refactor (interface signature change + caller updates).
- ✅ One bug fix + the regression test for it.
- ✅ One config/metadata file change with the code that consumes it.
- ❌ Multiple unrelated improvements bundled in one commit.
- ❌ Implementation + docs + integration tests + CI in one commit
  (split into ≥2 commits).
- ❌ Big rewrites that touch >3 files (split into a sequence of
  ordered commits, each L1-auditable, OR use phase-grouped L2).

R89.7 Phase 1 had this pattern naturally: A.1 / A.6 / B.1 / B.2 / B.3
each landed in their own commit with focused review prompts.

## L1 invocation (Claude self-triggers in sandbox)

```bash
# Locate the script
SCRIPT=$(find / -name "codex_audit.py" -path "*codex-audit*" 2>/dev/null | head -1)

# Run with 40s timeout so Claude can detect sandbox kill cleanly
timeout 40 python "$SCRIPT" \
  --prompt docs/r89_X/CODEX_REVIEW_PROMPT_X.md \
  --output docs/r89_X/CODEX_AUDIT_X.md \
  --reasoning high
```

After the bash call:
- **Exit 0** → audit complete, parse verdict per the exit code table
  below.
- **Exit 1-6** → audit complete with non-PASS verdict, halt for user
  per the table.
- **Exit 124** → `timeout` killed it (sandbox couldn't fit the audit).
  **Switch to L2 fallback** with the same prompt/output paths. Do NOT
  retry L1 with the same prompt.

## L2 invocation (Claude Code on Mac, multi-round auto-fix loop)

When L1 isn't suitable (or you're at a phase boundary), give the
user this exact template, with prompt/output paths filled in. The
inner block is what the user pastes into a Claude Code session on
their Mac:

```
L2 audit — multi-round Codex CLI loop with auto-fix. Please run
on your Mac in a Claude Code session:

  cd /Users/Apple/Documents/GitHub/<repo>

Then paste this prompt to Claude Code:

╭─── PROMPT FOR CLAUDE CODE (Mac) ──────────────────────────────╮

You are running a multi-round Codex CLI audit + fix loop on the
current HEAD of this repo. The audit pipeline is in
`scripts/codex_audit.py`. Trust boundary rules are hard-coded in
that script — do NOT modify it during this loop.

Round procedure:

1. Run the audit:

       python scripts/codex_audit.py \
           --prompt docs/r89_X/CODEX_REVIEW_PROMPT_X.md \
           --output docs/r89_X/CODEX_AUDIT_X.md \
           --reasoning xhigh

2. Inspect the exit code:
   - **0**: PASS or PASS WITH FOLLOWUPS without P0/P1 → if any
     P2/P3 followups in the report, commit a closure per finding
     (one commit per finding, with `fix(audit-loop): close
     <finding>` style messages) and re-run the audit. **Do NOT
     exit the loop on the first exit-0** — the confirmation round
     is where cross-file consistency issues surface. Exit ONLY
     after TWO consecutive exit-0 rounds (or one exit-0 round
     when the prior round was also exit-0 with no commits since).
     See `references/audit-failure-modes.md` for why: R102 v2
     Phase C had round 2 exit 0 (PASS WITH FOLLOWUPS), then
     round 3 found a 🔴 P0 ship-blocker that the runbook
     prescribed an unsupported config — exiting on round 2's
     exit-0 would have shipped the bug.
   - **1, 2**: HALT verdict (PASS WITH FOLLOWUPS + P0/P1, or
     CONDITIONAL/FAIL). Read `CODEX_AUDIT_X.md`, understand the
     finding(s), plan a code fix, apply via Edit/Write, run
     `make test-lib && pytest tests/scripts/` (if applicable),
     commit with message `fix(audit-loop): close <finding ID>`,
     then go back to step 1.
   - **3, 5, 6, 124**: parse error / network / ambiguous /
     timeout → STOP loop, report to Tom for manual review.

3. Loop guard: if you reach round 5 without exit 0, STOP and
   report. Do not iterate indefinitely.

4. At end of loop, write a summary message to Tom:
   - Final verdict (PASS / halted)
   - Number of rounds
   - Each fix commit's SHA + finding ID + brief rationale
   - Audit file paths
   - Total tokens used (sum from CODEX_AUDIT_LOG.jsonl entries
     for this loop)

╰────────────────────────────────────────────────────────────────╯

Reply "L2 done, final verdict <PASS|halted>" when the Claude Code
loop finishes. I will read the audit log and proceed.
```

The L2 fix commits land in your repo via Mac → next sandbox
session sees them. Trust boundary: every fix is re-audited by codex
before the loop exits, so a PASS verdict means "code passed AFTER
all fixes were applied". Tom can `git log` to see exactly what
Claude Code changed.

## L3 invocation (Tom direct, no Claude middleware)

Reserve for trust-critical cases (auditing the audit pipeline,
pre-deploy gates, or when Tom requests explicitly).

Give Tom this template with the prompt content quoted in full:

```
L3 audit — please run this with zero Claude middleware. Steps:

1. Open your codex CLI / ChatGPT interface (NOT Claude Code, NOT
   any agent that might paraphrase the audit).

2. Paste this prompt verbatim:

╭─── PROMPT (paste to codex) ──────────────────────────────────╮
[full content of docs/r89_X/CODEX_REVIEW_PROMPT_X.md]
╰───────────────────────────────────────────────────────────────╯

3. Wait for codex to respond.

4. Copy codex's response **verbatim** (full markdown — no edits,
   no summarization) into:

       docs/r89_X/CODEX_AUDIT_X.md

5. Reply "L3 done" with the verdict line (PASS / PASS WITH
   FOLLOWUPS / CONDITIONAL / FAIL).

I will read the audit but will NOT propose any fix until you
direct me to. The L3 verdict is yours to interpret and yours to
escalate.
```

For L3, Claude does NOT generate the L2-style auto-fix loop —
Tom is the loop driver. Claude waits for Tom's direction after
each L3 audit.

## Interpreting exit codes (L1, L2)

The script's exit code is the load-bearing signal regardless of
which executor ran it. Do NOT auto-retry on any non-zero exit —
those require user review (L1) or Claude Code's loop logic (L2).

| Exit | Meaning | L1 action | L2 action |
|------|---------|-----------|-----------|
| 0 | PASS / PASS WITH FOLLOWUPS no P0/P1 | proceed | exit loop |
| 1 | PASS WITH FOLLOWUPS + P0/P1 | halt for Tom | iterate (auto-fix) |
| 2 | CONDITIONAL or FAIL | halt for Tom | iterate (auto-fix) |
| 3 | Verdict unparseable | halt for Tom | halt for Tom |
| 4 | Invocation error | halt for Tom | halt for Tom |
| 5 | Auth / network failure | halt for Tom | halt for Tom |
| 6 | AMBIGUOUS multiple `[x]` | halt for Tom | halt for Tom |
| 124 | sandbox bash timeout | escalate to L2 | (impossible — no Mac timeout) |

L3 has no exit codes — Tom interprets verdict directly.

## After the audit (any layer, same flow)

Always summarize the audit outcome to the user in plain language:

1. State the verdict (e.g. "PASS WITH FOLLOWUPS, 3 P2 cleanup
   items").
2. List findings briefly (P0/P1 first, then P2/P3, then notes).
3. Cite the audit file path so user can read full detail.
4. State next action based on exit code / Tom direction.

Example summary:

```
Codex audit verdict: PASS WITH FOLLOWUPS (L1, exit 0, no P0/P1)

Findings:
  F1 (P2): X — fix sketch: ...
  F2 (P2): Y — fix sketch: ...
  F3 (P3): wording nit in Z

Audit: docs/r89_X/CODEX_AUDIT_X.md
Log:   docs/r89_X/CODEX_AUDIT_LOG.jsonl

Next: I'll commit followup closure for F1+F2+F3, then proceed to
step N+1 of the implementation plan. Will report back when committed.
```

## Prerequisites (one-time setup)

### For L1 (sandbox)

1. **Codex CLI installed in sandbox**:
   ```bash
   ls ~/.local/node_modules/.bin/codex || \
     (mkdir -p ~/.local/lib/node_modules && \
      npm install --prefix ~/.local @openai/codex)
   ```

2. **Codex auth in sandbox**: `~/.codex/auth.json` must exist (from
   ChatGPT login on user's Mac, copied into sandbox via working
   directory transfer).
   ```bash
   ~/.local/node_modules/.bin/codex login status
   # Expected: Logged in using ChatGPT
   ```

### For L2 (Mac with Claude Code)

User has codex CLI installed globally
(`npm install -g @openai/codex`), logged into their ChatGPT
subscription (`codex login`), and a working `~/.codex/auth.json`.
Claude Code itself is the user's installed Mac app.
The script bundled with this skill auto-detects the codex CLI
location across PATH / Homebrew / npm-global.

### For L3 (Tom direct)

User has access to a codex interface (CLI, ChatGPT app, or web).
No setup beyond standard ChatGPT subscription login.

## Trust-boundary verification (L1, L2)

After every codex_audit.py invocation, the user can verify Claude
didn't tamper with codex's output:

```bash
sha256sum docs/r89_X/CODEX_AUDIT_X.md.raw.txt
grep response_sha256 docs/r89_X/CODEX_AUDIT_X.md
# These two MUST be the same hex string.
```

The `_LOG.jsonl` file records every invocation (across L1 and L2).
`git log -p docs/r89_X/CODEX_AUDIT_LOG.jsonl` shows the full
multi-layer audit history.

For L3, trust verification is identical — the audit file is whatever
Tom pasted, with no `_LOG.jsonl` entry from Claude. Tom is
responsible for verbatim transfer.

## Reference

- `references/trust-boundary.md` — full trust boundary rules and
  verification cheatsheet for the user.
- `references/phase-grouped-audits.md` — phase-grouping cadence
  for multi-step implementations: when to phase-group vs per-step
  audit, phase composition heuristics, per-phase workflow,
  audit-prompt template, R89.8 C.1 worked example.
- `references/audit-failure-modes.md` — catalog of bug classes
  that single-round audits miss but multi-round catch (config-
  references-unsupported-feature, silent-clamp-no-warning, test-
  assertion-strips-discriminator, test-env-leak). Includes
  detection rules for Claude when writing audit prompts AND
  when running the L2 loop. R102 v2 Phase C's R3-P0 ship-blocker
  is the load-bearing worked example.
