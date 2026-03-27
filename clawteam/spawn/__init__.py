"""Spawn backends for launching team agents."""

from __future__ import annotations

import os
import shutil
import socket
from pathlib import Path

from clawteam.spawn.base import SpawnBackend


def _find_wsh() -> str | None:
    """Find wsh executable via PATH or known locations."""
    found = shutil.which("wsh")
    if found:
        return found
    for p in [
        Path.home() / ".local/share/tideterm/bin/wsh",
        Path.home() / ".local/state/waveterm/bin/wsh",
    ]:
        if p.is_file() and os.access(p, os.X_OK):
            return str(p)
    return None


def _wsh_is_connected() -> bool:
    """Check if TideTerm server is reachable."""
    socket_path = Path.home() / ".local/share/tideterm/tideterm.sock"
    if not socket_path.exists():
        socket_path = Path.home() / ".local/state/waveterm/tideterm.sock"
    if not socket_path.exists():
        return False
    try:
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.settimeout(1.0)
        sock.connect(str(socket_path))
        sock.close()
        return True
    except (socket.error, socket.timeout, OSError):
        return False


def get_backend(name: str = "auto") -> SpawnBackend:
    """Factory function to get a spawn backend by name.

    Args:
        name: Backend name ("auto", "tmux", "wsh", "subprocess").
              "auto" selects wsh > tmux > subprocess by availability.

    Returns:
        SpawnBackend instance.

    Raises:
        ValueError: If backend name is unknown.
    """
    if name == "auto":
        if _find_wsh() and _wsh_is_connected():
            from clawteam.spawn.wsh_backend import WshBackend

            return WshBackend()
        elif shutil.which("tmux"):
            from clawteam.spawn.tmux_backend import TmuxBackend

            return TmuxBackend()
        else:
            from clawteam.spawn.subprocess_backend import SubprocessBackend

            return SubprocessBackend()
    elif name == "wsh":
        from clawteam.spawn.wsh_backend import WshBackend

        return WshBackend()
    elif name == "subprocess":
        from clawteam.spawn.subprocess_backend import SubprocessBackend

        return SubprocessBackend()
    elif name == "tmux":
        from clawteam.spawn.tmux_backend import TmuxBackend

        return TmuxBackend()
    else:
        raise ValueError(f"Unknown spawn backend: {name}. Available: auto, tmux, wsh, subprocess")


__all__ = ["SpawnBackend", "get_backend"]
