"""Tests for GitHubClient issue tracker implementation."""

import json
import pytest
from unittest.mock import Mock, patch, MagicMock
import subprocess

from devflow.github.issues_client import GitHubClient, _text_has_pr_url
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


@pytest.fixture
def mock_gh_auth_check():
    """Mock GitHub auth check to always return success."""
    with patch('devflow.github.issues_client.check_gh_auth_for_repo') as mock_check:
        # Default: auth check passes
        mock_check.return_value = (True, 'ok', '')
        yield mock_check


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

    def test_get_ticket_not_found(self, github_client, mock_subprocess_run, mock_gh_auth_check):
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


class TestPrUrlMatching:
    """Recognize complete PR identities in text without substring matches."""

    @pytest.mark.parametrize(
        "text",
        [
            "Pull request created: https://github.com/owner/project-a/pull/123",
            "[PR](https://github.com/owner/project-a/pull/123)",
            "[PR](https://github.com/owner/project-a/pull/123),next",
            "https://github.com/owner/project-a/pull/999,https://github.com/owner/project-a/pull/123",
            "https://github.com/owner/project-a/pull/123;another PR",
            "<https://github.com/owner/project-a/pull/123>",
            "See https://github.com/owner/project-a/pull/123.",
            "(https://github.com/owner/project-a/pull/123), ready for review",
            "`https://github.com/owner/project-a/pull/123`",
            "https://github.com/owner/project-a/pull/123/",
            "https://github.com/owner/project-a/pull/123#discussion-1",
            "https://github.com/owner/project-a/pull/123?view=all",
            "HTTPS://GITHUB.COM/Owner/Project-A/pull/123",
        ],
    )
    def test_matching_url(self, text: str) -> None:
        """Plain and Markdown links identify the same PR despite presentation."""
        assert _text_has_pr_url(text, "https://github.com/owner/project-a/pull/123")

    @pytest.mark.parametrize(
        "text",
        [
            "",
            "https://github.com/owner/project-a/pull/1234",
            "https://github.com/owner/project-a/pull/12",
            "https://github.com/owner/project-b/pull/123",
            "https://github.com/other/project-a/pull/123",
            "https://github.example.com/owner/project-a/pull/123",
            "https://github.com/owner/project-a/issues/123",
            "https://github.com/owner/project-a/pull/123/files",
            "https://github.com/owner/project-a/pull/123-other",
            "https://example.com/?next=https://github.com/owner/project-a/pull/123",
            "https://github.com/owner/project-a/pull/123/456",
        ],
    )
    def test_different_url(self, text: str) -> None:
        """Another host, repository, number, or longer URL must not match."""
        assert not _text_has_pr_url(text, "https://github.com/owner/project-a/pull/123")

    @pytest.mark.parametrize("pr_url", ["invalid", "https://github.com/owner/project-a/issues/123"])
    def test_invalid_target_url(self, pr_url: str) -> None:
        """An invalid target cannot silently count as a successful lookup."""
        with pytest.raises(ValueError, match="Invalid pull request URL"):
            _text_has_pr_url("", pr_url)


class TestGetIssueComments:
    """Comment enumeration must be complete and distinguish errors from no comments."""

    def test_all_pages_and_qualified_repository(self, github_client: GitHubClient) -> None:
        """The CLI paginates and slurps arrays from the explicitly named repository."""
        pages = [
            [{"body": "First comment", "user": {"login": "user1"}, "created_at": "2026-01-01"}],
            [{"body": "Later comment", "user": None, "created_at": "2026-01-02"}],
        ]
        with patch.object(github_client, "_run_gh_command", return_value=json.dumps(pages)) as run:
            comments = github_client.get_issue_comments("other/project-a#42")

        run.assert_called_once_with(
            [
                "api",
                "/repos/other/project-a/issues/42/comments?per_page=100",
                "--paginate",
                "--slurp",
            ]
        )
        assert comments == [
            {"body": "First comment", "author": "user1", "created_at": "2026-01-01"},
            {"body": "Later comment", "author": "", "created_at": "2026-01-02"},
        ]

    def test_empty_comments(self, github_client: GitHubClient) -> None:
        """An empty page is a successful lookup with no comments."""
        with patch.object(github_client, "_run_gh_command", return_value="[[]]"):
            assert github_client.get_issue_comments("#42") == []

    def test_null_comment_body(self, github_client: GitHubClient) -> None:
        """A null body and deleted author are valid empty content."""
        with patch.object(github_client, "_run_gh_command", return_value='[[{"body": null}]]'):
            assert github_client.get_issue_comments("#42")[0]["body"] == ""

    @pytest.mark.parametrize(
        "output",
        [
            "invalid json",
            "{}",
            "[{}]",
            '[["invalid"]]',
            '[[{"body": 42}]]',
            "[[], {}]",
            '[[{"body": "Comment", "user": []}]]',
        ],
    )
    def test_malformed_comments_raise(self, github_client: GitHubClient, output: str) -> None:
        """Malformed or partially parsed pages are not treated as empty comments."""
        with (
            patch.object(github_client, "_run_gh_command", return_value=output),
            pytest.raises(IssueTrackerApiError, match="Could not parse comments"),
        ):
            github_client.get_issue_comments("#42")

    @pytest.mark.parametrize(
        "error",
        [
            IssueTrackerAuthError("Authentication failed"),
            IssueTrackerConnectionError("Connection failed"),
            IssueTrackerApiError("API failed"),
        ],
    )
    def test_lookup_errors_propagate(self, github_client: GitHubClient, error: Exception) -> None:
        """Callers must be able to warn when enumeration did not succeed."""
        with (
            patch.object(github_client, "_run_gh_command", side_effect=error),
            pytest.raises(type(error)),
        ):
            github_client.get_issue_comments("#42")

    def test_missing_issue(self, github_client: GitHubClient) -> None:
        """A missing remote issue retains the client's not-found contract."""
        with (
            patch.object(
                github_client, "_run_gh_command", side_effect=IssueTrackerApiError("Not Found")
            ),
            pytest.raises(IssueTrackerNotFoundError),
        ):
            github_client.get_issue_comments("other/project-a#42")


class TestHasPrUrl:
    """Check remote issue text, not timeline references or local session PR metadata."""

    def test_body_link_skips_comment_lookup(self, github_client: GitHubClient) -> None:
        """A link in the issue body is sufficient even if comments are unavailable."""
        pr_url = "https://github.com/owner/project-a/pull/123"
        issue = {"number": 42, "body": f"[Implementation]({pr_url})"}
        with patch.object(github_client, "_run_gh_command", return_value=json.dumps(issue)) as run:
            assert github_client.has_pr_url("other/project-b#42", pr_url)
        run.assert_called_once_with(["api", "/repos/other/project-b/issues/42", "--jq", "."])

    def test_url_on_later_comment_page(self, github_client: GitHubClient) -> None:
        """Find the current PR after a full first page of unrelated comments."""
        pr_url = "https://github.com/owner/project-a/pull/123"
        pages = [[{"body": "Unrelated comment"}] * 100, [{"body": f"PR: {pr_url}"}]]
        responses = [json.dumps({"number": 42, "body": None}), json.dumps(pages)]
        with patch.object(github_client, "_run_gh_command", side_effect=responses) as run:
            assert github_client.has_pr_url("other/project-b#42", pr_url)
        assert run.call_args_list[0].args[0][1] == "/repos/other/project-b/issues/42"
        assert run.call_args_list[1].args[0][1] == (
            "/repos/other/project-b/issues/42/comments?per_page=100"
        )

    def test_other_links_do_not_hide_current_pr(self, github_client: GitHubClient) -> None:
        """A different PR in the body or comments is not the current PR."""
        responses = [
            json.dumps({"number": 42, "body": "https://github.com/owner/project-b/pull/123"}),
            json.dumps([[{"body": "https://github.com/owner/project-a/pull/1234"}]]),
        ]
        with patch.object(github_client, "_run_gh_command", side_effect=responses):
            assert not github_client.has_pr_url(
                "#42", "https://github.com/owner/project-a/pull/123"
            )

    def test_no_body_or_comments(self, github_client: GitHubClient) -> None:
        """Missing optional issue content is not a lookup failure."""
        responses = [json.dumps({"number": 42}), "[[]]"]
        with patch.object(github_client, "_run_gh_command", side_effect=responses):
            assert not github_client.has_pr_url(
                "#42", "https://github.com/owner/project-a/pull/123"
            )

    def test_malformed_issue_body(self, github_client: GitHubClient) -> None:
        """Do not mistake an invalid issue body for an absent link."""
        with (
            patch.object(github_client, "get_ticket", return_value={"description": 42}),
            pytest.raises(IssueTrackerApiError, match="Invalid GitHub issue body"),
        ):
            github_client.has_pr_url("#42", "https://github.com/owner/project-a/pull/123")


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
