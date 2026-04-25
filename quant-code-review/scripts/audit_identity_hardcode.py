#!/usr/bin/env python3
"""
audit_identity_hardcode.py — 维度 4.5.2 自动化扫描

Find hardcoded string literals assigned to monitor_export.identity.* fields.

Usage:
    python audit_identity_hardcode.py [project_root]

Exit code:
    0 = OK
    1 = WARN (suspicious patterns found)
    2 = CRITICAL (clear hardcoded identity strategy strings)

This script is part of the quant-code-review skill, dimension 4.5.2
(Identity Anti-Hardcode). Origin: 2026-04-19 cascade incident, where
identity.strategy = "Regime-Adaptive DCA V15 (MEGA V2)" was a hardcoded
constant in live_dca_bot.py:4972, leading the assistant to misdiagnose
"H1+H2 not deployed" while H1+H2 was actually active in the loaded profile.
"""
import json
import re
import sys
from pathlib import Path

# Match assignments like:
#   "strategy": "Regime-Adaptive DCA V15 (MEGA V2)"
#   "bot_name": "V15_PROD"
# inside source files. We flag string literals that are not derived from cfg.*
HARDCODE_PATTERN = re.compile(
    r"['\"](strategy|bot_name|exchange|profile_name)['\"]\s*:\s*['\"]([^'\"]+)['\"]",
)
# Heuristic markers indicating the value is dynamic (NOT hardcoded).
DYNAMIC_MARKERS = ['cfg.', 'self.cfg', 'config.', 'profile[', 'getattr(']

# Internal codenames that should NEVER appear as constants in identity strings.
SUSPICIOUS_CODENAMES = [
    'MEGA V2', 'MEGA_V2', 'V15 MEGA', 'H1+H2', 'V37 Champion',
    'V37 Global Optimum', 'Diamond Hands', 'Regime-Adaptive',
    'rs14_xp15', 'Champion',
]


def is_dynamic_context(text: str, match_pos: int) -> bool:
    """Look at the surrounding 200 chars; if any dynamic marker present, treat as dynamic."""
    window = text[max(0, match_pos-200):match_pos+200]
    return any(m in window for m in DYNAMIC_MARKERS)


def scan(root: Path) -> dict:
    skip_dirs = {'__pycache__', '.git', 'node_modules', '.venv', 'venv',
                 'archive', 'tests', 'data', 'output', 'results'}
    issues = []
    for py in root.rglob("*.py"):
        if any(part in skip_dirs for part in py.parts):
            continue
        try:
            text = py.read_text(errors='ignore')
        except Exception:
            continue
        for m in HARDCODE_PATTERN.finditer(text):
            field, value = m.group(1), m.group(2)
            line_no = text[:m.start()].count('\n') + 1
            ctx = text.split('\n')[line_no-1].strip()[:160]
            # Skip obvious non-issues: variable refs like {label}, {{...}}
            if '{' in value or '}' in value or '%s' in value or '%(' in value:
                continue
            severity = '⚠️ WARN'
            reason = 'String literal assigned to identity field'
            for codename in SUSPICIOUS_CODENAMES:
                if codename.lower() in value.lower():
                    severity = '🔴 CRITICAL'
                    reason = f"Internal codename '{codename}' hardcoded in identity"
                    break
            # Lower severity if the surrounding code looks like fallback/default
            if 'default' in ctx.lower() or 'placeholder' in ctx.lower() or 'unknown' in ctx.lower():
                severity = '✅ OK (fallback)'
                continue
            issues.append({
                'file': str(py.relative_to(root)),
                'line': line_no,
                'field': field,
                'value': value,
                'severity': severity,
                'reason': reason,
                'context': ctx,
            })
    issues.sort(key=lambda x: (
        0 if 'CRITICAL' in x['severity'] else 1,
        x['file'],
    ))
    return {
        'issue_count': len(issues),
        'critical_count': sum(1 for i in issues if 'CRITICAL' in i['severity']),
        'warn_count': sum(1 for i in issues if 'WARN' in i['severity']),
        'issues': issues,
    }


def print_human(rep: dict):
    print("=" * 78)
    print("Identity Anti-Hardcode Audit — dimension 4.5.2")
    print("=" * 78)
    print()
    print(f"Issues: {rep['issue_count']}  "
          f"({rep['critical_count']} 🔴 CRITICAL, {rep['warn_count']} ⚠️ WARN)")
    if rep['issues']:
        print()
        for i in rep['issues'][:30]:
            print(f"  {i['severity']}  {i['field']}=\"{i['value']}\"")
            print(f"      → {i['file']}:{i['line']}")
            print(f"      → {i['reason']}")
        if len(rep['issues']) > 30:
            print(f"  ... +{len(rep['issues'])-30} more (see JSON output)")
    print()
    print("Recommendation: identity.strategy must be derived from cfg fields, "
          "NOT a constant string. See SKILL.md dimension 4.5.2 for fix template.")


def main():
    root = Path(sys.argv[1] if len(sys.argv) > 1 else '.')
    if not root.exists():
        print(f"Path not found: {root}", file=sys.stderr)
        sys.exit(2)
    rep = scan(root)
    print_human(rep)
    if '--json' in sys.argv:
        print(json.dumps(rep, indent=2))
    if rep['critical_count'] > 0:
        sys.exit(2)
    if rep['warn_count'] > 0:
        sys.exit(1)
    sys.exit(0)


if __name__ == '__main__':
    main()
