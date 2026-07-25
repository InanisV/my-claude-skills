# Phase-grouped audit cadence

For multi-step implementations, **DO NOT run one audit per step**.
Group steps into phases (typically 2-3 steps per phase) and run
**one L2 audit per phase**. Within a phase, Claude commits each
step + runs unit tests + does silent self-review. The phase boundary
is where L2 fires.

## Why this exists

Tom's verbatim feedback during R89.8 Batch C.1 implementation:

> 这样是不是拆的有点太碎了？L2 应该是大的模块，不然我要一直复制还是在来回传话

Translation: "Isn't this too granular? L2 should be at the big-module
level — otherwise I'm constantly copy-pasting back and forth."

The earlier pattern was per-step audits — every commit got its own
L2 prompt for Tom to paste into Claude Code on Mac. That meant 6
copy-paste cycles for a 6-step implementation. The phase-grouped
pattern reduces that to 3 cycles (one per phase) AND adds a benefit:
the audit also verifies producer/consumer integration across the
steps in that phase.

## When phase-grouping makes sense

Phase-group when ALL of:

- The implementation is ≥ 4 steps that build on each other
  (a producer step writes data, a consumer step reads it).
- Each step is small enough on its own (≤ 200 line diff) that
  a per-step audit would feel like overkill.
- The cross-step contract (producer/consumer interface) is the
  most likely failure surface, not the per-step internals.
- The user is involved in the audit loop (L2 with paste prompts —
  not L1 sandbox-self-driven, which has zero copy-paste cost).

Per-step audits still make sense when:

- Steps are independent (no producer/consumer dependency).
- The implementation is small (≤ 3 steps total).
- L1 is feasible for each step (single commit, ≤ 80-line prompt,
  Claude self-runs in sandbox — no Tom involvement needed per step).

## Phase composition heuristics

A phase typically groups:

- **Producer + immediate consumer** (e.g. step A writes a JSON
  metadata file, step B's function reads it).
- **Library + caller** (e.g. step A adds new keyword args to a
  function, step B calls the function with those args).
- **Refactor + new module that uses it** (e.g. step A splits a
  monolith into pure functions, step B's new module imports them).

A phase typically does NOT group:

- An implementation phase with a CLI integration phase (test the
  library independently, then audit the CLI/cron wrapper as its
  own phase — that wrapper failure mode is different).
- A core-correctness phase with an observability phase (different
  invariants).

R89.8 Batch C.1's grouping (worked well, 3 phases for 6 steps):

```
Phase A — panel data layer
  step 1: build_listing_dates.py (one-off metadata producer)
  step 2: build_features kwargs (consumer of step 1)
  audit: producer/consumer contract + each side's per-step internals

Phase B — v30 builder layer
  step 3: r63 split into pure functions (load_canonical / derive)
  step 3.5: r63 windowing kwargs (small extension of step 3)
  step 4: build_v30_live.py (calls step 3's pure functions)
  audit: pure-function contract + Phase 4 adapter + integration

Phase C — cron integration layer
  step 5: auto_refresh_funding.py cron (data producer)
  step 6: auto_refresh_v30_features wrapper switch (consumer of step 5
          via build_v30_live, plus updated upstream gate)
  audit: cron chain end-to-end + wrapper contract preservation
```

## Per-phase workflow

Within a phase, Claude does this WITHOUT involving Tom:

1. **Implement step N** — write code + unit tests for the step.
2. **Run regression suite** — `python -m pytest tests/scripts/` —
   the whole script test directory, not just the new file. This
   catches cross-test side effects.
3. **Self-review** — read the diff, run a smoke test against real
   data if relevant.
4. **git-cleanup skill** — classify any uncommitted files, update
   `.gitignore`, write a clean commit message. (See the
   `git-cleanup` skill — "review before every commit" is a project
   rule.)
5. **Commit** — message format `feat(<scope>): step N — <one-liner>`.
   The body should explain WHY (closed which finding / which
   spec section), what was preserved, what tests cover it.
6. **Loop** — go back to step 1 for step N+1, until the phase is done.

Phase boundary triggers L2 audit:

7. **Write the phase audit prompt** to
   `docs/<area>/CODEX_REVIEW_PROMPT_<topic>_phase_<X>.md`.
   The prompt MUST:
   - List the commits the audit covers (`git show <sha>` for each).
   - Reference any prior-phase audit as **baseline** ("treat as
     PASSed, don't re-audit deeply").
   - Have a separate **deeper-review** section per step.
   - Have a **phase-level integration** section with explicit
     producer/consumer contract questions that neither standalone
     audit could verify alone.
   - Mark "explicitly NOT in scope" for cross-cutting concerns
     deferred to a later phase or P2 follow-up tracker.
   - End with the standard verdict scale (PASS / PASS WITH
     FOLLOWUPS / CONDITIONAL / FAIL).
8. **Commit the prompt** so it's pinned to repo state.
9. **Surface to Tom** — give the L2 paste template (one block, ready
   to copy into Claude Code on Mac).
10. **Tom runs L2** on Mac with auto-fix loop.
11. **Read the verdict** when Tom reports back. If PASS WITH
    FOLLOWUPS / deferred P2 — track in the task list.
12. **Move to the next phase**.

## Audit prompt template (phase-level)

```markdown
# Codex review — <Topic> implementation Phase <X>

**Phase <X>** = <description> = step <N> + step <M> from
`<DESIGN_DOC>::§<plan section>`. This is the **<Xth> of <total>
grouped implementation audits** for <topic>. Group rationale:
<why these steps belong together — typically producer/consumer>.

Step plan:

    Phase A (...)  — step 1 + step 2 ← PASSED, audit archived
    Phase B (...)  — step 3 + step 4 ← this audit
    Phase C (...)  — step 5 + step 6 ← later audit

You audited Phase <X-1>
(`<archived audit path>`, **<verdict>**). Phase <X> is new in
these commits.

## Scope

<N> commits:

- `<sha1> <commit subject>`
- `<sha2> <commit subject>`

<commit summary — what each one ships>

## What I want from you

> <one-paragraph integration question — typically about
> producer/consumer contract>

### Step <N> — deeper review here

<list verifications, with file:line citations>

### Step <M> — deeper review here

<list verifications, with file:line citations>

### Phase <X> integration (THE phase-level question)

This is the part neither standalone audit could verify alone:

A. <Producer/consumer contract question>
B. <End-to-end chain question>
C. <Phase <X+1> readiness question>

### Things explicitly NOT in scope

- <cross-cutting concern deferred>
- <byte-equivalence test deferred to P2>

## Verdict scale

End your report with one of:

- [ ] **PASS** — Phase <X> is correct, proceed to Phase <X+1>.
- [ ] **PASS WITH FOLLOWUPS** — correct but specific cleanups (P2/P3).
- [ ] **CONDITIONAL** — has an issue that should be fixed before
      Phase <X+1> starts.
- [ ] **FAIL** — fundamental problem; redo.

## Resources

- Commits: `<sha1>`, `<sha2>`. Diffs: `git show <sha>`.
- Phase <X-1> audit (PASS, baseline): `<path>`.
- Design contract: `<DESIGN_DOC>::§<sections>`.
- Repo HEAD: `<sha>` on master.

## Output

Print your full report as your response — the pipeline captures
stdout (`--sandbox read-only`: you cannot write files). For L3
manual runs, Tom saves the verbatim response to
`<archived audit path>`.
```

## Auto-fix loop in phase-grouped pattern

When the L2 verdict is PASS WITH FOLLOWUPS or CONDITIONAL, Claude
Code on Mac runs the standard auto-fix loop (up to 5 rounds, see
SKILL.md::"L2 invocation"). For phase-grouped audits, the fix
commits get the same `fix(audit-loop): close <finding-id>` message
convention.

🔴 **Critical loop discipline — don't exit on first exit-0.**
Phase-grouped audits cover producer/consumer integration across
multiple files; that integration surface is exactly where
single-pass audits miss things and re-audit-after-fix catches them.
R102 v2 Phase C is the canonical case: round 2 returned exit 0
(PASS WITH FOLLOWUPS), round 3 found a 🔴 P0 ship-blocker
(runbook prescribed `legs = ["d16_fg", "DAU", "LSR"]` but pipeline
has no DAU/LSR branches and the milestone evidence proved
LSR-overlay was harmful). Exiting on round-2's exit-0 would have
shipped the bug. See `references/audit-failure-modes.md` for the
full catalog of bug classes confirmation rounds catch and the
detection rules for Claude. **Exit only after TWO consecutive
exit-0 rounds** (unified rule: an exit-0 round with zero commits
since the prior audited HEAD may exit immediately — see
SKILL.md::"L2 invocation").

R89.8 C.1 Phase B's auto-fix loop closed 3 findings in 3 rounds:

```
76d709d fix(audit-loop): close P1-load-universe-shape
0480c10 fix(audit-loop): close P2-funding-dir-ignored
30ff6e4 fix(audit-loop): close P3-real-data-smoke-test
e6c2851 docs(R89.8-C1): archive Phase B codex audit (PASS WITH FOLLOWUPS)
```

The deferred P2 (byte-equivalence test) was acknowledged in the
audit + recorded as a separate task to close after the next phase.

## Cross-phase audit references

When writing Phase <X+1>'s prompt:

- Reference Phase <X>'s archived audit as **baseline**:
  > "You audited Phase <X> (`<path>`, PASS WITH FOLLOWUPS). Treat
  > as the baseline — re-audit ONLY if you find a phase-level
  > integration issue Phase <X> couldn't have caught."
- Avoid re-auditing already-PASSed step internals. The phase-grouped
  audit is meant to LAYER on top of prior phases, not redo their
  work.

## Single-source-of-truth: the design doc

A multi-step implementation should have ONE design doc that:

- Lists the steps in order (`§<N>.<M> Implementation order`).
- Describes the cross-step contracts (e.g. JSON schemas, function
  signatures).
- Records design audits against the doc itself (the doc gets
  reviewed BEFORE implementation begins — separate from
  implementation audits).

Examples:
- `docs/r89_8/BATCH_C1_DESIGN.md` — design doc for Phase A/B/C.
- `docs/r89_8/CODEX_AUDIT_C1_DESIGN.md` — round-1 design audit
  (CONDITIONAL).
- `docs/r89_8/CODEX_AUDIT_C1_DESIGN_v2.md` — round-2 design audit
  after fixes (PASS WITH FOLLOWUPS).

When a phase implementation audit notices the design doc itself is
wrong (rare but possible), update the design + re-run the design
audit before fixing the implementation. The design doc is the
contract; if it's wrong, the implementation can't be made right.
