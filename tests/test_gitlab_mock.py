"""Tests for MockGitLabClient."""

import pytest

from devflow.mocks.gitlab_mock import MockGitLabClient
from devflow.mocks.persistence import MockDataStore


@pytest.fixture
def mock_gitlab(temp_daf_home):
    """Provide a clean MockGitLabClient instance."""
    store = MockDataStore()
    store.clear_all()
    return MockGitLabClient()


def test_create_mr(mock_gitlab):
    """Test creating a GitLab merge request."""
    mr = mock_gitlab.create_mr(
        project="group/project",
        title="Test MR",
        description="Test description",
        source_branch="feature-branch",
        target_branch="main"
    )

    assert mr is not None
    assert mr["iid"] == 1
    assert mr["title"] == "Test MR"
    assert mr["description"] == "Test description"
    assert mr["state"] == "opened"
    assert mr["source_branch"] == "feature-branch"
    assert mr["target_branch"] == "main"


def test_get_mr(mock_gitlab):
    """Test getting a merge request."""
    # Create an MR first
    mock_gitlab.create_mr(
        project="group/project",
        title="Test MR",
        description="Description",
        source_branch="feature"
    )

    # Get the MR
    mr = mock_gitlab.get_mr("group/project", 1)

    assert mr is not None
    assert mr["iid"] == 1
    assert mr["title"] == "Test MR"


def test_get_mr_not_found(mock_gitlab):
    """Test getting a non-existent MR."""
    mr = mock_gitlab.get_mr("group/project", 999)
    assert mr is None


def test_list_mrs(mock_gitlab):
    """Test listing merge requests."""
    # Create multiple MRs
    mock_gitlab.create_mr("group/project", "MR 1", "Description", "branch1")
    mock_gitlab.create_mr("group/project", "MR 2", "Description", "branch2")

    # List MRs
    mrs = mock_gitlab.list_mrs("group/project")
    assert len(mrs) == 2


def test_list_mrs_filtered_by_state(mock_gitlab):
    """Test listing MRs filtered by state."""
    # Create MRs
    mock_gitlab.create_mr("group/project", "MR 1", "Description", "branch1")
    mock_gitlab.create_mr("group/project", "MR 2", "Description", "branch2")

    # Close one MR
    mock_gitlab.close_mr("group/project", 1)

    # List only opened MRs
    opened_mrs = mock_gitlab.list_mrs("group/project", state="opened")
    assert len(opened_mrs) == 1
    assert opened_mrs[0]["iid"] == 2

    # List only closed MRs
    closed_mrs = mock_gitlab.list_mrs("group/project", state="closed")
    assert len(closed_mrs) == 1
    assert closed_mrs[0]["iid"] == 1


def test_update_mr(mock_gitlab):
    """Test updating a merge request."""
    # Create an MR
    mock_gitlab.create_mr("group/project", "Original Title", "Description", "branch")

    # Update the MR
    updated_mr = mock_gitlab.update_mr("group/project", 1, title="Updated Title")

    assert updated_mr is not None
    assert updated_mr["title"] == "Updated Title"


def test_update_mr_not_found(mock_gitlab):
    """Test updating a non-existent MR."""
    result = mock_gitlab.update_mr("group/project", 999, title="Should fail")
    assert result is None


def test_merge_mr(mock_gitlab):
    """Test merging a merge request."""
    # Create an MR
    mock_gitlab.create_mr("group/project", "Test MR", "Description", "branch")

    # Merge the MR
    success = mock_gitlab.merge_mr("group/project", 1)
    assert success is True

    # Verify MR is merged
    mr = mock_gitlab.get_mr("group/project", 1)
    assert mr["state"] == "merged"
    assert "merged_at" in mr


def test_merge_mr_not_found(mock_gitlab):
    """Test merging a non-existent MR."""
    success = mock_gitlab.merge_mr("group/project", 999)
    assert success is False


def test_close_mr(mock_gitlab):
    """Test closing a merge request without merging."""
    # Create an MR
    mock_gitlab.create_mr("group/project", "Test MR", "Description", "branch")

    # Close the MR
    success = mock_gitlab.close_mr("group/project", 1)
    assert success is True

    # Verify MR is closed
    mr = mock_gitlab.get_mr("group/project", 1)
    assert mr["state"] == "closed"
    assert "closed_at" in mr


def test_close_mr_not_found(mock_gitlab):
    """Test closing a non-existent MR."""
    success = mock_gitlab.close_mr("group/project", 999)
    assert success is False


def test_add_mr_comment(mock_gitlab):
    """Test adding a comment to an MR."""
    # Create an MR
    mock_gitlab.create_mr("group/project", "Test MR", "Description", "branch")

    # Add comments
    success1 = mock_gitlab.add_mr_comment("group/project", 1, "First comment")
    success2 = mock_gitlab.add_mr_comment("group/project", 1, "Second comment")

    assert success1 is True
    assert success2 is True

    # Verify comments
    mr = mock_gitlab.get_mr("group/project", 1)
    assert "notes" in mr
    assert len(mr["notes"]) == 2


def test_add_mr_comment_not_found(mock_gitlab):
    """Test adding a comment to a non-existent MR."""
    success = mock_gitlab.add_mr_comment("group/project", 999, "Should fail")
    assert success is False


def test_create_draft_mr(mock_gitlab):
    """Test creating a draft merge request."""
    mr = mock_gitlab.create_mr(
        project="group/project",
        title="Feature",
        description="Work in progress",
        source_branch="feature",
        draft=True
    )

    assert mr["draft"] is True
    assert mr["work_in_progress"] is True
    assert mr["title"].startswith("Draft: ")


def test_mark_mr_as_draft(mock_gitlab):
    """Test marking an MR as draft."""
    # Create a regular MR
    mock_gitlab.create_mr("group/project", "Test MR", "Description", "branch")

    # Mark as draft
    success = mock_gitlab.mark_mr_as_draft("group/project", 1)
    assert success is True

    # Verify
    mr = mock_gitlab.get_mr("group/project", 1)
    assert mr["draft"] is True
    assert mr["title"].startswith("Draft: ")


def test_unmark_mr_as_draft(mock_gitlab):
    """Test removing draft status from an MR."""
    # Create a draft MR
    mock_gitlab.create_mr("group/project", "Test", "Description", "branch", draft=True)

    # Unmark as draft
    success = mock_gitlab.unmark_mr_as_draft("group/project", 1)
    assert success is True

    # Verify
    mr = mock_gitlab.get_mr("group/project", 1)
    assert mr["draft"] is False
    assert not mr["title"].startswith("Draft: ")


def test_multiple_projects(mock_gitlab):
    """Test creating MRs in multiple projects."""
    # Create MRs in different projects
    mr1 = mock_gitlab.create_mr("group/project1", "MR in project1", "Description", "branch")
    mr2 = mock_gitlab.create_mr("group/project2", "MR in project2", "Description", "branch")

    assert mr1["iid"] == 1
    assert mr2["iid"] == 1  # Each project has its own numbering

    # Create another MR in project1
    mr3 = mock_gitlab.create_mr("group/project1", "Another MR", "Description", "branch2")
    assert mr3["iid"] == 2
