"""Tests for CLI utility functions."""

import os
from io import StringIO
from pathlib import Path
from unittest.mock import patch, Mock

import click
import pytest
import requests

from devflow.cli.utils import (
    get_active_conversation,
    get_session_with_prompt,
    display_session_header,
    add_jira_comment,
    get_status_display,
    resolve_goal_input,
    require_outside_claude,
    _read_goal_from_file,
    _fetch_goal_from_url,
)
from devflow.config.loader import ConfigLoader
from devflow.jira.exceptions import JiraApiError
from devflow.session.manager import SessionManager


def test_get_session_with_prompt_with_valid_session_id(temp_daf_home):
    """Test get_session_with_prompt with session_id parameter (deprecated but still accepted)."""
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    # Create a session
    session = session_manager.create_session(
        name="test-session",
        goal="Test goal",
        working_directory="test-dir",
        project_path="/path/to/project",
        ai_agent_session_id="test-uuid-123",
    )

    # Get session with session_id parameter (deprecated but should still work)
    # session_id is ignored since session groups no longer exist
    result = get_session_with_prompt(
        session_manager,
        "test-session",
        session_id=1  # Ignored parameter
    )

    assert result is not None
    assert result.goal == "Test goal"


def test_get_session_with_prompt_with_invalid_session_id(temp_daf_home):
    """Test get_session_with_prompt returns session even when session_id not provided.

    Since session groups are removed, session_id parameter is deprecated.
    Sessions are looked up by name only.
    """
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    # Create a session
    session_manager.create_session(
        name="test-session",
        goal="Test goal",
        working_directory="test-dir",
        project_path="/path/to/project",
        ai_agent_session_id="test-uuid-123",
    )

    # Get session by name (session_id parameter is ignored)
    result = get_session_with_prompt(
        session_manager,
        "test-session"
    )

    # Should return the session since it exists
    assert result is not None
    assert result.goal == "Test goal"


def test_get_session_with_prompt_error_if_not_found_false(temp_daf_home):
    """Test get_session_with_prompt with error_if_not_found=False."""
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    # Try to get non-existent session with error_if_not_found=False
    result = get_session_with_prompt(
        session_manager,
        "non-existent",
        error_if_not_found=False
    )

    assert result is None


def test_display_session_header_with_branch(temp_daf_home):
    """Test display_session_header displays branch when present."""
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    session = session_manager.create_session(
        name="test-session",
        goal="Test goal",
        working_directory="test-dir",
        project_path="/path/to/project",
        ai_agent_session_id="test-uuid-123",
        branch="feature/test-branch"
    )

    # Just ensure it doesn't raise an exception
    display_session_header(session)


def test_add_jira_comment_file_not_found(temp_daf_home):
    """Test add_jira_comment when JIRA CLI is not found."""
    with patch('devflow.jira.client.JiraClient.add_comment') as mock_add:
        mock_add.side_effect = FileNotFoundError("jira command not found")

        result = add_jira_comment("PROJ-12345", "Test comment")

        assert result is False


def test_add_jira_comment_general_exception(temp_daf_home):
    """Test add_jira_comment when general exception occurs."""
    with patch('devflow.jira.client.JiraClient.add_comment') as mock_add:
        mock_add.side_effect = JiraApiError("Something went wrong", status_code=500)

        result = add_jira_comment("PROJ-12345", "Test comment")

        assert result is False


def test_get_status_display_in_progress():
    """Test get_status_display for in_progress status."""
    text, color = get_status_display("in_progress")
    assert text == "in_progress"
    assert color == "yellow"


def test_get_status_display_paused():
    """Test get_status_display for paused status."""
    text, color = get_status_display("paused")
    assert text == "paused"
    assert color == "blue"


def test_get_status_display_complete():
    """Test get_status_display for complete status."""
    text, color = get_status_display("complete")
    assert text == "complete"
    assert color == "green"


def test_get_status_display_created():
    """Test get_status_display for created status."""
    text, color = get_status_display("created")
    assert text == "created"
    assert color == "cyan"


def test_get_status_display_unknown():
    """Test get_status_display for unknown status."""
    text, color = get_status_display("unknown_status")
    assert text == "unknown_status"
    assert color == "white"


def test_get_active_conversation_no_env_var(temp_daf_home):
    """Test get_active_conversation when AI_AGENT_SESSION_ID is not set."""
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    # Ensure AI_AGENT_SESSION_ID is not set
    if "AI_AGENT_SESSION_ID" in os.environ:
        del os.environ["AI_AGENT_SESSION_ID"]

    result = get_active_conversation(session_manager)
    assert result is None


def test_get_active_conversation_with_matching_session(temp_daf_home):
    """Test get_active_conversation when a matching session exists."""
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    # Create a session with a conversation
    session = session_manager.create_session(
        name="test-session",
        goal="Test goal",
        working_directory="test-repo",
        project_path="/path/to/test-repo",
        ai_agent_session_id="test-claude-session-123",
    )

    # Set AI_AGENT_SESSION_ID environment variable
    os.environ["AI_AGENT_SESSION_ID"] = "test-claude-session-123"

    try:
        result = get_active_conversation(session_manager)

        assert result is not None
        active_session, active_conversation, working_dir = result
        assert active_session.name == "test-session"
        assert active_conversation.ai_agent_session_id == "test-claude-session-123"
        assert working_dir == "test-repo"
    finally:
        # Clean up
        if "AI_AGENT_SESSION_ID" in os.environ:
            del os.environ["AI_AGENT_SESSION_ID"]


def test_get_active_conversation_with_non_matching_session(temp_daf_home):
    """Test get_active_conversation when no matching session exists."""
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    # Create a session with a different ai_agent_session_id
    session_manager.create_session(
        name="test-session",
        goal="Test goal",
        working_directory="test-repo",
        project_path="/path/to/test-repo",
        ai_agent_session_id="different-session-id",
    )

    # Set AI_AGENT_SESSION_ID to a non-matching ID
    os.environ["AI_AGENT_SESSION_ID"] = "non-existent-session-id"

    try:
        result = get_active_conversation(session_manager)
        assert result is None
    finally:
        # Clean up
        if "AI_AGENT_SESSION_ID" in os.environ:
            del os.environ["AI_AGENT_SESSION_ID"]


def test_get_active_conversation_with_multiple_conversations(temp_daf_home):
    """Test get_active_conversation with session containing multiple conversations."""
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    # Create a session
    session = session_manager.create_session(
        name="multi-session",
        goal="Test multi-conversation",
        working_directory="repo1",
        project_path="/path/to/repo1",
        ai_agent_session_id="session-1",
    )

    # Add a second conversation
    session.add_conversation(
        working_dir="repo2",
        ai_agent_session_id="session-2",
        project_path="/path/to/repo2",
        branch="feature-2",
        workspace=None,
    )
    session_manager.update_session(session)

    # Set AI_AGENT_SESSION_ID to the second conversation
    os.environ["AI_AGENT_SESSION_ID"] = "session-2"

    try:
        result = get_active_conversation(session_manager)

        assert result is not None
        active_session, active_conversation, working_dir = result
        assert active_session.name == "multi-session"
        assert active_conversation.ai_agent_session_id == "session-2"
        assert working_dir == "repo2"
    finally:
        # Clean up
        if "AI_AGENT_SESSION_ID" in os.environ:
            del os.environ["AI_AGENT_SESSION_ID"]


def test_prevent_duplicate_conversation_for_same_directory(temp_daf_home):
    """Test that add_conversation prevents creating duplicate conversations for same directory."""
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    # Create a session with a conversation
    session = session_manager.create_session(
        name="test-session",
        goal="Test duplicate prevention",
        working_directory="repo1",
        project_path="/path/to/repo1",
        ai_agent_session_id="session-1",
    )

    # Try to add another conversation with the same working_dir
    with pytest.raises(ValueError) as exc_info:
        session.add_conversation(
            working_dir="repo1",  # Same working_dir
            ai_agent_session_id="session-2",
            project_path="/path/to/repo1",
            branch="feature-2",
            workspace=None,
        )

    assert "already exists" in str(exc_info.value).lower()
    assert "repo1" in str(exc_info.value)

    # Verify only the original conversation exists 
    assert len(session.conversations) == 1
    assert session.conversations["repo1"].active_session.ai_agent_session_id == "session-1"


# Tests for resolve_goal_input function

def test_resolve_goal_input_plain_text():
    """Test resolve_goal_input with plain text returns text as-is."""
    goal = "This is a simple plain text goal"
    result = resolve_goal_input(goal)
    assert result == goal


def test_resolve_goal_input_empty_string():
    """Test resolve_goal_input with empty string."""
    result = resolve_goal_input("")
    assert result == ""


def test_resolve_goal_input_none():
    """Test resolve_goal_input with None."""
    result = resolve_goal_input(None)
    assert result is None


def test_resolve_goal_input_file_path(tmp_path):
    """Test resolve_goal_input with file:// prefix reads file content."""
    # Create a test file
    test_file = tmp_path / "requirements.md"
    test_content = "# Requirements\n\nThis is the goal from a file."
    test_file.write_text(test_content, encoding="utf-8")

    # Test with file:// prefix
    goal = f"file://{test_file}"
    result = resolve_goal_input(goal)
    assert result == test_content


def test_resolve_goal_input_file_path_with_tilde(tmp_path, monkeypatch):
    """Test resolve_goal_input with file:// prefix and ~ expansion."""
    # Create a test file
    test_file = tmp_path / "test.txt"
    test_content = "Goal from home directory file"
    test_file.write_text(test_content, encoding="utf-8")

    # Mock Path.expanduser to return our test path
    original_expanduser = Path.expanduser

    def mock_expanduser(self):
        if str(self).startswith("~/"):
            return test_file
        return original_expanduser(self)

    monkeypatch.setattr(Path, "expanduser", mock_expanduser)

    # Test with ~ in path
    goal = "file://~/test.txt"
    result = resolve_goal_input(goal)
    assert result == test_content


def test_resolve_goal_input_bare_file_path(tmp_path):
    """Test resolve_goal_input with bare file path (no file:// prefix)."""
    # Create a test file
    test_file = tmp_path / "requirements.md"
    test_content = "# Requirements\n\nBare file path test"
    test_file.write_text(test_content, encoding="utf-8")

    # Test with bare absolute path
    goal = str(test_file)
    result = resolve_goal_input(goal)
    assert result == test_content


def test_resolve_goal_input_bare_file_path_with_tilde(tmp_path, monkeypatch):
    """Test resolve_goal_input with bare file path using ~ expansion."""
    # Create a test file
    test_file = tmp_path / "spec.txt"
    test_content = "Specification from home directory"
    test_file.write_text(test_content, encoding="utf-8")

    # Mock Path.expanduser to return our test path
    original_expanduser = Path.expanduser

    def mock_expanduser(self):
        if str(self).startswith("~/"):
            return test_file
        return original_expanduser(self)

    monkeypatch.setattr(Path, "expanduser", mock_expanduser)

    # Test with bare ~ path
    goal = "~/spec.txt"
    result = resolve_goal_input(goal)
    assert result == test_content


def test_resolve_goal_input_bare_relative_path(tmp_path, monkeypatch):
    """Test resolve_goal_input with bare relative file path."""
    # Create a test file
    test_file = tmp_path / "local.md"
    test_content = "Local file content"
    test_file.write_text(test_content, encoding="utf-8")

    # Change to the temp directory
    monkeypatch.chdir(tmp_path)

    # Test with relative path
    goal = "local.md"
    result = resolve_goal_input(goal)
    assert result == test_content


def test_resolve_goal_input_bare_path_not_found():
    """Test resolve_goal_input raises error for non-existent bare file path."""
    # Path that looks like a file but doesn't exist
    goal = "/nonexistent/path/requirements.md"

    with pytest.raises(click.ClickException) as exc_info:
        resolve_goal_input(goal)

    assert "File not found" in str(exc_info.value)


def test_resolve_goal_input_bare_path_is_directory(tmp_path):
    """Test resolve_goal_input raises error when bare path is a directory."""
    # Create a directory
    test_dir = tmp_path / "testdir"
    test_dir.mkdir()

    with pytest.raises(click.ClickException) as exc_info:
        resolve_goal_input(str(test_dir))

    assert "directory, not a file" in str(exc_info.value)


def test_resolve_goal_input_plain_text_not_confused_with_path():
    """Test that plain text without path indicators is not confused with file path."""
    # Plain text that doesn't look like a path
    goal = "Add retry logic to subscription API"
    result = resolve_goal_input(goal)
    assert result == goal


def test_resolve_goal_input_multi_word_with_path_chars():
    """Test that multi-word text is always treated as plain text, even with path-like characters."""
    # Multi-word text containing characters that might look path-like
    goal = "Get this error 'Usage: daf [OPTIONS] Try 'daf --help' for help. Error: Got unexpected extra argument (PROJ-60640)' when running daf export PROJ-60640 --output ~/Downloads/PROJ-60640.tar.gz"
    result = resolve_goal_input(goal)
    # Should return the text as-is, not try to parse as a path
    assert result == goal


def test_resolve_goal_input_extension_triggers_file_check():
    """Test that text ending with file extension triggers file existence check."""
    # Text ending with .md but file doesn't exist
    goal = "requirements.md"

    with pytest.raises(click.ClickException) as exc_info:
        resolve_goal_input(goal)

    assert "File not found" in str(exc_info.value)


def test_resolve_goal_input_http_url(monkeypatch):
    """Test resolve_goal_input with http:// URL fetches content."""
    url = "http://example.com/requirements.txt"
    expected_content = "Requirements from HTTP URL"

    # Mock the requests.get function
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.text = expected_content

    def mock_get(*args, **kwargs):
        return mock_response

    monkeypatch.setattr(requests, "get", mock_get)

    result = resolve_goal_input(url)
    assert result == expected_content


def test_resolve_goal_input_https_url(monkeypatch):
    """Test resolve_goal_input with https:// URL fetches content."""
    url = "https://secure.example.com/spec.md"
    expected_content = "# Specification\n\nSecure content"

    # Mock the requests.get function
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.text = expected_content

    def mock_get(*args, **kwargs):
        return mock_response

    monkeypatch.setattr(requests, "get", mock_get)

    result = resolve_goal_input(url)
    assert result == expected_content


def test_read_goal_from_file_not_found():
    """Test _read_goal_from_file raises exception when file doesn't exist."""
    with pytest.raises(click.ClickException) as exc_info:
        _read_goal_from_file("/nonexistent/path/to/file.txt")

    assert "File not found" in str(exc_info.value)


def test_read_goal_from_file_is_directory(tmp_path):
    """Test _read_goal_from_file raises exception when path is a directory."""
    # Create a directory
    test_dir = tmp_path / "testdir"
    test_dir.mkdir()

    with pytest.raises(click.ClickException) as exc_info:
        _read_goal_from_file(str(test_dir))

    assert "not a file" in str(exc_info.value)


def test_read_goal_from_file_utf8(tmp_path):
    """Test _read_goal_from_file reads UTF-8 content correctly."""
    test_file = tmp_path / "utf8.txt"
    test_content = "UTF-8 content with émojis 🎉 and spëcial chars"
    test_file.write_text(test_content, encoding="utf-8")

    result = _read_goal_from_file(str(test_file))
    assert result == test_content


def test_read_goal_from_file_non_utf8_with_replacement(tmp_path):
    """Test _read_goal_from_file handles non-UTF-8 files with replacement."""
    test_file = tmp_path / "latin1.txt"
    # Write with latin-1 encoding
    test_file.write_bytes(b"Content with \xe9 special char")

    # Should not raise, but replace invalid UTF-8
    result = _read_goal_from_file(str(test_file))
    assert "Content with" in result


def test_fetch_goal_from_url_success(monkeypatch):
    """Test _fetch_goal_from_url successful fetch."""
    url = "https://example.com/goal.txt"
    expected_content = "Goal content from URL"

    # Mock the requests.get function
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.text = expected_content

    def mock_get(*args, **kwargs):
        return mock_response

    monkeypatch.setattr(requests, "get", mock_get)

    result = _fetch_goal_from_url(url)
    assert result == expected_content


def test_fetch_goal_from_url_404_error(monkeypatch):
    """Test _fetch_goal_from_url raises exception on 404."""
    url = "https://example.com/notfound.txt"

    # Mock the requests.get function to return 404
    mock_response = Mock()
    mock_response.status_code = 404
    mock_response.reason = "Not Found"

    def mock_get(*args, **kwargs):
        return mock_response

    monkeypatch.setattr(requests, "get", mock_get)

    with pytest.raises(click.ClickException) as exc_info:
        _fetch_goal_from_url(url)

    assert "HTTP 404" in str(exc_info.value)


def test_fetch_goal_from_url_500_error(monkeypatch):
    """Test _fetch_goal_from_url raises exception on 500."""
    url = "https://example.com/error.txt"

    # Mock the requests.get function to return 500
    mock_response = Mock()
    mock_response.status_code = 500
    mock_response.reason = "Internal Server Error"

    def mock_get(*args, **kwargs):
        return mock_response

    monkeypatch.setattr(requests, "get", mock_get)

    with pytest.raises(click.ClickException) as exc_info:
        _fetch_goal_from_url(url)

    assert "HTTP 500" in str(exc_info.value)


def test_fetch_goal_from_url_timeout(monkeypatch):
    """Test _fetch_goal_from_url raises exception on timeout."""
    url = "https://example.com/slow.txt"

    # Mock requests.get to raise Timeout exception
    def mock_get(*args, **kwargs):
        raise requests.exceptions.Timeout("Connection timed out")

    monkeypatch.setattr(requests, "get", mock_get)

    with pytest.raises(click.ClickException) as exc_info:
        _fetch_goal_from_url(url)

    assert "Timeout" in str(exc_info.value)


def test_fetch_goal_from_url_connection_error(monkeypatch):
    """Test _fetch_goal_from_url raises exception on connection error."""
    url = "https://example.com/unreachable.txt"

    # Mock requests.get to raise ConnectionError exception
    def mock_get(*args, **kwargs):
        raise requests.exceptions.ConnectionError("Connection failed")

    monkeypatch.setattr(requests, "get", mock_get)

    with pytest.raises(click.ClickException) as exc_info:
        _fetch_goal_from_url(url)

    assert "Failed to fetch URL" in str(exc_info.value)


def test_require_outside_claude_decorator_allows_when_not_in_claude(monkeypatch):
    """Test require_outside_claude decorator allows execution when AI_AGENT_SESSION_ID is not set."""
    # Ensure AI_AGENT_SESSION_ID is not set
    monkeypatch.delenv("AI_AGENT_SESSION_ID", raising=False)

    # Create a test function with the decorator
    @require_outside_claude
    def test_function():
        return "success"

    # Should execute without error
    result = test_function()
    assert result == "success"


def test_require_outside_claude_decorator_blocks_when_in_claude(monkeypatch):
    """Test require_outside_claude decorator blocks execution when DEVFLOW_IN_SESSION is set."""
    # Set DEVFLOW_IN_SESSION to simulate running inside an AI agent session
    monkeypatch.setenv("DEVFLOW_IN_SESSION", "1")

    # Create a test function with the decorator
    @require_outside_claude
    def test_function():
        return "should not reach here"

    # Should exit with code 1
    with pytest.raises(SystemExit) as exc_info:
        test_function()

    assert exc_info.value.code == 1


def test_require_outside_claude_decorator_with_arguments(monkeypatch):
    """Test require_outside_claude decorator works with function arguments."""
    # Ensure AI_AGENT_SESSION_ID is not set
    monkeypatch.delenv("AI_AGENT_SESSION_ID", raising=False)

    # Create a test function with arguments
    @require_outside_claude
    def test_function(a, b, c=None):
        return (a, b, c)

    # Should execute without error and preserve arguments
    result = test_function(1, 2, c=3)
    assert result == (1, 2, 3)


def test_require_outside_claude_decorator_preserves_function_metadata():
    """Test require_outside_claude decorator preserves function metadata via functools.wraps."""
    @require_outside_claude
    def test_function():
        """Test function docstring."""
        pass

    # Check that function metadata is preserved
    assert test_function.__name__ == "test_function"
    assert test_function.__doc__ == "Test function docstring."


def test_require_outside_claude_decorator_with_empty_session_id(monkeypatch):
    """Test require_outside_claude decorator allows execution when AI_AGENT_SESSION_ID is empty string."""
    # Set AI_AGENT_SESSION_ID to empty string (should be treated as not set)
    monkeypatch.setenv("AI_AGENT_SESSION_ID", "")

    # Create a test function with the decorator
    @require_outside_claude
    def test_function():
        return "success"

    # Empty string is falsy, so should allow execution
    result = test_function()
    assert result == "success"
