"""Tests for hierarchical skills installation and management (issue #315)."""

import json
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

import pytest

from devflow.utils.hierarchical_skills import (
    detect_repository_layout,
    RepositoryLayout,
    download_json_config,
    create_backup,
    list_backups,
    restore_backup,
    list_remote_skills,
    has_file_changed,
    download_skill,
)


# =============================================================================
# Repository Layout Detection Tests
# =============================================================================

class TestDetectRepositoryLayout:
    """Test repository layout detection (standard vs legacy)."""

    def test_detects_standard_layout_with_configs_dir(self, tmp_path):
        """Test detection of standard layout when configs/ directory exists."""
        # Setup: Create standard layout
        config_source = tmp_path / "my-org"
        config_source.mkdir()
        (config_source / "configs").mkdir()

        # Execute
        layout = detect_repository_layout(str(config_source))

        # Verify
        assert layout == RepositoryLayout.STANDARD

    def test_detects_standard_layout_with_context_dir(self, tmp_path):
        """Test detection of standard layout when context/ directory exists."""
        # Setup
        config_source = tmp_path / "my-org"
        config_source.mkdir()
        (config_source / "context").mkdir()

        # Execute
        layout = detect_repository_layout(str(config_source))

        # Verify
        assert layout == RepositoryLayout.STANDARD

    def test_detects_standard_layout_with_daf_skills_dir(self, tmp_path):
        """Test detection of standard layout when daf-skills/ directory exists."""
        # Setup
        config_source = tmp_path / "my-org"
        config_source.mkdir()
        (config_source / "daf-skills").mkdir()

        # Execute
        layout = detect_repository_layout(str(config_source))

        # Verify
        assert layout == RepositoryLayout.STANDARD

    def test_detects_legacy_layout_when_no_standard_dirs(self, tmp_path):
        """Test detection of legacy layout when no standard directories exist."""
        # Setup: Create legacy layout (files at root)
        config_source = tmp_path / "my-org"
        config_source.mkdir()
        (config_source / "ENTERPRISE.md").write_text("# Enterprise")

        # Execute
        layout = detect_repository_layout(str(config_source))

        # Verify
        assert layout == RepositoryLayout.LEGACY

    def test_detects_standard_layout_with_file_protocol(self, tmp_path):
        """Test detection with file:// URL."""
        # Setup
        config_source = tmp_path / "my-org"
        config_source.mkdir()
        (config_source / "configs").mkdir()

        # Execute
        layout = detect_repository_layout(f"file://{config_source}")

        # Verify
        assert layout == RepositoryLayout.STANDARD

    @patch('devflow.utils.hierarchical_skills.requests.head')
    def test_detects_standard_layout_with_http_url(self, mock_head):
        """Test detection with HTTP URL."""
        # Setup: Mock HTTP HEAD response for configs/enterprise.json check
        # The actual implementation tries HEAD request to configs/enterprise.json
        mock_response = MagicMock()
        mock_response.status_code = 200  # Successfully found configs/enterprise.json
        mock_head.return_value = mock_response

        # Execute
        layout = detect_repository_layout("https://github.com/org/repo")

        # Verify
        assert layout == RepositoryLayout.STANDARD
        # Verify HEAD request was made to the expected URL
        mock_head.assert_called_once()
        call_args = mock_head.call_args
        assert 'configs/enterprise.json' in call_args[0][0]

    @patch('devflow.utils.hierarchical_skills.requests.head')
    def test_detects_legacy_layout_with_http_url_when_no_configs_dir(self, mock_head):
        """Test detection of legacy layout with HTTP URL when configs/ doesn't exist."""
        # Setup: Mock HTTP 404 response (configs/ directory not found)
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_head.return_value = mock_response

        # Execute
        layout = detect_repository_layout("https://github.com/org/repo")

        # Verify
        assert layout == RepositoryLayout.LEGACY


# =============================================================================
# JSON Config Download Tests
# =============================================================================

class TestDownloadJsonConfig:
    """Test JSON config file downloading."""

    def test_downloads_json_from_local_standard_layout(self, tmp_path):
        """Test downloading JSON config from local filesystem (standard layout)."""
        # Setup
        config_source = tmp_path / "my-org"
        configs_dir = config_source / "configs"
        configs_dir.mkdir(parents=True)

        json_data = {"field_mappings": {"acceptance_criteria": "customfield_12345"}}
        (configs_dir / "enterprise.json").write_text(json.dumps(json_data))

        # Execute
        result = download_json_config(str(config_source), "enterprise.json", RepositoryLayout.STANDARD)

        # Verify
        assert result == json_data

    def test_returns_none_when_json_not_found(self, tmp_path):
        """Test returns None when JSON file doesn't exist."""
        # Setup
        config_source = tmp_path / "my-org"
        configs_dir = config_source / "configs"
        configs_dir.mkdir(parents=True)

        # Execute
        result = download_json_config(str(config_source), "nonexistent.json", RepositoryLayout.STANDARD)

        # Verify
        assert result is None

    def test_downloads_json_with_file_protocol(self, tmp_path):
        """Test downloading JSON with file:// protocol."""
        # Setup
        config_source = tmp_path / "my-org"
        configs_dir = config_source / "configs"
        configs_dir.mkdir(parents=True)

        json_data = {"test": "value"}
        (configs_dir / "test.json").write_text(json.dumps(json_data))

        # Execute
        result = download_json_config(f"file://{config_source}", "test.json", RepositoryLayout.STANDARD)

        # Verify
        assert result == json_data


# =============================================================================
# Backup System Tests
# =============================================================================

class TestBackupSystem:
    """Test backup creation, listing, and restoration."""

    def test_create_backup_creates_timestamped_file(self, tmp_path, temp_daf_home):
        """Test backup creation with timestamp."""
        # Setup
        test_file = temp_daf_home / "enterprise.json"
        test_file.write_text('{"test": "value"}')

        # Execute
        backup_path = create_backup(test_file)

        # Verify
        assert backup_path is not None
        assert backup_path.exists()
        assert backup_path.parent == temp_daf_home / "backups"
        assert backup_path.name.startswith("enterprise.json.")
        assert backup_path.name.endswith(".backup")
        assert backup_path.read_text() == '{"test": "value"}'

    def test_create_backup_returns_none_if_file_not_exists(self, tmp_path):
        """Test backup returns None if source file doesn't exist."""
        # Setup
        nonexistent_file = tmp_path / "nonexistent.json"

        # Execute
        backup_path = create_backup(nonexistent_file)

        # Verify
        assert backup_path is None

    def test_list_backups_returns_sorted_by_timestamp(self, temp_daf_home):
        """Test listing backups sorted by modification time (newest first)."""
        import time

        # Setup: Create multiple backups with different modification times
        backup_dir = temp_daf_home / "backups"
        backup_dir.mkdir(exist_ok=True)

        # Create files with increasing modification times
        old_file = backup_dir / "enterprise.json.2026-03-26T10:00:00.backup"
        old_file.write_text("old")
        time.sleep(0.01)  # Ensure different mtime

        mid_file = backup_dir / "organization.json.2026-03-26T11:00:00.backup"
        mid_file.write_text("other")
        time.sleep(0.01)  # Ensure different mtime

        new_file = backup_dir / "enterprise.json.2026-03-26T12:00:00.backup"
        new_file.write_text("new")

        # Execute
        backups = list_backups(backup_dir=backup_dir)

        # Verify: Sorted by mtime, newest first (not by filename timestamp)
        assert len(backups) == 3
        assert backups[0] == new_file  # Most recently created
        assert backups[1] == mid_file  # Middle
        assert backups[2] == old_file  # Oldest

    def test_list_backups_filters_by_filename(self, temp_daf_home):
        """Test listing backups filtered by filename."""
        # Setup
        backup_dir = temp_daf_home / "backups"
        backup_dir.mkdir(exist_ok=True)

        (backup_dir / "enterprise.json.2026-03-26T10:00:00.backup").write_text("test")
        (backup_dir / "organization.json.2026-03-26T11:00:00.backup").write_text("test")

        # Execute
        backups = list_backups(filename="enterprise.json", backup_dir=backup_dir)

        # Verify: Only enterprise backups
        assert len(backups) == 1
        assert "enterprise.json" in backups[0].name

    def test_restore_backup_restores_file_content(self, temp_daf_home):
        """Test restoring a file from backup."""
        # Setup
        backup_dir = temp_daf_home / "backups"
        backup_dir.mkdir(exist_ok=True)

        backup_file = backup_dir / "enterprise.json.2026-03-26T10:00:00.backup"
        backup_file.write_text('{"restored": true}')

        target_path = temp_daf_home / "enterprise.json"

        # Execute
        restored_path = restore_backup(backup_file, target_path)

        # Verify
        assert restored_path == target_path
        assert target_path.exists()
        assert target_path.read_text() == '{"restored": true}'


# =============================================================================
# Dynamic Skill Discovery Tests
# =============================================================================

class TestListRemoteSkills:
    """Test dynamic skill discovery."""

    def test_lists_skills_from_local_filesystem(self, tmp_path):
        """Test discovering skills from local filesystem."""
        # Setup
        config_source = tmp_path / "my-org"
        skills_dir = config_source / "daf-skills"
        skills_dir.mkdir(parents=True)

        (skills_dir / "enterprise").mkdir()
        (skills_dir / "enterprise" / "SKILL.md").write_text("# Enterprise Skill")

        (skills_dir / "organization").mkdir()
        (skills_dir / "organization" / "SKILL.md").write_text("# Org Skill")

        (skills_dir / "team").mkdir()
        (skills_dir / "team" / "SKILL.md").write_text("# Team Skill")

        # Create a directory without SKILL.md (should be skipped)
        (skills_dir / "incomplete").mkdir()

        # Execute
        skills = list_remote_skills(str(config_source), RepositoryLayout.STANDARD)

        # Verify
        assert sorted(skills) == ["enterprise", "organization", "team"]

    def test_returns_empty_list_when_no_skills_found(self, tmp_path):
        """Test returns empty list when no skills exist."""
        # Setup
        config_source = tmp_path / "my-org"
        skills_dir = config_source / "daf-skills"
        skills_dir.mkdir(parents=True)

        # Execute
        skills = list_remote_skills(str(config_source), RepositoryLayout.STANDARD)

        # Verify
        assert skills == []

    @patch('devflow.utils.hierarchical_skills.requests.get')
    def test_lists_skills_from_github_api(self, mock_get):
        """Test discovering skills from GitHub API."""
        # Setup: Mock GitHub API response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = [
            {"name": "enterprise", "type": "dir"},
            {"name": "organization", "type": "dir"},
            {"name": "README.md", "type": "file"}  # Should be ignored
        ]
        mock_get.return_value = mock_response

        # Execute
        skills = list_remote_skills("https://github.com/org/repo", RepositoryLayout.STANDARD)

        # Verify
        assert sorted(skills) == ["enterprise", "organization"]


# =============================================================================
# Change Detection Tests
# =============================================================================

class TestHasFileChanged:
    """Test file change detection."""

    def test_returns_true_when_file_not_exists(self, tmp_path):
        """Test returns True when file doesn't exist."""
        # Setup
        nonexistent_file = tmp_path / "nonexistent.txt"

        # Execute
        result = has_file_changed(nonexistent_file, "new content")

        # Verify
        assert result is True

    def test_returns_true_when_content_differs(self, tmp_path):
        """Test returns True when content differs."""
        # Setup
        test_file = tmp_path / "test.txt"
        test_file.write_text("old content")

        # Execute
        result = has_file_changed(test_file, "new content")

        # Verify
        assert result is True

    def test_returns_false_when_content_identical(self, tmp_path):
        """Test returns False when content is identical."""
        # Setup
        test_file = tmp_path / "test.txt"
        test_file.write_text("same content")

        # Execute
        result = has_file_changed(test_file, "same content")

        # Verify
        assert result is False

    def test_handles_json_with_trailing_newline(self, tmp_path):
        """Test JSON change detection with trailing newline."""
        # Setup
        test_file = tmp_path / "test.json"
        json_content = '{"key": "value"}\n'
        test_file.write_text(json_content)

        # Execute: Compare with same content
        result = has_file_changed(test_file, json_content)

        # Verify
        assert result is False


# =============================================================================
# Skill Download Tests
# =============================================================================

class TestDownloadSkill:
    """Test skill content downloading."""

    def test_downloads_skill_from_local_file_url(self, tmp_path):
        """Test downloading skill from file:// URL."""
        # Setup
        skill_dir = tmp_path / "daf-skills" / "enterprise"
        skill_dir.mkdir(parents=True)
        skill_file = skill_dir / "SKILL.md"
        skill_file.write_text("# Enterprise Skill Content")

        # Execute
        content = download_skill(f"file://{skill_dir}")

        # Verify
        assert content == "# Enterprise Skill Content"

    def test_downloads_skill_from_relative_path(self, tmp_path):
        """Test downloading skill from relative path."""
        # Setup
        config_dir = tmp_path / "context"
        config_dir.mkdir(parents=True)
        config_file = config_dir / "ENTERPRISE.md"
        config_file.write_text("# Config")

        skill_dir = tmp_path / "daf-skills" / "enterprise"
        skill_dir.mkdir(parents=True)
        skill_file = skill_dir / "SKILL.md"
        skill_file.write_text("# Skill Content")

        # Execute: Relative path from config file location
        content = download_skill("../daf-skills/enterprise", config_file_path=config_file)

        # Verify
        assert content == "# Skill Content"

    def test_raises_error_for_relative_path_without_config_file(self):
        """Test raises ValueError for relative path without config_file_path."""
        # Execute & Verify
        with pytest.raises(ValueError, match="Relative skill_url .* requires config_file_path"):
            download_skill("../daf-skills/enterprise")

    def test_raises_error_when_skill_file_not_found(self, tmp_path):
        """Test raises FileNotFoundError when SKILL.md doesn't exist."""
        # Setup
        skill_dir = tmp_path / "daf-skills" / "enterprise"
        skill_dir.mkdir(parents=True)
        # Note: SKILL.md is NOT created

        # Execute & Verify
        with pytest.raises(FileNotFoundError, match="Skill file not found"):
            download_skill(f"file://{skill_dir}")


# =============================================================================
# Integration Tests
# =============================================================================

class TestInstallHierarchicalSkillsIntegration:
    """Integration tests for full hierarchical skills installation workflow."""

    def test_standard_layout_full_workflow(self, tmp_path, temp_daf_home, monkeypatch):
        """Test complete installation workflow for standard layout."""
        # Setup: Create standard repository layout
        org_repo = tmp_path / "my-org"
        org_repo.mkdir()

        # Create configs/
        configs_dir = org_repo / "configs"
        configs_dir.mkdir()
        (configs_dir / "enterprise.json").write_text('{"field_mappings": {}}')

        # Create context/
        context_dir = org_repo / "context"
        context_dir.mkdir()
        (context_dir / "ENTERPRISE.md").write_text("# Enterprise Policy")

        # Create daf-skills/
        skills_dir = org_repo / "daf-skills"
        skills_dir.mkdir()
        enterprise_skill = skills_dir / "enterprise"
        enterprise_skill.mkdir()
        (enterprise_skill / "SKILL.md").write_text("# Enterprise Skill Instructions")

        # Setup config.json
        config_file = temp_daf_home / "config.json"
        config_file.write_text(json.dumps({
            "repos": {
                "hierarchical_config_source": str(org_repo)
            }
        }))

        # Mock SSL settings
        monkeypatch.setenv("DAF_SSL_VERIFY", "false")

        # Execute
        from devflow.utils.hierarchical_skills import install_hierarchical_skills
        changed, up_to_date, failed = install_hierarchical_skills(dry_run=False, quiet=True)

        # Verify: JSON config synced
        assert (temp_daf_home / "enterprise.json").exists()
        assert json.loads((temp_daf_home / "enterprise.json").read_text()) == {"field_mappings": {}}

        # Verify: Context file synced
        assert (temp_daf_home / "ENTERPRISE.md").exists()
        assert (temp_daf_home / "ENTERPRISE.md").read_text() == "# Enterprise Policy"

        # Verify: Skill installed
        skill_path = temp_daf_home / ".claude" / "skills" / "enterprise" / "SKILL.md"
        assert skill_path.exists()
        assert skill_path.read_text() == "# Enterprise Skill Instructions"

        # Verify: Installation counts
        assert "enterprise.json" in changed
        assert "ENTERPRISE.md" in changed
        assert "enterprise" in changed

    def test_dry_run_mode_does_not_modify_files(self, tmp_path, temp_daf_home):
        """Test dry-run mode doesn't actually modify files."""
        # Setup
        org_repo = tmp_path / "my-org"
        configs_dir = org_repo / "configs"
        configs_dir.mkdir(parents=True)
        (configs_dir / "enterprise.json").write_text('{"test": "value"}')

        config_file = temp_daf_home / "config.json"
        config_file.write_text(json.dumps({
            "repos": {
                "hierarchical_config_source": str(org_repo)
            }
        }))

        # Execute: Dry run
        from devflow.utils.hierarchical_skills import install_hierarchical_skills
        changed, up_to_date, failed = install_hierarchical_skills(dry_run=True, quiet=True)

        # Verify: No files created
        assert not (temp_daf_home / "enterprise.json").exists()

        # Verify: Changes reported
        assert "enterprise.json" in changed
