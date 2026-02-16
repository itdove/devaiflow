"""Tests for workspace functionality (AAP-63377)."""

from pathlib import Path

import pytest

from devflow.config.models import Config, RepoConfig, WorkspaceDefinition


def test_workspace_definition_model():
    """Test WorkspaceDefinition model creation."""
    workspace = WorkspaceDefinition(
        name="primary",
        path="/Users/test/development"
    )

    assert workspace.name == "primary"
    assert workspace.path == "/Users/test/development"


def test_workspace_definition_path_expansion(tmp_path):
    """Test that WorkspaceDefinition expands ~ in paths."""
    workspace = WorkspaceDefinition(
        name="test",
        path="~/development"
    )

    # Path should be expanded (not contain ~)
    assert "~" not in workspace.path
    assert workspace.path.startswith("/")


def test_repo_config_with_workspaces():
    """Test RepoConfig with multiple workspaces."""
    config = RepoConfig(
        workspaces=[
            WorkspaceDefinition(name="primary", path="/path/primary"),
            WorkspaceDefinition(name="product-a", path="/path/product-a"),
            WorkspaceDefinition(name="feat-caching", path="/path/feat-caching"),
        ]
    )

    assert len(config.workspaces) == 3
    assert config.workspaces[0].name == "primary"


def test_repo_config_get_workspace_by_name():
    """Test getting workspace by name."""
    config = RepoConfig(
        workspaces=[
            WorkspaceDefinition(name="primary", path="/path/primary"),
            WorkspaceDefinition(name="product-a", path="/path/product-a"),
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
            WorkspaceDefinition(name="primary", path="/path/primary"),
        ]
    )

    workspace = config.get_workspace_by_name("nonexistent")
    assert workspace is None


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
    import uuid
    unique_suffix = str(uuid.uuid4())[:8]

    session1 = manager.create_session(
        name=f"workspace-session-1-{unique_suffix}",
        goal="Test workspace isolation",
        working_directory="repo",
        project_path="/test/repo",
        ai_agent_session_id=f"uuid-1-{unique_suffix}"
    )
    session1.workspace_name = "feat-caching"
    session1.status = "in_progress"
    manager.update_session(session1)

    session2 = manager.create_session(
        name=f"workspace-session-2-{unique_suffix}",
        goal="Test workspace isolation",
        working_directory="repo",
        project_path="/test/repo",
        ai_agent_session_id=f"uuid-2-{unique_suffix}"
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
    assert active_in_feat_caching.name == f"workspace-session-1-{unique_suffix}"

    # Check for active session in product-a workspace
    active_in_product_a = manager.get_active_session_for_project(
        "/test/repo",
        workspace_name="product-a"
    )
    assert active_in_product_a is not None
    assert active_in_product_a.name == f"workspace-session-2-{unique_suffix}"

    # Check for active session in non-existent workspace
    active_in_other = manager.get_active_session_for_project(
        "/test/repo",
        workspace_name="other-workspace"
    )
    assert active_in_other is None

    # Cleanup
    manager.delete_session(f"workspace-session-1-{unique_suffix}")
    manager.delete_session(f"workspace-session-2-{unique_suffix}")


def test_get_active_session_for_project_no_workspace():
    """Test backward compatibility - workspace_name=None still works."""
    from devflow.config.loader import ConfigLoader
    from devflow.session.manager import SessionManager

    config_loader = ConfigLoader()
    manager = SessionManager(config_loader)

    # Create session without workspace_name (backward compatibility)
    import uuid
    unique_suffix = str(uuid.uuid4())[:8]

    session = manager.create_session(
        name=f"legacy-session-{unique_suffix}",
        goal="Test backward compatibility",
        working_directory="repo",
        project_path="/test/repo",
        ai_agent_session_id=f"uuid-legacy-{unique_suffix}"
    )
    session.status = "in_progress"
    manager.update_session(session)

    # Should find session when no workspace specified
    active = manager.get_active_session_for_project("/test/repo")
    assert active is not None
    assert active.name == f"legacy-session-{unique_suffix}"

    # Should also find session when workspace_name=None explicitly
    active_none = manager.get_active_session_for_project(
        "/test/repo",
        workspace_name=None
    )
    assert active_none is not None
    assert active_none.name == f"legacy-session-{unique_suffix}"

    # Cleanup
    manager.delete_session(f"legacy-session-{unique_suffix}")


def test_workspace_persistence_in_session():
    """Test that workspace_name is persisted in session metadata."""
    from devflow.config.loader import ConfigLoader
    from devflow.session.manager import SessionManager

    config_loader = ConfigLoader()
    manager = SessionManager(config_loader)

    # Create session with workspace
    import uuid
    unique_suffix = str(uuid.uuid4())[:8]

    session = manager.create_session(
        name=f"test-workspace-persist-{unique_suffix}",
        goal="Test workspace persistence",
        working_directory="repo",
        project_path="/test/repo",
        ai_agent_session_id=f"uuid-persist-{unique_suffix}"
    )
    session.workspace_name = "feat-caching"
    manager.update_session(session)

    # Reload session and verify workspace persisted
    loaded_session = manager.get_session(f"test-workspace-persist-{unique_suffix}")
    assert loaded_session is not None
    assert loaded_session.workspace_name == "feat-caching"

    # Cleanup
    manager.delete_session(f"test-workspace-persist-{unique_suffix}")


def test_open_command_w_flag_persists_workspace(monkeypatch, tmp_path):
    """Test that daf open -w flag persists workspace selection (AAP-64886)."""
    from devflow.config.loader import ConfigLoader
    from devflow.session.manager import SessionManager
    from devflow.cli.utils import select_workspace, get_workspace_path
    from devflow.config.models import Config, JiraConfig, RepoConfig, WorkspaceDefinition

    # Setup config with multiple workspaces
    config_loader = ConfigLoader()

    # Create config object with workspaces
    config = Config(
        jira=JiraConfig(url="https://jira.example.com", transitions={}),
        repos=RepoConfig(
            workspaces=[
                WorkspaceDefinition(name="primary", path=str(tmp_path / "primary")),
                WorkspaceDefinition(name="product-a", path=str(tmp_path / "product-a")),
            ]
        )
    )

    # Mock the config loader to return our test config
    monkeypatch.setattr(config_loader, 'load_config', lambda: config)

    # Create session with initial workspace
    import uuid
    unique_suffix = str(uuid.uuid4())[:8]

    manager = SessionManager(config_loader)
    session = manager.create_session(
        name=f"test-session-w-flag-{unique_suffix}",
        goal="Test -w flag persistence",
        working_directory="repo",
        project_path=str(tmp_path / "primary" / "repo"),
        ai_agent_session_id=f"uuid-wflag-{unique_suffix}"
    )
    session.workspace_name = "primary"
    manager.update_session(session)

    # Simulate daf open with -w flag selecting different workspace
    # This mimics the code in open_command.py lines 197-218
    selected_workspace_name = select_workspace(
        config,
        workspace_flag="product-a",  # User specified -w product-a
        session=session,
        skip_prompt=False
    )

    workspace_path = None
    if selected_workspace_name:
        workspace_path = get_workspace_path(config, selected_workspace_name)

        # AAP-64886: Save selected workspace to session if it changed
        if selected_workspace_name != session.workspace_name:
            session.workspace_name = selected_workspace_name
            manager.update_session(session)

    # Verify workspace was updated
    assert session.workspace_name == "product-a"

    # Reload session and verify persistence
    loaded_session = manager.get_session(f"test-session-w-flag-{unique_suffix}")
    assert loaded_session is not None
    assert loaded_session.workspace_name == "product-a"

    # Verify workspace path was updated correctly
    assert workspace_path == str(tmp_path / "product-a")

    # Cleanup
    manager.delete_session(f"test-session-w-flag-{unique_suffix}")


def test_open_command_w_flag_no_update_when_same_workspace(monkeypatch, tmp_path):
    """Test that daf open -w doesn't update session if workspace unchanged (AAP-64886)."""
    from devflow.config.loader import ConfigLoader
    from devflow.session.manager import SessionManager
    from devflow.cli.utils import select_workspace, get_workspace_path
    from devflow.config.models import Config, JiraConfig, RepoConfig, WorkspaceDefinition

    # Setup config with multiple workspaces
    config_loader = ConfigLoader()

    # Create config object with workspaces
    config = Config(
        jira=JiraConfig(url="https://jira.example.com", transitions={}),
        repos=RepoConfig(
            workspaces=[
                WorkspaceDefinition(name="primary", path=str(tmp_path / "primary")),
                WorkspaceDefinition(name="product-a", path=str(tmp_path / "product-a")),
            ]
        )
    )

    # Mock the config loader to return our test config
    monkeypatch.setattr(config_loader, 'load_config', lambda: config)

    # Create session with workspace
    import uuid
    unique_suffix = str(uuid.uuid4())[:8]

    manager = SessionManager(config_loader)
    session = manager.create_session(
        name=f"test-session-no-update-{unique_suffix}",
        goal="Test no update when same workspace",
        working_directory="repo",
        project_path=str(tmp_path / "primary" / "repo"),
        ai_agent_session_id=f"uuid-noupdate-{unique_suffix}"
    )
    session.workspace_name = "primary"
    manager.update_session(session)

    # Get last_active before simulated open
    original_last_active = session.last_active

    # Simulate daf open with -w flag selecting SAME workspace
    selected_workspace_name = select_workspace(
        config,
        workspace_flag="primary",  # Same workspace
        session=session,
        skip_prompt=False
    )

    workspace_path = None
    if selected_workspace_name:
        workspace_path = get_workspace_path(config, selected_workspace_name)

        # AAP-64886: Only update if workspace changed
        if selected_workspace_name != session.workspace_name:
            session.workspace_name = selected_workspace_name
            manager.update_session(session)

    # Verify workspace is still primary
    assert session.workspace_name == "primary"

    # Verify last_active didn't change (no unnecessary update)
    assert session.last_active == original_last_active

    # Cleanup
    manager.delete_session(f"test-session-no-update-{unique_suffix}")


def test_new_command_w_flag_uses_correct_workspace(monkeypatch, tmp_path):
    """Test that daf new -w flag uses correct workspace for repository discovery (AAP-64886)."""
    from devflow.config.loader import ConfigLoader
    from devflow.cli.commands.new_command import _suggest_and_select_repository
    from devflow.config.models import Config, JiraConfig, RepoConfig, WorkspaceDefinition
    from devflow.git.utils import GitUtils
    import subprocess

    # Create two workspace directories with different repositories
    primary_ws = tmp_path / "primary"
    ai_ws = tmp_path / "ai"
    primary_ws.mkdir()
    ai_ws.mkdir()

    # Create git repos in primary workspace
    (primary_ws / "backend-api").mkdir()
    (primary_ws / "frontend-app").mkdir()

    # Create git repos in ai workspace
    (ai_ws / "devaiflow").mkdir()
    (ai_ws / "ml-models").mkdir()

    # Initialize git repos (minimal setup)
    def init_git_repo(path):
        subprocess.run(["git", "init"], cwd=path, capture_output=True)
        subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=path, capture_output=True)
        subprocess.run(["git", "config", "user.name", "Test User"], cwd=path, capture_output=True)

    init_git_repo(primary_ws / "backend-api")
    init_git_repo(primary_ws / "frontend-app")
    init_git_repo(ai_ws / "devaiflow")
    init_git_repo(ai_ws / "ml-models")

    # Setup config with multiple workspaces
    config_loader = ConfigLoader()
    config = Config(
        jira=JiraConfig(url="https://jira.example.com", transitions={}),
        repos=RepoConfig(
            workspaces=[
                WorkspaceDefinition(name="primary", path=str(primary_ws)),
                WorkspaceDefinition(name="ai", path=str(ai_ws)),
            ]
        )
    )

    # Mock the config loader
    monkeypatch.setattr(config_loader, 'load_config', lambda: config)

    # Mock Prompt.ask to select first repository automatically
    from rich.prompt import Prompt
    monkeypatch.setattr(Prompt, 'ask', lambda *args, **kwargs: "1")

    # Test repository discovery with ai workspace
    selected_path = _suggest_and_select_repository(
        config_loader,
        workspace_name="ai"
    )

    # Verify the selected path is from ai workspace, not primary
    assert selected_path is not None
    assert "devaiflow" in selected_path or "ml-models" in selected_path
    assert str(ai_ws) in selected_path
    assert str(primary_ws) not in selected_path


