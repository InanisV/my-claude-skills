---
name: git-cleanup
description: >
  Git workspace management — classify uncommitted files, update .gitignore,
  write clear commit messages, and keep the working tree clean. Use this skill
  whenever the user mentions "git", "commit", "uncommitted files", "working tree",
  "untracked", ".gitignore", "clean up the repo", "what needs to be committed",
  or any variation of "check/handle/process uncommitted changes". Also trigger
  when you notice untracked or modified files after completing a task and want
  to tidy up before finishing. This skill is about the LOCAL working tree —
  not about branches, PRs, merge conflicts, or remote operations.
---

# Git Workspace Cleanup

You are a Git workspace manager. Your job is to keep the repository's working tree
clean by classifying changes, updating ignore rules, and making well-structured commits.

## When to use this skill

- User says "commit", "clean up", "what changed", "uncommitted files", etc.
- After completing a coding task, before reporting done — check if there are
  uncommitted artifacts that should be committed or ignored
- User uploads or generates files and you want to make sure nothing is left dangling

## Workflow

### Step 1: Assess the workspace

Run these commands to understand the current state:

```bash
git status                    # overview (never use -uall on large repos)
git diff --stat               # modified tracked files
git log --oneline -5          # recent commits for message style reference
```

### Step 2: Classify every file

For each untracked or modified file, decide one of:

| Classification | When to use | Action |
|---|---|---|
| **commit** | Source code, scripts, config, small data/results that are part of the project | `git add <file>` |
| **ignore** | Auto-generated output (HTML reports, large binaries, build artifacts, caches) | Add pattern to `.gitignore` |
| **ask user** | Ambiguous files — could go either way (e.g., notebooks, large CSVs, .env-like files) | Present the file with a one-line explanation and ask |

Classification heuristics:

- `.py`, `.js`, `.ts`, `.go`, `.rs`, `.sh`, `.md`, `.yaml`, `.json` (small) → **commit**
- `*.html` (auto-generated reports/dashboards), `*.csv` (large data), `*.pkl`, `*.db` → **ignore**
- `__pycache__/`, `node_modules/`, `.venv/`, `dist/`, `build/` → **ignore**
- `.env`, credentials, API keys → **never commit**, warn the user
- JSON results under 10KB that document important experiments → **commit**
- JSON/CSV results over 100KB → **ignore**

When in doubt, ask. It's better to confirm than to silently ignore something important
or commit something that shouldn't be tracked.

### Step 3: Update .gitignore if needed

If you're adding ignore patterns:

1. Read the existing `.gitignore` first
2. Check if a pattern already covers the file
3. Add new patterns grouped with a comment explaining what they are
4. Place the new patterns near related existing patterns

Example:
```gitignore
# Auto-generated backtest HTML reports
reports/adaptive_*.html
reports/backtest_*.html
```

### Step 4: Stage and commit

Group related changes into logical commits. Don't lump unrelated changes together.

**Commit message format** — follow the project's existing style. If there's no clear
style, use conventional commits:

```
<type>: <short description>

<optional body explaining why, not what>

Co-Authored-By: ...
```

Types: `feat`, `fix`, `chore`, `docs`, `refactor`, `test`, `perf`

Good commit messages explain the **why**:
- "fix: adaptive vol baseline — enable signals in low-vol markets" ✓
- "update files" ✗

Always use a HEREDOC for multi-line messages:
```bash
git commit -m "$(cat <<'EOF'
type: short description

Body explaining context and reasoning.

Co-Authored-By: ...
EOF
)"
```

### Step 5: Verify

Run `git status` after committing to confirm the working tree is clean.
If there are still untracked files that should be ignored, go back to step 3.

## Important rules

- **Never** commit files that likely contain secrets (`.env`, `credentials.json`,
  API keys, private keys). Warn the user if they ask you to.
- **Never** use `git add .` or `git add -A` — always add specific files by name.
  This prevents accidentally staging secrets or large binaries.
- **Never** use destructive commands (`git reset --hard`, `git clean -f`) unless
  the user explicitly asks. Even then, double-check.
- **Never** amend commits unless the user explicitly asks — create new commits.
- **Never** skip hooks (`--no-verify`) unless the user explicitly asks.
- Stage files by name, not by wildcard, especially in repos with sensitive data.
- When the working tree is already clean, just say so — don't create empty commits.

## Presenting results

After cleanup, give a concise summary:

```
✅ Committed: 3 files (feat: add adaptive settlement scripts)
🚫 Ignored: 8 HTML reports (added to .gitignore)
⚠️ Skipped: credentials.json (contains secrets)
Working tree clean.
```

Don't over-explain. The user can run `git log` if they want details.
