# ClawTeam Coordination Workflows

## Leader Loop Protocol

The leader runs a continuous supervision loop after spawning workers.

### Loop Steps

```
1. clawteam board show <team>              — check overall progress
2. clawteam inbox receive <team> --agent leader  — check worker messages
3. Process any messages:
   - Worker completed task → acknowledge, check if dependents unblocked
   - Worker needs help → provide guidance or reassign
   - Worker reports idle → check if more tasks available, shut down if not
4. clawteam task list <team> --status blocked  — check if any tasks can be unblocked
5. Check for stalled workers (see Stalled Worker Protocol)
6. If all tasks completed → proceed to Review & Integration
7. Sleep briefly (10-30s), then go to step 1
```

### Message Handling Rules

| Message Type | Leader Action |
|---|---|
| Worker task completion report | Acknowledge, check dependents, assign next task or shut down |
| Worker help request | Provide guidance via `clawteam inbox send` |
| Worker idle notification | Check for available tasks; if none, `clawteam lifecycle request-shutdown` |
| Worker error/blocker | Investigate, reassign task or provide workaround |

### Task Assignment After Worker Completes

```bash
# Check if there are unassigned pending tasks
clawteam task list <team> --status pending

# If yes, assign to the now-idle worker
clawteam task update <team> <task-id> --owner <worker-name>

# Notify the worker
clawteam inbox send <team> <worker-name> "New task assigned: <task-id>. Check your task list."
# Nudge the worker if needed (see Stalled Worker Protocol)
```

## Worker Loop Protocol

Workers MUST NOT exit after completing a single task. The expected behavior is:

### Loop Steps

```
1. clawteam task list <team> --owner <me>   — check for assigned tasks
2. If task found:
   a. clawteam task update <team> <id> --status in_progress
   b. Do the work (read code, write code, run tests)
   c. git add -A && git commit -m "Implement <summary>"
   d. clawteam task update <team> <id> --status completed
   e. clawteam inbox send <team> leader "Completed <id>: <summary>"
   f. Go to step 1
3. If no task found:
   a. clawteam inbox receive <team> --agent <me>   — check for leader instructions
   b. If message received (new task, correction, etc.):
      - Process it, go to step 1
   c. If no message:
      - Increment empty poll counter
      - If empty polls < 5: go to step 1
      - If empty polls >= 5:
        - clawteam lifecycle idle <team>
        - clawteam inbox send <team> leader "Idle: no tasks or messages after 5 polls. Awaiting instructions."
        - Go to step 1
```

### LLM Interruption Recovery

When a worker's LLM session is interrupted (context limit, error, etc.) and the leader
nudges it via `tmux send-keys` or `wsh send-input`:

1. Worker receives the nudge text as a new user message
2. Worker should:
   - Check if it was in the middle of a task (`clawteam task list <team> --owner <me>`)
   - If task is `in_progress`: resume work from where it left off
   - If no active task: check inbox for new assignments, enter normal loop

### Worker Exit Conditions

A worker should ONLY exit when:
- Leader sends a `shutdown_request` message → worker approves and exits
- Worker has confirmed no more tasks AND leader acknowledges the idle report

## Stalled Worker Protocol

A worker is "stalled" when it stops making progress despite having assigned work.

### Detection

Leader detects a stalled worker by:
1. Checking the task board — worker has `in_progress` task but no update for a while
2. Reading the worker's terminal output to see if it's idle
3. Receiving an `idle` notification while tasks are still assigned

### Terminal Inspection

**tmux backend:**
```bash
# Read the last 30 lines of the worker's terminal
tmux capture-pane -p -t clawteam-<team>:<worker-name> | tail -30
```

**wsh backend:**
```bash
# Read the worker's terminal output
wsh file cat wavefile://<block-id>/term | tail -30
```

Look for: prompt indicator (`❯`, `>`, `›`), error messages, or idle state.

### Nudge (Wake Up)

**tmux backend:**
```bash
tmux send-keys -t clawteam-<team>:<worker-name> "Continue working. Read your inbox and resume your current task." Enter
```

**wsh backend:**
```bash
wsh rpc send-input --block <block-id> --input "Continue working. Read your inbox and resume your current task.\n"
```

**subprocess backend:** Cannot be nudged. Kill and respawn:
```bash
clawteam spawn --team <team> --agent-name <name> --replace --task "<task-description>"
```

### Escalation

If a worker fails to respond after 2 nudges:
1. Check if the task can be reassigned to another worker
2. If yes: reassign (`clawteam task update <team> <id> --owner <other-worker>`)
3. If no: kill and respawn (`clawteam spawn --replace`)

## Graceful Shutdown

### Leader Shuts Down a Worker

```bash
# Request shutdown
clawteam lifecycle request-shutdown <team> leader <worker> --reason "All tasks complete"

# Worker receives the message, finishes current work, approves
# Leader verifies via inbox or board
```

### Worker Shuts Down Itself

```bash
# Worker notifies leader it's done
clawteam lifecycle idle <team>

# Worker waits for leader's shutdown_request message
# Upon receiving it:
clawteam lifecycle approve-shutdown <team> <request-id> leader
# Then exit the session
```

## Review & Integration Protocol

After ALL tasks are completed, the leader performs a full review cycle.

### Step 1: Collect Output

```bash
# List all worker workspaces
clawteam workspace list <team>

# Check what each worker changed
clawteam context diff <team> <worker-name>
```

### Step 2: Review Each Worker

For each worker's changes:
1. Read the changed files
2. Verify they match the task requirements
3. Check for code quality issues
4. Run tests if applicable

### Step 3: Handle Issues

If a review finds problems:
```bash
# Send correction to the worker
clawteam inbox send <team> <worker-name> "Review issue: <description>. Fix in your worktree and re-commit."

# Nudge the worker to pick up the message
tmux send-keys -t clawteam-<team>:<worker-name> "You have a new correction. Read your inbox and process it." Enter
```

### Step 4: Merge & Test

```bash
# Merge each worker's worktree into main branch
for worker in worker1 worker2 worker3; do
  clawteam workspace merge <team> $worker
done

# Run the project's test suite
# (use the project's actual test command)
```

### Step 5: Commit & Cleanup

```bash
# Commit the integrated result
git add -A && git commit -m "<descriptive message covering all changes>"

# Clean up all team resources
clawteam team cleanup <team> --force
```

## Join Request Protocol

```bash
# Agent requests to join (blocks until response)
clawteam team request-join <team> <name> --capabilities "frontend specialist" --timeout 120

# Leader checks inbox and approves
clawteam inbox peek <team> --agent leader
clawteam team approve-join <team> join-abc123
```

## Plan Approval Flow

```bash
# Worker submits plan (inline text or file path)
clawteam plan submit <team> <agent> "1. Refactor auth\n2. Add OAuth2" --summary "Auth upgrade"
# Leader reviews and decides
clawteam plan approve <team> <plan-id> <agent> --feedback "Looks good"
# or: clawteam plan reject <team> <plan-id> <agent> --feedback "Add error handling"
```

## Monitoring Commands

```bash
clawteam board overview                           # all teams summary
clawteam board show <team>                        # kanban + messages
clawteam board live <team> --interval 3           # auto-refresh
clawteam board attach <team>                      # tiled tmux view
clawteam board serve --port 8080                  # web UI
clawteam --json task list <team> --status blocked  # JSON output for scripting
```
