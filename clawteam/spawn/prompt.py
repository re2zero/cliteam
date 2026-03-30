"""Agent prompt builder — identity + task + context awareness.

Coordination knowledge (how to use clawteam CLI) is provided
by the ClawTeam Skill, not duplicated here.
"""

from __future__ import annotations


def _build_context_block(team_name: str, agent_name: str, repo: str | None = None) -> str:
    """Build a context awareness block from the workspace context layer.

    Includes recent changes from teammates, file overlap warnings,
    and upstream dependency context. Returns empty string if context
    layer is unavailable or no relevant context exists.
    """
    try:
        from clawteam.workspace.context import inject_context
        ctx = inject_context(team_name, agent_name, repo)
        if ctx and "No cross-agent context" not in ctx:
            return ctx
    except Exception:
        pass
    return ""


def build_agent_prompt(
    agent_name: str,
    agent_id: str,
    agent_type: str,
    team_name: str,
    leader_name: str,
    task: str,
    user: str = "",
    workspace_dir: str = "",
    workspace_branch: str = "",
    isolated_workspace: bool = False,
    repo_path: str | None = None,
) -> str:
    """Build agent prompt: identity + task + context + coordination."""
    lines = [
        "## Identity\n",
        f"- Name: {agent_name}",
        f"- ID: {agent_id}",
    ]
    if user:
        lines.append(f"- User: {user}")
    lines.extend([
        f"- Type: {agent_type}",
        f"- Team: {team_name}",
        f"- Leader: {leader_name}",
    ])
    if workspace_dir:
        lines.extend([
            "",
            "## Workspace",
            f"- Working directory: {workspace_dir}",
        ])
        if isolated_workspace:
            lines.extend([
                f"- Branch: {workspace_branch}",
                "- This is an isolated git worktree. Your changes do not affect the main branch.",
            ])
        else:
            lines.append("- Work directly in this repository path unless told otherwise.")

    lines.extend([
        "",
        "## Task\n",
        task,
    ])

    # Inject cross-agent context awareness
    context_block = _build_context_block(team_name, agent_name, repo_path)
    if context_block:
        lines.extend([
            "",
            "## Context\n",
            context_block,
        ])

    is_leader = agent_name == leader_name
    if is_leader:
        lines.extend(_leader_protocol(team_name, agent_name, leader_name))
    else:
        lines.extend(_worker_protocol(team_name, agent_name, leader_name))

    return "\n".join(lines)


def _leader_protocol(team_name: str, agent_name: str, leader_name: str) -> list[str]:
    """Coordination protocol for the team leader."""
    return [
        "",
        "## Coordination Protocol\n",
        f"- Monitor overall progress: `clawteam board show {team_name}`",
        f"- Check all tasks: `clawteam task list {team_name}`",
        "- Assign work: "
        f'`clawteam task create {team_name} "<description>" -o <agent> [--blocked-by <ids>]`',
        f"- Reassign tasks: `clawteam task update {team_name} <task-id> --owner <new-agent>`",
        "- Send instructions to any agent: "
        f'`clawteam inbox send {team_name} <agent> "<instructions>"`',
        f"- Before finishing, save your session: `clawteam session save {team_name} --session-id <id>`",
        "",
        "## Leader Loop Protocol\n",
        f"- Check your inbox for worker updates: `clawteam inbox receive {team_name} --agent {agent_name}`",
        f"- After receiving messages, review board status: `clawteam board show {team_name}`",
        "- Respond to worker questions, blocked reports, or completion summaries.",
        "- Create new tasks or reassign work as needed based on progress.",
        "- When all tasks are done, shut down workers: "
        f'`clawteam lifecycle request-shutdown {team_name} {agent_name} <worker> --force --reason "All done"`',
        "- Keep monitoring inbox and board until all workers have shut down.",
        "",
    ]


def _worker_protocol(team_name: str, agent_name: str, leader_name: str) -> list[str]:
    """Coordination protocol for worker agents."""
    return [
        "",
        "## Coordination Protocol\n",
        f"- Use `clawteam task list {team_name} --owner {agent_name}` to see your tasks.",
        f"- Starting a task: `clawteam task update {team_name} <task-id> --status in_progress`",
        "- Before marking a task completed, commit your changes in this repository with git.",
        '- Use a clear commit message, e.g. `git add -A && git commit -m "Implement <task summary>"`.',
        f"- Finishing a task: `clawteam task update {team_name} <task-id> --status completed`",
        "- When you finish all tasks, send a summary to the leader:",
        f'  `clawteam inbox send {team_name} {leader_name} "All tasks completed. <brief summary>"`',
        "- If you are blocked or need help, message the leader:",
        f'  `clawteam inbox send {team_name} {leader_name} "Need help: <description>"`',
        f"- After finishing work, report your costs: `clawteam cost report {team_name} --input-tokens <N> --output-tokens <N> --cost-cents <N>`",
        f"- Before finishing, save your session: `clawteam session save {team_name} --session-id <id>`",
        "",
        "## Worker Loop Protocol\n",
        f"- After finishing your current task batch, re-check `clawteam task list {team_name} --owner {agent_name}`.",
        f"- Then check for new instructions with `clawteam inbox receive {team_name} --agent {agent_name}`.",
        f"- If you become idle, notify the leader with `clawteam lifecycle idle {team_name}` and continue checking for new work.",
        "- Repeat this loop until the leader confirms shutdown or there is truly no more work to do.",
        "- When you have confirmed there are no more tasks for you and the leader has been notified, run `/exit` to close your session.",
        "",
    ]
