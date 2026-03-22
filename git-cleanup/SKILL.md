---
name: git-cleanup
description: >
  Git workspace management — classify uncommitted files, update .gitignore,
  write clear commit messages, and keep the working tree clean.

  强制触发：每次执行 git commit 之前，必须先调用此 skill 完成文件分类和清理。
  无论是用户要求 commit，还是 Claude 自己完成任务后准备 commit，都要先过这个流程。
  这是铁律，没有例外。

  也在以下场景触发：用户提到 "git"、"commit"、"提交"、"uncommitted files"、
  "working tree"、"untracked"、".gitignore"、"clean up the repo"、
  "什么还没提交"、"清理一下"，或任何涉及检查/处理未提交改动的请求。
  完成编码任务后注意到有未跟踪或已修改的文件时也要触发。

  此 skill 管理的是本地工作区 — 不涉及分支、PR、合并冲突或远程操作。
---

# Git Workspace Cleanup

You are a Git workspace manager. Your job is to keep the repository's working tree
clean by classifying changes, updating ignore rules, and making well-structured commits.

## When to use this skill

- **每次 commit 之前（强制）** — 无论谁发起的 commit（用户要求或 Claude 主动），
  都必须先跑完这个 skill 的完整流程（分类文件 → 更新 .gitignore → 分组提交）。
  直接跳过分类就 `git add` 是不允许的。这样做的原因是：不经分类就提交很容易把
  生成的 HTML 报告、大 CSV、临时文件、甚至 credentials 混进去，事后清理很麻烦。
- User says "commit", "clean up", "what changed", "uncommitted files", etc.
- After completing a coding task, before reporting done — check if there are
  uncommitted artifacts that should be committed or ignored
- User uploads or generates files and you want to make sure nothing is left dangling

## Workflow

### Step 0: Clear stale .git lock files

在执行任何 git 操作之前，先检查是否存在残留的 lock 文件。这在 Cowork 沙箱环境中
尤其常见——多个 session 并行操作同一个 repo 时，前一个 session 的 git 操作可能
留下 `index.lock` 或 `HEAD.lock`，而沙箱的 immutable 属性导致这些文件无法直接删除。

**检测**：
```bash
ls -la .git/index.lock .git/HEAD.lock 2>/dev/null
```

**如果存在 lock 文件，先尝试直接删除**：
```bash
rm -f .git/index.lock .git/HEAD.lock
```

**如果 `rm` 报 `Operation not permitted`（沙箱 immutable 保护），使用 /tmp 中转**：
```bash
# 1. 复制 .git 到可写的 /tmp
cp -r .git /tmp/git-clean

# 2. 在 /tmp 中删除 lock 文件
rm -f /tmp/git-clean/index.lock /tmp/git-clean/HEAD.lock

# 3. 后续所有 git 操作使用环境变量指向 /tmp
export GIT_DIR=/tmp/git-clean
export GIT_WORK_TREE=$(pwd)

# 4. 所有 git 操作完成后，同步回原目录（排除 lock 文件）
rsync -a /tmp/git-clean/ .git/ --exclude='*.lock'
unset GIT_DIR GIT_WORK_TREE

# 5. 清理临时目录
rm -rf /tmp/git-clean
```

**注意事项**：
- 使用 `/tmp` 中转时，所有 Step 1–5 的 git 命令都需要带 `GIT_DIR` 和 `GIT_WORK_TREE` 环境变量
- 如果 `GIT_AUTHOR_NAME` / `GIT_AUTHOR_EMAIL` 未配置，也需要一并设置（沙箱可能没有 git config）
- rsync 回写时 `--exclude='*.lock'` 防止把新产生的 lock 同步回去
- 如果没有 lock 文件，跳过此步骤，正常执行后续流程

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
| **ignore** | Auto-generated output that会持续产生 (HTML reports, build artifacts) | Add pattern to `.gitignore` |
| **delete** | 一次性垃圾文件、过期缓存、临时调试产物，留着没用还占空间 | `rm -rf <file>` |
| **ask user** | Ambiguous files — could go either way (e.g., notebooks, large CSVs, .env-like files) | Present the file with a one-line explanation and ask |

**delete vs ignore 的区别**：ignore 是"以后还会生成，加到 .gitignore 让 git 永久忽略"；
delete 是"这个文件本身就不该存在，直接删掉"。判断标准：如果文件是某个工具/流程自动
反复生成的，用 ignore；如果是一次性的临时产物或已经过期的缓存，用 delete。

Classification heuristics:

- `.py`, `.js`, `.ts`, `.go`, `.rs`, `.sh`, `.md`, `.yaml`, `.json` (small) → **commit**
- `*.html` (auto-generated reports/dashboards), `*.csv` (large data), `*.pkl`, `*.db` → **ignore**
- `__pycache__/`, `node_modules/`, `.venv/`, `dist/`, `build/` → **ignore** (会反复生成)
- `.env`, credentials, API keys → **never commit**, warn the user
- JSON results under 10KB that document important experiments → **commit**
- JSON/CSV results over 100KB → **ignore**
- `*.pyc`, `.pytest_cache/`, `.mypy_cache/`, `.ruff_cache/` → **delete** (随时可重建的缓存)
- `tmp_*`, `*.tmp`, `*.bak`, `*.swp`, `*~` → **delete** (编辑器/系统临时文件)
- `nohup.out`, `*.log` (非项目日志) → **delete** (一次性运行产物)
- 空目录、残留的 `.DS_Store`、`Thumbs.db` → **delete**

**删除前的安全规则**：
- 删除操作必须在分类表中列出并展示给用户确认，不能静默删除
- 如果不确定某个文件是否有用，归类为 **ask user** 而不是 delete
- 对于大于 10MB 的文件，单独提醒用户文件大小，确认后再删

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

### Step 3.5: Delete junk files

If any files were classified as **delete**:

1. 在分类表中向用户展示待删除列表（文件名 + 原因 + 大小）
2. 用户确认后，执行删除：`rm -rf <file-or-dir>`
3. 如果被删的文件已经在 git tracked 中，还需要 `git rm --cached` 并在 .gitignore 中加上对应 pattern 防止以后再出现

删除顺序：先删再 commit。这样 git status 更干净，commit 的 diff 也更清晰。

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
🔓 Lock cleared: .git/index.lock (via /tmp workaround)
✅ Committed: 3 files (feat: add adaptive settlement scripts)
🚫 Ignored: 8 HTML reports (added to .gitignore)
🗑️ Deleted: 12 files — __pycache__ (3), .pytest_cache (1), *.pyc (5), tmp_debug_* (3)
⚠️ Skipped: credentials.json (contains secrets)
Working tree clean.
```

Don't over-explain. The user can run `git log` if they want details.
