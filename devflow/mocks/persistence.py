"""Thread-safe persistent storage for mock services data.

This module provides a thread-safe data store for mock services that persists
data across command invocations. The data is stored in JSON files in the
DevAIFlow home/mocks directory.
"""

import json
import threading
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from devflow.utils.paths import get_cs_home


class MockDataStore:
    """Thread-safe persistent storage for mock services data.

    This class manages mock data for JIRA, GitHub, GitLab, and Claude Code services.
    Data is stored in JSON files and synchronized across threads using locks.

    Attributes:
        data_dir: Directory where mock data files are stored
        _data: In-memory cache of mock data
        _lock: Thread lock for synchronizing access
    """

    _instance: Optional["MockDataStore"] = None
    _lock_class = threading.Lock()

    def __new__(cls):
        """Singleton pattern to ensure only one data store instance exists."""
        with cls._lock_class:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
            return cls._instance

    def __init__(self):
        """Initialize the mock data store."""
        if self._initialized:
            return

        self.data_dir = get_cs_home() / "mocks"
        self.data_dir.mkdir(parents=True, exist_ok=True)

        self._data: Dict[str, Dict[str, Any]] = {
            "jira": {},
            "github": {},
            "gitlab": {},
            "claude": {},
        }
        self._lock = threading.RLock()  # Reentrant lock for nested calls
        self._load_all()
        self._initialized = True

    def _load_all(self) -> None:
        """Load all mock data from disk."""
        for service in self._data.keys():
            self._load_service(service)

    def _load_service(self, service: str) -> None:
        """Load data for a specific service from disk.

        Args:
            service: Service name (jira, github, gitlab, claude)
        """
        data_file = self.data_dir / f"{service}.json"
        if data_file.exists():
            try:
                with open(data_file, "r") as f:
                    self._data[service] = json.load(f)
            except (json.JSONDecodeError, IOError):
                # If file is corrupted, start fresh
                self._data[service] = {}
        else:
            self._data[service] = {}

    def _save_service(self, service: str) -> None:
        """Save data for a specific service to disk.

        Args:
            service: Service name (jira, github, gitlab, claude)
        """
        data_file = self.data_dir / f"{service}.json"
        try:
            with open(data_file, "w") as f:
                json.dump(self._data[service], f, indent=2, default=str)
        except (IOError, TypeError) as e:
            # Log error but don't crash
            import sys
            print(f"Warning: Failed to save mock data for {service}: {e}", file=sys.stderr)

    # JIRA mock data methods

    def get_jira_ticket(self, key: str) -> Optional[Dict[str, Any]]:
        """Get a issue tracker ticket by key.

        Args:
            key: issue tracker key (e.g., "PROJ-12345")

        Returns:
            Ticket data dict or None if not found
        """
        with self._lock:
            tickets = self._data["jira"].get("tickets", {})
            return tickets.get(key)

    def set_jira_ticket(self, key: str, data: Dict[str, Any]) -> None:
        """Store or update a issue tracker ticket.

        Args:
            key: issue tracker key
            data: Ticket data dict
        """
        with self._lock:
            if "tickets" not in self._data["jira"]:
                self._data["jira"]["tickets"] = {}
            self._data["jira"]["tickets"][key] = data
            self._save_service("jira")

    def get_jira_comments(self, key: str) -> List[str]:
        """Get comments for a issue tracker ticket.

        Args:
            key: issue tracker key

        Returns:
            List of comment strings
        """
        with self._lock:
            comments = self._data["jira"].get("comments", {})
            return comments.get(key, [])

    def add_jira_comment(self, key: str, comment: str) -> None:
        """Add a comment to a issue tracker ticket.

        Args:
            key: issue tracker key
            comment: Comment text
        """
        with self._lock:
            if "comments" not in self._data["jira"]:
                self._data["jira"]["comments"] = {}
            if key not in self._data["jira"]["comments"]:
                self._data["jira"]["comments"][key] = []
            self._data["jira"]["comments"][key].append(comment)
            self._save_service("jira")

    def get_jira_attachments(self, key: str) -> List[str]:
        """Get attachments for a issue tracker ticket.

        Args:
            key: issue tracker key

        Returns:
            List of attachment filenames
        """
        with self._lock:
            attachments = self._data["jira"].get("attachments", {})
            return attachments.get(key, [])

    def add_jira_attachment(self, key: str, filename: str) -> None:
        """Add an attachment to a issue tracker ticket.

        Args:
            key: issue tracker key
            filename: Attachment filename
        """
        with self._lock:
            if "attachments" not in self._data["jira"]:
                self._data["jira"]["attachments"] = {}
            if key not in self._data["jira"]["attachments"]:
                self._data["jira"]["attachments"][key] = []
            self._data["jira"]["attachments"][key].append(filename)
            self._save_service("jira")

    def get_jira_transition(self, key: str) -> Optional[str]:
        """Get the current transition status for a ticket.

        Args:
            key: issue tracker key

        Returns:
            Status name or None
        """
        with self._lock:
            transitions = self._data["jira"].get("transitions", {})
            return transitions.get(key)

    def set_jira_transition(self, key: str, status: str) -> None:
        """Set the transition status for a ticket.

        Args:
            key: issue tracker key
            status: New status name
        """
        with self._lock:
            if "transitions" not in self._data["jira"]:
                self._data["jira"]["transitions"] = {}
            self._data["jira"]["transitions"][key] = status

            # Also update the ticket status if it exists
            if "tickets" in self._data["jira"] and key in self._data["jira"]["tickets"]:
                if "fields" not in self._data["jira"]["tickets"][key]:
                    self._data["jira"]["tickets"][key]["fields"] = {}
                if "status" not in self._data["jira"]["tickets"][key]["fields"]:
                    self._data["jira"]["tickets"][key]["fields"]["status"] = {}
                self._data["jira"]["tickets"][key]["fields"]["status"]["name"] = status

            self._save_service("jira")

    def list_jira_tickets(self) -> List[Dict[str, Any]]:
        """List all issue tracker tickets.

        Returns:
            List of ticket data dicts
        """
        with self._lock:
            tickets = self._data["jira"].get("tickets", {})
            return list(tickets.values())

    # GitHub mock data methods

    def get_github_pr(self, repo: str, pr_number: int) -> Optional[Dict[str, Any]]:
        """Get a GitHub pull request.

        Args:
            repo: Repository name (e.g., "owner/repo")
            pr_number: PR number

        Returns:
            PR data dict or None if not found
        """
        with self._lock:
            prs = self._data["github"].get("prs", {})
            key = f"{repo}#{pr_number}"
            return prs.get(key)

    def set_github_pr(self, repo: str, pr_number: int, data: Dict[str, Any]) -> None:
        """Store or update a GitHub pull request.

        Args:
            repo: Repository name
            pr_number: PR number
            data: PR data dict
        """
        with self._lock:
            if "prs" not in self._data["github"]:
                self._data["github"]["prs"] = {}
            key = f"{repo}#{pr_number}"
            self._data["github"]["prs"][key] = data
            self._save_service("github")

    def list_github_prs(self, repo: str) -> List[Dict[str, Any]]:
        """List all pull requests for a repository.

        Args:
            repo: Repository name

        Returns:
            List of PR data dicts
        """
        with self._lock:
            prs = self._data["github"].get("prs", {})
            return [pr for key, pr in prs.items() if key.startswith(f"{repo}#")]

    # GitLab mock data methods

    def get_gitlab_mr(self, project: str, mr_number: int) -> Optional[Dict[str, Any]]:
        """Get a GitLab merge request.

        Args:
            project: Project name (e.g., "group/project")
            mr_number: MR number

        Returns:
            MR data dict or None if not found
        """
        with self._lock:
            mrs = self._data["gitlab"].get("mrs", {})
            key = f"{project}!{mr_number}"
            return mrs.get(key)

    def set_gitlab_mr(self, project: str, mr_number: int, data: Dict[str, Any]) -> None:
        """Store or update a GitLab merge request.

        Args:
            project: Project name
            mr_number: MR number
            data: MR data dict
        """
        with self._lock:
            if "mrs" not in self._data["gitlab"]:
                self._data["gitlab"]["mrs"] = {}
            key = f"{project}!{mr_number}"
            self._data["gitlab"]["mrs"][key] = data
            self._save_service("gitlab")

    def list_gitlab_mrs(self, project: str) -> List[Dict[str, Any]]:
        """List all merge requests for a project.

        Args:
            project: Project name

        Returns:
            List of MR data dicts
        """
        with self._lock:
            mrs = self._data["gitlab"].get("mrs", {})
            return [mr for key, mr in mrs.items() if key.startswith(f"{project}!")]

    # Claude Code mock data methods

    def get_claude_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get a Claude Code session.

        Args:
            session_id: Claude session UUID

        Returns:
            Session data dict or None if not found
        """
        with self._lock:
            sessions = self._data["claude"].get("sessions", {})
            return sessions.get(session_id)

    def set_claude_session(self, session_id: str, data: Dict[str, Any]) -> None:
        """Store or update a Claude Code session.

        Args:
            session_id: Claude session UUID
            data: Session data dict
        """
        with self._lock:
            if "sessions" not in self._data["claude"]:
                self._data["claude"]["sessions"] = {}
            self._data["claude"]["sessions"][session_id] = data
            self._save_service("claude")

    def list_claude_sessions(self) -> List[Dict[str, Any]]:
        """List all Claude Code sessions.

        Returns:
            List of session data dicts
        """
        with self._lock:
            sessions = self._data["claude"].get("sessions", {})
            return list(sessions.values())

    # Session management methods (for SessionIndex)

    def load_session_index(self) -> Optional[Dict[str, Any]]:
        """Load session index from mock storage.

        Returns:
            Session index dict or None if not found
        """
        sessions_file = self.data_dir / "sessions.json"
        if sessions_file.exists():
            try:
                with open(sessions_file, "r") as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                return None
        return None

    def save_session_index(self, index_data: Dict[str, Any]) -> None:
        """Save session index to mock storage.

        Args:
            index_data: Session index dict to save
        """
        sessions_file = self.data_dir / "sessions.json"
        try:
            self.data_dir.mkdir(parents=True, exist_ok=True)
            with open(sessions_file, "w") as f:
                json.dump(index_data, f, indent=2, default=str)
        except (IOError, TypeError) as e:
            import sys
            print(f"Warning: Failed to save mock session index: {e}", file=sys.stderr)

    # Utility methods

    def clear_all(self) -> None:
        """Clear all mock data including sessions."""
        with self._lock:
            for service in self._data.keys():
                self._data[service] = {}
                self._save_service(service)

            # Also clear sessions
            sessions_file = self.data_dir / "sessions.json"
            if sessions_file.exists():
                sessions_file.unlink()

    def clear_service(self, service: str) -> None:
        """Clear mock data for a specific service.

        Args:
            service: Service name (jira, github, gitlab, claude)
        """
        with self._lock:
            if service in self._data:
                self._data[service] = {}
                self._save_service(service)

    def export_data(self) -> Dict[str, Dict[str, Any]]:
        """Export all mock data.

        Returns:
            Complete mock data dict
        """
        with self._lock:
            return json.loads(json.dumps(self._data, default=str))

    def import_data(self, data: Dict[str, Dict[str, Any]]) -> None:
        """Import mock data.

        Args:
            data: Complete mock data dict
        """
        with self._lock:
            for service in self._data.keys():
                if service in data:
                    self._data[service] = data[service]
                    self._save_service(service)
