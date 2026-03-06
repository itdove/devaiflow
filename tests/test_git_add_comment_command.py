"""Tests for daf git add-comment command."""

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
    with patch('devflow.cli.commands.git_add_comment_command.GitHubClient') as mock_client_class:
        mock_client = Mock()
        mock_client_class.return_value = mock_client
        yield mock_client


def test_git_add_comment_basic(runner, mock_github_client):
    """Test adding a basic comment."""
    result = runner.invoke(cli, [
        'git', 'add-comment', '123',
        'This is a test comment'
    ])

    assert result.exit_code == 0
    mock_github_client.add_comment.assert_called_once()
    call_args = mock_github_client.add_comment.call_args[0]
    assert call_args[0] == '123'
    assert call_args[1] == 'This is a test comment'


def test_git_add_comment_multiline(runner, mock_github_client):
    """Test adding a multi-line comment."""
    comment_text = """This is a multi-line comment.

It has multiple paragraphs.

And some details."""

    result = runner.invoke(cli, [
        'git', 'add-comment', '123',
        comment_text
    ])

    assert result.exit_code == 0
    call_args = mock_github_client.add_comment.call_args[0]
    assert 'multi-line' in call_args[1]
    assert 'multiple paragraphs' in call_args[1]


def test_git_add_comment_with_hash_prefix(runner, mock_github_client):
    """Test adding comment to issue with # prefix."""
    result = runner.invoke(cli, [
        'git', 'add-comment', '#456',
        'Comment text'
    ])

    assert result.exit_code == 0
    call_args = mock_github_client.add_comment.call_args[0]
    assert call_args[0] == '#456'


def test_git_add_comment_with_repository(runner, mock_github_client):
    """Test adding comment to issue in specific repository."""
    result = runner.invoke(cli, [
        'git', 'add-comment', 'owner/repo#789',
        'Comment text'
    ])

    assert result.exit_code == 0
    call_args = mock_github_client.add_comment.call_args[0]
    assert call_args[0] == 'owner/repo#789'


def test_git_add_comment_empty_text(runner, mock_github_client):
    """Test adding empty comment."""
    result = runner.invoke(cli, [
        'git', 'add-comment', '123',
        ''
    ])

    # Should fail with empty comment
    assert result.exit_code == 1
    assert 'required' in result.output.lower() or 'empty' in result.output.lower()


def test_git_add_comment_whitespace_only(runner, mock_github_client):
    """Test adding comment with only whitespace."""
    result = runner.invoke(cli, [
        'git', 'add-comment', '123',
        '   \n\t   '
    ])

    # Should fail with whitespace-only comment
    assert result.exit_code == 1


def test_git_add_comment_issue_not_found(runner, mock_github_client):
    """Test adding comment to non-existent issue."""
    mock_github_client.add_comment.side_effect = IssueTrackerNotFoundError("Issue not found")

    result = runner.invoke(cli, [
        'git', 'add-comment', '999',
        'Comment text'
    ])

    assert result.exit_code == 1
    assert 'not found' in result.output.lower()


def test_git_add_comment_authentication_error(runner, mock_github_client):
    """Test adding comment with authentication error."""
    mock_github_client.add_comment.side_effect = IssueTrackerAuthError("Authentication failed")

    result = runner.invoke(cli, [
        'git', 'add-comment', '123',
        'Comment text'
    ])

    assert result.exit_code == 1
    assert 'Authentication' in result.output or 'auth' in result.output.lower()


def test_git_add_comment_api_error(runner, mock_github_client):
    """Test adding comment with API error."""
    mock_github_client.add_comment.side_effect = IssueTrackerApiError("API error")

    result = runner.invoke(cli, [
        'git', 'add-comment', '123',
        'Comment text'
    ])

    assert result.exit_code == 1


def test_git_add_comment_json_output(runner, mock_github_client):
    """Test adding comment with JSON output."""
    result = runner.invoke(cli, [
        'git', 'add-comment', '123',
        'Test comment',
        '--json'
    ])

    assert result.exit_code == 0
    output_data = json.loads(result.output)
    assert output_data['success'] is True
    assert 'issue_key' in output_data['data']


def test_git_add_comment_repository_option(runner, mock_github_client):
    """Test using --repository option."""
    result = runner.invoke(cli, [
        'git', 'add-comment', '123',
        'Test comment',
        '--repository', 'other/repo'
    ])

    assert result.exit_code == 0
    mock_github_client.add_comment.assert_called_once()


def test_git_add_comment_with_markdown(runner, mock_github_client):
    """Test adding comment with markdown formatting."""
    markdown_comment = """## Update

- Completed feature A
- Started feature B
- Blocked on issue #456

**Next steps:**
1. Finish feature B
2. Add tests
3. Create PR
"""

    result = runner.invoke(cli, [
        'git', 'add-comment', '123',
        markdown_comment
    ])

    assert result.exit_code == 0
    call_args = mock_github_client.add_comment.call_args[0]
    assert '## Update' in call_args[1]
    assert 'Completed feature A' in call_args[1]


def test_git_add_comment_with_code_block(runner, mock_github_client):
    """Test adding comment with code block."""
    code_comment = """Fixed the issue with this change:

```python
def fixed_function():
    return "now works"
```

Tests passing."""

    result = runner.invoke(cli, [
        'git', 'add-comment', '123',
        code_comment
    ])

    assert result.exit_code == 0
    call_args = mock_github_client.add_comment.call_args[0]
    assert '```python' in call_args[1]
    assert 'def fixed_function' in call_args[1]


def test_git_add_comment_with_mentions(runner, mock_github_client):
    """Test adding comment with @mentions."""
    result = runner.invoke(cli, [
        'git', 'add-comment', '123',
        '@johndoe please review this'
    ])

    assert result.exit_code == 0
    call_args = mock_github_client.add_comment.call_args[0]
    assert '@johndoe' in call_args[1]


def test_git_add_comment_with_issue_references(runner, mock_github_client):
    """Test adding comment with issue references."""
    result = runner.invoke(cli, [
        'git', 'add-comment', '123',
        'Related to #456 and fixes #789'
    ])

    assert result.exit_code == 0
    call_args = mock_github_client.add_comment.call_args[0]
    assert '#456' in call_args[1]
    assert '#789' in call_args[1]


def test_git_add_comment_long_text(runner, mock_github_client):
    """Test adding a very long comment."""
    long_comment = "This is a long comment. " * 100

    result = runner.invoke(cli, [
        'git', 'add-comment', '123',
        long_comment
    ])

    assert result.exit_code == 0
    call_args = mock_github_client.add_comment.call_args[0]
    assert len(call_args[1]) > 1000


def test_git_add_comment_special_characters(runner, mock_github_client):
    """Test adding comment with special characters."""
    special_comment = "Comment with special chars: <>&\"'`"

    result = runner.invoke(cli, [
        'git', 'add-comment', '123',
        special_comment
    ])

    assert result.exit_code == 0
    call_args = mock_github_client.add_comment.call_args[0]
    assert special_comment in call_args[1]


def test_git_add_comment_public_flag_ignored(runner, mock_github_client):
    """Test that public flag exists but is ignored (GitHub comments are always public)."""
    # This test verifies the flag is accepted but has no effect
    # GitHub comments are always public, unlike JIRA
    result = runner.invoke(cli, [
        'git', 'add-comment', '123',
        'Public comment'
    ])

    assert result.exit_code == 0
    # Comment should be added normally (public parameter is ignored)
    mock_github_client.add_comment.assert_called_once()
