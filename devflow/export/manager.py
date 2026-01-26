"""Export and import manager for DevAIFlow."""

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


class ExportManager(ArchiveManagerBase):
    """Manage export and import operations.

    Inherits shared archive functionality from ArchiveManagerBase.
    """

    def __init__(self, config_loader: Optional[ConfigLoader] = None):
        """Initialize the export manager.

        Args:
            config_loader: ConfigLoader instance. Defaults to new instance.
        """
        super().__init__(config_loader)

    def export_sessions(
        self,
        identifiers: Optional[List[str]] = None,
        output_path: Optional[Path] = None,
    ) -> Path:
        """Export one or more sessions for team handoff.

        Always includes ALL conversations and conversation history.
        Each session represents one issue tracker ticket's complete work.

        Args:
            identifiers: List of session identifiers (names or JIRA keys) to export. If None, exports all sessions.
            output_path: Output file path. Defaults to timestamped export file.

        Returns:
            Path to created export file
        """
        sessions_index = self.config_loader.load_sessions()

        # Determine which sessions to export
        if identifiers is None:
            # Export all sessions
            sessions_to_export = sessions_index.sessions
        else:
            # Export specific sessions using smart lookup
            sessions_to_export = {}
            for identifier in identifiers:
                session = sessions_index.get_session(identifier)
                if session:
                    sessions_to_export[session.name] = session

        if not sessions_to_export:
            raise ValueError("No sessions found to export")

        # Generate output path if not provided
        if output_path is None:
            # Load config to get workspace (create default if doesn't exist)
            config = self.config_loader.load_config()
            if not config:
                config = self.config_loader.create_default_config()

            workspace_path = config.repos.get_default_workspace_path() if config and config.repos else None
            if workspace_path:
                workspace = Path(workspace_path)
                # Ensure workspace directory exists
                workspace.mkdir(parents=True, exist_ok=True)
            else:
                # Fall back to home directory if no workspace configured
                workspace = Path.home()

            if identifiers and len(identifiers) == 1:
                # Single session export - use issue key if available, otherwise session name
                session = list(sessions_to_export.values())[0]
                if session:
                    issue_key = session.issue_key
                    if issue_key:
                        output_path = workspace / f"{issue_key}-session-export.tar.gz"
                    else:
                        # Fall back to session name if no issue key
                        output_path = workspace / f"{identifiers[0]}-session-export.tar.gz"
                else:
                    # Should not happen but handle gracefully
                    output_path = workspace / f"{identifiers[0]}-session-export.tar.gz"
            else:
                # Multiple sessions - use count-based naming in workspace
                count = len(sessions_to_export)
                output_path = workspace / f"{count}sessions-session-export.tar.gz"

        # Capture git remote URLs before creating export data
        from devflow.git.utils import GitUtils
        for session_name, session in sessions_to_export.items():
            # Capture remote URL for each conversation 
            if session.conversations:
                for working_dir, conversation in session.conversations.items():
                    # Process all sessions (active + archived) in this Conversation
                    for conv in conversation.get_all_sessions():
                        if conv.project_path and not conv.remote_url:
                            remote_url = GitUtils.get_remote_url(Path(conv.project_path))
                            if remote_url:
                                conv.remote_url = remote_url
            # Fallback: Support legacy single-conversation sessions
            elif session.project_path and not hasattr(session, 'remote_url'):
                remote_url = GitUtils.get_remote_url(Path(session.project_path))
                if remote_url:
                    session.remote_url = remote_url

        # Create export data (always includes conversations for team handoff)
        export_data = self._create_export_data(sessions_to_export)

        # Create tar.gz archive
        with tarfile.open(output_path, "w:gz") as tar:
            # Add export metadata
            self._add_json_to_tar(tar, "export-metadata.json", export_data["metadata"])

            # Add sessions data
            self._add_json_to_tar(tar, "sessions.json", export_data["sessions"])

            # Add session directories (metadata, notes, etc.)
            for group_name in sessions_to_export.keys():
                session_dir = self.config_loader.get_session_dir(group_name)
                if session_dir.exists():
                    tar.add(session_dir, arcname=f"sessions/{group_name}")

            # Add conversation history (always included for team handoff)
            for session_name, session in sessions_to_export.items():
                # Export ALL conversations in the session 
                if session.conversations:
                    for working_dir, conversation in session.conversations.items():
                        # Process all sessions (active + archived) in this Conversation
                        for conv in conversation.get_all_sessions():
                            if conv.ai_agent_session_id:
                                jsonl_path = self._find_conversation_file(conv.ai_agent_session_id)
                                if jsonl_path and jsonl_path.exists():
                                    # Include working_dir in arcname for clarity
                                    arcname = f"conversations/{session_name}-{working_dir}-{conv.ai_agent_session_id}.jsonl"
                                    tar.add(jsonl_path, arcname=arcname)
                # Fallback: Support legacy single-conversation sessions
                elif session.ai_agent_session_id:
                    jsonl_path = self._find_conversation_file(session.ai_agent_session_id)
                    if jsonl_path and jsonl_path.exists():
                        arcname = f"conversations/{session_name}-{session.ai_agent_session_id}.jsonl"
                        tar.add(jsonl_path, arcname=arcname)

            # Add mock data if in mock mode
            # This is needed for collaboration workflow tests where sessions are exported/imported
            # between different DEVAIFLOW_HOME environments
            from devflow.utils import is_mock_mode
            if is_mock_mode():
                mocks_dir = get_cs_home() / "mocks"
                if mocks_dir.exists():
                    tar.add(mocks_dir, arcname="mocks")

            # Note: Diagnostic logs are NOT included in session exports
            # They contain global system logs from ALL sessions and would leak data.
            # Session exports are for targeted team handoffs (session-specific data only).
            # For full system backups with diagnostic logs, use 'daf backup' instead.

        return output_path

    def peek_export_file(self, export_path: Path) -> Dict:
        """Peek at export file metadata without full extraction.

        Args:
            export_path: Path to export file

        Returns:
            Dictionary with metadata and session keys:
            {
                "session_count": int,
                "session_keys": List[str],
                "created": str
            }

        Raises:
            FileNotFoundError: If export file doesn't exist
            ValueError: If export file is invalid or is a backup file
        """
        if not export_path.exists():
            raise FileNotFoundError(f"Export file not found: {export_path}")

        # Extract only metadata files to temp directory
        temp_dir = get_cs_home() / ".peek-temp"
        temp_dir.mkdir(exist_ok=True)

        try:
            with tarfile.open(export_path, "r:gz") as tar:
                # Extract only metadata files
                for member in tar.getmembers():
                    if member.name in ["export-metadata.json", "backup-metadata.json", "sessions.json"]:
                        tar.extract(member, temp_dir)

            # Validate archive type (reject backup files)
            metadata_file = temp_dir / "export-metadata.json"
            backup_metadata_file = temp_dir / "backup-metadata.json"

            if backup_metadata_file.exists():
                raise ValueError(
                    "This is a backup archive created by 'daf backup'. "
                    "Use 'daf restore' to restore backup files. "
                    "For team handoff, use 'daf export' instead."
                )

            # Read export metadata
            metadata = {}
            if metadata_file.exists():
                with open(metadata_file, "r") as f:
                    metadata = json.load(f)

                # Double-check archive type
                if metadata.get("archive_type") == "backup":
                    raise ValueError(
                        "This is a backup archive. Use 'daf restore' to restore backup files."
                    )

            # Read sessions data
            sessions_file = temp_dir / "sessions.json"
            if not sessions_file.exists():
                raise ValueError("Invalid export file: sessions.json not found")

            with open(sessions_file, "r") as f:
                exported_sessions_data = json.load(f)

            # Extract session keys (group names which are typically JIRA keys)
            session_keys = list(exported_sessions_data.keys())

            return {
                "session_count": metadata.get("session_count", len(session_keys)),
                "session_keys": session_keys,
                "created": metadata.get("created", "unknown"),
            }

        finally:
            # Clean up temp directory
            shutil.rmtree(temp_dir, ignore_errors=True)

    def import_sessions(self, export_path: Path, merge: bool = True) -> List[str]:
        """Import sessions from an export file.

        Args:
            export_path: Path to export file
            merge: If True, merge with existing sessions. If False, replace conflicting sessions.

        Returns:
            List of imported JIRA keys
        """
        if not export_path.exists():
            raise FileNotFoundError(f"Export file not found: {export_path}")

        # Extract to temporary directory
        temp_dir = get_cs_home() / ".import-temp"
        temp_dir.mkdir(exist_ok=True)

        imported_keys = []

        try:
            with tarfile.open(export_path, "r:gz") as tar:
                tar.extractall(temp_dir)

            # Validate archive type (reject backup files)
            metadata_file = temp_dir / "export-metadata.json"
            backup_metadata_file = temp_dir / "backup-metadata.json"

            if backup_metadata_file.exists():
                raise ValueError(
                    "This is a backup archive created by 'daf backup'. "
                    "Use 'daf restore' to restore backup files. "
                    "For team handoff, use 'daf export' instead."
                )

            # Read export metadata
            if metadata_file.exists():
                with open(metadata_file, "r") as f:
                    metadata = json.load(f)

                    # Double-check archive type
                    if metadata.get("archive_type") == "backup":
                        raise ValueError(
                            "This is a backup archive. Use 'daf restore' to restore backup files."
                        )

            # Read sessions data
            sessions_file = temp_dir / "sessions.json"
            if not sessions_file.exists():
                raise ValueError("Invalid export file: sessions.json not found")

            with open(sessions_file, "r") as f:
                exported_sessions_data = json.load(f)

            # Load existing sessions
            existing_sessions = self.config_loader.load_sessions()

            # Import each session
            for session_name, session_data in exported_sessions_data.items():
                # Check if session already exists
                if session_name in existing_sessions.sessions and merge:
                    # Skip if exists and merging
                    continue

                # session_data can be either a dict (new format) or a list (old format)
                if isinstance(session_data, list):
                    # Old format: list of sessions - take the first one
                    # (multi-session format is no longer supported, use single session with multiple conversations)
                    session_dict = session_data[0] if session_data else {}
                else:
                    # New format: single session dict
                    session_dict = session_data

                session = Session(**session_dict)
                # Migrate conversation paths to use current workspace
                self._migrate_session_paths(session)

                existing_sessions.sessions[session_name] = session

                imported_keys.append(session_name)

                # Copy session directory
                export_session_dir = temp_dir / "sessions" / session_name
                if export_session_dir.exists():
                    target_dir = self.config_loader.get_session_dir(session_name)
                    if target_dir.exists() and not merge:
                        shutil.rmtree(target_dir)
                    shutil.copytree(export_session_dir, target_dir, dirs_exist_ok=True)

            # Save updated sessions index
            self.config_loader.save_sessions(existing_sessions)

            # Import conversation history files if present
            conversations_dir = temp_dir / "conversations"
            if conversations_dir.exists():
                claude_dir = Path.home() / ".claude" / "projects"
                if not claude_dir.exists():
                    claude_dir.mkdir(parents=True)

                for conversation_file in conversations_dir.glob("*.jsonl"):
                    # Parse filename to extract UUID
                    # Format: {group_name}-{session_id}-{working_dir}-{UUID}.jsonl
                    # where UUID is always the last 5 dash-separated parts
                    parts = conversation_file.stem.rsplit("-", 5)
                    if len(parts) < 6:
                        # Invalid format, skip
                        continue

                    ai_agent_session_id = "-".join(parts[-5:])

                    # IMPORTANT: Use session metadata FIRST
                    # The conversation file may contain paths from the exporter's machine,
                    # but we need to place it at the importer's project path.
                    project_path = None

                    # Find the session that owns this conversation by matching the ai_agent_session_id
                    for session_name, session in existing_sessions.sessions.items():
                        # Check all conversations in the session 
                        if session.conversations:
                            for conversation in session.conversations.values():
                                # Iterate through all sessions (active + archived) in this Conversation
                                for conv in conversation.get_all_sessions():
                                    if conv.ai_agent_session_id == ai_agent_session_id:
                                        # For ticket_creation sessions with temp_directory,
                                        # use original_project_path for conversation storage
                                        if conv.temp_directory and conv.original_project_path:
                                            project_path = conv.original_project_path
                                        else:
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
                        encoded_path = self._encode_path(project_path)
                        target_dir = claude_dir / encoded_path
                        target_dir.mkdir(parents=True, exist_ok=True)

                        target_file = target_dir / f"{ai_agent_session_id}.jsonl"
                        if not target_file.exists() or not merge:
                            shutil.copy2(conversation_file, target_file)

            # Import mock data if present (for mock mode testing)
            # This is needed for collaboration workflow tests where sessions are exported/imported
            # between different DEVAIFLOW_HOME environments
            mocks_dir = temp_dir / "mocks"
            if mocks_dir.exists():
                from devflow.utils import is_mock_mode
                if is_mock_mode():
                    target_mocks_dir = get_cs_home() / "mocks"
                    if target_mocks_dir.exists() and not merge:
                        shutil.rmtree(target_mocks_dir)
                    shutil.copytree(mocks_dir, target_mocks_dir, dirs_exist_ok=True)

            # Note: Diagnostic logs are NOT restored from session exports
            # Session exports don't include global system logs (only session-specific data).
            # Diagnostic logs are only included in full system backups created with 'daf backup'.

            # Verify repository existence and warn about missing ones
            # Only check the newly imported sessions, not all existing sessions
            config = self.config_loader.load_config()
            workspace = config.repos.get_default_workspace_path() if config and config.repos else None

            # Create a sessions index with only the imported sessions
            from devflow.config.models import SessionIndex
            imported_sessions_only = SessionIndex(sessions={})
            for group_name in imported_keys:
                if group_name in existing_sessions.sessions:
                    imported_sessions_only.sessions[group_name] = existing_sessions.sessions[group_name]

            missing_repos = self._check_missing_repositories(imported_sessions_only, workspace)
            if missing_repos:
                self._display_missing_repository_warning(missing_repos, workspace)

        finally:
            # Clean up temp directory
            shutil.rmtree(temp_dir, ignore_errors=True)

        return imported_keys

    def _create_export_data(
        self,
        sessions: Dict[str, Session],
    ) -> Dict:
        """Create export data structure.

        Always includes conversations for team handoff.

        Args:
            sessions: Sessions to export (Dict[str, Session])

        Returns:
            Export data dictionary
        """
        # Count total sessions
        total_sessions = len(sessions)

        return {
            "metadata": {
                "version": "1.0",
                "archive_type": "export",
                "created": datetime.now().isoformat(),
                "session_count": total_sessions,
                "includes_conversations": True,  # Always True for team handoff
            },
            "sessions": {
                session_name: session.model_dump(mode='json', exclude={'workspace_name'})
                for session_name, session in sessions.items()
            }
        }


    def _migrate_session_paths(self, session: Session) -> None:
        """Reconstruct conversation paths using current workspace.

        This method reconstructs absolute paths from relative paths when importing sessions.
        If conversations have relative_path set, we use the current workspace to rebuild
        the full path. This enables portable session export/import across different machines.

        Args:
            session: Session to migrate
        """
        config = self.config_loader.load_config()
        if not config:
            return

        workspace = config.repos.get_default_workspace_path() if config.repos else None

        for working_dir, conversation in session.conversations.items():
            # Process all sessions (active + archived) in this Conversation
            for conv in conversation.get_all_sessions():
                # If conversation has relative_path, reconstruct project_path from workspace
                if conv.relative_path and workspace:
                    new_project_path = conv.get_project_path(workspace)
                    conv.project_path = new_project_path
                # If no relative_path but has project_path, compute it from workspace
                elif conv.project_path and workspace and not conv.relative_path:
                    from pathlib import Path
                    workspace_path = Path(workspace).expanduser().resolve()
                    project_path = Path(conv.project_path).expanduser().resolve()

                    # Try to compute relative path
                    try:
                        rel_path = project_path.relative_to(workspace_path)
                        conv.relative_path = str(rel_path)
                        conv.repo_name = project_path.name
                    except ValueError:
                        # Project not in workspace, just set repo_name
                        conv.repo_name = project_path.name

    def _check_missing_repositories(
        self, sessions_index: "SessionsIndex", workspace: Optional[str]
    ) -> List[Dict]:
        """Check which repositories are missing from workspace.

        Args:
            sessions_index: SessionsIndex containing imported sessions
            workspace: Workspace root directory

        Returns:
            List of dicts with missing repo info:
            [{
                'repo_name': str,
                'project_path': str,
                'session_name': str,
                'issue_key': str,
                'remote_url': Optional[str]
            }]
        """
        from devflow.git.utils import GitUtils

        missing_repos = []
        seen_paths = set()  # Track unique missing paths

        for session_name, session in sessions_index.sessions.items():
            # Check each conversation in the session 
            for working_dir, conversation in session.conversations.items():
                # Process all sessions (active + archived) in this Conversation
                for conv in conversation.get_all_sessions():
                    project_path = None

                    # Get the project path
                    if conv.project_path:
                        project_path = conv.project_path
                    elif conv.relative_path and workspace:
                        project_path = conv.get_project_path(workspace)

                    if not project_path:
                        continue

                    # Check if repository exists
                    path_obj = Path(project_path)
                    if not path_obj.exists():
                        # Avoid duplicates
                        if project_path not in seen_paths:
                            seen_paths.add(project_path)

                            # Get repository name
                            repo_name = conv.get_repo_name()

                            # Try to get remote URL if available
                            remote_url = conv.remote_url

                            missing_repos.append({
                                'repo_name': repo_name,
                                'project_path': project_path,
                                'session_name': session.name,
                                'issue_key': session.issue_key,
                                'remote_url': remote_url
                            })

        return missing_repos

    def _display_missing_repository_warning(
        self, missing_repos: List[Dict], workspace: Optional[str]
    ) -> None:
        """Display warning about missing repositories with clone instructions.

        Args:
            missing_repos: List of missing repository info dicts
            workspace: Workspace root directory
        """
        from rich.console import Console
        from rich.panel import Panel
        from rich.text import Text

        console = Console()

        # Display warning header
        console.print()
        console.print("[yellow]⚠  Missing repositories detected[/yellow]")
        console.print()
        console.print(
            "The following repositories are referenced by imported sessions but not found in your workspace:"
        )
        console.print()

        # Display each missing repository
        for repo_info in missing_repos:
            repo_name = repo_info['repo_name']
            project_path = repo_info['project_path']
            session_name = repo_info['session_name']
            issue_key = repo_info.get('issue_key', 'N/A')
            remote_url = repo_info.get('remote_url')

            # Create info text
            info_text = Text()
            info_text.append(f"  Repository: ", style="bold")
            info_text.append(f"{repo_name}\n", style="cyan")
            info_text.append(f"  Expected path: ", style="bold")
            info_text.append(f"{project_path}\n", style="dim")
            info_text.append(f"  Session: ", style="bold")
            info_text.append(f"{issue_key} ({session_name})\n", style="yellow")

            console.print(info_text)

            # Display clone instructions
            console.print("  [bold]Please clone this repository before opening the session:[/bold]")
            console.print()

            if remote_url:
                # We have the remote URL - provide exact clone command
                console.print(f"    [green]Option 1 - Clone to workspace (recommended):[/green]")
                if workspace:
                    console.print(f"      cd {workspace}")
                console.print(f"      git clone {remote_url} {repo_name}")
                console.print()
                console.print(f"    [green]Option 2 - Clone from a different fork/branch:[/green]")
                console.print(f"      # Ask your teammate for their fork URL and branch")
                console.print(f"      git clone <fork-url> {repo_name}")
            else:
                # No remote URL - provide general instructions
                console.print(f"    [green]Option 1 - Clone to workspace (recommended):[/green]")
                if workspace:
                    console.print(f"      cd {workspace}")
                console.print(f"      git clone <remote-url> {repo_name}")
                console.print()
                console.print(f"    [green]Option 2 - Use existing clone elsewhere:[/green]")
                console.print(f"      When you run 'daf open {issue_key}', you'll be prompted to select the directory")

            console.print()
            console.print("  [dim]→ Tip: Ask your teammate for the git remote URL and preferred branch[/dim]")
            console.print()

        # Summary footer
        console.print(
            f"[yellow]You can still work with imported sessions, but you'll need to clone the repositories before opening them.[/yellow]"
        )

