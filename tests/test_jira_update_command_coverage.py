"""Additional tests for jira_update_command.py to improve coverage."""

import pytest
from unittest.mock import Mock, MagicMock, patch, mock_open
from devflow.cli.commands.jira_update_command import update_jira_issue, build_field_value
from devflow.jira.exceptions import JiraApiError, JiraNotFoundError, JiraAuthError, JiraConnectionError


@pytest.fixture
def mock_env(monkeypatch):
    """Set up environment variables."""
    monkeypatch.setenv("JIRA_API_TOKEN", "mock-token")
    monkeypatch.setenv("JIRA_URL", "https://jira.example.com")


def test_update_issue_no_field_mappings(mock_env, monkeypatch, temp_daf_home):
    """Test update with no cached field mappings."""
    mock_client = MagicMock()
    mock_client.update_issue = MagicMock()
    mock_client.get_ticket_detailed = MagicMock(return_value={})

    mock_mapper = MagicMock()
    mock_mapper.get_field_id = MagicMock(return_value=None)

    with patch("devflow.cli.commands.jira_update_command.JiraClient", return_value=mock_client):
        with patch("devflow.cli.commands.jira_update_command.JiraFieldMapper", return_value=mock_mapper):
            with patch("devflow.cli.commands.jira_update_command.ConfigLoader") as mock_config_loader:
                mock_config = MagicMock()
                mock_config.jira.field_mappings = None  # No cached mappings
                mock_config_loader.return_value.load_config.return_value = mock_config

                # Should print message about no cached field mappings
                update_jira_issue("TEST-123", summary="New summary")


def test_update_issue_description_from_file_error(mock_env, monkeypatch, temp_daf_home):
    """Test update with file read error."""
    with patch("devflow.cli.commands.jira_update_command.ConfigLoader"):
        with patch("builtins.open", side_effect=FileNotFoundError("File not found")):
            with pytest.raises(SystemExit) as exc_info:
                update_jira_issue("TEST-123", description_file="/nonexistent/file.txt")
            assert exc_info.value.code == 1


def test_update_issue_git_pr_not_found_error(mock_env, monkeypatch, temp_daf_home):
    """Test git PR update when ticket not found."""
    mock_client = MagicMock()
    mock_client.get_ticket_pr_links = MagicMock(side_effect=JiraNotFoundError("Ticket not found"))

    with patch("devflow.cli.commands.jira_update_command.JiraClient", return_value=mock_client):
        with patch("devflow.cli.commands.jira_update_command.ConfigLoader"):
            with patch("devflow.cli.commands.jira_update_command.JiraFieldMapper"):
                with pytest.raises(SystemExit) as exc_info:
                    update_jira_issue("TEST-123", git_pull_request="https://github.com/org/repo/pull/1")
                assert exc_info.value.code == 1


def test_update_issue_git_pr_not_found_json_output(mock_env, monkeypatch, temp_daf_home):
    """Test git PR update error with JSON output."""
    mock_client = MagicMock()
    mock_client.get_ticket_pr_links = MagicMock(side_effect=JiraNotFoundError("Ticket not found"))

    with patch("devflow.cli.commands.jira_update_command.JiraClient", return_value=mock_client):
        with patch("devflow.cli.commands.jira_update_command.ConfigLoader"):
            with patch("devflow.cli.commands.jira_update_command.JiraFieldMapper"):
                with patch("devflow.cli.commands.jira_update_command.json_output") as mock_json:
                    with pytest.raises(SystemExit):
                        update_jira_issue("TEST-123", git_pull_request="https://github.com/org/repo/pull/1", output_json=True)
                    mock_json.assert_called_once()
                    assert mock_json.call_args[1]["success"] is False
                    assert mock_json.call_args[1]["error"]["code"] == "NOT_FOUND"


def test_update_issue_git_pr_api_error(mock_env, monkeypatch, temp_daf_home):
    """Test git PR update with API error."""
    mock_client = MagicMock()
    mock_client.get_ticket_pr_links = MagicMock(side_effect=JiraApiError("API error"))

    with patch("devflow.cli.commands.jira_update_command.JiraClient", return_value=mock_client):
        with patch("devflow.cli.commands.jira_update_command.ConfigLoader"):
            with patch("devflow.cli.commands.jira_update_command.JiraFieldMapper"):
                with pytest.raises(SystemExit) as exc_info:
                    update_jira_issue("TEST-123", git_pull_request="https://github.com/org/repo/pull/1")
                assert exc_info.value.code == 1


def test_update_issue_git_pr_api_error_json_output(mock_env, monkeypatch, temp_daf_home):
    """Test git PR API error with JSON output."""
    mock_client = MagicMock()
    mock_client.get_ticket_pr_links = MagicMock(side_effect=JiraAuthError("Auth error"))

    with patch("devflow.cli.commands.jira_update_command.JiraClient", return_value=mock_client):
        with patch("devflow.cli.commands.jira_update_command.ConfigLoader"):
            with patch("devflow.cli.commands.jira_update_command.JiraFieldMapper"):
                with patch("devflow.cli.commands.jira_update_command.json_output") as mock_json:
                    with pytest.raises(SystemExit):
                        update_jira_issue("TEST-123", git_pull_request="https://github.com/org/repo/pull/1", output_json=True)
                    assert mock_json.call_args[1]["error"]["code"] == "API_ERROR"


def test_update_issue_git_pr_connection_error(mock_env, monkeypatch, temp_daf_home):
    """Test git PR update with connection error."""
    mock_client = MagicMock()
    mock_client.get_ticket_pr_links = MagicMock(side_effect=JiraConnectionError("Connection error"))

    with patch("devflow.cli.commands.jira_update_command.JiraClient", return_value=mock_client):
        with patch("devflow.cli.commands.jira_update_command.ConfigLoader"):
            with patch("devflow.cli.commands.jira_update_command.JiraFieldMapper"):
                with pytest.raises(SystemExit):
                    update_jira_issue("TEST-123", git_pull_request="https://github.com/org/repo/pull/1")


def test_update_issue_custom_fields_discovery_error(mock_env, monkeypatch, temp_daf_home):
    """Test custom field update with discovery error."""
    mock_client = MagicMock()
    mock_client.update_issue = MagicMock()

    mock_mapper = MagicMock()
    mock_mapper.discover_editable_fields = MagicMock(side_effect=Exception("Discovery failed"))
    mock_mapper.get_field_id = MagicMock(return_value="customfield_123")

    with patch("devflow.cli.commands.jira_update_command.JiraClient", return_value=mock_client):
        with patch("devflow.cli.commands.jira_update_command.JiraFieldMapper", return_value=mock_mapper):
            with patch("devflow.cli.commands.jira_update_command.ConfigLoader") as mock_config_loader:
                mock_config = MagicMock()
                mock_config.jira.field_mappings = {"test_field": {"id": "customfield_123", "type": "string", "schema": "string"}}
                mock_config_loader.return_value.load_config.return_value = mock_config

                # Should fall back to creation field mappings and still complete
                update_jira_issue("TEST-123", summary="Test", custom_field_test_field="value")


def test_update_issue_custom_field_unknown(mock_env, monkeypatch, temp_daf_home):
    """Test update with unknown custom field."""
    mock_client = MagicMock()
    mock_client.update_issue = MagicMock()

    mock_mapper = MagicMock()
    mock_mapper.discover_editable_fields = MagicMock(return_value={"known_field": {"id": "customfield_123"}})
    mock_mapper.get_field_id = MagicMock(return_value=None)

    with patch("devflow.cli.commands.jira_update_command.JiraClient", return_value=mock_client):
        with patch("devflow.cli.commands.jira_update_command.JiraFieldMapper", return_value=mock_mapper):
            with patch("devflow.cli.commands.jira_update_command.ConfigLoader"):
                # Should print warning about unknown field and exit (no fields to update)
                with pytest.raises(SystemExit) as exc_info:
                    update_jira_issue("TEST-123", custom_field_unknown="value")
                assert exc_info.value.code == 1


def test_update_issue_custom_field_none_value(mock_env, monkeypatch, temp_daf_home):
    """Test update with None custom field value."""
    mock_client = MagicMock()
    mock_client.update_issue = MagicMock()

    mock_mapper = MagicMock()
    mock_mapper.discover_editable_fields = MagicMock(return_value={})
    mock_mapper.get_field_id = MagicMock(return_value=None)

    with patch("devflow.cli.commands.jira_update_command.JiraClient", return_value=mock_client):
        with patch("devflow.cli.commands.jira_update_command.JiraFieldMapper", return_value=mock_mapper):
            with patch("devflow.cli.commands.jira_update_command.ConfigLoader"):
                # Should skip None values and exit (no fields to update)
                with pytest.raises(SystemExit) as exc_info:
                    update_jira_issue("TEST-123", custom_field_test=None)
                assert exc_info.value.code == 1


def test_build_field_value_multiurl_schema():
    """Test build_field_value with multiurl schema."""
    field_info = {"type": "string", "schema": "multiurl"}
    result = build_field_value(field_info, "https://example.com", MagicMock())
    assert result == "https://example.com"


def test_build_field_value_url_in_schema():
    """Test build_field_value with URL in schema name."""
    field_info = {"type": "string", "schema": "array<url>"}
    result = build_field_value(field_info, "https://example.com", MagicMock())
    assert result == "https://example.com"


def test_build_field_value_option_schema():
    """Test build_field_value with option schema."""
    field_info = {"type": "string", "schema": "option"}
    result = build_field_value(field_info, "High", MagicMock())
    assert result == {"value": "High"}


def test_build_field_value_select_schema():
    """Test build_field_value with select schema."""
    field_info = {"type": "string", "schema": "com.atlassian.jira.plugin.system.customfieldtypes:select"}
    result = build_field_value(field_info, "Value", MagicMock())
    assert result == {"value": "Value"}


def test_build_field_value_array_with_option():
    """Test build_field_value with array of options."""
    field_info = {"type": "array", "schema": "array<option>"}
    result = build_field_value(field_info, "Value", MagicMock())
    assert result == [{"value": "Value"}]


def test_build_field_value_array_of_strings():
    """Test build_field_value with array of strings."""
    field_info = {"type": "array", "schema": "array<string>"}
    result = build_field_value(field_info, "Value", MagicMock())
    assert result == ["Value"]


def test_build_field_value_priority_schema():
    """Test build_field_value with priority schema."""
    field_info = {"type": "priority", "schema": "priority"}
    result = build_field_value(field_info, "High", MagicMock())
    assert result == {"name": "High"}


def test_build_field_value_user_schema():
    """Test build_field_value with user schema."""
    field_info = {"type": "user", "schema": "user"}
    result = build_field_value(field_info, "jdoe", MagicMock())
    assert result == {"name": "jdoe"}


def test_build_field_value_user_none():
    """Test build_field_value with user=none to clear field."""
    field_info = {"type": "user", "schema": "user"}
    result = build_field_value(field_info, "none", MagicMock())
    assert result is None


def test_build_field_value_default_string():
    """Test build_field_value defaults to string."""
    field_info = {"type": "string", "schema": "string"}
    result = build_field_value(field_info, "Some text", MagicMock())
    assert result == "Some text"
