"""File-based storage backend for sessions."""

import json
import os
import shutil
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from devflow.config.models import Session, SessionIndex

from .base import StorageBackend
from .filters import SessionFilters


class FileBackend(StorageBackend):
    """File-based storage backend.

    Stores sessions in JSON files on the local filesystem.
    Default storage backend for DevAIFlow.
    """

    def __init__(self, sessions_dir: Path, sessions_file: Path):
        """Initialize the file backend.

        Args:
            sessions_dir: Directory for session data
            sessions_file: Path to sessions.json index file
        """
        self.sessions_dir = sessions_dir
        self.sessions_file = sessions_file

        # Ensure directories exist
        self.sessions_dir.mkdir(parents=True, exist_ok=True)

    def load_index(self) -> SessionIndex:
        """Load session index from sessions.json.

        If mock mode is enabled (DAF_MOCK_MODE=1), loads from mock storage instead.

        Returns:
            SessionIndex object (empty if file doesn't exist)
        """
        from devflow.utils import is_mock_mode

        # Check if mock mode is enabled via environment variable
        if is_mock_mode():
            from devflow.mocks.persistence import MockDataStore
            store = MockDataStore()
            mock_data = store.load_session_index()
            if mock_data:
                return SessionIndex(**mock_data)
            return SessionIndex()

        # Normal (non-mock) behavior
        if not self.sessions_file.exists():
            return SessionIndex()

        try:
            with open(self.sessions_file, "r") as f:
                data = json.load(f)
            return SessionIndex(**data)
        except Exception as e:
            raise ValueError(f"Failed to load sessions: {e}")

    def save_index(self, index: SessionIndex) -> None:
        """Save session index to sessions.json with file locking.

        If mock mode is enabled (DAF_MOCK_MODE=1), saves to mock storage instead.

        Uses file locking (fcntl.flock on Unix) to prevent simultaneous writes
        from multiple processes.

        Args:
            index: SessionIndex object to save
        """
        from devflow.utils import is_mock_mode

        # Check if mock mode is enabled via environment variable
        if is_mock_mode():
            from devflow.mocks.persistence import MockDataStore
            store = MockDataStore()
            store.save_session_index(index.model_dump())
            return

        # Normal (non-mock) behavior with file locking
        with open(self.sessions_file, "w") as f:
            # Acquire exclusive lock on Unix/Linux/macOS
            # Windows doesn't support fcntl, so we skip locking there
            if sys.platform != "win32":
                import fcntl
                fcntl.flock(f.fileno(), fcntl.LOCK_EX)

            try:
                json.dump(index.model_dump(), f, indent=2, default=str)
                f.flush()  # Explicitly flush to ensure data is written
                os.fsync(f.fileno())  # Force OS to write to disk (prevents data loss on signal)
            finally:
                # Release lock (happens automatically on close, but explicit is better)
                if sys.platform != "win32":
                    import fcntl
                    fcntl.flock(f.fileno(), fcntl.LOCK_UN)

    def load_session_metadata(self, session_name: str) -> Optional[Dict]:
        """Load session metadata from session directory.

        Args:
            session_name: Session name

        Returns:
            Dictionary of session metadata or None if not found
        """
        session_dir = self.get_session_dir(session_name)
        metadata_file = session_dir / "metadata.json"

        if not metadata_file.exists():
            return None

        try:
            with open(metadata_file, "r") as f:
                return json.load(f)
        except Exception as e:
            raise ValueError(f"Failed to load session metadata: {e}")

    def save_session_metadata(self, session: Session) -> None:
        """Save session metadata to session directory.

        Args:
            session: Session object to save
        """
        session_dir = self.get_session_dir(session.name)
        metadata_file = session_dir / "metadata.json"

        # Get active conversation data (for backward compatibility)
        active_conv = session.active_conversation
        project_path = active_conv.project_path if active_conv else None
        branch = active_conv.branch if active_conv else None

        # Serialize conversations to dict format (Pydantic models need to be converted)
        conversations_dict = {}
        for repo_key, conversation in session.conversations.items():
            if hasattr(conversation, 'model_dump'):
                conversations_dict[repo_key] = conversation.model_dump()
            elif isinstance(conversation, dict):
                conversations_dict[repo_key] = conversation
            else:
                # Fallback: try to convert to dict
                conversations_dict[repo_key] = dict(conversation)

        metadata = {
            "name": session.name,
            "issue_key": session.issue_key,
            # Issue tracker fields
            "issue_tracker": session.issue_tracker,
            "issue_updated": session.issue_updated,
            "issue_metadata": session.issue_metadata,
            "goal": session.goal,
            "session_type": session.session_type,
            "created": session.created.isoformat() if session.created else None,
            "tags": session.tags,
            "related_sessions": session.related_sessions,
            # Required fields for reopening sessions
            "project_path": project_path,
            "working_directory": session.working_directory,
            "branch": branch,
            "status": session.status,
            "conversation_count": len(session.conversations),
            # Store full conversations structure for reliable rebuilds
            "conversations": conversations_dict,
        }

        with open(metadata_file, "w") as f:
            json.dump(metadata, f, indent=2, default=str)
            f.flush()  # Explicitly flush to ensure data is written
            os.fsync(f.fileno())  # Force OS to write to disk (prevents data loss on signal)

    def delete_session_data(self, session_name: str) -> None:
        """Delete all data for a session.

        Args:
            session_name: Session group name
        """
        session_dir = self.get_session_dir(session_name)
        if session_dir.exists():
            shutil.rmtree(session_dir)

    def get_session_dir(self, session_name: str) -> Path:
        """Get the directory for a specific session group.

        Args:
            session_name: Session group name (primary identifier)

        Returns:
            Path to session directory
        """
        session_dir = self.sessions_dir / session_name
        session_dir.mkdir(parents=True, exist_ok=True)
        return session_dir

    def add_note(self, session: Session, note: str) -> None:
        """Add a note to a session.

        Args:
            session: Session object
            note: Note text to add
        """
        # Use session name for directory (not issue key, which might be None)
        session_dir = self.get_session_dir(session.name)
        notes_file = session_dir / "notes.md"

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
        note_entry = f"\n## {timestamp}\n- {note}\n"

        if notes_file.exists():
            with open(notes_file, "a") as f:
                f.write(note_entry)
        else:
            with open(notes_file, "w") as f:
                # Use session name for the title
                f.write(f"# Session Notes: {session.name}\n")
                if session.issue_key:
                    f.write(f"*JIRA:* {session.issue_key}\n\n")
                f.write(note_entry)

    def list_sessions(self, index: SessionIndex, filters: SessionFilters) -> List[Session]:
        """List sessions with optional filters.

        Args:
            index: SessionIndex to filter
            filters: Filter criteria

        Returns:
            List of Session objects matching the filters
        """
        # Get all sessions
        all_sessions = list(index.sessions.values())

        # Apply filters
        filtered_sessions = all_sessions

        if filters.status:
            # Support comma-separated status values
            status_list = [s.strip() for s in filters.status.split(",")]
            filtered_sessions = [s for s in filtered_sessions if s.status in status_list]

        if filters.working_directory:
            filtered_sessions = [s for s in filtered_sessions if s.working_directory == filters.working_directory]

        if filters.issue_metadata_filters:
            for field_name, field_value in filters.issue_metadata_filters.items():
                filtered_sessions = [
                    s
                    for s in filtered_sessions
                    if s.issue_metadata and s.issue_metadata.get(field_name) == field_value
                ]

        if filters.issue_status:
            # Support comma-separated JIRA status values
            issue_status_list = [s.strip() for s in filters.issue_status.split(",")]
            filtered_sessions = [
                s
                for s in filtered_sessions
                if s.issue_metadata and s.issue_metadata.get("status") in issue_status_list
            ]

        if filters.since:
            filtered_sessions = [s for s in filtered_sessions if s.last_active >= filters.since]

        if filters.before:
            filtered_sessions = [s for s in filtered_sessions if s.last_active < filters.before]

        # Sort by last_active (most recent first) to match SessionIndex.get_all_sessions() behavior
        filtered_sessions.sort(key=lambda s: s.last_active, reverse=True)

        return filtered_sessions

    def rename_session(self, old_name: str, new_name: str, session: Session) -> None:
        """Rename a session and its directory.

        Args:
            old_name: Current session name
            new_name: New session name
            session: Session object being renamed

        Raises:
            ValueError: If directories cannot be renamed
        """
        # Rename session directory
        old_dir = self.sessions_dir / old_name
        new_dir = self.sessions_dir / new_name

        if old_dir.exists():
            # Remove destination if it exists (shouldn't happen in normal use, but can occur in tests)
            if new_dir.exists():
                shutil.rmtree(new_dir)
            shutil.move(str(old_dir), str(new_dir))
