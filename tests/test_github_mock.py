"""Tests for MockGitHubClient."""

import pytest

from devflow.mocks.github_mock import MockGitHubClient
from devflow.mocks.persistence import MockDataStore


@pytest.fixture
def mock_github(temp_daf_home):
    """Provide a clean MockGitHubClient instance."""
    store = MockDataStore()
    store.clear_all()
    return MockGitHubClient()


def test_create_pr(mock_github):
    """Test creating a GitHub pull request."""
    pr = mock_github.create_pr(
        repo="owner/repo",
        title="Test PR",
        body="Test description",
        head="feature-branch",
        base="main"
    )

    assert pr is not None
    assert pr["number"] == 1
    assert pr["title"] == "Test PR"
    assert pr["body"] == "Test description"
    assert pr["state"] == "open"
    assert pr["head"]["ref"] == "feature-branch"
    assert pr["base"]["ref"] == "main"
    assert "html_url" in pr


def test_get_pr(mock_github):
    """Test getting a pull request."""
    # Create a PR first
    mock_github.create_pr(
        repo="owner/repo",
        title="Test PR",
        body="Description",
        head="feature"
    )

    # Get the PR
    pr = mock_github.get_pr("owner/repo", 1)

    assert pr is not None
    assert pr["number"] == 1
    assert pr["title"] == "Test PR"


def test_get_pr_not_found(mock_github):
    """Test getting a non-existent PR."""
    pr = mock_github.get_pr("owner/repo", 999)
    assert pr is None


def test_list_prs(mock_github):
    """Test listing pull requests."""
    # Create multiple PRs
    mock_github.create_pr("owner/repo", "PR 1", "Description", "branch1")
    mock_github.create_pr("owner/repo", "PR 2", "Description", "branch2")

    # List PRs
    prs = mock_github.list_prs("owner/repo")
    assert len(prs) == 2


def test_list_prs_filtered_by_state(mock_github):
    """Test listing PRs filtered by state."""
    # Create PRs
    mock_github.create_pr("owner/repo", "PR 1", "Description", "branch1")
    mock_github.create_pr("owner/repo", "PR 2", "Description", "branch2")

    # Close one PR
    mock_github.close_pr("owner/repo", 1)

    # List only open PRs
    open_prs = mock_github.list_prs("owner/repo", state="open")
    assert len(open_prs) == 1
    assert open_prs[0]["number"] == 2

    # List only closed PRs
    closed_prs = mock_github.list_prs("owner/repo", state="closed")
    assert len(closed_prs) == 1
    assert closed_prs[0]["number"] == 1


def test_update_pr(mock_github):
    """Test updating a pull request."""
    # Create a PR
    mock_github.create_pr("owner/repo", "Original Title", "Description", "branch")

    # Update the PR
    updated_pr = mock_github.update_pr("owner/repo", 1, title="Updated Title")

    assert updated_pr is not None
    assert updated_pr["title"] == "Updated Title"


def test_update_pr_not_found(mock_github):
    """Test updating a non-existent PR."""
    result = mock_github.update_pr("owner/repo", 999, title="Should fail")
    assert result is None


def test_merge_pr(mock_github):
    """Test merging a pull request."""
    # Create a PR
    mock_github.create_pr("owner/repo", "Test PR", "Description", "branch")

    # Merge the PR
    success = mock_github.merge_pr("owner/repo", 1)
    assert success is True

    # Verify PR is merged
    pr = mock_github.get_pr("owner/repo", 1)
    assert pr["state"] == "closed"
    assert pr["merged"] is True
    assert "merged_at" in pr


def test_merge_pr_not_found(mock_github):
    """Test merging a non-existent PR."""
    success = mock_github.merge_pr("owner/repo", 999)
    assert success is False


def test_close_pr(mock_github):
    """Test closing a pull request without merging."""
    # Create a PR
    mock_github.create_pr("owner/repo", "Test PR", "Description", "branch")

    # Close the PR
    success = mock_github.close_pr("owner/repo", 1)
    assert success is True

    # Verify PR is closed but not merged
    pr = mock_github.get_pr("owner/repo", 1)
    assert pr["state"] == "closed"
    assert pr["merged"] is False


def test_close_pr_not_found(mock_github):
    """Test closing a non-existent PR."""
    success = mock_github.close_pr("owner/repo", 999)
    assert success is False


def test_add_pr_comment(mock_github):
    """Test adding a comment to a PR."""
    # Create a PR
    mock_github.create_pr("owner/repo", "Test PR", "Description", "branch")

    # Add comments
    success1 = mock_github.add_pr_comment("owner/repo", 1, "First comment")
    success2 = mock_github.add_pr_comment("owner/repo", 1, "Second comment")

    assert success1 is True
    assert success2 is True

    # Verify comments
    pr = mock_github.get_pr("owner/repo", 1)
    assert "comments" in pr
    assert len(pr["comments"]) == 2


def test_add_pr_comment_not_found(mock_github):
    """Test adding a comment to a non-existent PR."""
    success = mock_github.add_pr_comment("owner/repo", 999, "Should fail")
    assert success is False


def test_create_draft_pr(mock_github):
    """Test creating a draft pull request."""
    pr = mock_github.create_pr(
        repo="owner/repo",
        title="Draft PR",
        body="Work in progress",
        head="feature",
        draft=True
    )

    assert pr["draft"] is True


def test_multiple_repos(mock_github):
    """Test creating PRs in multiple repositories."""
    # Create PRs in different repos
    pr1 = mock_github.create_pr("owner/repo1", "PR in repo1", "Description", "branch")
    pr2 = mock_github.create_pr("owner/repo2", "PR in repo2", "Description", "branch")

    assert pr1["number"] == 1
    assert pr2["number"] == 1  # Each repo has its own numbering

    # Create another PR in repo1
    pr3 = mock_github.create_pr("owner/repo1", "Another PR", "Description", "branch2")
    assert pr3["number"] == 2
