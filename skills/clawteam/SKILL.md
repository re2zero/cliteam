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
version: 0.4.0
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

## Quick Start

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

## Key Gotchas

- `inbox receive` **consumes** messages — use `peek` for non-destructive reads
- Completing a task **auto-unblocks** dependent tasks
- Workers should **keep polling** tasks/inbox after their first task (Worker Loop Protocol)
- `clawteam spawn` defaults: auto backend (wsh > tmux > subprocess), git worktree, skip-permissions
- `task wait` includes idle watchdog that auto-kills and respawns stalled workers
- Use `--profile` for non-default providers instead of manual env vars
- All commands support `--json` (place before subcommand): `clawteam --json task list my-team`

## Additional Resources

- **`references/data-model.md`** — Task statuses, message types, file storage layout, env vars
- **`references/workflows.md`** — Join protocol, plan approval, graceful shutdown, monitoring
