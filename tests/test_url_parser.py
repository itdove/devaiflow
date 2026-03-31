"""Tests for URL parser utility."""

import pytest
from devflow.utils.url_parser import parse_issue_url, parse_issue_identifier, get_hostname_from_url


class TestParseIssueIdentifier:
    """Tests for parse_issue_identifier function (handles both URLs and short formats)."""

    def test_full_github_url(self):
        """Test parsing full GitHub URL."""
        identifier = "https://github.com/itdove/devaiflow/issues/305"
        result = parse_issue_identifier(identifier)

        assert result is not None
        backend, repository, issue_id = result
        assert backend == 'github'
        assert repository == 'itdove/devaiflow'
        assert issue_id == '305'

    def test_github_short_format(self):
        """Test parsing GitHub short format (owner/repo#123)."""
        identifier = "itdove/devaiflow#305"
        result = parse_issue_identifier(identifier)

        assert result is not None
        backend, repository, issue_id = result
        assert backend == 'github'
        assert repository == 'itdove/devaiflow'
        assert issue_id == '305'

    def test_gitlab_short_format(self):
        """Test parsing GitLab short format (group/project#42)."""
        identifier = "group/project#42"
        result = parse_issue_identifier(identifier)

        assert result is not None
        backend, repository, issue_id = result
        assert backend == 'github'  # Defaults to github for short format
        assert repository == 'group/project'
        assert issue_id == '42'

    def test_jira_key_format(self):
        """Test parsing JIRA key format (AAP-123)."""
        identifier = "AAP-70183"
        result = parse_issue_identifier(identifier)

        assert result is not None
        backend, repository, issue_id = result
        assert backend == 'jira'
        assert repository == ''
        assert issue_id == 'AAP-70183'

    def test_full_jira_url(self):
        """Test parsing full JIRA URL."""
        identifier = "https://redhat.atlassian.net/browse/AAP-70183"
        result = parse_issue_identifier(identifier)

        assert result is not None
        backend, repository, issue_id = result
        assert backend == 'jira'
        assert repository == 'https://redhat.atlassian.net'
        assert issue_id == 'AAP-70183'

    def test_invalid_format(self):
        """Test parsing invalid format returns None."""
        identifier = "invalid-format"
        result = parse_issue_identifier(identifier)

        assert result is None

    def test_empty_string(self):
        """Test parsing empty string returns None."""
        result = parse_issue_identifier("")

        assert result is None


class TestParseIssueUrl:
    """Tests for parse_issue_url function."""

    def test_github_url(self):
        """Test parsing GitHub issue URL."""
        url = "https://github.com/itdove/devaiflow/issues/305"
        result = parse_issue_url(url)

        assert result is not None
        backend, repository, issue_id = result
        assert backend == 'github'
        assert repository == 'itdove/devaiflow'
        assert issue_id == '305'

    def test_gitlab_url(self):
        """Test parsing GitLab issue URL."""
        url = "https://gitlab.com/group/project/-/issues/42"
        result = parse_issue_url(url)

        assert result is not None
        backend, repository, issue_id = result
        assert backend == 'gitlab'
        assert repository == 'group/project'
        assert issue_id == '42'

    def test_gitlab_enterprise_url(self):
        """Test parsing GitLab enterprise instance URL."""
        url = "https://gitlab.cee.redhat.com/group/subgroup/project/-/issues/123"
        result = parse_issue_url(url)

        assert result is not None
        backend, repository, issue_id = result
        assert backend == 'gitlab'
        assert repository == 'group/subgroup/project'
        assert issue_id == '123'

    def test_jira_atlassian_url(self):
        """Test parsing JIRA Atlassian URL."""
        url = "https://redhat.atlassian.net/browse/AAP-70183"
        result = parse_issue_url(url)

        assert result is not None
        backend, repository, issue_id = result
        assert backend == 'jira'
        assert repository == 'https://redhat.atlassian.net'
        assert issue_id == 'AAP-70183'

    def test_jira_custom_domain_url(self):
        """Test parsing JIRA custom domain URL."""
        url = "https://jira.company.com/browse/PROJ-456"
        result = parse_issue_url(url)

        assert result is not None
        backend, repository, issue_id = result
        assert backend == 'jira'
        assert repository == 'https://jira.company.com'
        assert issue_id == 'PROJ-456'

    def test_invalid_url(self):
        """Test parsing invalid URL returns None."""
        url = "https://example.com/invalid/path"
        result = parse_issue_url(url)

        assert result is None

    def test_empty_string(self):
        """Test parsing empty string returns None."""
        result = parse_issue_url("")

        assert result is None

    def test_none_input(self):
        """Test parsing None returns None."""
        result = parse_issue_url(None)

        assert result is None

    def test_github_pr_url_not_supported(self):
        """Test GitHub PR URL is not recognized (only issues)."""
        url = "https://github.com/owner/repo/pull/123"
        result = parse_issue_url(url)

        assert result is None

    def test_gitlab_mr_url_not_supported(self):
        """Test GitLab MR URL is not recognized (only issues)."""
        url = "https://gitlab.com/group/project/-/merge_requests/123"
        result = parse_issue_url(url)

        assert result is None


class TestGetHostnameFromUrl:
    """Tests for get_hostname_from_url function."""

    def test_github_hostname(self):
        """Test extracting hostname from GitHub URL."""
        url = "https://github.com/owner/repo/issues/123"
        hostname = get_hostname_from_url(url)

        assert hostname == 'github.com'

    def test_gitlab_enterprise_hostname(self):
        """Test extracting hostname from GitLab enterprise URL."""
        url = "https://gitlab.cee.redhat.com/group/project/-/issues/123"
        hostname = get_hostname_from_url(url)

        assert hostname == 'gitlab.cee.redhat.com'

    def test_jira_hostname(self):
        """Test extracting hostname from JIRA URL."""
        url = "https://redhat.atlassian.net/browse/AAP-123"
        hostname = get_hostname_from_url(url)

        assert hostname == 'redhat.atlassian.net'

    def test_empty_string(self):
        """Test extracting hostname from empty string returns None."""
        hostname = get_hostname_from_url("")

        assert hostname is None

    def test_none_input(self):
        """Test extracting hostname from None returns None."""
        hostname = get_hostname_from_url(None)

        assert hostname is None
