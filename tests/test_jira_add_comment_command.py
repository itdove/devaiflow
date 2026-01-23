"""Tests for daf jira add-comment command."""

import pytest
from unittest.mock import patch, MagicMock, mock_open
from devflow.cli.commands.jira_add_comment_command import add_comment
from devflow.jira.exceptions import (
    JiraNotFoundError,
    JiraAuthError,
    JiraApiError,
    JiraConnectionError,
)


def test_add_comment_with_text_argument(monkeypatch):
    """Test adding a comment with text as argument."""
    mock_client = MagicMock()

    with patch('devflow.cli.commands.jira_add_comment_command.JiraClient', return_value=mock_client):
        add_comment("PROJ-12345", comment="Test comment", output_json=False)

    # Verify add_comment was called with correct parameters
    mock_client.add_comment.assert_called_once_with("PROJ-12345", "Test comment", public=False)


def test_add_comment_with_file(monkeypatch):
    """Test adding a comment from a file."""
    mock_client = MagicMock()
    file_content = "Comment from file\nwith multiple lines"

    with patch('devflow.cli.commands.jira_add_comment_command.JiraClient', return_value=mock_client):
        with patch('builtins.open', mock_open(read_data=file_content)):
            add_comment("PROJ-12345", file_path="/path/to/comment.txt", output_json=False)

    # Verify add_comment was called with file content
    mock_client.add_comment.assert_called_once_with("PROJ-12345", file_content, public=False)


def test_add_comment_with_stdin(monkeypatch):
    """Test adding a comment from stdin."""
    mock_client = MagicMock()
    stdin_content = "Comment from stdin"

    with patch('devflow.cli.commands.jira_add_comment_command.JiraClient', return_value=mock_client):
        with patch('sys.stdin.read', return_value=stdin_content):
            add_comment("PROJ-12345", stdin=True, output_json=False)

    # Verify add_comment was called with stdin content
    mock_client.add_comment.assert_called_once_with("PROJ-12345", stdin_content, public=False)


def test_add_comment_missing_text():
    """Test error when no comment text is provided."""
    with pytest.raises(SystemExit) as exc_info:
        add_comment("PROJ-12345", output_json=False)

    assert exc_info.value.code == 1


def test_add_comment_empty_text():
    """Test error when comment text is empty."""
    with pytest.raises(SystemExit) as exc_info:
        add_comment("PROJ-12345", comment="   ", output_json=False)

    assert exc_info.value.code == 1


def test_add_comment_file_not_found():
    """Test error when file does not exist."""
    with patch('builtins.open', side_effect=FileNotFoundError):
        with pytest.raises(SystemExit) as exc_info:
            add_comment("PROJ-12345", file_path="/nonexistent/file.txt", output_json=False)

        assert exc_info.value.code == 1


def test_add_comment_public_flag(monkeypatch):
    """Test adding a public comment (requires confirmation)."""
    mock_client = MagicMock()

    # Mock the Confirm.ask to return True
    with patch('devflow.cli.commands.jira_add_comment_command.JiraClient', return_value=mock_client):
        with patch('devflow.cli.commands.jira_add_comment_command.Confirm.ask', return_value=True):
            add_comment("PROJ-12345", comment="Public comment", public=True, output_json=False)

    # Verify add_comment was called with public=True
    mock_client.add_comment.assert_called_once_with("PROJ-12345", "Public comment", public=True)


def test_add_comment_public_flag_cancelled(monkeypatch):
    """Test cancelling public comment."""
    mock_client = MagicMock()

    with patch('devflow.cli.commands.jira_add_comment_command.JiraClient', return_value=mock_client):
        with patch('devflow.cli.commands.jira_add_comment_command.Confirm.ask', return_value=False):
            add_comment("PROJ-12345", comment="Public comment", public=True, output_json=False)

    # Verify add_comment was NOT called since user cancelled
    mock_client.add_comment.assert_not_called()


def test_add_comment_not_found_error():
    """Test handling of JiraNotFoundError."""
    mock_client = MagicMock()
    mock_client.add_comment.side_effect = JiraNotFoundError(
        "Issue not found",
        resource_type="issue",
        resource_id="PROJ-99999"
    )

    with patch('devflow.cli.commands.jira_add_comment_command.JiraClient', return_value=mock_client):
        with pytest.raises(SystemExit) as exc_info:
            add_comment("PROJ-99999", comment="Test", output_json=False)

        assert exc_info.value.code == 1


def test_add_comment_auth_error():
    """Test handling of JiraAuthError."""
    mock_client = MagicMock()
    mock_client.add_comment.side_effect = JiraAuthError(
        "Authentication failed",
        status_code=401
    )

    with patch('devflow.cli.commands.jira_add_comment_command.JiraClient', return_value=mock_client):
        with pytest.raises(SystemExit) as exc_info:
            add_comment("PROJ-12345", comment="Test", output_json=False)

        assert exc_info.value.code == 1


def test_add_comment_api_error():
    """Test handling of JiraApiError."""
    mock_client = MagicMock()
    mock_client.add_comment.side_effect = JiraApiError(
        "API error",
        status_code=500,
        response_text="Internal server error"
    )

    with patch('devflow.cli.commands.jira_add_comment_command.JiraClient', return_value=mock_client):
        with pytest.raises(SystemExit) as exc_info:
            add_comment("PROJ-12345", comment="Test", output_json=False)

        assert exc_info.value.code == 1


def test_add_comment_connection_error():
    """Test handling of JiraConnectionError."""
    mock_client = MagicMock()
    mock_client.add_comment.side_effect = JiraConnectionError("Connection failed")

    with patch('devflow.cli.commands.jira_add_comment_command.JiraClient', return_value=mock_client):
        with pytest.raises(SystemExit) as exc_info:
            add_comment("PROJ-12345", comment="Test", output_json=False)

        assert exc_info.value.code == 1


def test_add_comment_json_output_success():
    """Test JSON output on success."""
    mock_client = MagicMock()

    with patch('devflow.cli.commands.jira_add_comment_command.JiraClient', return_value=mock_client):
        with patch('devflow.cli.commands.jira_add_comment_command.json_output') as mock_json_output:
            add_comment("PROJ-12345", comment="Test comment", output_json=True)

            # Verify JSON output was called with success=True
            mock_json_output.assert_called_once()
            call_args = mock_json_output.call_args
            assert call_args[1]['success'] is True
            assert call_args[1]['data']['issue_key'] == "PROJ-12345"
            assert call_args[1]['data']['visibility'] == "Example Group"


def test_add_comment_json_output_error():
    """Test JSON output on error."""
    mock_client = MagicMock()
    mock_client.add_comment.side_effect = JiraNotFoundError(
        "Issue not found",
        resource_type="issue",
        resource_id="PROJ-99999"
    )

    with patch('devflow.cli.commands.jira_add_comment_command.JiraClient', return_value=mock_client):
        with patch('devflow.cli.commands.jira_add_comment_command.json_output') as mock_json_output:
            with pytest.raises(SystemExit):
                add_comment("PROJ-99999", comment="Test", output_json=True)

            # Verify JSON output was called with success=False
            mock_json_output.assert_called_once()
            call_args = mock_json_output.call_args
            assert call_args[1]['success'] is False
            assert 'error' in call_args[1]


def test_add_comment_strips_whitespace():
    """Test that comment text is stripped of leading/trailing whitespace."""
    mock_client = MagicMock()

    with patch('devflow.cli.commands.jira_add_comment_command.JiraClient', return_value=mock_client):
        add_comment("PROJ-12345", comment="  Test comment  \n", output_json=False)

    # Verify add_comment was called with stripped text
    mock_client.add_comment.assert_called_once_with("PROJ-12345", "Test comment", public=False)
