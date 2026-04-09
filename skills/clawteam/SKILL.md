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
version: 0.7.0
---

# ClawTeam Multi-Agent Coordination

ClawTeam is a CLI tool for coordinating multiple AI agents as a team. Operations
are via `clawteam` CLI, data in `~/.clawteam/`.

## CRITICAL: Template-First Strategy

**ALWAYS check for a matching template BEFORE doing manual orchestration.**
Templates encapsulate battle-tested workflows with proper stage ordering, quality gates,
agent roles, and coordination protocols. Using them avoids subtle errors and omissions.

### Step 1: Detect Project Type (Use Smart Selection)

**Method A: CLI-based detection (recommended for direct use)**

```bash
clawteam template suggest <project-directory>
```

This command scans the project (CMakeLists.txt, debian/control, source files) and returns
the best matching template deterministically.

**Method B: Programmatic smart selection (for Python-based agents)**

```python
from clawteam.templates import smart_select_template

# Automatically select the best template
template_name = smart_select_template(project_dir)
# Returns: "dde-trellis" for DDE projects, "software-dev" for others

# Then launch with the selected template
import subprocess
subprocess.run([
    "clawteam", "launch", template_name,
    "--team", team_name,
    "--goal", user_goal
])
```

**Interpreting results:**

| Template | When to use | Notes |
|----------|------------|-------|
| `dde-trellis` | DDE projects (DTK/Qt detected) | **Requires trellis initialization** first: `/trellis/onboard` |
| `software-dev` | Generic fallback | Works for most general software projects |
| Other specialized | Matched via signal detection | Use directly when returned |

**Do NOT use `template list`** — `template suggest` or `smart_select_template()` already considers all available templates and minimizes unnecessary LLM decisions.

### Step 3: Use Template if Match Found → Mode 1 (Launch)

**This is the PREFERRED path.** When a template matches:

```bash
# For templates that define a full team:
clawteam launch <template-name> -g "<user's actual goal>" --team <team-name>

# With backend override if user specifies wsh:
clawteam launch <template-name> -g "<user's actual goal>" --backend wsh

# With workspace isolation:
clawteam launch <template-name> -g "<user's actual goal>" --workspace
```

**WHAT `clawteam launch` DOES FOR YOU (do NOT duplicate these steps):**
1. Creates the team with the template's leader
2. Adds all template-defined agents as team members
3. Creates all template-defined tasks (with dependencies)
4. Spawns ALL agents (leader + workers) with their template-defined prompts
5. Starts a background task waiter for completion monitoring

**YOUR ONLY JOB after `clawteam launch` is SUPERVISION:**
```bash
# Monitor progress
clawteam board show <team-name>

# Attach to watch agents work (tmux only)
tmux attach -t clawteam-<team-name>

# Check messages from agents
clawteam inbox receive <team-name> --agent <leader-name>
```

**NEVER do these after `clawteam launch`:**
- Do NOT manually create the team again (`team spawn-team`)
- Do NOT manually create tasks (`task create`) — the template already did this
- Do NOT manually spawn workers (`spawn --agent-name`) — the template already did this

### Step 4: No Template Match → Mode 2 (Manual)

Only fall back to manual orchestration when NO template matches the user's request.

## Mode 2: Manual Orchestration (FALLBACK ONLY)

Use ONLY when no template matches. Follow this exact sequence.

### Phase 0: Pre-flight — Read Design & Requirements

Before creating any team, gather context:

1. **Read design docs** — Check for specs, architecture docs, task breakdowns:
   - `.sdd/changes/`, `.trellis/` — Active changes with specs and designs
   - `AGENTS.md` — Project conventions
   - Any `docs/`, `design/`, `specs/`, or `plans/`, `tasks/` directories with relevant specs
2. **Understand the goal** — What is the user trying to achieve? What are the constraints?
3. **Identify subtasks** — Break the goal into independent, parallelizable work items:
   - Each subtask should be self-contained (no file conflicts between workers)
   - Identify dependencies between subtasks (use `--blocked-by`)
   - Each subtask should have clear acceptance criteria

### Phase 1: Team Setup

```bash
# 1. Set leader identity (REQUIRED before any team operations)
export CLAWTEAM_AGENT_ID="leader-001"
export CLAWTEAM_AGENT_NAME="leader"
export CLAWTEAM_AGENT_TYPE="leader"

# 2. Create the team
clawteam team spawn-team <team-name> -d "<description>" -n leader
```

### Phase 2: Create Tasks with Dependencies

Create ALL tasks before spawning any workers. Use `--blocked-by` for dependencies.

```bash
# Independent tasks (can run in parallel)
T1=$(clawteam --json task create <team> "<task-subject>" -o worker1 -d "<detailed-description>" | python3 -c "import sys,json;print(json.load(sys.stdin)['id'])")

# Dependent tasks (blocked until prerequisites complete)
T3=$(clawteam --json task create <team> "<task-subject>" -o worker3 -d "<description>" --blocked-by "$T1,$T2" | python3 -c "import sys,json;print(json.load(sys.stdin)['id'])")
```

**Rules for task creation:**
- Each task gets a clear owner (worker name)
- Description MUST include: what to do, which files to modify, acceptance criteria
- Use `--blocked-by` for ordering constraints
- Verify with `clawteam task list <team>` before proceeding

### Phase 3: Spawn Workers

Spawn each worker as an independent session. The leader stays in its own session.

```bash
# Spawn workers — each gets its own git worktree + tmux/wsh session
clawteam spawn --team <team> --agent-name worker1 --task "<initial-task-description>"

clawteam spawn --team <team> --agent-name worker2 --task "<initial-task-description>"

# Verify all workers are running
clawteam team status <team>
clawteam board show <team>
```

**Spawn defaults:** auto backend (wsh > tmux > subprocess), git worktree, skip-permissions.

For non-default providers: `clawteam profile wizard` then `clawteam spawn --profile <name> ...`.

### Phase 4: Leader Supervision Loop

The leader monitors progress via the task board and inbox. This is a CONTINUOUS loop.

```
LOOP:
  1. Check board:  clawteam board show <team>
  2. Check inbox:  clawteam inbox receive <team> --agent leader
  3. Process messages (worker reports, questions, completions)
  4. Check for stalled workers (see Stalled Worker Protocol below)
  5. If new tasks unlocked, assign them
  6. If all tasks done, proceed to Phase 5
  7. Wait briefly, then LOOP again
```

#### Stalled Worker Detection & Recovery

A worker is "stalled" when:
- It has been assigned a task but no status update for a long time
- Its tmux pane shows it's idle/at a prompt (not actively working)
- It sent an `idle` message but still has assigned tasks

**How to nudge a stalled worker:**

For **tmux** backend:
```bash
# Check what the worker is doing (read the tmux pane)
tmux capture-pane -p -t clawteam-<team>:<worker-name> | tail -30

# If idle/at prompt, send a nudge message via tmux
tmux send-keys -t clawteam-<team>:<worker-name> "Continue working. Read your inbox and resume your current task." Enter
```

For **wsh** backend:
```bash
# Read the worker's terminal output
wsh file cat wavefile://<block-id>/term | tail -30

# Send input to the worker's block
wsh rpc send-input --block <block-id> --input "Continue working. Read your inbox and resume your current task.\n"
```

For **subprocess** backend — workers cannot be nudged. Kill and respawn:
```bash
clawteam spawn --team <team> --agent-name <name> --replace --task "<task>"
```

#### When to Shut Down a Worker

Shut down a worker when:
- All its assigned tasks are completed
- No more tasks can be assigned to it (everything remaining is blocked or assigned)
- The worker has been idle and confirmed no more work

```bash
clawteam lifecycle request-shutdown <team> leader <worker-name> --reason "All tasks complete"
```

### Phase 5: Review & Integration

After ALL tasks are completed:

1. **Review each worker's output:**
   ```bash
   # Check what each worker changed in their worktree
   clawteam workspace list <team>
   clawteam context diff <team> <worker-name>

   # Or inspect directly
   ls ~/.clawteam/workspaces/<team>/<worker-name>/
   ```

2. **Run tests:**
   ```bash
   # Merge all worktrees and test
   clawteam workspace merge <team> <worker-name>
   # Run project test suite
   ```

3. **If issues found — send corrections:**
   ```bash
   clawteam inbox send <team> <worker-name> "Issue found: <description>. Fix and re-commit."
   # Nudge the worker to pick up the message (see Stalled Worker Protocol)
   ```

4. **Final integration:**
   ```bash
   # Merge all worktrees into main
   clawteam workspace merge <team> <worker-name>   # repeat for each worker

   # Commit the integrated result
   git add -A && git commit -m "<descriptive commit message>"

   # Clean up
   clawteam team cleanup <team> --force
   ```

## Leader Responsibilities (Summary)

| Responsibility | How |
|---|---|
| Check templates first | `clawteam template list` → match → `clawteam launch` |
| Create team & tasks | `clawteam team spawn-team`, `clawtask task create` (Mode 2 only) |
| Spawn workers | `clawteam spawn --team <team> --agent-name <name> --task "..."` (Mode 2 only) |
| Monitor progress | `clawteam board show <team>`, `clawteam inbox receive` |
| Assign new tasks | `clawteam task create`, `clawteam task update --owner` |
| Nudge stalled workers | `tmux send-keys` or `wsh rpc send-input` (see protocol) |
| Shut down idle workers | `clawteam lifecycle request-shutdown` |
| Review worker output | `clawteam context diff`, `clawteam workspace merge` |
| Handle issues | `clawteam inbox send` corrections, nudge worker to retry |
| Final integration | Merge worktrees, test, commit, cleanup |

## Worker Responsibilities (Summary)

| Responsibility | How |
|---|---|
| Read assigned tasks | `clawteam task list <team> --owner <me>` |
| Start a task | `clawteam task update <team> <id> --status in_progress` |
| Do the work | Write code in the assigned worktree |
| Commit changes | `git add -A && git commit -m "..."` |
| Complete a task | `clawteam task update <team> <id> --status completed` |
| Report to leader | `clawteam inbox send <team> leader "Done: ..."` |
| Loop for more tasks | Re-check task list + inbox (see Worker Loop Protocol) |
| Report idle | `clawteam lifecycle idle <team>` after 5 empty polls |

## Key Gotchas

- `inbox receive` **consumes** messages — use `peek` for non-destructive reads
- Completing a task **auto-unblocks** dependent tasks
- Workers MUST keep polling tasks/inbox (Worker Loop Protocol) — do NOT exit after first task
- Leader MUST keep polling inbox/board (Leader Loop Protocol)
- `clawteam spawn` defaults: auto backend (wsh > tmux > subprocess), git worktree, skip-permissions
- Use `--profile` for non-default providers instead of manual env vars
- All commands support `--json` (place before subcommand): `clawteam --json task list <team>`
- `task wait` includes idle watchdog that auto-kills and respawns stalled workers
- **NEVER spawn a leader via `clawteam spawn` in Mode 2** — the current session IS the leader
- **`clawteam launch` already creates team, tasks, and spawns all agents** — do NOT duplicate
- For `dde-trellis` template: 7-stage workflow with quality gates — trust the process. **Requires `/trellis/onboard` first.**
- Long template prompts are injected via post-launch RPC, not command-line args — do not worry about prompt length

## CRITICAL: Team Name Consistency

**ALWAYS use the SAME team name throughout the entire workflow.** Team name inconsistency causes orphaned worker sessions that will never be cleaned up.

### ✅ CORRECT — Consistent team name:
```bash
TEAM_NAME="my-project"

# 1. Create team
clawteam team spawn-team $TEAM_NAME

# 2. Create tasks (same team name)
clawteam task create $TEAM_NAME "Task 1"

# 3. Spawn workers (SAME team name!)
clawteam spawn --team $TEAM_NAME --agent-name worker1 --task "..." wsh claude
clawteam spawn --team $TEAM_NAME --agent-name worker2 --task "..." wsh claude

# 4. Wait for completion (same team name)
clawteam task wait $TEAM_NAME

# 5. Cleanup
clawteam team cleanup $TEAM_NAME
```

### ❌ WRONG — Inconsistent team names causes orphans:
```bash
# Team created with "my-project"
clawteam team spawn-team my-project

# Tasks created for "my-project"
clawteam task create my-project "Task 1"

# BUT workers spawned with WRONG team name!
clawteam spawn --team wrong-name ...  # Creates orphaned registry!
clawteam spawn --team another-name ...

# task wait only cleans "my-project" registry
# Orphans in wrong-name/ and another-name/ NEVER get cleaned!
```

### Rule of Thumb:

Define team name as a variable or alias and reuse it:

```bash
TEAM="my-feature-branch"  # ONE SOURCE OF TRUTH

# Use $TEAM everywhere
clawteam team spawn-team $TEAM
clawteam task create $TEAM "..."
clawteam spawn --team $TEAM --agent-name ...
clawteam task wait $TEAM
```

## Additional Resources

- **`references/data-model.md`** — Task statuses, message types, file storage layout, env vars
- **`references/workflows.md`** — Detailed leader/worker loop protocols, shutdown, monitoring
