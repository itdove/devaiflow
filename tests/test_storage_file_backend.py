"""Tests for FileBackend storage implementation."""

from datetime import datetime, timedelta
from pathlib import Path

import pytest

from devflow.config.models import Session, SessionIndex
from devflow.storage import FileBackend, SessionFilters


def test_file_backend_initialization(temp_daf_home):
    """Test FileBackend initialization."""
    sessions_dir = Path(temp_daf_home) / "sessions"
    sessions_file = Path(temp_daf_home) / "sessions.json"

    backend = FileBackend(sessions_dir=sessions_dir, sessions_file=sessions_file)

    assert backend.sessions_dir == sessions_dir
    assert backend.sessions_file == sessions_file
    assert backend.sessions_dir.exists()


def test_file_backend_load_empty_index(temp_daf_home):
    """Test loading an empty index."""
    sessions_dir = Path(temp_daf_home) / "sessions"
    sessions_file = Path(temp_daf_home) / "sessions.json"

    backend = FileBackend(sessions_dir=sessions_dir, sessions_file=sessions_file)
    index = backend.load_index()

    assert isinstance(index, SessionIndex)
    assert len(index.sessions) == 0


def test_file_backend_save_and_load_index(temp_daf_home):
    """Test saving and loading session index."""
    sessions_dir = Path(temp_daf_home) / "sessions"
    sessions_file = Path(temp_daf_home) / "sessions.json"

    backend = FileBackend(sessions_dir=sessions_dir, sessions_file=sessions_file)

    # Create a test session
    session = Session(
        name="test-session",        issue_key="PROJ-12345",
        goal="Test goal",
        working_directory="test-dir",
        status="created",
        created=datetime.now(),
        last_active=datetime.now(),
    )

    # Create index and add session
    index = SessionIndex()
    index.add_session(session)

    # Save index
    backend.save_index(index)

    # Load index
    loaded_index = backend.load_index()

    assert len(loaded_index.sessions) == 1
    assert "test-session" in loaded_index.sessions
    assert loaded_index.sessions["test-session"].issue_key == "PROJ-12345"


def test_file_backend_save_and_load_session_metadata(temp_daf_home):
    """Test saving and loading session metadata."""
    sessions_dir = Path(temp_daf_home) / "sessions"
    sessions_file = Path(temp_daf_home) / "sessions.json"

    backend = FileBackend(sessions_dir=sessions_dir, sessions_file=sessions_file)

    # Create a test session
    session = Session(
        name="metadata-test",        issue_key="PROJ-67890",
        goal="Metadata test",
        working_directory="meta-dir",
        status="in_progress",
        created=datetime.now(),
        last_active=datetime.now(),
        session_type="development",
        tags=["tag1", "tag2"],
    )

    # Save metadata
    backend.save_session_metadata(session)

    # Load metadata
    loaded_metadata = backend.load_session_metadata("metadata-test")

    assert loaded_metadata is not None
    assert loaded_metadata["name"] == "metadata-test"
    assert loaded_metadata["issue_key"] == "PROJ-67890"
    assert loaded_metadata["goal"] == "Metadata test"
    assert loaded_metadata["status"] == "in_progress"
    assert loaded_metadata["session_type"] == "development"
    assert loaded_metadata["tags"] == ["tag1", "tag2"]


def test_file_backend_load_nonexistent_metadata(temp_daf_home):
    """Test loading metadata for nonexistent session."""
    sessions_dir = Path(temp_daf_home) / "sessions"
    sessions_file = Path(temp_daf_home) / "sessions.json"

    backend = FileBackend(sessions_dir=sessions_dir, sessions_file=sessions_file)

    # Try to load nonexistent metadata
    metadata = backend.load_session_metadata("nonexistent-session")

    assert metadata is None


def test_file_backend_get_session_dir(temp_daf_home):
    """Test getting session directory."""
    sessions_dir = Path(temp_daf_home) / "sessions"
    sessions_file = Path(temp_daf_home) / "sessions.json"

    backend = FileBackend(sessions_dir=sessions_dir, sessions_file=sessions_file)

    # Get session directory
    session_dir = backend.get_session_dir("test-session")

    assert session_dir.exists()
    assert session_dir.name == "test-session"
    assert session_dir.parent == sessions_dir


def test_file_backend_add_note(temp_daf_home):
    """Test adding notes to a session."""
    sessions_dir = Path(temp_daf_home) / "sessions"
    sessions_file = Path(temp_daf_home) / "sessions.json"

    backend = FileBackend(sessions_dir=sessions_dir, sessions_file=sessions_file)

    # Create a test session
    session = Session(
        name="note-test",        issue_key="PROJ-11111",
        goal="Note test",
        working_directory="note-dir",
        status="created",
        created=datetime.now(),
        last_active=datetime.now(),
    )

    # Add first note
    backend.add_note(session, "First note")

    # Verify notes file exists
    notes_file = backend.get_session_dir("note-test") / "notes.md"
    assert notes_file.exists()

    # Read notes file
    notes_content = notes_file.read_text()
    assert "First note" in notes_content
    assert "note-test" in notes_content
    assert "PROJ-11111" in notes_content

    # Add second note
    backend.add_note(session, "Second note")

    # Verify both notes exist
    notes_content = notes_file.read_text()
    assert "First note" in notes_content
    assert "Second note" in notes_content


def test_file_backend_list_sessions_no_filters(temp_daf_home):
    """Test listing sessions without filters."""
    sessions_dir = Path(temp_daf_home) / "sessions"
    sessions_file = Path(temp_daf_home) / "sessions.json"

    backend = FileBackend(sessions_dir=sessions_dir, sessions_file=sessions_file)

    # Create test sessions
    session1 = Session(
        name="session-1",        goal="First session",
        working_directory="dir1",
        status="created",
        created=datetime.now(),
        last_active=datetime.now(),
    )

    session2 = Session(
        name="session-2",        goal="Second session",
        working_directory="dir2",
        status="in_progress",
        created=datetime.now(),
        last_active=datetime.now(),
    )

    # Create index and add sessions
    index = SessionIndex()
    index.add_session(session1)
    index.add_session(session2)

    # List all sessions
    filters = SessionFilters()
    sessions = backend.list_sessions(index, filters)

    assert len(sessions) == 2


def test_file_backend_list_sessions_with_status_filter(temp_daf_home):
    """Test listing sessions with status filter."""
    sessions_dir = Path(temp_daf_home) / "sessions"
    sessions_file = Path(temp_daf_home) / "sessions.json"

    backend = FileBackend(sessions_dir=sessions_dir, sessions_file=sessions_file)

    # Create test sessions with different statuses
    session1 = Session(
        name="session-1",        goal="Created session",
        working_directory="dir1",
        status="created",
        created=datetime.now(),
        last_active=datetime.now(),
    )

    session2 = Session(
        name="session-2",        goal="In progress session",
        working_directory="dir2",
        status="in_progress",
        created=datetime.now(),
        last_active=datetime.now(),
    )

    session3 = Session(
        name="session-3",        goal="Completed session",
        working_directory="dir3",
        status="complete",
        created=datetime.now(),
        last_active=datetime.now(),
    )

    # Create index and add sessions
    index = SessionIndex()
    index.add_session(session1)
    index.add_session(session2)
    index.add_session(session3)

    # Filter by status
    filters = SessionFilters(status="in_progress")
    sessions = backend.list_sessions(index, filters)

    assert len(sessions) == 1
    assert sessions[0].status == "in_progress"


def test_file_backend_list_sessions_with_multiple_status_filter(temp_daf_home):
    """Test listing sessions with comma-separated status filter."""
    sessions_dir = Path(temp_daf_home) / "sessions"
    sessions_file = Path(temp_daf_home) / "sessions.json"

    backend = FileBackend(sessions_dir=sessions_dir, sessions_file=sessions_file)

    # Create test sessions
    session1 = Session(
        name="session-1",        goal="Created",
        working_directory="dir1",
        status="created",
        created=datetime.now(),
        last_active=datetime.now(),
    )

    session2 = Session(
        name="session-2",        goal="In progress",
        working_directory="dir2",
        status="in_progress",
        created=datetime.now(),
        last_active=datetime.now(),
    )

    session3 = Session(
        name="session-3",        goal="Complete",
        working_directory="dir3",
        status="complete",
        created=datetime.now(),
        last_active=datetime.now(),
    )

    # Create index
    index = SessionIndex()
    index.add_session(session1)
    index.add_session(session2)
    index.add_session(session3)

    # Filter by multiple statuses
    filters = SessionFilters(status="created,in_progress")
    sessions = backend.list_sessions(index, filters)

    assert len(sessions) == 2
    statuses = {s.status for s in sessions}
    assert statuses == {"created", "in_progress"}


def test_file_backend_list_sessions_with_time_filters(temp_daf_home):
    """Test listing sessions with time range filters."""
    sessions_dir = Path(temp_daf_home) / "sessions"
    sessions_file = Path(temp_daf_home) / "sessions.json"

    backend = FileBackend(sessions_dir=sessions_dir, sessions_file=sessions_file)

    now = datetime.now()
    yesterday = now - timedelta(days=1)
    two_days_ago = now - timedelta(days=2)

    # Create test sessions with different last_active times
    session1 = Session(
        name="session-1",        goal="Old session",
        working_directory="dir1",
        status="created",
        created=two_days_ago,
        last_active=two_days_ago,
    )

    session2 = Session(
        name="session-2",        goal="Recent session",
        working_directory="dir2",
        status="created",
        created=yesterday,
        last_active=yesterday,
    )

    session3 = Session(
        name="session-3",        goal="Today session",
        working_directory="dir3",
        status="created",
        created=now,
        last_active=now,
    )

    # Create index
    index = SessionIndex()
    index.add_session(session1)
    index.add_session(session2)
    index.add_session(session3)

    # Filter sessions since yesterday
    filters = SessionFilters(since=yesterday)
    sessions = backend.list_sessions(index, filters)

    assert len(sessions) == 2  # session2 and session3

    # Filter sessions before yesterday
    filters = SessionFilters(before=yesterday)
    sessions = backend.list_sessions(index, filters)

    assert len(sessions) == 1  # session1 only


def test_file_backend_rename_session(temp_daf_home):
    """Test renaming a session directory."""
    sessions_dir = Path(temp_daf_home) / "sessions"
    sessions_file = Path(temp_daf_home) / "sessions.json"

    backend = FileBackend(sessions_dir=sessions_dir, sessions_file=sessions_file)

    # Create a test session
    session = Session(
        name="old-name",        goal="Rename test",
        working_directory="test-dir",
        status="created",
        created=datetime.now(),
        last_active=datetime.now(),
    )

    # Save metadata to create directory
    backend.save_session_metadata(session)

    # Verify old directory exists
    old_dir = backend.get_session_dir("old-name")
    assert old_dir.exists()

    # Rename session
    session.name = "new-name"
    backend.rename_session("old-name", "new-name", [session])

    # Verify new directory exists and old one doesn't
    new_dir = sessions_dir / "new-name"
    old_dir = sessions_dir / "old-name"

    assert new_dir.exists()
    assert not old_dir.exists()


def test_file_backend_delete_session_data(temp_daf_home):
    """Test deleting session data."""
    sessions_dir = Path(temp_daf_home) / "sessions"
    sessions_file = Path(temp_daf_home) / "sessions.json"

    backend = FileBackend(sessions_dir=sessions_dir, sessions_file=sessions_file)

    # Create a test session
    session = Session(
        name="delete-me",        goal="Delete test",
        working_directory="test-dir",
        status="created",
        created=datetime.now(),
        last_active=datetime.now(),
    )

    # Save metadata to create directory
    backend.save_session_metadata(session)

    # Verify directory exists
    session_dir = backend.get_session_dir("delete-me")
    assert session_dir.exists()

    # Delete session data
    backend.delete_session_data("delete-me")

    # Verify directory no longer exists
    assert not session_dir.exists()
