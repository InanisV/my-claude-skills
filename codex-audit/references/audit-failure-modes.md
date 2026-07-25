# Audit failure modes — what multi-round audits catch that single-round misses

This file catalogs classes of bug that codex L2 multi-round audits
have caught after one or more earlier rounds passed. The pattern:
a single audit pass cannot see the entire surface; later rounds re-read
the artifacts with the prior round's findings already closed, and
sometimes notice an inconsistency that only becomes visible *after* the
attention-grabbers are out of the way.

For Claude: when writing prompts and running audits, **the existence of
this catalog is the strongest argument for not exiting the L2 loop on
the first PASS**. If the auto-fix loop fixes findings in round N, ALWAYS
do round N+1 to confirm — and treat a NEW finding in N+1 as fully
legitimate, not as "round N missed something embarrassing".

## Failure mode A — config example references unsupported feature

**Definition.** Documentation, runbook, README, deploy guide, or design
doc shows a configuration / API call / CLI flag that the actual code
doesn't support. Common form: a list of options where one or more
entries don't have a code path; the example would crash on first run.

**Why single-round misses it.** Round 1 reads each artifact in
isolation — runbook, code, tests — and audits each against its prompt's
verifications. The runbook "looks reasonable" because the format is
right; the code "looks correct" because each branch is implemented.
The bug is in the SET RELATION between them: the runbook prescribes
something the code rejects.

**Why multi-round catches it.** After round-1 fixes land, round 2 has
fewer P0/P1 items to focus on, so attention shifts to cross-file
consistency. Round 3's "is this still PASS?" pass often runs that
consistency check more rigorously than round 1's "is each thing
correct?" pass.

**R102 v2 Phase C R3-P0 worked example (2026-05-06).**

The Phase C runbook prescribed:

```python
legs = ["d16_fg", "DAU", "LSR"]   # 3-leg R102 v2 champion
```

But:

1. `live/signals/pipeline.py:_load_leg_returns()` only has branches
   for `D16` / `d16_fg` / `PPO_ens` / `SAC_mega` / `Funding` / `v30` /
   `CM30d`. No DAU/LSR branch. Bot startup would raise
   `RuntimeError: Failed to load legs: ['DAU', 'LSR']`.
2. The R102 v2 milestone (`MILESTONE_R102_V2_HONEST.md`) explicitly
   showed LSR overlay was *harmful* (414% vs 487% baseline) and
   D16+LSR was *worse than D16-only* (629% vs 713.7%). The actual
   champion was D16-only with F&G overlay.

R1 PASSED on the runbook (round-1 validators didn't grep example
config strings against pipeline branches). R2 PASSED. R3 caught it
under exit code 2 (FAIL) with a P0 verdict.

**Detection rule for Claude (writing prompts).** When the prompt covers
a runbook / docs / examples file, ALWAYS include this verification:

> For every config example / API call / CLI flag in the runbook, grep
> for it in the implementing code (pipeline branches, CLI argparse,
> handler dispatch tables). Flag any reference that has no
> corresponding code branch. Where the runbook references prior
> milestone/research evidence (e.g. "champion config"), check that
> evidence with a citation, not from memory.

**Detection rule for Claude (running audits in the L2 loop).** When
loop round N returns exit 0 (PASS or PASS WITH FOLLOWUPS no P0/P1)
after round N-1 had P0/P1, ALWAYS schedule one more confirmation
round before exiting. The follow-up round IS the cross-file
consistency check.

## Failure mode B — silent overshoot under safety nets

**Definition.** A defensive cap / clamp / normalization fires
silently when input exceeds a bound. The cap prevents the immediate
disaster but hides the upstream signal bug that produced the
overshooting input. Operators only notice when PnL drifts.

**Why single-round misses it.** Round 1's correctness check confirms
"the cap works as designed". The bug isn't the cap, it's the absence
of a `log.warning` or alert when the cap fires.

**Why multi-round catches it.** Once round 1's correctness items are
closed, round 2's "anything else?" sweep looks at the cap from a
debugging-affordance angle: "if this fires in production, will we
know?".

**R102 v2 Phase C R1-P1 example.** `_normalize_leg_weights` capped a
leg's gross at `max_gross` silently. Fix: add `log.warning("Leg %r
gross overshoot: observed=%.4f > cap=%.4f, ...")` so a signal bug
that produces gross > cap leaves a forensic trail.

**Detection rule for Claude.** Whenever code has a "if x > cap: x =
cap" or `min(x, cap)` pattern, the audit prompt should include:
> Confirm the clamp emits a `log.warning` (or equivalent) on every
> firing. A silent clamp is a debugging black hole.

## Failure mode C — test assertion that strips the discriminator

**Definition.** A test compares two structures with a comparison
helper that has been weakened to silence noise (e.g.
`reset_index(drop=True)` before `assert_frame_equal`). The strip
makes the test pass even when the two structures actually differ on
the stripped attribute.

**Why single-round misses it.** Round 1 reads the test and confirms
"it asserts equality". It doesn't notice the equality is on a
projection.

**Why multi-round catches it.** Round 2's
"is the assertion strong enough?" pass spots the projection.

**R102 v2 Phase C R3-P2 example.** The byte-equivalence test had
`actual.reset_index(drop=True), expected.reset_index(drop=True)` —
which would pass even if the index dates shifted. Fix: drop the
`reset_index` so index equality is also checked, and use
`check_freq=False` for the synthetic-vs-rebuild metadata
difference (the only legitimate difference).

**Detection rule for Claude.** When the prompt covers a comparison
test (byte-equivalence, regression, golden-file), include:
> Confirm the assertion does not strip / drop / project away any
> attribute that participates in the contract under test. Index,
> dtype, frequency, name: each must be checked unless the
> contract explicitly excludes it AND the exclusion is justified
> with a code comment.

## Failure mode D — test environment leak across files

**Definition.** A test sets a global side-effect (env var, sys.path,
working directory, monkeypatch on a global object) that persists
beyond the test's lifetime and influences subsequent tests in
unrelated files. Often invisible in isolation; only manifests when
test ordering changes.

**Why single-round misses it.** Round 1 runs the affected test and
its dependencies in a clean order; the leak doesn't surface.

**Why multi-round catches it.** Once the regression suite runs at
several different commits across the loop, ordering perturbations
expose the leak.

**R102 v2 Phase C R2-P3 example.** A test set `os.environ["ALLOW_STALE_LEGS"]
= "1"` directly. After the test exited, the env var stayed set,
affecting later tests. Fix: `monkeypatch.setenv("ALLOW_STALE_LEGS",
"1")` so pytest auto-undoes on teardown.

**Detection rule for Claude.** When the prompt covers tests that touch
env vars / sys.path / working dir, include:
> Confirm every global side effect uses pytest's `monkeypatch`
> fixture (or equivalent context manager) so it's auto-undone on
> teardown. Direct `os.environ[...] = X` or `sys.path.insert(0,
> X)` without cleanup is a leak.

## Anti-pattern — exiting the L2 loop on the first exit-0

The class of bug this catalog describes is exactly what gets missed
when Claude Code exits the L2 loop the moment one round returns
exit 0. The R102 v2 Phase C audit log shows this pattern:

| Round | Exit | Verdict | Findings |
|---|---|---|---|
| 1 | 1 | FAIL | P1 + P2 + P3 |
| 2 | 0 | PASS WITH FOLLOWUPS | P3 only |
| 3 | 2 | FAIL | **P0** + P2 |
| 4 | 0 | PASS WITH FOLLOWUPS | none (op note only) |

If round 2's exit 0 had ended the loop, the P0 from round 3 would
have shipped. The lesson: **after fixing findings, re-audit until an exit-0
round lands on a tree with no commits since the prior audit** — in
the common case, TWO consecutive exit-0 rounds. (A
preference-only exit-0 round with zero commits exits immediately —
nothing changed to re-audit; see `references/finding-triage.md`.)

The auto-fix loop logic in `SKILL.md::"L2 invocation"` accommodates
this — when the verdict is PASS WITH FOLLOWUPS in round N, Claude
Code commits the followup closures and runs round N+1 as a
confirmation round. The confirmation round is what surfaces
cross-file consistency issues that only become visible after the
attention-grabbing P0/P1 items are out of the way.

## Anti-pattern — single-pass design audit

The same logic applies to design-document audits, not just
implementation audits. A design doc that PASSes round 1 should still
get round 2 — round 2 reads the doc with awareness of round 1's
adjustments and often spots cross-section inconsistencies (e.g.
section §3 prescribes a config that contradicts section §5's worked
example).

## Reference
- L2 loop bounds and re-audit-after-fix rule: `references/trust-boundary.md::"Rule 6"`.
- Phase-grouped audit cadence: `references/phase-grouped-audits.md`.
