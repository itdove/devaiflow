"""Tests for GitHubClient issue tracker implementation."""

import json
import pytest
from unittest.mock import Mock, patch, MagicMock
import subprocess

from devflow.github.issues_client import GitHubClient
from devflow.issue_tracker.exceptions import (
    IssueTrackerApiError,
    IssueTrackerAuthError,
    IssueTrackerConnectionError,
    IssueTrackerNotFoundError,
    IssueTrackerValidationError,
    IssueTrackerConfigError,
)


@pytest.fixture
def github_client():
    """Provide a GitHubClient instance."""
    return GitHubClient(repository="owner/repo")


@pytest.fixture
def mock_subprocess_run():
    """Mock subprocess.run for gh CLI commands."""
    with patch('subprocess.run') as mock_run:
        yield mock_run


class TestInitialization:
    """Tests for GitHubClient initialization."""

    def test_init_with_repository(self):
        """Test initialization with repository."""
        client = GitHubClient(repository="owner/repo")
        assert client.repository == "owner/repo"
        assert client.timeout == 30

    def test_init_with_custom_timeout(self):
        """Test initialization with custom timeout."""
        client = GitHubClient(timeout=60)
        assert client.timeout == 60

    def test_init_without_repository(self):
        """Test initialization without repository."""
        client = GitHubClient()
        assert client.repository is None


class TestParseIssueNumber:
    """Tests for _parse_issue_number method."""

    def test_parse_issue_number_only(self, github_client):
        """Test parsing issue number without repository."""
        repo, num = github_client._parse_issue_number("#123")
        assert repo is None
        assert num == 123

    def test_parse_issue_number_without_hash(self, github_client):
        """Test parsing issue number without # prefix."""
        repo, num = github_client._parse_issue_number("123")
        assert repo is None
        assert num == 123

    def test_parse_full_issue_key(self, github_client):
        """Test parsing full issue key with repository."""
        repo, num = github_client._parse_issue_number("owner/repo#456")
        assert repo == "owner/repo"
        assert num == 456

    def test_parse_invalid_format(self, github_client):
        """Test parsing invalid issue key format."""
        with pytest.raises(IssueTrackerValidationError) as exc_info:
            github_client._parse_issue_number("invalid-format")
        assert "Invalid GitHub issue key format" in str(exc_info.value)


class TestGetRepository:
    """Tests for _get_repository method."""

    def test_get_repository_from_parameter(self, github_client):
        """Test getting repository from parameter."""
        repo = github_client._get_repository("other/repo")
        assert repo == "other/repo"

    def test_get_repository_from_client_default(self, github_client):
        """Test getting repository from client default."""
        repo = github_client._get_repository()
        assert repo == "owner/repo"

    @patch('devflow.github.issues_client.GitRemoteDetector')
    def test_get_repository_auto_detect(self, mock_detector_class):
        """Test auto-detecting repository from git remote."""
        # Create client without repository
        client = GitHubClient()

        # Mock git remote detector
        mock_detector = Mock()
        mock_detector.get_github_repository.return_value = "detected/repo"
        mock_detector_class.return_value = mock_detector

        repo = client._get_repository()
        assert repo == "detected/repo"

    @patch('devflow.github.issues_client.GitRemoteDetector')
    def test_get_repository_no_repo_available(self, mock_detector_class):
        """Test error when no repository is available."""
        client = GitHubClient()

        # Mock git remote detector to return None
        mock_detector = Mock()
        mock_detector.get_github_repository.return_value = None
        mock_detector_class.return_value = mock_detector

        with pytest.raises(IssueTrackerConfigError) as exc_info:
            client._get_repository()
        assert "No GitHub repository specified" in str(exc_info.value)


class TestRunGhCommand:
    """Tests for _run_gh_command method."""

    def test_successful_command(self, github_client, mock_subprocess_run):
        """Test successful gh command execution."""
        mock_subprocess_run.return_value = Mock(
            returncode=0,
            stdout='{"result": "success"}',
            stderr=''
        )

        result = github_client._run_gh_command(['api', 'test'])
        assert result == '{"result": "success"}'
        mock_subprocess_run.assert_called_once()

    def test_authentication_error(self, github_client, mock_subprocess_run):
        """Test authentication error handling."""
        mock_subprocess_run.return_value = Mock(
            returncode=4,
            stdout='',
            stderr='authentication failed'
        )

        with pytest.raises(IssueTrackerAuthError) as exc_info:
            github_client._run_gh_command(['api', 'test'])
        assert "GitHub authentication failed" in str(exc_info.value)

    def test_connection_error(self, github_client, mock_subprocess_run):
        """Test connection error handling."""
        mock_subprocess_run.return_value = Mock(
            returncode=1,
            stdout='',
            stderr='connection timeout'
        )

        with pytest.raises(IssueTrackerConnectionError):
            github_client._run_gh_command(['api', 'test'])

    def test_timeout_error(self, github_client, mock_subprocess_run):
        """Test timeout error handling."""
        mock_subprocess_run.side_effect = subprocess.TimeoutExpired(
            cmd=['gh'], timeout=30
        )

        with pytest.raises(IssueTrackerConnectionError) as exc_info:
            github_client._run_gh_command(['api', 'test'])
        assert "timed out" in str(exc_info.value)

    def test_gh_not_found(self, github_client, mock_subprocess_run):
        """Test error when gh CLI is not installed."""
        mock_subprocess_run.side_effect = FileNotFoundError()

        with pytest.raises(IssueTrackerConfigError) as exc_info:
            github_client._run_gh_command(['api', 'test'])
        assert "GitHub CLI (gh) not found" in str(exc_info.value)

    def test_generic_api_error(self, github_client, mock_subprocess_run):
        """Test generic API error handling."""
        mock_subprocess_run.return_value = Mock(
            returncode=1,
            stdout='',
            stderr='API error: resource not found'
        )

        with pytest.raises(IssueTrackerApiError):
            github_client._run_gh_command(['api', 'test'])


class TestGetTicket:
    """Tests for get_ticket method."""

    def test_get_ticket_success(self, github_client, mock_subprocess_run):
        """Test successfully getting a ticket."""
        mock_response = {
            "number": 123,
            "title": "Test Issue",
            "body": "Description",
            "state": "open",
            "labels": [{"name": "bug"}, {"name": "priority: high"}],
            "assignees": [{"login": "user1"}],
            "milestone": {"title": "v1.0"},
        }

        mock_subprocess_run.return_value = Mock(
            returncode=0,
            stdout=json.dumps(mock_response),
            stderr=''
        )

        issue = github_client.get_ticket("#123")

        # Key includes repository (owner/repo#123)
        assert issue['key'] == 'owner/repo#123'
        assert issue['summary'] == 'Test Issue'
        assert issue['description'] == 'Description'
        assert issue['status'] == 'open'
        assert issue['type'] == 'bug'
        assert issue['priority'] == 'high'
        assert issue['assignee'] == 'user1'
        assert issue['milestone'] == 'v1.0'

    def test_get_ticket_not_found(self, github_client, mock_subprocess_run):
        """Test getting a non-existent ticket."""
        mock_subprocess_run.return_value = Mock(
            returncode=1,
            stdout='',
            stderr='Not Found'
        )

        with pytest.raises(IssueTrackerNotFoundError) as exc_info:
            github_client.get_ticket("#999")
        assert "owner/repo#999 not found" in str(exc_info.value)

    def test_get_ticket_with_acceptance_criteria(self, github_client, mock_subprocess_run):
        """Test getting ticket with acceptance criteria."""
        body = '''Description text

<!-- ACCEPTANCE_CRITERIA_START -->
- [ ] Criterion 1
- [ ] Criterion 2
<!-- ACCEPTANCE_CRITERIA_END -->'''

        mock_response = {
            "number": 123,
            "title": "Test Issue",
            "body": body,
            "state": "open",
            "labels": [],
        }

        mock_subprocess_run.return_value = Mock(
            returncode=0,
            stdout=json.dumps(mock_response),
            stderr=''
        )

        issue = github_client.get_ticket("#123")

        assert 'acceptance_criteria' in issue
        assert len(issue['acceptance_criteria']) == 2
        assert 'Criterion 1' in issue['acceptance_criteria'][0]


class TestCreateIssue:
    """Tests for create_issue method."""

    def test_create_issue_basic(self, github_client, mock_subprocess_run):
        """Test creating a basic issue."""
        # gh CLI with --jq '.number' returns just the issue number
        mock_subprocess_run.return_value = Mock(
            returncode=0,
            stdout='124',
            stderr=''
        )

        from devflow.github.field_mapper import GitHubFieldMapper
        field_mapper = GitHubFieldMapper()

        issue_key = github_client.create_issue(
            issue_type='bug',
            summary='New Issue',
            description='Description',
            priority='',
            project_key='owner/repo',
            field_mapper=field_mapper,
        )

        assert issue_key == 'owner/repo#124'

    def test_create_issue_with_labels(self, github_client, mock_subprocess_run):
        """Test creating issue with labels."""
        # gh CLI with --jq '.number' returns just the issue number
        mock_subprocess_run.return_value = Mock(
            returncode=0,
            stdout='125',
            stderr=''
        )

        from devflow.github.field_mapper import GitHubFieldMapper
        field_mapper = GitHubFieldMapper()

        issue_key = github_client.create_issue(
            issue_type='enhancement',
            summary='Issue with Labels',
            description='Description',
            priority='high',
            project_key='owner/repo',
            field_mapper=field_mapper,
            points=5,
        )

        assert issue_key == 'owner/repo#125'

    def test_create_issue_with_acceptance_criteria(self, github_client, mock_subprocess_run):
        """Test creating issue with acceptance criteria."""
        # gh CLI with --jq '.number' returns just the issue number
        mock_subprocess_run.return_value = Mock(
            returncode=0,
            stdout='126',
            stderr=''
        )

        from devflow.github.field_mapper import GitHubFieldMapper
        field_mapper = GitHubFieldMapper()

        issue_key = github_client.create_issue(
            issue_type=None,
            summary='Issue with AC',
            description='Description',
            priority='',
            project_key='owner/repo',
            field_mapper=field_mapper,
            required_custom_fields={'acceptance_criteria': ['Criterion 1', 'Criterion 2']},
        )

        assert issue_key == 'owner/repo#126'


class TestUpdateIssue:
    """Tests for update_issue method."""

    def test_update_issue_title(self, github_client, mock_subprocess_run):
        """Test updating issue title."""
        mock_subprocess_run.return_value = Mock(
            returncode=0,
            stdout='{}',
            stderr=''
        )

        github_client.update_issue("#123", {'title': 'Updated Title'})

        # Verify gh api was called
        mock_subprocess_run.assert_called_once()

    def test_update_issue_state(self, github_client, mock_subprocess_run):
        """Test updating issue state."""
        mock_subprocess_run.return_value = Mock(
            returncode=0,
            stdout='{}',
            stderr=''
        )

        github_client.update_issue("#123", {'state': 'closed'})

        mock_subprocess_run.assert_called_once()

    def test_update_issue_labels(self, github_client, mock_subprocess_run):
        """Test updating issue labels."""
        mock_subprocess_run.return_value = Mock(
            returncode=0,
            stdout='{}',
            stderr=''
        )

        github_client.update_issue("#123", {'labels': ['bug', 'priority: high']})

        mock_subprocess_run.assert_called_once()


class TestAddComment:
    """Tests for add_comment method."""

    def test_add_comment_success(self, github_client, mock_subprocess_run):
        """Test successfully adding a comment."""
        mock_response = {
            "id": 1,
            "body": "Test comment"
        }

        mock_subprocess_run.return_value = Mock(
            returncode=0,
            stdout=json.dumps(mock_response),
            stderr=''
        )

        github_client.add_comment("#123", "Test comment")

        mock_subprocess_run.assert_called_once()

    def test_add_comment_public_flag_ignored(self, github_client, mock_subprocess_run):
        """Test that public flag is ignored (GitHub comments are always public)."""
        mock_response = {"id": 1, "body": "Comment"}

        mock_subprocess_run.return_value = Mock(
            returncode=0,
            stdout=json.dumps(mock_response),
            stderr=''
        )

        # public parameter is ignored for GitHub
        github_client.add_comment("#123", "Comment", public=False)

        mock_subprocess_run.assert_called_once()


class TestTransitionTicket:
    """Tests for transition_ticket method."""

    def test_transition_to_open(self, github_client, mock_subprocess_run):
        """Test transitioning issue to open state."""
        mock_subprocess_run.return_value = Mock(
            returncode=0,
            stdout='{}',
            stderr=''
        )

        github_client.transition_ticket("#123", "open")

        mock_subprocess_run.assert_called_once()

    def test_transition_to_closed(self, github_client, mock_subprocess_run):
        """Test transitioning issue to closed state."""
        mock_subprocess_run.return_value = Mock(
            returncode=0,
            stdout='{}',
            stderr=''
        )

        github_client.transition_ticket("#123", "closed")

        mock_subprocess_run.assert_called_once()

    def test_transition_invalid_state(self, github_client, mock_subprocess_run):
        """Test transitioning to invalid state (passed through to API)."""
        # GitHub API will validate the state, not our code
        # Our code just passes through unknown states
        mock_subprocess_run.return_value = Mock(
            returncode=0,
            stdout='{}',
            stderr=''
        )

        # Should not raise - unknown states are passed through
        github_client.transition_ticket("#123", "invalid")

        # Verify the API was called (state passed as-is)
        mock_subprocess_run.assert_called_once()


class TestAttachFile:
    """Tests for attach_file method (not supported)."""

    def test_attach_file_not_supported(self, github_client):
        """Test that file attachments raise NotImplementedError."""
        with pytest.raises(NotImplementedError) as exc_info:
            github_client.attach_file("#123", "/path/to/file.txt")
        assert "GitHub Issues do not support file attachments" in str(exc_info.value)


class TestListTickets:
    """Tests for list_tickets method."""

    def test_list_tickets_basic(self, github_client, mock_subprocess_run):
        """Test listing tickets."""
        mock_response = [
            {"number": 1, "title": "Issue 1", "state": "open", "labels": []},
            {"number": 2, "title": "Issue 2", "state": "open", "labels": []},
        ]

        mock_subprocess_run.return_value = Mock(
            returncode=0,
            stdout=json.dumps(mock_response),
            stderr=''
        )

        issues = github_client.list_tickets()

        assert len(issues) == 2
        assert issues[0]['key'] == 'owner/repo#1'
        assert issues[1]['key'] == 'owner/repo#2'

    def test_list_tickets_with_filter(self, github_client, mock_subprocess_run):
        """Test listing tickets with status filter."""
        mock_response = [
            {"number": 1, "title": "Open Issue", "state": "open", "labels": []},
        ]

        mock_subprocess_run.return_value = Mock(
            returncode=0,
            stdout=json.dumps(mock_response),
            stderr=''
        )

        issues = github_client.list_tickets(status=["open"])

        assert len(issues) == 1
        assert issues[0]['status'] == 'open'


class TestGetTicketPrLinks:
    """Tests for get_ticket_pr_links method."""

    def test_get_pr_links_from_body(self, github_client, mock_subprocess_run):
        """Test extracting PR links from issue body."""
        body = '''Description

Related PRs:
- #45
- https://github.com/owner/repo/pull/46
'''

        mock_response = {
            "number": 123,
            "title": "Issue",
            "body": body,
            "state": "open",
            "labels": [],
        }

        mock_subprocess_run.return_value = Mock(
            returncode=0,
            stdout=json.dumps(mock_response),
            stderr=''
        )

        pr_links = github_client.get_ticket_pr_links("#123")

        # Should find PR references
        assert pr_links is not None


class TestLinkIssues:
    """Tests for link_issues method (not supported)."""

    def test_link_issues_creates_reference(self, github_client, mock_subprocess_run):
        """Test that issue linking creates a reference comment."""
        mock_subprocess_run.return_value = Mock(
            returncode=0,
            stdout='{}',
            stderr=''
        )

        # Link issues by adding a reference comment
        github_client.link_issues("#123", "relates to", "#456", comment="Additional context")

        # Verify add_comment was called with reference text
        mock_subprocess_run.assert_called_once()
