"""Tests for daf export command branch sync functionality (PROJ-60772)."""

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, call, patch

import pytest

from devflow.cli.commands.export_command import (
    _sync_all_branches_for_export,
    _sync_single_conversation_branch,
)
from devflow.config.models import Conversation, ConversationContext, Session


@pytest.fixture
def mock_git_utils():
    """Mock GitUtils methods."""
    with patch("devflow.cli.commands.export_command.GitUtils") as mock:
        yield mock


def test_sync_skips_non_git_repository(mock_git_utils, tmp_path):
    """Test that sync skips non-git repositories."""
    mock_git_utils.is_git_repository.return_value = False

    # Should not raise and should return early
    _sync_single_conversation_branch(
        project_path=tmp_path,
        branch="feature/test",
        session_name="test-session",
    )

    mock_git_utils.is_git_repository.assert_called_once()
    # No other git operations should be called
    mock_git_utils.get_current_branch.assert_not_called()


def test_sync_checks_out_session_branch(mock_git_utils, tmp_path):
    """Test that sync checks out session branch if not already on it."""
    mock_git_utils.is_git_repository.return_value = True
    mock_git_utils.get_current_branch.return_value = "main"
    mock_git_utils.checkout_branch.return_value = True
    mock_git_utils.fetch_origin.return_value = True
    mock_git_utils.is_branch_pushed.return_value = False
    mock_git_utils.has_uncommitted_changes.return_value = False

    _sync_single_conversation_branch(
        project_path=tmp_path,
        branch="feature/test",
        session_name="test-session",
    )

    mock_git_utils.checkout_branch.assert_called_once_with(tmp_path, "feature/test")


def test_sync_raises_error_on_checkout_failure(mock_git_utils, tmp_path):
    """Test that sync raises ValueError if checkout fails."""
    mock_git_utils.is_git_repository.return_value = True
    mock_git_utils.get_current_branch.return_value = "main"
    mock_git_utils.checkout_branch.return_value = False

    with pytest.raises(ValueError, match="Cannot checkout branch 'feature/test'"):
        _sync_single_conversation_branch(
            project_path=tmp_path,
            branch="feature/test",
            session_name="test-session",
        )


def test_sync_fetches_from_origin(mock_git_utils, tmp_path):
    """Test that sync fetches from origin."""
    mock_git_utils.is_git_repository.return_value = True
    mock_git_utils.get_current_branch.return_value = "feature/test"
    mock_git_utils.fetch_origin.return_value = True
    mock_git_utils.is_branch_pushed.return_value = False
    mock_git_utils.has_uncommitted_changes.return_value = False

    _sync_single_conversation_branch(
        project_path=tmp_path,
        branch="feature/test",
        session_name="test-session",
    )

    mock_git_utils.fetch_origin.assert_called_once_with(tmp_path)


def test_sync_pulls_latest_changes_if_branch_pushed(mock_git_utils, tmp_path):
    """Test that sync pulls latest changes if branch exists on remote."""
    mock_git_utils.is_git_repository.return_value = True
    mock_git_utils.get_current_branch.return_value = "feature/test"
    mock_git_utils.fetch_origin.return_value = True
    mock_git_utils.is_branch_pushed.return_value = True
    mock_git_utils.pull_current_branch.return_value = True
    mock_git_utils.has_uncommitted_changes.return_value = False

    _sync_single_conversation_branch(
        project_path=tmp_path,
        branch="feature/test",
        session_name="test-session",
    )

    mock_git_utils.pull_current_branch.assert_called_once_with(tmp_path)


def test_sync_raises_error_on_merge_conflicts(mock_git_utils, tmp_path):
    """Test that sync raises ValueError if pull results in merge conflicts."""
    mock_git_utils.is_git_repository.return_value = True
    mock_git_utils.get_current_branch.return_value = "feature/test"
    mock_git_utils.fetch_origin.return_value = True
    mock_git_utils.is_branch_pushed.return_value = True
    mock_git_utils.pull_current_branch.return_value = False
    mock_git_utils.has_merge_conflicts.return_value = True
    mock_git_utils.get_conflicted_files.return_value = ["file1.py", "file2.py"]

    with pytest.raises(ValueError, match=r"Merge conflicts[\s\S]*file1\.py, file2\.py"):
        _sync_single_conversation_branch(
            project_path=tmp_path,
            branch="feature/test",
            session_name="test-session",
        )


def test_sync_commits_uncommitted_changes_required(mock_git_utils, tmp_path):
    """Test that sync commits uncommitted changes without prompting (REQUIRED)."""
    mock_git_utils.is_git_repository.return_value = True
    mock_git_utils.get_current_branch.return_value = "feature/test"
    mock_git_utils.fetch_origin.return_value = True
    mock_git_utils.is_branch_pushed.return_value = False
    mock_git_utils.has_uncommitted_changes.return_value = True
    mock_git_utils.get_status_summary.return_value = "M file1.py\nA file2.py"
    mock_git_utils.commit_all.return_value = True
    mock_git_utils.push_branch.return_value = True

    _sync_single_conversation_branch(
        project_path=tmp_path,
        branch="feature/test",
        session_name="test-session",
        issue_key="PROJ-12345",
    )

    # Verify commit was called without any prompting
    mock_git_utils.commit_all.assert_called_once()
    call_args = mock_git_utils.commit_all.call_args
    assert call_args[0][0] == tmp_path
    assert "WIP: Export for PROJ-12345" in call_args[0][1]
    assert "Co-Authored-By: Claude" in call_args[0][1]


def test_sync_raises_error_on_commit_failure(mock_git_utils, tmp_path):
    """Test that sync raises ValueError if commit fails (REQUIRED operation)."""
    mock_git_utils.is_git_repository.return_value = True
    mock_git_utils.get_current_branch.return_value = "feature/test"
    mock_git_utils.fetch_origin.return_value = True
    mock_git_utils.is_branch_pushed.return_value = False
    mock_git_utils.has_uncommitted_changes.return_value = True
    mock_git_utils.get_status_summary.return_value = "M file1.py"
    mock_git_utils.commit_all.return_value = False

    with pytest.raises(ValueError, match=r"Failed to commit changes[\s\S]*Cannot export without committing"):
        _sync_single_conversation_branch(
            project_path=tmp_path,
            branch="feature/test",
            session_name="test-session",
        )


def test_sync_pushes_unpushed_branch_required(mock_git_utils, tmp_path):
    """Test that sync pushes unpushed branch without prompting (REQUIRED)."""
    mock_git_utils.is_git_repository.return_value = True
    mock_git_utils.get_current_branch.return_value = "feature/test"
    mock_git_utils.fetch_origin.return_value = True
    mock_git_utils.is_branch_pushed.return_value = False
    mock_git_utils.has_uncommitted_changes.return_value = False
    mock_git_utils.push_branch.return_value = True

    _sync_single_conversation_branch(
        project_path=tmp_path,
        branch="feature/test",
        session_name="test-session",
    )

    # Verify push was called without any prompting
    mock_git_utils.push_branch.assert_called_once_with(tmp_path, "feature/test")


def test_sync_raises_error_on_push_failure_unpushed_branch(mock_git_utils, tmp_path):
    """Test that sync raises ValueError if push fails for unpushed branch."""
    mock_git_utils.is_git_repository.return_value = True
    mock_git_utils.get_current_branch.return_value = "feature/test"
    mock_git_utils.fetch_origin.return_value = True
    mock_git_utils.is_branch_pushed.return_value = False
    mock_git_utils.has_uncommitted_changes.return_value = False
    mock_git_utils.push_branch.return_value = False

    with pytest.raises(ValueError, match=r"Failed to push branch[\s\S]*Teammate needs branch on remote"):
        _sync_single_conversation_branch(
            project_path=tmp_path,
            branch="feature/test",
            session_name="test-session",
        )


def test_sync_pushes_existing_branch_required(mock_git_utils, tmp_path):
    """Test that sync pushes existing branch without prompting (REQUIRED)."""
    mock_git_utils.is_git_repository.return_value = True
    mock_git_utils.get_current_branch.return_value = "feature/test"
    mock_git_utils.fetch_origin.return_value = True
    mock_git_utils.is_branch_pushed.return_value = True
    mock_git_utils.pull_current_branch.return_value = True
    mock_git_utils.has_uncommitted_changes.return_value = False
    mock_git_utils.push_branch.return_value = True

    _sync_single_conversation_branch(
        project_path=tmp_path,
        branch="feature/test",
        session_name="test-session",
    )

    # Verify push was called without any prompting
    mock_git_utils.push_branch.assert_called_once_with(tmp_path, "feature/test")


def test_sync_raises_error_on_push_failure_existing_branch(mock_git_utils, tmp_path):
    """Test that sync raises ValueError if push fails for existing branch."""
    mock_git_utils.is_git_repository.return_value = True
    mock_git_utils.get_current_branch.return_value = "feature/test"
    mock_git_utils.fetch_origin.return_value = True
    mock_git_utils.is_branch_pushed.return_value = True
    mock_git_utils.pull_current_branch.return_value = True
    mock_git_utils.has_uncommitted_changes.return_value = False
    mock_git_utils.push_branch.return_value = False

    with pytest.raises(ValueError, match=r"Failed to push to remote[\s\S]*Teammate may not have latest"):
        _sync_single_conversation_branch(
            project_path=tmp_path,
            branch="feature/test",
            session_name="test-session",
        )


def test_sync_captures_remote_url(mock_git_utils, tmp_path):
    """Test that sync captures remote URL for fork support."""
    mock_git_utils.is_git_repository.return_value = True
    mock_git_utils.get_current_branch.return_value = "feature/test"
    mock_git_utils.fetch_origin.return_value = True
    mock_git_utils.is_branch_pushed.return_value = False
    mock_git_utils.has_uncommitted_changes.return_value = False
    mock_git_utils.push_branch.return_value = True
    mock_git_utils.get_branch_remote_url.return_value = "git@github.com:user/repo.git"

    conversation = MagicMock()
    _sync_single_conversation_branch(
        project_path=tmp_path,
        branch="feature/test",
        session_name="test-session",
        conversation=conversation,
    )

    mock_git_utils.get_branch_remote_url.assert_called_once_with(tmp_path, "feature/test")
    assert conversation.remote_url == "git@github.com:user/repo.git"


def test_sync_complete_workflow_with_checkout_pull_commit_push(mock_git_utils, tmp_path):
    """Test complete sync workflow: checkout -> fetch -> pull -> commit -> push."""
    mock_git_utils.is_git_repository.return_value = True
    mock_git_utils.get_current_branch.return_value = "main"  # Different branch
    mock_git_utils.checkout_branch.return_value = True
    mock_git_utils.fetch_origin.return_value = True
    mock_git_utils.is_branch_pushed.return_value = True
    mock_git_utils.pull_current_branch.return_value = True
    mock_git_utils.has_uncommitted_changes.return_value = True
    mock_git_utils.get_status_summary.return_value = "M file1.py"
    mock_git_utils.commit_all.return_value = True
    mock_git_utils.push_branch.return_value = True
    mock_git_utils.get_branch_remote_url.return_value = "git@github.com:user/repo.git"

    conversation = MagicMock()
    _sync_single_conversation_branch(
        project_path=tmp_path,
        branch="feature/test",
        session_name="test-session",
        issue_key="PROJ-12345",
        working_dir_name="repo1",
        conversation=conversation,
    )

    # Verify all steps were executed in order
    assert mock_git_utils.get_current_branch.called
    assert mock_git_utils.checkout_branch.called
    assert mock_git_utils.fetch_origin.called
    assert mock_git_utils.pull_current_branch.called
    assert mock_git_utils.commit_all.called
    assert mock_git_utils.push_branch.called
    assert mock_git_utils.get_branch_remote_url.called
    assert conversation.remote_url == "git@github.com:user/repo.git"


def test_sync_multi_conversation_uses_working_dir_name(mock_git_utils, tmp_path):
    """Test that working_dir_name is used in error messages for multi-conversation sessions."""
    mock_git_utils.is_git_repository.return_value = True
    mock_git_utils.get_current_branch.return_value = "main"
    mock_git_utils.checkout_branch.return_value = False

    with pytest.raises(ValueError, match="Cannot checkout branch 'feature/test' in repo1"):
        _sync_single_conversation_branch(
            project_path=tmp_path,
            branch="feature/test",
            session_name="test-session",
            working_dir_name="repo1",
        )


def test_sync_uses_session_name_when_no_issue_key(mock_git_utils, tmp_path):
    """Test that commit message uses session name when issue key is not provided."""
    mock_git_utils.is_git_repository.return_value = True
    mock_git_utils.get_current_branch.return_value = "feature/test"
    mock_git_utils.fetch_origin.return_value = True
    mock_git_utils.is_branch_pushed.return_value = False
    mock_git_utils.has_uncommitted_changes.return_value = True
    mock_git_utils.get_status_summary.return_value = "M file1.py"
    mock_git_utils.commit_all.return_value = True
    mock_git_utils.push_branch.return_value = True

    _sync_single_conversation_branch(
        project_path=tmp_path,
        branch="feature/test",
        session_name="my-session",
    )

    call_args = mock_git_utils.commit_all.call_args
    assert "WIP: Export for my-session" in call_args[0][1]


def test_sync_all_branches_with_conversation_class(mock_git_utils, tmp_path, temp_daf_home):
    """Test _sync_all_branches_for_export correctly accesses active_session from Conversation objects.
    
    This test ensures the bug found in collaboration workflow is caught:
    Previously tried to access conversation.project_path directly,
    but conversation is now a Conversation object, must access conversation.active_session.project_path
    """
    # Create a session with Conversation objects (new format)
    from datetime import datetime
    
    conversation_ctx = ConversationContext(
        ai_agent_session_id="uuid-123",
        project_path=str(tmp_path),
        branch="feature/test",
        base_branch="main",
        created=datetime.now(),
        last_active=datetime.now(),
    )
    
    conversation = Conversation(
        active_session=conversation_ctx,
        archived_sessions=[]
    )
    
    session = Session(
        name="test-session",
        goal="Test goal",
        working_directory="test-repo",
        status="in_progress",
        created=datetime.now(),
        last_active=datetime.now(),
        conversations={"test-repo": conversation},
        issue_key="PROJ-123"
    )
    
    # Mock GitUtils
    mock_git_utils.is_git_repository.return_value = True
    mock_git_utils.get_current_branch.return_value = "feature/test"
    mock_git_utils.fetch_origin.return_value = True
    mock_git_utils.is_branch_pushed.return_value = False
    mock_git_utils.has_uncommitted_changes.return_value = False
    mock_git_utils.push_branch.return_value = True
    mock_git_utils.get_branch_remote_url.return_value = "git@github.com:user/repo.git"
    
    # This should NOT raise AttributeError about 'Conversation' object has no attribute 'project_path'
    _sync_all_branches_for_export(session)
    
    # Verify it correctly accessed active_session fields
    assert mock_git_utils.is_git_repository.called
    assert mock_git_utils.get_current_branch.called
    assert mock_git_utils.push_branch.called
    
    # Verify remote URL was captured on the active session
    assert conversation.active_session.remote_url == "git@github.com:user/repo.git"
