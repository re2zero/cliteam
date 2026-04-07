"""Review launcher for automated code review workflows."""

from __future__ import annotations

import asyncio
import logging
import uuid
from typing import Dict, List

from clawteam.config import get_review_template, is_review_enabled
from clawteam.spawn import get_backend
from clawteam.team.manager import TeamManager
from clawteam.team.tasks import TaskStore
from clawteam.templates import TemplateDef, load_template, render_task

logger = logging.getLogger(__name__)


class ReviewLauncher:
    """Handles automated launching and monitoring of code review teams."""

    def __init__(self):
        self._review_templates: Dict[str, TemplateDef] = {}
        self._active_reviews: Dict[str, asyncio.Task] = {}

    async def launch_review(
        self, team_name: str, task_id: str, code_paths: List[str]
    ) -> str:
        """Launch a code review team for the specified task.

        Args:
            team_name: Name of the original team
            task_id: ID of the task to review
            code_paths: List of file paths to review

        Returns:
            Review team ID
        """
        # Check if review is enabled
        if not is_review_enabled():
            logger.info(f"Review is disabled in configuration, skipping review launch for task {task_id}")
            raise RuntimeError("Review is disabled in configuration")

        # Generate unique review team name
        review_team_id = f"review-{task_id}-{uuid.uuid4().hex[:8]}"

        logger.info(f"Launching review team {review_team_id} for task {task_id}")

        try:
            # Load review template from configuration
            template_name = get_review_template()
            template = load_template(template_name)

            # Configure review-specific settings
            goal = f"Review code changes for task {task_id}. Focus on files: {', '.join(code_paths)}"

            # Create review team asynchronously
            await self._create_review_team(review_team_id, template, goal, code_paths)

            # Start monitoring task
            monitor_task = asyncio.create_task(
                self._monitor_review_progress(review_team_id, task_id)
            )
            self._active_reviews[review_team_id] = monitor_task

            logger.info(f"Review team {review_team_id} launched successfully")
            return review_team_id

        except Exception as e:
            logger.error(f"Failed to launch review for task {task_id}: {e}")
            raise

    def configure_review_template(self, template: Dict) -> None:
        """Configure a custom review template.

        Args:
            template: Template configuration dictionary
        """
        # This would allow custom review templates beyond the built-in code-review
        # For now, we use the built-in template
        logger.info("Review template configuration updated")

    async def _create_review_team(
        self,
        review_team_id: str,
        template: TemplateDef,
        goal: str,
        code_paths: List[str]
    ) -> None:
        """Create and launch the review team.

        Args:
            review_team_id: Unique review team identifier
            template: Loaded template definition
            goal: Review goal description
            code_paths: Files to review
        """
        # Create review team
        leader_id = uuid.uuid4().hex[:12]
        TeamManager.create_team(
            name=review_team_id,
            leader_name=template.leader.name,
            leader_id=leader_id,
            description=f"Automated code review for task with goal: {goal}",
            user="",  # Use default user
        )

        # Add team members
        agent_ids = {template.leader.name: leader_id}
        for agent in template.agents:
            agent_id = uuid.uuid4().hex[:12]
            agent_ids[agent.name] = agent_id
            TeamManager.add_member(
                team_name=review_team_id,
                member_name=agent.name,
                agent_id=agent_id,
                agent_type=agent.type,
                user="",
            )

        # Create initial review tasks
        task_store = TaskStore(review_team_id)
        task_store.create(
            subject="Complete code review",
            description=f"Review the following files: {', '.join(code_paths)}",
            owner=template.leader.name,
        )

        # Launch review agents
        await asyncio.to_thread(
            self._spawn_review_agents,
            review_team_id,
            template,
            agent_ids,
            goal
        )

    def _spawn_review_agents(
        self,
        review_team_id: str,
        template: TemplateDef,
        agent_ids: Dict[str, str],
        goal: str
    ) -> None:
        """Spawn all review agents.

        Args:
            review_team_id: Review team identifier
            template: Template definition
            agent_ids: Mapping of agent names to IDs
            goal: Review goal
        """
        from clawteam.spawn.prompt import build_agent_prompt

        backend = get_backend(template.backend)
        all_agents = [template.leader] + list(template.agents)

        for agent in all_agents:
            agent_id = agent_ids[agent.name]

            # Render agent task with variables
            rendered_task = render_task(
                agent.task,
                goal=goal,
                team_name=review_team_id,
                agent_name=agent.name,
            )

            # Build full prompt
            prompt = build_agent_prompt(
                agent_name=agent.name,
                agent_id=agent_id,
                agent_type=agent.type,
                team_name=review_team_id,
                leader_name=template.leader.name,
                task=rendered_task,
                user="",  # Use default user
                workspace_dir="",
                workspace_branch="",
                isolated_workspace=False,
            )

            # Spawn agent
            result = backend.spawn(
                command=agent.command or template.command,
                agent_name=agent.name,
                agent_id=agent_id,
                agent_type=agent.type,
                team_name=review_team_id,
                prompt=prompt,
                env=None,
                cwd=None,
                skip_permissions=False,
            )

            logger.debug(f"Spawned review agent {agent.name} in team {review_team_id}: {result}")

    async def _monitor_review_progress(self, review_team_id: str, original_task_id: str) -> None:
        """Monitor the progress of a review team.

        Args:
            review_team_id: Review team to monitor
            original_task_id: Original task being reviewed
        """
        try:
            # Simple polling-based monitoring
            task_store = TaskStore(review_team_id)
            poll_interval = 10.0  # seconds

            while True:
                tasks = task_store.list_tasks()
                completed_tasks = [t for t in tasks if t.status == "completed"]
                total_tasks = len(tasks)

                if completed_tasks and len(completed_tasks) == total_tasks:
                    logger.info(f"Review {review_team_id} completed for task {original_task_id}")
                    break

                await asyncio.sleep(poll_interval)

        except Exception as e:
            logger.error(f"Error monitoring review {review_team_id}: {e}")
        finally:
            # Clean up monitoring task
            if review_team_id in self._active_reviews:
                del self._active_reviews[review_team_id]