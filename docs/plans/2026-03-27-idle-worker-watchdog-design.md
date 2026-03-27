# Idle Worker Watchdog Design

## Problem

Workers (claude agents) complete their initial task but fail to enter the Worker Loop protocol. The claude context fills up during task execution, pushing out the loop instructions. The worker becomes idle (no output) but stays alive in the terminal, blocking new task assignment.

## Design

### Overview

Extend `TaskWaiter` with idle worker detection and auto-respawn capability. When `clawteam task wait` is running (which it always is during multi-agent coordination), it will also:

1. Detect idle-but-alive workers (output unchanged for N seconds)
2. Kill the idle worker's terminal
3. Auto-respawn with the next pending task

### Idle Detection

In each poll cycle (default 5s), for each registered agent in the team:

1. Call `_capture_block_output(block_id)` to read terminal content
2. Compute `hash(content)` and compare with previous hash
3. Track consecutive idle count (hash unchanged)
4. If `idle_count >= idle_threshold` (default 12 = 60s at 5s intervals):
   - Mark worker as idle
   - Call `stop_agent(team, agent_name)` to kill the block
   - Find next pending task for that worker from `TaskStore`
   - Call `backend.spawn(...)` with `--replace` semantics to respawn
   - Notify leader via inbox

### New Config Fields

Add to `ClawTeamConfig` in `clawteam/config.py`:

```python
idle_timeout: float = 60.0  # seconds of no output before considering idle
idle_poll_interval: float = 5.0  # how often to check output (uses poll_interval from TaskWaiter)
```

### Architecture

```
TaskWaiter.wait()
  │
  ├── Drain inbox
  ├── _check_dead_agents()        (existing - process dead)
  ├── _check_idle_agents()        (NEW - process alive but idle)
  │     ├── For each agent in team:
  │     │   ├── capture block output → hash
  │     │   ├── if hash unchanged for N polls → mark idle
  │     │   ├── stop_agent()
  │     │   └── respawn with next task
  │     └── Reset idle counter when output changes
  ├── Check task status
  └── Sleep poll_interval
```

### Auto-Respawn Logic

When respawning a worker:

1. Find the next pending task owned by this agent from `TaskStore`
2. If no pending task, skip (worker has no more work)
3. Get the original spawn command from `spawn_registry.json`
4. Call `backend.spawn(command, agent_name, ..., prompt=None)` to restart
5. The new agent will pick up the Worker Loop and check `clawteam task list`

The respawn reuses the same `backend` (wsh/tmux/subprocess) that was originally used, read from the registry.

### Integration Point

The `_check_idle_agents()` method is added to `TaskWaiter` alongside `_check_dead_agents()`:

```python
# waiter.py wait() loop
while self._running:
    messages = self.mailbox.receive(...)
    self._check_dead_agents()
    self._check_idle_agents()  # NEW
    tasks = self.task_store.list_tasks()
    ...
```

### Output Hash Cache

```python
self._output_hashes: dict[str, str] = {}  # agent_name -> last known hash
self._idle_counts: dict[str, int] = {}     # agent_name -> consecutive idle polls
```

Reset idle counter whenever hash changes (new output detected).

### Files Modified

| File | Change |
|------|--------|
| `clawteam/team/waiter.py` | Add `_check_idle_agents()`, output hash tracking, auto-respawn logic |
| `clawteam/config.py` | Add `idle_timeout` field to `ClawteamConfig` |
| `clawteam/team/models.py` | No change needed |

### Error Handling

- `_capture_block_output` fails → skip this agent (may be temporary issue)
- `stop_agent` fails → skip respawn, try again next cycle
- `backend.spawn` fails → log error, keep agent in idle state
- No pending tasks for idle worker → stop but don't respawn
