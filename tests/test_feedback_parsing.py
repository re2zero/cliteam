"""Tests for FeedbackStore parsing improvements."""

import json
from datetime import datetime, timezone
from unittest.mock import Mock

import pytest

from clawteam.store.feedback import FeedbackStore, FeedbackItem
from clawteam.team.models import TeamMessage


@pytest.fixture
def sample_message():
    """Create a sample TeamMessage for testing."""
    return TeamMessage(
        key="task-123",
        request_id="req-456",
        content="",
        from_agent="reviewer",
        timestamp="2024-01-15T10:30:00Z"
    )


class TestJSONParsing:
    """Test JSON format parsing."""
    
    def test_parse_json_snake_case(self, sample_message):
        """Test parsing JSON with snake_case field names."""
        content = json.dumps({
            "feedback_type": "review",
            "issue_type": "bug",
            "severity": "high",
            "resolution_time": "2024-01-15T12:00:00Z",
            "description": "Found a critical bug"
        })
        sample_message.content = content
        
        store = FeedbackStore("test-team")
        result = store.parse_inbox_message(sample_message)
        
        assert result is not None
        assert result.feedback_type == "review"
        assert result.issue_type == "bug"
        assert result.severity == "high"
        assert result.resolution_time == "2024-01-15T12:00:00Z"
        assert result.content["parser_used"] == "JSON"
    
    def test_parse_json_camel_case(self, sample_message):
        """Test parsing JSON with camelCase field names."""
        content = json.dumps({
            "feedbackType": "review",
            "issueType": "feature",
            "severity": "medium",
            "resolutionTime": "2024-01-15T12:00:00Z"
        })
        sample_message.content = content
        
        store = FeedbackStore("test-team")
        result = store.parse_inbox_message(sample_message)
        
        assert result is not None
        assert result.feedback_type == "review"
        assert result.issue_type == "feature"
        assert result.severity == "medium"
    
    def test_parse_json_mixed_case(self, sample_message):
        """Test parsing JSON with mixed field naming conventions."""
        content = json.dumps({
            "feedback_type": "review",
            "issueType": "bug",
            "severity": "critical",
            "resolved_at": "2024-01-15T12:00:00Z"
        })
        sample_message.content = content
        
        store = FeedbackStore("test-team")
        result = store.parse_inbox_message(sample_message)
        
        assert result is not None
        assert result.feedback_type == "review"
        assert result.issue_type == "bug"
        assert result.severity == "critical"
        assert result.resolution_time == "2024-01-15T12:00:00Z"
    
    def test_parse_json_with_additional_fields(self, sample_message):
        """Test parsing JSON with additional custom fields."""
        content = json.dumps({
            "feedback_type": "review",
            "issue_type": "bug",
            "severity": "high",
            "custom_field": "custom_value",
            "another_field": 123
        })
        sample_message.content = content
        
        store = FeedbackStore("test-team")
        result = store.parse_inbox_message(sample_message)
        
        assert result is not None
        assert "additional_fields" in result.content
        assert result.content["additional_fields"]["custom_field"] == "custom_value"
        assert result.content["additional_fields"]["another_field"] == 123
    
    def test_parse_json_invalid(self, sample_message):
        """Test parsing invalid JSON."""
        sample_message.content = "{ invalid json }"
        
        store = FeedbackStore("test-team")
        result = store.parse_inbox_message(sample_message)
        
        # Should fall back to other parsers
        assert result is not None
        assert result.content["parser_used"] != "JSON"


class TestMarkdownTableParsing:
    """Test Markdown table format parsing."""
    
    def test_parse_markdown_table_simple(self, sample_message):
        """Test parsing simple markdown table."""
        content = """
| Field | Value |
|-------|-------|
| Issue Type | bug |
| Severity | high |
| Resolution Time | 2024-01-15T12:00:00Z |
"""
        sample_message.content = content
        
        store = FeedbackStore("test-team")
        result = store.parse_inbox_message(sample_message)
        
        assert result is not None
        assert result.issue_type == "bug"
        assert result.severity == "high"
        assert result.resolution_time == "2024-01-15T12:00:00Z"
        assert result.content["parser_used"] == "Markdown Table"
    
    def test_parse_markdown_table_with_feedback_type(self, sample_message):
        """Test parsing markdown table with feedback type."""
        content = """
| Field | Value |
|-------|-------|
| Feedback Type | user_rating |
| Issue Type | feature |
| Severity | medium |
"""
        sample_message.content = content
        
        store = FeedbackStore("test-team")
        result = store.parse_inbox_message(sample_message)
        
        assert result is not None
        assert result.feedback_type == "user_rating"
        assert result.issue_type == "feature"
        assert result.severity == "medium"
    
    def test_parse_markdown_table_priority_field(self, sample_message):
        """Test parsing markdown table with priority field."""
        content = """
| Field | Value |
|-------|-------|
| Issue Type | security |
| Priority | critical |
| Resolved At | 2024-01-15T12:00:00Z |
"""
        sample_message.content = content
        
        store = FeedbackStore("test-team")
        result = store.parse_inbox_message(sample_message)
        
        assert result is not None
        assert result.issue_type == "security"
        assert result.severity == "critical"
        assert result.resolution_time == "2024-01-15T12:00:00Z"
    
    def test_parse_markdown_table_no_table(self, sample_message):
        """Test parsing content without markdown table."""
        sample_message.content = "This is just plain text without a table."
        
        store = FeedbackStore("test-team")
        result = store.parse_inbox_message(sample_message)
        
        assert result is not None
        assert result.content["parser_used"] != "Markdown Table"


class TestStructuredTextParsing:
    """Test structured text format parsing."""
    
    def test_parse_key_value_pairs(self, sample_message):
        """Test parsing key:value pairs."""
        content = """
Issue Type: bug
Severity: high
Resolution Time: 2024-01-15T12:00:00Z
"""
        sample_message.content = content
        
        store = FeedbackStore("test-team")
        result = store.parse_inbox_message(sample_message)
        
        assert result is not None
        assert result.issue_type == "bug"
        assert result.severity == "high"
        assert result.resolution_time == "2024-01-15T12:00:00Z"
        assert result.content["parser_used"] == "Structured Text"
    
    def test_parse_quoted_pairs(self, sample_message):
        """Test parsing "key" = "value" format."""
        content = '''
"issue_type" = "bug"
"severity" = "critical"
"resolution_time" = "2024-01-15T12:00:00Z"
'''
        sample_message.content = content
        
        store = FeedbackStore("test-team")
        result = store.parse_inbox_message(sample_message)
        
        assert result is not None
        assert result.issue_type == "bug"
        assert result.severity == "critical"
        assert result.resolution_time == "2024-01-15T12:00:00Z"
    
    def test_parse_bullet_points(self, sample_message):
        """Test parsing bullet point format."""
        content = """
- Issue Type: feature
- Severity: medium
- Resolution Time: 2024-01-15T12:00:00Z
"""
        sample_message.content = content
        
        store = FeedbackStore("test-team")
        result = store.parse_inbox_message(sample_message)
        
        assert result is not None
        assert result.issue_type == "feature"
        assert result.severity == "medium"
        assert result.resolution_time == "2024-01-15T12:00:00Z"
    
    def test_parse_mixed_structured_text(self, sample_message):
        """Test parsing mixed structured text formats."""
        content = """
Feedback Type: review
Issue Type: performance
Priority: high
- Resolution Time: 2024-01-15T12:00:00Z
"""
        sample_message.content = content
        
        store = FeedbackStore("test-team")
        result = store.parse_inbox_message(sample_message)
        
        assert result is not None
        assert result.feedback_type == "review"
        assert result.issue_type == "performance"
        assert result.severity == "high"


class TestUnstructuredTextParsing:
    """Test unstructured text parsing (fallback)."""
    
    def test_parse_unstructured_with_context(self, sample_message):
        """Test parsing unstructured text with contextual keywords."""
        content = """
I found a bug in the authentication module.
This is marked as high severity.
The issue was resolved at 2024-01-15T12:00:00Z.
"""
        sample_message.content = content
        
        store = FeedbackStore("test-team")
        result = store.parse_inbox_message(sample_message)
        
        assert result is not None
        assert result.issue_type == "bug"
        assert result.severity == "high"
        assert result.resolution_time == "2024-01-15T12:00:00Z"
        assert result.content["parser_used"] == "Unstructured Text"
    
    def test_parse_unstructured_feature_request(self, sample_message):
        """Test parsing unstructured feature request."""
        content = """
We need a feature for user notifications.
Priority: medium
"""
        sample_message.content = content
        
        store = FeedbackStore("test-team")
        result = store.parse_inbox_message(sample_message)
        
        assert result is not None
        assert result.issue_type == "feature"
        assert result.severity == "medium"
    
    def test_parse_unstructured_security_issue(self, sample_message):
        """Test parsing unstructured security issue."""
        content = """
There's a security vulnerability in the login system.
This is critical severity.
"""
        sample_message.content = content
        
        store = FeedbackStore("test-team")
        result = store.parse_inbox_message(sample_message)
        
        assert result is not None
        assert result.issue_type == "security"
        assert result.severity == "critical"


class TestValidation:
    """Test data validation and normalization."""
    
    def test_validate_issue_type(self, sample_message):
        """Test issue type validation."""
        content = json.dumps({
            "issue_type": "BUG",  # Should be normalized to lowercase
            "severity": "HIGH"
        })
        sample_message.content = content
        
        store = FeedbackStore("test-team")
        result = store.parse_inbox_message(sample_message)
        
        assert result is not None
        assert result.issue_type == "bug"
        assert result.severity == "high"
    
    def test_validate_invalid_issue_type(self, sample_message):
        """Test validation with invalid issue type."""
        content = json.dumps({
            "issue_type": "invalid_type",
            "severity": "high"
        })
        sample_message.content = content
        
        store = FeedbackStore("test-team")
        result = store.parse_inbox_message(sample_message)
        
        assert result is not None
        assert result.issue_type is None  # Invalid type should be set to None
    
    def test_validate_invalid_severity(self, sample_message):
        """Test validation with invalid severity."""
        content = json.dumps({
            "issue_type": "bug",
            "severity": "invalid_severity"
        })
        sample_message.content = content
        
        store = FeedbackStore("test-team")
        result = store.parse_inbox_message(sample_message)
        
        assert result is not None
        assert result.severity is None  # Invalid severity should be set to None
    
    def test_validate_invalid_resolution_time(self, sample_message):
        """Test validation with invalid resolution time format."""
        content = json.dumps({
            "issue_type": "bug",
            "severity": "high",
            "resolution_time": "invalid_time_format"
        })
        sample_message.content = content
        
        store = FeedbackStore("test-team")
        result = store.parse_inbox_message(sample_message)
        
        assert result is not None
        assert result.resolution_time is None  # Invalid time should be set to None
    
    def test_validate_feedback_type(self, sample_message):
        """Test feedback type validation."""
        content = json.dumps({
            "feedback_type": "USER_RATING",  # Should be normalized
            "issue_type": "bug"
        })
        sample_message.content = content
        
        store = FeedbackStore("test-team")
        result = store.parse_inbox_message(sample_message)
        
        assert result is not None
        assert result.feedback_type == "user_rating"
    
    def test_validate_default_feedback_type(self, sample_message):
        """Test default feedback type when not specified."""
        content = json.dumps({
            "issue_type": "bug"
        })
        sample_message.content = content
        
        store = FeedbackStore("test-team")
        result = store.parse_inbox_message(sample_message)
        
        assert result is not None
        assert result.feedback_type == "review"  # Default value


class TestErrorHandling:
    """Test error handling and edge cases."""
    
    def test_empty_content(self, sample_message):
        """Test parsing empty content."""
        sample_message.content = ""
        
        store = FeedbackStore("test-team")
        result = store.parse_inbox_message(sample_message)
        
        assert result is None  # Empty content should return None
    
    def test_whitespace_only_content(self, sample_message):
        """Test parsing whitespace-only content."""
        sample_message.content = "   \n\t   "
        
        store = FeedbackStore("test-team")
        result = store.parse_inbox_message(sample_message)
        
        assert result is None
    
    def test_invalid_timestamp(self, sample_message):
        """Test handling of invalid timestamp."""
        sample_message.content = json.dumps({"issue_type": "bug"})
        sample_message.timestamp = "invalid-timestamp"
        
        store = FeedbackStore("test-team")
        result = store.parse_inbox_message(sample_message)
        
        assert result is not None
        # Should use current time as fallback
        assert isinstance(result.timestamp, datetime)
    
    def test_missing_task_id(self, sample_message):
        """Test handling of missing task ID."""
        sample_message.content = json.dumps({"issue_type": "bug"})
        sample_message.key = None
        sample_message.request_id = None
        
        store = FeedbackStore("test-team")
        result = store.parse_inbox_message(sample_message)
        
        assert result is not None
        assert result.task_id == "unknown"
    
    def test_extract_task_id_from_content(self, sample_message):
        """Test extracting task ID from content."""
        sample_message.content = "Task ID: task-789\nIssue Type: bug"
        sample_message.key = None
        sample_message.request_id = None
        
        store = FeedbackStore("test-team")
        result = store.parse_inbox_message(sample_message)
        
        assert result is not None
        assert result.task_id == "task-789"
    
    def test_all_parsers_fail(self, sample_message):
        """Test behavior when all parsers fail."""
        sample_message.content = "Random text with no structured information"
        
        store = FeedbackStore("test-team")
        result = store.parse_inbox_message(sample_message)
        
        assert result is not None
        assert result.feedback_type == "review"  # Default
        assert result.issue_type is None
        assert result.severity is None


class TestParserPriority:
    """Test parser priority and fallback behavior."""
    
    def test_json_parser_priority(self, sample_message):
        """Test that JSON parser is tried first."""
        content = json.dumps({"issue_type": "bug", "severity": "high"})
        sample_message.content = content
        
        store = FeedbackStore("test-team")
        result = store.parse_inbox_message(sample_message)
        
        assert result is not None
        assert result.content["parser_used"] == "JSON"
    
    def test_markdown_parser_fallback(self, sample_message):
        """Test markdown parser when JSON fails."""
        content = """
| Field | Value |
|-------|-------|
| Issue Type | bug |
"""
        sample_message.content = content
        
        store = FeedbackStore("test-team")
        result = store.parse_inbox_message(sample_message)
        
        assert result is not None
        assert result.content["parser_used"] == "Markdown Table"
    
    def test_structured_text_fallback(self, sample_message):
        """Test structured text parser when JSON and markdown fail."""
        content = "Issue Type: bug\nSeverity: high"
        sample_message.content = content
        
        store = FeedbackStore("test-team")
        result = store.parse_inbox_message(sample_message)
        
        assert result is not None
        assert result.content["parser_used"] == "Structured Text"
    
    def test_unstructured_fallback(self, sample_message):
        """Test unstructured parser as final fallback."""
        content = "Found a bug with high severity"
        sample_message.content = content
        
        store = FeedbackStore("test-team")
        result = store.parse_inbox_message(sample_message)
        
        assert result is not None
        assert result.content["parser_used"] == "Unstructured Text"


class TestComplexScenarios:
    """Test complex real-world scenarios."""
    
    def test_code_review_feedback(self, sample_message):
        """Test parsing code review feedback."""
        content = json.dumps({
            "feedback_type": "review",
            "issue_type": "bug",
            "severity": "medium",
            "resolution_time": "2024-01-15T12:00:00Z",
            "file": "src/auth.py",
            "line": 42,
            "description": "Null pointer dereference"
        })
        sample_message.content = content
        
        store = FeedbackStore("test-team")
        result = store.parse_inbox_message(sample_message)
        
        assert result is not None
        assert result.feedback_type == "review"
        assert result.issue_type == "bug"
        assert result.severity == "medium"
        assert "additional_fields" in result.content
        assert result.content["additional_fields"]["file"] == "src/auth.py"
        assert result.content["additional_fields"]["line"] == 42
    
    def test_user_rating_feedback(self, sample_message):
        """Test parsing user rating feedback."""
        content = """
| Field | Value |
|-------|-------|
| Feedback Type | user_rating |
| Quality | high |
| Completion Time | fast |
"""
        sample_message.content = content
        
        store = FeedbackStore("test-team")
        result = store.parse_inbox_message(sample_message)
        
        assert result is not None
        assert result.feedback_type == "user_rating"
    
    def test_performance_feedback(self, sample_message):
        """Test parsing performance feedback."""
        content = """
Feedback Type: performance
Issue Type: performance
Severity: high
Resolution Time: 2024-01-15T12:00:00Z
"""
        sample_message.content = content
        
        store = FeedbackStore("test-team")
        result = store.parse_inbox_message(sample_message)
        
        assert result is not None
        assert result.feedback_type == "performance"
        assert result.issue_type == "performance"
        assert result.severity == "high"
    
    def test_mixed_format_content(self, sample_message):
        """Test content that could match multiple formats."""
        # JSON should take priority
        content = json.dumps({
            "issue_type": "bug",
            "severity": "critical"
        })
        sample_message.content = content
        
        store = FeedbackStore("test-team")
        result = store.parse_inbox_message(sample_message)
        
        assert result is not None
        assert result.content["parser_used"] == "JSON"
