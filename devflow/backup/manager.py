"""Backup and restore manager for DevAIFlow."""

import json
import shutil
import tarfile
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from devflow.archive.base import ArchiveManagerBase
from devflow.config.loader import ConfigLoader
from devflow.config.models import Session
from devflow.utils.paths import get_cs_home


class BackupManager(ArchiveManagerBase):
    """Manage backup and restore operations.

    Inherits shared archive functionality from ArchiveManagerBase.
    """

    def __init__(self, config_loader: Optional[ConfigLoader] = None):
        """Initialize the backup manager.

        Args:
            config_loader: ConfigLoader instance. Defaults to new instance.
        """
        super().__init__(config_loader)

    def create_backup(self, output_path: Optional[Path] = None) -> Path:
        """Create a complete backup of all sessions.

        Includes:
        - sessions.json (main index)
        - All session directories (metadata, notes, etc.)
        - All conversation history (.jsonl files)

        Args:
            output_path: Output file path. Defaults to timestamped backup file.

        Returns:
            Path to created backup file
        """
        if output_path is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = get_cs_home() / f"backups/devaiflow-backup-{timestamp}.tar.gz"
            output_path.parent.mkdir(parents=True, exist_ok=True)

        backup_data = self._collect_backup_data()

        # Create tar.gz archive
        with tarfile.open(output_path, "w:gz") as tar:
            # Add backup metadata
            self._add_json_to_tar(tar, "backup-metadata.json", {
                "version": "1.0",
                "archive_type": "backup",
                "created": datetime.now().isoformat()
            })

            # Add sessions.json
            sessions_file = self.config_loader.sessions_file
            if sessions_file.exists():
                tar.add(sessions_file, arcname="sessions.json")

            # Add all session directories
            sessions_dir = self.config_loader.sessions_dir
            if sessions_dir.exists():
                tar.add(sessions_dir, arcname="sessions")

            # Add conversation history files
            for session_name, session_data in backup_data["sessions"].items():
                # Iterate over conversations in the session
                conversations = session_data.get("conversations", {})
                for working_dir, conversation in conversations.items():
                    ai_agent_session_id = conversation.get("ai_agent_session_id")
                    if ai_agent_session_id:
                        jsonl_path = self._find_conversation_file(ai_agent_session_id)
                        if jsonl_path and jsonl_path.exists():
                            # Store with a recognizable name
                            arcname = f"conversations/{session_name}-{working_dir}-{ai_agent_session_id}.jsonl"
                            tar.add(jsonl_path, arcname=arcname)

            # Add diagnostic logs
            self._add_diagnostic_logs(tar)

        return output_path

    def restore_backup(self, backup_path: Path, merge: bool = False) -> None:
        """Restore from a complete backup.

        Args:
            backup_path: Path to backup file
            merge: If True, merge with existing sessions. If False, replace all.
        """
        if not backup_path.exists():
            raise FileNotFoundError(f"Backup file not found: {backup_path}")

        # Extract to temporary directory
        temp_dir = get_cs_home() / ".restore-temp"
        temp_dir.mkdir(exist_ok=True)

        try:
            with tarfile.open(backup_path, "r:gz") as tar:
                tar.extractall(temp_dir)

            # Validate archive type (reject export files)
            export_metadata_file = temp_dir / "export-metadata.json"
            backup_metadata_file = temp_dir / "backup-metadata.json"

            if export_metadata_file.exists():
                raise ValueError(
                    "This is an export archive created by 'daf export'. "
                    "Use 'daf import' to import exported sessions. "
                    "For complete system backup, use 'daf backup' instead."
                )

            # Read backup metadata if exists
            if backup_metadata_file.exists():
                with open(backup_metadata_file, "r") as f:
                    metadata = json.load(f)

                    # Double-check archive type
                    if metadata.get("archive_type") == "export":
                        raise ValueError(
                            "This is an export archive. Use 'daf import' to import exported sessions."
                        )

            # Restore sessions.json
            sessions_json = temp_dir / "sessions.json"
            if sessions_json.exists():
                if merge:
                    # Merge with existing sessions
                    existing_sessions = self.config_loader.load_sessions()
                    with open(sessions_json, "r") as f:
                        backup_data = json.load(f)

                    backup_sessions_data = backup_data.get("sessions", {})

                    for session_name, session_data in backup_sessions_data.items():
                        # Skip if session already exists and merge is enabled
                        if session_name not in existing_sessions.sessions:
                            # session_data can be dict (new format) or list (old format)
                            if isinstance(session_data, list):
                                # Old format: take first session
                                session_dict = session_data[0] if session_data else {}
                            else:
                                # New format: single session dict
                                session_dict = session_data
                            existing_sessions.sessions[session_name] = Session(**session_dict)

                    self.config_loader.save_sessions(existing_sessions)
                else:
                    # Replace all sessions
                    shutil.copy2(sessions_json, self.config_loader.sessions_file)

            # Restore session directories
            backup_sessions_dir = temp_dir / "sessions"
            if backup_sessions_dir.exists():
                if not merge:
                    # Clear existing sessions directory
                    if self.config_loader.sessions_dir.exists():
                        shutil.rmtree(self.config_loader.sessions_dir)
                    self.config_loader.sessions_dir.mkdir(parents=True, exist_ok=True)

                # Copy session directories
                for session_dir in backup_sessions_dir.iterdir():
                    if session_dir.is_dir():
                        target_dir = self.config_loader.sessions_dir / session_dir.name
                        if target_dir.exists() and merge:
                            # Skip if exists and merging
                            continue
                        shutil.copytree(session_dir, target_dir, dirs_exist_ok=True)

            # Restore conversation history files
            conversations_dir = temp_dir / "conversations"
            if conversations_dir.exists():
                # Find Claude's projects directory
                claude_dir = Path.home() / ".claude" / "projects"
                if not claude_dir.exists():
                    claude_dir.mkdir(parents=True)

                # Load the restored sessions for fallback lookup
                restored_sessions = self.config_loader.load_sessions()

                for conversation_file in conversations_dir.glob("*.jsonl"):
                    # Parse filename to extract UUID
                    # Format: {group_name}-{session_id}-{working_dir}-{UUID}.jsonl
                    # where UUID is always the last 5 dash-separated parts
                    parts = conversation_file.stem.rsplit("-", 5)  # Split on last 5 dashes (UUID has 4)
                    if len(parts) < 6:
                        # Invalid format, skip
                        continue

                    ai_agent_session_id = "-".join(parts[-5:])  # Reconstruct UUID

                    # IMPORTANT: Use session metadata FIRST
                    # The conversation file may contain paths from the backup source machine,
                    # but we need to place it at the restore target's project path.
                    project_path = None

                    # Find the session that owns this conversation by matching the ai_agent_session_id
                    for session_name, session in restored_sessions.sessions.items():
                        # Check all conversations in the session 
                        if session.conversations:
                            for conversation in session.conversations.values():
                                # Iterate through all sessions (active + archived) in this Conversation
                                for conv in conversation.get_all_sessions():
                                    if conv.ai_agent_session_id == ai_agent_session_id:
                                        project_path = conv.project_path
                                        break
                                if project_path:
                                    break
                        if project_path:
                            break

                    # Fallback: If no session metadata, scan conversation file for cwd
                    # This handles edge cases where session metadata is incomplete
                    if not project_path:
                        with open(conversation_file, "r") as f:
                            for line in f:
                                try:
                                    msg = json.loads(line)
                                    if "cwd" in msg:
                                        project_path = msg["cwd"]
                                        break
                                except json.JSONDecodeError:
                                    continue

                    # Copy conversation file if we found a project_path
                    if project_path:
                        # Encode path like Claude does
                        encoded_path = self._encode_path(project_path)
                        target_dir = claude_dir / encoded_path
                        target_dir.mkdir(parents=True, exist_ok=True)

                        # Copy conversation file
                        target_file = target_dir / f"{ai_agent_session_id}.jsonl"
                        shutil.copy2(conversation_file, target_file)

            # Restore diagnostic logs
            self._restore_diagnostic_logs(temp_dir)

        finally:
            # Clean up temp directory
            shutil.rmtree(temp_dir, ignore_errors=True)

    def _collect_backup_data(self) -> Dict:
        """Collect all backup data.

        Returns:
            Dictionary with backup metadata and session data
        """
        sessions_index = self.config_loader.load_sessions()

        backup_data = {
            "version": "1.0",
            "archive_type": "backup",
            "created": datetime.now().isoformat(),
            "sessions": {}
        }

        # sessions is now a Dict[str, Session]
        for session_name, session in sessions_index.sessions.items():
            # Convert session to dict (use mode='json' for datetime serialization)
            backup_data["sessions"][session_name] = session.model_dump(mode='json')

        return backup_data
