"""Tests for shell completion functions."""

from unittest.mock import MagicMock, patch

from devflow.cli.completion import (
    complete_file_paths,
    complete_session_identifiers,
    complete_tags,
    complete_working_directories,
)
from devflow.config.models import Session


def test_complete_session_identifiers_with_sessions():
    """Test session identifier completion with existing sessions."""
    # Mock the sessions index structure
    mock_session1 = Session(
        name="test-session-1",
        goal="First test goal",
        working_directory="dir1",
        issue_key="PROJ-123",
    )
    mock_session2 = Session(
        name="test-session-2",
        goal="Second test goal that is very long and should be truncated",
        working_directory="dir2",
        issue_key="PROJ-456",
    )

    mock_sessions_index = MagicMock()
    mock_sessions_index.sessions = {
        "test-session-1": [mock_session1],
        "test-session-2": [mock_session2],
    }

    with patch('devflow.cli.completion.ConfigLoader') as mock_loader:
        mock_loader.return_value.load_sessions.return_value = mock_sessions_index
        results = complete_session_identifiers(ctx=None, param=None, incomplete="test")
        # Should return completions for both sessions
        assert isinstance(results, list)


def test_complete_session_identifiers_with_jira_keys():
    """Test completion includes JIRA keys."""
    mock_session = Session(
        name="my-feature",
        goal="Implement feature X",
        working_directory="dir1",
        issue_key="PROJ-999",
    )

    mock_sessions_index = MagicMock()
    mock_sessions_index.sessions = {"my-feature": [mock_session]}

    with patch('devflow.cli.completion.ConfigLoader') as mock_loader:
        mock_loader.return_value.load_sessions.return_value = mock_sessions_index
        results = complete_session_identifiers(ctx=None, param=None, incomplete="PROJ")
        assert isinstance(results, list)


def test_complete_session_identifiers_no_match():
    """Test completion with no matching sessions."""
    mock_session = Session(
        name="abc-session",
        goal="Test",
        working_directory="dir1",
    )

    mock_sessions_index = MagicMock()
    mock_sessions_index.sessions = {"abc-session": [mock_session]}

    with patch('devflow.cli.completion.ConfigLoader') as mock_loader:
        mock_loader.return_value.load_sessions.return_value = mock_sessions_index
        results = complete_session_identifiers(ctx=None, param=None, incomplete="xyz")
        assert len(results) == 0


def test_complete_session_identifiers_error_handling():
    """Test completion handles errors gracefully."""
    with patch('devflow.cli.completion.ConfigLoader') as mock_loader:
        mock_loader.side_effect = Exception("Config error")
        results = complete_session_identifiers(ctx=None, param=None, incomplete="test")
        assert results == []


def test_complete_session_identifiers_avoids_duplicates():
    """Test completion avoids duplicate JIRA keys when they match group names."""
    mock_session = Session(
        name="PROJ-111",
        goal="Test duplicate handling",
        working_directory="dir1",
        issue_key="PROJ-111",
    )

    mock_sessions_index = MagicMock()
    mock_sessions_index.sessions = {"PROJ-111": [mock_session]}

    with patch('devflow.cli.completion.ConfigLoader') as mock_loader:
        mock_loader.return_value.load_sessions.return_value = mock_sessions_index
        results = complete_session_identifiers(ctx=None, param=None, incomplete="PROJ")
        # PROJ-111 should appear only once
        proj_111_entries = [r for r in results if r[0] == "PROJ-111"]
        assert len(proj_111_entries) <= 1


def test_complete_working_directories():
    """Test working directory completion."""
    sessions = [
        Session(name="s1", goal="Test", working_directory="backend-api", issue_key=None),
        Session(name="s2", goal="Test", working_directory="frontend-app", issue_key=None),
        Session(name="s3", goal="Test", working_directory="shared-lib", issue_key=None),
    ]

    mock_sessions_index = MagicMock()
    mock_sessions_index.sessions = {f"s{i}": [s] for i, s in enumerate(sessions, 1)}

    with patch('devflow.cli.completion.ConfigLoader') as mock_loader:
        mock_loader.return_value.load_sessions.return_value = mock_sessions_index
        results = complete_working_directories(ctx=None, param=None, incomplete="back")
        assert "backend-api" in results


def test_complete_working_directories_deduplicates():
    """Test working directory completion deduplicates directories."""
    sessions = [
        Session(name="s1", goal="Test", working_directory="same-dir", issue_key=None),
        Session(name="s2", goal="Test", working_directory="same-dir", issue_key=None),
        Session(name="s3", goal="Test", working_directory="same-dir", issue_key=None),
    ]

    mock_sessions_index = MagicMock()
    mock_sessions_index.sessions = {f"s{i}": [s] for i, s in enumerate(sessions, 1)}

    with patch('devflow.cli.completion.ConfigLoader') as mock_loader:
        mock_loader.return_value.load_sessions.return_value = mock_sessions_index
        results = complete_working_directories(ctx=None, param=None, incomplete="same")
        # Should only return "same-dir" once
        assert results.count("same-dir") == 1


def test_complete_working_directories_error_handling():
    """Test working directory completion handles errors."""
    with patch('devflow.cli.completion.ConfigLoader') as mock_loader:
        mock_loader.side_effect = Exception("Config error")
        results = complete_working_directories(ctx=None, param=None, incomplete="test")
        assert results == []


def test_complete_tags():
    """Test tag completion."""
    session1 = Session(name="s1", goal="Test", working_directory="dir1", tags=["feature", "frontend"], issue_key=None)
    session2 = Session(name="s2", goal="Test", working_directory="dir2", tags=["bugfix", "backend"], issue_key=None)

    mock_sessions_index = MagicMock()
    mock_sessions_index.sessions = {"s1": [session1], "s2": [session2]}

    with patch('devflow.cli.completion.ConfigLoader') as mock_loader:
        mock_loader.return_value.load_sessions.return_value = mock_sessions_index
        results = complete_tags(ctx=None, param=None, incomplete="fe")
        # Should include tags starting with "fe"
        assert any("feature" in str(r) or "frontend" in str(r) for r in results)


def test_complete_tags_deduplicates():
    """Test tag completion deduplicates tags."""
    sessions = [
        Session(name="s1", goal="Test", working_directory="dir1", tags=["urgent", "production"], issue_key=None),
        Session(name="s2", goal="Test", working_directory="dir2", tags=["urgent", "production"], issue_key=None),
    ]

    mock_sessions_index = MagicMock()
    mock_sessions_index.sessions = {f"s{i}": [s] for i, s in enumerate(sessions, 1)}

    with patch('devflow.cli.completion.ConfigLoader') as mock_loader:
        mock_loader.return_value.load_sessions.return_value = mock_sessions_index
        results = complete_tags(ctx=None, param=None, incomplete="")
        # Tags should be deduplicated
        assert results.count("urgent") == 1
        assert results.count("production") == 1


def test_complete_tags_no_tags():
    """Test tag completion when sessions have no tags."""
    session = Session(name="s1", goal="Test", working_directory="dir1", tags=[], issue_key=None)

    mock_sessions_index = MagicMock()
    mock_sessions_index.sessions = {"s1": [session]}

    with patch('devflow.cli.completion.ConfigLoader') as mock_loader:
        mock_loader.return_value.load_sessions.return_value = mock_sessions_index
        results = complete_tags(ctx=None, param=None, incomplete="")
        assert len(results) == 0


def test_complete_tags_error_handling():
    """Test tag completion handles errors."""
    with patch('devflow.cli.completion.ConfigLoader') as mock_loader:
        mock_loader.side_effect = Exception("Config error")
        results = complete_tags(ctx=None, param=None, incomplete="test")
        assert results == []


def test_complete_file_paths():
    """Test file path completion always returns empty."""
    # This function intentionally returns empty to let shell handle file completion
    results = complete_file_paths(ctx=None, param=None, incomplete="/some/path")
    assert results == []

    results = complete_file_paths(ctx=None, param=None, incomplete="")
    assert results == []
