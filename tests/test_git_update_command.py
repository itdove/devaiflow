"""Tests for daf git update command."""

import json
import pytest
from unittest.mock import patch, Mock
from click.testing import CliRunner

from devflow.cli.main import cli
from devflow.issue_tracker.exceptions import (
    IssueTrackerNotFoundError,
    IssueTrackerAuthError,
    IssueTrackerApiError,
)


@pytest.fixture
def runner():
    """Provide a CliRunner instance."""
    return CliRunner()


@pytest.fixture
def mock_github_client():
    """Mock GitHubClient for testing."""
    # Patch GitRemoteDetector to return GitHub platform
    with patch('devflow.cli.commands.git_update_command.GitRemoteDetector') as mock_detector_class:
        mock_detector = Mock()
        mock_detector.parse_repository_info.return_value = ('github', 'owner', 'repo')
        mock_detector_class.return_value = mock_detector

        # Patch the factory to return a mock client
        with patch('devflow.cli.commands.git_update_command.create_issue_tracker_client') as mock_factory:
            mock_client = Mock()
            mock_client.repository = None
            mock_factory.return_value = mock_client
            yield mock_client


def test_git_update_title(runner, mock_github_client):
    """Test updating issue title."""
    result = runner.invoke(cli, [
        'git', 'update', '123',
        '--title', 'New Title'
    ])

    assert result.exit_code == 0
    mock_github_client.update_issue.assert_called_once()
    call_args = mock_github_client.update_issue.call_args[0]
    assert call_args[0] == '123'
    assert call_args[1]['title'] == 'New Title'


def test_git_update_description(runner, mock_github_client):
    """Test updating issue description."""
    result = runner.invoke(cli, [
        'git', 'update', '123',
        '--description', 'New description text'
    ])

    assert result.exit_code == 0
    call_args = mock_github_client.update_issue.call_args[0]
    assert call_args[1]['body'] == 'New description text'


def test_git_update_state_open(runner, mock_github_client):
    """Test reopening an issue."""
    result = runner.invoke(cli, [
        'git', 'update', '123',
        '--state', 'open'
    ])

    assert result.exit_code == 0
    call_args = mock_github_client.update_issue.call_args[0]
    assert call_args[1]['state'] == 'open'


def test_git_update_state_closed(runner, mock_github_client):
    """Test closing an issue."""
    result = runner.invoke(cli, [
        'git', 'update', '123',
        '--state', 'closed'
    ])

    assert result.exit_code == 0
    call_args = mock_github_client.update_issue.call_args[0]
    assert call_args[1]['state'] == 'closed'


def test_git_update_labels(runner, mock_github_client):
    """Test updating issue labels."""
    result = runner.invoke(cli, [
        'git', 'update', '123',
        '--labels', 'bug,priority: high,backend'
    ])

    assert result.exit_code == 0
    call_args = mock_github_client.update_issue.call_args[0]
    assert 'labels' in call_args[1]
    assert call_args[1]['labels'] == ['bug', 'priority: high', 'backend']


def test_git_update_assignee(runner, mock_github_client):
    """Test updating issue assignee."""
    result = runner.invoke(cli, [
        'git', 'update', '123',
        '--assignee', 'johndoe'
    ])

    assert result.exit_code == 0
    call_args = mock_github_client.update_issue.call_args[0]
    assert call_args[1]['assignees'] == ['johndoe']


def test_git_update_milestone(runner, mock_github_client):
    """Test updating issue milestone."""
    result = runner.invoke(cli, [
        'git', 'update', '123',
        '--milestone', 'v2.0'
    ])

    assert result.exit_code == 0
    call_args = mock_github_client.update_issue.call_args[0]
    assert call_args[1]['milestone'] == 'v2.0'


def test_git_update_multiple_fields(runner, mock_github_client):
    """Test updating multiple fields at once."""
    result = runner.invoke(cli, [
        'git', 'update', '123',
        '--title', 'Updated Title',
        '--state', 'closed',
        '--labels', 'bug,resolved'
    ])

    assert result.exit_code == 0
    call_args = mock_github_client.update_issue.call_args[0]
    assert call_args[1]['title'] == 'Updated Title'
    assert call_args[1]['state'] == 'closed'
    assert 'bug' in call_args[1]['labels']


def test_git_update_with_hash_prefix(runner, mock_github_client):
    """Test updating issue with # prefix."""
    result = runner.invoke(cli, [
        'git', 'update', '#456',
        '--title', 'New Title'
    ])

    assert result.exit_code == 0
    call_args = mock_github_client.update_issue.call_args[0]
    assert call_args[0] == '#456'


def test_git_update_with_repository(runner, mock_github_client):
    """Test updating issue in specific repository."""
    result = runner.invoke(cli, [
        'git', 'update', 'owner/repo#789',
        '--title', 'New Title'
    ])

    assert result.exit_code == 0
    call_args = mock_github_client.update_issue.call_args[0]
    assert call_args[0] == 'owner/repo#789'


def test_git_update_no_fields(runner, mock_github_client):
    """Test updating without specifying any fields."""
    result = runner.invoke(cli, [
        'git', 'update', '123'
    ])

    # Should fail or warn about no fields to update
    assert result.exit_code == 1
    assert 'No fields to update' in result.output or 'at least one option' in result.output


def test_git_update_invalid_state(runner, mock_github_client):
    """Test updating with invalid state."""
    result = runner.invoke(cli, [
        'git', 'update', '123',
        '--state', 'invalid'
    ])

    # Should fail due to invalid choice
    assert result.exit_code != 0


def test_git_update_issue_not_found(runner, mock_github_client):
    """Test updating non-existent issue."""
    mock_github_client.update_issue.side_effect = IssueTrackerNotFoundError("Issue not found")

    result = runner.invoke(cli, [
        'git', 'update', '999',
        '--title', 'New Title'
    ])

    assert result.exit_code == 1
    assert 'not found' in result.output.lower()


def test_git_update_authentication_error(runner, mock_github_client):
    """Test updating with authentication error."""
    mock_github_client.update_issue.side_effect = IssueTrackerAuthError("Authentication failed")

    result = runner.invoke(cli, [
        'git', 'update', '123',
        '--title', 'New Title'
    ])

    assert result.exit_code == 1
    assert 'Authentication' in result.output or 'auth' in result.output.lower()


def test_git_update_api_error(runner, mock_github_client):
    """Test updating with API error."""
    mock_github_client.update_issue.side_effect = IssueTrackerApiError("API error")

    result = runner.invoke(cli, [
        'git', 'update', '123',
        '--title', 'New Title'
    ])

    assert result.exit_code == 1


def test_git_update_json_output(runner, mock_github_client):
    """Test updating issue with JSON output."""
    result = runner.invoke(cli, [
        'git', 'update', '123',
        '--title', 'New Title',
        '--json'
    ])

    assert result.exit_code == 0
    output_data = json.loads(result.output)
    assert output_data['success'] is True
    assert 'issue_key' in output_data['data']


def test_git_update_labels_comma_separated(runner, mock_github_client):
    """Test updating labels with comma-separated values."""
    result = runner.invoke(cli, [
        'git', 'update', '123',
        '--labels', 'bug, priority: high, backend'
    ])

    assert result.exit_code == 0
    call_args = mock_github_client.update_issue.call_args[0]
    # Should strip whitespace
    assert 'bug' in call_args[1]['labels']
    assert 'priority: high' in call_args[1]['labels']
    assert 'backend' in call_args[1]['labels']


def test_git_update_empty_labels(runner, mock_github_client):
    """Test clearing labels with empty string."""
    result = runner.invoke(cli, [
        'git', 'update', '123',
        '--labels', ''
    ])

    assert result.exit_code == 0
    # Should accept empty labels (clear all labels)
    mock_github_client.update_issue.assert_called_once()


def test_git_update_repository_option(runner, mock_github_client):
    """Test using --repository option."""
    result = runner.invoke(cli, [
        'git', 'update', '123',
        '--title', 'New Title',
        '--repository', 'other/repo'
    ])

    assert result.exit_code == 0
    # Repository should be passed to client
    mock_github_client.update_issue.assert_called_once()


def test_git_update_works_inside_claude_session(runner, mock_github_client, monkeypatch):
    """Test that git update works inside Claude sessions (no @require_outside_claude decorator)."""
    # Simulate running inside a Claude Code session
    monkeypatch.setenv("DEVAIFLOW_IN_SESSION", "1")
    monkeypatch.setenv("AI_AGENT_SESSION_ID", "test-session-123")

    result = runner.invoke(cli, [
        'git', 'update', '123',
        '--title', 'Updated from Claude session'
    ])

    # Should succeed (not blocked by decorator)
    assert result.exit_code == 0
    mock_github_client.update_issue.assert_called_once()
    call_args = mock_github_client.update_issue.call_args[0]
    assert call_args[1]['title'] == 'Updated from Claude session'
