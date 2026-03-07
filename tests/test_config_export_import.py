"""Tests for config export and import functionality."""

import json
import tarfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from devflow.config.exporter import ConfigExporter, LocalPathWarning
from devflow.config.importer import ConfigImporter


@pytest.fixture
def config_dir(tmp_path):
    """Create a temporary config directory with sample files."""
    config_dir = tmp_path / "config"
    config_dir.mkdir()

    # Create config.json
    config_data = {
        "repos": {
            "workspaces": [
                {"name": "default", "path": "/Users/alice/development"},
                {"name": "secondary", "path": "~/projects"}
            ],
            "last_used_workspace": "default"
        },
        "context_files": [
            {"path": "file:///Users/alice/notes/TEAM.md", "description": "Team notes"},
            {"path": "https://github.com/org/repo/main/ORGANIZATION.md", "description": "Org docs"}
        ],
        "pr_template_url": "file:///Users/alice/templates/PR.md",
        "time_tracking": {"enabled": True}
    }

    with open(config_dir / "config.json", "w") as f:
        json.dump(config_data, f, indent=2)

    # Create organization.json
    org_data = {
        "jira_project": "PROJ",
        "hierarchical_config_source": "file:///Users/alice/configs",
        "transitions": {
            "on_start": {
                "from": ["To Do"],
                "to": "In Progress",
                "prompt": False
            }
        }
    }

    with open(config_dir / "organization.json", "w") as f:
        json.dump(org_data, f, indent=2)

    # Create team.json
    team_data = {
        "jira_custom_field_defaults": {"workstream": "Platform"},
        "time_tracking_enabled": True
    }

    with open(config_dir / "team.json", "w") as f:
        json.dump(team_data, f, indent=2)

    # Create enterprise.json
    enterprise_data = {
        "agent_backend": "claude"
    }

    with open(config_dir / "enterprise.json", "w") as f:
        json.dump(enterprise_data, f, indent=2)

    # Create backends/jira.json
    backends_dir = config_dir / "backends"
    backends_dir.mkdir()

    backend_data = {
        "url": "https://jira.example.com",
        "field_mappings": {"severity": {"id": "customfield_12345"}}
    }

    with open(backends_dir / "jira.json", "w") as f:
        json.dump(backend_data, f, indent=2)

    return config_dir


class TestConfigExporter:
    """Tests for ConfigExporter."""

    def test_scan_for_local_paths_detects_workspace_paths(self, config_dir):
        """Test that scanner detects absolute workspace paths."""
        exporter = ConfigExporter(config_dir)
        warnings = exporter.scan_for_local_paths()

        # Should detect workspace path
        workspace_warnings = [w for w in warnings if "workspaces" in w.field]
        assert len(workspace_warnings) >= 1

        # Check for absolute path
        abs_path_warning = next(
            (w for w in workspace_warnings if w.path.startswith("/")),
            None
        )
        assert abs_path_warning is not None
        assert abs_path_warning.file == "config.json"

    def test_scan_for_local_paths_detects_file_urls(self, config_dir):
        """Test that scanner detects file:// URLs."""
        exporter = ConfigExporter(config_dir)
        warnings = exporter.scan_for_local_paths()

        # Should detect context_files file:// URL
        context_warnings = [w for w in warnings if "context_files" in w.field]
        assert len(context_warnings) >= 1
        assert any(w.path.startswith("file://") for w in context_warnings)

        # Should detect pr_template_url
        pr_warnings = [w for w in warnings if "pr_template_url" in w.field]
        assert len(pr_warnings) == 1
        assert pr_warnings[0].path.startswith("file://")

        # Should detect hierarchical_config_source
        org_warnings = [w for w in warnings if "hierarchical_config_source" in w.field]
        assert len(org_warnings) == 1
        assert org_warnings[0].file == "organization.json"

    def test_scan_ignores_http_urls(self, config_dir):
        """Test that scanner ignores http/https URLs."""
        exporter = ConfigExporter(config_dir)
        warnings = exporter.scan_for_local_paths()

        # GitHub URL in context_files should not trigger warning
        github_warnings = [
            w for w in warnings
            if "context_files" in w.field and "github.com" in w.path
        ]
        assert len(github_warnings) == 0

    def test_export_config_creates_tarball(self, config_dir, tmp_path):
        """Test that export creates a valid tar.gz archive."""
        exporter = ConfigExporter(config_dir)
        output_path = tmp_path / "export.tar.gz"

        # Mock confirmation
        with patch("rich.prompt.Confirm.ask", return_value=True):
            result = exporter.export_config(output_path=output_path, force=False)

        assert result == output_path
        assert output_path.exists()

        # Verify tar.gz is valid
        with tarfile.open(output_path, "r:gz") as tar:
            names = tar.getnames()
            assert "config-export-metadata.json" in names
            assert "config.json" in names
            assert "organization.json" in names
            assert "team.json" in names
            assert "enterprise.json" in names
            assert "backends/jira.json" in names

    def test_export_includes_metadata(self, config_dir, tmp_path):
        """Test that export includes correct metadata."""
        exporter = ConfigExporter(config_dir)
        output_path = tmp_path / "export.tar.gz"

        result = exporter.export_config(output_path=output_path, force=True)

        # Extract and check metadata
        with tarfile.open(result, "r:gz") as tar:
            metadata_file = tar.extractfile("config-export-metadata.json")
            metadata = json.load(metadata_file)

            assert metadata["version"] == "1.0"
            assert metadata["archive_type"] == "config_export"
            assert metadata["file_count"] == 5
            assert "created" in metadata
            assert set(metadata["files"]) == {
                "config.json",
                "organization.json",
                "team.json",
                "enterprise.json",
                "backends/jira.json"
            }

    def test_export_includes_warnings_in_metadata(self, config_dir, tmp_path):
        """Test that export includes path warnings in metadata."""
        exporter = ConfigExporter(config_dir)
        output_path = tmp_path / "export.tar.gz"

        result = exporter.export_config(output_path=output_path, force=True)

        # Extract and check warnings
        with tarfile.open(result, "r:gz") as tar:
            metadata_file = tar.extractfile("config-export-metadata.json")
            metadata = json.load(metadata_file)

            warnings = metadata.get("warnings", [])
            assert len(warnings) > 0

            # Check warning structure
            assert all("file" in w for w in warnings)
            assert all("field" in w for w in warnings)
            assert all("path" in w for w in warnings)
            assert all("suggestion" in w for w in warnings)

    def test_export_with_force_skips_confirmation(self, config_dir, tmp_path):
        """Test that force flag skips confirmation prompt."""
        exporter = ConfigExporter(config_dir)
        output_path = tmp_path / "export.tar.gz"

        # Should not prompt with force=True
        with patch("rich.prompt.Confirm.ask") as mock_confirm:
            exporter.export_config(output_path=output_path, force=True)
            mock_confirm.assert_not_called()

    def test_export_fails_if_no_config_files(self, tmp_path):
        """Test that export fails if no config files exist."""
        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()

        exporter = ConfigExporter(empty_dir)

        with pytest.raises(ValueError, match="No configuration files found"):
            exporter.export_config(force=True)


class TestConfigImporter:
    """Tests for ConfigImporter."""

    @pytest.fixture
    def export_file(self, config_dir, tmp_path):
        """Create an export file for testing."""
        exporter = ConfigExporter(config_dir)
        output_path = tmp_path / "test-export.tar.gz"
        return exporter.export_config(output_path=output_path, force=True)

    def test_peek_export_returns_metadata(self, config_dir, export_file):
        """Test that peek returns correct metadata."""
        importer = ConfigImporter(config_dir)
        metadata = importer.peek_config_export(export_file)

        assert metadata["file_count"] == 5
        assert len(metadata["files"]) == 5
        assert "created" in metadata
        assert len(metadata.get("warnings", [])) > 0

    def test_peek_rejects_invalid_archives(self, config_dir, tmp_path):
        """Test that peek rejects invalid archive types."""
        # Create a fake backup archive
        fake_backup = tmp_path / "backup.tar.gz"
        with tarfile.open(fake_backup, "w:gz") as tar:
            metadata = {
                "version": "1.0",
                "archive_type": "backup",  # Wrong type
                "created": "2024-01-01T00:00:00"
            }
            import io
            json_bytes = json.dumps(metadata).encode("utf-8")
            tarinfo = tarfile.TarInfo(name="config-export-metadata.json")
            tarinfo.size = len(json_bytes)
            tar.addfile(tarinfo, io.BytesIO(json_bytes))

        importer = ConfigImporter(config_dir)

        with pytest.raises(ValueError, match="Invalid archive type"):
            importer.peek_config_export(fake_backup)

    def test_import_config_merge_mode(self, tmp_path, export_file):
        """Test that import in merge mode preserves workspace paths."""
        # Create target dir with existing config
        target_dir = tmp_path / "target"
        target_dir.mkdir()

        existing_config = {
            "repos": {
                "workspaces": [
                    {"name": "default", "path": "/Users/bob/code"}
                ],
                "last_used_workspace": "default"
            },
            "time_tracking": {"enabled": False}
        }

        with open(target_dir / "config.json", "w") as f:
            json.dump(existing_config, f, indent=2)

        importer = ConfigImporter(target_dir)

        # Import in merge mode
        imported = importer.import_config(export_file, merge=True, force=True)

        assert "config.json" in imported

        # Check that workspace paths were preserved
        with open(target_dir / "config.json", "r") as f:
            result = json.load(f)

        assert result["repos"]["workspaces"][0]["path"] == "/Users/bob/code"
        # But other fields should be imported
        assert "context_files" in result

    def test_import_config_replace_mode(self, tmp_path, export_file):
        """Test that import in replace mode overwrites everything."""
        # Create target dir with existing config
        target_dir = tmp_path / "target"
        target_dir.mkdir()

        existing_config = {
            "repos": {
                "workspaces": [
                    {"name": "default", "path": "/Users/bob/code"}
                ]
            }
        }

        with open(target_dir / "config.json", "w") as f:
            json.dump(existing_config, f, indent=2)

        importer = ConfigImporter(target_dir)

        # Import in replace mode
        imported = importer.import_config(export_file, merge=False, force=True)

        assert "config.json" in imported

        # Check that everything was replaced
        with open(target_dir / "config.json", "r") as f:
            result = json.load(f)

        # Should have the exported workspace paths, not Bob's
        assert result["repos"]["workspaces"][0]["path"] != "/Users/bob/code"

    def test_import_creates_new_files(self, tmp_path, export_file):
        """Test that import creates new files that don't exist."""
        target_dir = tmp_path / "target"
        target_dir.mkdir()

        importer = ConfigImporter(target_dir)

        imported = importer.import_config(export_file, merge=True, force=True)

        # Should import all files
        assert len(imported) == 5
        assert (target_dir / "config.json").exists()
        assert (target_dir / "organization.json").exists()
        assert (target_dir / "team.json").exists()
        assert (target_dir / "enterprise.json").exists()
        assert (target_dir / "backends" / "jira.json").exists()

    def test_import_with_force_skips_confirmation(self, tmp_path, export_file):
        """Test that force flag skips confirmation."""
        target_dir = tmp_path / "target"
        target_dir.mkdir()

        importer = ConfigImporter(target_dir)

        with patch("rich.prompt.Confirm.ask") as mock_confirm:
            importer.import_config(export_file, merge=True, force=True)
            mock_confirm.assert_not_called()


class TestEndToEndWorkflow:
    """End-to-end tests for export/import workflow."""

    def test_export_import_roundtrip(self, config_dir, tmp_path):
        """Test full export/import cycle preserves data."""
        # Export
        exporter = ConfigExporter(config_dir)
        export_path = tmp_path / "export.tar.gz"
        exported = exporter.export_config(output_path=export_path, force=True)

        # Import to new location
        import_dir = tmp_path / "imported"
        import_dir.mkdir()

        importer = ConfigImporter(import_dir)
        importer.import_config(exported, merge=False, force=True)

        # Verify all files were imported correctly
        with open(config_dir / "team.json", "r") as f:
            original = json.load(f)

        with open(import_dir / "team.json", "r") as f:
            imported_data = json.load(f)

        assert original == imported_data

    def test_no_secrets_in_export(self, config_dir, tmp_path):
        """Test that export does not include API tokens."""
        # Add a config with JIRA URL (safe) but no tokens (tokens are in env vars)
        config_data = {
            "jira": {
                "url": "https://jira.example.com"
                # No API tokens - they're in environment variables
            }
        }

        with open(config_dir / "config.json", "w") as f:
            json.dump(config_data, f, indent=2)

        # Export
        exporter = ConfigExporter(config_dir)
        export_path = tmp_path / "export.tar.gz"
        exported = exporter.export_config(output_path=export_path, force=True)

        # Verify export doesn't contain tokens
        with tarfile.open(exported, "r:gz") as tar:
            config_file = tar.extractfile("config.json")
            config_content = config_file.read().decode("utf-8")

            # Should not contain any API token-like strings
            assert "JIRA_API_TOKEN" not in config_content
            assert "GITHUB_TOKEN" not in config_content
            assert "api_token" not in config_content.lower()

    def test_local_path_warnings_displayed(self, config_dir, tmp_path):
        """Test that local path warnings are shown during export."""
        exporter = ConfigExporter(config_dir)
        warnings = exporter.scan_for_local_paths()

        # Should have warnings for file:// URLs and absolute paths
        assert len(warnings) > 0

        # Check that warnings have helpful suggestions
        for warning in warnings:
            assert warning.suggestion
            assert ("GitHub" in warning.suggestion or
                    "GitLab" in warning.suggestion or
                    "relative" in warning.suggestion or
                    "document" in warning.suggestion)
