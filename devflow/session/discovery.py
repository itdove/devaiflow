"""Discover existing file-backed AI agent sessions."""

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from devflow.agent import create_agent_client
from devflow.utils.paths import get_claude_config_dir


@dataclass
class DiscoveredSession:
    """A Claude Code session discovered on the filesystem."""

    uuid: str
    project_path: str
    message_count: int
    created: datetime
    last_active: datetime
    first_message: Optional[str] = None
    working_directory: Optional[str] = None


class SessionDiscovery:
    """Discover existing sessions for a selected file-backed agent."""

    def __init__(
        self,
        claude_dir: Optional[Path] = None,
        agent_backend: str = "claude",
        agent=None,
    ):
        """Initialize session discovery.

        Args:
            claude_dir: Agent home directory override retained for compatibility.
            agent_backend: Agent backend to discover.
            agent: Optional pre-created agent adapter.
        """
        self.agent = agent or create_agent_client(agent_backend, agent_home=claude_dir)
        self.agent_backend = self.agent.get_agent_name()
        self.claude_dir = claude_dir or get_claude_config_dir()
        self.projects_dir = self.claude_dir / "projects"

    def discover_sessions(self) -> List[DiscoveredSession]:
        """Discover all Claude Code sessions.

        Returns:
            List of DiscoveredSession objects
        """
        sessions = []

        get_session_files = getattr(self.agent, "get_session_files", None)
        if get_session_files:
            for session_file in get_session_files():
                try:
                    session = self._parse_session_file(
                        session_file,
                        session_file.parent,
                        session_id=self._session_id_from_file(session_file),
                    )
                    if session:
                        sessions.append(session)
                except Exception:
                    continue

            sessions.sort(key=lambda s: s.last_active, reverse=True)
            return sessions

        if not self.projects_dir.exists():
            return sessions

        # Scan all project directories
        for project_dir in self.projects_dir.iterdir():
            if not project_dir.is_dir():
                continue

            # Find all .jsonl files (each is a session)
            for session_file in project_dir.glob("*.jsonl"):
                try:
                    session = self._parse_session_file(session_file, project_dir)
                    if session:
                        sessions.append(session)
                except Exception:
                    # Skip files that can't be parsed
                    continue

        # Sort by last_active (most recent first)
        sessions.sort(key=lambda s: s.last_active, reverse=True)
        return sessions

    @staticmethod
    def _session_id_from_file(session_file: Path) -> str:
        """Extract an ID from plain or timestamp-prefixed session filenames."""
        return session_file.stem.rsplit("_", 1)[-1]

    def _parse_session_file(
        self,
        session_file: Path,
        project_dir: Path,
        session_id: Optional[str] = None,
    ) -> Optional[DiscoveredSession]:
        """Parse a session .jsonl file.

        Args:
            session_file: Path to .jsonl file
            project_dir: Parent project directory

        Returns:
            DiscoveredSession object or None if parsing fails
        """
        uuid = session_id or session_file.stem
        messages = []
        first_message = None
        working_directory = None
        project_path = None

        # Read all messages
        with open(session_file, "r") as f:
            for line in f:
                try:
                    msg = json.loads(line.strip())
                    messages.append(msg)
                except json.JSONDecodeError:
                    continue

        if not messages:
            return None

        # Get first user message and project path from messages
        # Claude Code format: {"type": "user", "message": {"role": "user", "content": "..."}, "cwd": "..."}
        for msg in messages:
            # Extract cwd if not found yet. Pi records it in the session header,
            # while Claude Code records it on individual messages.
            message_obj = msg.get("message", {})
            if not isinstance(message_obj, dict):
                message_obj = {}
            if not project_path:
                project_path = msg.get("cwd") or msg.get("projectPath") or message_obj.get("cwd")
            if project_path:
                working_directory = Path(project_path).name

            # Extract first user message
            role = message_obj.get("role") or msg.get("role")
            if not first_message and (msg.get("type") == "user" or role == "user"):
                content = message_obj.get("content") or msg.get("content")
                if isinstance(content, str):
                    first_message = content
                elif isinstance(content, list):
                    # Extract text from content blocks
                    for block in content:
                        if isinstance(block, dict) and block.get("type") == "text":
                            first_message = block.get("text", "")
                            break

            # Stop if we have both
            if first_message and project_path:
                break

        # Get file timestamps
        stat = session_file.stat()
        created = datetime.fromtimestamp(stat.st_ctime)
        last_active = datetime.fromtimestamp(stat.st_mtime)

        if self.agent_backend == "pi":
            message_count = sum(
                1
                for message in messages
                if message.get("type") == "message"
                or (
                    isinstance(message.get("message"), dict)
                    and message["message"].get("role") in {"user", "assistant", "toolResult"}
                )
            )
        else:
            message_count = len(messages)

        return DiscoveredSession(
            uuid=uuid,
            project_path=project_path or "unknown",
            message_count=message_count,
            created=created,
            last_active=last_active,
            first_message=first_message,
            working_directory=working_directory or "unknown",
        )
