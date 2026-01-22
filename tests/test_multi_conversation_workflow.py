"""Tests for multi-conversation workflow in daf new and daf open commands."""

import pytest
from pathlib import Path

from devflow.config.loader import ConfigLoader
from devflow.session.manager import SessionManager


def test_daf_new_creates_first_session(temp_daf_home, tmp_path):
    """Test that daf new creates a session when none exists."""
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    # Create first session
    session = session_manager.create_session(
        name="test-multi",
        goal="Multi-repo test",
        working_directory="repo1",
        project_path=str(tmp_path / "repo1"),
        branch="feature",
        ai_agent_session_id="uuid-1",
    )

    assert session.name == "test-multi"
    assert len(session.conversations) == 1
    assert "repo1" in session.conversations


def test_add_conversation_to_existing_session(temp_daf_home, tmp_path):
    """Test that adding a conversation to an existing session works correctly."""
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    # Create first session with one conversation
    session = session_manager.create_session(
        name="test-multi",
        goal="Multi-repo test",
        working_directory="repo1",
        project_path=str(tmp_path / "repo1"),
        branch="feature",
        ai_agent_session_id="uuid-1",
    )

    assert len(session.conversations) == 1

    # Add second conversation to same session
    session.add_conversation(
        working_dir="repo2",
        ai_agent_session_id="uuid-2",
        project_path=str(tmp_path / "repo2"),
        branch="feature",
    )
    session_manager.update_session(session)

    # Verify session now has 2 conversations
    assert len(session.conversations) == 2
    assert "repo1" in session.conversations
    assert "repo2" in session.conversations

    # Verify still only 1 session in the group
    sessions = session_manager.index.get_sessions("test-multi")
    assert len(sessions) == 1
    

def test_multiple_sessions_in_group_have_different_ids(temp_daf_home, tmp_path):
    """Test that attempting to create duplicate session names raises ValueError."""
    import pytest

    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    # Create first session
    session1 = session_manager.create_session(
        name="test-multi",
        goal="First work stream",
        working_directory="repo1",
        project_path=str(tmp_path / "repo1"),
        branch="feature-1",
        ai_agent_session_id="uuid-1",
    )

    # Attempting to create second session with same name should raise ValueError
    with pytest.raises(ValueError, match="Session 'test-multi' already exists"):
        session_manager.create_session(
            name="test-multi",
            goal="Second work stream",
            working_directory="repo1",
            project_path=str(tmp_path / "repo1"),
            branch="feature-2",
            ai_agent_session_id="uuid-2",
        )


def test_get_conversation_from_session(temp_daf_home, tmp_path):
    """Test retrieving a specific conversation from a session."""
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    session = session_manager.create_session(
        name="test-multi",
        goal="Multi-repo test",
        working_directory="repo1",
        project_path=str(tmp_path / "repo1"),
        branch="feature",
        ai_agent_session_id="uuid-1",
    )

    session.add_conversation(
        working_dir="repo2",
        ai_agent_session_id="uuid-2",
        project_path=str(tmp_path / "repo2"),
        branch="feature",
    )

    # Get specific conversations
    conv1 = session.get_conversation("repo1")
    conv2 = session.get_conversation("repo2")
    conv_none = session.get_conversation("nonexistent")

    assert conv1 is not None
    assert conv1.ai_agent_session_id == "uuid-1"
    assert conv2 is not None
    assert conv2.ai_agent_session_id == "uuid-2"
    assert conv_none is None


def test_active_conversation_property(temp_daf_home, tmp_path):
    """Test that active_conversation returns the correct conversation."""
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    session = session_manager.create_session(
        name="test-multi",
        goal="Multi-repo test",
        working_directory="repo1",
        project_path=str(tmp_path / "repo1"),
        branch="feature",
        ai_agent_session_id="uuid-1",
    )

    session.add_conversation(
        working_dir="repo2",
        ai_agent_session_id="uuid-2",
        project_path=str(tmp_path / "repo2"),
        branch="feature",
    )

    # Set working directory to repo2
    session.working_directory = "repo2"

    # Active conversation should be repo2
    active = session.active_conversation
    assert active is not None
    assert active.ai_agent_session_id == "uuid-2"

    # Switch to repo1
    session.working_directory = "repo1"
    active = session.active_conversation
    assert active is not None
    assert active.ai_agent_session_id == "uuid-1"


def test_cannot_add_duplicate_conversation(temp_daf_home, tmp_path):
    """Test that adding multiple conversations to same working_dir raises error.

    With PROJ-63490, to add a new Claude session to the same repository, you must use
    create_new_conversation() which archives the current one. add_conversation() is only
    for adding conversations to NEW repositories.
    """
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    session = session_manager.create_session(
        name="test-multi",
        goal="Multi-repo test",
        working_directory="repo1",
        project_path=str(tmp_path / "repo1"),
        branch="feature",
        ai_agent_session_id="uuid-1",
    )

    # Try to add second conversation with same working_dir - should raise error
    with pytest.raises(ValueError, match="Conversation already exists"):
        session.add_conversation(
            working_dir="repo1",  # Same as existing
            ai_agent_session_id="uuid-2",
            project_path=str(tmp_path / "repo1"),
            branch="feature",
        )

    # Verify only one conversation exists
    assert len(session.conversations) == 1
    assert session.conversations["repo1"].active_session.ai_agent_session_id == "uuid-1"
    assert len(session.conversations["repo1"].archived_sessions) == 0


def test_export_includes_all_conversations(temp_daf_home, tmp_path):
    """Test that exporting a session includes all conversations."""
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    # Create session with multiple conversations
    session = session_manager.create_session(
        name="test-export",
        goal="Export test",
        working_directory="repo1",
        project_path=str(tmp_path / "repo1"),
        branch="feature",
        ai_agent_session_id="uuid-1",
    )

    session.add_conversation(
        working_dir="repo2",
        ai_agent_session_id="uuid-2",
        project_path=str(tmp_path / "repo2"),
        branch="feature",
    )

    session.add_conversation(
        working_dir="repo3",
        ai_agent_session_id="uuid-3",
        project_path=str(tmp_path / "repo3"),
        branch="feature",
    )

    session_manager.update_session(session)

    # Re-load session from disk
    reloaded = session_manager.get_session("test-export")

    assert reloaded is not None
    assert len(reloaded.conversations) == 3
    assert "repo1" in reloaded.conversations
    assert "repo2" in reloaded.conversations
    assert "repo3" in reloaded.conversations
