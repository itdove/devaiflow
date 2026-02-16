"""Tests for workspace commands (AAP-63388)."""

from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

import pytest

from devflow.config.models import Config, JiraConfig, RepoConfig, WorkspaceDefinition


@pytest.fixture
def mock_config(tmp_path):
    """Create a test config with workspaces."""
    primary_path = tmp_path / "primary"
    product_path = tmp_path / "product-a"
    primary_path.mkdir()
    product_path.mkdir()

    return Config(
        jira=JiraConfig(url="https://jira.example.com", transitions={}),
        repos=RepoConfig(
            workspaces=[
                WorkspaceDefinition(name="primary", path=str(primary_path)),
                WorkspaceDefinition(name="product-a", path=str(product_path)),
            ],
            last_used_workspace="primary"
        )
    )


@pytest.fixture
def mock_config_loader(mock_config):
    """Create a mock config loader."""
    from devflow.config.loader import ConfigLoader

    loader = Mock(spec=ConfigLoader)
    loader.load_config.return_value = mock_config
    loader.save_config.return_value = None
    return loader


def test_list_workspaces_success(mock_config_loader, capsys):
    """Test listing workspaces successfully."""
    from devflow.cli.commands.workspace_commands import list_workspaces

    with patch('devflow.cli.commands.workspace_commands.ConfigLoader', return_value=mock_config_loader):
        list_workspaces()

    captured = capsys.readouterr()
    assert "primary" in captured.out
    assert "product-a" in captured.out


def test_list_workspaces_no_config(capsys):
    """Test listing workspaces when no config exists."""
    from devflow.cli.commands.workspace_commands import list_workspaces

    mock_loader = Mock()
    mock_loader.load_config.return_value = None

    with patch('devflow.cli.commands.workspace_commands.ConfigLoader', return_value=mock_loader):
        list_workspaces()

    captured = capsys.readouterr()
    assert "No configuration found" in captured.out


def test_list_workspaces_empty(mock_config_loader, capsys):
    """Test listing workspaces when none configured."""
    from devflow.cli.commands.workspace_commands import list_workspaces

    # Clear workspaces
    mock_config_loader.load_config.return_value.repos.workspaces = []

    with patch('devflow.cli.commands.workspace_commands.ConfigLoader', return_value=mock_config_loader):
        list_workspaces()

    captured = capsys.readouterr()
    assert "No workspaces configured" in captured.out


@patch('devflow.cli.commands.workspace_commands.require_outside_claude', lambda f: f)
def test_add_workspace_success(mock_config_loader, tmp_path, capsys):
    """Test adding a workspace successfully."""
    from devflow.cli.commands.workspace_commands import add_workspace

    new_workspace = tmp_path / "new-workspace"
    new_workspace.mkdir()

    with patch('devflow.cli.commands.workspace_commands.ConfigLoader', return_value=mock_config_loader):
        with patch('devflow.utils.workspace_utils.ensure_workspace_skills_and_commands', return_value=(True, None)):
            add_workspace("new-ws", str(new_workspace), set_default=False)

    captured = capsys.readouterr()
    assert "Added workspace: new-ws" in captured.out
    assert mock_config_loader.save_config.called


@patch('devflow.cli.commands.workspace_commands.require_outside_claude', lambda f: f)
def test_add_workspace_no_config(capsys):
    """Test adding workspace when no config exists."""
    from devflow.cli.commands.workspace_commands import add_workspace

    mock_loader = Mock()
    mock_loader.load_config.return_value = None

    with patch('devflow.cli.commands.workspace_commands.ConfigLoader', return_value=mock_loader):
        add_workspace("test", "/tmp/test")

    captured = capsys.readouterr()
    assert "No configuration found" in captured.out


@patch('devflow.cli.commands.workspace_commands.require_outside_claude', lambda f: f)
def test_add_workspace_already_exists(mock_config_loader, tmp_path, capsys):
    """Test adding workspace with duplicate name."""
    from devflow.cli.commands.workspace_commands import add_workspace

    with patch('devflow.cli.commands.workspace_commands.ConfigLoader', return_value=mock_config_loader):
        add_workspace("primary", str(tmp_path / "duplicate"))

    captured = capsys.readouterr()
    assert "Workspace already exists: primary" in captured.out


@patch('devflow.cli.commands.workspace_commands.require_outside_claude', lambda f: f)
def test_add_workspace_auto_derive_name_from_path(mock_config_loader, tmp_path, capsys):
    """Test auto-deriving workspace name from path."""
    from devflow.cli.commands.workspace_commands import add_workspace

    new_workspace = tmp_path / "auto-named-workspace"
    new_workspace.mkdir()

    with patch('devflow.cli.commands.workspace_commands.ConfigLoader', return_value=mock_config_loader):
        with patch('devflow.utils.workspace_utils.ensure_workspace_skills_and_commands', return_value=(True, None)):
            # Pass path as name argument (single arg mode)
            add_workspace(str(new_workspace), None, set_default=False)

    captured = capsys.readouterr()
    assert "Auto-derived workspace name" in captured.out


@patch('devflow.cli.commands.workspace_commands.require_outside_claude', lambda f: f)
def test_add_workspace_create_directory(mock_config_loader, tmp_path, capsys):
    """Test creating workspace directory if it doesn't exist."""
    from devflow.cli.commands.workspace_commands import add_workspace

    new_workspace = tmp_path / "nonexistent-workspace"

    with patch('devflow.cli.commands.workspace_commands.ConfigLoader', return_value=mock_config_loader):
        with patch('devflow.cli.commands.workspace_commands.Confirm.ask', return_value=True):
            with patch('devflow.utils.workspace_utils.ensure_workspace_skills_and_commands', return_value=(True, None)):
                add_workspace("new-ws", str(new_workspace), set_default=False)

    captured = capsys.readouterr()
    assert "Created directory" in captured.out
    assert new_workspace.exists()


@patch('devflow.cli.commands.workspace_commands.require_outside_claude', lambda f: f)
def test_add_workspace_cancel_directory_creation(mock_config_loader, tmp_path, capsys):
    """Test canceling directory creation."""
    from devflow.cli.commands.workspace_commands import add_workspace

    new_workspace = tmp_path / "cancelled-workspace"

    with patch('devflow.cli.commands.workspace_commands.ConfigLoader', return_value=mock_config_loader):
        with patch('devflow.cli.commands.workspace_commands.Confirm.ask', return_value=False):
            add_workspace("cancelled", str(new_workspace), set_default=False)

    captured = capsys.readouterr()
    assert "Cancelled" in captured.out
    assert not new_workspace.exists()


@patch('devflow.cli.commands.workspace_commands.require_outside_claude', lambda f: f)
def test_add_workspace_with_git_repo(mock_config_loader, tmp_path, capsys):
    """Test adding workspace that is a git repository."""
    from devflow.cli.commands.workspace_commands import add_workspace

    git_workspace = tmp_path / "git-workspace"
    git_workspace.mkdir()
    (git_workspace / ".git").mkdir()

    with patch('devflow.cli.commands.workspace_commands.ConfigLoader', return_value=mock_config_loader):
        with patch('devflow.git.utils.GitUtils.is_git_repository', return_value=True):
            with patch('devflow.utils.workspace_utils.ensure_workspace_skills_and_commands', return_value=(True, None)):
                add_workspace("git-ws", str(git_workspace), set_default=False)

    captured = capsys.readouterr()
    assert "Workspace is a git repository" in captured.out


@patch('devflow.cli.commands.workspace_commands.require_outside_claude', lambda f: f)
def test_add_workspace_contains_git_repos(mock_config_loader, tmp_path, capsys):
    """Test adding workspace that contains git repositories."""
    from devflow.cli.commands.workspace_commands import add_workspace

    workspace = tmp_path / "workspace-with-repos"
    workspace.mkdir()
    (workspace / "repo1").mkdir()
    (workspace / "repo1" / ".git").mkdir()

    with patch('devflow.cli.commands.workspace_commands.ConfigLoader', return_value=mock_config_loader):
        with patch('devflow.git.utils.GitUtils.is_git_repository', return_value=False):
            with patch('devflow.utils.workspace_utils.ensure_workspace_skills_and_commands', return_value=(True, None)):
                add_workspace("repos-ws", str(workspace), set_default=False)

    captured = capsys.readouterr()
    assert "Workspace contains git repositories" in captured.out


@patch('devflow.cli.commands.workspace_commands.require_outside_claude', lambda f: f)
def test_add_workspace_no_git_warning(mock_config_loader, tmp_path, capsys):
    """Test warning when workspace has no git repositories."""
    from devflow.cli.commands.workspace_commands import add_workspace

    empty_workspace = tmp_path / "empty-workspace"
    empty_workspace.mkdir()

    with patch('devflow.cli.commands.workspace_commands.ConfigLoader', return_value=mock_config_loader):
        with patch('devflow.git.utils.GitUtils.is_git_repository', return_value=False):
            with patch('devflow.utils.workspace_utils.ensure_workspace_skills_and_commands', return_value=(True, None)):
                add_workspace("empty-ws", str(empty_workspace), set_default=False)

    captured = capsys.readouterr()
    assert "does not appear to contain git repositories" in captured.out


@patch('devflow.cli.commands.workspace_commands.require_outside_claude', lambda f: f)
def test_add_workspace_set_as_default(mock_config_loader, tmp_path, capsys):
    """Test adding workspace and setting it as default."""
    from devflow.cli.commands.workspace_commands import add_workspace

    new_workspace = tmp_path / "default-workspace"
    new_workspace.mkdir()

    with patch('devflow.cli.commands.workspace_commands.ConfigLoader', return_value=mock_config_loader):
        with patch('devflow.utils.workspace_utils.ensure_workspace_skills_and_commands', return_value=(True, None)):
            add_workspace("default-ws", str(new_workspace), set_default=True)

    captured = capsys.readouterr()
    assert "Last used: Yes" in captured.out
    assert mock_config_loader.load_config.return_value.repos.last_used_workspace == "default-ws"


@patch('devflow.cli.commands.workspace_commands.require_outside_claude', lambda f: f)
def test_remove_workspace_success(mock_config_loader, capsys):
    """Test removing workspace successfully."""
    from devflow.cli.commands.workspace_commands import remove_workspace

    mock_session_manager = Mock()
    mock_session_manager.index.sessions = {}

    with patch('devflow.cli.commands.workspace_commands.ConfigLoader', return_value=mock_config_loader):
        with patch('devflow.session.manager.SessionManager', return_value=mock_session_manager):
            with patch('devflow.cli.commands.workspace_commands.Confirm.ask', return_value=True):
                remove_workspace("product-a")

    captured = capsys.readouterr()
    assert "Removed workspace: product-a" in captured.out
    assert mock_config_loader.save_config.called


@patch('devflow.cli.commands.workspace_commands.require_outside_claude', lambda f: f)
def test_remove_workspace_no_config(capsys):
    """Test removing workspace when no config exists."""
    from devflow.cli.commands.workspace_commands import remove_workspace

    mock_loader = Mock()
    mock_loader.load_config.return_value = None

    with patch('devflow.cli.commands.workspace_commands.ConfigLoader', return_value=mock_loader):
        remove_workspace("test")

    captured = capsys.readouterr()
    assert "No configuration found" in captured.out


@patch('devflow.cli.commands.workspace_commands.require_outside_claude', lambda f: f)
def test_remove_workspace_not_found(mock_config_loader, capsys):
    """Test removing non-existent workspace."""
    from devflow.cli.commands.workspace_commands import remove_workspace

    with patch('devflow.cli.commands.workspace_commands.ConfigLoader', return_value=mock_config_loader):
        remove_workspace("nonexistent")

    captured = capsys.readouterr()
    assert "Workspace not found: nonexistent" in captured.out


@patch('devflow.cli.commands.workspace_commands.require_outside_claude', lambda f: f)
def test_remove_workspace_cancel_confirmation(mock_config_loader, capsys):
    """Test canceling workspace removal."""
    from devflow.cli.commands.workspace_commands import remove_workspace

    with patch('devflow.cli.commands.workspace_commands.ConfigLoader', return_value=mock_config_loader):
        with patch('devflow.cli.commands.workspace_commands.Confirm.ask', return_value=False):
            remove_workspace("product-a")

    captured = capsys.readouterr()
    assert "Cancelled" in captured.out


@patch('devflow.cli.commands.workspace_commands.require_outside_claude', lambda f: f)
def test_remove_workspace_with_active_sessions(mock_config_loader, capsys):
    """Test removing workspace with active sessions."""
    from devflow.cli.commands.workspace_commands import remove_workspace
    from devflow.config.models import Session

    mock_session = Mock(spec=Session)
    mock_session.name = "test-session"
    mock_session.workspace_name = "product-a"

    mock_session_manager = Mock()
    mock_session_manager.index.sessions = {"test": mock_session}

    with patch('devflow.cli.commands.workspace_commands.ConfigLoader', return_value=mock_config_loader):
        with patch('devflow.session.manager.SessionManager', return_value=mock_session_manager):
            with patch('devflow.cli.commands.workspace_commands.Confirm.ask', side_effect=[True, True]):
                remove_workspace("product-a")

    captured = capsys.readouterr()
    assert "session(s) are using this workspace" in captured.out


@patch('devflow.cli.commands.workspace_commands.require_outside_claude', lambda f: f)
def test_remove_workspace_updates_default(mock_config_loader, capsys):
    """Test removing default workspace updates to new default."""
    from devflow.cli.commands.workspace_commands import remove_workspace

    mock_session_manager = Mock()
    mock_session_manager.index.sessions = {}

    with patch('devflow.cli.commands.workspace_commands.ConfigLoader', return_value=mock_config_loader):
        with patch('devflow.session.manager.SessionManager', return_value=mock_session_manager):
            with patch('devflow.cli.commands.workspace_commands.Confirm.ask', return_value=True):
                remove_workspace("primary")  # Remove default workspace

    captured = capsys.readouterr()
    assert "Set 'product-a' as new default" in captured.out


@patch('devflow.cli.commands.workspace_commands.require_outside_claude', lambda f: f)
def test_set_default_workspace_success(mock_config_loader, capsys):
    """Test setting workspace as default."""
    from devflow.cli.commands.workspace_commands import set_default_workspace

    with patch('devflow.cli.commands.workspace_commands.ConfigLoader', return_value=mock_config_loader):
        with patch('devflow.utils.workspace_utils.ensure_workspace_skills_and_commands', return_value=(True, None)):
            set_default_workspace("product-a")

    captured = capsys.readouterr()
    assert "Set 'product-a' as last used workspace" in captured.out
    assert mock_config_loader.load_config.return_value.repos.last_used_workspace == "product-a"


@patch('devflow.cli.commands.workspace_commands.require_outside_claude', lambda f: f)
def test_set_default_workspace_no_config(capsys):
    """Test setting default workspace when no config exists."""
    from devflow.cli.commands.workspace_commands import set_default_workspace

    mock_loader = Mock()
    mock_loader.load_config.return_value = None

    with patch('devflow.cli.commands.workspace_commands.ConfigLoader', return_value=mock_loader):
        set_default_workspace("test")

    captured = capsys.readouterr()
    assert "No configuration found" in captured.out


@patch('devflow.cli.commands.workspace_commands.require_outside_claude', lambda f: f)
def test_set_default_workspace_not_found(mock_config_loader, capsys):
    """Test setting non-existent workspace as default."""
    from devflow.cli.commands.workspace_commands import set_default_workspace

    with patch('devflow.cli.commands.workspace_commands.ConfigLoader', return_value=mock_config_loader):
        set_default_workspace("nonexistent")

    captured = capsys.readouterr()
    assert "Workspace not found: nonexistent" in captured.out


@patch('devflow.cli.commands.workspace_commands.require_outside_claude', lambda f: f)
def test_set_default_workspace_already_default(mock_config_loader, capsys):
    """Test setting already default workspace."""
    from devflow.cli.commands.workspace_commands import set_default_workspace

    with patch('devflow.cli.commands.workspace_commands.ConfigLoader', return_value=mock_config_loader):
        set_default_workspace("primary")  # Already default

    captured = capsys.readouterr()
    assert "is already the last used workspace" in captured.out


@patch('devflow.cli.commands.workspace_commands.require_outside_claude', lambda f: f)
def test_rename_workspace_success(mock_config_loader, capsys):
    """Test renaming workspace successfully."""
    from devflow.cli.commands.workspace_commands import rename_workspace

    mock_session_manager = Mock()
    mock_session_manager.index.sessions = {}
    mock_session_manager.save_session = Mock()

    with patch('devflow.cli.commands.workspace_commands.ConfigLoader', return_value=mock_config_loader):
        with patch('devflow.session.manager.SessionManager', return_value=mock_session_manager):
            rename_workspace("product-a", "product-b")

    captured = capsys.readouterr()
    assert "Renamed workspace: product-a → product-b" in captured.out
    assert mock_config_loader.save_config.called


@patch('devflow.cli.commands.workspace_commands.require_outside_claude', lambda f: f)
def test_rename_workspace_no_config(capsys):
    """Test renaming workspace when no config exists."""
    from devflow.cli.commands.workspace_commands import rename_workspace

    mock_loader = Mock()
    mock_loader.load_config.return_value = None

    with patch('devflow.cli.commands.workspace_commands.ConfigLoader', return_value=mock_loader):
        rename_workspace("old", "new")

    captured = capsys.readouterr()
    assert "No configuration found" in captured.out


@patch('devflow.cli.commands.workspace_commands.require_outside_claude', lambda f: f)
def test_rename_workspace_not_found(mock_config_loader, capsys):
    """Test renaming non-existent workspace."""
    from devflow.cli.commands.workspace_commands import rename_workspace

    with patch('devflow.cli.commands.workspace_commands.ConfigLoader', return_value=mock_config_loader):
        rename_workspace("nonexistent", "new-name")

    captured = capsys.readouterr()
    assert "Workspace not found: nonexistent" in captured.out


@patch('devflow.cli.commands.workspace_commands.require_outside_claude', lambda f: f)
def test_rename_workspace_same_name(mock_config_loader, capsys):
    """Test renaming workspace to same name."""
    from devflow.cli.commands.workspace_commands import rename_workspace

    with patch('devflow.cli.commands.workspace_commands.ConfigLoader', return_value=mock_config_loader):
        rename_workspace("primary", "primary")

    captured = capsys.readouterr()
    assert "New name is same as current name" in captured.out


@patch('devflow.cli.commands.workspace_commands.require_outside_claude', lambda f: f)
def test_rename_workspace_duplicate_name(mock_config_loader, capsys):
    """Test renaming workspace to existing name."""
    from devflow.cli.commands.workspace_commands import rename_workspace

    with patch('devflow.cli.commands.workspace_commands.ConfigLoader', return_value=mock_config_loader):
        rename_workspace("primary", "product-a")  # product-a already exists

    captured = capsys.readouterr()
    assert "Workspace already exists with name: product-a" in captured.out


@patch('devflow.cli.commands.workspace_commands.require_outside_claude', lambda f: f)
def test_rename_workspace_updates_sessions(mock_config_loader, capsys):
    """Test renaming workspace updates associated sessions."""
    from devflow.cli.commands.workspace_commands import rename_workspace
    from devflow.config.models import Session

    mock_session = Mock(spec=Session)
    mock_session.workspace_name = "product-a"

    mock_session_manager = Mock()
    mock_session_manager.index.sessions = {"test": mock_session}
    mock_session_manager.save_session = Mock()

    with patch('devflow.cli.commands.workspace_commands.ConfigLoader', return_value=mock_config_loader):
        with patch('devflow.session.manager.SessionManager', return_value=mock_session_manager):
            rename_workspace("product-a", "product-b")

    captured = capsys.readouterr()
    assert "Updated 1 session(s)" in captured.out
    assert mock_session.workspace_name == "product-b"
