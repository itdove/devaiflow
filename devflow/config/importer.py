"""Configuration import functionality."""

import json
import shutil
import tarfile
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from rich.console import Console
from rich.table import Table

console = Console()


class ConfigImporter:
    """Import configuration files from export archive."""

    def __init__(self, config_dir: Path):
        """Initialize config importer.

        Args:
            config_dir: Configuration directory (typically ~/.daf-sessions)
        """
        self.config_dir = config_dir

    def peek_config_export(self, export_path: Path) -> Dict:
        """Peek at export file metadata without full extraction.

        Args:
            export_path: Path to config export file

        Returns:
            Dictionary with metadata:
            {
                "file_count": int,
                "files": List[str],
                "created": str,
                "warnings": List[dict]
            }

        Raises:
            FileNotFoundError: If export file doesn't exist
            ValueError: If export file is invalid
        """
        if not export_path.exists():
            raise FileNotFoundError(f"Export file not found: {export_path}")

        # Extract only metadata to temp directory
        temp_dir = self.config_dir / ".config-peek-temp"
        temp_dir.mkdir(exist_ok=True)

        try:
            with tarfile.open(export_path, "r:gz") as tar:
                # Extract only metadata file
                for member in tar.getmembers():
                    if member.name == "config-export-metadata.json":
                        tar.extract(member, temp_dir)
                        break

            # Read metadata
            metadata_file = temp_dir / "config-export-metadata.json"
            if not metadata_file.exists():
                raise ValueError("Invalid config export: metadata not found")

            with open(metadata_file, "r") as f:
                metadata = json.load(f)

            # Validate archive type
            if metadata.get("archive_type") != "config_export":
                raise ValueError(
                    f"Invalid archive type: {metadata.get('archive_type')}. "
                    "Expected config_export."
                )

            return metadata

        finally:
            # Clean up temp directory
            shutil.rmtree(temp_dir, ignore_errors=True)

    def show_import_preview(
        self,
        metadata: Dict,
        merge: bool = True,
    ) -> None:
        """Display preview of what will be imported.

        Args:
            metadata: Export metadata from peek_config_export
            merge: Whether importing in merge mode
        """
        console.print("\n[bold]Configuration Export Details:[/bold]")
        console.print(f"  Created: [cyan]{metadata.get('created', 'unknown')}[/cyan]")
        console.print(f"  Files: [cyan]{metadata.get('file_count', 0)}[/cyan]")
        console.print()

        # Show files that will be imported
        files = metadata.get("files", [])
        if files:
            table = Table(title="Files to Import", show_header=True)
            table.add_column("File", style="cyan")
            table.add_column("Status", style="yellow")

            for file in files:
                target_path = self.config_dir / file
                status = "exists (will be merged)" if target_path.exists() and merge else \
                         "exists (will be replaced)" if target_path.exists() else \
                         "new"
                table.add_row(file, status)

            console.print(table)
            console.print()

        # Show warnings if any
        warnings = metadata.get("warnings", [])
        if warnings:
            console.print("[yellow]⚠  Warnings from export:[/yellow]\n")
            for warning in warnings:
                console.print(f"  [bold]{warning.get('file')}[/bold] → [cyan]{warning.get('field')}[/cyan]")
                console.print(f"    Path: [dim]{warning.get('path')}[/dim]")
                console.print(f"    💡 {warning.get('suggestion')}\n")

        # Show import mode
        if merge:
            console.print("[dim]Mode: Merge (existing values preserved for conflicting fields)[/dim]")
        else:
            console.print("[yellow]Mode: Replace (existing files will be overwritten)[/yellow]")

        console.print()

    def import_config(
        self,
        export_path: Path,
        merge: bool = True,
        force: bool = False,
    ) -> List[str]:
        """Import configuration from export archive.

        Args:
            export_path: Path to config export file
            merge: If True, merge with existing config. If False, replace entirely.
            force: Skip confirmation prompt

        Returns:
            List of imported file names

        Raises:
            FileNotFoundError: If export file doesn't exist
            ValueError: If export is invalid
        """
        if not export_path.exists():
            raise FileNotFoundError(f"Export file not found: {export_path}")

        # Peek at metadata first
        metadata = self.peek_config_export(export_path)

        # Show preview
        if not force:
            self.show_import_preview(metadata, merge)

            from rich.prompt import Confirm
            if not Confirm.ask("Proceed with import?"):
                raise ValueError("Import cancelled by user")

        # Extract to temporary directory
        temp_dir = self.config_dir / ".config-import-temp"
        temp_dir.mkdir(exist_ok=True)

        imported_files = []

        try:
            with tarfile.open(export_path, "r:gz") as tar:
                tar.extractall(temp_dir)

            # Import each config file
            files = metadata.get("files", [])
            for file in files:
                source_path = temp_dir / file
                target_path = self.config_dir / file

                if not source_path.exists():
                    console.print(f"[yellow]⚠[/yellow] File missing in archive: {file}")
                    continue

                # Create parent directory if needed (for backends/jira.json)
                target_path.parent.mkdir(parents=True, exist_ok=True)

                if merge and target_path.exists():
                    # Merge mode: merge JSON objects
                    merged_data = self._merge_configs(target_path, source_path)
                    with open(target_path, "w") as f:
                        json.dump(merged_data, f, indent=2)
                else:
                    # Replace mode or new file: copy directly
                    shutil.copy2(source_path, target_path)

                imported_files.append(file)

        finally:
            # Clean up temp directory
            shutil.rmtree(temp_dir, ignore_errors=True)

        return imported_files

    def _merge_configs(self, existing_path: Path, new_path: Path) -> Dict:
        """Merge two JSON config files, preserving user-specific values.

        Strategy:
        - Start with existing config
        - For workspace paths: keep existing (user-specific)
        - For other fields: use new values (organization policies)

        Args:
            existing_path: Path to existing config file
            new_path: Path to new config file from import

        Returns:
            Merged configuration dictionary
        """
        with open(existing_path, "r") as f:
            existing = json.load(f)

        with open(new_path, "r") as f:
            new = json.load(f)

        # For config.json, preserve workspace paths
        if existing_path.name == "config.json":
            # Preserve existing workspace configuration
            if "repos" in existing and "workspaces" in existing["repos"]:
                if "repos" not in new:
                    new["repos"] = {}
                # Keep existing workspaces, only add new ones if missing
                new["repos"]["workspaces"] = existing["repos"]["workspaces"]
                # Preserve last_used_workspace
                if "last_used_workspace" in existing["repos"]:
                    new["repos"]["last_used_workspace"] = existing["repos"]["last_used_workspace"]

        # For all files: use deep merge to combine
        return self._deep_merge(existing, new)

    def _deep_merge(self, base: Dict, override: Dict) -> Dict:
        """Deep merge two dictionaries.

        Args:
            base: Base dictionary
            override: Override dictionary (takes precedence)

        Returns:
            Merged dictionary
        """
        result = dict(base)

        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                # Both are dicts - recurse
                result[key] = self._deep_merge(result[key], value)
            else:
                # Override the value
                result[key] = value

        return result
