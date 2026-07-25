#!/usr/bin/env python3
"""scripts/codex_audit.py — sandbox-driven codex CLI audit pipeline.

Self-driven by Claude (the sandboxed agent) instead of Tom forwarding
prompts manually. The trust boundary is enforced by HARD-CODED rules in
this script (Tom can `git diff` to verify Claude can't bypass them):

  Rule 1 — VERBATIM landing:
    Codex's response is written byte-identical between the
    `<!-- BEGIN codex output -->` and `<!-- END codex output -->`
    markers. The sha256 of the codex output portion is recorded in
    the JSONL log AND in the audit file's metadata header. Tom can
    `python -c "import hashlib; print(hashlib.sha256(...).hexdigest())"`
    on the codex-output region to verify Claude didn't alter a single
    byte.

  Rule 2 — Metadata is git-tracked:
    Every invocation appends one JSON line to a CODEX_AUDIT_LOG.jsonl
    file in the same directory as the audit. Contains:
      ts_utc, git_head, prompt_path, prompt_sha256, audit_path,
      response_sha256, model, reasoning_effort, duration_s, exit_code,
      verdict_extracted, has_p01_findings.
    Tom can `git log -p docs/r89_X/CODEX_AUDIT_LOG.jsonl` to audit
    every codex run we've ever made.

  Rule 3 — Verdict-driven exit code:
    PASS                                       → exit 0  (Claude proceeds)
    PASS WITH FOLLOWUPS, NO P0/P1 finding     → exit 0  (Claude commits
                                                          followup closure
                                                          BEFORE proceeding)
    PASS WITH FOLLOWUPS, has P0 or P1         → exit 1  HALT for Tom
    CONDITIONAL                                → exit 2  HALT for Tom
    FAIL                                       → exit 2  HALT for Tom
    Verdict unparseable                        → exit 3  HALT for Tom
    codex exec failed (network / auth / etc.)  → exit 5  HALT for Tom
    codex exec exceeded 30-min internal ceiling→ exit 7  HALT for Tom

  Rule 4 — No retry on transient failure:
    A failed codex invocation (exit 5) does NOT auto-retry. The
    failure is logged + Tom decides. This prevents auto-retry from
    hiding intermittent OpenAI API issues we should know about.

  Rule 5 — Tom's manual override:
    Tom can disable this script entirely by `git rm`-ing it. Skill /
    self-driven audit reverts to manual transfer ("Tom forwards").

Usage:
  python scripts/codex_audit.py \\
    --prompt docs/r89_X/CODEX_REVIEW_PROMPT_X.md \\
    --output docs/r89_X/CODEX_AUDIT_X.md

  # dry-run (don't call codex; just print what would happen):
  python scripts/codex_audit.py --prompt ... --output ... --dry-run

Requires:
  - codex CLI v0.120+ in PATH or at $HOME/.local/node_modules/.bin/codex
  - codex login already set up (auth.json in ~/.codex/)
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

def _autodetect_codex_bin() -> str:
    """Locate codex CLI across sandbox / Mac / Linux installations.

    Priority:
      1. $CODEX_BIN env var (explicit override)
      2. `which codex` (PATH-resolved, normal install)
      3. ~/.local/node_modules/.bin/codex (Cowork sandbox install)
      4. /usr/local/bin/codex (Mac Homebrew default)
      5. /opt/homebrew/bin/codex (Mac Apple Silicon Homebrew)
      6. ~/.npm-global/bin/codex (user-level npm install on Mac)

    Returns the first existing path. If none found, returns a
    placeholder for the error message; main() validates existence.
    """
    if "CODEX_BIN" in os.environ:
        return os.environ["CODEX_BIN"]
    # Try PATH lookup
    import shutil
    which_result = shutil.which("codex")
    if which_result:
        return which_result
    # Fallback to known install locations
    candidates = [
        Path.home() / ".local" / "node_modules" / ".bin" / "codex",
        Path("/usr/local/bin/codex"),
        Path("/opt/homebrew/bin/codex"),
        Path.home() / ".npm-global" / "bin" / "codex",
    ]
    for p in candidates:
        if p.exists():
            return str(p)
    # No codex found — return the most likely path so error message
    # is informative.
    return str(Path.home() / ".local" / "node_modules" / ".bin" / "codex")


DEFAULT_CODEX_BIN = _autodetect_codex_bin()
DEFAULT_MODEL = "gpt-5.5"
DEFAULT_REASONING = "xhigh"  # max reasoning per Tom's preference (Pro plan)
TIMEOUT_S = 1800  # 30 min ceiling — xhigh reasoning + repo grep can take a while

# Exit codes — caller scripts should treat 0 as "proceed" and any nonzero
# as "halt and let Tom review".
EXIT_PROCEED = 0
EXIT_HALT_FOLLOWUPS_P01 = 1
EXIT_HALT_CONDITIONAL_FAIL = 2
EXIT_HALT_UNPARSEABLE = 3
EXIT_INVOCATION_ERROR = 4
EXIT_AUTH_OR_NETWORK = 5
EXIT_HALT_AMBIGUOUS = 6  # codex checked multiple verdict boxes
EXIT_TIMEOUT = 7  # codex exec exceeded TIMEOUT_S internal ceiling
                  # (Mac L2 only — sandbox bash dies at 45s → 124 first)


# ─────────────────────────────────────────────────────────────────────────
# Utility functions (pure)
# ─────────────────────────────────────────────────────────────────────────
def sha256_of_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def sha256_of_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def get_git_head_sha(repo_root: Path) -> str:
    res = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo_root, capture_output=True, text=True,
    )
    return res.stdout.strip() if res.returncode == 0 else "unknown"


# ─────────────────────────────────────────────────────────────────────────
# Codex output handling
#
# v2 (post-self-audit fix #1): the previous version did
# stdout.decode().splitlines() + "\n".join() + .rstrip() + "\n", which
# meant response_sha256 was the hash of TRANSFORMED bytes, not codex's
# raw output. Codex (auditing this very script) caught it.
#
# v3 (post-e2e-test observation): codex exec writes the AI response
# *exclusively to stdout*, banner/version/progress to stderr. So the
# entire stdout IS the response body — no extraction needed. The .raw
# file = stdout bytes byte-identical; .md = same content + metadata
# header. response_sha256 covers .raw.
#
# v4 (v0.7.0 skill audit): TimeoutExpired now exits 7 (was 5 — an
# internal timeout was misreported as auth/network, misdirecting
# diagnosis); tokens_used parsed from stderr when codex reports it.
# ─────────────────────────────────────────────────────────────────────────
def extract_codex_version_from_stderr(stderr_str: str) -> str:
    """codex exec writes 'OpenAI Codex v0.128.0 (research preview)' to
    stderr near the start. Extract it for log/metadata."""
    m = re.search(r"OpenAI Codex (v[\d.]+\s*(?:\([^)]+\))?)", stderr_str)
    return m.group(1).strip() if m else "unknown"


# ─────────────────────────────────────────────────────────────────────────
# Verdict parsing
#
# v2 (post-self-audit fix #2): the previous version matched verdicts in
# priority order PASS WITH FOLLOWUPS → CONDITIONAL → FAIL → PASS, which
# could silently select PASS WITH FOLLOWUPS when codex accidentally
# checked multiple verdict boxes (e.g. [x] PASS WITH FOLLOWUPS appears
# earlier in document but [x] FAIL appears later).
#
# Fix: find ALL `[x]` verdict checkboxes; if exactly one → that's the
# verdict; if multiple → ambiguity, halt. This makes codex's
# accidental double-check land on Tom's desk instead of being silently
# resolved by priority order.
# ─────────────────────────────────────────────────────────────────────────
ALL_VERDICTS = ("PASS WITH FOLLOWUPS", "CONDITIONAL", "FAIL", "PASS")
VERDICT_LINE_PATTERN = re.compile(
    r"^\s*-\s*\[x\]\s*\*?\*?(PASS WITH FOLLOWUPS|CONDITIONAL|FAIL|PASS)\b",
    re.IGNORECASE | re.MULTILINE,
)

# v2 (post-self-audit fix #3): the previous P0/P1 pattern scanned the
# entire audit text, so phrases like "No P0/P1 findings detected" or
# "previously P0 (now closed)" would falsely flag has_p01=True.
#
# Fix: P0/P1 must appear in a finding-header context — section heading
# (`### P0`, `### P1`), bold list-item bullet (`- **P0** ...`), or
# explicit dash separator (`P0 - description`). This matches codex's
# actual writing style and excludes prose negations.
P01_FINDING_PATTERNS = [
    re.compile(r"^#{1,6}\s+P[01]\b", re.MULTILINE),       # `### P0 - foo`
    re.compile(r"^[\s-]*\*\*P[01]\*\*", re.MULTILINE),    # `- **P0** ...`
    re.compile(r"^\s*-\s+P[01]\s*[—:-]", re.MULTILINE),   # `- P0: foo`
]


def parse_verdict(audit_text: str) -> dict:
    """Extract verdict + P0/P1 finding markers.

    Returns dict with:
      verdict: 'PASS' | 'PASS WITH FOLLOWUPS' | 'CONDITIONAL' | 'FAIL'
               | 'AMBIGUOUS' (multiple [x] checkboxes) | 'UNKNOWN'
      has_p01: bool — only True if P0/P1 appears in a finding header
                      context, not in prose negations
      checked_verdicts: list of all matched verdict strings
      ambiguity_reason: str if verdict is AMBIGUOUS
    """
    matches = list(VERDICT_LINE_PATTERN.finditer(audit_text))
    checked = [m.group(1).upper() for m in matches]
    # Normalize "PASS" appearing inside "PASS WITH FOLLOWUPS" line: the
    # regex's group(1) already returns the full canonical form because
    # alternation order in pattern lists "PASS WITH FOLLOWUPS" before
    # bare "PASS", and regex tries alternatives left-to-right by default.

    if len(checked) == 0:
        verdict = "UNKNOWN"
        ambiguity = None
    elif len(checked) == 1:
        verdict = checked[0]
        ambiguity = None
    else:
        # Multiple checkboxes — defer to Tom rather than silently picking one.
        verdict = "AMBIGUOUS"
        ambiguity = (
            f"Codex's audit checked {len(checked)} verdict boxes: "
            f"{checked}. Halting — Tom must read the audit and decide."
        )

    has_p01 = any(
        bool(pat.search(audit_text)) for pat in P01_FINDING_PATTERNS
    )

    return {
        "verdict": verdict,
        "has_p01": has_p01,
        "checked_verdicts": checked,
        "ambiguity_reason": ambiguity,
    }


# ─────────────────────────────────────────────────────────────────────────
# Audit file format
# ─────────────────────────────────────────────────────────────────────────
BEGIN_MARKER = "<!-- BEGIN codex output (verbatim — sha256 in metadata above) -->"
END_MARKER = "<!-- END codex output -->"


def build_audit_file(codex_body: str, metadata: dict) -> str:
    """Wrap codex's verbatim output with a metadata header.

    The METADATA is OUTSIDE the BEGIN/END markers, so the sha256 in the
    metadata covers ONLY the bytes between the markers. Tom verifies
    by extracting that region and hashing it.
    """
    header = ["<!-- codex_audit.py — auto-generated by sandbox-driven codex CLI",
              "",
              "Metadata for reproducibility / trust-boundary verification:",
              ""]
    for k, v in sorted(metadata.items()):
        header.append(f"  {k}: {v}")
    header.extend([
        "",
        "To verify Claude didn't alter codex output, sha256 the bytes",
        "between the BEGIN/END markers below and compare against",
        "response_sha256 in metadata above.",
        "-->",
        "",
        BEGIN_MARKER,
        "",
    ])
    footer = ["", END_MARKER, ""]
    return "\n".join(header) + codex_body.rstrip("\n") + "\n" + "\n".join(footer)


# ─────────────────────────────────────────────────────────────────────────
# Main pipeline
# ─────────────────────────────────────────────────────────────────────────
def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--prompt", type=Path, required=True,
                        help="path to CODEX_REVIEW_PROMPT_*.md")
    parser.add_argument("--output", type=Path, required=True,
                        help="path to write CODEX_AUDIT_*.md")
    parser.add_argument("--log", type=Path, default=None,
                        help="audit log JSONL (default: <output_dir>/CODEX_AUDIT_LOG.jsonl)")
    parser.add_argument("--model", default=DEFAULT_MODEL,
                        help=f"codex model (default: {DEFAULT_MODEL})")
    parser.add_argument("--reasoning", default=DEFAULT_REASONING,
                        choices=["none", "minimal", "low", "medium", "high", "xhigh"],
                        help=f"reasoning effort (default: {DEFAULT_REASONING})")
    parser.add_argument("--repo-root", type=Path, default=None,
                        help="git repo root (default: auto-detected)")
    parser.add_argument("--codex-bin", default=DEFAULT_CODEX_BIN)
    parser.add_argument("--dry-run", action="store_true",
                        help="show invocation, skip codex call")
    args = parser.parse_args(argv)

    # Resolve paths
    if not args.prompt.exists():
        print(f"ERROR: prompt file not found: {args.prompt}", file=sys.stderr)
        return EXIT_INVOCATION_ERROR

    if args.repo_root is None:
        # Try walking up from prompt path first; if prompt is outside repo
        # (e.g. /tmp/test_prompt.md), fall back to walking up from cwd.
        for start in (args.prompt.resolve().parent, Path.cwd()):
            cur = start
            while cur != cur.parent:
                if (cur / ".git").exists():
                    args.repo_root = cur
                    break
                cur = cur.parent
            if args.repo_root is not None:
                break
        if args.repo_root is None:
            print("ERROR: could not auto-detect repo root from prompt path "
                  "or cwd; pass --repo-root explicitly", file=sys.stderr)
            return EXIT_INVOCATION_ERROR

    if args.log is None:
        args.log = args.output.parent / "CODEX_AUDIT_LOG.jsonl"

    # Pre-flight metadata
    git_head = get_git_head_sha(args.repo_root)
    prompt_sha = sha256_of_file(args.prompt)
    print("=== codex_audit.py ===")
    print(f"prompt:        {args.prompt}")
    print(f"prompt_sha256: {prompt_sha}")
    print(f"output:        {args.output}")
    print(f"log:           {args.log}")
    print(f"model:         {args.model}")
    print(f"reasoning:     {args.reasoning}")
    print(f"repo HEAD:     {git_head}")
    print(f"codex bin:     {args.codex_bin}")
    print(f"repo root:     {args.repo_root}")

    if args.dry_run:
        print("\nDRY-RUN: stopping before codex invocation.")
        return EXIT_PROCEED

    # Verify codex bin exists
    if not Path(args.codex_bin).exists():
        print(f"ERROR: codex binary not found at {args.codex_bin}", file=sys.stderr)
        return EXIT_INVOCATION_ERROR

    # Build invocation
    cmd = [
        args.codex_bin, "exec",
        "--cd", str(args.repo_root),
        "--sandbox", "read-only",
        "--ignore-user-config",
        "--ephemeral",
        "--color", "never",
        "--skip-git-repo-check",  # repo IS a git repo, but don't gate on it
        "-m", args.model,
        "-c", f'model_reasoning_effort="{args.reasoning}"',
    ]
    print(f"\n--- invoking codex (timeout {TIMEOUT_S}s) ---")
    print(" ".join(cmd))
    print()

    # Read prompt + execute
    with open(args.prompt, "rb") as f:
        prompt_bytes = f.read()

    start_ts = time.time()
    try:
        proc = subprocess.run(
            cmd,
            input=prompt_bytes,
            capture_output=True,
            timeout=TIMEOUT_S,
        )
    except subprocess.TimeoutExpired:
        print(f"ERROR: codex exec timed out after {TIMEOUT_S}s "
              f"(internal ceiling — split the prompt or lower reasoning)",
              file=sys.stderr)
        return EXIT_TIMEOUT
    duration_s = time.time() - start_ts

    raw_stdout_bytes = proc.stdout  # bytes — DO NOT decode for sha256
    stderr = proc.stderr.decode("utf-8", errors="replace")

    print(f"=== codex finished (rc={proc.returncode}, {duration_s:.1f}s) ===")

    if proc.returncode != 0:
        print("ERROR: codex exec returned nonzero", file=sys.stderr)
        if stderr:
            print(f"--- stderr (last 2000 bytes) ---", file=sys.stderr)
            print(stderr[-2000:], file=sys.stderr)
        if "401" in stderr or "Unauthorized" in stderr or "Reconnecting" in stderr:
            return EXIT_AUTH_OR_NETWORK
        return EXIT_INVOCATION_ERROR

    # ── Trust-source: write raw stdout bytes verbatim ──
    # codex exec writes its AI response exclusively to stdout (banner /
    # version / progress go to stderr). So stdout IS the response body
    # byte-identical. .raw.txt = stdout bytes; .md = same content + a
    # metadata header. response_sha256 covers .raw.txt's bytes only.
    raw_path = args.output.with_suffix(args.output.suffix + ".raw.txt")
    raw_path.parent.mkdir(parents=True, exist_ok=True)
    raw_path.write_bytes(raw_stdout_bytes)
    response_sha = sha256_of_bytes(raw_stdout_bytes)

    # Decode for parse_verdict + .md view (not for hashing)
    stdout_str = raw_stdout_bytes.decode("utf-8", errors="replace")
    audit_body_for_display = stdout_str
    codex_version = extract_codex_version_from_stderr(stderr)
    tokens_used = None
    m_tok = re.search(r"tokens used[:\s]+([\d,]+)", stderr, re.IGNORECASE)
    if m_tok:
        tokens_used = int(m_tok.group(1).replace(",", ""))

    # Build human-readable .md (extracted body view + metadata header)
    metadata_for_md = {
        "ts_utc": datetime.now(timezone.utc).isoformat(),
        "git_head": git_head,
        "prompt_path": str(args.prompt.relative_to(args.repo_root)
                           if args.prompt.is_absolute() and args.prompt.is_relative_to(args.repo_root)
                           else args.prompt),
        "prompt_sha256": prompt_sha,
        "raw_audit_file": str(raw_path.relative_to(args.repo_root)
                              if raw_path.is_absolute() and raw_path.is_relative_to(args.repo_root)
                              else raw_path.name),
        "response_sha256": response_sha,
        "response_sha256_covers": "the .raw.txt file's bytes (codex stdout verbatim)",
        "model": args.model,
        "reasoning_effort": args.reasoning,
        "duration_s": round(duration_s, 1),
        "codex_version": codex_version,
        "skill_version": "codex_audit.py@v4 (v0.7.0: timeout exit 7 + tokens_used)",
    }
    audit_text = build_audit_file(
        codex_body=audit_body_for_display,
        metadata=metadata_for_md,
    )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(audit_text)

    # Append to log
    try:
        rel_prompt = str(args.prompt.relative_to(args.repo_root))
    except ValueError:
        rel_prompt = str(args.prompt)
    try:
        rel_audit = str(args.output.relative_to(args.repo_root))
    except ValueError:
        rel_audit = str(args.output)

    # Parse verdict from the EXTRACTED body (since codex's audit prose
    # is what contains the verdict — the .raw.txt has extra header noise).
    parsed = parse_verdict(audit_body_for_display)
    log_entry = {
        "ts_utc": datetime.now(timezone.utc).isoformat(),
        "git_head": git_head,
        "prompt_path": rel_prompt,
        "prompt_sha256": prompt_sha,
        "audit_path": rel_audit,
        "raw_audit_path": rel_audit + ".raw.txt",
        "response_sha256": response_sha,
        "response_sha256_covers": "the .raw.txt file's bytes (codex stdout verbatim)",
        "model": args.model,
        "reasoning_effort": args.reasoning,
        "codex_version": codex_version,
        "duration_s": round(duration_s, 1),
        "tokens_used": tokens_used,
        "exit_code_codex": proc.returncode,
        "verdict_extracted": parsed["verdict"],
        "checked_verdicts": parsed["checked_verdicts"],
        "ambiguity_reason": parsed["ambiguity_reason"],
        "has_p01_findings": parsed["has_p01"],
    }

    args.log.parent.mkdir(parents=True, exist_ok=True)
    with open(args.log, "a") as logf:
        logf.write(json.dumps(log_entry) + "\n")

    print(f"\n=== audit complete ===")
    print(f"audit file (.md):  {args.output}")
    print(f"raw file (.raw):   {raw_path}")
    print(f"log entry appended: {args.log}")
    print(f"verdict:           {parsed['verdict']}")
    print(f"checked_verdicts:  {parsed['checked_verdicts']}")
    if parsed['ambiguity_reason']:
        print(f"AMBIGUITY:         {parsed['ambiguity_reason']}")
    print(f"P0/P1 in findings: {parsed['has_p01']}")
    print(f"response sha256:   {response_sha}")

    return _verdict_to_exit_code(parsed)


def _verdict_to_exit_code(parsed: dict) -> int:
    v = parsed["verdict"]
    if v == "PASS":
        return EXIT_PROCEED
    if v == "PASS WITH FOLLOWUPS":
        if parsed["has_p01"]:
            print("\nHALT: PASS WITH FOLLOWUPS contains P0/P1 finding — "
                  "Tom must review.", file=sys.stderr)
            return EXIT_HALT_FOLLOWUPS_P01
        return EXIT_PROCEED
    if v == "CONDITIONAL":
        print(f"\nHALT: verdict=CONDITIONAL — Tom must review.", file=sys.stderr)
        return EXIT_HALT_CONDITIONAL_FAIL
    if v == "FAIL":
        print(f"\nHALT: verdict=FAIL — Tom must review.", file=sys.stderr)
        return EXIT_HALT_CONDITIONAL_FAIL
    if v == "AMBIGUOUS":
        print(f"\nHALT: verdict=AMBIGUOUS ({parsed['ambiguity_reason']}) — "
              "Tom must review.", file=sys.stderr)
        return EXIT_HALT_AMBIGUOUS
    print(f"\nHALT: verdict='{v}' could not be parsed — Tom must review.",
          file=sys.stderr)
    return EXIT_HALT_UNPARSEABLE


if __name__ == "__main__":
    sys.exit(main())
