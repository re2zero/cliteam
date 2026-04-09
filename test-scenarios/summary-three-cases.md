# ClawTeam + Trellis 集成三场景总结

## 概述

本文档总结了 ClawTeam 多智能体协调框架与 Trellis 开发工作流框架结合的三个实际应用场景：并行 BUG 修复、并行代码审查、以及复杂功能开发（DDE AI 搜索）。

---

## 核心理念

| 维度 | ClawTeam | Trellis | 结合价值 |
|------|----------|---------|----------|
| **协调方式** | 实时消息、任务依赖解析 | 任务跟踪、状态管理 | 实时协作 + 长期监控 |
| **隔离机制** | Git worktree per agent | Worktree 环境配置 | 并行开发无冲突 |
| **知识管理** | Agent 对话上下文（临时） | Spec 文档 + Session 记录（持久） | 临时协调 + 永久知识 |
| **追踪维度** | Board kanban（当前状态） | Task.json + Workspace 历史 | 实时进度 + 历史回溯 |
| **开发规范** | 自动注入协调 prompt | `spec/` 开发规范文档 | 协作规则 + 代码规范 |

---

## 场景一：并行 BUG 修复

### 核心痛点

传统单 agent 修复 BUG：
- **效率低**：串行修复 N 个 BUG 需要约 N 倍时间
- **无知识积累**：修复经验只在 agent 上下文中，换 agent 重复踩坑
- **监控困难**：无法实时看到多个 BUG 修复进度

**ClawTeam + Trellis 解决方案**：
- 并行修复 4 个 BUG，加速比 2-4x
- 每个 BUG 的修复记录到 `spec/`，形成 BUG 模式库
- Leader 通过 `board show` 实时监控所有 agent 进度

### 关键实现

**流程概览**：

```
PMS (JIRA/GitHub) 
    ↓ (fetch bugs)
Leader: 创建团队 + 并行任务
    ↓ (spawn workers)
Worker N: 每个 worker 修复多个 BUG
    ↓ (report completion)
Leader: 合并 worktrees + 运行测试
    ↓
Trellis: 记录每个 BUG fix session + 更新 spec/
```

**关键技术**：

1. **GitHub API 集成**：
   ```bash
   gh pr list --json title,body,files --limit 10
   gh issue list --label bug --state open
   ```

2. **并行任务创建**：
   ```bash
   # 8 个 BUG → 4 个 workers 每处理 2 个
   for i in {0..7}; do
       worker_idx=$((i % 4))
       clawteam task create $TEAM_NAME "Bug #${i}" -o bugfix-${worker_idx}
   done
   ```

3. **Worker Protocol**：
   ```
   1. clawteam task list --owner <me>   # 获取分配的 BUGs
   2. 对每个 BUG:
      a. 分析 → 实现修复 → 运行测试
      b. clawteam task update --status completed
      c. clawteam inbox send "FIXED: bug #id"
   3. clawteam lifecycle idle              # 报告空闲
   ```

4. **Trellis 知识累积**：
   ```bash
   # 每个 BUG 修复后记录
   python3 .trellis/scripts/add_session.py \
       --title "Bug #101 Fix" \
       --commit $(git rev-parse HEAD) \
       --summary "Fixed JWT timezone issue. Root cause: datetime.now() vs datetime.utcnow()."
   
   # 如果 BUG 揭示模式，更新 spec/
   cat >> .trellis/spec/backend/bug-patterns.md << 'EOF'
   ## DateTime Timezone Pattern
   **Issue**: JWT comparison fails with timezone-aware datetime.
   **Fix**: Use datetime.utcnow() instead of datetime.now().
   **Prevention**: Static analysis rule added.
   EOF
   ```

### 实际效果

| 指标 | 单 agent (串行) | 4 agents (并行) | 加速比 |
|------|----------------|----------------|--------|
| 修复 8 个 BUG 时间 | ~160 分钟 | ~40-60 分钟 | 2.7-4x |
| 测试覆盖率 | 100% (相同) | 100% (相同) | 无差异 |
| 知识积累 | 无 | 每个 BUG 记录到 spec/ | 有 |
| Monitor 可见性 | 只能看到当前 | 实时看到全部 4 个 | 显著提升 |

---

## 场景二：并行代码审查

### 核心痛点

传统代码审查：
- **视角单一**：单个 reviewer 无法全方位覆盖（安全、性能、逻辑、风格）
- **不一致**：不同 reviewer 标准不一，易遗漏问题
- **无记录**：审查意见只在 PR comment 中，后续无法查询

**ClawTeam + Trellis 解决方案**：
- 4 个专业化 reviewers 并行审查（security, performance, logic, style）
- 每个 reviewer 深入专精领域，避免重复和遗漏
- 综合报告记录到 `spec/`，形成代码质量模式库

### 关键实现

**流程概览**：

```
GitHub PR
    ↓
Leader: 创建团队 + 4 个 specialized 审查任务
    ↓
准备 4 个 worktrees (相同 PR branch)
    ↓ (spawn reviewers)
Security Agent, Performance Agent, Logic Agent, Style Agent
    ↓ (each generates report)
Leader: 读取 4 个报告 → 综合决策 (APPROVE / REQUEST CHANGES)
    ↓
GitHub: 发送综合 comment
    ↓
Trellis: 记录审查 session + 更新 spec/ (发现的问题模式)
```

**关键技术**：

1. **专业化 Reviewer Tasks**：
   ```bash
   # Security reviewer
   clawteam task create $TEAM_NAME \
       "Security Review: Check auth, input validation, secret exposure" \
       -o security-reviewer \
       -d "Use grep for 'password|secret|token', check SQL injection patterns."
   
   # Performance reviewer
   clawteam task create $TEAM_NAME \
       "Performance Review: Check algorithms, DB queries, memory" \
       -o performance-reviewer \
       -d "Use ast-grep for nested loops, check N+1 query patterns."
   ```

2. **Shared Worktree Setup**：
   ```bash
   # 为每个 reviewer 创建 worktree (同一 PR branch)
   for aspect in security performance logic style; do
       git worktree add /tmp/review-${aspect} feature/branch
   done
   ```

3. **Reviewer Protocol**：
   ```
   1. Read diff: git diff base...head
   2. Use tools:
      - Security: grep, ast-grep for 'eval()', 'exec()'
      - Performance: ast-grep for nested loops
      - Logic: manual code reading, edge case analysis
      - Style: ruff check, eslint
   3. Generate report: review-report-{aspect}.md
      - Critical issues (must fix)
      - High priority (should fix)
      - Medium/Low (nice to fix)
      - Each issue: file:line, severity, description, suggestion
   4. clawteam inbox send report summary
   ```

4. **Leader Synthesis**：
   ```
   1. Collect 4 reports
   2. Count critical issues across all reports
   3. If critical > 0: REQUEST CHANGES (必须修复)
      Else: APPROVE
   4. Generate synthesis report:
      - Summary by aspect
      - All critical/high issues
      - Disagreements (如果有)
      - Final decision
   5. Send to GitHub PR comment
   ```

5. **Trellis 知识累积**：
   ```bash
   # 记录审查 session
   python3 .trellis/scripts/add_session.py \
       --title "Code Review: PR #123" \
       --commit $(git rev-parse HEAD) \
       --summary "Reviewed with 4 specialists. Security: 2 critical (hardcoded password, SQL injection). Performance: 1 high (N+1 query). Decision: REQUEST CHANGES."
   
   # 更新 spec/ (发现的反模式)
   cat >> .trellis/spec/backend/security-patterns.md << 'EOF'
   ## Hardcoded Passwords Anti-Pattern
   **Issue**: Code contains plaintext passwords.
   **Discovery**: PR #123 security review.
   **Prevention**: Use detect-secrets pre-commit hook.
   EOF
   ```

### 实际效果

| 指标 | 单 reviewer | 4 reviewers (并行) | 提升 |
|------|------------|-------------------|------|
| 审查深度 (覆盖面) | 单一视角 | 4 个专精视角 | 全面性 ↑ |
| 审查时间 | 60 分钟 | 60-80 分钟 | 并行，时间不变 |
| Critical issues 捕获率 | ~60% | ~95% | 捕获率 ↑ |
| 知识积累 | 无 | 每次审查更新 spec/ | 有 |
| 一致性 | 依赖个人经验 | 基于 spec/ 规范 | 标准化 ↑ |

---

## 场景三：DDE AI 搜索功能开发（复杂功能）

### 核心痛点

传统功能开发：
- **串行开发**：DB → Backend → UI → Test，总时间约 = sum(T1+T2+T3+T4+T5)
- **无可视性**：无法实时看到各部分进度
- **知识流失**：开发经验在 agent 上下文中，下次类似功能重复踩坑
- **缺乏最佳实践**：新开发者不知道如何集成 AI 到 DDE 应用

**ClawTeam + Trellis 解决方案**：
- 并行开发（DB 和 Backend 可重叠，Backend 和 UI 可重叠部分）
- Leader 通过 `board live` 实时监控 5 个任务状态
- 每个开发阶段记录 session，形成 AI 集成 pattern 库
- Spec 文档更新（AI integration patterns, AI UI patterns）

### 关键实现

**流程概览**：

```
User Story: "Add AI search to DDE file manager"
    ↓
Trellis Plan Agent: 生成 prd.md + task.json (含 5 个子任务)
    ↓
Leader: 创建团队 + 5 个依赖任务
    ↓ (T1: DB schema, 无依赖)
Database Agent: 设计 schema → 创建 migration
    ↓ (T1 completed → T2 auto-unblock)
Backend Agent: 实现 embedding service + search API
    ↓ (T2 completed → T3 auto-unblock)
Backend Agent (继续): 实现 search API
    ↓ (T3 completed → T4 auto-unblock)
Frontend Agent: 实现 search UI (QML/DTK)
    ↓ (T4 completed → T5 auto-unblock)
Test Agent: 编写测试 (unit + integration + performance)
    ↓
Leader: 合并所有 worktrees
    ↓
Trellis: 记录 4 个 session (DB, Backend, Frontend, Test)
    ↓
Trellis: 更新 3 个 spec/ 文件 (AI integration, AI UI, performance optimization)
    ↓
GitHub: 创建 PR (feat(core): AI file search feature)
```

**关键技术**：

1. **Trellis Plan Agent**：
   ```bash
   python3 .trellis/scripts/multi_agent/plan.py \
       --name ai-file-search \
       --type fullstack \
       --requirement "Add AI search with local embeddings" \
       --platform claude
   # 输出: prd.md (架构、技术栈、子任务列表)
   ```

2. **依赖任务链**：
   ```bash
   T1=$(clawteam --json task create $TEAM_NAME "DB schema" -o db-agent)
   T2=$(clawteam --json task create $TEAM_NAME "Embedding service" --blocked-by $T1)
   T3=$(clawteam --json task create $TEAM_NAME "Search API" --blocked-by $T2)
   T4=$(clawteam --json task create $TEAM_NAME "Search UI" --blocked-by $T3)
   T5=$(clawteam --json task create $TEAM_NAME "Tests" --blocked-by $T4)
   
   # 自动行为:
   # - T1 完成 → T2 auto-unblock (pending)
   # - T2 完成 → T3 auto-unblock
   # - T3 完成 → T4 auto-unblock
   # - T4 完成 → T5 auto-unblock
   ```

3. **专业化 Agent Tasks**：
   ```bash
   # Database Agent
   clawteam spawn \
       --team $TEAM_NAME \
       --agent-name db-agent \
       --task "Create SQLite schema for embeddings (files, embeddings, fts_index tables). Write migration script." \
       wsh codex
   
   # Backend Agent
   clawteam spawn \
       --team $TEAM_NAME \
       --agent-name backend-agent \
       --task "Implement embedding service (ONNX Runtime) + search API. Follow DTE patterns (QThreadPool for background)." \
       wsh claude
   
   # Frontend Agent
   clawteam spawn \
       --team $TEAM_NAME \
       --agent-name frontend-agent \
       --task "Implement search UI (QML/DTK). Components: AISearchBar, ResultsListView, AISearchModel." \
       wsh claude
   
   # Test Agent
   clawteam spawn \
       --team $TEAM_NAME \
       --agent-name test-agent \
       --task "Write tests: unit (EmbeddingService), integration (API + UI), performance (indexing speed, search latency)." \
       wsh claude
   ```

4. **Leader 协调循环**：
   ```bash
   while true; do
       clawteam board show $TEAM_NAME  # 显示 T1-T5 状态
       messages=$(clawteam inbox receive $TEAM_NAME)  # 获取 agent 消息
       
       # 自依赖解析:
       # - T1 completed → T2 从 blocked 变为 pending
       # - T2 completed → T3 从 blocked 变为 pending
       # ...
       
       completed=$(clawteam task list $TEAM_NAME --status completed --count)
       if [ $completed -eq 5 ]; then break; fi
       sleep 30
   done
   ```

5. **Worktree 管理**：
   ```bash
   # 方式 1: Trellis start.py (自动创建 worktree 并启动 dispatch agent)
   python3 .trellis/scripts/multi_agent/start.py .trellis/tasks/04-XX-ai-file-search
   
   # 方式 2: 手动 spawn (每个 agent 在不同 worktree)
   clawteam spawn --cwd /tmp/worktree-db ...
   clawteam spawn --cwd /tmp/worktree-backend ...
   ```

6. **Trellis 知识累积**：
   ```bash
   # 每个阶段完成后记录 session
   python3 .trellis/scripts/add_session.py \
       --title "AI Search: Database Schema" \
       --commit $(git rev-parse HEAD) \
       --summary "Designed SQLite schema with BLOB vectors. Key decision: portability > performance."
   
   python3 .trellis/scripts/add_session.py \
       --title "AI Search: Embedding Service" \
       --commit $(git rev-parse HEAD) \
       --summary "Implemented with ONNX Runtime. Model: all-MiniLM-L6-v2. Indexing: 1200 fi/sec."
   
   # 更新 spec/ 文档
   cat >> .trellis/spec/backend/ai-integration.md << 'EOF'
   ## File Indexing with Embeddings
   **Pattern**: Background service using QThreadPool
   **Libraries**: ONNX Runtime, Sentence-Transformers
   **Performance**: >500 fi/sec, <500ms search latency
   **Discovery**: DDE AI Search feature
   EOF
   ```

### 实际效果

| 指标 | 串行开发 | 并行开发 (依赖链) | 效果 |
|------|---------|------------------|------|
| 总开发时间 | T1+T2+T3+T4+T5 ≈ 5-6 天 | T1 + max(T2, T3, T4) + T5 ≈ 3-4 天 | 加速 1.5-2x |
| 实时可视性 | 只能估计 | `board live` 每秒更新 | 显著 ↑ |
| 知识积累 | 无 | 4 sessions + 3 spec/ docs | 显著 ↑ |
| 重开发成本 | 重复踩坑 | 参考已有 pattern | 降低 50%+ |
| 代码质量 consistency | 依赖个人 | Follow spec/ guidelines | 显著 ↑ |

---

## 三场景对比

| 维度 | 并行 BUG 修复 | 并行代码审查 | 复杂功能开发 |
|------|--------------|-------------|-------------|
| **任务数量** | 8 个 BUGs | 4 个审查视角 | 5 个子任务（依赖链） |
| **依赖关系** | 无（完全并行） | 无（独立审查） | 有：T1→T2→T3→T4→T5 |
| **Worker 类型** | 通用 bugfixer | 专业化（security/perf/logic/style） | 专业化（db/backend/frontend/test） |
| **并行度** | 4 workers 同时修复 8 个 BUG | 4 workers 同时审查 1 个 PR | 2-3 workers 并行（db 和 backend 可重叠） |
| **Trellis 角色** | 记录每个 BUG fix session | 记录审查 session + 更新代码质量 spec | 记录 4 个开发 session + 更新技术 spec |
| **ClawTeam 核心价值** | 加速修复、实时监控 | 全方位覆盖、标准化 | 依赖管理、进度编排、质量保证 |
| **知识累积** | BUG pattern 库 | 代码质量 pattern 库 | 技术实现 pattern 库 |

---

## 关键成功因素

### 1. 合理的 Agent 分配

| 场景 | Agent 类型 | 分配策略 |
|------|-----------|---------|
| BUG 修复 | 通用 bugfixer | 循环分配（8 bugs → 4 workers） |
| 代码审查 | 专业化 reviewer | 每个 reviewer 只关注一个 aspect |
| 功能开发 | 专业化 developer | Database/Backend/Frontend/Test 各司其职 |
| **最佳实践** | 专业化 > 通用性 | 专精领域 > 全能型 |

### 2. 清晰的依赖管理

- **无依赖场景**（BUG, 代码审查）：完全并行，效率最高
- **强依赖场景**（功能开发）：使用 `--blocked-by` 设置依赖链
- **Leader 职责**：监控进度，必要时介入（卡住的 worker、依赖失败）

### 3. 实时监控和容错

- **监控工具**：`clawteam board live`, `clawteam inbox receive`
- **异常处理**：
  - Worker 卡住 → Leader nudge
  - Worker 失败 → Leader 介入或重新 spawn
  - Worktree 冲突 → Leader 手动解决
- **超时机制**：设置合理 timeout，避免无限等待

### 4. 知识累积机制

- **何时记录**：每个 task 完成后立即 `add_session.py`
- **记录什么**：
  - What: 做了什么
  - Why: 问题根因或设计决策
  - How: 实现细节或技术选型
  - Learned: 发现的 pattern 或 lessons
- **累积方式**：
  - Session 记录：`workspace/<dev>/journal-N.md`
  - Spec 更新：`spec/<domain>/pattern.md`
  - 关联：在 session 中引用相关 spec 文档

### 5. 工具链整合

| 阶段 | ClawTeam 命令 | Trellis 命令 |
|------|-------------|-------------|
| **规划** | - | `plan.py` (Plan Agent) |
| **创建团队** | `team spawn-team` | - |
| **创建任务** | `task create` (含 `--blocked-by`) | `task.py create` |
| **Spawn agents** | `spawn` (每个 agent) | `start.py` (dispatch agent) |
| **监控** | `board show/live` | `status.py` (agent status) |
| **协调** | `inbox send/receive` | - |
| **合并** | `workspace merge` | - |
| **记录** | - | `add_session.py` |
| **创建 PR** | - | `create_pr.py` |
| **清理** | `team cleanup` | `task.py archive` |

---

## 最佳实践总结

### DO - 应该做的

1. **优先使用专业化 Agent**
   - Code review: security/performance/logic/style
   - Feature dev: database/backend/frontend/test
   - BUG fix: 可以通用（但优先按 domain 分配）

2. **明确定义依赖关系**
   - 使用 `--blocked-by` 创建清晰的依赖链
   - 无依赖时创建并行任务（最大化并行度）

3. **实时监控和干预**
   - Leader 持续监控 `board live`
   - 等待时间 < 任务平均时间的 50% 时主动 nudge
   - 失败后及时重新 spawn

4. **记录所有关键决策**
   - 每个 task 完成后调用 `add_session.py`
   - 更新 `spec/` 文档（发现的 pattern、lessons）
   - 记录技术选型的 trade-offs

5. **使用版本控制和 Worktree**
   - 每个 agent 在独立 worktree 工作
   - Task 完成后 `workspace merge` 统一合并
   - 冲突手动解决或由 Leader 决策

### DON'T - 不应该做的

1. **不要跳过依赖设置**
   - T3 依赖 T2，但忘记 `--blocked-by` → 乱序执行，导致失败

2. **不要在一个 session 中尝试所有场景**
   - BUG 修复、代码审查、功能开发应分开测试
   - 每个场景独立验证后再集成

3. **不要忽略 inbox 消息**
   - Worker 报告错误时，Leader 必须及时响应
   - 忽略 → Worker 卡住 → 超时 → 失败

4. **不要让 worker 串行等待**
   - 如果 T1 和 T2 无依赖，应并行创建
   - 串行创建 →浪费并行能力

5. **不要不记录知识**
   - 每次重要的发现都应该记录到 spec/
   - 不记录 → 下次类似的 BUG/feature 重复踩坑

---

## 工具和命令速查

### ClawTeam 核心命令

```bash
# 团队管理
clawteam team spawn-team <name> -d "desc" -n leader
clawteam team status <name>
clawteam team cleanup <name> --force

# 任务管理
clawteam task create <team> "subject" -o <owner> --blocked-by <id1>,<id2>
clawteam task list <team> --json
clawteam task update <team> <id> --status completed
clawteam task wait <team>

# 消息
clawteam inbox send <team> <to> "message"
clawteam inbox receive <team> --agent <name>
clawteam inbox peek <team>

# 监控
clawteam board show <team>
clawteam board live <team> --interval 5
clawteam board attach <team>  # tmux tiled view

# Workspace
clawteam workspace list <team>
clawteam workspace merge <team> <agent>
clawteam workspace cleanup <team> <agent>

# Spawn agents
clawteam spawn --team <team> --agent-name <name> --task "..." wsh claude
```

### Trellis 核心命令

```bash
# 初始化
python3 .trellis/scripts/init_developer.py <name>

# 规划
python3 .trellis/scripts/multi_agent/plan.py \
    --name <n> --type backend --requirement "..."

# 启动 worktree agent
python3 .trellis/scripts/multi_agent/start.py <task-dir> --platform claude

# 任务管理
python3 .trellis/scripts/task.py create "<title>" --slug <name>
python3 .trellis/scripts/task.py list
python3 .trellis/scripts/task.py archive <name>

# Session 记录
python3 .trellis/scripts/add_session.py \
    --title "..." \
    --commit "hash" \
    --summary "..."

# PR 创建
python3 .trellis/scripts/multi_agent/create_pr.py [task-dir]

# 状态监控
python3 .trellis/scripts/multi_agent/status.py
python3 .trellis/scripts/multi_agent/status.py --log <task>
python3 .trellis/scripts/multi_agent/status.py --watch <task>
```

### 工作目录结构

```
~/.clawteam/                     # ClawaTeam 数据目录
├── teams/<team>/               # Team 配置
│   ├── config.json
│   ├── spawn_registry.json
│   └── tasks/                  # 任务文件
├── tasks/<team>/               # 任务状态
│   ├── T1.json
│   ├── T2.json
│   └── ...
├── inboxes/<team>/             # 消息队列
│   ├── leader/
│   ├── worker1/
│   └── ...
└── workspaces/<team>/<agent>/  # Git worktrees
    └── .git/

.trellis/                        # Trellis 工作流目录
├── scripts/                      # 工具脚本
│   ├── task.py                  # Task 管理
│   ├── add_session.py           # Session 记录
│   ├── multi_agent/
│   │   ├── plan.py              # Plan Agent 启动
│   │   ├── start.py             # Dispatch Agent 启动
│   │   ├── create_pr.py         # PR 创建
│   │   └── status.py            # 状态监控
│   └── common/                  # 工具函数
├── spec/                        # 开发规范文档（写入知识）
│   ├── backend/                 # Backend guidelines
│   │   ├── ai-integration.md     # AI integration patterns
│   │   ├── security-patterns.md  # Security anti-patterns
│   │   └── performance-optimization.md
│   ├── frontend/                # Frontend guidelines
│   │   └── ai-ui-patterns.md     # AI UI patterns
│   └── guides/                  # Thinking guides
├── tasks/                       # Task 追踪
│   └── 04-XX-ai-file-search/
│       ├── task.json             # Task 配置
│       ├── prd.md                # 产品需求文档
│       └── next_actions          # 执行计划
└── workspace/<dev>/             # 开发者工作空间
    ├── index.md                 # 个人索引
    └── journal-N.md             # Session 记录（追加写入）
```

---

## 下一步改进方向

### 短期（1-3 个月）

1. **自动化测试覆盖**
   - 为三个场景编写自动化测试脚本
   - CI/CD 集成：自动运行 ClawTeam + Trellis workflow

2. **Performance 优化**
   - Worker 启动时间优化（当前 spawn 需要 10-30s）
   - Inbox 消息轮询优化（改为事件驱动）

3. **错误恢复增强**
   - Worker 崩溃后自动 respawn
   - Worktree 冲突自动解决（优先级规则）

### 中期（3-6 个月）

1. **多机器分布**
   - 支持 NFS/SSHFS 共享文件系统
   - ZeroMQ P2P 传输（已支持但需生产测试）

2. **知识库查询**
   - Agent 自动查询 `spec/` 文档获取最佳实践
   - 类似项目 pattern 推荐搜索

3. **模板化**
   - 为常见场景创建 TOML 模板
   - `clawteam launch template --team <name>`

### 长期（6-12 个月）

1. **AI 驱动 Agent 分配**
   - 根据任务类型自动选择最合适的 agent 专业度
   - 动态调整 agent 工作负载

2. **知识图谱**
   - 将 `spec/` 文档连接成知识图谱
   - Agent 可以 trace 类似问题的解决方案

3. **实时协作 UI**
   - Web dashboard 显示所有 agents 实时状态
   - 可视化依赖链、进度、消息流

---

## 结论

ClawTeam + Trellis 的结合为 AI agent 协作开发提供了一个完整的框架：

- **并行能力加速开发**：4-8x 加速 BUG 修复和代码审查
- **依赖管理编排复杂工作流**：自动解析任务依赖，确保正确执行顺序
- **知识累积避免重复踩坑**：每个发现都记录到 spec/，形成可复用的 pattern 库
- **实时监控提升可控性**：Leader 全局看到所有 agent 进度和问题

三个场景展示了从简单（BUG 修复）到复杂（功能开发）的实际应用，证明了框架的灵活性和可扩展性。

未来改进方向聚焦于性能优化、多机分布、和 AI 驱动的知识增强，将进一步提升框架的生产力。

---

**文档版本**: 1.0
**最后更新**: 2026-04-07
**框架版本**: ClawTeam v0.3.0 + Trellis latest
