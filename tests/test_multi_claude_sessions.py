"""Unit tests for multiple Claude sessions per conversation."""

import uuid
from datetime import datetime
from pathlib import Path

import pytest

from devflow.config.loader import ConfigLoader
from devflow.config.models import ConversationContext, Session
from devflow.session.manager import SessionManager


def test_conversation_context_has_archived_field():
    """Test that ConversationContext has archived field with default False."""
    conv = ConversationContext(
        ai_agent_session_id="test-uuid-123",
        project_path="/path/to/project",
        branch="main",
    )

    assert hasattr(conv, "archived")
    assert conv.archived is False


def test_conversation_context_has_conversation_history():
    """Test that ConversationContext has conversation_history field."""
    conv = ConversationContext(
        ai_agent_session_id="test-uuid-123",
        project_path="/path/to/project",
        branch="main",
    )

    assert hasattr(conv, "conversation_history")
    assert isinstance(conv.conversation_history, list)


def test_conversation_history_auto_populated():
    """Test that conversation_history is auto-populated with ai_agent_session_id."""
    conv = ConversationContext(
        ai_agent_session_id="test-uuid-123",
        project_path="/path/to/project",
        branch="main",
    )

    # The validator should auto-populate conversation_history
    assert "test-uuid-123" in conv.conversation_history


def test_session_conversations_is_conversation_object():
    """Test that Session.conversations uses Conversation class structure."""
    from devflow.config.models import Conversation

    session = Session(
        name="test-session",
        goal="Test goal",
    )

    # Add a conversation
    session.add_conversation(
        working_dir="repo1",
        ai_agent_session_id="uuid-1",
        project_path="/path/to/repo1",
        branch="main",
    )

    # Check that conversations is a dict of Conversation objects
    assert isinstance(session.conversations["repo1"], Conversation)
    assert session.conversations["repo1"].active_session.ai_agent_session_id == "uuid-1"
    assert session.conversations["repo1"].active_session.archived is False
    assert len(session.conversations["repo1"].archived_sessions) == 0


def test_add_multiple_conversations_same_working_dir_raises_error():
    """Test that adding multiple conversations to same working_dir raises an error."""
    session = Session(
        name="test-session",
        goal="Test goal",
    )

    # Add first conversation
    session.add_conversation(
        working_dir="repo1",
        ai_agent_session_id="uuid-1",
        project_path="/path/to/repo1",
        branch="main",
    )

    # Try to add second conversation to same working_dir - should raise error
    with pytest.raises(ValueError, match="Conversation already exists"):
        session.add_conversation(
            working_dir="repo1",
            ai_agent_session_id="uuid-2",
            project_path="/path/to/repo1",
            branch="main",
        )


def test_active_conversation_returns_active_session():
    """Test that active_conversation returns the active session (not archived)."""
    session = Session(
        name="test-session",
        goal="Test goal",
        working_directory="repo1",
    )

    # Add first conversation
    session.add_conversation(
        working_dir="repo1",
        ai_agent_session_id="uuid-1",
        project_path="/path/to/repo1",
        branch="main",
    )

    # Create new conversation (archives uuid-1 and creates uuid-2)
    session.create_new_conversation(
        working_dir="repo1",
        project_path="/path/to/repo1",
        branch="main",
    )

    # active_conversation should return the new active session (not archived)
    active = session.active_conversation
    assert active is not None
    assert active.archived is False
    # The new one should NOT be uuid-1 (that's archived now)
    assert active.ai_agent_session_id != "uuid-1"

    # Verify the old one is archived
    assert len(session.conversations["repo1"].archived_sessions) == 1
    assert session.conversations["repo1"].archived_sessions[0].ai_agent_session_id == "uuid-1"
    assert session.conversations["repo1"].archived_sessions[0].archived is True


def test_get_conversation_returns_active_one():
    """Test that get_conversation returns the active session."""
    session = Session(
        name="test-session",
        goal="Test goal",
    )

    # Add first conversation
    session.add_conversation(
        working_dir="repo1",
        ai_agent_session_id="uuid-1",
        project_path="/path/to/repo1",
        branch="main",
    )

    # Create new conversation (archives uuid-1)
    session.create_new_conversation(
        working_dir="repo1",
        project_path="/path/to/repo1",
        branch="main",
    )

    # get_conversation should return the active one (not uuid-1)
    conv = session.get_conversation("repo1")
    assert conv is not None
    assert conv.archived is False
    assert conv.ai_agent_session_id != "uuid-1"


def test_get_all_conversations():
    """Test get_all_conversations helper method."""
    session = Session(
        name="test-session",
        goal="Test goal",
    )

    # Add first conversation to repo1
    session.add_conversation(
        working_dir="repo1",
        ai_agent_session_id="uuid-1",
        project_path="/path/to/repo1",
        branch="main",
    )

    # Create new conversation on repo1 (archives uuid-1)
    session.create_new_conversation(
        working_dir="repo1",
        project_path="/path/to/repo1",
        branch="main",
    )

    # Add conversation to repo2
    session.add_conversation(
        working_dir="repo2",
        ai_agent_session_id="uuid-3",
        project_path="/path/to/repo2",
        branch="main",
    )

    # Should have 3 total: 2 from repo1 (1 archived + 1 active) + 1 from repo2
    all_convs = session.get_all_conversations()
    assert len(all_convs) == 3
    # uuid-1 should be in the list (archived)
    uuids = {c.ai_agent_session_id for c in all_convs}
    assert "uuid-1" in uuids  # archived one
    assert "uuid-3" in uuids  # repo2


def test_get_conversation_by_uuid():
    """Test get_conversation_by_uuid helper method."""
    session = Session(
        name="test-session",
        goal="Test goal",
    )

    # Add conversations
    session.add_conversation(
        working_dir="repo1",
        ai_agent_session_id="uuid-1",
        project_path="/path/to/repo1",
        branch="main",
    )
    session.add_conversation(
        working_dir="repo2",
        ai_agent_session_id="uuid-2",
        project_path="/path/to/repo2",
        branch="main",
    )

    # Find by UUID
    conv = session.get_conversation_by_uuid("uuid-2")
    assert conv is not None
    assert conv.ai_agent_session_id == "uuid-2"
    assert conv.project_path == "/path/to/repo2"


def test_create_new_conversation():
    """Test create_new_conversation method (main method for --new-conversation)."""
    session = Session(
        name="test-session",
        goal="Test goal",
        working_directory="repo1",
    )

    # Add initial conversation
    session.add_conversation(
        working_dir="repo1",
        ai_agent_session_id="uuid-1",
        project_path="/path/to/repo1",
        branch="feature-branch",
    )

    # Create new conversation
    new_conv = session.create_new_conversation(
        working_dir="repo1",
        project_path="/path/to/repo1",
        branch="feature-branch",
    )

    # Verify new conversation created
    assert new_conv is not None
    assert new_conv.archived is False
    assert new_conv.ai_agent_session_id != "uuid-1"  # Should be a new UUID

    # Verify old conversation archived
    assert len(session.conversations["repo1"].archived_sessions) == 1
    assert session.conversations["repo1"].archived_sessions[0].archived is True
    assert session.conversations["repo1"].archived_sessions[0].ai_agent_session_id == "uuid-1"

    # Verify new conversation is the active one
    assert session.conversations["repo1"].active_session.ai_agent_session_id == new_conv.ai_agent_session_id
    assert session.conversations["repo1"].active_session.archived is False


def test_reactivate_conversation():
    """Test reactivate_conversation method (main method for --conversation-id)."""
    session = Session(
        name="test-session",
        goal="Test goal",
        working_directory="repo1",
    )

    # Add first conversation
    session.add_conversation(
        working_dir="repo1",
        ai_agent_session_id="uuid-1",
        project_path="/path/to/repo1",
        branch="main",
    )

    # Create new conversation (archives uuid-1 and creates new one)
    new_conv = session.create_new_conversation(
        working_dir="repo1",
        project_path="/path/to/repo1",
        branch="main",
    )

    # At this point:
    # - active_session should be the new one (not uuid-1)
    # - archived_sessions should contain uuid-1
    assert session.conversations["repo1"].active_session.ai_agent_session_id != "uuid-1"
    assert len(session.conversations["repo1"].archived_sessions) == 1
    assert session.conversations["repo1"].archived_sessions[0].ai_agent_session_id == "uuid-1"

    # Reactivate the first one (uuid-1)
    result = session.reactivate_conversation("uuid-1")

    assert result is True
    # uuid-1 should now be active
    assert session.conversations["repo1"].active_session.ai_agent_session_id == "uuid-1"
    assert session.conversations["repo1"].active_session.archived is False
    # The new one should now be archived
    assert len(session.conversations["repo1"].archived_sessions) == 1
    assert session.conversations["repo1"].archived_sessions[0].archived is True
    assert session.working_directory == "repo1"


def test_reactivate_conversation_not_found():
    """Test reactivate_conversation with non-existent UUID."""
    session = Session(
        name="test-session",
        goal="Test goal",
    )

    session.add_conversation(
        working_dir="repo1",
        ai_agent_session_id="uuid-1",
        project_path="/path/to/repo1",
        branch="main",
    )

    result = session.reactivate_conversation("nonexistent-uuid")
    assert result is False


def test_migration_from_old_format(temp_daf_home):
    """Test auto-migration from old Dict[str, ConversationContext] to new Conversation format."""
    from devflow.config.models import Conversation

    # Simulate old format by manually creating session with old structure
    # This would happen when loading from JSON
    session = Session(
        name="test-session",
        goal="Test goal",
    )

    # Manually set old format (this simulates what JSON loading would do)
    old_conv = ConversationContext(
        ai_agent_session_id="uuid-1",
        project_path="/path/to/repo1",
        branch="main",
    )

    # Directly assign old format (bypassing normal add_conversation)
    session.conversations = {"repo1": old_conv}  # type: ignore

    # Trigger migration validator
    session = session.migrate_conversations()

    # Should be migrated to Conversation object format
    assert isinstance(session.conversations["repo1"], Conversation)
    assert session.conversations["repo1"].active_session.ai_agent_session_id == "uuid-1"
    assert session.conversations["repo1"].active_session.archived is False
    assert len(session.conversations["repo1"].archived_sessions) == 0


def test_session_with_persistence(temp_daf_home, tmp_path):
    """Test that sessions with multiple conversations persist correctly."""
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    # Create session with initial conversation
    session = session_manager.create_session(
        name="test-multi",
        goal="Multi-conversation test",
        working_directory="repo1",
        project_path=str(tmp_path / "repo1"),
        branch="main",
        ai_agent_session_id="uuid-1",
    )

    # Create new conversation (archives uuid-1)
    session.create_new_conversation(
        working_dir="repo1",
        project_path=str(tmp_path / "repo1"),
        branch="main",
    )

    # Save session
    session_manager.update_session(session)

    # Load fresh session manager
    session_manager2 = SessionManager(config_loader)
    loaded_session = session_manager2.get_session("test-multi")

    # Verify persistence
    assert loaded_session is not None
    # Should have 1 active session + 1 archived session
    assert len(loaded_session.conversations["repo1"].archived_sessions) == 1
    assert loaded_session.conversations["repo1"].archived_sessions[0].ai_agent_session_id == "uuid-1"
    assert loaded_session.conversations["repo1"].archived_sessions[0].archived is True
    assert loaded_session.conversations["repo1"].active_session.archived is False
    assert loaded_session.conversations["repo1"].active_session.ai_agent_session_id != "uuid-1"


def test_conversation_context_has_summary_field():
    """Test that ConversationContext has summary field."""
    conv = ConversationContext(
        ai_agent_session_id="test-uuid-123",
        project_path="/path/to/project",
        branch="main",
    )

    assert hasattr(conv, "summary")
    assert conv.summary is None  # Default is None


def test_summary_field_persists():
    """Test that summary field is persisted when set."""
    conv = ConversationContext(
        ai_agent_session_id="test-uuid-123",
        project_path="/path/to/project",
        branch="main",
        summary="This conversation added user authentication",
    )

    assert conv.summary == "This conversation added user authentication"

    # Verify it serializes correctly
    conv_dict = conv.model_dump(mode="json")
    assert conv_dict["summary"] == "This conversation added user authentication"
