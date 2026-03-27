from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from clawteam.team.mailbox import MailboxManager
from clawteam.team.models import TaskItem, TaskStatus
from clawteam.team.tasks import TaskStore
from clawteam.team.waiter import TaskWaiter


def _make_waiter(
    team_name: str = "test-team",
    poll_interval: float = 5.0,
) -> TaskWaiter:
    mailbox = MailboxManager(team_name)
    task_store = TaskStore(team_name)
    return TaskWaiter(
        team_name=team_name,
        agent_name="leader",
        mailbox=mailbox,
        task_store=task_store,
        poll_interval=poll_interval,
    )


def test_idle_counter_resets_on_new_output(team_name):
    waiter = _make_waiter(team_name)
    waiter._output_hashes["alice"] = "hash1"
    waiter._idle_counts["alice"] = 3

    with (
        patch("clawteam.config.load_config", return_value=MagicMock(idle_timeout=60.0)),
        patch("clawteam.spawn.registry.get_registry") as mock_reg,
        patch.object(waiter, "_capture_wsh_output", return_value="new content"),
    ):
        mock_reg.return_value = {
            "alice": {"backend": "wsh", "block_id": "block-1", "command": ["claude"]},
        }
        waiter._check_idle_agents()

    assert waiter._idle_counts["alice"] == 0
    assert waiter._output_hashes["alice"] == hash("new content")


def test_idle_triggers_at_threshold(team_name):
    waiter = _make_waiter(team_name, poll_interval=5.0)
    initial_hash = hash("stable content")
    waiter._output_hashes["alice"] = initial_hash
    waiter._idle_counts["alice"] = 0

    with (
        patch("clawteam.config.load_config", return_value=MagicMock(idle_timeout=5.0)),
        patch("clawteam.spawn.registry.get_registry") as mock_reg,
        patch.object(waiter, "_capture_wsh_output", return_value="stable content"),
        patch.object(waiter, "_respawn_idle_worker") as mock_respawn,
    ):
        mock_reg.return_value = {
            "alice": {"backend": "wsh", "block_id": "block-1", "command": ["claude"]},
        }
        waiter._check_idle_agents()

    mock_respawn.assert_called_once()
    assert waiter._idle_counts["alice"] == 1


def test_respawn_stops_and_spawns(team_name):
    waiter = _make_waiter(team_name)
    spawn_info = {
        "backend": "wsh",
        "block_id": "block-1",
        "command": ["claude", "--prompt", "do task"],
    }

    waiter.task_store.create(subject="Build feature", owner="alice")
    tasks = waiter.task_store.list_tasks()
    waiter.task_store.update(tasks[0].id, status=TaskStatus.completed)
    waiter.task_store.create(subject="Write tests", owner="alice")

    cfg = MagicMock(idle_timeout=60.0)

    with (
        patch("clawteam.spawn.registry.stop_agent", return_value=True),
        patch("clawteam.spawn.get_backend") as mock_get_backend,
        patch("clawteam.team.manager.TeamManager.get_leader_name", return_value="leader"),
        patch.object(waiter.mailbox, "send"),
    ):
        mock_backend = MagicMock()
        mock_backend.spawn.return_value = "spawned"
        mock_get_backend.return_value = mock_backend

        waiter._respawn_idle_worker("alice", spawn_info, cfg)

    mock_backend.spawn.assert_called_once()
    call_kwargs = mock_backend.spawn.call_args.kwargs
    assert call_kwargs["agent_name"] == "alice"
    assert call_kwargs["team_name"] == team_name
    assert "Write tests" in call_kwargs.get("prompt", "")
    assert "Worker Loop Protocol" in call_kwargs.get("prompt", "")


def test_respawn_skips_when_no_pending_tasks(team_name):
    waiter = _make_waiter(team_name)
    spawn_info = {"backend": "wsh", "block_id": "block-1", "command": ["claude"]}

    waiter.task_store.create(subject="Done task", owner="alice")
    tasks = waiter.task_store.list_tasks()
    waiter.task_store.update(tasks[0].id, status=TaskStatus.completed)

    cfg = MagicMock(idle_timeout=60.0)

    with patch("clawteam.spawn.registry.stop_agent", return_value=True) as mock_stop:
        waiter._respawn_idle_worker("alice", spawn_info, cfg)

    mock_stop.assert_called_once()
    assert "alice" not in waiter._respawned_agents


def test_idle_skips_non_wsh_backends(team_name):
    waiter = _make_waiter(team_name)

    with (
        patch("clawteam.config.load_config", return_value=MagicMock(idle_timeout=60.0)),
        patch("clawteam.spawn.registry.get_registry") as mock_reg,
        patch.object(waiter, "_capture_wsh_output") as mock_wsh,
        patch.object(waiter, "_capture_tmux_output") as mock_tmux,
    ):
        mock_reg.return_value = {
            "alice": {"backend": "subprocess", "pid": 123, "command": ["claude"]},
        }
        waiter._check_idle_agents()

    mock_wsh.assert_not_called()
    mock_tmux.assert_not_called()


def test_idle_skips_dead_agents(team_name):
    waiter = _make_waiter(team_name)
    waiter._known_dead.add("alice")

    with (
        patch("clawteam.config.load_config", return_value=MagicMock(idle_timeout=60.0)),
        patch("clawteam.spawn.registry.get_registry") as mock_reg,
        patch.object(waiter, "_capture_wsh_output") as mock_capture,
    ):
        mock_reg.return_value = {
            "alice": {"backend": "wsh", "block_id": "block-1", "command": ["claude"]},
        }
        waiter._check_idle_agents()

    mock_capture.assert_not_called()


def test_capture_wsh_output_returns_content(team_name):
    waiter = _make_waiter(team_name)

    with patch("clawteam.spawn.wsh_backend._capture_block_output", return_value="output") as mock:
        result = waiter._capture_wsh_output("block-1")

    assert result == "output"
    mock.assert_called_once_with("block-1")


def test_capture_wsh_output_returns_none_on_error(team_name):
    waiter = _make_waiter(team_name)

    with patch(
        "clawteam.spawn.wsh_backend._capture_block_output", side_effect=RuntimeError("fail")
    ):
        result = waiter._capture_wsh_output("block-1")

    assert result is None


def test_capture_wsh_output_returns_none_on_empty_id(team_name):
    waiter = _make_waiter(team_name)

    result = waiter._capture_wsh_output("")
    assert result is None


def test_capture_tmux_output_returns_content(team_name):
    waiter = _make_waiter(team_name)

    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="pane content")
        result = waiter._capture_tmux_output("sess:win")

    assert result == "pane content"
    mock_run.assert_called_once()


def test_capture_tmux_output_returns_none_on_error(team_name):
    waiter = _make_waiter(team_name)

    with patch("subprocess.run", side_effect=RuntimeError("fail")):
        result = waiter._capture_tmux_output("sess:win")

    assert result is None


def test_idle_detection_uses_tmux_backend(team_name):
    waiter = _make_waiter(team_name, poll_interval=5.0)
    initial_hash = hash("stable pane content")
    waiter._output_hashes["alice"] = initial_hash
    waiter._idle_counts["alice"] = 0

    with (
        patch("clawteam.config.load_config", return_value=MagicMock(idle_timeout=5.0)),
        patch("clawteam.spawn.registry.get_registry") as mock_reg,
        patch.object(waiter, "_capture_tmux_output", return_value="stable pane content"),
        patch.object(waiter, "_respawn_idle_worker") as mock_respawn,
    ):
        mock_reg.return_value = {
            "alice": {
                "backend": "tmux",
                "tmux_target": "sess:win",
                "command": ["claude"],
            },
        }
        waiter._check_idle_agents()

    mock_respawn.assert_called_once()
    waiter = _make_waiter(team_name)
    spawn_info = {"backend": "wsh", "block_id": "block-1", "command": ["claude"]}

    waiter.task_store.create(subject="Next task", owner="alice")
    waiter._output_hashes["alice"] = "old_hash"
    waiter._idle_counts["alice"] = 5

    cfg = MagicMock(idle_timeout=60.0)

    with (
        patch("clawteam.spawn.registry.stop_agent", return_value=True),
        patch("clawteam.spawn.get_backend") as mock_get_backend,
        patch("clawteam.team.manager.TeamManager.get_leader_name", return_value="leader"),
        patch.object(waiter.mailbox, "send"),
    ):
        mock_get_backend.return_value = MagicMock()
        waiter._respawn_idle_worker("alice", spawn_info, cfg)

    assert "alice" not in waiter._output_hashes
    assert "alice" not in waiter._idle_counts
    assert "alice" not in waiter._respawned_agents
