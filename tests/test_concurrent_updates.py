"""Tests for concurrent session updates (PROJ-60619).

This module tests the read-modify-write pattern implementation
to prevent data loss from concurrent updates to sessions.json.
"""

import json
from pathlib import Path

import pytest

from devflow.config.loader import ConfigLoader
from devflow.config.models import Session
from devflow.session.manager import SessionManager


def test_concurrent_updates_to_different_sessions(temp_daf_home):
    """Test that concurrent updates to different sessions both succeed.

    Simulates the scenario where two processes modify different sessions:
    - Process A modifies session1
    - Process B modifies session2
    - Both changes should be preserved
    """
    # Setup: Create two sessions
    manager1 = SessionManager()
    session1 = manager1.create_session(
        name="session1",
        goal="First session",
        working_directory="dir1",
        project_path="/path/to/project1",
        ai_agent_session_id="uuid-1",
    )
    session2 = manager1.create_session(
        name="session2",
        goal="Second session",
        working_directory="dir2",
        project_path="/path/to/project2",
        ai_agent_session_id="uuid-2",
    )

    # Simulate Process A: Load sessions and modify session1
    manager_a = SessionManager()
    session_a = manager_a.get_session("session1")
    assert session_a is not None
    session_a.status = "in_progress"
    if not session_a.issue_metadata:
        session_a.issue_metadata = {}
    session_a.issue_metadata["summary"] = "Updated by Process A"

    # Simulate Process B: Load sessions (at same time) and modify session2
    manager_b = SessionManager()
    session_b = manager_b.get_session("session2")
    assert session_b is not None
    session_b.status = "completed"
    if not session_b.issue_metadata:
        session_b.issue_metadata = {}
    session_b.issue_metadata["summary"] = "Updated by Process B"

    # Process A saves first
    manager_a.update_session(session_a)

    # Process B saves second (should preserve Process A's changes via read-modify-write)
    manager_b.update_session(session_b)

    # Verify: Both changes should be preserved
    manager_verify = SessionManager()

    session1_final = manager_verify.get_session("session1")
    assert session1_final is not None
    assert session1_final.status == "in_progress"
    assert session1_final.issue_metadata.get("summary") == "Updated by Process A"

    session2_final = manager_verify.get_session("session2")
    assert session2_final is not None
    assert session2_final.status == "completed"
    assert session2_final.issue_metadata.get("summary") == "Updated by Process B"


def test_concurrent_updates_to_same_session_last_write_wins(temp_daf_home):
    """Test concurrent updates to same session (last write wins).

    When two processes modify the same session concurrently,
    the last write wins (standard conflict resolution).
    """
    # Setup: Create a session
    manager1 = SessionManager()
    session1 = manager1.create_session(
        name="shared-session",
        goal="Shared session",
        working_directory="shared-dir",
        project_path="/path/to/shared",
        ai_agent_session_id="shared-uuid",
    )
    original_status = session1.status

    # Simulate Process A: Load session and modify it
    manager_a = SessionManager()
    session_a = manager_a.get_session("shared-session")
    assert session_a is not None
    session_a.status = "in_progress"
    if not session_a.issue_metadata:
        session_a.issue_metadata = {}
    session_a.issue_metadata["summary"] = "Updated by Process A"

    # Simulate Process B: Load session (at same time) and modify it differently
    manager_b = SessionManager()
    session_b = manager_b.get_session("shared-session")
    assert session_b is not None
    session_b.status = "completed"
    if not session_b.issue_metadata:
        session_b.issue_metadata = {}
    session_b.issue_metadata["summary"] = "Updated by Process B"

    # Process A saves first
    manager_a.update_session(session_a)

    # Process B saves second (should overwrite Process A's changes for same session)
    manager_b.update_session(session_b)

    # Verify: Process B's changes win (last write wins)
    manager_verify = SessionManager()
    session_final = manager_verify.get_session("shared-session")
    assert session_final is not None
    assert session_final.status == "completed"
    assert session_final.issue_metadata.get("summary") == "Updated by Process B"


def test_concurrent_create_and_update(temp_daf_home):
    """Test concurrent session creation and update.

    Process A creates session2 while Process B updates session1.
    Both changes should be preserved.
    """
    # Setup: Create initial session
    manager1 = SessionManager()
    session1 = manager1.create_session(
        name="session1",
        goal="First session",
        working_directory="dir1",
        project_path="/path/to/project1",
        ai_agent_session_id="uuid-1",
    )

    # Simulate Process A: Load sessions and create new session
    manager_a = SessionManager()
    session2_a = manager_a.create_session(
        name="session2",
        goal="Second session",
        working_directory="dir2",
        project_path="/path/to/project2",
        ai_agent_session_id="uuid-2",
    )

    # Simulate Process B: Load sessions (at same time) and update session1
    manager_b = SessionManager()
    session1_b = manager_b.get_session("session1")
    assert session1_b is not None
    session1_b.status = "in_progress"
    manager_b.update_session(session1_b)

    # Verify: Both session2 creation and session1 update should be preserved
    manager_verify = SessionManager()

    session1_final = manager_verify.get_session("session1")
    assert session1_final is not None
    assert session1_final.status == "in_progress"

    session2_final = manager_verify.get_session("session2")
    assert session2_final is not None
    assert session2_final.goal == "Second session"


def test_multiple_sessions_in_same_group_concurrent_update(temp_daf_home):
    """Test that attempting to create duplicate session names raises ValueError.

    Session groups have been removed - each session must have a unique name.
    """
    # Setup: Create first session
    manager1 = SessionManager()
    session1_1 = manager1.create_session(
        name="multi-session",
        goal="First session in group",
        working_directory="dir1",
        project_path="/path/to/project1",
        ai_agent_session_id="uuid-1",
    )

    # Attempting to create second session with same name should raise ValueError
    import pytest
    with pytest.raises(ValueError, match="Session 'multi-session' already exists"):
        session1_2 = manager1.create_session(
            name="multi-session",
            goal="Second session in group",
            working_directory="dir2",
            project_path="/path/to/project2",
            ai_agent_session_id="uuid-2",
        )


def test_read_modify_write_preserves_unmodified_sessions(temp_daf_home):
    """Test that read-modify-write only updates modified sessions.

    When Process B saves, it should:
    - Update sessions modified by Process B
    - Preserve sessions modified by Process A
    - Keep all other sessions unchanged
    """
    # Setup: Create three sessions
    manager1 = SessionManager()
    session1 = manager1.create_session(
        name="session1",
        goal="Session 1",
        working_directory="dir1",
        project_path="/path1",
        ai_agent_session_id="uuid-1",
    )
    session2 = manager1.create_session(
        name="session2",
        goal="Session 2",
        working_directory="dir2",
        project_path="/path2",
        ai_agent_session_id="uuid-2",
    )
    session3 = manager1.create_session(
        name="session3",
        goal="Session 3",
        working_directory="dir3",
        project_path="/path3",
        ai_agent_session_id="uuid-3",
    )

    # Process A: Modify session1
    manager_a = SessionManager()
    session_a = manager_a.get_session("session1")
    assert session_a is not None
    if not session_a.issue_metadata:
        session_a.issue_metadata = {}
    session_a.issue_metadata["summary"] = "Modified by A"
    manager_a.update_session(session_a)

    # Process B: Load sessions (sees original state), modify session2
    manager_b = SessionManager()
    session_b = manager_b.get_session("session2")
    assert session_b is not None
    if not session_b.issue_metadata:
        session_b.issue_metadata = {}
    session_b.issue_metadata["summary"] = "Modified by B"
    manager_b.update_session(session_b)

    # Verify: All three sessions should exist with correct modifications
    manager_verify = SessionManager()

    session1_final = manager_verify.get_session("session1")
    assert session1_final is not None
    assert session1_final.issue_metadata.get("summary") == "Modified by A"

    session2_final = manager_verify.get_session("session2")
    assert session2_final is not None
    assert session2_final.issue_metadata.get("summary") == "Modified by B"

    session3_final = manager_verify.get_session("session3")
    assert session3_final is not None
    assert session3_final.issue_metadata.get("summary") is None  # Unchanged


def test_no_save_when_no_modifications(temp_daf_home):
    """Test that _save_index does nothing when no sessions are modified.

    This is an optimization to avoid unnecessary disk I/O.
    """
    # Setup: Create a session
    manager1 = SessionManager()
    session1 = manager1.create_session(
        name="session1",
        goal="Session 1",
        working_directory="dir1",
        project_path="/path1",
        ai_agent_session_id="uuid-1",
    )

    # Create a new manager (loads sessions but doesn't modify anything)
    manager2 = SessionManager()

    # Manually call _save_index (should be a no-op)
    manager2._save_index()

    # Verify: Session should still exist unchanged
    manager_verify = SessionManager()
    session_final = manager_verify.get_session("session1")
    assert session_final is not None
    assert session_final.goal == "Session 1"


def test_modified_groups_cleared_after_save(temp_daf_home):
    """Test that modified sessions tracker is cleared after save."""
    # Setup: Create a session
    manager = SessionManager()
    session = manager.create_session(
        name="test-session",
        goal="Test",
        working_directory="test-dir",
        project_path="/path",
        ai_agent_session_id="uuid-test",
    )

    # Verify modified sessions was cleared after create_session
    assert len(manager._modified_sessions) == 0

    # Modify session
    session.status = "in_progress"
    manager.update_session(session)

    # Verify modified sessions was cleared after update_session
    assert len(manager._modified_sessions) == 0
