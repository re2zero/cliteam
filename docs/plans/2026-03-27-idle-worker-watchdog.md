# Idle Worker Watchdog Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Detect idle-but-alive workers, kill them, and auto-respawn with next pending task.

**Architecture:** Extend `TaskWaiter._check_idle_agents()` alongside existing `_check_dead_agents()`. Detect idle by hashing wsh block output. Kill via `stop_agent()`, respawn via `backend.spawn()`.

**Tech Stack:** Python 3.10+, pydantic, existing TaskWaiter/TaskStore/registry infrastructure

---

### Task 1: Add `idle_timeout` config field

**Files:**
- Modify: `clawteam/config.py:38-53` (ClawTeamConfig)
- Modify: `clawteam/config.py:119-125` (scalar_config_keys)
- Modify: `clawteam/config.py:82-101` (get_effective env_map)

**Step 1: Add field to ClawTeamConfig**

In `clawteam/config.py`, add `idle_timeout` field after `spawn_ready_timeout`:

```python
idle_timeout: float = 60.0  # seconds of no output before considering worker idle
```

**Step 2: Add to env_map in get_effective**

In `clawteam/config.py`, add to the `env_map` dict:

```python
"idle_timeout": "CLAWTEAM_IDLE_TIMEOUT",
```

**Step 3: Run tests**

Run: `pytest tests/ -v --tb=short -k "config"`
Expected: PASS

**Step 4: Commit**

```bash
git add clawteam/config.py
git commit -m "feat(config): add idle_timeout config field"
```

---

### Task 2: Add idle detection helpers to waiter.py

**Files:**
- Modify: `clawteam/team/waiter.py` (entire file)

**Step 1: Add imports and state tracking fields to `__init__`**

In `TaskWaiter.__init__`, add:

```python
self._output_hashes: dict[str, str] = {}
self._idle_counts: dict[str, int] = {}
self._respawned_agents: set[str] = set()
```

After the existing `self._known_dead = set()` line.

**Step 2: Write `_check_idle_agents` method**

Add after `_check_dead_agents` method:

```python
def _check_idle_agents(self) -> None:
    """Detect idle-but-alive workers and auto-respawn with next task."""
    from clawteam.config import load_config
    from clawteam.spawn.registry import get_registry, stop_agent

    cfg = load_config()
    idle_threshold = int(cfg.idle_timeout / self.poll_interval)
    registry = get_registry(self.team_name)

    # Only check agents that have a spawn entry and are alive
    for agent_name, info in registry.items():
        if agent_name in self._known_dead or agent_name in self._respawned_agents:
            continue

        backend = info.get("backend", "")
        if backend != "wsh":
            continue  # Only wsh backend supports output capture

        block_id = info.get("block_id", "")
        if not block_id:
            continue

        content = self._capture_wsh_output(block_id)
        if content is None:
            continue  # capture failed, skip

        content_hash = hash(content)
        last_hash = self._output_hashes.get(agent_name)

        if content_hash == last_hash:
            self._idle_counts[agent_name] = self._idle_counts.get(agent_name, 0) + 1
        else:
            self._idle_counts[agent_name] = 0
        self._output_hashes[agent_name] = content_hash

        if self._idle_counts.get(agent_name, 0) >= idle_threshold:
            self._respawn_idle_worker(agent_name, info, cfg)

def _capture_wsh_output(self, block_id: str) -> str | None:
    """Capture wsh block output via wavefile protocol, returns stripped content or None."""
    try:
        from clawteam.spawn.wsh_backend import _capture_block_output
        return _capture_block_output(block_id)
    except Exception:
        return None

def _respawn_idle_worker(self, agent_name: str, spawn_info: dict, cfg) -> None:
    """Stop idle worker and respawn with next pending task."""
    stopped = stop_agent(self.team_name, agent_name)
    if stopped is not True:
        return

    # Find next pending task for this agent
    tasks = self.task_store.list_tasks()
    next_task = None
    for t in tasks:
        if t.owner == agent_name and t.status == TaskStatus.pending:
            next_task = t
            break

    if next_task is None:
        self._respawned_agents.discard(agent_name)
        return

    # Respawn using original command
    command = spawn_info.get("command", [])
    if not command:
        self._respawned_agents.discard(agent_name)
        return

    try:
        from clawteam.spawn import get_backend
        backend = get_backend(spawn_info.get("backend", "wsh"))
        backend.spawn(
            command=command,
            agent_name=agent_name,
            agent_id=spawn_info.get("agent_id", ""),
            agent_type="general-purpose",
            team_name=self.team_name,
        )
        self._respawned_agents.discard(agent_name)
        # Reset idle tracking for respawned agent
        self._output_hashes.pop(agent_name, None)
        self._idle_counts.pop(agent_name, None)
    except Exception:
        self._respawned_agents.discard(agent_name)
```

**Step 3: Integrate `_check_idle_agents` into wait loop**

In `TaskWaiter.wait()`, add call after `self._check_dead_agents()`:

```python
self._check_idle_agents()
```

**Step 4: Run existing tests**

Run: `pytest tests/ -v --tb=short`
Expected: All existing tests PASS (no regressions)

**Step 5: Write idle detection unit tests**

Create: `tests/test_idle_watchdog.py`

```python
"""Tests for idle worker watchdog in TaskWaiter."""
from __future__ import annotations

def test_idle_detection_resets_on_new_output():
    """Idle counter resets when block output changes."""

def test_idle_detection_triggers_at_threshold():
    """Worker is marked idle after consecutive unchanged polls."""

def test_respawn_finds_next_pending_task():
    """Respawn picks up next pending task for the same owner."""

def test_respawn_skips_when_no_pending_tasks():
    """Worker is killed but not respawned when no pending tasks remain."""

def test_respawn_skips_non_wsh_backends():
    """Idle detection only applies to wsh backend workers."""

def test_idle_detection_skips_dead_agents():
    """Already-dead agents are not checked for idleness."""
```

**Step 6: Run new tests**

Run: `pytest tests/test_idle_watchdog.py -v --tb=short`
Expected: All PASS

**Step 7: Commit**

```bash
git add clawteam/team/waiter.py tests/test_idle_watchdog.py
git commit -m "feat(watchdog): add idle worker detection and auto-respawn"
```

---

### Task 3: Add leader notification for idle/respawn events

**Files:**
- Modify: `clawteam/team/waiter.py` (`_respawn_idle_worker` method)

**Step 1: Add inbox notification to `_respawn_idle_worker`**

In `_respawn_idle_worker`, after successful respawn, send a message to the leader:

```python
from clawteam.team.mailbox import MailboxManager
mailbox = MailboxManager(self.team_name)
leader = TeamManager.get_leader_name(self.team_name) or "leader"
mailbox.send(
    from_agent=self.agent_name,
    to=leader,
    content=f"Worker '{agent_name}' was idle (no output for {cfg.idle_timeout:.0f}s). "
           f"Killed and respawned. Assigned next task: {next_task.subject} "
           f"({next_task.id}).",
)
```

**Step 2: Run tests**

Run: `pytest tests/ -v --tb=short`
Expected: All PASS

**Step 3: Commit**

```bash
git add clawteam/team/waiter.py
git commit -m "feat(watchdog): notify leader on idle worker respawn"
```
