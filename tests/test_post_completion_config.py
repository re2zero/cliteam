"""Test post-completion configuration system."""

import pytest
from pathlib import Path
from clawteam.config import (
    PostCompletionConfig,
    ReviewConfig,
    FeedbackConfig,
    OptimizationConfig,
    PostCompletionSettings,
    load_post_completion_config,
    is_post_completion_enabled,
    is_review_enabled,
    is_review_auto_launch,
    get_review_template,
    is_feedback_enabled,
    is_feedback_auto_collect,
    get_feedback_collect_types,
    get_feedback_store_backend,
    is_optimization_enabled,
    get_optimization_interval_hours,
    get_optimization_mode,
    are_optimization_suggestions_enabled,
)


def test_post_completion_config_defaults():
    """Test that default configuration values are correct."""
    config = PostCompletionConfig()
    assert config.enabled is True


def test_review_config_defaults():
    """Test that default review configuration values are correct."""
    config = ReviewConfig()
    assert config.enabled is True
    assert config.team_template == "code-review"
    assert config.trigger_conditions == ["task_completed"]
    assert config.auto_launch is True


def test_feedback_config_defaults():
    """Test that default feedback configuration values are correct."""
    config = FeedbackConfig()
    assert config.enabled is True
    assert config.collect_types == ["user_rating", "performance", "quality", "completion_time"]
    assert config.auto_collect is True
    assert config.store_backend == "file"


def test_optimization_config_defaults():
    """Test that default optimization configuration values are correct."""
    config = OptimizationConfig()
    assert config.enabled is True
    assert config.analysis_interval_hours == 24
    assert config.optimization_mode == "auto"
    assert config.suggestions_enabled is True


def test_post_completion_settings_defaults():
    """Test that default post-completion settings are correct."""
    settings = PostCompletionSettings()
    assert settings.post_completion.enabled is True
    assert settings.review.enabled is True
    assert settings.feedback.enabled is True
    assert settings.optimization.enabled is True


def test_load_post_completion_config():
    """Test loading post-completion configuration from file."""
    # This test assumes the post-completion.toml file exists
    # If it doesn't, the function should return defaults
    config = load_post_completion_config()
    assert isinstance(config, PostCompletionSettings)
    assert config.post_completion.enabled is True
    assert config.review.enabled is True
    assert config.feedback.enabled is True
    assert config.optimization.enabled is True


def test_is_post_completion_enabled():
    """Test checking if post-completion is enabled."""
    # Should return True by default
    assert is_post_completion_enabled() is True


def test_is_review_enabled():
    """Test checking if review is enabled."""
    # Should return True by default
    assert is_review_enabled() is True


def test_is_review_auto_launch():
    """Test checking if review auto-launch is enabled."""
    # Should return True by default
    assert is_review_auto_launch() is True


def test_get_review_template():
    """Test getting review template name."""
    # Should return "code-review" by default
    assert get_review_template() == "code-review"


def test_is_feedback_enabled():
    """Test checking if feedback is enabled."""
    # Should return True by default
    assert is_feedback_enabled() is True


def test_is_feedback_auto_collect():
    """Test checking if feedback auto-collect is enabled."""
    # Should return True by default
    assert is_feedback_auto_collect() is True


def test_get_feedback_collect_types():
    """Test getting feedback collect types."""
    # Should return default types
    types = get_feedback_collect_types()
    assert types == ["user_rating", "performance", "quality", "completion_time"]


def test_get_feedback_store_backend():
    """Test getting feedback store backend."""
    # Should return "file" by default
    assert get_feedback_store_backend() == "file"


def test_is_optimization_enabled():
    """Test checking if optimization is enabled."""
    # Should return True by default
    assert is_optimization_enabled() is True


def test_get_optimization_interval_hours():
    """Test getting optimization interval hours."""
    # Should return 24 by default
    assert get_optimization_interval_hours() == 24


def test_get_optimization_mode():
    """Test getting optimization mode."""
    # Should return "auto" by default
    assert get_optimization_mode() == "auto"


def test_are_optimization_suggestions_enabled():
    """Test checking if optimization suggestions are enabled."""
    # Should return True by default
    assert are_optimization_suggestions_enabled() is True


def test_post_completion_settings_from_dict():
    """Test creating PostCompletionSettings from dictionary."""
    data = {
        "post_completion": {"enabled": False},
        "review": {"enabled": False, "team_template": "custom-review"},
        "feedback": {"enabled": False, "collect_types": ["custom_type"]},
        "optimization": {"enabled": False, "analysis_interval_hours": 48},
    }
    settings = PostCompletionSettings(**data)
    assert settings.post_completion.enabled is False
    assert settings.review.enabled is False
    assert settings.review.team_template == "custom-review"
    assert settings.feedback.enabled is False
    assert settings.feedback.collect_types == ["custom_type"]
    assert settings.optimization.enabled is False
    assert settings.optimization.analysis_interval_hours == 48
