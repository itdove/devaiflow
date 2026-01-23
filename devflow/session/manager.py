"""Session management for Claude Code sessions."""

from datetime import datetime
from typing import Dict, List, Optional

from devflow.config.loader import ConfigLoader
from devflow.config.models import Session, SessionIndex, WorkSession
from devflow.storage import FileBackend, SessionFilters, StorageBackend
from devflow.utils import get_current_user


class SessionManager:
    """Manage Claude Code sessions."""

    def __init__(
        self,
        config_loader: Optional[ConfigLoader] = None,
        storage: Optional[StorageBackend] = None,
    ):
        """Initialize the session manager.

        Args:
            config_loader: ConfigLoader instance. Defaults to new instance.
            storage: StorageBackend instance. Defaults to FileBackend.
        """
        self.config_loader = config_loader or ConfigLoader()

        # Initialize storage backend
        if storage is None:
            # Default to FileBackend
            self.storage = FileBackend(
                sessions_dir=self.config_loader.sessions_dir,
                sessions_file=self.config_loader.sessions_file,
            )
        else:
            self.storage = storage

        # Load sessions from storage
        self.index = self.storage.load_index()

        # Track which sessions have been modified in this instance
        # This includes creates, updates, and deletes
        # Format: {session_name: True}
        self._modified_sessions: Dict[str, bool] = {}

    def create_session(
        self,
        name: str,
        goal: str,
        working_directory: Optional[str] = None,
        project_path: Optional[str] = None,
        branch: Optional[str] = None,
        ai_agent_session_id: Optional[str] = None,
        issue_key: Optional[str] = None,
    ) -> Session:
        """Create a new session.

        Args:
            name: Session group name (primary identifier)
            goal: Session goal/description
            working_directory: Working directory name
            project_path: Full path to project
            branch: Git branch name
            ai_agent_session_id: Claude Code session UUID
            issue_key: Optional issue tracker key

        Returns:
            Created Session object
        """
        session = Session(
            name=name,
            issue_key=issue_key,
            goal=goal,
            working_directory=working_directory,
            status="created",
        )

        # Create initial conversation if we have the required info (NEW in PROJ-59791)
        if working_directory and project_path and ai_agent_session_id:
            config = self.config_loader.load_config()
            workspace = config.repos.workspace if config else None

            session.add_conversation(
                working_dir=working_directory,
                ai_agent_session_id=ai_agent_session_id,
                project_path=project_path,
                branch=branch or "main",
                workspace=workspace,
            )

        # Auto-start time tracking if configured
        config = self.config_loader.load_config()
        if config and hasattr(config, 'time_tracking') and config.time_tracking and hasattr(config.time_tracking, 'auto_start') and config.time_tracking.auto_start:
            from devflow.config.models import WorkSession
            session.work_sessions.append(WorkSession(start=datetime.now()))
            session.time_tracking_state = "running"

        self.index.add_session(session)
        self._mark_modified(session)
        self._save_index()
        self._save_session_metadata(session)

        return session

    def get_session(self, identifier: str) -> Optional[Session]:
        """Get a session by name or issue key.

        Smart lookup: tries session name first, then issue key.

        Args:
            identifier: Session name or issue tracker key

        Returns:
            Session object if found, None otherwise
        """
        return self.index.get_session(identifier)

    def update_session(self, session: Session) -> None:
        """Update an existing session.

        Args:
            session: Session object to update
        """
        session.last_active = datetime.now()

        # Find and update the session
        # IMPORTANT: We search by name first, then across all sessions because
        # the session.name might be stale (if session was renamed but caller still
        # has old session object). We must use the ACTUAL name from the index.
        actual_name = None

        # First, try to find by exact name match (fastest path)
        if session.name in self.index.sessions:
            self.index.sessions[session.name] = session
            actual_name = session.name
        else:
            # If not found by name, search all sessions by conversations or issue_key
            for session_name, s in self.index.sessions.items():
                # Use conversations to match - they're unique per session
                conv_match = (
                    set(s.conversations.keys()) == set(session.conversations.keys())
                    if s.conversations and session.conversations
                    else False
                )
                # Also check issue key if both have it
                issue_match = (s.issue_key == session.issue_key) if (s.issue_key and session.issue_key) else False

                # Match requires: same conversations OR same issue_key
                if conv_match or issue_match:
                    self.index.sessions[session_name] = session
                    actual_name = session_name
                    break

        if actual_name:
            # Use the actual name from index, not session.name which might be stale
            self._mark_session_modified_by_name(actual_name)
            self._save_index()
            # Get the updated session from index to ensure we have the correct name
            updated_session = self.index.sessions[actual_name]
            self._save_session_metadata(updated_session)

    def delete_session(self, identifier: str) -> None:
        """Delete a session.

        Smart lookup: tries session name first, then issue key.

        Args:
            identifier: Session name or issue tracker key
        """
        # Find the session name that will be affected
        session_name = self._find_session_name(identifier)

        self.index.remove_session(identifier)

        # Mark the session as modified if deletion occurred
        if session_name:
            self._mark_session_modified_by_name(session_name)

        self._save_index()

    def _find_session_name(self, identifier: str) -> Optional[str]:
        """Find the session name for an identifier.

        Args:
            identifier: Session name or issue tracker key

        Returns:
            Session name if found, None otherwise
        """
        # Check if identifier is directly a session name
        if identifier in self.index.sessions:
            return identifier

        # Search for issue key match
        for name, session in self.index.sessions.items():
            if session.issue_key == identifier:
                return name

        return None

    def list_sessions(
        self,
        status: Optional[str] = None,
        working_directory: Optional[str] = None,
        sprint: Optional[str] = None,
        issue_status: Optional[str] = None,
        since: Optional[datetime] = None,
        before: Optional[datetime] = None,
    ) -> List[Session]:
        """List sessions with optional filters.

        Args:
            status: Filter by session status (comma-separated for multiple)
            working_directory: Filter by working directory
            sprint: Filter by sprint
            issue_status: Filter by issue tracker status (comma-separated for multiple)
            since: Filter by sessions active since this datetime
            before: Filter by sessions active before this datetime

        Returns:
            List of Session objects
        """
        filters = SessionFilters(
            status=status,
            working_directory=working_directory,
            sprint=sprint,
            issue_status=issue_status,
            since=since,
            before=before,
        )
        return self.storage.list_sessions(self.index, filters)

    def get_active_session_for_project(self, project_path: str) -> Optional[Session]:
        """Check if there's an active session (status=in_progress) for the given project.

        Args:
            project_path: Full path to the project directory

        Returns:
            Active Session object if found, None otherwise
        """
        # Iterate through all sessions to find active ones with matching project_path
        for session in self.index.sessions.values():
            if session.status == "in_progress":
                # Check if any conversation in this session matches the project_path
                for conversation in session.conversations.values():
                    # Check all sessions (active + archived) in this Conversation
                    for conv_ctx in conversation.get_all_sessions():
                        if conv_ctx.project_path == project_path:
                            return session
        return None

    def start_work_session(self, identifier: str) -> None:
        """Start a new work session for time tracking.

        Smart lookup: tries session name first, then issue key.

        Args:
            identifier: Session name or issue tracker key
        """
        session = self.get_session(identifier)
        if not session:
            raise ValueError(f"Session {identifier} not found")

        # End any existing active work session
        if session.work_sessions and session.work_sessions[-1].end is None:
            self.end_work_session(identifier)

        # Start new work session with current user
        work_session = WorkSession(
            start=datetime.now(),
            user=get_current_user()
        )
        session.work_sessions.append(work_session)
        session.time_tracking_state = "active"

        # Update session status to in_progress when starting work
        if session.status == "created":
            session.status = "in_progress"

        if session.started is None:
            session.started = datetime.now()

        self.update_session(session)

    def end_work_session(self, identifier: str) -> None:
        """End the current work session.

        Smart lookup: tries session name first, then issue key.

        Args:
            identifier: Session name or issue tracker key
        """
        session = self.get_session(identifier)
        if not session:
            raise ValueError(f"Session {identifier} not found")

        if session.work_sessions and session.work_sessions[-1].end is None:
            work_session = session.work_sessions[-1]
            work_session.end = datetime.now()
            duration = work_session.end - work_session.start
            hours = int(duration.total_seconds() // 3600)
            minutes = int((duration.total_seconds() % 3600) // 60)
            work_session.duration = f"{hours}h {minutes}m"
            session.time_tracking_state = "paused"
            self.update_session(session)

    def add_note(self, identifier: str, note: str) -> None:
        """Add a note to a session.

        Smart lookup: tries session name first, then issue key.

        Args:
            identifier: Session name or issue tracker key
            note: Note text
        """
        session = self.get_session(identifier)
        if not session:
            raise ValueError(f"Session {identifier} not found")

        # Delegate to storage backend
        self.storage.add_note(session, note)

        self.update_session(session)

    def _mark_modified(self, session: Session) -> None:
        """Mark a session's group as modified for read-modify-write tracking.

        Args:
            session: Session that was modified
        """
        self._modified_sessions[session.name] = True

    def _mark_session_modified_by_name(self, session_name: str) -> None:
        """Mark a session as modified by name (for deletions or bulk operations).

        Args:
            session_name: Name of the session that was modified
        """
        self._modified_sessions[session_name] = True

    def _save_index(self) -> None:
        """Save the session index to disk using read-modify-write pattern.

        This method implements a read-modify-write pattern to prevent data loss
        from concurrent updates:

        1. Re-read current sessions.json from disk
        2. Merge only modified session groups into fresh state
        3. Write merged result atomically

        This ensures concurrent processes don't overwrite each other's changes.
        Only session groups that were modified in this SessionManager instance
        are updated; all other groups are preserved from disk.
        """
        # If no groups were modified, no need to save
        if not self._modified_sessions:
            return

        # STEP 1: Re-read current state from disk
        fresh_index = self.storage.load_index()

        # STEP 2: Merge our modified session groups into fresh state
        for session_name in self._modified_sessions.keys():
            # Replace session with our version
            if session_name in self.index.sessions:
                # Session exists in our index - copy it to fresh index
                fresh_index.sessions[session_name] = self.index.sessions[session_name]
            else:
                # Session was deleted in our index - remove from fresh index
                if session_name in fresh_index.sessions:
                    del fresh_index.sessions[session_name]

        # STEP 3: Write merged result to disk (delegate to storage - PROJ-61112)
        self.storage.save_index(fresh_index)

        # Update our in-memory index: preserve modified sessions, update unmodified ones
        for session_name, session in fresh_index.sessions.items():
            if session_name not in self._modified_sessions:
                # This session wasn't modified by us - update from disk
                self.index.sessions[session_name] = session

        # Remove sessions that were deleted on disk but we didn't modify
        sessions_to_remove = []
        for session_name in self.index.sessions.keys():
            if session_name not in fresh_index.sessions and session_name not in self._modified_sessions:
                sessions_to_remove.append(session_name)
        for session_name in sessions_to_remove:
            del self.index.sessions[session_name]

        # Clear modified sessions tracker after successful save
        self._modified_sessions.clear()

    def _save_session_metadata(self, session: Session) -> None:
        """Save session metadata to session directory.

        Args:
            session: Session object to save
        """
        # Delegate to storage backend
        self.storage.save_session_metadata(session)

    def rename_session(self, old_name: str, new_name: str) -> None:
        """Rename a session group and its directory.

        Args:
            old_name: Current session group name
            new_name: New session group name

        Raises:
            ValueError: If old session doesn't exist or new name already exists
        """
        # Validate old session exists
        if old_name not in self.index.sessions:
            raise ValueError(f"Session '{old_name}' not found")

        # Validate new name is available
        if new_name in self.index.sessions:
            raise ValueError(f"Session '{new_name}' already exists")

        # Get session
        session = self.index.sessions[old_name]

        # Update name in session
        session.name = new_name

        # Update index (move to new key)
        self.index.sessions[new_name] = session
        del self.index.sessions[old_name]

        # Mark both sessions as modified 
        # We MUST mark old_name as modified so _save_index() deletes it from fresh_index
        # We MUST mark new_name as modified so _save_index() adds it to fresh_index
        self._mark_session_modified_by_name(old_name)
        self._mark_session_modified_by_name(new_name)

        # Delegate directory rename to storage backend
        self.storage.rename_session(old_name, new_name, session)

        # Save changes
        self._save_index()

        # Update metadata.json in new location
        self._save_session_metadata(session)
