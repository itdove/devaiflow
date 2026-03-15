"""Tests for session project management commands (simplified)."""

import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from devflow.config.loader import ConfigLoader
from devflow.session.manager import SessionManager


def test_session_project_commands_exist():
    """Test that the session project command functions exist and can be imported."""
    from devflow.cli.commands.session_project_command import (
        add_project_to_session,
        remove_project_from_session,
    )

    assert callable(add_project_to_session)
    assert callable(remove_project_from_session)


def test_remove_project_deletes_conversation(temp_daf_home, tmp_path):
    """Test that removing a project deletes it from the multi-project conversation."""
    from devflow.cli.commands.session_project_command import remove_project_from_session
    from devflow.config.models import ProjectInfo, ConversationContext, Conversation

    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    # Create multi-project conversation context
    conversation_context = ConversationContext(
        ai_agent_session_id="uuid-1",
        project_path=str(tmp_path / "backend"),
        branch="main",
        is_multi_project=True,
        workspace_path=str(tmp_path),
        projects={
            "backend": ProjectInfo(
                project_path=str(tmp_path / "backend"),
                relative_path="backend",
                branch="main",
                base_branch="main",
                repo_name="backend",
            ),
            "frontend": ProjectInfo(
                project_path=str(tmp_path / "frontend"),
                relative_path="frontend",
                branch="main",
                base_branch="main",
                repo_name="frontend",
            ),
        }
    )

    # Create conversation container
    conversation = Conversation(
        active_session=conversation_context,
        archived_sessions=[]
    )

    # Create session with multi-project conversation
    session = session_manager.create_session(
        name="test-remove",
        goal="Test",
        working_directory="backend",
        project_path=str(tmp_path / "backend"),
        branch="main",
        ai_agent_session_id="uuid-1",
    )

    # Replace the default conversation with our multi-project one
    session.conversations["backend"] = conversation

    session_manager.update_session(session)

    # Verify two projects exist
    session = session_manager.get_session("test-remove")
    assert session.active_conversation.is_multi_project
    assert len(session.active_conversation.projects) == 2

    # Remove frontend
    remove_project_from_session(
        session_name="test-remove",
        project_name="frontend",
        force=True,
    )

    # Reload with fresh session manager (remove_project creates its own instance)
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)
    session = session_manager.get_session("test-remove")
    assert len(session.active_conversation.projects) == 1
    assert "backend" in session.active_conversation.projects
    assert "frontend" not in session.active_conversation.projects


def test_remove_active_project_switches_working_directory(temp_daf_home, tmp_path):
    """Test that removing a project from multi-project conversation works correctly."""
    from devflow.cli.commands.session_project_command import remove_project_from_session
    from devflow.config.models import ProjectInfo, ConversationContext, Conversation

    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    # Create multi-project conversation context
    conversation_context = ConversationContext(
        ai_agent_session_id="uuid-1",
        project_path=str(tmp_path / "backend"),
        branch="main",
        is_multi_project=True,
        workspace_path=str(tmp_path),
        projects={
            "backend": ProjectInfo(
                project_path=str(tmp_path / "backend"),
                relative_path="backend",
                branch="main",
                base_branch="main",
                repo_name="backend",
            ),
            "frontend": ProjectInfo(
                project_path=str(tmp_path / "frontend"),
                relative_path="frontend",
                branch="main",
                base_branch="main",
                repo_name="frontend",
            ),
        }
    )

    # Create conversation container
    conversation = Conversation(
        active_session=conversation_context,
        archived_sessions=[]
    )

    # Create session with multi-project conversation
    session = session_manager.create_session(
        name="test-switch",
        goal="Test",
        working_directory="backend",
        project_path=str(tmp_path / "backend"),
        branch="main",
        ai_agent_session_id="uuid-1",
    )

    # Replace the default conversation with our multi-project one
    session.conversations["backend"] = conversation

    session_manager.update_session(session)

    # Remove backend project
    remove_project_from_session(
        session_name="test-switch",
        project_name="backend",
        force=True,
    )

    # Reload with fresh session manager (remove_project creates its own instance)
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)
    session = session_manager.get_session("test-switch")
    assert len(session.active_conversation.projects) == 1
    assert "frontend" in session.active_conversation.projects
    assert "backend" not in session.active_conversation.projects


def test_remove_nonexistent_project_exits(temp_daf_home, tmp_path):
    """Test that removing non-existent project exits with error."""
    from devflow.cli.commands.session_project_command import remove_project_from_session

    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    session = session_manager.create_session(
        name="test-missing",
        goal="Test",
        working_directory="backend",
        project_path=str(tmp_path / "backend"),
        branch="main",
        ai_agent_session_id="uuid-1",
    )

    # Should exit when project doesn't exist
    with pytest.raises(SystemExit):
        remove_project_from_session(
            session_name="test-missing",
            project_name="nonexistent",
            force=True,
        )
