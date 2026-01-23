"""Tests for workspace functionality (AAP-63377)."""

from pathlib import Path

import pytest

from devflow.config.models import Config, RepoConfig, WorkspaceDefinition


def test_workspace_definition_model():
    """Test WorkspaceDefinition model creation."""
    workspace = WorkspaceDefinition(
        name="primary",
        path="/Users/test/development",
        is_default=True
    )

    assert workspace.name == "primary"
    assert workspace.path == "/Users/test/development"
    assert workspace.is_default is True


def test_workspace_definition_path_expansion(tmp_path):
    """Test that WorkspaceDefinition expands ~ in paths."""
    workspace = WorkspaceDefinition(
        name="test",
        path="~/development",
        is_default=False
    )

    # Path should be expanded (not contain ~)
    assert "~" not in workspace.path
    assert workspace.path.startswith("/")


def test_repo_config_with_workspaces():
    """Test RepoConfig with multiple workspaces."""
    config = RepoConfig(
        workspaces=[
            WorkspaceDefinition(name="primary", path="/path/primary", is_default=True),
            WorkspaceDefinition(name="product-a", path="/path/product-a", is_default=False),
            WorkspaceDefinition(name="feat-caching", path="/path/feat-caching", is_default=False),
        ]
    )

    assert len(config.workspaces) == 3
    assert config.workspaces[0].name == "primary"
    assert config.workspaces[0].is_default is True


def test_repo_config_backward_compatibility_migration():
    """Test that single workspace string migrates to workspaces list."""
    # Old config format with single workspace string
    config = RepoConfig(
        workspace="/Users/test/development"
    )

    # Should auto-migrate to workspaces list
    assert len(config.workspaces) == 1
    assert config.workspaces[0].name == "default"
    assert config.workspaces[0].path == "/Users/test/development"
    assert config.workspaces[0].is_default is True


def test_repo_config_get_default_workspace():
    """Test getting the default workspace."""
    config = RepoConfig(
        workspaces=[
            WorkspaceDefinition(name="primary", path="/path/primary", is_default=False),
            WorkspaceDefinition(name="product-a", path="/path/product-a", is_default=True),
            WorkspaceDefinition(name="feat-caching", path="/path/feat-caching", is_default=False),
        ]
    )

    default = config.get_default_workspace()
    assert default is not None
    assert default.name == "product-a"
    assert default.is_default is True


def test_repo_config_get_default_workspace_none():
    """Test get_default_workspace when no default is set."""
    config = RepoConfig(
        workspaces=[
            WorkspaceDefinition(name="primary", path="/path/primary", is_default=False),
            WorkspaceDefinition(name="product-a", path="/path/product-a", is_default=False),
        ]
    )

    default = config.get_default_workspace()
    assert default is None


def test_repo_config_get_workspace_by_name():
    """Test getting workspace by name."""
    config = RepoConfig(
        workspaces=[
            WorkspaceDefinition(name="primary", path="/path/primary", is_default=True),
            WorkspaceDefinition(name="product-a", path="/path/product-a", is_default=False),
        ]
    )

    workspace = config.get_workspace_by_name("product-a")
    assert workspace is not None
    assert workspace.name == "product-a"
    assert workspace.path == "/path/product-a"


def test_repo_config_get_workspace_by_name_not_found():
    """Test getting non-existent workspace by name."""
    config = RepoConfig(
        workspaces=[
            WorkspaceDefinition(name="primary", path="/path/primary", is_default=True),
        ]
    )

    workspace = config.get_workspace_by_name("nonexistent")
    assert workspace is None


def test_repo_config_multiple_defaults_correction():
    """Test that RepoConfig corrects multiple default workspaces."""
    # Create config with multiple defaults (invalid state)
    config = RepoConfig(
        workspaces=[
            WorkspaceDefinition(name="primary", path="/path/primary", is_default=True),
            WorkspaceDefinition(name="product-a", path="/path/product-a", is_default=True),
            WorkspaceDefinition(name="feat-caching", path="/path/feat-caching", is_default=False),
        ]
    )

    # Should auto-correct to have only one default (the first one)
    default_count = sum(1 for w in config.workspaces if w.is_default)
    assert default_count == 1
    assert config.workspaces[0].is_default is True
    assert config.workspaces[1].is_default is False


def test_session_workspace_name_field():
    """Test that Session model has workspace_name field."""
    from devflow.config.models import Session

    session = Session(
        name="test-session",
        workspace_name="primary"
    )

    assert session.workspace_name == "primary"


def test_session_workspace_name_optional():
    """Test that workspace_name is optional on Session."""
    from devflow.config.models import Session

    session = Session(
        name="test-session"
    )

    assert session.workspace_name is None


def test_get_active_session_for_project_with_workspace():
    """Test workspace-aware concurrent session detection."""
    from devflow.config.loader import ConfigLoader
    from devflow.session.manager import SessionManager
    from devflow.config.models import Session

    config_loader = ConfigLoader()
    manager = SessionManager(config_loader)

    # Create two sessions on same project but different workspaces
    session1 = manager.create_session(
        name="session-1",
        goal="Test workspace isolation",
        working_directory="repo",
        project_path="/test/repo",
        ai_agent_session_id="uuid-1"
    )
    session1.workspace_name = "feat-caching"
    session1.status = "in_progress"
    manager.update_session(session1)

    session2 = manager.create_session(
        name="session-2",
        goal="Test workspace isolation",
        working_directory="repo",
        project_path="/test/repo",
        ai_agent_session_id="uuid-2"
    )
    session2.workspace_name = "product-a"
    session2.status = "in_progress"
    manager.update_session(session2)

    # Check for active session in feat-caching workspace
    active_in_feat_caching = manager.get_active_session_for_project(
        "/test/repo",
        workspace_name="feat-caching"
    )
    assert active_in_feat_caching is not None
    assert active_in_feat_caching.name == "session-1"

    # Check for active session in product-a workspace
    active_in_product_a = manager.get_active_session_for_project(
        "/test/repo",
        workspace_name="product-a"
    )
    assert active_in_product_a is not None
    assert active_in_product_a.name == "session-2"

    # Check for active session in non-existent workspace
    active_in_other = manager.get_active_session_for_project(
        "/test/repo",
        workspace_name="other-workspace"
    )
    assert active_in_other is None

    # Cleanup
    manager.delete_session("session-1")
    manager.delete_session("session-2")


def test_get_active_session_for_project_no_workspace():
    """Test backward compatibility - workspace_name=None still works."""
    from devflow.config.loader import ConfigLoader
    from devflow.session.manager import SessionManager

    config_loader = ConfigLoader()
    manager = SessionManager(config_loader)

    # Create session without workspace_name (backward compatibility)
    session = manager.create_session(
        name="legacy-session",
        goal="Test backward compatibility",
        working_directory="repo",
        project_path="/test/repo",
        ai_agent_session_id="uuid-1"
    )
    session.status = "in_progress"
    manager.update_session(session)

    # Should find session when no workspace specified
    active = manager.get_active_session_for_project("/test/repo")
    assert active is not None
    assert active.name == "legacy-session"

    # Should also find session when workspace_name=None explicitly
    active_none = manager.get_active_session_for_project(
        "/test/repo",
        workspace_name=None
    )
    assert active_none is not None
    assert active_none.name == "legacy-session"

    # Cleanup
    manager.delete_session("legacy-session")


def test_workspace_persistence_in_session():
    """Test that workspace_name is persisted in session metadata."""
    from devflow.config.loader import ConfigLoader
    from devflow.session.manager import SessionManager

    config_loader = ConfigLoader()
    manager = SessionManager(config_loader)

    # Create session with workspace
    session = manager.create_session(
        name="test-workspace-persist",
        goal="Test workspace persistence",
        working_directory="repo",
        project_path="/test/repo",
        ai_agent_session_id="uuid-1"
    )
    session.workspace_name = "feat-caching"
    manager.update_session(session)

    # Reload session and verify workspace persisted
    loaded_session = manager.get_session("test-workspace-persist")
    assert loaded_session is not None
    assert loaded_session.workspace_name == "feat-caching"

    # Cleanup
    manager.delete_session("test-workspace-persist")
