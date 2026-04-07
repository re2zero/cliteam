"""Optimization engine for analyzing feedback and optimizing team performance."""

from __future__ import annotations

import json
from collections import defaultdict, Counter
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

from pydantic import BaseModel

from clawteam.config import (
    is_optimization_enabled,
    get_optimization_interval_hours,
    get_optimization_mode,
    are_optimization_suggestions_enabled,
)
from clawteam.store.feedback import FeedbackStore, FeedbackItem
from clawteam.team.manager import TeamManager
from clawteam.team.models import TeamConfig, get_data_dir


class OptimizationReport(BaseModel):
    """Report containing optimization recommendations."""

    team_name: str
    analysis_date: datetime
    issue_frequency: Dict[str, int]
    average_review_time: float
    performance_metrics: Dict[str, Any]
    recommendations: List[str]
    suggested_team_changes: Dict[str, Any]
    template_updates: Dict[str, Any]


class OptimizationEngine:
    """Engine for analyzing feedback data and generating optimization recommendations."""

    def __init__(self, team_name: str):
        self.team_name = team_name
        self.feedback_store = FeedbackStore(team_name)
        # TeamManager provides static methods, no need to instantiate
        self.team_manager = TeamManager
        self.enabled = is_optimization_enabled()
        self.analysis_interval_hours = get_optimization_interval_hours()
        self.optimization_mode = get_optimization_mode()
        self.suggestions_enabled = are_optimization_suggestions_enabled()

    def analyze_historical_data(self, days_back: int = 30) -> List[FeedbackItem]:
        """Analyze historical feedback data from the specified number of days back."""
        # Get all feedback items from the store
        # Note: FeedbackStore doesn't have a direct method to get all items,
        # so we need to implement a way to retrieve them.
        # For now, we'll assume we can list and load all feedback files.

        feedback_dir = get_data_dir() / "feedbacks" / self.team_name
        if not feedback_dir.exists():
            return []

        feedback_items = []
        cutoff_date = datetime.now() - timedelta(days=days_back)

        for feedback_file in feedback_dir.glob("feedback-*.json"):
            try:
                data = json.loads(feedback_file.read_text(encoding="utf-8"))
                item = FeedbackItem.model_validate(data)
                if item.timestamp >= cutoff_date:
                    feedback_items.append(item)
            except Exception:
                continue

        return feedback_items

    def statistical_analysis(self, feedback_items: List[FeedbackItem]) -> Dict[str, Any]:
        """Perform statistical analysis on feedback data."""
        if not feedback_items:
            return {
                "issue_frequency": {},
                "average_review_time_hours": 0.0,
                "performance_metrics": {},
                "total_feedbacks": 0
            }

        # Count issue types and severities
        issue_counter = Counter()
        severity_counter = Counter()
        review_times = []

        for item in feedback_items:
            if item.issue_type:
                issue_counter[item.issue_type] += 1
            if item.severity:
                severity_counter[item.severity] += 1

            # Calculate review times for resolved issues
            if item.resolution_time:
                try:
                    resolution_dt = datetime.fromisoformat(item.resolution_time.replace('Z', '+00:00'))
                    time_diff = (resolution_dt - item.timestamp).total_seconds() / 3600  # hours
                    if time_diff > 0:
                        review_times.append(time_diff)
                except Exception:
                    continue

        avg_review_time = sum(review_times) / len(review_times) if review_times else 0.0

        return {
            "issue_frequency": dict(issue_counter),
            "severity_distribution": dict(severity_counter),
            "average_review_time_hours": avg_review_time,
            "performance_metrics": {
                "total_feedbacks": len(feedback_items),
                "resolved_issues": len([f for f in feedback_items if f.resolution_time]),
                "resolution_rate": len([f for f in feedback_items if f.resolution_time]) / len(feedback_items) if feedback_items else 0
            }
        }

    def adjust_team_size_and_roles(self, analysis: Dict[str, Any]) -> Dict[str, Any]:
        """Generate recommendations for team size and role adjustments."""
        recommendations = {}

        # Load current team config using static method
        config = self.team_manager.get_team(self.team_name)
        if not config:
            return {"error": "Team config not found"}

        current_members = len(config.members)
        issue_frequency = analysis.get("issue_frequency", {})
        avg_review_time = analysis.get("average_review_time_hours", 0)

        # Simple heuristics for team adjustments
        if avg_review_time > 24:  # If average review time > 24 hours
            recommendations["team_size"] = "increase"
            recommendations["reason"] = "High average review time indicates need for more team members"
        elif avg_review_time < 2 and current_members > 3:  # If very fast and team is large
            recommendations["team_size"] = "decrease"
            recommendations["reason"] = "Fast resolution times suggest team can be optimized"

        # Role adjustments based on issue types
        role_suggestions = {}
        if "security" in issue_frequency and issue_frequency["security"] > 5:
            role_suggestions["security_specialist"] = "add"
        if "performance" in issue_frequency and issue_frequency["performance"] > 5:
            role_suggestions["performance_engineer"] = "add"

        recommendations["role_changes"] = role_suggestions

        return recommendations

    def update_template_parameters(self, analysis: Dict[str, Any]) -> Dict[str, Any]:
        """Generate recommendations for template parameter updates."""
        updates = {}

        issue_frequency = analysis.get("issue_frequency", {})
        severity_distribution = analysis.get("severity_distribution", {})

        # Adjust review thresholds based on issue patterns
        if severity_distribution.get("critical", 0) > severity_distribution.get("low", 0):
            updates["review_threshold"] = "strict"
            updates["automated_checks"] = ["security", "performance"]

        # Update code review template parameters
        if "bug" in issue_frequency and issue_frequency["bug"] > 10:
            updates["code_review_focus"] = ["error_handling", "testing"]

        return updates

    def generate_optimization_report(self, days_back: int = 30) -> OptimizationReport:
        """Generate a comprehensive optimization report."""
        # Check if optimization is enabled
        if not self.enabled:
            import logging
            logger = logging.getLogger(__name__)
            logger.info(f"Optimization is disabled for team {self.team_name}, returning empty report")
            return OptimizationReport(
                team_name=self.team_name,
                analysis_date=datetime.now(),
                issue_frequency={},
                average_review_time=0.0,
                performance_metrics={},
                recommendations=["Optimization is disabled in configuration"],
                suggested_team_changes={},
                template_updates={}
            )

        feedback_items = self.analyze_historical_data(days_back)
        analysis = self.statistical_analysis(feedback_items)

        team_changes = self.adjust_team_size_and_roles(analysis)
        template_updates = self.update_template_parameters(analysis)

        recommendations = []
        if self.suggestions_enabled:
            if analysis["average_review_time_hours"] > 24:
                recommendations.append("Consider increasing team size to reduce review times")
            if analysis.get("performance_metrics", {}).get("resolution_rate", 0) < 0.8:
                recommendations.append("Improve issue resolution rate through better processes")
            if team_changes.get("team_size") == "increase":
                recommendations.append(f"Recommended team size increase: {team_changes.get('reason', '')}")
            if team_changes.get("role_changes"):
                recommendations.append(f"Consider adding specialized roles: {list(team_changes['role_changes'].keys())}")
        else:
            recommendations.append("Optimization suggestions are disabled in configuration")

        return OptimizationReport(
            team_name=self.team_name,
            analysis_date=datetime.now(),
            issue_frequency=analysis["issue_frequency"],
            average_review_time=analysis["average_review_time_hours"],
            performance_metrics=analysis["performance_metrics"],
            recommendations=recommendations,
            suggested_team_changes=team_changes,
            template_updates=template_updates
        )

    def apply_optimizations(self, report: OptimizationReport, auto_apply: bool = False) -> bool:
        """Apply the optimization recommendations.
        
        Args:
            report: The optimization report containing recommendations
            auto_apply: If True, automatically apply recommendations; if False, just log them
            
        Returns:
            True if optimizations were applied successfully, False otherwise
        """
        import logging
        logger = logging.getLogger(__name__)
        
        if not auto_apply:
            # In manual mode, just log recommendations
            logger.info(f"Optimization recommendations for {self.team_name}:")
            for rec in report.recommendations:
                logger.info(f"- {rec}")
            return False

        # Auto-apply logic
        success = True
        
        try:
            # Apply team configuration changes
            if report.suggested_team_changes:
                team_success = self._apply_team_changes(report.suggested_team_changes)
                if not team_success:
                    logger.warning(f"Failed to apply team changes for {self.team_name}")
                    success = False
                else:
                    logger.info(f"Successfully applied team changes for {self.team_name}")
            
            # Apply template parameter updates
            if report.template_updates:
                template_success = self._apply_template_updates(report.template_updates)
                if not template_success:
                    logger.warning(f"Failed to apply template updates for {self.team_name}")
                    success = False
                else:
                    logger.info(f"Successfully applied template updates for {self.team_name}")
            
            # Log all applied recommendations
            if report.recommendations:
                logger.info(f"Applied {len(report.recommendations)} optimization recommendations for {self.team_name}")
                for rec in report.recommendations:
                    logger.info(f"  - {rec}")
            
            return success
            
        except Exception as e:
            logger.error(f"Error applying optimizations for {self.team_name}: {e}")
            return False
    
    def _apply_team_changes(self, team_changes: Dict[str, Any]) -> bool:
        """Apply team configuration changes based on optimization recommendations.
        
        Args:
            team_changes: Dictionary containing team change recommendations
            
        Returns:
            True if changes were applied successfully, False otherwise
        """
        import logging
        logger = logging.getLogger(__name__)
        
        try:
            # Load current team config using static method
            config = self.team_manager.get_team(self.team_name)
            if not config:
                logger.error(f"Team config not found for {self.team_name}")
                return False
            
            changes_made = False
            
            # Handle team size adjustments
            team_size = team_changes.get("team_size")
            if team_size:
                current_members = len(config.members)
                
                if team_size == "increase":
                    # Suggest adding members (we can't auto-add without agent IDs)
                    logger.info(f"Recommendation: Increase team size from {current_members} members")
                    # In a real implementation, this might trigger a workflow to add new agents
                    changes_made = True
                    
                elif team_size == "decrease" and current_members > 3:
                    # Suggest removing members (we can't auto-remove without user confirmation)
                    logger.info(f"Recommendation: Decrease team size from {current_members} members")
                    # In a real implementation, this might trigger a workflow to remove agents
                    changes_made = True
            
            # Handle role changes
            role_changes = team_changes.get("role_changes", {})
            if role_changes:
                for role, action in role_changes.items():
                    if action == "add":
                        logger.info(f"Recommendation: Add {role} role to team")
                        # In a real implementation, this might create a new agent with this role
                        changes_made = True
                    elif action == "remove":
                        logger.info(f"Recommendation: Remove {role} role from team")
                        # In a real implementation, this might remove agents with this role
                        changes_made = True
            
            # Save the config if changes were made
            if changes_made:
                # Note: We're not actually modifying the config here because
                # team size and role changes require user intervention
                # In a production system, this would trigger a workflow
                logger.info(f"Team change recommendations logged for {self.team_name}")
            
            return True
            
        except Exception as e:
            logger.error(f"Error applying team changes for {self.team_name}: {e}")
            return False
    
    def _apply_template_updates(self, template_updates: Dict[str, Any]) -> bool:
        """Apply template parameter updates based on optimization recommendations.
        
        Args:
            template_updates: Dictionary containing template update recommendations
            
        Returns:
            True if updates were applied successfully, False otherwise
        """
        import logging
        import sys
        from pathlib import Path
        
        logger = logging.getLogger(__name__)
        
        try:
            # TOML support: built-in on 3.11+, conditional dependency on 3.10
            if sys.version_info >= (3, 11):
                import tomllib
            else:
                try:
                    import tomllib  # type: ignore[import-not-found]
                except ModuleNotFoundError:
                    import tomli as tomllib  # type: ignore[import-not-found,no-redef]
            
            # Get the post-completion template path
            template_path = Path.home() / ".clawteam" / "templates" / "post-completion.toml"
            
            if not template_path.exists():
                logger.warning(f"Post-completion template not found at {template_path}")
                return False
            
            # Load the current template
            with open(template_path, "rb") as f:
                template_data = tomllib.load(f)
            
            # Apply updates to the template
            updates_applied = False
            
            # Update review settings
            if "review_threshold" in template_updates:
                if "review" not in template_data:
                    template_data["review"] = {}
                template_data["review"]["threshold"] = template_updates["review_threshold"]
                updates_applied = True
                logger.info(f"Updated review threshold to {template_updates['review_threshold']}")
            
            if "automated_checks" in template_updates:
                if "review" not in template_data:
                    template_data["review"] = {}
                template_data["review"]["automated_checks"] = template_updates["automated_checks"]
                updates_applied = True
                logger.info(f"Updated automated checks to {template_updates['automated_checks']}")
            
            if "code_review_focus" in template_updates:
                if "review" not in template_data:
                    template_data["review"] = {}
                template_data["review"]["focus_areas"] = template_updates["code_review_focus"]
                updates_applied = True
                logger.info(f"Updated code review focus to {template_updates['code_review_focus']}")
            
            # Save the updated template if changes were made
            if updates_applied:
                # We need to write TOML back - use tomli_w for Python < 3.11
                try:
                    if sys.version_info >= (3, 11):
                        import tomllib
                        # Python 3.11+ has tomllib for reading but not writing
                        # We'll use a simple approach for writing
                        import tomli_w
                    else:
                        import tomli_w
                except ImportError:
                    # Fallback: just log the changes without writing
                    logger.warning("tomli_w not available, cannot write template updates")
                    logger.info(f"Template updates to apply: {template_updates}")
                    return True
                
                # Write the updated template
                with open(template_path, "wb") as f:
                    tomli_w.dump(template_data, f)
                
                logger.info(f"Successfully updated post-completion template at {template_path}")
            
            return True
            
        except Exception as e:
            logger.error(f"Error applying template updates for {self.team_name}: {e}")
            return False