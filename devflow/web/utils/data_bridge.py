"""Bridge between DevAIFlow data layers and the web dashboard.

This module provides a clean interface for the web UI to access session data,
configuration, and notes without duplicating business logic. It wraps
SessionManager, ConfigLoader, and StorageBackend with web-friendly methods.
"""

from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import quote

from devflow.config.loader import ConfigLoader
from devflow.config.models import Config, Session
from devflow.session.manager import SessionManager
from devflow.utils.paths import get_cs_home


class DataBridge:
    """Bridge between DevAIFlow data layers and the web dashboard.

    Provides read-focused methods for the web UI. Each call re-reads from disk
    to ensure fresh data (sessions may be modified by CLI or other processes).
    """

    def __init__(self, config_loader: Optional[ConfigLoader] = None):
        """Initialize the data bridge.

        Args:
            config_loader: Optional ConfigLoader instance. Creates a new one if not provided.
        """
        self.config_loader = config_loader or ConfigLoader()

    def _get_manager(self) -> SessionManager:
        """Create a fresh SessionManager to read latest data from disk.

        Returns:
            SessionManager instance with fresh data.
        """
        return SessionManager(config_loader=self.config_loader)

    def list_sessions(
        self,
        status: Optional[str] = None,
        working_directory: Optional[str] = None,
        workspace: Optional[str] = None,
        issue_tracker: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """List sessions as dictionaries suitable for the web UI.

        Args:
            status: Optional status filter (comma-separated for multiple).
            working_directory: Optional working directory filter.
            workspace: Optional configured workspace filter.
            issue_tracker: Optional issue tracker filter. Use ``unlinked`` for
                sessions without an issue key.

        Returns:
            List of session dictionaries with display-friendly fields.
        """
        manager = self._get_manager()
        sessions = manager.list_sessions(
            status=status,
            working_directory=working_directory,
        )
        session_dicts = [self._session_to_dict(s) for s in sessions]
        if workspace is not None:
            session_dicts = [
                session
                for session in session_dicts
                if session["workspace"] == workspace
            ]
        if issue_tracker is not None:
            session_dicts = [
                session
                for session in session_dicts
                if session["issue_tracker"] == issue_tracker
            ]
        return session_dicts

    def get_session(self, identifier: str) -> Optional[Dict[str, Any]]:
        """Get a single session by name or issue key.

        Args:
            identifier: Session name or issue tracker key.

        Returns:
            Session dictionary or None if not found.
        """
        manager = self._get_manager()
        session = manager.get_session(identifier)
        if session is None:
            return None
        return self._session_to_detail_dict(session)

    def get_session_notes(self, session_name: str) -> str:
        """Read notes for a session.

        Args:
            session_name: Session name.

        Returns:
            Notes content as string, or empty string if no notes exist.
        """
        sessions_dir = getattr(self.config_loader, "sessions_dir", None)
        if not isinstance(sessions_dir, Path):
            sessions_dir = get_cs_home() / "sessions"
        notes_file = sessions_dir / session_name / "notes.md"
        if notes_file.exists():
            return notes_file.read_text(encoding="utf-8")
        return ""

    def add_session_note(self, identifier: str, note: str) -> bool:
        """Add a note to a session.

        Args:
            identifier: Session name or issue key.
            note: Note text to add.

        Returns:
            True if note was added successfully, False otherwise.
        """
        try:
            manager = self._get_manager()
            manager.add_note(identifier, note)
            return True
        except (ValueError, Exception):
            return False

    def get_config_summary(self) -> Dict[str, Any]:
        """Get a summary of the current configuration.

        Returns:
            Dictionary with configuration summary.
        """
        config = self.config_loader.load_config()
        if config is None:
            return {"loaded": False}

        summary: Dict[str, Any] = {"loaded": True}

        summary["issue_tracker_backend"] = self._get_issue_tracker_backend()

        # JIRA config
        if getattr(config, "jira", None):
            summary["jira"] = {
                "url": config.jira.url or "Not configured",
                "project": config.jira.project or "Not configured",
            }

        # GitHub config
        if getattr(config, "github", None):
            summary["github"] = {
                "enabled": bool(config.github.repository),
                "repository": config.github.repository or "Not configured",
            }

        # GitLab config
        if getattr(config, "gitlab", None):
            summary["gitlab"] = {
                "enabled": bool(config.gitlab.repository),
                "repository": config.gitlab.repository or "Not configured",
            }

        # Repos config
        if getattr(config, "repos", None):
            workspaces = []
            if config.repos.workspaces:
                for ws in config.repos.workspaces:
                    workspaces.append({"name": ws.name, "path": ws.path})
            summary["workspaces"] = workspaces

        # Agent
        summary["agent_backend"] = config.agent_backend or "claude"

        return summary

    def get_session_count_by_status(self) -> Dict[str, int]:
        """Get count of sessions grouped by status.

        Returns:
            Dictionary mapping status to count.
        """
        manager = self._get_manager()
        all_sessions = manager.list_sessions()
        counts: Dict[str, int] = {}
        for session in all_sessions:
            status = session.status or "unknown"
            counts[status] = counts.get(status, 0) + 1
        return counts

    def _session_to_dict(self, session: Session) -> Dict[str, Any]:
        """Convert a Session to a display-friendly dictionary.

        Args:
            session: Session model instance.

        Returns:
            Dictionary with key session fields for table display.
        """
        # Calculate total time
        total_minutes = 0
        for ws in session.work_sessions:
            if ws.start and ws.end:
                delta = ws.end - ws.start
                total_minutes += int(delta.total_seconds() / 60)
            elif ws.start and ws.end is None:
                # Active work session
                delta = datetime.now() - ws.start
                total_minutes += int(delta.total_seconds() / 60)

        hours = total_minutes // 60
        minutes = total_minutes % 60
        time_str = f"{hours}h {minutes}m" if hours > 0 else f"{minutes}m"

        # Get workspace name
        workspace = session.workspace_name or ""

        # Get issue key
        issue_key = session.issue_key or ""
        issue_tracker = self._get_issue_tracker_backend() if issue_key else "unlinked"

        # Format last active
        last_active_str = ""
        if session.last_active:
            last_active_str = session.last_active.strftime("%Y-%m-%d %H:%M")

        return {
            "name": session.name,
            "status": session.status or "unknown",
            "workspace": workspace,
            "issue_key": issue_key,
            "issue_tracker": issue_tracker,
            "issue_url": self.get_issue_url(issue_key) if issue_key else None,
            "goal": session.goal or "",
            "time": time_str,
            "last_active": last_active_str,
            "session_type": session.session_type or "development",
        }

    def _session_to_detail_dict(self, session: Session) -> Dict[str, Any]:
        """Convert a Session to a detailed dictionary for the detail page.

        Args:
            session: Session model instance.

        Returns:
            Dictionary with all session fields for detail display.
        """
        base = self._session_to_dict(session)

        # Add conversations, including archived conversations for repositories
        # that have been reopened or rotated over time.
        conversations = []
        for working_dir, conv in session.conversations.items():
            contexts = (
                conv.get_all_sessions() if hasattr(conv, "get_all_sessions") else [conv]
            )
            for context in contexts:
                conversations.append(
                    {
                        "working_dir": working_dir,
                        "project_path": getattr(context, "project_path", "") or "",
                        "branch": getattr(context, "branch", "") or "",
                        "session_id": getattr(context, "ai_agent_session_id", "") or "",
                        "message_count": getattr(context, "message_count", 0) or 0,
                        "prs": getattr(context, "prs", []) or [],
                        "archived": bool(getattr(context, "archived", False)),
                        "summary": getattr(context, "summary", None) or "",
                        "created": self._format_datetime(
                            getattr(context, "created", None)
                        ),
                        "last_active": self._format_datetime(
                            getattr(context, "last_active", None)
                        ),
                    }
                )

        base["conversations"] = conversations

        # Add work sessions
        work_sessions = []
        for ws in session.work_sessions:
            ws_dict: Dict[str, Any] = {
                "start": ws.start.strftime("%Y-%m-%d %H:%M") if ws.start else "",
                "end": ws.end.strftime("%Y-%m-%d %H:%M") if ws.end else "Active",
                "duration": ws.duration or "",
                "user": ws.user or "",
            }
            work_sessions.append(ws_dict)

        base["work_sessions"] = work_sessions
        base["time_tracking_state"] = session.time_tracking_state or "paused"
        base["tags"] = session.tags or []
        base["created"] = (
            session.created.strftime("%Y-%m-%d %H:%M") if session.created else ""
        )
        base["issue_url"] = self.get_issue_url(session.issue_key or "")

        return base

    @staticmethod
    def _format_datetime(value: Any) -> str:
        """Format a datetime-like value for the web UI."""
        return value.strftime("%Y-%m-%d %H:%M") if hasattr(value, "strftime") else ""

    def _get_issue_tracker_backend(self) -> str:
        """Return the configured issue tracker backend for display and calls."""
        try:
            config = self.config_loader.load_config()
            backend = getattr(config, "issue_tracker_backend", "jira")
            return backend.lower() if isinstance(backend, str) else "jira"
        except Exception:
            return "jira"

    def _get_issue_tracker_config(self) -> Any:
        """Return the configured backend section, if available."""
        try:
            config = self.config_loader.load_config()
            return getattr(config, self._get_issue_tracker_backend(), None)
        except Exception:
            return None

    def get_issue_url(self, issue_key: str) -> Optional[str]:
        """Build an external issue URL without making a network request."""
        if not issue_key:
            return None

        backend = self._get_issue_tracker_backend()
        tracker_config = self._get_issue_tracker_config()
        if backend == "jira":
            base_url = getattr(tracker_config, "url", "")
            if not isinstance(base_url, str) or not base_url:
                return None
            return f"{base_url.rstrip('/')}/browse/{quote(issue_key, safe='')}"

        repository = getattr(tracker_config, "repository", None)
        if not isinstance(repository, str):
            repository = None
        if "#" in issue_key:
            issue_repository, number = issue_key.rsplit("#", 1)
            if issue_repository:
                repository = issue_repository
        else:
            number = issue_key.lstrip("#")
        if not repository or not number:
            return None

        if backend == "github":
            api_url = getattr(tracker_config, "api_url", "https://api.github.com")
            if not isinstance(api_url, str):
                api_url = "https://api.github.com"
            host = api_url.split("/api/", 1)[0].rstrip("/")
            if host == "https://api.github.com":
                host = "https://github.com"
            return f"{host}/{repository}/issues/{quote(number, safe='')}"
        if backend == "gitlab":
            api_url = getattr(tracker_config, "api_url", "https://gitlab.com/api/v4")
            if not isinstance(api_url, str):
                api_url = "https://gitlab.com/api/v4"
            host = api_url.split("/api/", 1)[0].rstrip("/")
            return f"{host}/{quote(repository, safe='/')}/-/issues/{quote(number, safe='')}"
        return None

    def _create_issue_tracker_client(self) -> Any:
        """Create the configured issue tracker client for a web request."""
        from devflow.issue_tracker.factory import create_issue_tracker_client

        tracker_config = self._get_issue_tracker_config()
        backend = self._get_issue_tracker_backend()
        repository = getattr(tracker_config, "repository", None)
        hostname = getattr(tracker_config, "hostname", None)
        if not isinstance(repository, str):
            repository = None
        if not isinstance(hostname, str):
            hostname = None
        return create_issue_tracker_client(
            backend=backend,
            repository=repository,
            hostname=hostname,
        )

    def get_issue_details(self, issue_key: str) -> Optional[Dict[str, Any]]:
        """Fetch detailed issue data for the issue tracker page."""
        try:
            client = self._create_issue_tracker_client()
            try:
                details = client.get_ticket_detailed(
                    issue_key,
                    include_changelog=True,
                    include_comments=True,
                )
            except TypeError:
                details = client.get_ticket_detailed(
                    issue_key,
                    include_changelog=True,
                )
            if isinstance(details, dict):
                details.setdefault("url", self.get_issue_url(issue_key))
                return details
        except Exception:
            return None
        return None

    def add_issue_comment(self, issue_key: str, comment: str) -> bool:
        """Add a comment to an issue through the configured backend."""
        if not comment.strip():
            return False
        try:
            client = self._create_issue_tracker_client()
            client.add_comment(issue_key, comment.strip())
            return True
        except Exception:
            return False

    # ------------------------------------------------------------------
    # Configuration read / write
    # ------------------------------------------------------------------

    def load_config(self) -> Optional[Config]:
        """Load the full Config object.

        Returns:
            Config instance or None if not available.
        """
        return self.config_loader.load_config()

    def save_config(self, config: Config) -> bool:
        """Save the Config object (with backup).

        Args:
            config: Config instance to save.

        Returns:
            True on success, False on error.
        """
        try:
            # Create backup before saving
            import shutil

            config_file = self.config_loader.config_file
            if config_file.exists():
                config_dir = getattr(self.config_loader, "config_dir", None)
                if not isinstance(config_dir, Path):
                    config_dir = get_cs_home()
                backup_dir = config_dir / "backups"
                backup_dir.mkdir(parents=True, exist_ok=True)
                ts = datetime.now().strftime("%Y%m%d-%H%M%S")
                shutil.copy2(config_file, backup_dir / f"config-{ts}.json")

            self.config_loader.save_config(config)
            return True
        except Exception:
            return False

    def get_config_as_json(self, config: Config) -> str:
        """Serialize Config to indented JSON for preview.

        Args:
            config: Config instance.

        Returns:
            JSON string.
        """
        import json

        return json.dumps(
            config.model_dump(by_alias=True, exclude_none=True),
            indent=2,
            default=str,
        )

    def get_enterprise_config(self) -> Optional[Dict[str, Any]]:
        """Load enterprise config as a dictionary.

        Returns:
            Dictionary representation or None.
        """
        ec = self.config_loader._load_enterprise_config()
        if ec is None:
            return None
        return ec.model_dump() if hasattr(ec, "model_dump") else {}

    def get_team_config(self) -> Optional[Dict[str, Any]]:
        """Load team config as a dictionary.

        Returns:
            Dictionary representation or None.
        """
        tc = self.config_loader._load_team_config()
        if tc is None:
            return None
        return tc.model_dump() if hasattr(tc, "model_dump") else {}

    def get_organization_config(self) -> Optional[Dict[str, Any]]:
        """Load organization config as a dictionary.

        Returns:
            Dictionary representation or None.
        """
        oc = self.config_loader._load_organization_config()
        if oc is None:
            return None
        return oc.model_dump() if hasattr(oc, "model_dump") else {}

    # ------------------------------------------------------------------
    # Time tracking helpers
    # ------------------------------------------------------------------

    def get_time_tracking_data(self) -> List[Dict[str, Any]]:
        """Get time tracking data for all sessions.

        Returns:
            List of dicts with session name, total time, work sessions.
        """
        manager = self._get_manager()
        sessions = manager.list_sessions()
        data = []
        for session in sessions:
            total_minutes = 0
            entries = []
            for ws in session.work_sessions:
                start = ws.start
                end = ws.end or datetime.now()
                if start:
                    delta = end - start
                    mins = int(delta.total_seconds() / 60)
                    total_minutes += mins
                    entries.append(
                        {
                            "start": start.strftime("%Y-%m-%d %H:%M"),
                            "end": (
                                ws.end.strftime("%Y-%m-%d %H:%M")
                                if ws.end
                                else "Active"
                            ),
                            "minutes": mins,
                            "user": ws.user or "",
                        }
                    )
            hours = total_minutes // 60
            minutes = total_minutes % 60
            data.append(
                {
                    "name": session.name,
                    "issue_key": session.issue_key or "",
                    "status": session.status or "unknown",
                    "total_time": f"{hours}h {minutes}m",
                    "total_minutes": total_minutes,
                    "entries": entries,
                }
            )
        return data
