---
name: session-memory
description: |
  跨会话记忆系统 — 在对话之间持久化项目上下文、关键决策和经验教训。

  这个 skill 是 Claude 的"长期记忆"。每次新会话开始时自动加载历史上下文，
  每次完成重要工作后自动保存新记忆。这样无论开多少个新会话，Claude 都能记住
  之前做过什么、决定了什么、学到了什么。

  触发时机（非常重要 — 宁可多触发也不要漏触发）：
  - 每个新会话的第一条消息（无论内容是什么）— 先加载记忆再干活
  - 用户提到之前的工作："上次"、"之前"、"继续"、"还记得吗"、"我们不是做过"
  - 用户开始新的重大任务或项目迭代（需要保存上下文）
  - 会话即将结束、任务完成时（需要保存新记忆）
  - 用户说"记住"、"别忘了"、"下次记得"
  - 任何涉及跨会话上下文的场景

  如果不确定是否需要触发，就触发。加载记忆的成本很低，但丢失上下文的代价很高。
---

# Session Memory — 跨会话记忆系统

## 设计理念

人类合作者不会每天早上把昨天的工作全忘了。这个 skill 让 Claude 也做到这一点。
记忆存储在用户的工作目录中，跨会话持久化，格式是人类可读的 Markdown。

## 记忆存储位置

记忆文件存放在用户工作目录下的 `.memory/` 文件夹中：

```
<workspace>/.memory/
├── MEMORY.md          # 主记忆文件（合并视图，只在加载时重建）
├── entries/           # 各 session 的独立记忆条目（追加写入，永不覆写）
│   └── <timestamp>-<session-short-id>.md
├── archive/           # 归档（已完成的项目记忆）
│   └── <project>-archive.md
└── snapshots/         # 重要节点快照（可选）
```

其中 `<workspace>` 是用户挂载的工作目录（通常是 `/sessions/*/mnt/my-claude-skills` 或类似路径）。

### 并发安全设计

多个 session 可能同时运行并产生记忆。为避免互相覆盖，采用"各写各的，统一合并"策略：

- **写入时**：每个 session 只往 `entries/` 目录追加自己的 `.md` 文件，文件名带时间戳+随机后缀，天然不冲突
- **读取时**：加载 MEMORY.md 作为基线，再扫描 `entries/` 目录获取最新条目，合并成完整视图
- **合并时**：通过 lock 文件防止两个 session 同时合并

**Lock 机制**：合并前检查 `.memory/.merge-lock` 文件。如果存在且创建时间 < 120 秒，说明另一个 session 正在合并，跳过合并步骤，直接读取现有 MEMORY.md + 未合并的 entries 建立上下文即可。如果 lock 文件超过 120 秒（可能是上次合并崩溃残留），删除它重新获取。

```bash
# 获取 lock（在合并前执行）
LOCK_FILE="<workspace>/.memory/.merge-lock"
if [ -f "$LOCK_FILE" ]; then
  LOCK_AGE=$(( $(date +%s) - $(stat -c %Y "$LOCK_FILE" 2>/dev/null || echo 0) ))
  if [ "$LOCK_AGE" -lt 120 ]; then
    echo "SKIP_MERGE"  # 另一个 session 正在合并，跳过
  else
    rm -f "$LOCK_FILE"  # 过期锁，清除
  fi
fi
echo $$ > "$LOCK_FILE"  # 写入当前进程 PID

# 合并完成后释放 lock
rm -f "$LOCK_FILE"
```

这样即使 5 个 session 同时在跑，各自产生的记忆也不会互相干扰。

## 核心工作流

### Phase 1: 会话开始 — 加载记忆（含合并）

每个新会话的第一件事，在做任何其他工作之前：

1. 如果 `.memory/` 目录不存在，运行初始化脚本创建它（见下方），然后跳到步骤 6
2. 读取 `.memory/MEMORY.md` 全部内容
3. 扫描 `.memory/entries/` 目录（不含 `merged/` 子目录），列出所有 `.md` 文件
4. **如果 entries/ 为空**：直接用 MEMORY.md 建立上下文，跳到步骤 6
5. **如果 entries/ 有未合并条目**：尝试合并
   a. 先检查 lock（见上方并发安全设计）。拿不到 lock → 跳过合并，直接读 MEMORY.md + entries 原文建立上下文
   b. 拿到 lock → 按时间戳排序读取所有 entry
   c. **合并规则**：
      - MEMORY.md 是"基线真相"，用户可能手动编辑过它，尊重其内容
      - 新的 session 摘要 → 插入 `## Recent Sessions` 顶部
      - 新的决策/经验 → 追加到对应 section
      - 项目状态更新 → 只更新明确提到的字段，不碰用户没提到的字段
      - 如果 entry 内容和 MEMORY.md 已有内容明显重复（同一个日期、同一个事件），跳过不重复添加
   d. **条目数量上限**：如果待合并的 entries 超过 15 个，只合并最新的 15 个，剩余的直接移入 `entries/merged/`（避免上下文爆炸）
   e. 写回 MEMORY.md，将已处理的 entries 移入 `entries/merged/`
   f. 释放 lock
6. **自动精简检查**：如果 MEMORY.md 超过 200 行，执行精简（见下方"自动精简"章节）
7. 在内心建立上下文，然后开始处理用户的实际请求

这一步是静默的 — 不需要告诉用户"我在加载记忆"，直接做就好。
但如果加载到了和当前任务高度相关的上下文，可以自然地提一句：
"上次我们把 V40 的回测跑完了，夏普从 2.1 提到了 2.8，你是想继续优化还是..."

合并逻辑的关键原则：
- **宁可重复也不遗漏** — 不确定某条 entry 是否已在 MEMORY.md 中，就加进去
- **尊重用户编辑** — MEMORY.md 是用户可见可编辑的文件，用户的手动修改优先级最高
- **跳过合并不是灾难** — 拿不到 lock 时，直接读 MEMORY.md + entries 原文也能建立完整上下文，只是 MEMORY.md 文件本身没更新而已，下次别的 session 启动时会补上

### Phase 2: 工作过程中 — 识别值得记忆的信息

在正常工作过程中，留意以下类型的信息：

**必须记录的：**
- 项目版本演进（V7 → V16 → V40 等）
- 关键架构/策略决策及其原因
- 回测/实验结果（量化数据）
- 发现的 bug 和解决方案
- 用户的偏好和工作习惯

**值得记录的：**
- 尝试过但放弃的方案（避免重复踩坑）
- 待办事项和下一步计划
- 重要的文件路径和项目结构
- 外部依赖和环境配置

**不需要记录的：**
- 日常闲聊
- 一次性的简单问答
- 已经被后续决策覆盖的旧信息

### Phase 3: 任务完成 — 保存新记忆（追加 entry，不直接改 MEMORY.md）

当一个重要任务或工作阶段完成时，**往 `entries/` 目录追加一个新文件**，而不是直接修改 MEMORY.md：

1. 生成文件名：`entries/<YYYYMMDD-HHmmss>-<6位随机hex>.md`
   - 随机后缀用 `$(head -c 3 /dev/urandom | xxd -p)` 生成，彻底消除文件名碰撞
   - 例如：`entries/20260321-153042-a7f3b2.md`
2. 文件内容用以下格式：

```markdown
---
timestamp: 2026-03-21T15:30:00
session: <从会话主题或当前任务推断的简短描述，如"V42回测优化">
type: session-end  # 或 decision / learning / milestone
---
<!-- Session 自我标识：不需要知道精确的 session ID。
     用当前任务的自然语言描述即可（如"分析实盘亏损"），
     目的是让下次合并时能区分不同来源，不需要机器精确匹配。 -->

## Session Summary
- **Goal**: 这次做了什么
- **Outcome**: 结果如何
- **Key changes**: 关键改动

## Project Updates
- [项目名]: [状态变化、版本变化、新数据等]

## Decisions (if any)
- [决策及原因]

## Learnings (if any)
- [经验教训]

## Next Steps
- [下一步计划]
```

3. 写入文件即完成，不需要读写 MEMORY.md（避免并发冲突）

保存时机（不需要用户提醒）：
- 完成了一个重大任务（回测跑完、新版本部署、架构重构等）
- 会话即将结束（用户说再见、长时间没有新消息）
- 做出了重要决策
- 发现了重要的 bug 或解决方案

这种设计的好处：10 个 session 同时往 `entries/` 写文件也不会冲突，因为每个文件名都是唯一的。合并只在下次某个 session 启动时才发生，那时只有一个 session 在做这件事。

## MEMORY.md 格式

```markdown
# Session Memory
> Last updated: 2026-03-21 by session xxx

## Active Projects

### [项目名称]
- **Status**: [进行中/暂停/待验证]
- **Current version**: V40
- **Key files**: `src/bot.py`, `config/settings.py`
- **Recent progress**: 简要描述最近进展
- **Next steps**: 下一步计划
- **Open questions**: 待解决的问题

## Key Decisions

### [日期] [决策标题]
- **Context**: 为什么需要这个决策
- **Decision**: 决定了什么
- **Rationale**: 为什么这样决定
- **Result**: 结果如何（如果已知）

## Learnings

### [日期] [经验标题]
- **What happened**: 发生了什么
- **Lesson**: 学到了什么
- **Action**: 以后怎么做

## User Preferences
- [用户的工作偏好、沟通风格、常用工具等]

## Recent Sessions

### [日期] [会话标题]
- **Goal**: 这次会话要做什么
- **Outcome**: 做到了什么
- **Key changes**: 关键改动
- **Next**: 下次要做什么
```

## 自动精简

当 MEMORY.md 超过 200 行时，在 Phase 1 合并后自动执行精简：

1. **归档已完成项目**：`Status` 为"已完成"或"已放弃"的项目，整体移入 `archive/<project-name>-archive.md`，在 Active Projects 中删除
2. **裁剪 Recent Sessions**：只保留最近 8 条，更早的移入 archive
3. **合并同类决策**：如果同一个主题有多条迭代决策（如 V7→V16→V40 的止盈策略调整），合并为一条保留最终结论，旧版本的推理过程移入 archive
4. **淘汰过时经验**：已被后续决策明确覆盖的 Learnings（如"减仓不是好方案"在采用新方案后已不再需要提醒），移入 archive
5. 精简后在 `> Last updated` 行注明 `(compacted)`

归档不是删除 — 所有内容仍然可以在 `archive/` 中找到。精简的目标是让主文件始终聚焦于"下一个 session 需要知道什么"。

## 长会话中途刷新

如果一个会话持续时间很长（超过 20 轮对话或 1 小时以上），在开始一个新的重大子任务前，可以快速扫描一下 `entries/` 目录看看有没有其他 session 写入的新条目。不需要做完整合并，只需要读一下新 entry 的内容，了解其他 session 的最新进展，避免基于过时信息做决策。

这不是强制的，只在以下情况下值得做：
- 用户提到了"另一个会话"或"那边"的进展
- 当前任务依赖于可能在其他 session 中被修改的状态（如策略版本号、回测参数）
- 你注意到文件在你读取后被修改了（编辑工具会报错提示）

## 写记忆的原则

1. **压缩但不丢信息** — 记录结论和数据，不记录过程细节。"夏普从 2.1 提升到 2.8" 比 "跑了三次回测调了很多参数最后效果变好了" 有用得多。

2. **面向未来的自己写** — 想象三天后的一个新 Claude 会话读到这段记忆，它需要知道什么才能无缝接手？

3. **量化优先** — 能用数字说的不用文字。回测结果、性能指标、错误率等尽量带具体数值。

4. **保持 MEMORY.md 精简** — 主文件控制在 200 行以内。超过的内容归档到 `archive/` 目录。活跃项目保留 3-5 个，已完成的移入归档。

5. **用中文** — 用户习惯中文交流，记忆也用中文写，保持一致性。

## 初始化

如果 `.memory/` 目录不存在，创建它并初始化 MEMORY.md：

```bash
mkdir -p <workspace>/.memory/{archive,entries/merged,snapshots}
cat > <workspace>/.memory/MEMORY.md << 'HEREDOC'
# Session Memory
> Last updated: [date] — initialized

## Active Projects
_No projects yet. Will be populated as we work together._

## Key Decisions
_No decisions recorded yet._

## Learnings
_No learnings recorded yet._

## User Preferences
_Will be discovered through collaboration._

## Recent Sessions
_No previous sessions recorded._
HEREDOC
```

## 与其他 Skill 的协作

这个记忆系统应该和其他 skill 自然配合：
- **dev-planner** 完成开发后，Phase 8 复盘的结论应该写入记忆
- **comparison-dashboard** 生成对比结果后，关键发现写入记忆
- **git-cleanup** 提交代码后，commit 摘要可以作为会话记录的一部分

## 注意事项

- 不要在记忆中存储敏感信息（API keys、密码等）
- 记忆文件是纯文本，用户可以随时查看和编辑。如果发现 MEMORY.md 的内容和你预期不一样（比如某些条目被删了或改了），那是用户手动编辑的结果，以用户的版本为准
- 如果用户说"忘掉 X"或"删除这条记忆"，照做并从 MEMORY.md 和相关 entries 中移除
- 记忆加载失败不应阻塞正常工作 — 提示用户但继续执行任务
- **工作区绑定**：记忆存储在用户选择的工作目录中。如果用户换了工作目录，记忆不会自动跟随。遇到这种情况可以提醒用户把 `.memory/` 文件夹复制到新目录
- **entries/ 清理**：`entries/merged/` 目录中的文件是已合并的历史条目，可以安全删除以节省空间。但建议至少保留 30 天，以防需要回溯
- **同一会话多次保存**：一个长会话中可以写多个 entry（比如完成了两个不同的重大任务），每次用不同的文件名和时间戳就行
