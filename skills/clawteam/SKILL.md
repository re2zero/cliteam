---
name: ClawTeam Multi-Agent Coordination
description: >
  Use when the user asks to "create a team", "spawn agents", "assign tasks",
  "coordinate multiple agents", "check team status", "view kanban board",
  "send messages between agents", "manage team tasks", "monitor team progress",
  or mentions "clawteam", "multi-agent coordination", "team collaboration",
  "agent inbox", "task board", "spawn worker". Also trigger when the task is
  complex enough to benefit from splitting into subtasks and delegating to
  multiple agents, or when work scope exceeds what a single agent can handle.
version: 0.5.0
---

# ClawTeam Multi-Agent Coordination

ClawTeam is a CLI tool for coordinating multiple AI agents as a team. Operations
are via `clawteam` CLI, data in `~/.clawteam/`.

## Core Concepts

- **Teams** — Named agent groups with one leader + workers
- **Inbox** — File-based message queue. `receive` is destructive; `peek` is not
- **Tasks** — Shared board: `pending` → `in_progress` → `completed` / `blocked`, with dependencies
- **Profiles** — Reusable client/provider/runtime configs (`clawteam profile wizard`)
- **Context** — Git/worktree-aware tools for overlap checks and prompt injection

## Two Modes

### Mode 1: Launch (recommended for automation)

Use when the task matches a known template, or when the user wants a fully
automated team where the leader coordinates without manual intervention.

```bash
# List available templates
clawteam template list

# Launch from template — leader + all workers are spawned automatically
clawteam launch software-dev -g "Build a REST API with auth"
clawteam launch code-review -g "Review the auth module changes"
clawteam launch research-paper -g "Survey LLM agent architectures"
clawteam launch hedge-fund -g "Analyze AAPL, TSLA, NVDA"
clawteam launch strategy-room -g "Plan migration from monolith to microservices"

# Monitor progress
clawteam board show <team>
tmux attach -t clawteam-<team>
```

Each agent (including leader) runs as an independent process in tmux.
The leader automatically monitors inbox, assigns work, and shuts down workers.

### Mode 2: Manual spawn

Use when the task requires dynamic orchestration that doesn't fit any template.
The AI session acts as leader and manually drives the workflow.

```bash
export CLAWTEAM_AGENT_ID="leader-001"
export CLAWTEAM_AGENT_NAME="leader"
export CLAWTEAM_AGENT_TYPE="leader"

clawteam team spawn-team my-team -d "Project team" -n leader
clawteam task create my-team "Design system" -o leader
clawteam task create my-team "Implement feature" -o worker1
clawteam spawn --team my-team --agent-name worker1 --task "Implement feature"
clawteam board show my-team
```

For non-default providers: `clawteam profile wizard` then `clawteam spawn --profile <name> ...`.

### How to choose

- Task fits a template → **Mode 1 (launch)** — fully automated, hands-off
- Task needs custom roles/tasks → **Mode 2 (manual)** — but spawn an automated
  leader process via `clawteam spawn --agent-type leader` instead of being the
  leader yourself, so the team runs autonomously

## Key Gotchas

- `inbox receive` **consumes** messages — use `peek` for non-destructive reads
- Completing a task **auto-unblocks** dependent tasks
- Workers should **keep polling** tasks/inbox after their first task (Worker Loop Protocol)
- Leader should **keep polling** inbox/board (Leader Loop Protocol)
- `clawteam spawn` defaults: auto backend (wsh > tmux > subprocess), git worktree, skip-permissions
- `task wait` includes idle watchdog that auto-kills and respawns stalled workers
- Use `--profile` for non-default providers instead of manual env vars
- All commands support `--json` (place before subcommand): `clawteam --json task list my-team`

## Additional Resources

- **`references/data-model.md`** — Task statuses, message types, file storage layout, env vars
- **`references/workflows.md`** — Join protocol, plan approval, graceful shutdown, monitoring
