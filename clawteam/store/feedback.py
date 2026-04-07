"""Feedback store for collecting and analyzing review feedback data."""

from __future__ import annotations

import json
import logging
import os
import re
import sys
import tempfile
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

if sys.platform == "win32":
    import msvcrt
else:
    import fcntl

from pydantic import BaseModel, ValidationError

from clawteam.paths import ensure_within_root, validate_identifier
from clawteam.team.models import TeamMessage, get_data_dir

logger = logging.getLogger(__name__)


class FeedbackItem(BaseModel):
    """A feedback item containing review feedback data."""

    model_config = {"populate_by_name": True}

    task_id: str
    feedback_type: str  # "review", "user_rating", "performance", "quality", "completion_time"
    content: dict[str, Any]
    timestamp: datetime
    source: str  # "user", "system", "agent"
    issue_type: str | None = None  # "bug", "feature", "performance", "security", etc.
    severity: str | None = None  # "low", "medium", "high", "critical"
    resolution_time: str | None = None  # ISO datetime string of when the issue was resolved


def _feedbacks_root(team_name: str) -> Path:
    d = ensure_within_root(
        get_data_dir() / "feedbacks",
        validate_identifier(team_name, "team name"),
    )
    d.mkdir(parents=True, exist_ok=True)
    return d


def _feedback_path(team_name: str, feedback_id: str) -> Path:
    return _feedbacks_root(team_name) / f"feedback-{feedback_id}.json"


def _feedbacks_lock_path(team_name: str) -> Path:
    return _feedbacks_root(team_name) / ".feedbacks.lock"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class FeedbackStore:
    """Store for managing feedback data.

    Feedback items are stored as JSON files on disk.
    """

    def __init__(self, team_name: str):
        self.team_name = validate_identifier(team_name, "team name")

    @contextmanager
    def _write_lock(self):
        lock_path = _feedbacks_lock_path(self.team_name)
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        with lock_path.open("a+", encoding="utf-8") as lock_file:
            if sys.platform == "win32":
                pos = lock_file.tell()
                lock_file.seek(0)
                msvcrt.locking(lock_file.fileno(), msvcrt.LK_LOCK, 1)
                lock_file.seek(pos)
            else:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                if sys.platform == "win32":
                    pos = lock_file.tell()
                    lock_file.seek(0)
                    msvcrt.locking(lock_file.fileno(), msvcrt.LK_UNLCK, 1)
                    lock_file.seek(pos)
                else:
                    fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)

    def _save_unlocked(self, feedback: FeedbackItem) -> None:
        """Save feedback item to disk (assumes write lock is held)."""
        path = _feedback_path(self.team_name, feedback.task_id)
        with path.open("w", encoding="utf-8") as f:
            json.dump(feedback.model_dump(), f, indent=2, default=str)

    def store_feedback(self, feedback: FeedbackItem) -> None:
        """Store a feedback item."""
        with self._write_lock():
            self._save_unlocked(feedback)

    def get_feedback(self, task_id: str) -> FeedbackItem | None:
        """Fetch feedback for a task, or None if not found."""
        path = _feedback_path(self.team_name, task_id)
        if not path.exists():
            return None
        try:
            with path.open("r", encoding="utf-8") as f:
                data = json.load(f)
            return FeedbackItem(**data)
        except (json.JSONDecodeError, ValueError):
            return None

    def list_feedbacks(self) -> list[FeedbackItem]:
        """List all feedback items."""
        root = _feedbacks_root(self.team_name)
        feedbacks = []
        for path in root.glob("feedback-*.json"):
            try:
                with path.open("r", encoding="utf-8") as f:
                    data = json.load(f)
                feedbacks.append(FeedbackItem(**data))
            except (json.JSONDecodeError, ValueError):
                continue
        return feedbacks

    def _parse_json_feedback(self, content: str) -> dict[str, Any]:
        """Parse JSON-formatted feedback with enhanced field mapping.
        
        Supports multiple field name conventions (snake_case, camelCase, etc.)
        and provides robust error handling.
        
        Args:
            content: JSON string to parse
            
        Returns:
            Dictionary containing extracted feedback fields
        """
        result = {
            "feedback_type": "review",
            "issue_type": None,
            "severity": None,
            "resolution_time": None,
            "parsed_fields": []
        }
        
        try:
            parsed = json.loads(content)
            if not isinstance(parsed, dict):
                logger.warning(f"JSON feedback is not a dictionary: {type(parsed)}")
                return result
            
            # Field name mappings for different conventions
            field_mappings = {
                "feedback_type": ["feedback_type", "feedbackType", "type", "feedbackType"],
                "issue_type": ["issue_type", "issueType", "issue", "category"],
                "severity": ["severity", "priority", "level"],
                "resolution_time": ["resolution_time", "resolutionTime", "resolved_at", "resolvedAt", "resolved"]
            }
            
            # Extract fields using mappings
            for target_field, possible_names in field_mappings.items():
                for name in possible_names:
                    if name in parsed and parsed[name] is not None:
                        result[target_field] = parsed[name]
                        result["parsed_fields"].append(name)
                        break
            
            # Include all other fields in structured content
            result["additional_fields"] = {
                k: v for k, v in parsed.items() 
                if k not in [name for names in field_mappings.values() for name in names]
            }
            
            logger.debug(f"Successfully parsed JSON feedback with fields: {result['parsed_fields']}")
            
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse JSON feedback: {e}")
        except Exception as e:
            logger.error(f"Unexpected error parsing JSON feedback: {e}")
        
        return result
    
    def _parse_markdown_table(self, content: str) -> dict[str, Any]:
        """Parse feedback from Markdown table format.
        
        Supports tables like:
        | Field | Value |
        |-------|-------|
        | Issue Type | bug |
        | Severity | high |
        
        Args:
            content: Markdown-formatted string
            
        Returns:
            Dictionary containing extracted feedback fields
        """
        result = {
            "feedback_type": "review",
            "issue_type": None,
            "severity": None,
            "resolution_time": None,
            "parsed_fields": []
        }
        
        try:
            lines = content.split('\n')
            table_start = -1
            
            # Find table start (look for |---| separator)
            for i, line in enumerate(lines):
                # Match lines like |---|---| or |:---|:---|
                if re.match(r'^\|[\s\-:|]+\|$', line.strip()):
                    table_start = i - 1
                    break
            
            if table_start < 0 or table_start >= len(lines):
                logger.debug("No markdown table found in content")
                return result
            
            # Parse data rows (skip header and separator)
            for i in range(table_start + 2, len(lines)):
                line = lines[i].strip()
                if not line.startswith('|') or not line.endswith('|'):
                    continue
                
                # Extract values from the row
                values = [v.strip() for v in line.split('|')[1:-1]]
                
                # Skip empty rows or rows with only one value
                if len(values) < 2:
                    continue
                
                # Treat first column as field name, second as value
                field_name = values[0]
                field_value = values[1]
                
                # Extract known fields
                field_lower = field_name.lower()
                
                if "issue" in field_lower and "type" in field_lower:
                    result["issue_type"] = field_value.lower()
                    result["parsed_fields"].append(field_name)
                elif "severity" in field_lower or "priority" in field_lower:
                    result["severity"] = field_value.lower()
                    result["parsed_fields"].append(field_name)
                elif "resolution" in field_lower and ("time" in field_lower or "at" in field_lower):
                    result["resolution_time"] = field_value
                    result["parsed_fields"].append(field_name)
                elif "feedback" in field_lower and "type" in field_lower:
                    result["feedback_type"] = field_value.lower()
                    result["parsed_fields"].append(field_name)
            
            logger.debug(f"Successfully parsed markdown table with fields: {result['parsed_fields']}")
            
        except Exception as e:
            logger.error(f"Error parsing markdown table: {e}")
        
        return result
    
    def _parse_structured_text(self, content: str) -> dict[str, Any]:
        """Parse feedback from structured text formats.
        
        Supports formats like:
        - Key: Value pairs
        - "Key" = "Value" pairs
        - Bullet points with labels
        
        Args:
            content: Text string to parse
            
        Returns:
            Dictionary containing extracted feedback fields
        """
        result = {
            "feedback_type": "review",
            "issue_type": None,
            "severity": None,
            "resolution_time": None,
            "parsed_fields": []
        }
        
        try:
            # Pattern 1: Key: Value pairs (more strict - require line start or specific format)
            key_value_patterns = [
                r'(?:^|\n)(?:issue\s*type|issue)[:\s]+([a-zA-Z_]+)',
                r'(?:^|\n)(?:severity|priority|level)[:\s]+([a-zA-Z]+)',
                r'(?:^|\n)(?:resolution\s*(?:time|at)|resolved)[:\s]+(\d{4}-\d{2}-\d{2}[T\s]\d{2}:\d{2}:\d{2})',
                r'(?:^|\n)(?:feedback\s*type|feedback)[:\s]+([a-zA-Z_]+)'
            ]
            
            # Pattern 2: "Key" = "Value" format
            quoted_patterns = [
                r'"(?:issue\s*type|issue)"\s*=\s*"([^"]+)"',
                r'"(?:severity|priority|level)"\s*=\s*"([^"]+)"',
                r'"(?:resolution\s*(?:time|at)|resolved)"\s*=\s*"(\d{4}-\d{2}-\d{2}[T\s]\d{2}:\d{2}:\d{2})"',
                r'"(?:feedback\s*type|feedback)"\s*=\s*"([^"]+)"'
            ]
            
            # Pattern 3: Bullet points
            bullet_patterns = [
                r'[-*]\s*(?:issue\s*type|issue)[:\s]+([a-zA-Z_]+)',
                r'[-*]\s*(?:severity|priority|level)[:\s]+([a-zA-Z]+)',
                r'[-*]\s*(?:resolution\s*(?:time|at)|resolved)[:\s]+(\d{4}-\d{2}-\d{2}[T\s]\d{2}:\d{2}:\d{2})',
                r'[-*]\s*(?:feedback\s*type|feedback)[:\s]+([a-zA-Z_]+)'
            ]
            
            all_patterns = key_value_patterns + quoted_patterns + bullet_patterns
            
            for pattern in all_patterns:
                match = re.search(pattern, content, re.IGNORECASE)
                if match:
                    value = match.group(1).strip()
                    pattern_lower = pattern.lower()
                    
                    if "issue" in pattern_lower:
                        result["issue_type"] = value.lower()
                        result["parsed_fields"].append("issue_type")
                    elif "severity" in pattern_lower or "priority" in pattern_lower:
                        result["severity"] = value.lower()
                        result["parsed_fields"].append("severity")
                    elif "resolution" in pattern_lower:
                        result["resolution_time"] = value
                        result["parsed_fields"].append("resolution_time")
                    elif "feedback" in pattern_lower:
                        result["feedback_type"] = value.lower()
                        result["parsed_fields"].append("feedback_type")
            
            logger.debug(f"Successfully parsed structured text with fields: {result['parsed_fields']}")
            
        except Exception as e:
            logger.error(f"Error parsing structured text: {e}")
        
        return result
    
    def _extract_from_unstructured_text(self, content: str) -> dict[str, Any]:
        """Extract feedback from unstructured text using keyword matching.
        
        This is a fallback method for free-form text.
        
        Args:
            content: Unstructured text string
            
        Returns:
            Dictionary containing extracted feedback fields
        """
        result = {
            "feedback_type": "review",
            "issue_type": None,
            "severity": None,
            "resolution_time": None,
            "parsed_fields": []
        }
        
        try:
            content_lower = content.lower()
            
            # Issue type extraction with more flexible patterns
            issue_patterns = [
                r'(?:found|identified|detected|there\s+is|there\s+was)\s+(?:a\s+)?(bug|error|defect)',
                r'(?:request|need|want|require)\s+(?:a\s+)?(feature|enhancement)',
                r'(?:performance|speed|latency)\s+(?:issue|problem|concern)',
                r'(?:security|vulnerability|exploit)\s+(?:issue|problem|concern)',
                r'(?:a\s+)?(bug|error|defect)\s+(?:in|at|on)',
                r'(?:a\s+)?(feature|enhancement)\s+(?:for|to)',
                r'(?:a\s+)?(security|performance)\s+(?:issue|problem|concern)'
            ]
            
            for pattern in issue_patterns:
                match = re.search(pattern, content_lower)
                if match:
                    result["issue_type"] = match.group(1)
                    result["parsed_fields"].append("issue_type")
                    break
            
            # Severity extraction with more flexible patterns
            severity_patterns = [
                r'(?:severity|priority|level)[:\s]+(critical|high|medium|low)',
                r'(?:this\s+is|marked\s+as|considered)\s+(critical|high|medium|low)\s+(?:severity|priority)',
                r'(critical|high|medium|low)\s+(?:severity|priority|level)',
                r'(?:is|was)\s+(critical|high|medium|low)\s+(?:severity|priority|level)?'
            ]
            
            for pattern in severity_patterns:
                match = re.search(pattern, content_lower)
                if match:
                    result["severity"] = match.group(1)
                    result["parsed_fields"].append("severity")
                    break
            
            # Resolution time extraction
            time_patterns = [
                r'resolved\s+(?:at|on)\s+(\d{4}-\d{2}-\d{2}[Tt]\d{2}:\d{2}:\d{2}(?:Z|[+-]\d{2}:\d{2})?)',
                r'fixed\s+(?:at|on)\s+(\d{4}-\d{2}-\d{2}[Tt]\d{2}:\d{2}:\d{2}(?:Z|[+-]\d{2}:\d{2})?)',
                r'completed\s+(?:at|on)\s+(\d{4}-\d{2}-\d{2}[Tt]\d{2}:\d{2}:\d{2}(?:Z|[+-]\d{2}:\d{2})?)',
                r'(?:resolved|fixed|completed)\s+(?:at|on)?\s*(\d{4}-\d{2}-\d{2}[Tt]\d{2}:\d{2}:\d{2}(?:Z|[+-]\d{2}:\d{2})?)'
            ]
            
            for pattern in time_patterns:
                match = re.search(pattern, content_lower)
                if match:
                    # Normalize the time format (convert 't' to 'T')
                    time_value = match.group(1).replace('t', 'T')
                    result["resolution_time"] = time_value
                    result["parsed_fields"].append("resolution_time")
                    break
            
            logger.debug(f"Extracted from unstructured text: {result['parsed_fields']}")
            
        except Exception as e:
            logger.error(f"Error extracting from unstructured text: {e}")
        
        return result
    
    def _validate_feedback_data(self, data: dict[str, Any]) -> dict[str, Any]:
        """Validate and normalize feedback data.
        
        Args:
            data: Raw feedback data dictionary
            
        Returns:
            Validated and normalized feedback data
        """
        validated = data.copy()
        
        # Validate issue_type
        valid_issue_types = ["bug", "feature", "performance", "security", "quality", "documentation"]
        if validated.get("issue_type") and validated["issue_type"].lower() in valid_issue_types:
            validated["issue_type"] = validated["issue_type"].lower()
        else:
            validated["issue_type"] = None
        
        # Validate severity
        valid_severities = ["critical", "high", "medium", "low"]
        if validated.get("severity") and validated["severity"].lower() in valid_severities:
            validated["severity"] = validated["severity"].lower()
        else:
            validated["severity"] = None
        
        # Validate resolution_time format
        if validated.get("resolution_time"):
            try:
                # Try to parse as ISO format
                datetime.fromisoformat(validated["resolution_time"])
            except (ValueError, TypeError):
                # If not valid ISO, try to normalize
                validated["resolution_time"] = None
                logger.warning(f"Invalid resolution_time format: {data.get('resolution_time')}")
        
        # Validate feedback_type
        valid_feedback_types = ["review", "user_rating", "performance", "quality", "completion_time"]
        if validated.get("feedback_type") and validated["feedback_type"].lower() in valid_feedback_types:
            validated["feedback_type"] = validated["feedback_type"].lower()
        else:
            validated["feedback_type"] = "review"
        
        return validated
    
    def parse_inbox_message(self, message: TeamMessage) -> FeedbackItem | None:
        """Parse an inbox message to extract feedback data.

        Extracts issue type, severity, and resolution time from message content.
        Supports multiple formats:
        - JSON (with flexible field naming)
        - Markdown tables
        - Structured text (key:value, "key"="value", bullet points)
        - Unstructured text (keyword matching)
        
        Includes robust error handling, validation, and logging.
        
        Args:
            message: TeamMessage object containing feedback data
            
        Returns:
            FeedbackItem object with extracted data, or None if parsing fails
        """
        content = message.content or ""
        
        if not content.strip():
            logger.warning("Empty message content, cannot parse feedback")
            return None
        
        structured_content = {"original_message": content}
        
        # Try different parsing strategies in order of preference
        parsers = [
            ("JSON", self._parse_json_feedback),
            ("Markdown Table", self._parse_markdown_table),
            ("Structured Text", self._parse_structured_text),
            ("Unstructured Text", self._extract_from_unstructured_text)
        ]
        
        parsed_data = None
        parser_used = None
        
        for parser_name, parser_func in parsers:
            try:
                result = parser_func(content)
                if result.get("parsed_fields"):
                    parsed_data = result
                    parser_used = parser_name
                    logger.info(f"Successfully parsed feedback using {parser_name} parser")
                    break
            except Exception as e:
                logger.warning(f"{parser_name} parser failed: {e}")
                continue
        
        if not parsed_data:
            logger.warning("All parsers failed, using default values")
            parsed_data = {
                "feedback_type": "review",
                "issue_type": None,
                "severity": None,
                "resolution_time": None,
                "parsed_fields": []
            }
        
        # Validate the parsed data
        validated_data = self._validate_feedback_data(parsed_data)
        
        # Extract task_id
        task_id = message.key or message.request_id or 'unknown'
        if not task_id or task_id == 'unknown':
            # Try to extract task_id from content
            task_match = re.search(r"task[_\s-]?id[:\s]+([a-zA-Z0-9_-]+)", content, re.IGNORECASE)
            if task_match:
                task_id = task_match.group(1)
                logger.debug(f"Extracted task_id from content: {task_id}")
        
        # Validate timestamp
        try:
            timestamp = datetime.fromisoformat(message.timestamp)
        except (ValueError, TypeError):
            logger.warning(f"Invalid timestamp in message: {message.timestamp}, using current time")
            timestamp = datetime.now(timezone.utc)
        
        # Build structured content
        structured_content.update({
            "parser_used": parser_used,
            "parsed_fields": validated_data.get("parsed_fields", []),
            "feedback_type": validated_data["feedback_type"]
        })
        
        # Add additional fields if present
        if "additional_fields" in validated_data:
            structured_content["additional_fields"] = validated_data["additional_fields"]
        
        # Create FeedbackItem
        try:
            feedback_item = FeedbackItem(
                task_id=task_id,
                feedback_type=validated_data["feedback_type"],
                content=structured_content,
                timestamp=timestamp,
                source=message.from_agent,
                issue_type=validated_data["issue_type"],
                severity=validated_data["severity"],
                resolution_time=validated_data["resolution_time"],
            )
            
            logger.info(f"Successfully created FeedbackItem for task {task_id}")
            return feedback_item
            
        except ValidationError as e:
            logger.error(f"Failed to create FeedbackItem: {e}")
            return None

    def get_stats(self) -> dict[str, Any]:
        """Aggregate feedback statistics."""
        feedbacks = self.list_feedbacks()
        issue_types = {}
        severities = {}
        for fb in feedbacks:
            if fb.issue_type:
                issue_types[fb.issue_type] = issue_types.get(fb.issue_type, 0) + 1
            if fb.severity:
                severities[fb.severity] = severities.get(fb.severity, 0) + 1
        return {
            "total_feedbacks": len(feedbacks),
            "issue_types": issue_types,
            "severities": severities,
        }