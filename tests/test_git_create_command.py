"""Tests for daf git create command."""

import json
import pytest
from unittest.mock import patch, Mock
from click.testing import CliRunner

from devflow.cli.main import cli
from devflow.issue_tracker.exceptions import (
    IssueTrackerValidationError,
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
    with patch('devflow.cli.commands.git_create_command.GitHubClient') as mock_client_class:
        mock_client = Mock()
        mock_client_class.return_value = mock_client
        yield mock_client


@pytest.fixture
def mock_config():
    """Mock config loader."""
    with patch('devflow.cli.commands.git_create_command.ConfigLoader') as mock_loader_class:
        mock_loader = Mock()
        mock_config = Mock()
        mock_config.github = Mock()
        mock_config.github.default_labels = []
        mock_config.github.issue_types = ["bug", "enhancement", "task", "spike", "epic"]
        mock_loader.load_config.return_value = mock_config
        mock_loader_class.return_value = mock_loader
        yield mock_config


def test_git_create_basic_issue(runner, mock_github_client, mock_config):
    """Test creating a basic issue without type."""
    mock_github_client.create_issue.return_value = 'owner/repo#123'

    result = runner.invoke(cli, [
        'git', 'create',
        '--summary', 'Test Issue',
        '--description', 'Test description'
    ])

    assert result.exit_code == 0
    assert '#123' in result.output or 'Created' in result.output
    mock_github_client.create_issue.assert_called_once()
    # Verify issue_type is None when not provided
    call_args = mock_github_client.create_issue.call_args[1]
    assert call_args['issue_type'] is None


def test_git_create_bug(runner, mock_github_client, mock_config):
    """Test creating a bug issue with explicit type."""
    mock_github_client.create_issue.return_value = 'owner/repo#124'

    result = runner.invoke(cli, [
        'git', 'create',
        'bug',
        '--summary', 'Fix timeout',
        '--description', 'Timeout occurs after 30s'
    ])

    assert result.exit_code == 0
    call_args = mock_github_client.create_issue.call_args[1]
    assert call_args['issue_type'] == 'bug'
    assert call_args['summary'] == 'Fix timeout'


def test_git_create_enhancement(runner, mock_github_client, mock_config):
    """Test creating an enhancement issue."""
    mock_github_client.create_issue.return_value = 'owner/repo#125'

    result = runner.invoke(cli, [
        'git', 'create',
        'enhancement',
        '--summary', 'Add caching',
        '--description', 'Add caching layer for better performance'
    ])

    assert result.exit_code == 0
    call_args = mock_github_client.create_issue.call_args[1]
    assert call_args['issue_type'] == 'enhancement'


def test_git_create_with_priority(runner, mock_github_client, mock_config):
    """Test creating issue with priority but no type."""
    mock_github_client.create_issue.return_value = 'owner/repo#126'

    result = runner.invoke(cli, [
        'git', 'create',
        '--summary', 'Critical bug',
        '--priority', 'critical',
        '--description', 'Critical issue that needs immediate attention'
    ])

    assert result.exit_code == 0
    call_args = mock_github_client.create_issue.call_args[1]
    assert call_args['priority'] == 'critical'
    assert call_args['issue_type'] is None  # No type specified


def test_git_create_with_story_points(runner, mock_github_client, mock_config):
    """Test creating issue with story points but no type."""
    mock_github_client.create_issue.return_value = 'owner/repo#127'

    result = runner.invoke(cli, [
        'git', 'create',
        '--summary', 'Medium task',
        '--points', '5',
        '--description', 'Medium complexity task'
    ])

    assert result.exit_code == 0
    call_args = mock_github_client.create_issue.call_args[1]
    assert call_args['points'] == 5
    assert call_args['issue_type'] is None  # No type specified


def test_git_create_with_labels(runner, mock_github_client, mock_config):
    """Test creating issue with additional labels but no type."""
    mock_github_client.create_issue.return_value = 'owner/repo#128'

    result = runner.invoke(cli, [
        'git', 'create',
        '--summary', 'Backend task',
        '--labels', 'backend,api',
        '--description', 'Backend API task'
    ])

    assert result.exit_code == 0
    call_args = mock_github_client.create_issue.call_args[1]
    required_fields = call_args.get('required_custom_fields', {})
    assert 'labels' in required_fields
    assert 'backend' in required_fields['labels']
    assert 'api' in required_fields['labels']
    assert call_args['issue_type'] is None  # No type specified


def test_git_create_with_assignee(runner, mock_github_client, mock_config):
    """Test creating issue with assignee but no type."""
    mock_github_client.create_issue.return_value = 'owner/repo#129'

    result = runner.invoke(cli, [
        'git', 'create',
        '--summary', 'Assigned task',
        '--assignee', 'johndoe',
        '--description', 'Task assigned to johndoe'
    ])

    assert result.exit_code == 0
    # Assignee is set via update_issue after creation
    mock_github_client.update_issue.assert_called_once()
    # Check that issue_type was None in create_issue call
    call_args = mock_github_client.create_issue.call_args[1]
    assert call_args['issue_type'] is None  # No type specified


def test_git_create_with_milestone(runner, mock_github_client, mock_config):
    """Test creating issue with milestone but no type."""
    mock_github_client.create_issue.return_value = 'owner/repo#130'

    result = runner.invoke(cli, [
        'git', 'create',
        '--summary', 'Sprint task',
        '--milestone', 'Sprint 24',
        '--description', 'Task for Sprint 24'
    ])

    assert result.exit_code == 0
    # Milestone is set via update_issue after creation
    mock_github_client.update_issue.assert_called_once()
    # Check that issue_type was None in create_issue call
    call_args = mock_github_client.create_issue.call_args[1]
    assert call_args['issue_type'] is None  # No type specified


def test_git_create_with_acceptance_criteria(runner, mock_github_client, mock_config):
    """Test creating issue with acceptance criteria but no type."""
    mock_github_client.create_issue.return_value = 'owner/repo#131'

    result = runner.invoke(cli, [
        'git', 'create',
        '--summary', 'Feature request',
        '--acceptance-criteria', 'Tests pass',
        '--acceptance-criteria', 'Documentation updated',
        '--description', 'Feature request with acceptance criteria'
    ])

    assert result.exit_code == 0
    call_args = mock_github_client.create_issue.call_args[1]
    required_fields = call_args.get('required_custom_fields', {})
    assert 'acceptance_criteria' in required_fields
    assert len(required_fields['acceptance_criteria']) == 2
    assert call_args['issue_type'] is None  # No type specified


def test_git_create_all_options(runner, mock_github_client, mock_config):
    """Test creating issue with all options including explicit type."""
    mock_github_client.create_issue.return_value = 'owner/repo#132'

    result = runner.invoke(cli, [
        'git', 'create',
        'bug',
        '--summary', 'Complex issue',
        '--description', 'Detailed description',
        '--priority', 'high',
        '--points', '8',
        '--labels', 'backend,urgent',
        '--assignee', 'janedoe',
        '--milestone', 'v2.0',
        '--acceptance-criteria', 'AC 1',
        '--acceptance-criteria', 'AC 2'
    ])

    assert result.exit_code == 0
    call_args = mock_github_client.create_issue.call_args[1]
    assert call_args['issue_type'] == 'bug'
    assert call_args['summary'] == 'Complex issue'
    assert call_args['priority'] == 'high'
    assert call_args['points'] == 8
    # Assignee and milestone are set via update_issue calls
    assert mock_github_client.update_issue.call_count == 2


def test_git_create_missing_summary(runner, mock_github_client, mock_config):
    """Test creating issue without required summary."""
    result = runner.invoke(cli, [
        'git', 'create',
        '--description', 'Has description but no summary'
    ])

    # Should fail due to missing required field
    assert result.exit_code != 0


def test_git_create_validation_error(runner, mock_github_client, mock_config):
    """Test creating issue with validation error."""
    mock_github_client.create_issue.side_effect = IssueTrackerValidationError("Invalid data")

    result = runner.invoke(cli, [
        'git', 'create',
        '--summary', 'Test',
        '--description', 'Test description'
    ])

    assert result.exit_code == 1
    assert 'Invalid' in result.output or 'Validation error' in result.output


def test_git_create_authentication_error(runner, mock_github_client, mock_config):
    """Test creating issue with authentication error."""
    mock_github_client.create_issue.side_effect = IssueTrackerAuthError("Authentication failed")

    result = runner.invoke(cli, [
        'git', 'create',
        '--summary', 'Test',
        '--description', 'Test description'
    ])

    assert result.exit_code == 1
    assert 'authentication failed' in result.output.lower() or 'gh auth login' in result.output.lower()


def test_git_create_api_error(runner, mock_github_client, mock_config):
    """Test creating issue with API error."""
    mock_github_client.create_issue.side_effect = IssueTrackerApiError("API error")

    result = runner.invoke(cli, [
        'git', 'create',
        '--summary', 'Test'
    ])

    assert result.exit_code == 1


def test_git_create_json_output(runner, mock_github_client, mock_config):
    """Test creating issue with JSON output."""
    mock_github_client.create_issue.return_value = 'owner/repo#133'

    result = runner.invoke(cli, [
        'git', 'create',
        '--summary', 'Test Issue',
        '--description', 'Test description',
        '--json'
    ])

    assert result.exit_code == 0
    output_data = json.loads(result.output)
    assert output_data['success'] is True
    assert 'issue_key' in output_data['data']


def test_git_create_with_repository(runner, mock_github_client, mock_config):
    """Test creating issue in specific repository."""
    mock_github_client.create_issue.return_value = 'other/repo#134'

    result = runner.invoke(cli, [
        'git', 'create',
        '--summary', 'Test',
        '--description', 'Test description',
        '--repository', 'other/repo'
    ])

    assert result.exit_code == 0


def test_git_create_invalid_priority(runner, mock_github_client, mock_config):
    """Test creating issue with invalid priority."""
    result = runner.invoke(cli, [
        'git', 'create',
        '--summary', 'Test',
        '--priority', 'invalid'
    ])

    # Should fail due to invalid choice
    assert result.exit_code != 0


def test_git_create_invalid_type(runner, mock_github_client, mock_config):
    """Test creating issue with invalid type."""
    result = runner.invoke(cli, [
        'git', 'create',
        'invalid',
        '--summary', 'Test'
    ])

    # Should fail due to invalid choice
    assert result.exit_code != 0


def test_git_create_with_parent(runner, mock_github_client, mock_config):
    """Test creating issue with parent parameter."""
    from devflow.issue_tracker.exceptions import IssueTrackerNotFoundError

    # Mock get_issue to validate parent exists
    mock_parent = {'summary': 'Parent Issue', 'key': 'owner/repo#456'}
    mock_github_client.get_issue.return_value = mock_parent
    mock_github_client.create_issue.return_value = 'owner/repo#123'

    result = runner.invoke(cli, [
        'git', 'create',
        'task',
        '--summary', 'Child Issue',
        '--description', 'Child task',
        '--parent', '#456'
    ])

    assert result.exit_code == 0
    assert '#123' in result.output or 'Created' in result.output

    # Verify parent validation was called
    mock_github_client.get_issue.assert_called_once_with('#456')

    # Verify create_issue was called with parent parameter
    call_args = mock_github_client.create_issue.call_args[1]
    assert call_args['parent'] == '#456'


def test_git_create_with_invalid_parent_format(runner, mock_github_client, mock_config):
    """Test creating issue with invalid parent key format."""
    mock_github_client.get_issue.side_effect = IssueTrackerValidationError(
        "Invalid format"
    )

    result = runner.invoke(cli, [
        'git', 'create',
        'task',
        '--summary', 'Child Issue',
        '--description', 'Child task description',
        '--parent', 'invalid-format'
    ])

    assert result.exit_code == 1
    assert 'Invalid parent issue key format' in result.output


def test_git_create_with_parent_not_found(runner, mock_github_client, mock_config):
    """Test creating issue when parent doesn't exist."""
    from devflow.issue_tracker.exceptions import IssueTrackerNotFoundError

    mock_github_client.get_issue.side_effect = IssueTrackerNotFoundError(
        "Parent not found",
        resource_type="issue",
        resource_id="#999"
    )

    result = runner.invoke(cli, [
        'git', 'create',
        'task',
        '--summary', 'Child Issue',
        '--description', 'Child task description',
        '--parent', '#999'
    ])

    assert result.exit_code == 1
    assert 'Parent issue #999 not found' in result.output
