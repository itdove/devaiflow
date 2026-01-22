"""Discover existing Claude Code sessions."""

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import List, Optional


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
    """Discover existing Claude Code sessions."""

    def __init__(self, claude_dir: Optional[Path] = None):
        """Initialize session discovery.

        Args:
            claude_dir: Path to .claude directory. Defaults to ~/.claude
        """
        self.claude_dir = claude_dir or Path.home() / ".claude"
        self.projects_dir = self.claude_dir / "projects"

    def discover_sessions(self) -> List[DiscoveredSession]:
        """Discover all Claude Code sessions.

        Returns:
            List of DiscoveredSession objects
        """
        sessions = []

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

    def _parse_session_file(self, session_file: Path, project_dir: Path) -> Optional[DiscoveredSession]:
        """Parse a session .jsonl file.

        Args:
            session_file: Path to .jsonl file
            project_dir: Parent project directory

        Returns:
            DiscoveredSession object or None if parsing fails
        """
        uuid = session_file.stem
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
            # Extract cwd if not found yet
            if not project_path and msg.get("cwd"):
                project_path = msg.get("cwd")
                working_directory = Path(project_path).name

            # Extract first user message
            if not first_message and msg.get("type") == "user":
                message_obj = msg.get("message", {})
                content = message_obj.get("content")
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

        return DiscoveredSession(
            uuid=uuid,
            project_path=project_path or "unknown",
            message_count=len(messages),
            created=created,
            last_active=last_active,
            first_message=first_message,
            working_directory=working_directory or "unknown",
        )
