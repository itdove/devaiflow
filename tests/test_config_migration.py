"""Tests for configuration migration from old to new format."""

import json
from pathlib import Path

import pytest

from devflow.config.loader import ConfigLoader
from devflow.config.models import Config


def test_is_old_format_detection(temp_daf_home):
    """Test detection of old vs new config format."""
    loader = ConfigLoader()

    # No config file - should return False
    assert loader._is_old_format() is False

    # Create old format config (has 'jira' key)
    old_config = {
        "jira": {
            "url": "https://jira.example.com",
            "user": "test-user",
            "transitions": {}
        },
        "repos": {
            "workspace": "/test/workspace"
        },
        "time_tracking": {}
    }

    with open(loader.config_file, "w") as f:
        json.dump(old_config, f)

    assert loader._is_old_format() is True

    # Create new format config (no 'jira' key, just user prefs)
    new_config = {
        "backend_config_source": "local",
        "repos": {
            "workspace": "/test/workspace"
        },
        "time_tracking": {}
    }

    with open(loader.config_file, "w") as f:
        json.dump(new_config, f)

    assert loader._is_old_format() is False


def test_load_old_format_config(temp_daf_home):
    """Test loading configuration in old single-file format."""
    loader = ConfigLoader()

    # Create old format config
    old_config = {
        "jira": {
            "url": "https://jira.example.com",
            "user": "test-user",
            "project": "TEST",
            "workstream": "Platform",
            "transitions": {
                "on_start": {
                    "from": ["New", "To Do"],
                    "to": "In Progress",
                    "prompt": False
                }
            },
            "filters": {
                "sync": {
                    "status": ["New", "To Do"],
                    "required_fields": [],
                    "assignee": "currentUser()"
                }
            }
        },
        "repos": {
            "workspace": "/test/workspace",
            "keywords": {}
        },
        "time_tracking": {
            "auto_start": True
        }
    }

    with open(loader.config_file, "w") as f:
        json.dump(old_config, f)

    # Load config - should work with old format
    config = loader.load_config()

    assert config is not None
    assert config.jira.url == "https://jira.example.com"
    assert config.jira.user == "test-user"
    assert config.jira.project == "TEST"
    assert config.jira.workstream == "Platform"
    assert config.repos.workspace == "/test/workspace"
    assert config.time_tracking.auto_start is True


def test_migration_on_first_save(temp_daf_home):
    """Test that migration happens on first save of old format config."""
    loader = ConfigLoader()

    # Create old format config
    config = loader.create_default_config()
    config.jira.project = "MIGRATED"
    config.jira.workstream = "Test"

    # Verify old format
    assert loader._is_old_format() is True

    # Modify and save - should trigger migration
    config.jira.user = "migrated-user"
    loader.save_config(config)

    # Verify migration happened
    assert loader._is_old_format() is False

    # Verify new format files exist
    assert loader.config_file.exists()
    assert (loader.config_dir / "organization.json").exists()
    assert (loader.config_dir / "team.json").exists()
    assert (loader.config_dir / "backends" / "jira.json").exists()

    # Verify backup was created
    backup_dir = loader.config_dir / ".deprecated"
    assert backup_dir.exists()
    backup_files = list(backup_dir.glob("config.json.*"))
    assert len(backup_files) == 1

    # Load and verify data preserved
    migrated_config = loader.load_config()
    assert migrated_config.jira.project == "MIGRATED"
    assert migrated_config.jira.workstream == "Test"
    assert migrated_config.jira.user == "migrated-user"


def test_load_new_format_config(temp_daf_home):
    """Test loading configuration from new 4-file format."""
    loader = ConfigLoader()

    # Create new format config files
    user_config = {
        "backend_config_source": "local",
        "repos": {
            "workspace": "/test/workspace",
            "keywords": {}
        },
        "time_tracking": {
            "auto_start": True
        },
        "prompts": {},
        "context_files": {"files": []},
        "templates": {}
    }

    backend_config = {
        "url": "https://jira.example.com",
        "user": "backend-user",
        "transitions": {
            "on_start": {
                "from": ["New"],
                "to": "In Progress",
                "prompt": False
            }
        },
        "field_mappings": None
    }

    org_config = {
        "jira_project": "ORG",
        "jira_workstream_field": "workstream",
        "sync_filters": {
            "sync": {
                "status": ["New", "To Do"],
                "required_fields": [],
                "assignee": "currentUser()"
            }
        }
    }

    team_config = {
        "jira_workstream": "Platform",
        "time_tracking_enabled": True,
        "jira_comment_visibility_type": "group",
        "jira_comment_visibility_value": "Employees"
    }

    # Write files
    with open(loader.config_file, "w") as f:
        json.dump(user_config, f)

    backends_dir = loader.config_dir / "backends"
    backends_dir.mkdir(parents=True, exist_ok=True)
    with open(backends_dir / "jira.json", "w") as f:
        json.dump(backend_config, f)

    with open(loader.config_dir / "organization.json", "w") as f:
        json.dump(org_config, f)

    with open(loader.config_dir / "team.json", "w") as f:
        json.dump(team_config, f)

    # Load merged config
    config = loader.load_config()

    assert config is not None
    # From backend
    assert config.jira.url == "https://jira.example.com"
    assert config.jira.user == "backend-user"
    # From organization
    assert config.jira.project == "ORG"
    assert config.jira.workstream_field == "workstream"
    # From team
    assert config.jira.workstream == "Platform"
    assert config.jira.comment_visibility_type == "group"
    # From user
    assert config.repos.workspace == "/test/workspace"


def test_save_new_format_config_splits_correctly(temp_daf_home):
    """Test that saving splits Config into correct 4 files."""
    loader = ConfigLoader()

    # Create a config with old format first
    config = loader.create_default_config()

    # Set values across all categories
    config.jira.url = "https://test.jira.com"
    config.jira.user = "test-user"
    config.jira.project = "SPLIT"
    config.jira.workstream = "Platform"
    config.jira.workstream_field = "workstream_field"
    config.jira.comment_visibility_type = "role"
    config.repos.workspace = "/split/workspace"
    config.pr_template_url = "https://example.com/template"

    # Trigger migration (first save)
    loader.save_config(config)

    # Verify split happened correctly

    # User config
    with open(loader.config_file, "r") as f:
        user_data = json.load(f)
    assert "jira" not in user_data  # No JIRA in user config
    assert user_data["repos"]["workspace"] == "/split/workspace"
    assert user_data["pr_template_url"] == "https://example.com/template"

    # Backend config
    with open(loader.config_dir / "backends" / "jira.json", "r") as f:
        backend_data = json.load(f)
    assert backend_data["url"] == "https://test.jira.com"
    assert backend_data["user"] == "test-user"

    # Organization config
    with open(loader.config_dir / "organization.json", "r") as f:
        org_data = json.load(f)
    assert org_data["jira_project"] == "SPLIT"
    assert org_data["jira_workstream_field"] == "workstream_field"

    # Team config
    with open(loader.config_dir / "team.json", "r") as f:
        team_data = json.load(f)
    assert team_data["jira_workstream"] == "Platform"
    assert team_data["jira_comment_visibility_type"] == "role"


def test_migration_preserves_all_fields(temp_daf_home):
    """Test that migration preserves all configuration fields."""
    loader = ConfigLoader()

    # Create comprehensive old format config
    config = loader.create_default_config()

    # Set all possible fields
    config.jira.url = "https://full.test.com"
    config.jira.user = "full-user"
    config.jira.project = "FULL"
    config.jira.workstream = "Full Team"
    config.jira.affected_version = "v1.0"
    config.jira.acceptance_criteria_field = "ac_field"
    config.jira.workstream_field = "ws_field"
    config.jira.epic_link_field = "epic_field"
    config.jira.time_tracking = False
    config.jira.comment_visibility_type = "group"
    config.jira.comment_visibility_value = "Team"
    config.jira.field_cache_auto_refresh = False
    config.jira.field_cache_max_age_hours = 48

    config.repos.workspace = "/full/workspace"
    config.repos.keywords = {"test": ["pattern1", "pattern2"]}

    config.time_tracking.auto_start = False
    config.time_tracking.auto_pause_after = "1h"
    config.time_tracking.reminder_interval = "30m"

    config.pr_template_url = "https://template.url"
    config.prompts.auto_commit_on_complete = True
    config.prompts.auto_create_pr_on_complete = False
    config.gcp_vertex_region = "us-central1"

    # Trigger migration
    loader.save_config(config)

    # Load and verify all fields preserved
    loaded = loader.load_config()

    assert loaded.jira.url == "https://full.test.com"
    assert loaded.jira.user == "full-user"
    assert loaded.jira.project == "FULL"
    assert loaded.jira.workstream == "Full Team"
    assert loaded.jira.affected_version == "v1.0"
    assert loaded.jira.acceptance_criteria_field == "ac_field"
    assert loaded.jira.workstream_field == "ws_field"
    assert loaded.jira.epic_link_field == "epic_field"
    assert loaded.jira.time_tracking is False
    assert loaded.jira.comment_visibility_type == "group"
    assert loaded.jira.comment_visibility_value == "Team"
    assert loaded.jira.field_cache_auto_refresh is False
    assert loaded.jira.field_cache_max_age_hours == 48

    assert loaded.repos.workspace == "/full/workspace"
    assert loaded.repos.keywords == {"test": ["pattern1", "pattern2"]}

    assert loaded.time_tracking.auto_start is False
    assert loaded.time_tracking.auto_pause_after == "1h"
    assert loaded.time_tracking.reminder_interval == "30m"

    assert loaded.pr_template_url == "https://template.url"
    assert loaded.prompts.auto_commit_on_complete is True
    assert loaded.prompts.auto_create_pr_on_complete is False
    assert loaded.gcp_vertex_region == "us-central1"


def test_new_format_resave_does_not_remigrate(temp_daf_home):
    """Test that re-saving new format doesn't trigger migration again."""
    loader = ConfigLoader()

    # Create and migrate
    config = loader.create_default_config()
    config.jira.project = "NOMIGRATE"
    loader.save_config(config)

    # Verify migrated
    assert loader._is_old_format() is False

    # Count backup files
    backup_dir = loader.config_dir / ".deprecated"
    initial_backups = len(list(backup_dir.glob("config.json.*")))

    # Load, modify, save again
    config2 = loader.load_config()
    config2.jira.user = "modified"
    loader.save_config(config2)

    # Should still be new format
    assert loader._is_old_format() is False

    # Should not create additional backup
    final_backups = len(list(backup_dir.glob("config.json.*")))
    assert final_backups == initial_backups

    # Verify change persisted
    config3 = loader.load_config()
    assert config3.jira.user == "modified"
    assert config3.jira.project == "NOMIGRATE"


def test_load_new_format_with_missing_files(temp_daf_home):
    """Test loading new format gracefully handles missing files."""
    loader = ConfigLoader()

    # Remove backend/org files created by fixture - we want to test missing files
    backends_dir = loader.config_dir / "backends"
    if backends_dir.exists():
        import shutil
        shutil.rmtree(backends_dir)

    org_file = loader.config_dir / "organization.json"
    if org_file.exists():
        org_file.unlink()

    # Create only user config (no backend/org/team)
    user_config = {
        "backend_config_source": "local",
        "repos": {
            "workspace": "/test/workspace"
        },
        "time_tracking": {},
        "prompts": {},
        "context_files": {"files": []},
        "templates": {}
    }

    with open(loader.config_file, "w") as f:
        json.dump(user_config, f)

    # Load - should use defaults for missing files
    config = loader.load_config()

    assert config is not None
    assert config.repos.workspace == "/test/workspace"
    # Defaults for missing backend/org/team
    assert config.jira.url == "https://jira.example.com"  # Backend default
    assert config.jira.project is None  # Org default
    assert config.jira.workstream is None  # Team default


def test_backward_compatibility_config_access(temp_daf_home):
    """Test that existing code accessing config.jira.* still works."""
    loader = ConfigLoader()

    # Create new format config
    user_config = {"repos": {"workspace": "/test"}, "time_tracking": {}, "prompts": {}, "context_files": {"files": []}, "templates": {}}
    backend_config = {"url": "https://jira.test.com", "user": "test", "transitions": {}}
    org_config = {"jira_project": "COMPAT"}
    team_config = {"jira_workstream": "Compat Team"}

    with open(loader.config_file, "w") as f:
        json.dump(user_config, f)

    backends_dir = loader.config_dir / "backends"
    backends_dir.mkdir(parents=True, exist_ok=True)
    with open(backends_dir / "jira.json", "w") as f:
        json.dump(backend_config, f)

    with open(loader.config_dir / "organization.json", "w") as f:
        json.dump(org_config, f)

    with open(loader.config_dir / "team.json", "w") as f:
        json.dump(team_config, f)

    # Load config
    config = loader.load_config()

    # Test existing code patterns still work
    assert config.jira.project == "COMPAT"  # Org field
    assert config.jira.workstream == "Compat Team"  # Team field
    assert config.jira.url == "https://jira.test.com"  # Backend field
    assert config.repos.workspace == "/test"  # User field

    # Test modification and save still works
    config.jira.project = "MODIFIED"
    loader.save_config(config)

    loaded = loader.load_config()
    assert loaded.jira.project == "MODIFIED"
