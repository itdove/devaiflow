"""Tests for jira_update_command functions (update_jira_issue and build_field_value)."""

import pytest
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch, mock_open

from devflow.cli.commands.jira_update_command import (
    build_field_value,
    update_jira_issue,
)
from devflow.config.models import Config, JiraConfig
from devflow.jira.exceptions import (
    JiraValidationError,
    JiraNotFoundError,
    JiraAuthError,
    JiraApiError,
    JiraConnectionError,
)


@pytest.fixture
def mock_config():
    """Create a mock config object."""
    config = Mock(spec=Config)
    config.jira = Mock(spec=JiraConfig)
    config.jira.url = "https://jira.example.com"
    config.jira.project = "PROJ"
    config.jira.field_mappings = {
        "workstream": {"id": "customfield_12319275"},
        "acceptance_criteria": {"id": "customfield_12315940"}
    }
    return config


@pytest.fixture
def mock_field_mapper():
    """Create a mock field mapper."""
    mapper = MagicMock()
    mapper.get_field_id.side_effect = lambda field_name: {
        "acceptance_criteria": "customfield_12315940",
        "workstream": "customfield_12319275",
        "git_pull_request": "customfield_12310220",
    }.get(field_name, None)
    mapper._cache = {
        "workstream": {"id": "customfield_12319275", "name": "Workstream"},
        "acceptance_criteria": {"id": "customfield_12315940", "name": "Acceptance Criteria"},
    }
    mapper.discover_editable_fields.return_value = {
        "workstream": {
            "id": "customfield_12319275",
            "type": "array",
            "schema": "array_option",  # Contains "option" to trigger [{"value": v}] format
            "allowed_values": ["Platform", "Core", "Backend"]
        },
        "acceptance_criteria": {
            "id": "customfield_12315940",
            "type": "string",
            "schema": "string"
        }
    }
    return mapper


class TestBuildFieldValue:
    """Tests for build_field_value function."""

    def test_multiurl_field(self):
        """Test building value for multiurl field."""
        field_info = {"type": "string", "schema": "multiurl"}
        result = build_field_value(field_info, "https://example.com", Mock())
        assert result == "https://example.com"

    def test_url_field(self):
        """Test building value for URL field."""
        field_info = {"type": "string", "schema": "url"}
        result = build_field_value(field_info, "https://github.com/org/repo/pull/123", Mock())
        assert result == "https://github.com/org/repo/pull/123"

    def test_option_field(self):
        """Test building value for single-select option field."""
        field_info = {"type": "option", "schema": "option"}
        result = build_field_value(field_info, "Platform", Mock())
        assert result == {"value": "Platform"}

    def test_custom_select_field(self):
        """Test building value for custom select field."""
        field_info = {"type": "string", "schema": "com.atlassian.jira.plugin.system.customfieldtypes:select"}
        result = build_field_value(field_info, "High", Mock())
        assert result == {"value": "High"}

    def test_array_with_option_schema(self):
        """Test building value for array field with option schema."""
        field_info = {"type": "array", "schema": "array-option"}
        result = build_field_value(field_info, "Platform", Mock())
        assert result == [{"value": "Platform"}]

    def test_array_of_strings(self):
        """Test building value for array of strings."""
        field_info = {"type": "array", "schema": "array"}
        result = build_field_value(field_info, "value1", Mock())
        assert result == ["value1"]

    def test_priority_field(self):
        """Test building value for priority field."""
        field_info = {"type": "priority", "schema": "priority"}
        result = build_field_value(field_info, "Critical", Mock())
        assert result == {"name": "Critical"}

    def test_user_field_with_username(self):
        """Test building value for user field with username."""
        field_info = {"type": "user", "schema": "user"}
        result = build_field_value(field_info, "johndoe", Mock())
        assert result == {"name": "johndoe"}

    def test_user_field_with_none(self):
        """Test building value for user field to clear assignee."""
        field_info = {"type": "user", "schema": "user"}
        result = build_field_value(field_info, "none", Mock())
        assert result is None

    def test_default_string_field(self):
        """Test building value for default string field."""
        field_info = {"type": "string", "schema": "string"}
        result = build_field_value(field_info, "Plain text value", Mock())
        assert result == "Plain text value"


class TestUpdateJiraIssue:
    """Tests for update_jira_issue function."""

    def test_no_config(self):
        """Test update when config doesn't exist."""
        mock_loader = Mock()
        mock_loader.load_config.return_value = None

        with patch('devflow.cli.commands.jira_update_command.ConfigLoader', return_value=mock_loader):
            with pytest.raises(SystemExit):
                update_jira_issue("PROJ-12345", summary="New summary")

    def test_no_jira_config(self, mock_config):
        """Test update when JIRA config doesn't exist."""
        mock_config.jira = None

        mock_loader = Mock()
        mock_loader.load_config.return_value = mock_config

        with patch('devflow.cli.commands.jira_update_command.ConfigLoader', return_value=mock_loader):
            with pytest.raises(SystemExit):
                update_jira_issue("PROJ-12345", summary="New summary")

    def test_update_description_from_string(self, mock_config, mock_field_mapper):
        """Test updating description from string."""
        mock_loader = Mock()
        mock_loader.load_config.return_value = mock_config

        mock_client = Mock()
        mock_client.update_issue = Mock()

        with patch('devflow.cli.commands.jira_update_command.ConfigLoader', return_value=mock_loader):
            with patch('devflow.cli.commands.jira_update_command.JiraClient', return_value=mock_client):
                with patch('devflow.cli.commands.jira_update_command.JiraFieldMapper', return_value=mock_field_mapper):
                    update_jira_issue("PROJ-12345", description="New description text")

                    mock_client.update_issue.assert_called_once()
                    call_args = mock_client.update_issue.call_args
                    assert call_args[0][0] == "PROJ-12345"
                    assert call_args[0][1]["fields"]["description"] == "New description text"

    def test_update_description_from_file(self, mock_config, mock_field_mapper, tmp_path):
        """Test updating description from file."""
        desc_file = tmp_path / "desc.txt"
        desc_file.write_text("Description from file")

        mock_loader = Mock()
        mock_loader.load_config.return_value = mock_config

        mock_client = Mock()
        mock_client.update_issue = Mock()

        with patch('devflow.cli.commands.jira_update_command.ConfigLoader', return_value=mock_loader):
            with patch('devflow.cli.commands.jira_update_command.JiraClient', return_value=mock_client):
                with patch('devflow.cli.commands.jira_update_command.JiraFieldMapper', return_value=mock_field_mapper):
                    update_jira_issue("PROJ-12345", description_file=str(desc_file))

                    call_args = mock_client.update_issue.call_args
                    assert call_args[0][1]["fields"]["description"] == "Description from file"

    def test_update_description_file_not_found(self, mock_config, mock_field_mapper):
        """Test error when description file doesn't exist."""
        mock_loader = Mock()
        mock_loader.load_config.return_value = mock_config

        with patch('devflow.cli.commands.jira_update_command.ConfigLoader', return_value=mock_loader):
            with patch('devflow.cli.commands.jira_update_command.JiraClient'):
                with pytest.raises(SystemExit):
                    update_jira_issue("PROJ-12345", description_file="/nonexistent/file.txt")

    def test_update_summary(self, mock_config, mock_field_mapper):
        """Test updating summary."""
        mock_loader = Mock()
        mock_loader.load_config.return_value = mock_config

        mock_client = Mock()

        with patch('devflow.cli.commands.jira_update_command.ConfigLoader', return_value=mock_loader):
            with patch('devflow.cli.commands.jira_update_command.JiraClient', return_value=mock_client):
                with patch('devflow.cli.commands.jira_update_command.JiraFieldMapper', return_value=mock_field_mapper):
                    update_jira_issue("PROJ-12345", summary="New summary")

                    call_args = mock_client.update_issue.call_args
                    assert call_args[0][1]["fields"]["summary"] == "New summary"

    def test_update_priority(self, mock_config, mock_field_mapper):
        """Test updating priority."""
        mock_loader = Mock()
        mock_loader.load_config.return_value = mock_config

        mock_client = Mock()

        with patch('devflow.cli.commands.jira_update_command.ConfigLoader', return_value=mock_loader):
            with patch('devflow.cli.commands.jira_update_command.JiraClient', return_value=mock_client):
                with patch('devflow.cli.commands.jira_update_command.JiraFieldMapper', return_value=mock_field_mapper):
                    update_jira_issue("PROJ-12345", priority="Critical")

                    call_args = mock_client.update_issue.call_args
                    assert call_args[0][1]["fields"]["priority"] == {"name": "Critical"}

    def test_update_assignee(self, mock_config, mock_field_mapper):
        """Test updating assignee."""
        mock_loader = Mock()
        mock_loader.load_config.return_value = mock_config

        mock_client = Mock()

        with patch('devflow.cli.commands.jira_update_command.ConfigLoader', return_value=mock_loader):
            with patch('devflow.cli.commands.jira_update_command.JiraClient', return_value=mock_client):
                with patch('devflow.cli.commands.jira_update_command.JiraFieldMapper', return_value=mock_field_mapper):
                    update_jira_issue("PROJ-12345", assignee="johndoe")

                    call_args = mock_client.update_issue.call_args
                    assert call_args[0][1]["fields"]["assignee"] == {"name": "johndoe"}

    def test_clear_assignee(self, mock_config, mock_field_mapper):
        """Test clearing assignee with 'none'."""
        mock_loader = Mock()
        mock_loader.load_config.return_value = mock_config

        mock_client = Mock()

        with patch('devflow.cli.commands.jira_update_command.ConfigLoader', return_value=mock_loader):
            with patch('devflow.cli.commands.jira_update_command.JiraClient', return_value=mock_client):
                with patch('devflow.cli.commands.jira_update_command.JiraFieldMapper', return_value=mock_field_mapper):
                    update_jira_issue("PROJ-12345", assignee="none")

                    call_args = mock_client.update_issue.call_args
                    assert call_args[0][1]["fields"]["assignee"] is None

    def test_update_acceptance_criteria(self, mock_config, mock_field_mapper):
        """Test updating acceptance criteria via custom fields."""
        mock_loader = Mock()
        mock_loader.load_config.return_value = mock_config

        mock_client = Mock()

        with patch('devflow.cli.commands.jira_update_command.ConfigLoader', return_value=mock_loader):
            with patch('devflow.cli.commands.jira_update_command.JiraClient', return_value=mock_client):
                with patch('devflow.cli.commands.jira_update_command.JiraFieldMapper', return_value=mock_field_mapper):
                    update_jira_issue("PROJ-12345", acceptance_criteria="New AC")

                    call_args = mock_client.update_issue.call_args
                    assert call_args[0][1]["fields"]["customfield_12315940"] == "New AC"

    def test_update_workstream(self, mock_config, mock_field_mapper):
        """Test updating workstream."""
        mock_loader = Mock()
        mock_loader.load_config.return_value = mock_config

        mock_client = Mock()

        with patch('devflow.cli.commands.jira_update_command.ConfigLoader', return_value=mock_loader):
            with patch('devflow.cli.commands.jira_update_command.JiraClient', return_value=mock_client):
                with patch('devflow.cli.commands.jira_update_command.JiraFieldMapper', return_value=mock_field_mapper):
                    update_jira_issue("PROJ-12345", workstream="Platform")

                    call_args = mock_client.update_issue.call_args
                    assert call_args[0][1]["fields"]["customfield_12319275"] == [{"value": "Platform"}]

    def test_update_git_pull_request(self, mock_config, mock_field_mapper):
        """Test updating git pull request links."""
        mock_loader = Mock()
        mock_loader.load_config.return_value = mock_config

        mock_client = Mock()
        mock_client.get_ticket_pr_links.return_value = "https://github.com/org/repo/pull/1"

        with patch('devflow.cli.commands.jira_update_command.ConfigLoader', return_value=mock_loader):
            with patch('devflow.cli.commands.jira_update_command.JiraClient', return_value=mock_client):
                with patch('devflow.cli.commands.jira_update_command.JiraFieldMapper', return_value=mock_field_mapper):
                    with patch('devflow.cli.commands.jira_update_command.merge_pr_urls') as mock_merge:
                        mock_merge.return_value = "https://github.com/org/repo/pull/1,https://github.com/org/repo/pull/2"

                        update_jira_issue("PROJ-12345", git_pull_request="https://github.com/org/repo/pull/2")

                        mock_client.get_ticket_pr_links.assert_called_once_with("PROJ-12345")
                        mock_merge.assert_called_once()

    def test_git_pull_request_not_found_error(self, mock_config, mock_field_mapper):
        """Test error handling when issue not found during PR fetch."""
        mock_loader = Mock()
        mock_loader.load_config.return_value = mock_config

        mock_client = Mock()
        mock_client.get_ticket_pr_links.side_effect = JiraNotFoundError("Issue not found")

        with patch('devflow.cli.commands.jira_update_command.ConfigLoader', return_value=mock_loader):
            with patch('devflow.cli.commands.jira_update_command.JiraClient', return_value=mock_client):
                with patch('devflow.cli.commands.jira_update_command.JiraFieldMapper', return_value=mock_field_mapper):
                    with pytest.raises(SystemExit):
                        update_jira_issue("PROJ-12345", git_pull_request="https://github.com/org/repo/pull/2")

    def test_git_pull_request_auth_error(self, mock_config, mock_field_mapper):
        """Test error handling when auth fails during PR fetch."""
        mock_loader = Mock()
        mock_loader.load_config.return_value = mock_config

        mock_client = Mock()
        mock_client.get_ticket_pr_links.side_effect = JiraAuthError("Auth failed")

        with patch('devflow.cli.commands.jira_update_command.ConfigLoader', return_value=mock_loader):
            with patch('devflow.cli.commands.jira_update_command.JiraClient', return_value=mock_client):
                with patch('devflow.cli.commands.jira_update_command.JiraFieldMapper', return_value=mock_field_mapper):
                    with pytest.raises(SystemExit):
                        update_jira_issue("PROJ-12345", git_pull_request="https://github.com/org/repo/pull/2")

    def test_no_fields_specified(self, mock_config, mock_field_mapper):
        """Test error when no fields are specified."""
        mock_loader = Mock()
        mock_loader.load_config.return_value = mock_config

        with patch('devflow.cli.commands.jira_update_command.ConfigLoader', return_value=mock_loader):
            with patch('devflow.cli.commands.jira_update_command.JiraClient'):
                with patch('devflow.cli.commands.jira_update_command.JiraFieldMapper', return_value=mock_field_mapper):
                    with pytest.raises(SystemExit):
                        update_jira_issue("PROJ-12345")

    def test_issue_linking_missing_linked_issue(self, mock_config, mock_field_mapper):
        """Test error when --issue provided without --linked-issue."""
        mock_loader = Mock()
        mock_loader.load_config.return_value = mock_config

        with patch('devflow.cli.commands.jira_update_command.ConfigLoader', return_value=mock_loader):
            with patch('devflow.cli.commands.jira_update_command.JiraClient'):
                with patch('devflow.cli.commands.jira_update_command.JiraFieldMapper', return_value=mock_field_mapper):
                    with pytest.raises(SystemExit):
                        update_jira_issue("PROJ-12345", issue="PROJ-999")

    def test_issue_linking_missing_issue(self, mock_config, mock_field_mapper):
        """Test error when --linked-issue provided without --issue."""
        mock_loader = Mock()
        mock_loader.load_config.return_value = mock_config

        with patch('devflow.cli.commands.jira_update_command.ConfigLoader', return_value=mock_loader):
            with patch('devflow.cli.commands.jira_update_command.JiraClient'):
                with patch('devflow.cli.commands.jira_update_command.JiraFieldMapper', return_value=mock_field_mapper):
                    with pytest.raises(SystemExit):
                        update_jira_issue("PROJ-12345", linked_issue="blocks")

    def test_issue_linking_success(self, mock_config, mock_field_mapper):
        """Test successful issue linking."""
        mock_loader = Mock()
        mock_loader.load_config.return_value = mock_config

        mock_client = Mock()
        mock_client.update_issue = Mock()
        mock_client.link_issues = Mock()

        with patch('devflow.cli.commands.jira_update_command.ConfigLoader', return_value=mock_loader):
            with patch('devflow.cli.commands.jira_update_command.JiraClient', return_value=mock_client):
                with patch('devflow.cli.commands.jira_update_command.JiraFieldMapper', return_value=mock_field_mapper):
                    with patch('devflow.jira.utils.validate_jira_ticket', return_value={"key": "PROJ-999"}):
                        update_jira_issue("PROJ-12345", summary="Test", linked_issue="blocks", issue="PROJ-999")

                        mock_client.link_issues.assert_called_once_with(
                            issue_key="PROJ-12345",
                            link_to_issue_key="PROJ-999",
                            link_type_description="blocks"
                        )

    def test_issue_linking_invalid_linked_issue(self, mock_config, mock_field_mapper):
        """Test error when linked issue is invalid."""
        mock_loader = Mock()
        mock_loader.load_config.return_value = mock_config

        with patch('devflow.cli.commands.jira_update_command.ConfigLoader', return_value=mock_loader):
            with patch('devflow.cli.commands.jira_update_command.JiraClient'):
                with patch('devflow.cli.commands.jira_update_command.JiraFieldMapper', return_value=mock_field_mapper):
                    with patch('devflow.jira.utils.validate_jira_ticket', return_value=None):
                        with pytest.raises(SystemExit):
                            update_jira_issue("PROJ-12345", summary="Test", linked_issue="blocks", issue="INVALID-999")

    def test_issue_linking_validation_error(self, mock_config, mock_field_mapper):
        """Test handling of validation error during linking."""
        mock_loader = Mock()
        mock_loader.load_config.return_value = mock_config

        mock_client = Mock()
        mock_client.update_issue = Mock()
        error = JiraValidationError("Invalid link type", error_messages=["Available types: blocks, is blocked by"])
        mock_client.link_issues.side_effect = error

        with patch('devflow.cli.commands.jira_update_command.ConfigLoader', return_value=mock_loader):
            with patch('devflow.cli.commands.jira_update_command.JiraClient', return_value=mock_client):
                with patch('devflow.cli.commands.jira_update_command.JiraFieldMapper', return_value=mock_field_mapper):
                    with patch('devflow.jira.utils.validate_jira_ticket', return_value={"key": "PROJ-999"}):
                        with pytest.raises(SystemExit):
                            update_jira_issue("PROJ-12345", summary="Test", linked_issue="invalid-type", issue="PROJ-999")

    def test_json_output_success(self, mock_config, mock_field_mapper):
        """Test JSON output on successful update."""
        mock_loader = Mock()
        mock_loader.load_config.return_value = mock_config

        mock_client = Mock()

        with patch('devflow.cli.commands.jira_update_command.ConfigLoader', return_value=mock_loader):
            with patch('devflow.cli.commands.jira_update_command.JiraClient', return_value=mock_client):
                with patch('devflow.cli.commands.jira_update_command.JiraFieldMapper', return_value=mock_field_mapper):
                    with patch('devflow.cli.commands.jira_update_command.json_output') as mock_json:
                        update_jira_issue("PROJ-12345", summary="Test", output_json=True)

                        mock_json.assert_called_once()
                        call_args = mock_json.call_args
                        assert call_args[1]['success'] is True
                        assert call_args[1]['data']['issue_key'] == "PROJ-12345"

    def test_json_output_on_error(self, mock_config, mock_field_mapper):
        """Test JSON output on error."""
        mock_loader = Mock()
        mock_loader.load_config.return_value = mock_config

        with patch('devflow.cli.commands.jira_update_command.ConfigLoader', return_value=mock_loader):
            with patch('devflow.cli.commands.jira_update_command.JiraClient'):
                with patch('devflow.cli.commands.jira_update_command.JiraFieldMapper', return_value=mock_field_mapper):
                    with patch('devflow.cli.commands.jira_update_command.json_output') as mock_json:
                        with pytest.raises(SystemExit):
                            update_jira_issue("PROJ-12345", output_json=True)

                        mock_json.assert_called_once()
                        call_args = mock_json.call_args
                        assert call_args[1]['success'] is False
