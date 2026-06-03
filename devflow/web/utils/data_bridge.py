"""Bridge between DevAIFlow data layers and the web dashboard.

This module provides a clean interface for the web UI to access session data,
configuration, and notes without duplicating business logic. It wraps
SessionManager, ConfigLoader, and StorageBackend with web-friendly methods.
"""

from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

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
    ) -> List[Dict[str, Any]]:
        """List sessions as dictionaries suitable for the web UI.

        Args:
            status: Optional status filter (comma-separated for multiple).
            working_directory: Optional working directory filter.

        Returns:
            List of session dictionaries with display-friendly fields.
        """
        manager = self._get_manager()
        sessions = manager.list_sessions(
            status=status,
            working_directory=working_directory,
        )
        return [self._session_to_dict(s) for s in sessions]

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
        cs_home = get_cs_home()
        notes_file = cs_home / "sessions" / session_name / "notes.md"
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

        # JIRA config
        if config.jira:
            summary["jira"] = {
                "url": config.jira.url or "Not configured",
                "project": config.jira.project or "Not configured",
            }

        # GitHub config
        if config.github:
            summary["github"] = {
                "enabled": bool(config.github.repository),
                "repository": config.github.repository or "Not configured",
            }

        # Repos config
        if config.repos:
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

        # Format last active
        last_active_str = ""
        if session.last_active:
            last_active_str = session.last_active.strftime("%Y-%m-%d %H:%M")

        return {
            "name": session.name,
            "status": session.status or "unknown",
            "workspace": workspace,
            "issue_key": issue_key,
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

        # Add conversations
        conversations = []
        for working_dir, conv in session.conversations.items():
            # conv is a Conversation object containing active_session and archived_sessions
            active_ctx = conv.active_session if hasattr(conv, "active_session") else conv
            conv_dict: Dict[str, Any] = {
                "working_dir": working_dir,
                "project_path": getattr(active_ctx, "project_path", "") or "",
                "branch": getattr(active_ctx, "branch", "") or "",
                "session_id": getattr(active_ctx, "ai_agent_session_id", "") or "",
                "message_count": getattr(active_ctx, "message_count", 0) or 0,
                "prs": getattr(active_ctx, "prs", []) or [],
            }
            conversations.append(conv_dict)

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

        return base

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
                backup_dir = get_cs_home() / "backups"
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
                    entries.append({
                        "start": start.strftime("%Y-%m-%d %H:%M"),
                        "end": ws.end.strftime("%Y-%m-%d %H:%M") if ws.end else "Active",
                        "minutes": mins,
                        "user": ws.user or "",
                    })
            hours = total_minutes // 60
            minutes = total_minutes % 60
            data.append({
                "name": session.name,
                "issue_key": session.issue_key or "",
                "status": session.status or "unknown",
                "total_time": f"{hours}h {minutes}m",
                "total_minutes": total_minutes,
                "entries": entries,
            })
        return data
