"""Mock Claude Code service for integration testing.

This module provides a mock implementation of Claude Code session operations
that uses persistent storage. It's designed to be used for integration testing
without requiring actual Claude Code execution.
"""

import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from devflow.mocks.persistence import MockDataStore


class MockClaudeCode:
    """Mock Claude Code service for session operations.

    This service simulates Claude Code session file creation and management
    without actually launching Claude Code.
    """

    def __init__(self):
        """Initialize the mock Claude Code service."""
        self.store = MockDataStore()

    def create_session(
        self,
        project_path: str,
        initial_prompt: str = None
    ) -> str:
        """Create a new Claude Code session.

        Args:
            project_path: Path to project directory
            initial_prompt: Initial prompt to send (optional)

        Returns:
            Session UUID
        """
        # Generate session UUID
        session_id = str(uuid.uuid4())

        # Create session data
        session_data = {
            "session_id": session_id,
            "project_path": project_path,
            "created_at": datetime.now().isoformat(),
            "messages": [],
            "active": True,
        }

        # Add initial message if provided
        if initial_prompt:
            session_data["messages"].append({
                "role": "user",
                "content": initial_prompt,
                "timestamp": datetime.now().isoformat(),
            })

        # Store session
        self.store.set_claude_session(session_id, session_data)

        return session_id

    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get a Claude Code session by ID.

        Args:
            session_id: Session UUID

        Returns:
            Session data dict or None if not found
        """
        return self.store.get_claude_session(session_id)

    def add_message(
        self,
        session_id: str,
        role: str,
        content: str
    ) -> bool:
        """Add a message to a session.

        Args:
            session_id: Session UUID
            role: Message role ("user" or "assistant")
            content: Message content

        Returns:
            True if successful, False if session not found
        """
        session = self.store.get_claude_session(session_id)
        if not session:
            return False

        # Add message
        session["messages"].append({
            "role": role,
            "content": content,
            "timestamp": datetime.now().isoformat(),
        })

        # Update session
        self.store.set_claude_session(session_id, session)

        return True

    def close_session(self, session_id: str) -> bool:
        """Close a Claude Code session.

        Args:
            session_id: Session UUID

        Returns:
            True if successful, False if session not found
        """
        session = self.store.get_claude_session(session_id)
        if not session:
            return False

        session["active"] = False
        session["closed_at"] = datetime.now().isoformat()

        self.store.set_claude_session(session_id, session)

        return True

    def resume_session(self, session_id: str) -> bool:
        """Resume a closed Claude Code session.

        Args:
            session_id: Session UUID

        Returns:
            True if successful, False if session not found
        """
        session = self.store.get_claude_session(session_id)
        if not session:
            return False

        session["active"] = True
        if "closed_at" in session:
            del session["closed_at"]

        self.store.set_claude_session(session_id, session)

        return True

    def list_sessions(
        self,
        project_path: str = None,
        active_only: bool = False
    ) -> List[Dict[str, Any]]:
        """List Claude Code sessions.

        Args:
            project_path: Filter by project path (optional)
            active_only: Only return active sessions

        Returns:
            List of session data dicts
        """
        sessions = self.store.list_claude_sessions()

        # Filter by project path
        if project_path:
            sessions = [s for s in sessions if s.get("project_path") == project_path]

        # Filter by active status
        if active_only:
            sessions = [s for s in sessions if s.get("active", False)]

        return sessions

    def create_session_file(
        self,
        session_id: str,
        claude_home: Path = None
    ) -> Optional[Path]:
        """Create a mock .jsonl session file in Claude home directory.

        This simulates the actual Claude Code session file format.

        Args:
            session_id: Session UUID
            claude_home: Path to Claude home directory (default: ~/.claude)

        Returns:
            Path to created session file or None if session not found
        """
        session = self.store.get_claude_session(session_id)
        if not session:
            return None

        # Determine Claude home directory
        if claude_home is None:
            claude_home = Path.home() / ".claude"

        # Create projects directory (encoding project path)
        project_path = session.get("project_path", "")
        # Simple encoding: replace / with _
        encoded_path = project_path.replace("/", "_").replace("\\", "_")
        projects_dir = claude_home / "projects" / encoded_path
        projects_dir.mkdir(parents=True, exist_ok=True)

        # Create session file
        session_file = projects_dir / f"{session_id}.jsonl"

        # Write messages in JSONL format
        with open(session_file, "w") as f:
            for msg in session.get("messages", []):
                # Each line is a JSON object representing a message
                line = {
                    "type": "message",
                    "role": msg["role"],
                    "content": msg["content"],
                    "timestamp": msg["timestamp"],
                }
                f.write(json.dumps(line) + "\n")

        return session_file

    def get_message_count(self, session_id: str) -> int:
        """Get the number of messages in a session.

        Args:
            session_id: Session UUID

        Returns:
            Number of messages, or 0 if session not found
        """
        session = self.store.get_claude_session(session_id)
        if not session:
            return 0

        return len(session.get("messages", []))

    def simulate_conversation(
        self,
        session_id: str,
        exchanges: int = 3
    ) -> bool:
        """Simulate a conversation by adding mock messages.

        Useful for testing scenarios that require session history.

        Args:
            session_id: Session UUID
            exchanges: Number of user-assistant message pairs to add

        Returns:
            True if successful, False if session not found
        """
        session = self.store.get_claude_session(session_id)
        if not session:
            return False

        for i in range(exchanges):
            # Add user message
            self.add_message(
                session_id,
                "user",
                f"Mock user message {i + 1}"
            )

            # Add assistant message
            self.add_message(
                session_id,
                "assistant",
                f"Mock assistant response {i + 1}"
            )

        return True
