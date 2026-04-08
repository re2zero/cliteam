"""Team template loader — load TOML templates for one-command team launch."""

from __future__ import annotations

import re
import sys
from pathlib import Path

from pydantic import BaseModel

# TOML support: built-in on 3.11+, conditional dependency on 3.10
if sys.version_info >= (3, 11):
    import tomllib
else:
    try:
        import tomllib  # type: ignore[import-not-found]
    except ModuleNotFoundError:
        import tomli as tomllib  # type: ignore[import-not-found,no-redef]


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------


class AgentDef(BaseModel):
    name: str
    type: str = "general-purpose"
    task: str = ""
    command: list[str] | None = None


class TaskDef(BaseModel):
    subject: str
    description: str = ""
    owner: str = ""


class TemplateDef(BaseModel):
    name: str
    description: str = ""
    command: list[str] = ["claude"]
    backend: str = "tmux"
    leader: AgentDef
    agents: list[AgentDef] = []
    tasks: list[TaskDef] = []


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

_BUILTIN_DIR = Path(__file__).parent
_USER_DIR = Path.home() / ".clawteam" / "templates"


def ensure_user_templates(overwrite: bool = False) -> None:
    _USER_DIR.mkdir(parents=True, exist_ok=True)
    for src in _BUILTIN_DIR.glob("*.toml"):
        dst = _USER_DIR / src.name
        if overwrite or not dst.is_file():
            dst.write_bytes(src.read_bytes())


ensure_user_templates(overwrite=True)


# ---------------------------------------------------------------------------
# Variable substitution helper
# ---------------------------------------------------------------------------


class _SafeDict(dict):
    """dict subclass that keeps unknown {placeholders} intact."""

    def __missing__(self, key: str) -> str:
        return "{" + key + "}"


def render_task(task: str, **variables: str) -> str:
    """Replace {goal}, {team_name}, {agent_name} etc. in task text."""
    return task.format_map(_SafeDict(**variables))


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------


def _parse_toml(path: Path) -> TemplateDef:
    with open(path, "rb") as f:
        raw = tomllib.load(f)

    tmpl = raw.get("template", {})

    leader_data = tmpl.get("leader", {})
    leader = AgentDef(**leader_data)

    agents = [AgentDef(**a) for a in tmpl.get("agents", [])]
    tasks = [TaskDef(**t) for t in tmpl.get("tasks", [])]

    return TemplateDef(
        name=tmpl.get("name", path.stem),
        description=tmpl.get("description", ""),
        command=tmpl.get("command", ["claude"]),
        backend=tmpl.get("backend", "tmux"),
        leader=leader,
        agents=agents,
        tasks=tasks,
    )


def load_template(name: str) -> TemplateDef:
    filename = f"{name}.toml"

    user_path = _USER_DIR / filename
    if user_path.is_file():
        return _parse_toml(user_path)

    builtin_path = _BUILTIN_DIR / filename
    if builtin_path.is_file():
        return _parse_toml(builtin_path)

    raise FileNotFoundError(f"Template '{name}' not found. Searched: {_USER_DIR}, {_BUILTIN_DIR}")


def list_templates() -> list[dict[str, str]]:
    seen: dict[str, dict[str, str]] = {}

    if _BUILTIN_DIR.is_dir():
        for p in sorted(_BUILTIN_DIR.glob("*.toml")):
            try:
                tmpl = _parse_toml(p)
                seen[tmpl.name] = {
                    "name": tmpl.name,
                    "description": tmpl.description,
                    "source": "builtin",
                }
            except Exception:
                continue

    if _USER_DIR.is_dir():
        for p in sorted(_USER_DIR.glob("*.toml")):
            try:
                tmpl = _parse_toml(p)
                seen[tmpl.name] = {
                    "name": tmpl.name,
                    "description": tmpl.description,
                    "source": "user",
                }
            except Exception:
                continue

    return list(seen.values())


# ---------------------------------------------------------------------------
# Project detection — deterministic template suggestion
# ---------------------------------------------------------------------------

_DDE_SIGNALS = [
    re.compile(r"find_package\s*\(\s*DTK", re.IGNORECASE),
    re.compile(r"find_package\s*\(\s*Qt\d", re.IGNORECASE),
    re.compile(r"find_package\s*\(\s*deepin", re.IGNORECASE),
    re.compile(r"\bdtkcore\b"),
    re.compile(r"\bdtkwidget\b"),
    re.compile(r"\bdtkgui\b"),
    re.compile(r"\bdde-"),
]

_DTE_SIGNALS = [
    re.compile(r"include\s*\(\s*\$\{DtkCMake\}"),
    re.compile(r"\bDtkCMake\b"),
]


def _read_file(path: Path, max_bytes: int = 32_000) -> str | None:
    if not path.is_file() or path.stat().st_size > max_bytes:
        return None
    try:
        return path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return None


def _scan_cmake(project_dir: Path) -> bool:
    top_cmake = project_dir / "CMakeLists.txt"
    content = _read_file(top_cmake)
    if content is None:
        return False
    for pattern in _DDE_SIGNALS:
        if pattern.search(content):
            return True
    for pattern in _DTE_SIGNALS:
        if pattern.search(content):
            return True
    return False


def _scan_debian_control(project_dir: Path) -> bool:
    for candidate in (
        project_dir / "debian" / "control",
        project_dir / "debian" / "control.in",
    ):
        content = _read_file(candidate)
        if content is None:
            continue
        for pattern in _DDE_SIGNALS:
            if pattern.search(content):
                return True
    return False


def _scan_source_files(project_dir: Path) -> bool:
    include_exts = {".h", ".hpp", ".cpp", ".cc", ".cxx"}
    for candidate in (
        project_dir / "src",
        project_dir / "lib",
        project_dir / "include",
    ):
        if not candidate.is_dir():
            continue
        checked = 0
        for p in candidate.rglob("*"):
            if checked >= 30:
                break
            if p.suffix not in include_exts:
                continue
            content = _read_file(p)
            if content is None:
                continue
            for pattern in _DDE_SIGNALS:
                if pattern.search(content):
                    return True
            checked += 1
    return False


def suggest_template(project_dir: str | Path) -> dict[str, str | list[str]]:
    """Deterministically suggest the best template for a project.

    Returns {"template": "<name>", "confidence": "high"|"low", "signals": ["..."]}.
    """
    root = Path(project_dir).resolve()
    signals: list[str] = []

    if _scan_cmake(root):
        signals.append("CMakeLists.txt contains DTK/Qt/deepin references")

    if not signals and _scan_debian_control(root):
        signals.append("debian/control contains DTK/deepin dependencies")

    if not signals and _scan_source_files(root):
        signals.append("source files contain DTK references")

    if signals:
        return {
            "template": "dde-trellis",
            "confidence": "high",
            "signals": signals,
        }

    return {
        "template": "software-dev",
        "confidence": "low",
        "signals": ["no DDE/DTK signals detected, using default"],
    }


def smart_select_template(project_dir: str | Path) -> str:
    """Smart template selection: suggest-first approach.

    Uses deterministic suggestion first. High confidence templates are returned
    immediately without LLM involvement. Low confidence returns the default template.

    This minimizes unnecessary LLM calls while providing consistent results for
    well-defined project types (e.g., DDE projects).

    Args:
        project_dir: Path to the project directory.

    Returns:
        Template name to use.
    """
    suggestion = suggest_template(project_dir)
    return str(suggestion["template"])
