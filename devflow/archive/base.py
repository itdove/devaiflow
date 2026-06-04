"""Base class for archive operations (backup/export)."""

import json
import tarfile
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from devflow.config.loader import ConfigLoader
from devflow.utils.paths import get_claude_config_dir

CONVERSATION_BACKUP_BACKENDS = {"claude", "ollama"}


class ArchiveManagerBase:
    """Base class for backup and export managers.

    Provides shared functionality for creating and extracting tar.gz archives
    containing session data and conversation history.
    """

    def __init__(self, config_loader: Optional[ConfigLoader] = None):
        """Initialize the archive manager.

        Args:
            config_loader: ConfigLoader instance. Defaults to new instance.
        """
        self.config_loader = config_loader or ConfigLoader()
        self._conversation_warnings: List[str] = []

    def _is_conversation_backupable(self, agent_backend: str) -> bool:
        """Check if an agent backend supports conversation file backup.

        Only agents that store conversations as individual files (JSONL)
        can be backed up with the current archive mechanism.

        Args:
            agent_backend: Agent backend name (e.g., "claude", "opencode")

        Returns:
            True if conversation backup is supported
        """
        return agent_backend.lower() in CONVERSATION_BACKUP_BACKENDS

    def get_conversation_warnings(self) -> List[str]:
        """Get warnings about skipped conversations.

        Returns:
            List of warning messages from the last operation
        """
        return list(self._conversation_warnings)

    def _find_conversation_file(
        self, session_id: str, agent_backend: Optional[str] = None
    ) -> Optional[Path]:
        """Find the conversation file for a session ID.

        Args:
            session_id: Agent session UUID
            agent_backend: Agent backend name. If provided and not supported,
                records a warning and returns None.

        Returns:
            Path to conversation file if found, None otherwise
        """
        if agent_backend and not self._is_conversation_backupable(agent_backend):
            return None

        claude_dir = get_claude_config_dir() / "projects"
        if not claude_dir.exists():
            return None

        for project_dir in claude_dir.iterdir():
            if project_dir.is_dir():
                jsonl_file = project_dir / f"{session_id}.jsonl"
                if jsonl_file.exists():
                    return jsonl_file

        return None

    def _add_json_to_tar(self, tar: tarfile.TarFile, arcname: str, data: Dict) -> None:
        """Add JSON data to tar archive.

        Args:
            tar: TarFile object
            arcname: Archive name for the file
            data: Data to serialize as JSON
        """
        import io

        json_str = json.dumps(data, indent=2)
        json_bytes = json_str.encode("utf-8")

        tarinfo = tarfile.TarInfo(name=arcname)
        tarinfo.size = len(json_bytes)
        tarinfo.mtime = int(datetime.now().timestamp())

        tar.addfile(tarinfo, io.BytesIO(json_bytes))

    def _encode_path(self, path: str) -> str:
        """Encode a path like Claude does.

        Args:
            path: Project path

        Returns:
            Encoded path string
        """
        # Claude Code replaces / with - in paths (keeps the leading -)
        # AND also replaces _ with - 
        return path.replace("/", "-").replace("_", "-")

    def _add_diagnostic_logs(self, tar: tarfile.TarFile) -> None:
        """Add diagnostic logs to archive.

        Includes all log files from DevAIFlow home/logs/ for debugging.

        Args:
            tar: TarFile object
        """
        from devflow.utils.paths import get_cs_home
        logs_dir = get_cs_home() / "logs"
        if logs_dir.exists():
            for log_file in logs_dir.glob("*.log"):
                arcname = f"logs/{log_file.name}"
                tar.add(log_file, arcname=arcname)

    def _restore_diagnostic_logs(self, temp_dir: Path) -> None:
        """Restore diagnostic logs from archive.

        Restores logs to a namespaced location to avoid conflicts with current logs.
        Logs are restored to DevAIFlow home/logs/imported/{timestamp}/ to preserve
        diagnostic history without polluting current logs.

        Args:
            temp_dir: Temporary directory containing extracted archive
        """
        import shutil
        from datetime import datetime
        from devflow.utils.paths import get_cs_home

        # Check if archive contains logs
        logs_dir = temp_dir / "logs"
        if not logs_dir.exists():
            return

        # Create timestamped imported logs directory
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        target_logs_dir = get_cs_home() / "logs" / "imported" / timestamp
        target_logs_dir.mkdir(parents=True, exist_ok=True)

        # Copy all log files to the namespaced location
        for log_file in logs_dir.glob("*.log"):
            target_file = target_logs_dir / log_file.name
            shutil.copy2(log_file, target_file)
