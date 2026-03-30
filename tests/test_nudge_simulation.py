"""Simulation: Worker goes idle and forgets to check inbox.

Compares behavior WITH nudge enabled vs WITHOUT nudge.

Scenario:
  1. Leader creates a task for worker 'alice'
  2. Leader sends a message to alice's inbox (e.g. new instructions)
  3. Alice finishes her current task but sits idle (forgot to check inbox)
  4. Leader's waiter loop polls every 5s
  5. WITH nudge: after 10s idle, alice gets nudged to check inbox
  6. WITHOUT nudge: alice sits idle until 60s watchdog kills her
"""

from __future__ import annotations

import time
from unittest.mock import MagicMock, patch

from clawteam.team.mailbox import MailboxManager
from clawteam.team.models import TaskItem, TaskStatus
from clawteam.team.tasks import TaskStore
from clawteam.team.waiter import TaskWaiter
from clawteam.transport.file import FileTransport


def _make_waiter(team_name: str, poll_interval: float = 5.0) -> TaskWaiter:
    transport = FileTransport(team_name)
    mailbox = MailboxManager(team_name, transport=transport)
    task_store = TaskStore(team_name)
    return TaskWaiter(
        team_name=team_name,
        agent_name="leader",
        mailbox=mailbox,
        task_store=task_store,
        poll_interval=poll_interval,
    )


def _simulate_idle_worker(
    team_name: str,
    poll_interval: float,
    nudge_enabled: bool,
    nudge_delay: float,
    idle_timeout: float,
    max_cycles: int = 30,
) -> dict:
    waiter = _make_waiter(team_name, poll_interval=poll_interval)
    transport = FileTransport(team_name)
    leader_mailbox = MailboxManager(team_name, transport=transport)

    leader_mailbox.send(
        from_agent="leader",
        to="alice",
        content="New task assigned: implement OAuth login flow",
    )

    idle_output = "All tasks completed.\n❯"
    initial_hash = hash(idle_output)

    cfg = MagicMock(
        idle_timeout=idle_timeout,
        nudge_enabled=nudge_enabled,
        nudge_delay=nudge_delay,
    )

    nudge_times: list[float] = []
    respawn_called = False
    cycle_results: list[dict] = []

    for cycle in range(max_cycles):
        elapsed = cycle * poll_interval

        with (
            patch("clawteam.config.load_config", return_value=cfg),
            patch("clawteam.spawn.registry.get_registry") as mock_reg,
            patch.object(waiter, "_capture_wsh_output", return_value=idle_output),
            patch.object(waiter, "_nudge_via_wsh", wraps=lambda bid, cmd: True) as mock_nudge,
            patch.object(waiter, "_respawn_idle_worker") as mock_respawn,
        ):
            mock_reg.return_value = {
                "alice": {
                    "backend": "wsh",
                    "block_id": "block-alice",
                    "command": ["claude"],
                },
            }

            if cycle == 0:
                waiter._output_hashes["alice"] = initial_hash
                waiter._idle_counts["alice"] = 0
            else:
                waiter._idle_counts["alice"] = cycle

            waiter._check_idle_agents()

            nudge_count = mock_nudge.call_count
            respawn_count = mock_respawn.call_count

            if nudge_count > 0:
                nudge_times.append(elapsed)

            if respawn_count > 0 and not respawn_called:
                respawn_called = True

            cycle_results.append(
                {
                    "cycle": cycle,
                    "elapsed_s": elapsed,
                    "idle_count": waiter._idle_counts.get("alice", 0),
                    "nudged": nudge_count > 0,
                    "nudge_total": nudge_count,
                    "respawned": respawn_count > 0,
                    "in_nudged_set": "alice" in waiter._nudged_agents,
                }
            )

            if respawn_called:
                break

    return {
        "nudge_enabled": nudge_enabled,
        "poll_interval": poll_interval,
        "nudge_delay": nudge_delay,
        "idle_timeout": idle_timeout,
        "nudge_times": nudge_times,
        "respawned": respawn_called,
        "first_nudge_s": nudge_times[0] if nudge_times else None,
        "cycles": cycle_results,
    }


def test_simulation_nudge_enabled():
    result = _simulate_idle_worker(
        team_name="sim-nudge-on",
        poll_interval=5.0,
        nudge_enabled=True,
        nudge_delay=10.0,
        idle_timeout=60.0,
    )

    assert result["nudge_enabled"] is True
    assert result["first_nudge_s"] is not None, "Nudge should have been sent"
    nudge_cycle = [c for c in result["cycles"] if c["nudged"]][0]
    actual_idle_s = nudge_cycle["idle_count"] * result["poll_interval"]
    assert actual_idle_s >= result["nudge_delay"], (
        f"Nudge too early: idle {actual_idle_s:.0f}s < delay {result['nudge_delay']:.0f}s"
    )
    assert actual_idle_s < result["idle_timeout"], (
        f"Nudge should happen before respawn: {actual_idle_s:.0f}s"
    )

    assert nudge_cycle["in_nudged_set"] is True

    print(f"\n  WITH nudge:")
    print(f"    Nudge sent at: idle {actual_idle_s:.0f}s (cycle {nudge_cycle['cycle']})")
    print(f"    Worker notified ~{result['idle_timeout'] - actual_idle_s:.0f}s BEFORE respawn")


def test_simulation_nudge_disabled():
    result = _simulate_idle_worker(
        team_name="sim-nudge-off",
        poll_interval=5.0,
        nudge_enabled=False,
        nudge_delay=10.0,
        idle_timeout=60.0,
    )

    assert result["nudge_enabled"] is False
    assert result["first_nudge_s"] is None, "No nudge should be sent when disabled"
    assert result["respawned"] is True, "Worker should be respawned after timeout"

    respawn_cycle = [c for c in result["cycles"] if c["respawned"]][0]
    print(f"\n  WITHOUT nudge:")
    print(
        f"    Worker sits idle until: {respawn_cycle['elapsed_s']:.0f}s (cycle {respawn_cycle['cycle']})"
    )
    print(f"    Leader had to KILL and RESPAWN the worker")


def test_simulation_comparison():
    poll_interval = 5.0
    nudge_delay = 10.0
    idle_timeout = 60.0

    with_nudge = _simulate_idle_worker(
        team_name="sim-compare-on",
        poll_interval=poll_interval,
        nudge_enabled=True,
        nudge_delay=nudge_delay,
        idle_timeout=idle_timeout,
    )

    without_nudge = _simulate_idle_worker(
        team_name="sim-compare-off",
        poll_interval=poll_interval,
        nudge_enabled=False,
        nudge_delay=nudge_delay,
        idle_timeout=idle_timeout,
    )

    nudge_s = with_nudge["first_nudge_s"]
    nudge_cycle = [c for c in with_nudge["cycles"] if c["nudged"]][0]
    actual_nudge_s = nudge_cycle["idle_count"] * poll_interval

    respawn_cycle = [c for c in without_nudge["cycles"] if c["respawned"]][0]
    actual_respawn_s = respawn_cycle["idle_count"] * poll_interval

    print("\n" + "=" * 60)
    print("  SIMULATION COMPARISON")
    print("=" * 60)
    print(f"  Worker idle, pending inbox messages, at prompt ❯")
    print(
        f"  Poll interval: {poll_interval}s | Nudge delay: {nudge_delay}s | Idle timeout: {idle_timeout}s"
    )
    print(f"  ─────────────────────────────────────────────")
    print(f"  WITH nudge:    Worker reminded at idle {actual_nudge_s:.0f}s")
    print(f"  WITHOUT nudge: Worker killed at idle {actual_respawn_s:.0f}s")
    print(f"  ─────────────────────────────────────────────")
    print(f"  Improvement:   {actual_respawn_s - actual_nudge_s:.0f}s earlier notification")
    print(f"  Worker saved:  Yes (no kill/respawn cycle needed)")
    print("=" * 60)

    assert actual_nudge_s >= nudge_delay
    assert actual_respawn_s > actual_nudge_s
    improvement = actual_respawn_s - actual_nudge_s
    assert improvement >= 40.0, f"Expected at least 40s improvement, got {improvement:.0f}s"


def test_simulation_worker_not_at_prompt():
    waiter = _make_waiter("sim-not-prompt", poll_interval=5.0)
    transport = FileTransport("sim-not-prompt")
    mailbox = MailboxManager("sim-not-prompt", transport=transport)
    mailbox.send(from_agent="leader", to="bob", content="Check your tasks")

    busy_output = "Running test suite...\n✓ test_auth passed\n✓ test_login passed"
    waiter._output_hashes["bob"] = hash(busy_output)

    cfg = MagicMock(idle_timeout=60.0, nudge_enabled=True, nudge_delay=10.0)

    with (
        patch("clawteam.config.load_config", return_value=cfg),
        patch("clawteam.spawn.registry.get_registry") as mock_reg,
        patch.object(waiter, "_capture_wsh_output", return_value=busy_output),
        patch.object(waiter, "_nudge_via_wsh") as mock_nudge,
    ):
        mock_reg.return_value = {
            "bob": {"backend": "wsh", "block_id": "block-bob", "command": ["claude"]},
        }
        for _ in range(3):
            waiter._idle_counts["bob"] = waiter._idle_counts.get("bob", 0) + 1
            waiter._check_idle_agents()

    mock_nudge.assert_not_called()
    print("\n  Worker busy (no prompt detected): nudge correctly skipped")


def test_simulation_output_resumes_nudge_reset():
    waiter = _make_waiter("sim-resume", poll_interval=5.0)
    transport = FileTransport("sim-resume")
    mailbox = MailboxManager("sim-resume", transport=transport)
    mailbox.send(from_agent="leader", to="carol", content="New task")

    idle_output = "Done.\n❯"
    waiter._output_hashes["carol"] = hash(idle_output)
    waiter._idle_counts["carol"] = 1

    cfg = MagicMock(idle_timeout=60.0, nudge_enabled=True, nudge_delay=10.0)

    with (
        patch("clawteam.config.load_config", return_value=cfg),
        patch("clawteam.spawn.registry.get_registry") as mock_reg,
        patch.object(waiter, "_nudge_via_wsh") as mock_nudge,
    ):
        mock_reg.return_value = {
            "carol": {"backend": "wsh", "block_id": "block-carol", "command": ["claude"]},
        }

        waiter._capture_wsh_output = MagicMock(return_value=idle_output)
        waiter._check_idle_agents()
        assert waiter._idle_counts["carol"] == 2
        assert mock_nudge.call_count == 1  # nudge at idle_count=2 (threshold)

        new_output = "Checking inbox...\nFound new task: OAuth login"
        waiter._capture_wsh_output = MagicMock(return_value=new_output)
        waiter._check_idle_agents()
        assert waiter._idle_counts["carol"] == 0

        waiter._capture_wsh_output = MagicMock(return_value=new_output)
        waiter._check_idle_agents()
        assert waiter._idle_counts["carol"] == 1
        assert mock_nudge.call_count == 1  # no second nudge

    print("\n  Worker resumed activity: idle counter correctly reset to 0")
