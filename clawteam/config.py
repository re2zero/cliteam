"""Persistent configuration for ClawTeam."""

from __future__ import annotations

import json
import logging
import os
import sys
from pathlib import Path

from pydantic import BaseModel, Field

from clawteam.fileutil import atomic_write_text

logger = logging.getLogger(__name__)

# TOML support: built-in on 3.11+, conditional dependency on 3.10
if sys.version_info >= (3, 11):
    import tomllib
else:
    try:
        import tomllib  # type: ignore[import-not-found]
    except ModuleNotFoundError:
        import tomli as tomllib  # type: ignore[import-not-found,no-redef]


class AgentProfile(BaseModel):
    """Reusable agent runtime profile for spawn/launch."""

    description: str = ""
    agent: str = ""
    command: list[str] = Field(default_factory=list)
    model: str = ""
    base_url: str = ""
    base_url_env: str = ""
    api_key_env: str = ""
    api_key_target_env: str = ""
    env: dict[str, str] = Field(default_factory=dict)
    env_map: dict[str, str] = Field(default_factory=dict)
    args: list[str] = Field(default_factory=list)


class AgentPreset(BaseModel):
    """Shared preset input for generating client-scoped profiles."""

    description: str = ""
    auth_env: str = ""
    base_url: str = ""
    env: dict[str, str] = Field(default_factory=dict)
    client_overrides: dict[str, AgentProfile] = Field(default_factory=dict)


class ClawTeamConfig(BaseModel):
    data_dir: str = ""
    user: str = ""
    default_team: str = ""
    default_profile: str = ""
    transport: str = ""
    task_store: str = ""  # "file" (default) — extensible for redis/sql later
    workspace: str = "auto"  # "auto" | "always" | "never" | ""
    default_backend: str = "tmux"  # "tmux" | "subprocess"
    skip_permissions: bool = True  # pass --dangerously-skip-permissions to claude
    timezone: str = "UTC"  # display timezone for human-readable timestamps
    gource_path: str = ""  # custom path to gource binary (auto-detected if empty)
    gource_resolution: str = "1280x720"  # default viewport resolution
    gource_seconds_per_day: float = 0.5  # animation speed
    profiles: dict[str, AgentProfile] = Field(default_factory=dict)
    presets: dict[str, AgentPreset] = Field(default_factory=dict)
    spawn_prompt_delay: float = 2.0  # fallback wait (seconds) if TUI ready-detection times out
    spawn_ready_timeout: float = 30.0  # max seconds to poll for TUI readiness before fallback
    idle_timeout: float = 60.0  # seconds of no output before considering worker idle
    nudge_enabled: bool = True  # send terminal nudge to idle workers before respawn
    nudge_delay: float = 10.0  # seconds of stable output before nudge (must be < idle_timeout)


def config_path() -> Path:
    """Fixed config location: ~/.clawteam/config.json (never affected by data_dir)."""
    return Path.home() / ".clawteam" / "config.json"


def load_config() -> ClawTeamConfig:
    """Load config from disk. Returns defaults if file doesn't exist."""
    p = config_path()
    if not p.exists():
        return ClawTeamConfig()
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        return ClawTeamConfig.model_validate(data)
    except Exception:
        return ClawTeamConfig()


def save_config(cfg: ClawTeamConfig) -> None:
    """Atomically write config to disk (mkstemp + replace)."""
    atomic_write_text(config_path(), cfg.model_dump_json(indent=2))


def get_effective(key: str) -> tuple[str, str]:
    """Get effective value for a config key. Returns (value, source).

    Priority: env var > config file > default.
    """
    env_map = {
        "data_dir": "CLAWTEAM_DATA_DIR",
        "user": "CLAWTEAM_USER",
        "default_team": "CLAWTEAM_TEAM_NAME",
        "default_profile": "CLAWTEAM_DEFAULT_PROFILE",
        "transport": "CLAWTEAM_TRANSPORT",
        "task_store": "CLAWTEAM_TASK_STORE",
        "workspace": "CLAWTEAM_WORKSPACE",
        "default_backend": "CLAWTEAM_DEFAULT_BACKEND",
        "skip_permissions": "CLAWTEAM_SKIP_PERMISSIONS",
        "timezone": "CLAWTEAM_TIMEZONE",
        "gource_path": "CLAWTEAM_GOURCE_PATH",
        "gource_resolution": "CLAWTEAM_GOURCE_RESOLUTION",
        "gource_seconds_per_day": "CLAWTEAM_GOURCE_SECONDS_PER_DAY",
        "spawn_prompt_delay": "CLAWTEAM_SPAWN_PROMPT_DELAY",
        "spawn_ready_timeout": "CLAWTEAM_SPAWN_READY_TIMEOUT",
        "idle_timeout": "CLAWTEAM_IDLE_TIMEOUT",
        "nudge_enabled": "CLAWTEAM_NUDGE_ENABLED",
        "nudge_delay": "CLAWTEAM_NUDGE_DELAY",
    }
    defaults = ClawTeamConfig()
    cfg = load_config()

    env_key = env_map.get(key)
    if env_key:
        env_val = os.environ.get(env_key)
        if env_val:
            return env_val, "env"

    file_val = getattr(cfg, key, "")
    default_val = getattr(defaults, key, "")
    if file_val != default_val:
        return str(file_val), "file"

    return str(default_val), "default"


def scalar_config_keys() -> list[str]:
    """Return user-facing scalar config keys (excluding nested structures)."""
    return [key for key in ClawTeamConfig.model_fields.keys() if key not in {"profiles", "presets"}]


# ---------------------------------------------------------------------------
# Post-completion configuration
# ---------------------------------------------------------------------------


class PostCompletionConfig(BaseModel):
    """Configuration for post-completion automation."""

    enabled: bool = True


class ReviewConfig(BaseModel):
    """Configuration for automated code review."""

    enabled: bool = True
    team_template: str = "code-review"
    trigger_conditions: list[str] = Field(default_factory=lambda: ["task_completed"])
    auto_launch: bool = True


class FeedbackConfig(BaseModel):
    """Configuration for feedback collection."""

    enabled: bool = True
    collect_types: list[str] = Field(default_factory=lambda: ["user_rating", "performance", "quality", "completion_time"])
    auto_collect: bool = True
    store_backend: str = "file"


class OptimizationConfig(BaseModel):
    """Configuration for optimization engine."""

    enabled: bool = True
    analysis_interval_hours: int = 24
    optimization_mode: str = "auto"
    suggestions_enabled: bool = True


class PostCompletionSettings(BaseModel):
    """Complete post-completion settings."""

    post_completion: PostCompletionConfig = Field(default_factory=PostCompletionConfig)
    review: ReviewConfig = Field(default_factory=ReviewConfig)
    feedback: FeedbackConfig = Field(default_factory=FeedbackConfig)
    optimization: OptimizationConfig = Field(default_factory=OptimizationConfig)


def post_completion_config_path() -> Path:
    """Get the path to the post-completion.toml configuration file."""
    return Path.home() / ".clawteam" / "templates" / "post-completion.toml"


def load_post_completion_config() -> PostCompletionSettings:
    """Load post-completion configuration from TOML file.
    
    Returns default configuration if file doesn't exist or parsing fails.
    """
    config_path = post_completion_config_path()
    
    if not config_path.exists():
        return PostCompletionSettings()
    
    try:
        with open(config_path, "rb") as f:
            raw = tomllib.load(f)
        
        # Parse post_completion section
        post_completion_data = raw.get("post_completion", {})
        post_completion = PostCompletionConfig(**post_completion_data)
        
        # Parse review section
        review_data = raw.get("review", {})
        review = ReviewConfig(**review_data)
        
        # Parse feedback section
        feedback_data = raw.get("feedback", {})
        feedback = FeedbackConfig(**feedback_data)
        
        # Parse optimization section
        optimization_data = raw.get("optimization", {})
        optimization = OptimizationConfig(**optimization_data)
        
        return PostCompletionSettings(
            post_completion=post_completion,
            review=review,
            feedback=feedback,
            optimization=optimization,
        )
    except Exception as e:
        # Log error and return defaults
        logger.warning(f"Failed to load post-completion config: {e}, using defaults")
        return PostCompletionSettings()


def is_post_completion_enabled() -> bool:
    """Check if post-completion automation is enabled."""
    config = load_post_completion_config()
    return config.post_completion.enabled


def is_review_enabled() -> bool:
    """Check if automated code review is enabled."""
    config = load_post_completion_config()
    return config.review.enabled


def is_review_auto_launch() -> bool:
    """Check if review should auto-launch on task completion."""
    config = load_post_completion_config()
    return config.review.auto_launch


def get_review_template() -> str:
    """Get the review team template name."""
    config = load_post_completion_config()
    return config.review.team_template


def is_feedback_enabled() -> bool:
    """Check if feedback collection is enabled."""
    config = load_post_completion_config()
    return config.feedback.enabled


def is_feedback_auto_collect() -> bool:
    """Check if feedback should be auto-collected."""
    config = load_post_completion_config()
    return config.feedback.auto_collect


def get_feedback_collect_types() -> list[str]:
    """Get the types of feedback to collect."""
    config = load_post_completion_config()
    return config.feedback.collect_types


def get_feedback_store_backend() -> str:
    """Get the feedback storage backend."""
    config = load_post_completion_config()
    return config.feedback.store_backend


def is_optimization_enabled() -> bool:
    """Check if optimization engine is enabled."""
    config = load_post_completion_config()
    return config.optimization.enabled


def get_optimization_interval_hours() -> int:
    """Get the optimization analysis interval in hours."""
    config = load_post_completion_config()
    return config.optimization.analysis_interval_hours


def get_optimization_mode() -> str:
    """Get the optimization mode."""
    config = load_post_completion_config()
    return config.optimization.optimization_mode


def are_optimization_suggestions_enabled() -> bool:
    """Check if optimization suggestions are enabled."""
    config = load_post_completion_config()
    return config.optimization.suggestions_enabled
