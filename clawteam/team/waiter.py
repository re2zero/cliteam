"""Task waiter - blocks until all tasks in a team are completed."""

from __future__ import annotations

import logging
import os
import re
import signal
import subprocess
import threading as _threading
import time
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Coroutine

from clawteam.team.completion import CompletionHandler
from clawteam.team.mailbox import MailboxManager
from clawteam.team.models import TaskItem, TaskStatus, TeamMessage
from clawteam.team.tasks import TaskStore

_PROMPT_RE = re.compile(r"[❯›>$#]\s*$")


@dataclass
class WaitResult:
    """Result returned by TaskWaiter.wait()."""

    status: str  # "completed", "timeout", "interrupted"
    elapsed: float = 0.0
    total: int = 0
    completed: int = 0
    in_progress: int = 0
    pending: int = 0
    blocked: int = 0
    messages_received: int = 0
    task_details: list[dict] = field(default_factory=list)


class TaskWaiter:
    """Blocks until all tasks in a team reach completed status.

    Each poll cycle:
    1. Drain inbox messages and invoke on_message callback
    2. Detect dead agents and recover their in_progress tasks
    3. Check task completion and invoke on_progress callback (if changed)
    4. Return if all done, timed out, or interrupted
    5. Sleep poll_interval seconds
    """

    def __init__(
        self,
        team_name: str,
        agent_name: str,
        mailbox: MailboxManager,
        task_store: TaskStore,
        poll_interval: float = 5.0,
        timeout: float | None = None,
        on_message: Callable[[TeamMessage], None] | None = None,
        on_progress: Callable[[int, int, int, int, int], None] | None = None,
        on_agent_dead: Callable[[str, list[TaskItem]], None] | None = None,
        observe_only: bool = False,
        completion_handler: CompletionHandler | None = None,
    ):
        self.team_name = team_name
        self.agent_name = agent_name
        self.mailbox = mailbox
        self.task_store = task_store
        self.poll_interval = poll_interval
        self.timeout = timeout
        self.on_message = on_message
        self.on_progress = on_progress
        self.on_agent_dead = on_agent_dead
        self._running = False
        self._messages_received = 0
        self._known_dead: set[str] = set()
        self._output_hashes: dict[str, str] = {}
        self._idle_counts: dict[str, int] = {}
        self._respawned_agents: set[str] = set()
        self._observe_only = observe_only
        self._nudged_agents: set[str] = set()
        self._nudge_log: dict[str, list[float]] = {}
        self.completion_handler = completion_handler
        self._previously_completed: set[str] = set()

    def wait(self, completion_callback: Callable[[TaskItem, str], Coroutine[Any, Any, None]] | None = None) -> WaitResult:
        """Block until all tasks are completed, timeout, or interrupted.

        Args:
            completion_callback: Optional coroutine callback to invoke when a task completes.
                                 Receives the completed task and team name.
        """
        self._running = True
        start = time.monotonic()

        # Save and install signal handlers (main thread only)
        is_main = isinstance(_threading.current_thread(), _threading._MainThread)
        prev_sigint = prev_sigterm = None
        if is_main:
            prev_sigint = signal.getsignal(signal.SIGINT)
            prev_sigterm = signal.getsignal(signal.SIGTERM)

        def _handle_signal(signum, frame):
            self._running = False

        if is_main:
            signal.signal(signal.SIGINT, _handle_signal)
            signal.signal(signal.SIGTERM, _handle_signal)

        last_summary = ""
        try:
            while self._running:
                # 1. Read inbox messages (peek in observe mode to avoid consuming)
                if self._observe_only:
                    messages = self.mailbox.peek(self.agent_name)
                else:
                    messages = self.mailbox.receive(self.agent_name, limit=50)
                for msg in messages:
                    self._messages_received += 1
                    if self.on_message:
                        self.on_message(msg)

                # 2. Detect dead agents and recover their tasks
                self._check_dead_agents()

                # 3. Detect idle-but-alive workers and auto-respawn
                self._check_idle_agents()

                # 4. Check task status
                tasks = self.task_store.list_tasks()
                total = len(tasks)
                completed = sum(1 for t in tasks if t.status == TaskStatus.completed)
                in_progress = sum(1 for t in tasks if t.status == TaskStatus.in_progress)
                pending = sum(1 for t in tasks if t.status == TaskStatus.pending)
                blocked = sum(1 for t in tasks if t.status == TaskStatus.blocked)

                # Check for newly completed tasks and handle completion
                current_completed = {t.id for t in tasks if t.status == TaskStatus.completed}
                newly_completed = current_completed - self._previously_completed
                if newly_completed:
                    for task_id in newly_completed:
                        task = next(t for t in tasks if t.id == task_id)
                        # Run completion handler asynchronously to avoid blocking
                        import asyncio
                        if completion_callback:
                            asyncio.create_task(completion_callback(task, self.team_name))
                        elif self.completion_handler:
                            asyncio.create_task(self.completion_handler.handle_completion(task, self.team_name))
                self._previously_completed = current_completed

                # Deduplicate progress output
                summary = f"{completed}/{total}/{in_progress}/{pending}/{blocked}"
                if summary != last_summary:
                    if self.on_progress:
                        self.on_progress(completed, total, in_progress, pending, blocked)
                    last_summary = summary

                # 5. All done?
                if total > 0 and completed == total:
                    if self._observe_only:
                        final_msgs = self.mailbox.peek(self.agent_name)
                    else:
                        final_msgs = self.mailbox.receive(self.agent_name, limit=50)
                    for msg in final_msgs:
                        self._messages_received += 1
                        if self.on_message:
                            self.on_message(msg)
                    
                    # Gracefully shutdown all worker sessions now that all tasks are complete
                    self._shutdown_all_workers()
                    
                    elapsed = time.monotonic() - start
                    return WaitResult(
                        status="completed",
                        elapsed=elapsed,
                        total=total,
                        completed=completed,
                        in_progress=0,
                        pending=0,
                        blocked=0,
                        messages_received=self._messages_received,
                        task_details=[_task_summary(t) for t in tasks],
                    )

                # 5b. In observe mode: all workers dead, no in_progress → force complete
                if self._observe_only and in_progress == 0:
                    from clawteam.spawn.registry import list_dead_agents

                    dead = list_dead_agents(self.team_name)
                    worker_names = [n for n in dead if n != self.agent_name]
                    all_workers = list({t.owner for t in tasks if t.owner != self.agent_name})
                    if all_workers and all(w in self._known_dead for w in all_workers):
                        elapsed = time.monotonic() - start
                        return WaitResult(
                            status="completed",
                            elapsed=elapsed,
                            total=total,
                            completed=completed,
                            in_progress=0,
                            pending=pending,
                            blocked=blocked,
                            messages_received=self._messages_received,
                            task_details=[_task_summary(t) for t in tasks],
                        )

                # 6. Timeout?
                elapsed = time.monotonic() - start
                if self.timeout and elapsed >= self.timeout:
                    return WaitResult(
                        status="timeout",
                        elapsed=elapsed,
                        total=total,
                        completed=completed,
                        in_progress=in_progress,
                        pending=pending,
                        blocked=blocked,
                        messages_received=self._messages_received,
                        task_details=[_task_summary(t) for t in tasks],
                    )

                # 7. Sleep
                time.sleep(self.poll_interval)

            # Interrupted
            elapsed = time.monotonic() - start
            tasks = self.task_store.list_tasks()
            total = len(tasks)
            return WaitResult(
                status="interrupted",
                elapsed=elapsed,
                total=total,
                completed=sum(1 for t in tasks if t.status == TaskStatus.completed),
                in_progress=sum(1 for t in tasks if t.status == TaskStatus.in_progress),
                pending=sum(1 for t in tasks if t.status == TaskStatus.pending),
                blocked=sum(1 for t in tasks if t.status == TaskStatus.blocked),
                messages_received=self._messages_received,
                task_details=[_task_summary(t) for t in tasks],
            )
        finally:
            if is_main and prev_sigint is not None:
                signal.signal(signal.SIGINT, prev_sigint)
                signal.signal(signal.SIGTERM, prev_sigterm)

    def _check_dead_agents(self) -> None:
        """Detect dead agents and mark their in_progress tasks as pending."""
        try:
            from clawteam.spawn.registry import list_dead_agents
        except ImportError:
            return

        dead_agents = list_dead_agents(self.team_name)
        for agent_name in dead_agents:
            if agent_name in self._known_dead:
                continue
            self._known_dead.add(agent_name)

            # Find this agent's in_progress tasks and reset them
            tasks = self.task_store.list_tasks()
            abandoned = [
                t for t in tasks if t.owner == agent_name and t.status == TaskStatus.in_progress
            ]
            for t in abandoned:
                self.task_store.update(t.id, status=TaskStatus.pending)

            if abandoned and self.on_agent_dead:
                self.on_agent_dead(agent_name, abandoned)

    def _check_idle_agents(self) -> None:
        from clawteam.config import load_config
        from clawteam.spawn.registry import get_registry, stop_agent

        cfg = load_config()
        idle_threshold = max(1, int(cfg.idle_timeout / self.poll_interval))
        nudge_threshold = max(1, int(cfg.nudge_delay / self.poll_interval))
        registry = get_registry(self.team_name)

        for agent_name, info in registry.items():
            if agent_name in self._known_dead or agent_name in self._respawned_agents:
                continue

            backend = info.get("backend", "")
            if backend == "wsh":
                content = self._capture_wsh_output(info.get("block_id", ""))
            elif backend == "tmux":
                content = self._capture_tmux_output(info.get("tmux_target", ""))
            else:
                continue

            if content is None:
                continue

            content_hash = hash(content)
            last_hash = self._output_hashes.get(agent_name)

            if content_hash == last_hash:
                self._idle_counts[agent_name] = self._idle_counts.get(agent_name, 0) + 1
            else:
                self._idle_counts[agent_name] = 0
            self._output_hashes[agent_name] = content_hash

            idle_count = self._idle_counts.get(agent_name, 0)

            if cfg.nudge_enabled and idle_count >= nudge_threshold and idle_count < idle_threshold:
                if self._try_nudge_agent(agent_name, info, content, cfg):
                    continue

            if idle_count >= idle_threshold:
                self._respawn_idle_worker(agent_name, info, cfg)

    def _capture_wsh_output(self, block_id: str) -> str | None:
        if not block_id:
            return None
        try:
            from clawteam.spawn.wsh_backend import _capture_block_output

            return _capture_block_output(block_id)
        except Exception:
            return None

    def _capture_tmux_output(self, target: str) -> str | None:
        import subprocess

        if not target:
            return None
        try:
            result = subprocess.run(
                ["tmux", "capture-pane", "-t", target, "-p", "-S", "-50"],
                capture_output=True,
                text=True,
                timeout=5.0,
            )
            if result.returncode != 0:
                return None
            return result.stdout
        except Exception:
            return None

    def _try_nudge_agent(
        self,
        agent_name: str,
        spawn_info: dict,
        content: str,
        cfg,
    ) -> bool:
        if agent_name in self._nudged_agents:
            return False

        if not self._is_at_prompt(content):
            return False

        if not self._has_pending_messages(agent_name):
            return False

        if not self._inject_nudge(agent_name, spawn_info):
            return False

        self._nudged_agents.add(agent_name)
        logging.info(
            "Nudge: sent reminder to '%s' (idle %.0fs, pending inbox messages)",
            agent_name,
            cfg.nudge_delay,
        )
        return True

    @staticmethod
    def _is_at_prompt(content: str) -> bool:
        lines = content.strip().splitlines()
        if not lines:
            return False
        last_line = lines[-1].strip()
        return bool(_PROMPT_RE.match(last_line))

    def _has_pending_messages(self, agent_name: str) -> bool:
        try:
            return self.mailbox.peek_count(agent_name) > 0
        except Exception:
            return False

    def _inject_nudge(self, agent_name: str, spawn_info: dict) -> bool:
        import shlex

        backend = spawn_info.get("backend", "")
        nudge_cmd = (
            f"clawteam inbox receive {shlex.quote(self.team_name)} "
            f"--agent {shlex.quote(agent_name)}"
        )
        if backend == "wsh":
            return self._nudge_via_wsh(spawn_info.get("block_id", ""), nudge_cmd)
        if backend == "tmux":
            return self._nudge_via_tmux(spawn_info.get("tmux_target", ""), nudge_cmd)
        return False

    @staticmethod
    def _nudge_via_wsh(block_id: str, command: str) -> bool:
        try:
            from clawteam.spawn.wsh_rpc import WshRpcClient

            return WshRpcClient().send_input(block_id, command + "\n")
        except Exception as exc:
            logging.warning("Nudge: failed to send to wsh block %s: %s", block_id, exc)
            return False

    @staticmethod
    def _nudge_via_tmux(target: str, command: str) -> bool:
        try:
            result = subprocess.run(
                ["tmux", "send-keys", "-t", target, command, "Enter"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=5.0,
            )
            return result.returncode == 0
        except Exception as exc:
            logging.warning("Nudge: failed to send to tmux target %s: %s", target, exc)
            return False

    def _respawn_idle_worker(self, agent_name: str, spawn_info: dict, cfg) -> None:
        from clawteam.spawn.registry import stop_agent
        from clawteam.team.manager import TeamManager

        stopped = stop_agent(self.team_name, agent_name)
        if stopped is not True:
            return

        tasks = self.task_store.list_tasks()
        next_task = None
        for t in tasks:
            if t.owner == agent_name and t.status == TaskStatus.pending:
                next_task = t
                break

        if next_task is None:
            leader_name = TeamManager.get_leader_name(self.team_name) or "leader"
            self.mailbox.send(
                from_agent=self.agent_name,
                to=leader_name,
                content=(
                    f"Worker '{agent_name}' was idle (no output for {cfg.idle_timeout:.0f}s) "
                    f"and has no pending tasks. Shutting down."
                ),
            )
            self._known_dead.add(agent_name)
            self._respawned_agents.discard(agent_name)
            return

        command = spawn_info.get("command", [])
        if not command:
            self._respawned_agents.discard(agent_name)
            return

        self._respawned_agents.add(agent_name)

        try:
            from clawteam.spawn import get_backend
            from clawteam.spawn.prompt import build_agent_prompt
            from clawteam.team.manager import TeamManager

            leader_name = TeamManager.get_leader_name(self.team_name) or "leader"
            respawn_prompt = build_agent_prompt(
                agent_name=agent_name,
                agent_id=spawn_info.get("agent_id", ""),
                agent_type="general-purpose",
                team_name=self.team_name,
                leader_name=leader_name,
                task=next_task.subject,
                user=os.environ.get("CLAWTEAM_USER", ""),
            )

            backend = get_backend(spawn_info.get("backend", "wsh"))
            backend.spawn(
                command=command,
                agent_name=agent_name,
                agent_id="",
                agent_type="general-purpose",
                team_name=self.team_name,
                prompt=respawn_prompt,
                cwd=spawn_info.get("cwd", ""),
                skip_permissions=True,
            )

            self.mailbox.send(
                from_agent=self.agent_name,
                to=leader_name,
                content=(
                    f"Worker '{agent_name}' was idle (no output for {cfg.idle_timeout:.0f}s). "
                    f"Killed and respawned. Assigned next task: {next_task.subject} "
                    f"({next_task.id})."
                ),
            )
        except Exception as exc:
            logging.warning("Watchdog: failed to respawn '%s': %s", agent_name, exc)
        finally:
            self._respawned_agents.discard(agent_name)
            self._nudged_agents.discard(agent_name)
            self._output_hashes.pop(agent_name, None)
            self._idle_counts.pop(agent_name, None)


    def _shutdown_all_workers(self) -> None:
        """Gracefully shutdown all active worker sessions for this team."""
        try:
            from clawteam.spawn.registry import get_registry, stop_agent
        except ImportError as exc:
            logging.warning("Cannot shutdown workers: spawn registry not available: %s", exc)
            return
        
        try:
            registry = get_registry(self.team_name)
        except Exception as exc:
            logging.warning("Failed to load worker registry: %s", exc)
            return
        
        shutdown_count = 0
        failed_count = 0
        
        for agent_name in list(registry.keys()):
            if agent_name == self.agent_name:
                continue  # Never shutdown the leader itself
                
            try:
                stopped = stop_agent(self.team_name, agent_name)
                if stopped:
                    shutdown_count += 1
                    logging.info("Successfully shutdown completed worker '%s'", agent_name)
                else:
                    failed_count += 1
                    logging.warning("Worker '%s' could not be stopped (already terminated?)", agent_name)
            except Exception as exc:
                failed_count += 1
                logging.warning("Failed to shutdown worker '%s': %s", agent_name, exc, exc_info=True)
        
        if shutdown_count > 0 or failed_count > 0:
            logging.info(
                "Task completion cleanup: shutdown %d workers, %d failed to stop",
                shutdown_count, failed_count
            )


def _task_summary(task: TaskItem) -> dict:
    """Summarize a task for the wait result."""
    return {
        "id": task.id,
        "subject": task.subject,
        "status": task.status.value,
        "owner": task.owner,
    }
