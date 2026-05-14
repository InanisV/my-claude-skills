# Finding triage — bug vs preference

## Why this matters

Codex audits return findings as a flat list under a verdict header.
The findings do NOT carry an explicit "bug" vs "opinion" flag — and
codex routinely produces both kinds in the same report, especially
in the P2/P3 tier.

The downstream consumer (Claude L1/L2 or Tom directly) has to make
that classification. The failure mode this rubric prevents:

> Treating every codex finding as a must-fix bug and mechanically
> closing each one in a fix commit, even when the finding is
> stylistic conservatism, an opinion about defaults, or a
> recommendation backed only by reviewer intuition.

Cumulatively this can cost real money on a deployed strategy by
silently tightening parameters that have a real operational drag.

**Source case**: `crypto-deep-learning-beta` R12-R15 (2026-05-14).
Three deference incidents found in retroactive self-audit after Tom
pushed back on the cron-buffer recommendation. See "Worked examples"
at the bottom — the math is small but the cumulative drag was real
(~2%/yr at scale).

## Classification rubric

A finding is a **BUG** if all of:

- States a concrete invariant violation
- Cites specific file:line or code path
- Verifiable by code grep, empirical A/B, or reading the diff
- Phrasing is declarative ("X is broken because Y", "X allows Y")

A finding is a **PREFERENCE** if any of:

- Uses softening language ("preferably", "consider", "may want")
- Recommends a default change without justifying $-magnitude
- Uses vague safety language ("would be safer", "tighter", "more
  robust") without specifying against what failure mode
- Backed by reviewer intuition rather than failure analysis
- First-person phrasing ("I would do X")

Borderline cases default to **PREFERENCE** — do the math.

## Trigger phrases that flag preferences

| Phrase from codex | Why it's a flag |
|---|---|
| "preferably" / "preferably use X" | by definition opinion |
| "consider" / "you may want to consider" | invitation, not instruction |
| "may want to" | conditional, not declarative |
| "suggest" / "I suggest" | opinion |
| "tight operationally" / "loose operationally" | aesthetic, not factual |
| "would be safer" | safer against what? at what cost? |
| "irrelevant slippage" / "trivial cost" | quantify it before agreeing |
| "small / marginal / negligible" | by what measure? |
| "I would do X" / "I would halt" | first-person opinion |
| "tighter would catch X earlier" | tighter at what cost? |
| "best practice" without citation | aesthetic |
| "stricter default" | conservatism, not bugs |

When you see any of these, **slow down**. The math takes 30 seconds.
The wrong fix takes a commit to revert + an audit-of-audits to spot.

## Math template for preferences

Before fixing a preference-flagged finding, compute:

```
Change cost   = expected_drag(NEW value) - expected_drag(OLD value)
Change benefit = avoided_loss_per_event × event_frequency

Net = benefit - cost
```

- If `net < 0` → KEEP old value, document the math in commit body.
- If `net > 0` → APPLY change, document the math in commit body.
- If you can't compute the inputs → ASK the user, don't accept the
  default.

Either way, the math goes in the commit log (or in a
`[NOT FIXED] P? <finding>: rejected — net = X-Y = -Z` line in the
audit closure message). Future Claude / Tom looking at the audit
chain should be able to see "this preference was considered +
rejected".

## Honor the user's prior judgment

If the user has previously stated an explicit position on the same
parameter or decision, the DEFAULT action is **keep their choice**.

Override ONLY when codex presents NEW FACTS:

| ✅ New fact (override OK) | ❌ New opinion (KEEP user's call) |
|---|---|
| "this code path crashes when X" | "I would set this differently" |
| "the data shows Y, not Z as assumed" | "tighter is conservative" |
| "an invariant Y is violated at file:line" | "would be safer to halt" |
| "empirical A/B shows X% impact" | "I'd preferably use 5s" |

When in doubt, ASK the user before applying codex's revision.

This applies retroactively too: if you're about to fix a finding
that contradicts a position the user took 3 rounds earlier, surface
it explicitly. Don't silently flip it.

## PASS WITH FOLLOWUPS exit criterion

The L2 auto-fix loop exits on first PASS WITH FOLLOWUPS without
P0/P1 (exit code 0). This does **NOT** mean "must close N followups
before exit".

**Cleanly exit** when:

- All followups are preferences AND your retro math doesn't
  support the change.
- Each preference is documented in the commit log as
  "considered + rejected" with reasoning.

**Iterate (auto-close)** when:

- Followups are bugs (file:line + invariant violation).
- Preferences whose math has positive EV.

Pure preference-only PASS WITH FOLLOWUPS that exits without closing
everything is a **valid outcome**. The loop's job is to close bugs,
not to please codex aesthetically.

## Worked examples (crypto-deep-learning-beta R12-R15)

### Example 1: R13 P2 cron buffer (FAILURE → revert)

**Codex finding (R13)**:
> "01:00:01 UTC is safe by assertion but tight operationally.
> DEPLOY.md should explicitly require NTP/chrony/systemd-timesyncd
> and **preferably use a few-second buffer, e.g. 01:00:05 UTC**."

**What Claude did**: directly changed `01:00:01 → 01:00:05` across
DEPLOY.md + signal_runner.py + checklist. Three commits propagated
the value forward.

**What Claude should have done**:

```
Change cost (1s → 5s):
  4s extra delay × ~30 positions × √(0.70²/yr / (365×24×3600))
  × ~20% daily turnover × 250 cycles/yr
  ≈ ~2%/yr expected drag

Change benefit (1s → 5s):
  Avoided "NTP-drift miss" events:
  - Modern NTP keeps drift < 100ms, miss requires NTP drift >500ms
    AND binance publish latency >500ms in same cycle → < 1/yr
  - Per miss = 1 day expected return = -0.4%/event
  - 1 × -0.4% / yr = -0.4%/yr
  Benefit ≈ 0.001%/yr (rough)

Net = 0.001% - 2% = -2%/yr → KEEP 1s.
```

The math was trivial (30 seconds). Claude didn't do it. Tom caught
it on R15 retrospective and the value got reverted in commit
`6fc988d`.

**The deference trigger**: "preferably" + "tight operationally".

### Example 2: R12 Recommendation shadow halt-by-default (LUCK)

**Codex finding (R12)**:
> "**I would** halt on v137 shadow fallback by default, with an
> explicit env override. Offline mean is not the 49,477x path,
> and shadow failure is likely deterministic data/code trouble,
> not a harmless transient."

**What Claude did**: changed `alert+continue → halt-by-default` with
`ALLOW_SHADOW_FALLBACK=1` opt-in. No math at the time.

**Retro math after Tom pushback**:

```
Shadow full-fail frequency:
  5 universes × 2 cost regimes × ~stable pipeline
  → essentially never, < 1/yr

Halt cost (when triggered):
  1 missed day × ~0.4%/day expected return = -0.4%

Continue cost (when triggered):
  Offline mean weights ≠ time-varying online weights.
  Memory says final-bar 96% u34 vs mean 19% u34 (drastic).
  1-7 days until operator intervenes × ~1-5% relative drag
  ≈ -1% to -5% absolute drag

Net halt vs continue = 0.4% << 1-5% → HALT is cheaper.
```

Math actually supports halt. Claude got **lucky** — the fix
happened to be correct. The PROCESS was still wrong: no
computation at the time of fixing.

**The deference trigger**: "I would" (first person opinion).

### Example 3: R13 P2 funding 24h → 12h (DEFENSIBLE, both ways)

**Codex finding (R13)**:
> "Funding 24h is loose for a high-impact source. 12h would catch
> two missed funding events at the daily launch time while
> tolerating one missed/immediately-delayed event."

**What Claude did**: changed `24h → 12h`. No math at the time.

**Retro math**:

```
At 01:00:01 cron, funding events at 00:00/08:00/16:00 UTC:
- 0 misses: latest = 1h old (well under either budget)
- 1 miss: latest = 9h old (under both budgets)
- 2 misses: latest = 17h old (over 12h, under 24h)
- 3 misses: latest = 25h old (over both)

False positive rate at either threshold: ~0
True positive: tightening to 12h catches genuine staleness ~11h
sooner per event. Funding-leg drag ~0.2%/day stale × 11h/24
= ~0.1% per event detected sooner.

Genuine staleness events / yr: maybe 1-2 (data outages are rare).
Tightening benefit: +0.1-0.2%/yr.
Tightening cost: minimal (false positive rate ~0 at either value).
```

Both 12h and 24h are defensible. Difference is in the noise.

Lesson: even when retro math says "either is fine", the act of
**not computing at fix time** was the failure. A defensible fix
arrived at by accident is still a process failure.

**The deference trigger**: "would catch X earlier".

## Audit-of-audits — retrospective step

After every multi-round audit sequence completes (or before
deployment), run a retrospective triage table:

| Round | Finding | Bug or Pref? | Math support? | Action | Status |
|---|---|---|---|---|---|
| R12 P0 | 23h aggregate | Bug | A/B confirmed | fix | done |
| R12 P0 | Funding fail-open | Bug | grep confirmed | fix | done |
| R12 P1 | Off-by-one ensemble | Bug | math derivation | fix | done (impact not measured) |
| R12 Rec | Shadow halt-by-default | Pref | retro math OK | fix | kept (lucky) |
| R13 P2 | Cron buffer 5s | Pref | retro math NO | revert | reverted (6fc988d) |
| R13 P2 | Funding 24h → 12h | Pref | retro math neutral | fix | kept (defensible) |
| ... | ... | ... | ... | ... | ... |

This audit-of-audits step is itself a worthwhile final commit
before deploy. It surfaces deference patterns that single-round
review missed.

For `crypto-deep-learning-beta` R12-R15: 3 of ~15 findings were
preferences accepted without math. 1 reverted (cron buffer); 2
defensible by retro math but lucky. Process failure rate
3/15 = 20%.

If your audit-of-audits shows > 10% deference rate, the audit
prompts likely need more constraint ("only flag concrete bugs,
not stylistic preferences") AND the fix loop needs the triage
step front-loaded.

## Practical workflow integration

For Claude (L1 self-run or L2 auto-fix loop):

```
1. Run codex audit.
2. Read CODEX_AUDIT_X.md.
3. ⮕ TRIAGE: classify each finding as Bug | Preference.
   For each Preference, compute EV math (template above).
   Surface the table to user before any fix commit if > 1
   preference flagged.
4. Plan fixes only for: bugs + math-positive preferences.
5. Apply fixes.
6. Re-run audit.
7. On loop exit: write the retrospective triage table to
   docs/<topic>/AUDIT_TRIAGE_<topic>.md (or similar).
```

For Tom (L3 manual):

```
1. Paste audit prompt to codex.
2. Read response.
3. Classify each finding (this rubric).
4. Decide which to act on (only bugs + math-positive prefs).
5. Apply fix or revert.
6. Reply to Claude with the triage outcome.
```

## When the user pushes back

If the user pushes back on a fix you applied, before defending or
explaining:

1. Re-read the finding's phrasing — was it "preferably" / "I would"
   / soft language?
2. If yes → admit the deference. Don't argue from codex authority.
3. Compute the retro math.
4. Revert if math doesn't support.

The user's pushback often catches the deference faster than your
own self-review. Treat it as a signal that the rubric should have
caught it earlier.

## Anti-pattern: arguing from codex authority

When Claude defers to codex without independent reasoning, the
explanation often takes the form:

> "Codex R13 found X, so I changed Y to Z."

This is **insufficient** as a fix justification. Codex's finding
is the **observation**, not the **decision**. The decision needs
to incorporate:

- Whether the finding is bug or preference
- If preference: the EV math
- The user's prior position on the parameter
- The reversibility/cost of the change

A correct explanation looks like:

> "Codex R13 flagged the cron buffer as 'tight operationally,
> preferably use 5s'. Triaging as preference (softening language,
> no $-magnitude). Math: 4s × 30 pos × turnover × vol × 250/yr
> ≈ 2%/yr drag vs 0.001%/yr miss cost. KEEPING 1s buffer.
> Documented in audit closure."

The first form is deference. The second is review.
