#!/usr/bin/env python3
"""
audit_risk_flags.py — 维度 P.4 自动化扫描

Scan a Python profile module for risk-related flags and report effectively-off values.
Usage:
    python audit_risk_flags.py path/to/profile.py PROFILE_NAME [--ast]

Exit code:
    0 = OK
    1 = WARN  (effectively-off ratio > 30%)
    2 = REJECT (effectively-off ratio > 50% — deployment forbidden)

This script is part of the quant-code-review skill, dimension P.4
(Profile Risk-Switch Inventory). Origin: 2026-04-19 V15_PROD cascade incident
where 9 of 17 risk flags were effectively-off (53%) and live equity dropped -73.8%.

Security: default loading uses exec() on the profile module (needed for
{**BASE, ...} style inheritance) -- run only on trusted repos. Pass --ast to
force AST-only parsing (no code execution) on untrusted codebases.
"""
import ast
import json
import re
import sys
from pathlib import Path

# Patterns that match risk-related flag names in profile dicts.
# Add project-specific patterns here if needed.
RISK_PATTERNS = [
    re.compile(r'^use_.*_check$'),           # use_liquidation_check, use_wick_check
    re.compile(r'^use_.*_simulation$'),
    re.compile(r'^use_.*_defense$'),
    re.compile(r'^use_.*_hibernation$'),
    re.compile(r'^use_.*_brake$'),
    re.compile(r'^use_.*_kill$'),
    re.compile(r'^.*_kill_.*$'),
    re.compile(r'^dd_tier_\d+$'),
    re.compile(r'^dd_scale_\d+$'),
    re.compile(r'^dd_score_\d+$'),
    re.compile(r'^max_exposure_.*$'),
    re.compile(r'^max_concurrent_.*$'),
    re.compile(r'^max_dca_layers$'),
    re.compile(r'^regime_scale_.*$'),
    re.compile(r'^regime_threshold_.*$'),
    re.compile(r'^regime_lc_.*$'),
    re.compile(r'^.*_per_position_cap_.*$'),
    re.compile(r'^.*_position_cap_.*$'),
    re.compile(r'^hysteresis_.*$'),
    re.compile(r'^cooldown_.*$'),
    re.compile(r'^.*_loss_cap_.*$'),
]


def is_risk_key(key: str) -> bool:
    return any(p.match(key) for p in RISK_PATTERNS)


def is_effectively_off(key: str, value):
    """Return (is_off: bool, reason: str)."""
    if isinstance(value, bool):
        if not value and key.startswith('use_'):
            return True, f"{key}=False (feature disabled)"
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if 'tier' in key and value >= 0.95:
            return True, f"{key}={value} (threshold near-100%, never triggers)"
        if 'scale' in key and value >= 1.0 and 'tier' not in key:
            return True, f"{key}={value} (scale=1.0, no reduction applied)"
        if 'kill' in key and value >= 0.95:
            return True, f"{key}={value} (kill threshold near-100%, never triggers)"
        if 'score' in key and 'dd_score' in key and value == 0.0:
            return True, f"{key}={value} (score adjustment is zero)"
        if 'max_exposure' in key and value >= 3.0:
            return True, f"{key}={value} (exposure >= 3x equity, very aggressive)"
    if value is None and ('cap' in key or 'limit' in key):
        return True, f"{key}=None (no cap)"
    return False, ""


def scan_profile(profile_dict: dict, profile_name: str) -> dict:
    risk_flags = {}
    effectively_off = []
    for key, value in profile_dict.items():
        if is_risk_key(key):
            risk_flags[key] = value
            off, reason = is_effectively_off(key, value)
            if off:
                effectively_off.append({'key': key, 'value': value, 'reason': reason})
    total = len(risk_flags)
    off_count = len(effectively_off)
    ratio = off_count / max(total, 1)
    if ratio > 0.5:
        severity = '🔴🔴 REJECT'
    elif ratio > 0.3:
        severity = '🔴 WARN'
    else:
        severity = '✅ OK'
    return {
        'profile': profile_name,
        'total_risk_flags': total,
        'effectively_off_count': off_count,
        'effectively_off_ratio': round(ratio, 3),
        'effectively_off_flags': effectively_off,
        'all_risk_flags': risk_flags,
        'severity': severity,
    }


def load_profile_dict(profile_file: Path, profile_name: str,
                      force_ast: bool = False) -> dict:
    """Try simple exec first; fall back to AST parsing if exec fails.

    force_ast=True skips exec entirely (safe on untrusted code).
    """
    text = profile_file.read_text()
    ns = {}
    if not force_ast:
        try:
            exec(compile(text, str(profile_file), 'exec'), ns)
        except Exception:
            ns = {}
    if not ns:
        # AST-based fallback: only walks Assign nodes for dict literals
        tree = ast.parse(text)
        for node in tree.body:
            if isinstance(node, ast.Assign):
                for tgt in node.targets:
                    if isinstance(tgt, ast.Name):
                        try:
                            ns[tgt.id] = ast.literal_eval(node.value)
                        except (ValueError, SyntaxError):
                            pass
    candidates = [
        profile_name,
        f"{profile_name}_PROFILE",
        profile_name.upper(),
        f"{profile_name.upper()}_PROFILE",
    ]
    for name in candidates:
        if name in ns and isinstance(ns[name], dict):
            return ns[name]
    raise KeyError(
        f"Profile {profile_name} not found in {profile_file}. "
        f"Tried: {candidates}"
    )


def main():
    force_ast = '--ast' in sys.argv
    args = [a for a in sys.argv[1:] if a != '--ast']
    if len(args) < 2:
        print(__doc__)
        sys.exit(2)
    profile_file = Path(args[0])
    profile_name = args[1]
    profile = load_profile_dict(profile_file, profile_name, force_ast=force_ast)
    report = scan_profile(profile, profile_name)
    print(json.dumps(report, indent=2, default=str))
    if 'REJECT' in report['severity']:
        sys.exit(2)
    if 'WARN' in report['severity']:
        sys.exit(1)
    sys.exit(0)


if __name__ == '__main__':
    main()
