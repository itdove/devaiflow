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
    """Test that removing a project deletes the conversation."""
    from devflow.cli.commands.session_project_command import remove_project_from_session

    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    # Create session with two projects
    session = session_manager.create_session(
        name="test-remove",
        goal="Test",
        working_directory="backend",
        project_path=str(tmp_path / "backend"),
        branch="main",
        ai_agent_session_id="uuid-1",
    )

    session.add_conversation(
        working_dir="frontend",
        ai_agent_session_id="uuid-2",
        project_path=str(tmp_path / "frontend"),
        branch="main",
    )

    session_manager.update_session(session)

    # Verify two conversations exist
    session = session_manager.get_session("test-remove")
    assert len(session.conversations) == 2

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
    assert len(session.conversations) == 1
    assert "backend" in session.conversations
    assert "frontend" not in session.conversations


def test_remove_active_project_switches_working_directory(temp_daf_home, tmp_path):
    """Test that removing the active project switches working_directory."""
    from devflow.cli.commands.session_project_command import remove_project_from_session

    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    session = session_manager.create_session(
        name="test-switch",
        goal="Test",
        working_directory="backend",
        project_path=str(tmp_path / "backend"),
        branch="main",
        ai_agent_session_id="uuid-1",
    )

    session.add_conversation(
        working_dir="frontend",
        ai_agent_session_id="uuid-2",
        project_path=str(tmp_path / "frontend"),
        branch="main",
    )

    session_manager.update_session(session)

    # Remove backend (active project)
    remove_project_from_session(
        session_name="test-switch",
        project_name="backend",
        force=True,
    )

    # Reload with fresh session manager (remove_project creates its own instance)
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)
    session = session_manager.get_session("test-switch")
    assert session.working_directory == "frontend"
    assert len(session.conversations) == 1


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
