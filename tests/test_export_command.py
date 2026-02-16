"""Tests for daf export command."""

import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from devflow.cli.commands.export_command import export_sessions, _sync_all_branches_for_export, _sync_single_conversation_branch
from devflow.config.loader import ConfigLoader
from devflow.config.models import ConversationContext, Conversation
from devflow.session.manager import SessionManager


def test_export_sessions_no_args(temp_daf_home, capsys):
    """Test export with no identifiers or --all flag."""
    export_sessions(issue_keys=None, all_sessions=False)

    captured = capsys.readouterr()
    assert "Must specify session identifiers or --all flag" in captured.out


def test_export_sessions_with_single_identifier(temp_daf_home, capsys):
    """Test export with a single session identifier."""
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    # Create a session
    session = session_manager.create_session(
        name="test-session",
        goal="Test export",
        working_directory="dir1",
        project_path="/path/to/project",
        ai_agent_session_id="uuid-1",
        issue_key="PROJ-123",
    )

    with patch('devflow.export.manager.ExportManager.export_sessions') as mock_export:
        # Create a temporary export file
        export_file = temp_daf_home / "export.tar.gz"
        export_file.write_bytes(b"test data")
        mock_export.return_value = export_file

        export_sessions(issue_keys=["PROJ-123"], all_sessions=False, output=None)

        captured = capsys.readouterr()
        assert "Exporting sessions: PROJ-123" in captured.out
        assert "Export created successfully" in captured.out


def test_export_sessions_all_flag(temp_daf_home, capsys):
    """Test export with --all flag."""
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    # Create sessions
    session_manager.create_session(
        name="session-1",
        goal="Test 1",
        working_directory="dir1",
        project_path="/path1",
        ai_agent_session_id="uuid-1",
    )
    session_manager.create_session(
        name="session-2",
        goal="Test 2",
        working_directory="dir2",
        project_path="/path2",
        ai_agent_session_id="uuid-2",
    )

    with patch('devflow.export.manager.ExportManager.export_sessions') as mock_export:
        export_file = temp_daf_home / "all_sessions.tar.gz"
        export_file.write_bytes(b"test data" * 100)
        mock_export.return_value = export_file

        export_sessions(issue_keys=None, all_sessions=True, output=None)

        captured = capsys.readouterr()
        assert "Exporting all sessions" in captured.out
        assert "Export created successfully" in captured.out


def test_export_sessions_with_output_path(temp_daf_home, capsys):
    """Test export with custom output path."""
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    session = session_manager.create_session(
        name="test-session",
        goal="Test export",
        working_directory="dir1",
        project_path="/path/to/project",
        ai_agent_session_id="uuid-1",
    )

    with patch('devflow.export.manager.ExportManager.export_sessions') as mock_export:
        export_file = temp_daf_home / "custom_export.tar.gz"
        export_file.write_bytes(b"test data")
        mock_export.return_value = export_file

        export_sessions(issue_keys=["test-session"], all_sessions=False, output=str(export_file))

        captured = capsys.readouterr()
        assert "Export created successfully" in captured.out
        assert "custom_export.tar.gz" in captured.out


def test_export_sessions_value_error(temp_daf_home, capsys):
    """Test export handles ValueError."""
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    session = session_manager.create_session(
        name="test-session",
        goal="Test export",
        working_directory="dir1",
        project_path="/path/to/project",
        ai_agent_session_id="uuid-1",
    )

    with patch('devflow.export.manager.ExportManager.export_sessions') as mock_export:
        mock_export.side_effect = ValueError("Export validation failed")

        export_sessions(issue_keys=["test-session"], all_sessions=False)

        captured = capsys.readouterr()
        assert "Export failed: Export validation failed" in captured.out


def test_export_sessions_unexpected_error(temp_daf_home):
    """Test export raises unexpected errors."""
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    session = session_manager.create_session(
        name="test-session",
        goal="Test export",
        working_directory="dir1",
        project_path="/path/to/project",
        ai_agent_session_id="uuid-1",
    )

    with patch('devflow.export.manager.ExportManager.export_sessions') as mock_export:
        mock_export.side_effect = RuntimeError("Unexpected failure")

        with pytest.raises(RuntimeError):
            export_sessions(issue_keys=["test-session"], all_sessions=False)


def test_sync_all_branches_multi_conversation(temp_daf_home, capsys):
    """Test syncing branches for multi-conversation session."""
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    session = session_manager.create_session(
        name="multi-session",
        goal="Multi-project work",
        working_directory="dir1",
        project_path="/path1",
        ai_agent_session_id="uuid-1",
    )

    # Add second conversation
    from datetime import datetime
    conv2 = Conversation(
        active_session=ConversationContext(
            ai_agent_session_id="uuid-2",
            project_path="/path2",
            branch="feature-branch",
            base_branch="main",
            created=datetime.now(),
            last_active=datetime.now(),
            message_count=5,
            prs=[],
            archived=False,
            conversation_history=["uuid-2"],
        ),
        archived_sessions=[],
    )
    session.conversations["dir2"] = conv2
    session_manager.update_session(session)

    with patch('devflow.git.utils.GitUtils.is_git_repository', return_value=False):
        _sync_all_branches_for_export(session)

        captured = capsys.readouterr()
        assert "Syncing 2 conversation(s)" in captured.out


def test_sync_all_branches_legacy_single_conversation(temp_daf_home, capsys):
    """Test syncing branches for legacy single-conversation session."""
    from devflow.config.models import Session, ConversationContext, Conversation
    from datetime import datetime

    # Create a legacy session with single conversation in conversations dict
    session = Session(
        name="legacy-session",
        issue_key="PROJ-123",
        goal="Legacy work",
        working_directory="dir1",
        status="in_progress",
        created=datetime.now(),
        last_active=datetime.now(),
    )

    # Add conversation with active_session (current format)
    conv = Conversation(
        active_session=ConversationContext(
            ai_agent_session_id="uuid-1",
            project_path="/path1",
            branch="legacy-branch",
            base_branch="main",
            created=datetime.now(),
            last_active=datetime.now(),
            message_count=5,
            prs=[],
            archived=False,
            conversation_history=["uuid-1"],
        ),
        archived_sessions=[],
    )
    session.conversations = {"dir1": conv}

    with patch('devflow.git.utils.GitUtils.is_git_repository', return_value=False):
        _sync_all_branches_for_export(session)

        captured = capsys.readouterr()
        assert "Syncing 1 conversation" in captured.out


def test_sync_single_conversation_not_git_repo(temp_daf_home, capsys):
    """Test sync skips non-git repositories."""
    with patch('devflow.git.utils.GitUtils.is_git_repository', return_value=False):
        _sync_single_conversation_branch(
            project_path=Path("/path/to/project"),
            branch="feature",
            session_name="test-session",
        )

        captured = capsys.readouterr()
        assert "Not a git repository" in captured.out


def test_sync_single_conversation_checkout_failure(temp_daf_home):
    """Test sync raises ValueError when checkout fails."""
    with patch('devflow.git.utils.GitUtils.is_git_repository', return_value=True):
        with patch('devflow.git.utils.GitUtils.get_current_branch', return_value="main"):
            with patch('devflow.git.utils.GitUtils.checkout_branch', return_value=False):
                with pytest.raises(ValueError, match="Cannot checkout branch"):
                    _sync_single_conversation_branch(
                        project_path=Path("/path/to/project"),
                        branch="feature",
                        session_name="test-session",
                    )


def test_sync_single_conversation_merge_conflict(temp_daf_home):
    """Test sync raises ValueError on merge conflicts."""
    with patch('devflow.git.utils.GitUtils.is_git_repository', return_value=True):
        with patch('devflow.git.utils.GitUtils.get_current_branch', return_value="feature"):
            with patch('devflow.git.utils.GitUtils.fetch_origin'):
                with patch('devflow.git.utils.GitUtils.is_branch_pushed', return_value=True):
                    with patch('devflow.git.utils.GitUtils.pull_current_branch', return_value=False):
                        with patch('devflow.git.utils.GitUtils.has_merge_conflicts', return_value=True):
                            with patch('devflow.git.utils.GitUtils.get_conflicted_files', return_value=["file1.py", "file2.py"]):
                                with pytest.raises(ValueError, match="Merge conflicts"):
                                    _sync_single_conversation_branch(
                                        project_path=Path("/path/to/project"),
                                        branch="feature",
                                        session_name="test-session",
                                    )


def test_sync_single_conversation_commit_failure(temp_daf_home):
    """Test sync raises ValueError when commit fails."""
    with patch('devflow.git.utils.GitUtils.is_git_repository', return_value=True):
        with patch('devflow.git.utils.GitUtils.get_current_branch', return_value="feature"):
            with patch('devflow.git.utils.GitUtils.fetch_origin'):
                with patch('devflow.git.utils.GitUtils.has_uncommitted_changes', return_value=True):
                    with patch('devflow.git.utils.GitUtils.get_status_summary', return_value="M file.py"):
                        with patch('devflow.git.utils.GitUtils.commit_all', return_value=False):
                            with pytest.raises(ValueError, match="Failed to commit changes"):
                                _sync_single_conversation_branch(
                                    project_path=Path("/path/to/project"),
                                    branch="feature",
                                    session_name="test-session",
                                )


def test_sync_single_conversation_push_failure_new_branch(temp_daf_home):
    """Test sync raises ValueError when push fails for new branch."""
    with patch('devflow.git.utils.GitUtils.is_git_repository', return_value=True):
        with patch('devflow.git.utils.GitUtils.get_current_branch', return_value="feature"):
            with patch('devflow.git.utils.GitUtils.fetch_origin'):
                with patch('devflow.git.utils.GitUtils.has_uncommitted_changes', return_value=False):
                    with patch('devflow.git.utils.GitUtils.is_branch_pushed', return_value=False):
                        with patch('devflow.git.utils.GitUtils.push_branch', return_value=False):
                            with pytest.raises(ValueError, match="Failed to push branch"):
                                _sync_single_conversation_branch(
                                    project_path=Path("/path/to/project"),
                                    branch="feature",
                                    session_name="test-session",
                                )


def test_sync_single_conversation_push_failure_existing_branch(temp_daf_home):
    """Test sync raises ValueError when push fails for existing branch."""
    with patch('devflow.git.utils.GitUtils.is_git_repository', return_value=True):
        with patch('devflow.git.utils.GitUtils.get_current_branch', return_value="feature"):
            with patch('devflow.git.utils.GitUtils.fetch_origin'):
                with patch('devflow.git.utils.GitUtils.has_uncommitted_changes', return_value=False):
                    with patch('devflow.git.utils.GitUtils.is_branch_pushed', return_value=True):
                        with patch('devflow.git.utils.GitUtils.pull_current_branch', return_value=True):
                            with patch('devflow.git.utils.GitUtils.push_branch', return_value=False):
                                with pytest.raises(ValueError, match="Failed to push to remote"):
                                    _sync_single_conversation_branch(
                                        project_path=Path("/path/to/project"),
                                        branch="feature",
                                        session_name="test-session",
                                    )


def test_sync_single_conversation_captures_remote_url(temp_daf_home):
    """Test sync captures remote URL for fork support."""
    mock_conversation = MagicMock()

    with patch('devflow.git.utils.GitUtils.is_git_repository', return_value=True):
        with patch('devflow.git.utils.GitUtils.get_current_branch', return_value="feature"):
            with patch('devflow.git.utils.GitUtils.fetch_origin'):
                with patch('devflow.git.utils.GitUtils.has_uncommitted_changes', return_value=False):
                    with patch('devflow.git.utils.GitUtils.is_branch_pushed', return_value=True):
                        with patch('devflow.git.utils.GitUtils.pull_current_branch', return_value=True):
                            with patch('devflow.git.utils.GitUtils.push_branch', return_value=True):
                                with patch('devflow.git.utils.GitUtils.get_branch_remote_url', return_value="https://github.com/user/repo.git"):
                                    _sync_single_conversation_branch(
                                        project_path=Path("/path/to/project"),
                                        branch="feature",
                                        session_name="test-session",
                                        conversation=mock_conversation,
                                    )

                                    assert mock_conversation.remote_url == "https://github.com/user/repo.git"
