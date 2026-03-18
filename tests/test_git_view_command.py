"""Tests for daf git view command."""

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
    with patch('devflow.cli.commands.git_view_command.GitRemoteDetector') as mock_detector_class:
        mock_detector = Mock()
        mock_detector.parse_repository_info.return_value = ('github', 'owner', 'repo')
        mock_detector_class.return_value = mock_detector

        # Patch the factory to return a mock client
        with patch('devflow.cli.commands.git_view_command.create_issue_tracker_client') as mock_factory:
            mock_client = Mock()
            mock_client.repository = None
            mock_factory.return_value = mock_client
            yield mock_client


def test_git_view_basic_issue(runner, mock_github_client):
    """Test viewing a basic GitHub issue."""
    mock_github_client.get_ticket.return_value = {
        'key': '#123',
        'summary': 'Test Issue',
        'description': 'Description text',
        'status': 'open',
        'type': 'bug',
        'priority': 'high',
    }

    result = runner.invoke(cli, ['git', 'view', '123'])

    assert result.exit_code == 0
    assert 'Issue: #123' in result.output
    assert 'Test Issue' in result.output
    assert 'State: open' in result.output
    assert 'Type: bug' in result.output
    # Issue key is normalized (# stripped during parsing)
    mock_github_client.get_ticket.assert_called_once_with('123')


def test_git_view_with_hash_prefix(runner, mock_github_client):
    """Test viewing issue with # prefix."""
    mock_github_client.get_ticket.return_value = {
        'key': '#456',
        'summary': 'Issue with hash',
        'status': 'open',
    }

    result = runner.invoke(cli, ['git', 'view', '#456'])

    assert result.exit_code == 0
    # Hash is preserved when explicitly provided
    mock_github_client.get_ticket.assert_called_once_with('#456')


def test_git_view_with_repository(runner, mock_github_client):
    """Test viewing issue in specific repository."""
    mock_github_client.get_ticket.return_value = {
        'key': 'owner/repo#789',
        'summary': 'Issue in specific repo',
        'status': 'open',
    }

    result = runner.invoke(cli, ['git', 'view', 'owner/repo#789'])

    assert result.exit_code == 0
    assert 'owner/repo#789' in result.output


def test_git_view_with_comments(runner, mock_github_client):
    """Test viewing issue with comments."""
    mock_github_client.get_ticket_detailed.return_value = {
        'key': '#123',
        'summary': 'Issue with comments',
        'status': 'open',
        'comments': [
            {'author': 'user1', 'body': 'First comment', 'created': '2026-01-01T10:00:00Z'},
            {'author': 'user2', 'body': 'Second comment', 'created': '2026-01-02T11:00:00Z'},
        ]
    }

    result = runner.invoke(cli, ['git', 'view', '123', '--comments'])

    assert result.exit_code == 0
    assert 'COMMENTS' in result.output  # Section header is uppercase
    assert 'user1' in result.output
    assert 'First comment' in result.output
    mock_github_client.get_ticket_detailed.assert_called_once()


def test_git_view_issue_not_found(runner, mock_github_client):
    """Test viewing non-existent issue."""
    mock_github_client.get_ticket.side_effect = IssueTrackerNotFoundError("Issue not found")

    result = runner.invoke(cli, ['git', 'view', '999'])

    assert result.exit_code == 1
    assert 'Issue not found' in result.output or 'not found' in result.output.lower()


def test_git_view_authentication_error(runner, mock_github_client):
    """Test viewing issue with authentication error."""
    mock_github_client.get_ticket.side_effect = IssueTrackerAuthError("Authentication failed")

    result = runner.invoke(cli, ['git', 'view', '123'])

    assert result.exit_code == 1
    assert 'Authentication' in result.output or 'auth' in result.output.lower()


def test_git_view_api_error(runner, mock_github_client):
    """Test viewing issue with API error."""
    mock_github_client.get_ticket.side_effect = IssueTrackerApiError("API error occurred")

    result = runner.invoke(cli, ['git', 'view', '123'])

    assert result.exit_code == 1
    assert 'error' in result.output.lower()


def test_git_view_json_output(runner, mock_github_client):
    """Test viewing issue with JSON output."""
    mock_github_client.get_ticket.return_value = {
        'key': '#123',
        'summary': 'Test Issue',
        'status': 'open',
        'type': 'bug',
    }

    result = runner.invoke(cli, ['git', 'view', '123', '--json'])

    assert result.exit_code == 0
    output_data = json.loads(result.output)
    assert output_data['success'] is True
    assert output_data['data']['key'] == '#123'
    assert output_data['data']['summary'] == 'Test Issue'


def test_git_view_with_acceptance_criteria(runner, mock_github_client):
    """Test viewing issue with acceptance criteria."""
    mock_github_client.get_ticket.return_value = {
        'key': '#123',
        'summary': 'Feature request',
        'status': 'open',
        'acceptance_criteria': [
            'Criterion 1',
            'Criterion 2',
            'Criterion 3',
        ]
    }

    result = runner.invoke(cli, ['git', 'view', '123'])

    assert result.exit_code == 0
    assert 'Acceptance Criteria:' in result.output
    assert 'Criterion 1' in result.output
    assert 'Criterion 2' in result.output


def test_git_view_with_milestone(runner, mock_github_client):
    """Test viewing issue with milestone."""
    mock_github_client.get_ticket.return_value = {
        'key': '#123',
        'summary': 'Milestone task',
        'status': 'open',
        'milestone': 'v2.0',
    }

    result = runner.invoke(cli, ['git', 'view', '123'])

    assert result.exit_code == 0
    assert 'Milestone: v2.0' in result.output


def test_git_view_with_assignee(runner, mock_github_client):
    """Test viewing issue with assignee."""
    mock_github_client.get_ticket.return_value = {
        'key': '#123',
        'summary': 'Assigned task',
        'status': 'open',
        'assignee': 'johndoe',
    }

    result = runner.invoke(cli, ['git', 'view', '123'])

    assert result.exit_code == 0
    assert '@johndoe' in result.output


def test_git_view_with_labels(runner, mock_github_client):
    """Test viewing issue with labels."""
    mock_github_client.get_ticket.return_value = {
        'key': '#123',
        'summary': 'Labeled issue',
        'status': 'open',
        'labels': ['bug', 'priority: high', 'backend'],
    }

    result = runner.invoke(cli, ['git', 'view', '123'])

    assert result.exit_code == 0
    assert 'Labels:' in result.output
    assert 'bug' in result.output
    assert 'priority: high' in result.output
