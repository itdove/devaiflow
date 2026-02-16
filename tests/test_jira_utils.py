"""Tests for devflow/jira/utils.py"""

import pytest
from unittest.mock import Mock, MagicMock
from devflow.jira.utils import merge_pr_urls, is_issue_key_pattern, validate_jira_ticket, is_version_field_required, get_field_with_alias
from devflow.jira.exceptions import JiraNotFoundError, JiraAuthError, JiraApiError, JiraConnectionError


class TestMergePrUrls:
    """Test suite for merge_pr_urls function."""

    def test_empty_existing_empty_new(self):
        """Test with both existing and new URLs empty."""
        result = merge_pr_urls("", "")
        assert result == ""

        result = merge_pr_urls(None, "")
        assert result == ""

        result = merge_pr_urls("", None)
        assert result == ""

        result = merge_pr_urls(None, None)
        assert result == ""

    def test_empty_existing_single_new(self):
        """Test adding single URL when no existing URLs."""
        result = merge_pr_urls("", "https://github.com/org/repo/pull/1")
        assert result == "https://github.com/org/repo/pull/1"

        result = merge_pr_urls(None, "https://github.com/org/repo/pull/1")
        assert result == "https://github.com/org/repo/pull/1"

    def test_empty_existing_multiple_new(self):
        """Test adding multiple URLs when no existing URLs."""
        new_urls = "https://github.com/org/repo/pull/1,https://github.com/org/repo/pull/2"
        result = merge_pr_urls("", new_urls)
        assert result == "https://github.com/org/repo/pull/1,https://github.com/org/repo/pull/2"

        result = merge_pr_urls(None, new_urls)
        assert result == "https://github.com/org/repo/pull/1,https://github.com/org/repo/pull/2"

    def test_single_existing_single_new(self):
        """Test merging single existing with single new URL."""
        existing = "https://github.com/org/repo/pull/1"
        new = "https://github.com/org/repo/pull/2"
        result = merge_pr_urls(existing, new)
        assert result == "https://github.com/org/repo/pull/1,https://github.com/org/repo/pull/2"

    def test_multiple_existing_single_new(self):
        """Test merging multiple existing with single new URL."""
        existing = "https://github.com/org/repo/pull/1,https://github.com/org/repo/pull/2"
        new = "https://github.com/org/repo/pull/3"
        result = merge_pr_urls(existing, new)
        assert result == "https://github.com/org/repo/pull/1,https://github.com/org/repo/pull/2,https://github.com/org/repo/pull/3"

    def test_multiple_existing_multiple_new(self):
        """Test merging multiple existing with multiple new URLs."""
        existing = "https://github.com/org/repo/pull/1,https://github.com/org/repo/pull/2"
        new = "https://github.com/org/repo/pull/3,https://github.com/org/repo/pull/4"
        result = merge_pr_urls(existing, new)
        assert result == "https://github.com/org/repo/pull/1,https://github.com/org/repo/pull/2,https://github.com/org/repo/pull/3,https://github.com/org/repo/pull/4"

    def test_duplicate_detection_single(self):
        """Test that duplicate URLs are not added (single URL)."""
        existing = "https://github.com/org/repo/pull/1,https://github.com/org/repo/pull/2"
        new = "https://github.com/org/repo/pull/2"  # Already exists
        result = merge_pr_urls(existing, new)
        assert result == "https://github.com/org/repo/pull/1,https://github.com/org/repo/pull/2"

    def test_duplicate_detection_multiple(self):
        """Test that duplicate URLs are not added (multiple URLs)."""
        existing = "https://github.com/org/repo/pull/1,https://github.com/org/repo/pull/2"
        new = "https://github.com/org/repo/pull/2,https://github.com/org/repo/pull/3"
        result = merge_pr_urls(existing, new)
        # Only PR 3 should be added, PR 2 already exists
        assert result == "https://github.com/org/repo/pull/1,https://github.com/org/repo/pull/2,https://github.com/org/repo/pull/3"

    def test_all_duplicates(self):
        """Test when all new URLs are duplicates."""
        existing = "https://github.com/org/repo/pull/1,https://github.com/org/repo/pull/2"
        new = "https://github.com/org/repo/pull/1,https://github.com/org/repo/pull/2"
        result = merge_pr_urls(existing, new)
        assert result == "https://github.com/org/repo/pull/1,https://github.com/org/repo/pull/2"

    def test_whitespace_handling_existing(self):
        """Test that whitespace is handled correctly in existing URLs."""
        existing = " https://github.com/org/repo/pull/1 , https://github.com/org/repo/pull/2 "
        new = "https://github.com/org/repo/pull/3"
        result = merge_pr_urls(existing, new)
        assert result == "https://github.com/org/repo/pull/1,https://github.com/org/repo/pull/2,https://github.com/org/repo/pull/3"

    def test_whitespace_handling_new(self):
        """Test that whitespace is handled correctly in new URLs."""
        existing = "https://github.com/org/repo/pull/1"
        new = " https://github.com/org/repo/pull/2 , https://github.com/org/repo/pull/3 "
        result = merge_pr_urls(existing, new)
        assert result == "https://github.com/org/repo/pull/1,https://github.com/org/repo/pull/2,https://github.com/org/repo/pull/3"

    def test_empty_string_elements_in_comma_separated(self):
        """Test handling of empty strings between commas."""
        existing = "https://github.com/org/repo/pull/1,,https://github.com/org/repo/pull/2"
        new = "https://github.com/org/repo/pull/3,,https://github.com/org/repo/pull/4"
        result = merge_pr_urls(existing, new)
        # Empty strings should be filtered out
        assert result == "https://github.com/org/repo/pull/1,https://github.com/org/repo/pull/2,https://github.com/org/repo/pull/3,https://github.com/org/repo/pull/4"

    def test_list_input_existing(self):
        """Test with existing URLs as a list (JIRA multiurl field format)."""
        existing = ["https://github.com/org/repo/pull/1", "https://github.com/org/repo/pull/2"]
        new = "https://github.com/org/repo/pull/3"
        result = merge_pr_urls(existing, new)
        assert result == "https://github.com/org/repo/pull/1,https://github.com/org/repo/pull/2,https://github.com/org/repo/pull/3"

    def test_list_input_new(self):
        """Test with new URLs as a list."""
        existing = "https://github.com/org/repo/pull/1"
        new = ["https://github.com/org/repo/pull/2", "https://github.com/org/repo/pull/3"]
        result = merge_pr_urls(existing, new)
        assert result == "https://github.com/org/repo/pull/1,https://github.com/org/repo/pull/2,https://github.com/org/repo/pull/3"

    def test_list_input_both(self):
        """Test with both existing and new URLs as lists."""
        existing = ["https://github.com/org/repo/pull/1", "https://github.com/org/repo/pull/2"]
        new = ["https://github.com/org/repo/pull/3", "https://github.com/org/repo/pull/4"]
        result = merge_pr_urls(existing, new)
        assert result == "https://github.com/org/repo/pull/1,https://github.com/org/repo/pull/2,https://github.com/org/repo/pull/3,https://github.com/org/repo/pull/4"

    def test_list_with_duplicates(self):
        """Test duplicate detection with list inputs."""
        existing = ["https://github.com/org/repo/pull/1", "https://github.com/org/repo/pull/2"]
        new = ["https://github.com/org/repo/pull/2", "https://github.com/org/repo/pull/3"]
        result = merge_pr_urls(existing, new)
        assert result == "https://github.com/org/repo/pull/1,https://github.com/org/repo/pull/2,https://github.com/org/repo/pull/3"

    def test_list_with_whitespace(self):
        """Test whitespace handling with list inputs."""
        existing = [" https://github.com/org/repo/pull/1 ", " https://github.com/org/repo/pull/2 "]
        new = [" https://github.com/org/repo/pull/3 "]
        result = merge_pr_urls(existing, new)
        assert result == "https://github.com/org/repo/pull/1,https://github.com/org/repo/pull/2,https://github.com/org/repo/pull/3"

    def test_list_with_empty_strings(self):
        """Test filtering of empty strings in list inputs."""
        existing = ["https://github.com/org/repo/pull/1", "", "https://github.com/org/repo/pull/2"]
        new = ["https://github.com/org/repo/pull/3", "", ""]
        result = merge_pr_urls(existing, new)
        assert result == "https://github.com/org/repo/pull/1,https://github.com/org/repo/pull/2,https://github.com/org/repo/pull/3"

    def test_preserves_order(self):
        """Test that URL order is preserved (existing first, then new)."""
        existing = "https://github.com/org/repo/pull/3,https://github.com/org/repo/pull/1"
        new = "https://github.com/org/repo/pull/4,https://github.com/org/repo/pull/2"
        result = merge_pr_urls(existing, new)
        # Order should be: existing URLs first, then new URLs in their original order
        assert result == "https://github.com/org/repo/pull/3,https://github.com/org/repo/pull/1,https://github.com/org/repo/pull/4,https://github.com/org/repo/pull/2"

    def test_gitlab_urls(self):
        """Test with GitLab merge request URLs."""
        existing = "https://gitlab.com/org/repo/-/merge_requests/1"
        new = "https://gitlab.com/org/repo/-/merge_requests/2"
        result = merge_pr_urls(existing, new)
        assert result == "https://gitlab.com/org/repo/-/merge_requests/1,https://gitlab.com/org/repo/-/merge_requests/2"

    def test_mixed_github_gitlab_urls(self):
        """Test with mix of GitHub PR and GitLab MR URLs."""
        existing = "https://github.com/org/repo/pull/1"
        new = "https://gitlab.com/org/repo/-/merge_requests/1"
        result = merge_pr_urls(existing, new)
        assert result == "https://github.com/org/repo/pull/1,https://gitlab.com/org/repo/-/merge_requests/1"

    def test_real_world_scenario_complete_command(self):
        """Test real-world scenario from daf complete command."""
        # Simulates daf complete adding a single new PR URL
        existing = "https://github.com/org/repo/pull/1,https://github.com/org/repo/pull/2"
        new = "https://github.com/org/repo/pull/3"
        result = merge_pr_urls(existing, new)
        assert result == "https://github.com/org/repo/pull/1,https://github.com/org/repo/pull/2,https://github.com/org/repo/pull/3"

    def test_real_world_scenario_update_command(self):
        """Test real-world scenario from daf jira update command."""
        # Simulates daf jira update with multiple comma-separated URLs
        existing = "https://github.com/org/repo/pull/1"
        new = "https://github.com/org/repo/pull/2,https://github.com/org/repo/pull/3"
        result = merge_pr_urls(existing, new)
        assert result == "https://github.com/org/repo/pull/1,https://github.com/org/repo/pull/2,https://github.com/org/repo/pull/3"

    def test_real_world_scenario_jira_list_return(self):
        """Test real-world scenario where JIRA returns list instead of string."""
        # Simulates JIRA multiurl field returning a list
        existing = ["https://github.com/org/repo/pull/1", "https://github.com/org/repo/pull/2"]
        new = "https://github.com/org/repo/pull/3"
        result = merge_pr_urls(existing, new)
        assert result == "https://github.com/org/repo/pull/1,https://github.com/org/repo/pull/2,https://github.com/org/repo/pull/3"

    def test_idempotency(self):
        """Test that running merge multiple times with same URL doesn't duplicate it."""
        existing = "https://github.com/org/repo/pull/1"
        new = "https://github.com/org/repo/pull/2"

        # First merge
        result1 = merge_pr_urls(existing, new)
        assert result1 == "https://github.com/org/repo/pull/1,https://github.com/org/repo/pull/2"

        # Second merge with same new URL (simulates daf complete running twice)
        result2 = merge_pr_urls(result1, new)
        assert result2 == "https://github.com/org/repo/pull/1,https://github.com/org/repo/pull/2"

        # Third merge
        result3 = merge_pr_urls(result2, new)
        assert result3 == "https://github.com/org/repo/pull/1,https://github.com/org/repo/pull/2"


class TestIsJiraKeyPattern:
    """Test suite for is_issue_key_pattern function."""

    def test_valid_patterns(self):
        """Test valid issue key patterns."""
        assert is_issue_key_pattern("PROJ-12345") is True
        assert is_issue_key_pattern("MYPROJ-999") is True
        assert is_issue_key_pattern("A-1") is True
        assert is_issue_key_pattern("ABC123-456") is True
        assert is_issue_key_pattern("PROJECT-1") is True

    def test_invalid_patterns(self):
        """Test invalid issue key patterns."""
        # Lowercase project key
        assert is_issue_key_pattern("prok-123") is False
        assert is_issue_key_pattern("myproj-999") is False

        # No hyphen
        assert is_issue_key_pattern("PROK12345") is False

        # No number
        assert is_issue_key_pattern("PROJ-") is False
        assert is_issue_key_pattern("PROJ") is False

        # No project key
        assert is_issue_key_pattern("-12345") is False
        assert is_issue_key_pattern("12345") is False

        # Special characters
        assert is_issue_key_pattern("PROJ_12345") is False
        assert is_issue_key_pattern("PROJ.12345") is False

        # Empty or None
        assert is_issue_key_pattern("") is False
        assert is_issue_key_pattern("invalid") is False

        # Multiple hyphens
        assert is_issue_key_pattern("PROJ-123-456") is False

        # Leading/trailing spaces
        assert is_issue_key_pattern(" PROJ-12345") is False
        assert is_issue_key_pattern("PROJ-12345 ") is False


class TestValidateJiraTicket:
    """Test suite for validate_jira_ticket function."""

    def test_valid_ticket(self, monkeypatch):
        """Test validation of a valid issue tracker ticket."""
        # Create a mock client
        mock_client = MagicMock()
        mock_client.get_ticket.return_value = {
            'key': 'PROJ-12345',
            'type': 'Story',
            'status': 'In Progress',
            'summary': 'Test ticket',
            'assignee': 'user@example.com'
        }

        # Mock console to suppress output during tests
        mock_console = MagicMock()
        monkeypatch.setattr('devflow.jira.utils.console', mock_console)

        # Test with provided client
        result = validate_jira_ticket("PROJ-12345", client=mock_client)

        assert result is not None
        assert result['key'] == 'PROJ-12345'
        assert result['type'] == 'Story'
        mock_client.get_ticket.assert_called_once_with("PROJ-12345")

    def test_ticket_not_found(self, monkeypatch):
        """Test validation when ticket is not found (404)."""
        # Create a mock client that raises JiraNotFoundError
        mock_client = MagicMock()
        mock_client.get_ticket.side_effect = JiraNotFoundError(
            "issue tracker ticket PROJ-99999 not found",
            resource_type="issue",
            resource_id="PROJ-99999"
        )

        # Mock console to capture output
        mock_console = MagicMock()
        monkeypatch.setattr('devflow.jira.utils.console', mock_console)

        # Test validation
        result = validate_jira_ticket("PROJ-99999", client=mock_client)

        assert result is None
        # Verify error message was displayed
        assert mock_console.print.call_count >= 1

    def test_auth_error(self, monkeypatch):
        """Test validation when authentication fails."""
        # Create a mock client that raises JiraAuthError
        mock_client = MagicMock()
        mock_client.get_ticket.side_effect = JiraAuthError(
            "Authentication failed",
            status_code=401
        )

        # Mock console to capture output
        mock_console = MagicMock()
        monkeypatch.setattr('devflow.jira.utils.console', mock_console)

        # Test validation
        result = validate_jira_ticket("PROJ-12345", client=mock_client)

        assert result is None
        # Verify error message was displayed
        assert mock_console.print.call_count >= 1

    def test_api_error(self, monkeypatch):
        """Test validation when JIRA API returns an error."""
        # Create a mock client that raises JiraApiError
        mock_client = MagicMock()
        mock_client.get_ticket.side_effect = JiraApiError(
            "API error occurred",
            status_code=500,
            response_text="Internal server error"
        )

        # Mock console to capture output
        mock_console = MagicMock()
        monkeypatch.setattr('devflow.jira.utils.console', mock_console)

        # Test validation
        result = validate_jira_ticket("PROJ-12345", client=mock_client)

        assert result is None
        # Verify error message was displayed
        assert mock_console.print.call_count >= 1

    def test_connection_error(self, monkeypatch):
        """Test validation when connection to JIRA fails."""
        # Create a mock client that raises JiraConnectionError
        mock_client = MagicMock()
        mock_client.get_ticket.side_effect = JiraConnectionError(
            "Connection failed: Network unreachable"
        )

        # Mock console to capture output
        mock_console = MagicMock()
        monkeypatch.setattr('devflow.jira.utils.console', mock_console)

        # Test validation
        result = validate_jira_ticket("PROJ-12345", client=mock_client)

        assert result is None
        # Verify error message was displayed
        assert mock_console.print.call_count >= 1

    def test_unexpected_error(self, monkeypatch):
        """Test validation when an unexpected error occurs."""
        # Create a mock client that raises a generic exception
        mock_client = MagicMock()
        mock_client.get_ticket.side_effect = Exception("Unexpected error")

        # Mock console to capture output
        mock_console = MagicMock()
        monkeypatch.setattr('devflow.jira.utils.console', mock_console)

        # Test validation
        result = validate_jira_ticket("PROJ-12345", client=mock_client)

        assert result is None
        # Verify error message was displayed
        assert mock_console.print.call_count >= 1

    def test_create_client_if_none_provided(self, monkeypatch):
        """Test that client is created if none is provided."""
        # Mock JiraClient constructor
        mock_jira_client_class = MagicMock()
        mock_client_instance = MagicMock()
        mock_client_instance.get_ticket.return_value = {
            'key': 'PROJ-12345',
            'type': 'Story',
            'status': 'New',
            'summary': 'Test',
            'assignee': None
        }
        mock_jira_client_class.return_value = mock_client_instance

        # Mock the JiraClient import (patch where it's imported FROM in validate_jira_ticket)
        import devflow.jira.utils
        monkeypatch.setattr('devflow.jira.JiraClient', mock_jira_client_class)

        # Mock console to suppress output
        mock_console = MagicMock()
        monkeypatch.setattr('devflow.jira.utils.console', mock_console)

        # Test validation without providing client
        result = validate_jira_ticket("PROJ-12345", client=None)

        assert result is not None
        assert result['key'] == 'PROJ-12345'
        # Verify client was created
        mock_jira_client_class.assert_called_once()

    def test_client_creation_fails(self, monkeypatch):
        """Test when client creation fails."""
        # Mock JiraClient constructor to raise exception
        mock_jira_client_class = MagicMock()
        mock_jira_client_class.side_effect = Exception("Failed to create client")

        # Mock the JiraClient import (patch where it's imported FROM in validate_jira_ticket)
        import devflow.jira.utils
        monkeypatch.setattr('devflow.jira.JiraClient', mock_jira_client_class)

        # Mock console to capture output
        mock_console = MagicMock()
        monkeypatch.setattr('devflow.jira.utils.console', mock_console)

        # Test validation
        result = validate_jira_ticket("PROJ-12345", client=None)

        assert result is None
        # Verify error message was displayed
        assert mock_console.print.call_count >= 1

class TestIsVersionFieldRequired:
    """Test suite for is_version_field_required function."""

    def test_no_issue_type_provided(self):
        """Test returns False when issue_type is None."""
        result = is_version_field_required(field_mapper=None, issue_type=None)
        assert result is False

    def test_no_field_mapper_provided(self):
        """Test returns False when field_mapper is None."""
        result = is_version_field_required(field_mapper=None, issue_type="Bug")
        assert result is False

    def test_field_mapper_no_mappings(self):
        """Test returns False when field_mapper has no field_mappings."""
        mock_field_mapper = MagicMock()
        mock_field_mapper.field_mappings = None
        result = is_version_field_required(field_mapper=mock_field_mapper, issue_type="Bug")
        assert result is False

    def test_version_required_for_bug_strategy1(self):
        """Test version field required for Bug using Strategy 1 (specific field name)."""
        mock_field_mapper = MagicMock()
        mock_field_mapper.field_mappings = {
            "affects_version/s": {
                "id": "versions",
                "name": "Affects Version/s",
                "required_for": ["Bug"],
                "allowed_values": ["v1.0.0", "v2.0.0"]
            }
        }
        result = is_version_field_required(field_mapper=mock_field_mapper, issue_type="Bug")
        assert result is True

    def test_version_not_required_for_story_strategy1(self):
        """Test version field not required for Story when only Bug is in required_for."""
        mock_field_mapper = MagicMock()
        mock_field_mapper.field_mappings = {
            "affects_version/s": {
                "id": "versions",
                "name": "Affects Version/s",
                "required_for": ["Bug"],
                "allowed_values": ["v1.0.0", "v2.0.0"]
            }
        }
        result = is_version_field_required(field_mapper=mock_field_mapper, issue_type="Story")
        assert result is False

    def test_version_required_for_multiple_types(self):
        """Test version field required for multiple issue types."""
        mock_field_mapper = MagicMock()
        mock_field_mapper.field_mappings = {
            "affects_version/s": {
                "id": "versions",
                "name": "Affects Version/s",
                "required_for": ["Bug", "Story", "Task"],
                "allowed_values": ["v1.0.0"]
            }
        }
        assert is_version_field_required(field_mapper=mock_field_mapper, issue_type="Bug") is True
        assert is_version_field_required(field_mapper=mock_field_mapper, issue_type="Story") is True
        assert is_version_field_required(field_mapper=mock_field_mapper, issue_type="Task") is True
        assert is_version_field_required(field_mapper=mock_field_mapper, issue_type="Epic") is False

    def test_version_field_strategy2_generic_match(self):
        """Test version field required using Strategy 2 (generic field name with 'version' or 'affect')."""
        mock_field_mapper = MagicMock()
        mock_field_mapper.field_mappings = {
            "affected_version": {
                "id": "customfield_12345",
                "name": "Affected Version",
                "required_for": ["Bug"],
                "allowed_values": ["v1.0.0"]
            }
        }
        result = is_version_field_required(field_mapper=mock_field_mapper, issue_type="Bug")
        assert result is True

    def test_version_field_empty_required_for(self):
        """Test version field with empty required_for list."""
        mock_field_mapper = MagicMock()
        mock_field_mapper.field_mappings = {
            "affects_version/s": {
                "id": "versions",
                "name": "Affects Version/s",
                "required_for": [],
                "allowed_values": ["v1.0.0"]
            }
        }
        result = is_version_field_required(field_mapper=mock_field_mapper, issue_type="Bug")
        assert result is False

    def test_version_field_missing_required_for(self):
        """Test version field without required_for field (defaults to empty list)."""
        mock_field_mapper = MagicMock()
        mock_field_mapper.field_mappings = {
            "affects_version/s": {
                "id": "versions",
                "name": "Affects Version/s",
                "allowed_values": ["v1.0.0"]
            }
        }
        result = is_version_field_required(field_mapper=mock_field_mapper, issue_type="Bug")
        assert result is False

    def test_multiple_version_fields_one_required(self):
        """Test when multiple version-related fields exist but only one is required."""
        mock_field_mapper = MagicMock()
        mock_field_mapper.field_mappings = {
            "affects_version/s": {
                "id": "versions",
                "name": "Affects Version/s",
                "required_for": [],
                "allowed_values": ["v1.0.0"]
            },
            "affected_version": {
                "id": "customfield_12345",
                "name": "Affected Version",
                "required_for": ["Bug"],
                "allowed_values": ["v1.0.0"]
            }
        }
        assert is_version_field_required(field_mapper=mock_field_mapper, issue_type="Bug") is True
        assert is_version_field_required(field_mapper=mock_field_mapper, issue_type="Story") is False

    def test_case_sensitive_issue_type(self):
        """Test that issue_type matching is case-sensitive."""
        mock_field_mapper = MagicMock()
        mock_field_mapper.field_mappings = {
            "affects_version/s": {
                "id": "versions",
                "name": "Affects Version/s",
                "required_for": ["Bug"],  # Capital B
                "allowed_values": ["v1.0.0"]
            }
        }
        # Should match with capital B
        assert is_version_field_required(field_mapper=mock_field_mapper, issue_type="Bug") is True
        # Should not match with lowercase b
        assert is_version_field_required(field_mapper=mock_field_mapper, issue_type="bug") is False


class TestGetFieldWithAlias:
    """Test suite for get_field_with_alias function - backward compatibility for server/cloud field names."""

    def test_field_exists_with_old_name(self):
        """Test getting field when it exists with old server name (component/s)."""
        field_mappings = {
            "component/s": {
                "id": "components",
                "name": "Component/s",
                "allowed_values": ["backend", "frontend"]
            }
        }
        # Should find it when searching with old name
        result = get_field_with_alias(field_mappings, "component/s")
        assert result is not None
        assert result["id"] == "components"

        # Should find it when searching with new name (alias lookup)
        result = get_field_with_alias(field_mappings, "components")
        assert result is not None
        assert result["id"] == "components"

    def test_field_exists_with_new_name(self):
        """Test getting field when it exists with new cloud name (components)."""
        field_mappings = {
            "components": {
                "id": "components",
                "name": "Components",
                "allowed_values": ["backend", "frontend"]
            }
        }
        # Should find it when searching with new name
        result = get_field_with_alias(field_mappings, "components")
        assert result is not None
        assert result["id"] == "components"

        # Should find it when searching with old name (reverse alias lookup)
        result = get_field_with_alias(field_mappings, "component/s")
        assert result is not None
        assert result["id"] == "components"

    def test_affects_versions_old_name(self):
        """Test getting affects_versions field with old server name."""
        field_mappings = {
            "affects_version/s": {
                "id": "versions",
                "name": "Affects Version/s",
                "allowed_values": ["v1.0.0", "v2.0.0"]
            }
        }
        # Should find it when searching with old name
        result = get_field_with_alias(field_mappings, "affects_version/s")
        assert result is not None
        assert result["id"] == "versions"

        # Should find it when searching with new name (alias lookup)
        result = get_field_with_alias(field_mappings, "affects_versions")
        assert result is not None
        assert result["id"] == "versions"

    def test_affects_versions_new_name(self):
        """Test getting affects_versions field with new cloud name."""
        field_mappings = {
            "affects_versions": {
                "id": "versions",
                "name": "Affects Versions",
                "allowed_values": ["v1.0.0", "v2.0.0"]
            }
        }
        # Should find it when searching with new name
        result = get_field_with_alias(field_mappings, "affects_versions")
        assert result is not None
        assert result["id"] == "versions"

        # Should find it when searching with old name (reverse alias lookup)
        result = get_field_with_alias(field_mappings, "affects_version/s")
        assert result is not None
        assert result["id"] == "versions"

    def test_field_not_found(self):
        """Test when field doesn't exist in mappings."""
        field_mappings = {
            "other_field": {
                "id": "customfield_12345",
                "name": "Other Field"
            }
        }
        # Should return None when field not found
        result = get_field_with_alias(field_mappings, "components")
        assert result is None

        result = get_field_with_alias(field_mappings, "component/s")
        assert result is None

    def test_empty_field_mappings(self):
        """Test with empty field mappings."""
        field_mappings = {}
        result = get_field_with_alias(field_mappings, "components")
        assert result is None

    def test_non_aliased_field(self):
        """Test getting a field that doesn't have an alias."""
        field_mappings = {
            "priority": {
                "id": "priority",
                "name": "Priority"
            }
        }
        # Should still work for non-aliased fields
        result = get_field_with_alias(field_mappings, "priority")
        assert result is not None
        assert result["id"] == "priority"

        # Should return None for non-existent field
        result = get_field_with_alias(field_mappings, "nonexistent")
        assert result is None
