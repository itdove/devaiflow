"""Tests for ConfigLoader."""

import json
from pathlib import Path

import pytest

from devflow.config.loader import ConfigLoader
from devflow.config.models import Config, SessionIndex, Session


def test_config_loader_initialization(temp_daf_home):
    """Test ConfigLoader initialization."""
    loader = ConfigLoader()

    assert loader.config_dir.exists()
    assert loader.sessions_dir.exists()
    assert loader.config_file == loader.config_dir / "config.json"
    assert loader.sessions_file == loader.config_dir / "sessions.json"


def test_load_config_nonexistent(temp_daf_home):
    """Test loading config when file doesn't exist."""
    loader = ConfigLoader()
    config = loader.load_config()

    assert config is None


def test_save_and_load_config(temp_daf_home):
    """Test saving and loading configuration."""
    loader = ConfigLoader()

    # Create default config
    config = loader.create_default_config()

    assert config is not None
    assert config.jira is not None
    assert config.repos is not None
    assert config.time_tracking is not None

    # Load it back
    loaded_config = loader.load_config()

    assert loaded_config is not None
    assert loaded_config.jira.url == "https://jira.example.com"
    assert len(loaded_config.repos.workspaces) == 1
    assert loaded_config.repos.workspaces[0].path == str(Path.home() / "development")


def test_load_config_invalid_json(temp_daf_home):
    """Test loading config with invalid JSON."""
    loader = ConfigLoader()

    # Write invalid JSON
    with open(loader.config_file, "w") as f:
        f.write("{ invalid json }")

    with pytest.raises(ValueError, match="Failed to load config"):
        loader.load_config()


def test_load_sessions_nonexistent(temp_daf_home):
    """Test loading sessions when file doesn't exist."""
    loader = ConfigLoader()
    index = loader.load_sessions()

    assert index is not None
    assert len(index.sessions) == 0


def test_save_and_load_sessions(temp_daf_home):
    """Test saving and loading session index."""
    loader = ConfigLoader()

    # Create session index with some sessions
    index = SessionIndex()
    session = Session(
        name="test-session",        goal="Test goal",
        working_directory="test-dir",
        project_path="/path/to/project",
        ai_agent_session_id="test-uuid-123",
    )
    index.sessions["test-session"] = session

    # Save it
    loader.save_sessions(index)

    # Load it back
    loaded_index = loader.load_sessions()

    assert len(loaded_index.sessions) == 1
    assert "test-session" in loaded_index.sessions
    assert loaded_index.sessions["test-session"].name == "test-session"
    assert loaded_index.sessions["test-session"].goal == "Test goal"


def test_load_sessions_invalid_json(temp_daf_home):
    """Test loading sessions with invalid JSON."""
    loader = ConfigLoader()

    # Write invalid JSON
    with open(loader.sessions_file, "w") as f:
        f.write("{ invalid json }")

    with pytest.raises(ValueError, match="Failed to load sessions"):
        loader.load_sessions()


def test_get_session_dir(temp_daf_home):
    """Test getting session directory."""
    loader = ConfigLoader()

    session_dir = loader.get_session_dir("my-session")

    assert session_dir.exists()
    assert session_dir == loader.sessions_dir / "my-session"
    assert session_dir.is_dir()


def test_get_session_dir_creates_directory(temp_daf_home):
    """Test that get_session_dir creates directory if it doesn't exist."""
    loader = ConfigLoader()

    session_dir = loader.get_session_dir("new-session")

    assert session_dir.exists()
    assert session_dir.is_dir()


def test_config_loader_custom_dir(tmp_path):
    """Test ConfigLoader with custom directory."""
    custom_dir = tmp_path / "custom-config"

    loader = ConfigLoader(config_dir=custom_dir)

    assert loader.config_dir == custom_dir
    assert custom_dir.exists()
    assert (custom_dir / "sessions").exists()


def test_create_default_config(temp_daf_home):
    """Test creating default configuration."""
    loader = ConfigLoader()

    config = loader.create_default_config()

    assert config is not None
    assert config.jira is not None
    assert config.jira.url == "https://jira.example.com"
    # Default transitions are now included in default config
    assert "on_start" in config.jira.transitions
    assert "on_complete" in config.jira.transitions
    assert config.repos is not None
    assert config.time_tracking is not None

    # Verify it was saved
    assert loader.config_file.exists()

    # When loaded back, patches should be applied
    loaded_config = loader.load_config()
    assert loaded_config.jira.url == "https://jira.example.com"
    assert "on_start" in loaded_config.jira.transitions
    assert "on_complete" in loaded_config.jira.transitions


def test_default_sync_filters_include_in_progress(temp_daf_home):
    """Test that default sync filters include 'In Progress' status."""
    loader = ConfigLoader()
    config = loader.create_default_config()

    assert config is not None
    assert "sync" in config.jira.filters
    sync_filters = config.jira.filters["sync"]

    # Verify status filter includes all three statuses
    assert "New" in sync_filters.status
    assert "To Do" in sync_filters.status
    assert "In Progress" in sync_filters.status
    assert len(sync_filters.status) == 3


def test_config_persistence(temp_daf_home):
    """Test that config persists across ConfigLoader instances."""
    # Create and save config with first loader
    loader1 = ConfigLoader()
    config1 = loader1.create_default_config()

    # Load with second loader
    loader2 = ConfigLoader()
    config2 = loader2.load_config()

    assert config2 is not None
    assert config2.jira.url == config1.jira.url


def test_sessions_persistence(temp_daf_home):
    """Test that sessions persist across ConfigLoader instances."""
    # Save sessions with first loader
    loader1 = ConfigLoader()
    index1 = SessionIndex()
    session = Session(
        name="persist-test",        goal="Test",
        working_directory="test-dir",
        project_path="/path",
        ai_agent_session_id="uuid-1",
    )
    index1.sessions["persist-test"] = session
    loader1.save_sessions(index1)

    # Load with second loader
    loader2 = ConfigLoader()
    index2 = loader2.load_sessions()

    assert "persist-test" in index2.sessions
    

def test_load_sessions_with_mock_services(temp_daf_home, monkeypatch):
    """Test that sessions load from mock storage when DAF_MOCK_MODE=1."""
    from devflow.config.models import Session

    loader = ConfigLoader()

    # Set environment to enable mock mode
    monkeypatch.setenv("DAF_MOCK_MODE", "1")

    # Save mock session data directly
    from devflow.mocks.persistence import MockDataStore
    store = MockDataStore()
    store.clear_all()

    mock_session_data = {
        "sessions": {
            "mock-session": {
                "name": "mock-session",
                "goal": "Mock test",
                "working_directory": "/path/to/mock",
                "project_path": "/path/to/mock",
                "ai_agent_session_id": "mock-uuid-123",
            }
        }
    }
    store.save_session_index(mock_session_data)

    # Load sessions - should come from mock storage
    index = loader.load_sessions()

    assert "mock-session" in index.sessions
    assert index.sessions["mock-session"].name == "mock-session"


def test_save_sessions_with_mock_services(temp_daf_home, monkeypatch):
    """Test that sessions save to mock storage when DAF_MOCK_MODE=1."""
    from devflow.config.models import SessionIndex, Session

    loader = ConfigLoader()

    # Set environment to enable mock mode
    monkeypatch.setenv("DAF_MOCK_MODE", "1")

    # Create session index
    index = SessionIndex()
    session = Session(
        name="test-mock-session",        goal="Test with mocks",
        working_directory="/test/path",
        project_path="/test/path",
        ai_agent_session_id="test-mock-uuid",
    )
    index.sessions["test-mock-session"] = session

    # Save sessions
    loader.save_sessions(index)

    # Verify saved to mock storage
    from devflow.mocks.persistence import MockDataStore
    store = MockDataStore()
    mock_data = store.load_session_index()

    assert mock_data is not None
    assert "sessions" in mock_data
    assert "test-mock-session" in mock_data["sessions"]
    assert mock_data["sessions"]["test-mock-session"]["name"] == "test-mock-session"


def test_save_config_preserves_none_values(temp_daf_home):
    """Test that save_config preserves fields with None values (PROJ-60465).

    This is a regression test for the bug where exclude_none=True caused
    fields with None values to be deleted from config.json.
    """
    loader = ConfigLoader()
    config = loader.create_default_config()

    # Set pr_template_url to None explicitly
    config.pr_template_url = None

    # Save the config
    loader.save_config(config)

    # Load it back (without patches to verify raw persistence)
    with open(loader.config_file, "r") as f:
        config_json = json.load(f)

    # Verify that pr_template_url exists in JSON with null value
    assert "pr_template_url" in config_json
    assert config_json["pr_template_url"] is None

    # Verify that prompts fields exist with null values
    assert "prompts" in config_json
    # All prompts fields should be present (even if None)
    prompts = config_json["prompts"]
    assert "auto_commit_on_complete" in prompts
    assert "auto_accept_ai_commit_message" in prompts
    assert "auto_create_pr_on_complete" in prompts


def test_pr_template_url_persists_across_save_load(temp_daf_home):
    """Test that pr_template_url persists across multiple save/load cycles (PROJ-60465)."""
    loader = ConfigLoader()
    config = loader.create_default_config()

    # Set pr_template_url to None
    config.pr_template_url = None
    loader.save_config(config)

    # Load it back
    loaded_config = loader.load_config()
    assert loaded_config is not None
    assert loaded_config.pr_template_url is None

    # Modify some other field
    loaded_config.jira.project = "NEW-PROJECT"
    loader.save_config(loaded_config)

    # Load again
    loaded_config2 = loader.load_config()
    assert loaded_config2 is not None
    # pr_template_url should still be None (not deleted)
    assert loaded_config2.pr_template_url is None
    assert loaded_config2.jira.project == "NEW-PROJECT"


def test_prompts_fields_persist_across_save_load(temp_daf_home):
    """Test that prompts.* fields persist across save/load cycles (PROJ-60465)."""
    loader = ConfigLoader()
    config = loader.create_default_config()

    # All prompts fields should default to None or their default values
    config.prompts.auto_commit_on_complete = None
    config.prompts.auto_accept_ai_commit_message = None
    config.prompts.auto_create_pr_on_complete = None

    loader.save_config(config)

    # Load it back
    loaded_config = loader.load_config()
    assert loaded_config is not None

    # Verify all prompts fields are preserved (even if None)
    assert hasattr(loaded_config, "prompts")
    assert hasattr(loaded_config.prompts, "auto_commit_on_complete")
    assert hasattr(loaded_config.prompts, "auto_accept_ai_commit_message")
    assert hasattr(loaded_config.prompts, "auto_create_pr_on_complete")


def test_field_auto_refresh_preserves_optional_fields(temp_daf_home):
    """Test that auto-refresh of JIRA field mappings preserves optional fields (PROJ-60465).

    This simulates the scenario where JIRA field auto-refresh (devflow/cli/main.py:94-101)
    would delete pr_template_url and prompts.* fields.
    """
    loader = ConfigLoader()
    config = loader.create_default_config()

    # Set pr_template_url to a value
    config.pr_template_url = "https://github.com/org/repo/blob/main/PULL_REQUEST_TEMPLATE.md"

    # Set some prompts fields
    config.prompts.auto_commit_on_complete = True
    config.prompts.auto_create_pr_on_complete = False

    loader.save_config(config)

    # Simulate auto-refresh (as in devflow/cli/main.py:87-101)
    # 1. Load config
    config_reloaded = loader.load_config()

    # 2. Modify only field_mappings and timestamp (simulate field discovery)
    config_reloaded.jira.field_mappings = {"test_field": {"id": "customfield_12345"}}
    from datetime import datetime
    config_reloaded.jira.field_cache_timestamp = datetime.now().isoformat()

    # 3. Save config (line 94)
    loader.save_config(config_reloaded)

    # 4. Reload config WITH patches (line 98)
    config_patched = loader.load_config()

    # 5. Save again with patches applied (line 101)
    loader.save_config(config_patched)

    # Verify that pr_template_url and prompts are NOT deleted
    config_final = loader.load_config()
    assert config_final.pr_template_url == "https://github.com/org/repo/blob/main/PULL_REQUEST_TEMPLATE.md"
    assert config_final.prompts.auto_commit_on_complete is True
    assert config_final.prompts.auto_create_pr_on_complete is False


def test_optional_fields_with_none_in_json(temp_daf_home):
    """Test that optional fields with null values in JSON are loaded correctly (PROJ-60465)."""
    loader = ConfigLoader()

    # Create a config JSON with explicit null values
    config_data = {
        "jira": {
            "url": "https://jira.example.com",
            "user": "test-user",
            "project": None,
            "workstream": None,
            "affected_version": None,
            "field_mappings": None,
            "field_cache_timestamp": None,
            "transitions": {
                "on_start": {
                    "from": ["New", "To Do"],
                    "to": "In Progress",
                    "prompt": False
                },
                "on_complete": {
                    "from": ["In Progress"],
                    "to": "",
                    "prompt": True
                }
            },
            "filters": {
                "sync": {
                    "status": ["New", "To Do", "In Progress"],
                    "required_fields": [],
                    "assignee": "currentUser()"
                }
            },
            "comment_visibility_type": "group",
            "comment_visibility_value": "project-team"
        },
        "repos": {
            "workspace": str(Path.home() / "development"),
            "keywords": {}
        },
        "time_tracking": {},
        "pr_template_url": None,
        "mock_services": None,
        "prompts": {
            "auto_commit_on_complete": None,
            "auto_accept_ai_commit_message": None,
            "auto_create_pr_on_complete": None,
            "auto_add_issue_summary": None
        }
    }

    # Write the config
    with open(loader.config_file, "w") as f:
        json.dump(config_data, f, indent=2)

    # Load the config
    config = loader.load_config()

    assert config is not None
    assert config.pr_template_url is None
    assert config.jira.project is None
    assert config.jira.custom_field_defaults is None or config.jira.custom_field_defaults == {}
    assert config.prompts.auto_commit_on_complete is None

    # Save it back
    loader.save_config(config)

    # Load again and verify fields still exist
    config2 = loader.load_config()
    assert config2 is not None
    assert config2.pr_template_url is None
