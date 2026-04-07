"""Team coordination layer for multi-agent collaboration."""

from clawteam.team.completion import CompletionHandler
from clawteam.store.feedback import FeedbackStore
from clawteam.team.lifecycle import LifecycleManager
from clawteam.team.mailbox import MailboxManager
from clawteam.team.manager import TeamManager
from clawteam.team.optimization import OptimizationEngine
from clawteam.team.plan import PlanManager
from clawteam.team.review import ReviewLauncher
from clawteam.team.watcher import InboxWatcher


def __getattr__(name: str):
    # Lazy import to avoid circular dependency with clawteam.store
    if name == "TaskStore":
        from clawteam.team.tasks import TaskStore
        return TaskStore
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "TeamManager",
    "MailboxManager",
    "TaskStore",
    "PlanManager",
    "LifecycleManager",
    "InboxWatcher",
    "CompletionHandler",
    "ReviewLauncher",
    "FeedbackStore",
    "OptimizationEngine",
]
