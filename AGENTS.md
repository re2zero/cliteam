# ClawTeam - Agent Development Guide

This document provides build/lint/test commands and code style guidelines for agentic coding agents working in this repository.

## Build, Lint, and Test Commands

### Installation
```bash
# Install from source (editable mode)
pip install -e .

# Install with P2P transport support
pip install -e ".[p2p]"

# Install development dependencies
pip install -e ".[dev]"
```

### Running Tests
```bash
# Run all tests
pytest

# Run a specific test file
pytest tests/test_spawn_backends.py

# Run a specific test function
pytest tests/test_spawn_backends.py::test_spawn_creates_block

# Run with verbose output
pytest -v

# Run with coverage
pytest --cov=clawteam --cov-report=html
```

### Linting and Formatting
```bash
# Check code style
ruff check .

# Check specific file
ruff check clawteam/spawn/tmux_backend.py

# Auto-fix issues where possible
ruff check --fix .

# Format code
ruff format .

# Format specific file
ruff format clawteam/spawn/wsh_backend.py
```

### Configuration
- **Python version**: 3.10+
- **Line length**: 100 characters (ruff configuration)
- **Type checker**: No mypy configured currently
- **Test framework**: pytest
- **Linter**: ruff (E, F, I, N, W rules)

## Code Style Guidelines

### Imports and Type Annotations

```python
from __future__ import annotations  # Required at top of every file

# Standard library imports first
import os
import json
from pathlib import Path

# Third-party imports second
import pytest
from pydantic import BaseModel, Field

# Local imports last
from clawteam.spawn.base import SpawnBackend
from clawteam.team.models import get_data_dir

# Type annotations (PEP 585)
def spawn(
    command: list[str],
    agent_name: str,
    team_name: str,
    prompt: str | None = None,  # Use | instead of Optional
    env: dict[str, str] | None = None,  # Use | instead of Optional
) -> str:
    ...
```

**Rules:**
- Always include `from __future__ import annotations` at file top
- Use `str | None` instead of `Optional[str]`
- Use `list[str]` instead of `List[str]`
- Use `dict[str, str]` instead of `Dict[str, str]`
- Import order: stdlib → third-party → local

### Naming Conventions

```python
# Classes: PascalCase
class SpawnBackend(ABC):
    ...

class TmuxBackend(SpawnBackend):
    ...

class WshRpcClient:
    ...

# Functions and variables: snake_case
def spawn_agent(command: list[str], team_name: str) -> str:
    ...

def is_agent_alive(team_name: str, agent_name: str) -> bool:
    ...

agent_name = "alice"
team_config = {}
block_id = "uuid-string"

# Constants: UPPER_SNAKE_CASE
_SHELL_ENV_KEY_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*\Z")
DEFAULT_TIMEOUT = 30.0
SOCKET_PATH = Path.home() / ".local/share/tideterm/tideterm.sock"

# Private module members: leading underscore
def _internal_helper():
    ...

class Backend:
    def __init__(self):
        self._internal_state = {}  # Private instance variable
```

### Error Handling

```python
# Try-except with specific exceptions
def load_config() -> ClawTeamConfig:
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        return ClawTeamConfig.model_validate(data)
    except Exception:  # Broad exception OK for logging/defaults
        return ClawTeamConfig()

# Process-specific exceptions
try:
    os.kill(pid, signal.SIGTERM)
except ProcessLookupError:
    pass  # Process doesn't exist
except PermissionError:
    return False  # Can't signal the process
```

**Rules:**
- Use specific exceptions when possible
- Use broad `Exception` for logging/fallback scenarios
- Don't silently suppress exceptions without documentation
- Return error strings from CLI commands (don't raise for user-facing errors)

### File and Atomic Operations

```python
# Atomic file writes (crash-safe)
def save_config(cfg: ClawTeamConfig) -> None:
    p = config_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".tmp")
    tmp.write_text(cfg.model_dump_json(indent=2), encoding="utf-8")
    tmp.rename(p)  # Atomic operation

# Atomic writes for JSON
def _save(path: Path, data: dict) -> None:
    import tempfile
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(data, f, indent=2)
        Path(tmp).replace(path)  # Atomic replace
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise
```

**Rules:**
- Use `path.replace()` for atomic file operations
- Use temporary files with `.tmp` suffix
- Clean up temporary files on error
- Use `missing_ok=True` for unlink operations

### Documentation Strings

```python
"""Module-level docstring.

Keep it concise. One or two sentences.
"""

class SpawnBackend(ABC):
    """Base class for different ways to spawn team agents."""

    @abstractmethod
    def spawn(self, command: list[str], agent_name: str, ...) -> str:
        """Spawn a new agent process. Returns a status message.

        Args:
            command: Command to execute.
            agent_name: Name for the agent.

        Returns:
            Status message string.
        """
```

**Rules:**
- Use triple double-quotes for docstrings
- Keep docstrings concise
- Document Args and Returns for public functions
- Don't document obvious parameters (e.g., "self")

### Pydantic Models

```python
from pydantic import BaseModel, Field

class ClawTeamConfig(BaseModel):
    data_dir: str = ""
    transport: str = ""
    default_backend: str = "tmux"
    spawn_ready_timeout: float = 30.0
    profiles: dict[str, AgentProfile] = Field(default_factory=dict)
```

**Rules:**
- Use `Field(default_factory=list)` instead of `default=[]` to avoid mutable defaults
- Use simple type hints (str, int, float, bool) where possible
- Use dict/list type hints instead of Dict/List from typing

### Subprocess Calls

```python
import subprocess
import shlex

# Capture output
result = subprocess.run(
    ["tmux", "list-panes", "-t", target, "-F", "#{pane_pid}"],
    capture_output=True,
    text=True,
)

# Check returncode
if result.returncode != 0:
    return f"Error: {result.stderr.strip()}"

# Parse output
stdout = result.stdout.strip()
if stdout:
    try:
        pid = int(stdout.splitlines()[0])
    except ValueError:
        pass

# Discard output
subprocess.run(
    ["tmux", "kill-window", "-t", target],
    stdout=subprocess.DEVNULL,
    stderr=subprocess.DEVNULL,
)

# Shell commands with quoting
cmd_str = " ".join(shlex.quote(c) for c in command)
subprocess.run(["sh", "-c", cmd_str])
```

**Rules:**
- Use `capture_output=True` and `text=True` for most cases
- Use `DEVNULL` for commands where output is irrelevant
- Check `returncode` before using stdout
- Use `shlex.quote()` for shell command construction
- Use `text=True` (Python 3.7+) instead of `universal_newlines=True`

### Configuration and Environment Variables

```python
import os
from pathlib import Path

# Environment variable with default
data_dir = os.environ.get("CLAWTEAM_DATA_DIR", "~/.clawteam")

# Path handling
config_path = Path.home() / ".clawteam" / "config.json"
if not config_path.exists():
    return ClawTeamConfig()

# Priority: env var > config file > default
env_val = os.environ.get("CLAWTEAM_TRANSPORT")
if env_val:
    return env_val

cfg = load_config()
file_val = cfg.transport
if file_val:
    return file_val

return "file"  # default
```

**Rules:**
- Use `Path.home()` instead of `~/` expansion
- Check `path.exists()` before reading
- Use `os.environ.get()` with default for env vars
- Document config priority: env var > config file > default

### Testing Patterns

```python
import pytest

# Fixture (conftest.py)
@pytest.fixture(autouse=True)
def isolated_data_dir(tmp_path, monkeypatch):
    """Point CLAWTEAM_DATA_DIR at a temp dir."""
    data_dir = tmp_path / ".clawteam"
    data_dir.mkdir()
    monkeypatch.setenv("CLAWTEAM_DATA_DIR", str(data_dir))
    return data_dir

# Test function
def test_spawn_creates_block(tmp_path):
    """Test that spawn creates a tmux pane."""
    backend = TmuxBackend()
    result = backend.spawn(...)
    assert "spawned in tmux" in result.lower()

# Test error cases
def test_spawn_fails_without_tmux(monkeypatch):
    """Test spawn fails gracefully without tmux."""
    monkeypatch.setattr(shutil, "which", lambda _: None)
    backend = TmuxBackend()
    result = backend.spawn(...)
    assert "not installed" in result.lower()
```

**Rules:**
- Use `tmp_path` fixture for temporary files
- Use `monkeypatch` fixture for mocking
- Test both success and error paths
- Write descriptive docstrings for tests
- Keep tests isolated (autouse fixtures for shared setup)

## Project Structure

```
clawteam/
├── __init__.py           # Package init
├── config.py            # Configuration management
├── cli/                 # CLI commands
│   ├── commands.py       # Main typer app
│   └── __init__.py
├── spawn/               # Agent spawn backends
│   ├── base.py          # SpawnBackend abstract class
│   ├── tmux_backend.py  # Tmux implementation
│   ├── subprocess_backend.py
│   ├── registry.py       # Agent process registry
│   └── __init__.py     # get_backend() factory
├── team/                # Team management
│   ├── models.py        # Data models
│   ├── tasks.py         # Task tracking
│   └── ...
├── workspace/           # Git worktree management
└── transport/           # Message transport (file/P2P)

tests/
├── conftest.py          # Shared fixtures
├── test_spawn_backends.py
└── ...
```

## Key Patterns

### Backend Factory Pattern

```python
def get_backend(name: str = "tmux") -> SpawnBackend:
    """Factory function to get a spawn backend by name."""
    if name == "subprocess":
        from clawteam.spawn.subprocess_backend import SubprocessBackend
        return SubprocessBackend()
    elif name == "tmux":
        from clawteam.spawn.tmux_backend import TmuxBackend
        return TmuxBackend()
    elif name == "wsh":
        from clawteam.spawn.wsh_backend import WshBackend
        return WshBackend()
    else:
        raise ValueError(f"Unknown spawn backend: {name}")
```

### Registry Integration

```python
from clawteam.spawn.registry import register_agent

# After spawning, record in registry
register_agent(
    team_name=team_name,
    agent_name=agent_name,
    backend="tmux",  # or "wsh", "subprocess"
    tmux_target=target,  # or block_id for wsh
    pid=pane_pid,
    command=list(final_command),
)
```

### Session Naming

- tmux: `clawteam-{team_name}`
- wsh: workspace-based, tracked via metadata
- subprocess: tracked by PID only

## Common Gotchas

1. **Mutable default arguments**: Always use `Field(default_factory=list)` for Pydantic models
2. **Path handling**: Use `Path` objects, resolve with `expanduser()` before use
3. **Shell escaping**: Use `shlex.quote()` when building shell commands
4. **Atomic writes**: Always write to `.tmp` file then `rename()` for crash safety
5. **Type annotations**: Use `str | None` not `Optional[str]` (requires `from __future__ import annotations`)
6. **Subprocess output**: Always check `returncode` before using `stdout`
7. **Environment variables**: Use `os.environ.get()` with defaults, document precedence
