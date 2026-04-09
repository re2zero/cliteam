"""Completion handler for task completion events."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Callable

from clawteam.config import (
    is_post_completion_enabled,
    is_review_enabled,
    is_review_auto_launch,
    is_feedback_enabled,
    is_feedback_auto_collect,
)
from clawteam.store.feedback import FeedbackItem
from clawteam.team.models import TaskItem

logger = logging.getLogger(__name__)


class CompletionHandler:
    """Handles task completion events and triggers post-completion processes."""

    def __init__(self):
        self._post_completion_hooks: list[Callable] = []

    async def handle_completion(self, task: TaskItem, team_name: str) -> None:
        """Handle task completion logic.

        Args:
            task: The completed task item
            team_name: Name of the team the task belongs to
        """
        logger.info(f"Handling completion for task {task.id} in team {team_name}")

        # Check if post-completion is enabled
        if not is_post_completion_enabled():
            logger.debug("Post-completion is disabled, skipping all post-completion processes")
            return

        # Trigger post-completion hooks
        for hook in self._post_completion_hooks:
            try:
                await hook(task, team_name)
            except Exception as e:
                logger.error(f"Error in post-completion hook: {e}")

        # Trigger review launcher if enabled and available
        if is_review_enabled() and is_review_auto_launch():
            try:
                from clawteam.team.review import ReviewLauncher
                review_launcher = ReviewLauncher()
                # Assume code_paths are in task metadata or description
                code_paths = task.metadata.get("code_paths", [])
                if code_paths:
                    review_id = await review_launcher.launch_review(team_name, task.id, code_paths)
                    logger.info(f"Launched review {review_id} for task {task.id}")
                else:
                    logger.debug("No code_paths found in task metadata, skipping review launch")
            except ImportError:
                logger.debug("ReviewLauncher not available, skipping review launch")
            except Exception as e:
                logger.error(f"Error launching review: {e}")
        else:
            logger.debug("Review is disabled or auto-launch is off, skipping review launch")

        # Handle feedback process if enabled
        if is_feedback_enabled() and is_feedback_auto_collect():
            try:
                from clawteam.store.feedback import FeedbackStore
                feedback_store = FeedbackStore(team_name)
                # Store completion feedback
                feedback = FeedbackItem(
                    task_id=task.id,
                    feedback_type="completion",
                    content={"status": "completed", "timestamp": task.updated_at},
                    timestamp=datetime.now(timezone.utc),
                    source="system"
                )
                feedback_store.store_feedback(feedback)
                logger.debug(f"Stored completion feedback for task {task.id}")
            except ImportError:
                logger.debug("FeedbackStore not available, skipping feedback storage")
            except Exception as e:
                logger.error(f"Error storing feedback: {e}")
        else:
            logger.debug("Feedback collection is disabled or auto-collect is off, skipping feedback storage")

    async def register_post_completion_hook(self, hook: Callable) -> None:
        """Register a hook to be called after task completion.

        Args:
            hook: Async callable that takes (task: TaskItem, team_name: str)
        """
        self._post_completion_hooks.append(hook)
        logger.debug(f"Registered post-completion hook: {hook}")