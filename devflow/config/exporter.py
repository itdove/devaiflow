"""Configuration export functionality."""

import json
import tarfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
from urllib.parse import urlparse

from rich.console import Console

console = Console()


@dataclass
class LocalPathWarning:
    """Warning about a local file path that won't work on other machines."""

    file: str
    field: str
    path: str
    suggestion: str


class ConfigExporter:
    """Export configuration files for user onboarding."""

    def __init__(self, config_dir: Path):
        """Initialize config exporter.

        Args:
            config_dir: Configuration directory (typically ~/.daf-sessions)
        """
        self.config_dir = config_dir

    def scan_for_local_paths(self) -> List[LocalPathWarning]:
        """Scan configuration files for local paths that won't work on other machines.

        Checks for:
        - file:// URLs in context_files, pr_template_url, hierarchical_config_source
        - Absolute workspace paths in repos.workspaces[].path

        Returns:
            List of LocalPathWarning objects
        """
        warnings = []

        # Check config.json for workspace paths and file:// URLs
        config_file = self.config_dir / "config.json"
        if config_file.exists():
            with open(config_file, "r") as f:
                config_data = json.load(f)

            # Check workspace paths
            if "repos" in config_data:
                repos = config_data["repos"]

                # Check workspaces array
                if "workspaces" in repos and isinstance(repos["workspaces"], list):
                    for workspace in repos["workspaces"]:
                        if "path" in workspace:
                            path = workspace["path"]
                            # Check if it's an absolute path (starts with / or ~)
                            if path.startswith("/") or path.startswith("~"):
                                warnings.append(
                                    LocalPathWarning(
                                        file="config.json",
                                        field=f"repos.workspaces[name={workspace.get('name', 'unknown')}].path",
                                        path=path,
                                        suggestion="Consider using relative paths or document the expected workspace structure",
                                    )
                                )

            # Check context_files for file:// URLs
            if "context_files" in config_data and isinstance(config_data["context_files"], list):
                for i, context_file in enumerate(config_data["context_files"]):
                    if isinstance(context_file, dict) and "path" in context_file:
                        path = context_file["path"]
                        if self._is_local_file_url(path):
                            warnings.append(
                                LocalPathWarning(
                                    file="config.json",
                                    field=f"context_files[{i}].path",
                                    path=path,
                                    suggestion="Replace with GitHub/GitLab raw URL (e.g., https://raw.githubusercontent.com/org/repo/main/file.md)",
                                )
                            )

            # Check pr_template_url
            if "pr_template_url" in config_data:
                url = config_data["pr_template_url"]
                if self._is_local_file_url(url):
                    warnings.append(
                        LocalPathWarning(
                            file="config.json",
                            field="pr_template_url",
                            path=url,
                            suggestion="Replace with GitHub/GitLab raw URL or organization .github repository URL",
                        )
                    )

        # Check organization.json for hierarchical_config_source
        org_file = self.config_dir / "organization.json"
        if org_file.exists():
            with open(org_file, "r") as f:
                org_data = json.load(f)

            if "hierarchical_config_source" in org_data:
                source = org_data["hierarchical_config_source"]
                if self._is_local_file_url(source):
                    warnings.append(
                        LocalPathWarning(
                            file="organization.json",
                            field="hierarchical_config_source",
                            path=source,
                            suggestion="Replace with GitHub/GitLab repository URL (e.g., https://github.com/org/configs)",
                        )
                    )

        return warnings

    def _is_local_file_url(self, url: str) -> bool:
        """Check if a URL is a local file:// URL.

        Args:
            url: URL to check

        Returns:
            True if it's a file:// URL or absolute file path
        """
        if not url:
            return False

        # Check for file:// protocol
        if url.startswith("file://"):
            return True

        # Check for absolute paths (could be mis-configured as URLs)
        parsed = urlparse(url)
        if not parsed.scheme and (url.startswith("/") or url.startswith("~")):
            return True

        return False

    def export_config(
        self,
        output_path: Optional[Path] = None,
        force: bool = False,
    ) -> Path:
        """Export configuration files to tar.gz archive.

        Args:
            output_path: Output file path. Defaults to config-export.tar.gz in home directory.
            force: Skip confirmation prompts

        Returns:
            Path to created export file

        Raises:
            ValueError: If config directory doesn't exist or no config files found
        """
        if not self.config_dir.exists():
            raise ValueError(f"Config directory not found: {self.config_dir}")

        # Scan for local paths and show warnings
        warnings = self.scan_for_local_paths()

        if warnings and not force:
            console.print("\n[yellow]⚠  Local paths detected in configuration[/yellow]\n")
            console.print(
                "The following paths may not work on other machines:\n"
            )

            for warning in warnings:
                console.print(f"  [bold]{warning.file}[/bold] → [cyan]{warning.field}[/cyan]")
                console.print(f"    Path: [dim]{warning.path}[/dim]")
                console.print(f"    💡 {warning.suggestion}\n")

            console.print(
                "[yellow]These paths will be exported as-is. "
                "Recipients will need to adjust them for their environment.[/yellow]\n"
            )

            from rich.prompt import Confirm
            if not Confirm.ask("Continue with export?"):
                raise ValueError("Export cancelled by user")

        # Determine which config files exist
        config_files = {
            "config.json": self.config_dir / "config.json",
            "enterprise.json": self.config_dir / "enterprise.json",
            "organization.json": self.config_dir / "organization.json",
            "team.json": self.config_dir / "team.json",
            "backends/jira.json": self.config_dir / "backends" / "jira.json",
        }

        existing_files = {name: path for name, path in config_files.items() if path.exists()}

        if not existing_files:
            raise ValueError("No configuration files found to export")

        # Generate output path if not provided
        if output_path is None:
            output_path = Path.home() / "config-export.tar.gz"

        # Ensure output directory exists
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Create metadata
        metadata = {
            "version": "1.0",
            "archive_type": "config_export",
            "created": datetime.now().isoformat(),
            "file_count": len(existing_files),
            "files": list(existing_files.keys()),
            "warnings": [
                {
                    "file": w.file,
                    "field": w.field,
                    "path": w.path,
                    "suggestion": w.suggestion,
                }
                for w in warnings
            ],
        }

        # Create tar.gz archive
        with tarfile.open(output_path, "w:gz") as tar:
            # Add metadata
            self._add_json_to_tar(tar, "config-export-metadata.json", metadata)

            # Add each config file
            for name, path in existing_files.items():
                tar.add(path, arcname=name)

        return output_path

    def _add_json_to_tar(self, tar: tarfile.TarFile, name: str, data: dict) -> None:
        """Add JSON data to tar archive.

        Args:
            tar: TarFile object
            name: Name of file in archive
            data: Data to serialize as JSON
        """
        import io

        json_bytes = json.dumps(data, indent=2).encode("utf-8")
        tarinfo = tarfile.TarInfo(name=name)
        tarinfo.size = len(json_bytes)
        tarinfo.mtime = int(datetime.now().timestamp())
        tar.addfile(tarinfo, io.BytesIO(json_bytes))
