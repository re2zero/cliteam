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
    lines.extend(
        [
            f"- Type: {agent_type}",
            f"- Team: {team_name}",
            f"- Leader: {leader_name}",
        ]
    )
    if workspace_dir:
        lines.extend(
            [
                "",
                "## Workspace",
                f"- Working directory: {workspace_dir}",
            ]
        )
        if isolated_workspace:
            lines.extend(
                [
                    f"- Branch: {workspace_branch}",
                    "- This is an isolated git worktree. Your changes do not affect the main branch.",
                ]
            )
        else:
            lines.append("- Work directly in this repository path unless told otherwise.")

    lines.extend(
        [
            "",
            "## Task\n",
            task,
        ]
    )

    # Inject cross-agent context awareness
    context_block = _build_context_block(team_name, agent_name, repo_path)
    if context_block:
        lines.extend(
            [
                "",
                "## Context\n",
                context_block,
            ]
        )

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
        f"- Reassign tasks: clawteam task update {team_name} <task-id> --owner <new-agent>",
        "- Send instructions to any agent: "
        f'`clawteam inbox send {team_name} <agent> "<instructions>"`',
        "",
        "## Worker Lifecycle (On-Demand Spawning)\n",
        "Workers are spawned on-demand by you. Use standard clawteam agent commands:\n",
        f"- **Spawn worker**: clawteam agent spawn --team {team_name} --agent-name <name>",
        f"- **Stop worker**: clawteam agent stop {team_name} <name>",
        "- Spawn only when needed (e.g., after Stage 3 completes and you have tasks ready)",
        "- Stop worker when it completes all assigned tasks and no more work is pending",
        "- Respawn failed workers using agent spawn with the same name and --replace",
        "",
        "## Task Execution Order\n",
        "Ensure tasks execute in correct order:\n",
        "1. Create tasks with dependencies using --blocked-by",
        "2. Tasks start in 'blocked' state when they depend on unfinished tasks",
        "3. Completed tasks auto-unblock their dependents (blocked → pending)",
        "4. Monitor task state transitions to validate execution order",
        "5. If tasks execute out of order, investigate and correct dependency chains",
        "",
        "## Worker Shutdown\n",
        "Shut down a worker when its tasks are all done and no more work is available:\n",
        f'- `clawteam agent stop {team_name} <worker> --reason "All tasks complete"`',
        "- Workers report completion via inbox when their last task is done",
        "- Verify all pending/blocked tasks before shutdown to avoid orphaned work",
        "",
        "## Leader Supervision Loop\n",
        "Run this loop continuously until all tasks are done:\n",
        f"1. `clawteam board show {team_name}` — check overall progress",
        f"2. `clawteam inbox receive {team_name} --agent {agent_name}` — check worker messages",
        "3. Process messages (completions, help requests, idle reports)",
        f"4. `clawteam task list {team_name} --status blocked` — check newly unblocked tasks",
        f"5. Spawn workers if needed for available tasks (use agent spawn)",
        "6. Check for stalled workers (see Stalled Worker Protocol below)",
        "7. Stop idle workers with no assigned tasks",
        "8. If all tasks done, proceed to Review & Integration",
        "9. Wait 10-30 seconds, then loop back to step 1",
        "",
        "## Stalled Worker Protocol\n",
        "A worker is stalled when it has an in_progress task but isn't making progress.\n",
        "**Detect:** Read the worker's terminal to check if it's idle:\n",
        f"- tmux: `tmux capture-pane -p -t clawteam-{team_name}:<worker-name> | tail -30`",
        "- wsh: No CLI available - use TideTerm UI to check worker terminal\n",
        "**Nudge** (send input to wake the worker):\n",
        f'- tmux: `tmux send-keys -t clawteam-{team_name}:<worker-name> "Continue working. Read your inbox and resume your current task." Enter`',
        "- wsh: NO COMMAND-LINE NUDGE AVAILABLE - switch to worker terminal in TideTerm UI and type directly\n",
        "**Escalate** (if no response after 2 nudges): agent stop, then agent spawn again with --replace.",
        "",
        "## Review & Integration (after all tasks complete)\n",
        "1. Review each worker's changes: `clawteam context diff {team_name} <worker>`",
        "2. If issues found, send correction and nudge worker to fix",
        "3. Merge all worktrees: `clawteam workspace merge {team_name} <worker>`",
        "4. Run project tests to verify integration",
        '5. Commit: `git add -A && git commit -m "<summary>"`',
        f"6. Cleanup: `clawteam team cleanup {team_name} --force`",
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
        "- When you finish a task, send a summary to the leader:",
        f'  `clawteam inbox send {team_name} {leader_name} "Completed <task-id>: <brief summary>"`',
        "- If you are blocked or need help, message the leader:",
        f'  `clawteam inbox send {team_name} {leader_name} "Need help: <description>"`',
        "",
        "## Worker Loop Protocol\n",
        "You MUST keep looping. Do NOT exit after your first task.\n",
        "```\n",
        "1. Check for assigned tasks:\n",
        f"   clawteam task list {team_name} --owner {agent_name}\n",
        "2. If task found:\n",
        "   a. Set status to in_progress\n",
        "   b. Do the work\n",
        "   c. Commit changes\n",
        "   d. Set status to completed\n",
        "   e. Report to leader via inbox\n",
        "   f. Go to step 1\n",
        "3. If no task found:\n",
        f"   a. clawteam inbox receive {team_name} --agent {agent_name}\n",
        "   b. If message received: process it, go to step 1\n",
        "   c. If no message: increment empty poll counter\n",
        "      - If counter < 5: go to step 1\n",
        "      - If counter >= 5:\n",
        f"        * clawteam lifecycle idle {team_name}\n",
        f'        * clawteam inbox send {team_name} {leader_name} "Idle: no tasks after 5 polls. Awaiting instructions."\n',
        "        * Go to step 1\n",
        "```\n",
        "",
        "## LLM Interruption Recovery\n",
        "If you receive a nudge message from the leader (e.g. 'Continue working'):\n",
        "- Check if you have an in_progress task → resume it",
        "- If no active task → check inbox for new assignments",
        "- Continue the normal worker loop",
        "",
        "## Exit Conditions\n",
        "Only exit when the leader sends a shutdown_request. Do NOT exit on your own.\n",
    ]
