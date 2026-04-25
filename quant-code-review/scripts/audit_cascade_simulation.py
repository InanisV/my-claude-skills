#!/usr/bin/env python3
"""
audit_cascade_simulation.py — 维度 2.13 自动化扫描

Scan all backtest scripts and profiles for realism flag values.
Flag any use_*_check / use_*_simulation / next_bar_entry set to False.

Usage:
    python audit_cascade_simulation.py [project_root]

Exit code:
    0 = OK (no critical issues)
    1 = WARN (any False in research scripts)
    2 = CRITICAL (any False in production profile)

This script is part of the quant-code-review skill, dimension 2.13
(Backtest Realism Flag Audit). Origin: 2026-04-19 V15_PROD cascade incident
where use_liquidation_check=False silently inflated H1+H2 fDD from real -79.1%
to reported -37.7%, causing 6 days of research on a false foundation.
"""
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

# Realism flags whose False value indicates a simulation shortcut.
REALISM_FLAGS = [
    'use_liquidation_check',
    'use_wick_check',
    'use_funding_cost',
    'use_slippage',
    'use_partial_fill',
    'use_realistic_spread',
    'next_bar_entry',
    'use_intra_bar',
]

# Match either dict key or kwarg style:
#   'use_liquidation_check': False
#   "use_wick_check": False
#   use_funding_cost=False
PATTERN = re.compile(
    r"['\"]?(" + "|".join(REALISM_FLAGS) + r")['\"]?\s*[:=]\s*(True|False)",
    re.IGNORECASE,
)

# Heuristic: paths matching these patterns are considered production profiles
PROD_PROFILE_HINTS = [
    'profile', 'config/', '_prod', 'production', 'preset',
]

# Heuristic: paths matching these patterns are considered research scripts
RESEARCH_HINTS = [
    'backtest_scripts', 'research', 'experiment', 'sweep', 'diagnose',
    'alpha_lab', 'kfold', 'safety_sweep',
]


def classify(file_path: str) -> str:
    p = file_path.lower()
    is_prod = any(h in p for h in PROD_PROFILE_HINTS)
    is_research = any(h in p for h in RESEARCH_HINTS)
    if is_prod and not is_research:
        return 'production'
    if is_research:
        return 'research'
    return 'unknown'


def scan(root: Path) -> dict:
    findings = defaultdict(list)
    skip_dirs = {'__pycache__', '.git', 'node_modules', '.venv', 'venv', 'archive'}
    for py in root.rglob("*.py"):
        if any(part in skip_dirs for part in py.parts):
            continue
        try:
            text = py.read_text(errors='ignore')
        except Exception:
            continue
        for m in PATTERN.finditer(text):
            flag, val = m.group(1), m.group(2)
            line_no = text[:m.start()].count('\n') + 1
            ctx = text.split('\n')[line_no-1].strip()[:140]
            findings[flag].append({
                'file': str(py.relative_to(root)),
                'line': line_no,
                'value': val == 'True',
                'context': ctx,
                'category': classify(str(py.relative_to(root))),
            })
    return findings


def report(findings: dict) -> dict:
    summary = {}
    issues = []
    for flag, entries in findings.items():
        false_count = sum(1 for e in entries if not e['value'])
        true_count = sum(1 for e in entries if e['value'])
        summary[flag] = {
            'true': true_count,
            'false': false_count,
            'total': len(entries),
        }
        for e in entries:
            if not e['value']:
                if e['category'] == 'production':
                    severity = '🔴 CRITICAL'
                elif e['category'] == 'research':
                    severity = '⚠️ WARN'
                else:
                    severity = '⚠️ WARN (uncategorized)'
                issues.append({**e, 'flag': flag, 'severity': severity})
    issues.sort(key=lambda x: (
        0 if 'CRITICAL' in x['severity'] else 1,
        x['file'],
    ))
    return {
        'summary': summary,
        'issue_count': len(issues),
        'critical_count': sum(1 for i in issues if 'CRITICAL' in i['severity']),
        'warn_count': sum(1 for i in issues if 'WARN' in i['severity']),
        'issues': issues,
    }


def print_human(rep: dict):
    print("=" * 78)
    print("Backtest Realism Flag Audit — dimension 2.13")
    print("=" * 78)
    print()
    print("Summary by flag:")
    for flag, c in rep['summary'].items():
        print(f"  {flag:30s}  True={c['true']:3d}  False={c['false']:3d}  Total={c['total']:3d}")
    print()
    print(f"Issues: {rep['issue_count']} total  "
          f"({rep['critical_count']} 🔴 CRITICAL, {rep['warn_count']} ⚠️ WARN)")
    if rep['issues']:
        print()
        for i in rep['issues'][:30]:
            print(f"  {i['severity']}  {i['flag']}=False  "
                  f"{i['file']}:{i['line']}")
            print(f"      → {i['context']}")
        if len(rep['issues']) > 30:
            print(f"  ... +{len(rep['issues'])-30} more (see JSON output)")
    print()


def main():
    root = Path(sys.argv[1] if len(sys.argv) > 1 else '.')
    if not root.exists():
        print(f"Path not found: {root}", file=sys.stderr)
        sys.exit(2)
    rep = report(scan(root))
    print_human(rep)
    # Also write JSON to stdout-style file if requested
    if '--json' in sys.argv:
        print(json.dumps(rep, indent=2))
    if rep['critical_count'] > 0:
        sys.exit(2)
    if rep['warn_count'] > 0:
        sys.exit(1)
    sys.exit(0)


if __name__ == '__main__':
    main()
