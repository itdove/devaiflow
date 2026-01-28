"""Tests for DAF_AGENTS.md validation logic."""

import pytest
from pathlib import Path
from devflow.cli.commands.open_command import (
    _validate_context_files,
    _check_and_upgrade_daf_agents,
    _get_bundled_daf_agents_content
)
from devflow.config.loader import ConfigLoader
from devflow.config.models import Conversation, ConversationContext, Session


def _create_mock_session(repo_dir: str) -> Session:
    """Helper to create a mock session object for testing."""
    import uuid
    # Create a ConversationContext (active session) with required fields
    context = ConversationContext(
        ai_agent_session_id=str(uuid.uuid4()),
        project_path=repo_dir,  # Set project_path for _validate_context_files
        working_directory=repo_dir,
        temp_directory=None
    )
    # Create Conversation with active_session
    conversation = Conversation(active_session=context)
    # Create Session with required fields (name is required)
    # Manually assign conversations dict instead of using add_conversation()
    session = Session(
        name="test-session",
        session_type="standard",
        conversations={repo_dir: conversation},
        working_directory=repo_dir
    )
    return session


def test_validate_daf_agents_in_repo(tmp_path, temp_daf_home):
    """Test DAF_AGENTS.md found in repository directory."""
    # Create a temp repo with up-to-date DAF_AGENTS.md
    repo_dir = tmp_path / "test-repo"
    repo_dir.mkdir()

    # Use actual bundled content to avoid triggering upgrade
    bundled_content, _ = _get_bundled_daf_agents_content()
    (repo_dir / "DAF_AGENTS.md").write_text(bundled_content)

    config_loader = ConfigLoader()
    session = _create_mock_session(str(repo_dir))

    # Should find DAF_AGENTS.md in repo
    result = _validate_context_files(session, config_loader)
    assert result is True


def test_validate_daf_agents_in_workspace_fallback(tmp_path, temp_daf_home):
    """Test DAF_AGENTS.md found in workspace directory as fallback."""
    from devflow.config.loader import ConfigLoader

    # Create workspace with up-to-date DAF_AGENTS.md
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    # Use actual bundled content to avoid triggering upgrade
    bundled_content, _ = _get_bundled_daf_agents_content()
    (workspace / "DAF_AGENTS.md").write_text(bundled_content)

    # Create repo WITHOUT DAF_AGENTS.md
    repo_dir = workspace / "test-repo"
    repo_dir.mkdir()

    # Create config with workspace path
    config_loader = ConfigLoader()
    config = config_loader.create_default_config()
    from devflow.config.models import WorkspaceDefinition
    config.repos.workspaces = [
        WorkspaceDefinition(name="default", path=str(workspace))
    ]
    config.repos.last_used_workspace = "default"
    config_loader.save_config(config)

    # Should find DAF_AGENTS.md in workspace (fallback)
    session = _create_mock_session(str(repo_dir))

    

    result = _validate_context_files(session, config_loader)
    assert result is True


def test_validate_daf_agents_not_found_user_declines(tmp_path, temp_daf_home, monkeypatch):
    """Test DAF_AGENTS.md not found and user declines installation."""
    from devflow.config.loader import ConfigLoader
    from unittest.mock import MagicMock

    # Mock Confirm.ask to return False (user declines)
    mock_confirm = MagicMock(return_value=False)
    monkeypatch.setattr("rich.prompt.Confirm.ask", mock_confirm)

    # Create workspace WITHOUT DAF_AGENTS.md
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    # Create repo WITHOUT DAF_AGENTS.md
    repo_dir = workspace / "test-repo"
    repo_dir.mkdir()

    # Create config with workspace path
    config_loader = ConfigLoader()
    config = config_loader.create_default_config()
    from devflow.config.models import WorkspaceDefinition
    config.repos.workspaces = [
        WorkspaceDefinition(name="default", path=str(workspace))
    ]
    config.repos.last_used_workspace = "default"
    config_loader.save_config(config)

    # Should NOT find DAF_AGENTS.md and user declined installation
    session = _create_mock_session(str(repo_dir))

    

    result = _validate_context_files(session, config_loader)
    assert result is False

    # Verify Confirm was called
    assert mock_confirm.called


def test_validate_daf_agents_auto_install_success(tmp_path, temp_daf_home, monkeypatch):
    """Test successful auto-installation of bundled DAF_AGENTS.md."""
    from devflow.config.loader import ConfigLoader
    from unittest.mock import MagicMock

    # Mock Confirm.ask to return True (user accepts installation)
    mock_confirm = MagicMock(return_value=True)
    monkeypatch.setattr("rich.prompt.Confirm.ask", mock_confirm)

    # Create workspace WITHOUT DAF_AGENTS.md
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    # Create repo WITHOUT DAF_AGENTS.md
    repo_dir = workspace / "test-repo"
    repo_dir.mkdir()

    # Create config with workspace path
    config_loader = ConfigLoader()
    config = config_loader.create_default_config()
    from devflow.config.models import WorkspaceDefinition
    config.repos.workspaces = [
        WorkspaceDefinition(name="default", path=str(workspace))
    ]
    config.repos.last_used_workspace = "default"
    config_loader.save_config(config)

    # Mock _install_bundled_cs_agents to simulate successful installation
    from devflow.cli.commands import open_command
    original_install = open_command._install_bundled_cs_agents
    def mock_install(destination):
        # Write a test DAF_AGENTS.md file
        destination.write_text("# DAF Tool Usage Guide (bundled)")
        return True, []  # Updated to return tuple
    monkeypatch.setattr("devflow.cli.commands.open_command._install_bundled_cs_agents", mock_install)

    # Should auto-install DAF_AGENTS.md and succeed
    session = _create_mock_session(str(repo_dir))

    

    result = _validate_context_files(session, config_loader)
    assert result is True

    # Verify DAF_AGENTS.md was created
    assert (repo_dir / "DAF_AGENTS.md").exists()

    # Verify Confirm was called
    assert mock_confirm.called


def test_validate_daf_agents_prefers_repo_over_workspace(tmp_path, temp_daf_home):
    """Test that repo DAF_AGENTS.md is preferred over workspace version."""
    from devflow.config.loader import ConfigLoader

    # Create workspace with DAF_AGENTS.md
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    # Use actual bundled content to avoid triggering upgrade
    bundled_content, _ = _get_bundled_daf_agents_content()
    (workspace / "DAF_AGENTS.md").write_text(bundled_content)

    # Create repo WITH DAF_AGENTS.md (also up-to-date)
    repo_dir = workspace / "test-repo"
    repo_dir.mkdir()
    (repo_dir / "DAF_AGENTS.md").write_text(bundled_content)

    # Create config with workspace path
    config_loader = ConfigLoader()
    config = config_loader.create_default_config()
    from devflow.config.models import WorkspaceDefinition
    config.repos.workspaces = [
        WorkspaceDefinition(name="default", path=str(workspace))
    ]
    config.repos.last_used_workspace = "default"
    config_loader.save_config(config)

    # Should find DAF_AGENTS.md (and prefer repo over workspace)
    session = _create_mock_session(str(repo_dir))

    

    result = _validate_context_files(session, config_loader)
    assert result is True


def test_validate_daf_agents_auto_install_failure_with_diagnostics(tmp_path, temp_daf_home, monkeypatch, capsys):
    """Test auto-installation failure displays detailed diagnostics."""
    from devflow.config.loader import ConfigLoader
    from unittest.mock import MagicMock

    # Mock Confirm.ask to return True (user accepts installation)
    mock_confirm = MagicMock(return_value=True)
    monkeypatch.setattr("rich.prompt.Confirm.ask", mock_confirm)

    # Create workspace WITHOUT DAF_AGENTS.md
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    # Create repo WITHOUT DAF_AGENTS.md
    repo_dir = workspace / "test-repo"
    repo_dir.mkdir()

    # Create config with workspace path
    config_loader = ConfigLoader()
    config = config_loader.create_default_config()
    from devflow.config.models import WorkspaceDefinition
    config.repos.workspaces = [
        WorkspaceDefinition(name="default", path=str(workspace))
    ]
    config.repos.last_used_workspace = "default"
    config_loader.save_config(config)

    # Mock _install_bundled_cs_agents to simulate failure with diagnostics
    from devflow.cli.commands import open_command
    def mock_install(destination):
        # Return failure with diagnostic messages
        diagnostics = [
            "  Method 1 (importlib.resources): FileNotFoundError - DAF_AGENTS.md not found",
            "    Searched path: /path/to/package/DAF_AGENTS.md",
            "  Method 2 (relative path): Searched: /path/to/devflow/cli/commands/../../../../DAF_AGENTS.md",
            "  Method 2 (relative path): File does not exist"
        ]
        return False, diagnostics
    monkeypatch.setattr("devflow.cli.commands.open_command._install_bundled_cs_agents", mock_install)

    # Should fail to install and return False
    session = _create_mock_session(str(repo_dir))

    

    result = _validate_context_files(session, config_loader)
    assert result is False

    # Verify DAF_AGENTS.md was NOT created
    assert not (repo_dir / "DAF_AGENTS.md").exists()


def test_install_bundled_cs_agents_from_relative_path(tmp_path):
    """Test _install_bundled_cs_agents successfully installs from relative path."""
    from devflow.cli.commands.open_command import _install_bundled_cs_agents
    from pathlib import Path

    # Create a source DAF_AGENTS.md at the expected relative path
    # Path(__file__).parent.parent.parent.parent / "DAF_AGENTS.md"
    # For this test, we'll use the actual DAF_AGENTS.md file from the repo
    source = Path(__file__).parent.parent / "DAF_AGENTS.md"

    # Skip test if source doesn't exist (shouldn't happen in development)
    if not source.exists():
        pytest.skip("DAF_AGENTS.md not found in repository root")

    destination = tmp_path / "DAF_AGENTS.md"

    # Call the function
    success, diagnostics = _install_bundled_cs_agents(destination)

    # Should succeed (in development mode with proper structure)
    assert success is True
    assert diagnostics == []
    assert destination.exists()
    assert destination.read_text().startswith("# DevAIFlow Agent Workflow Guide")


def test_install_bundled_cs_agents_returns_diagnostics_on_failure(tmp_path, monkeypatch):
    """Test _install_bundled_cs_agents returns detailed diagnostics on failure."""
    from devflow.cli.commands.open_command import _install_bundled_cs_agents
    import importlib.resources
    from pathlib import Path

    # Mock importlib.resources to raise FileNotFoundError
    def mock_files(package):
        # Simulate that DAF_AGENTS.md is not found
        class MockResource:
            def __truediv__(self, other):
                if other == "DAF_AGENTS.md":
                    # Simulate a path that doesn't exist
                    class NonExistentPath:
                        def __str__(self):
                            return "/mock/path/DAF_AGENTS.md"
                        def open(self, mode):
                            raise FileNotFoundError("DAF_AGENTS.md not found")
                    return NonExistentPath()
                return self
        return MockResource()

    monkeypatch.setattr("importlib.resources.files", mock_files)

    # Mock Path.__file__ to point to a location without DAF_AGENTS.md
    # This prevents the relative path method from succeeding
    fake_file_location = tmp_path / "fake_package" / "devflow" / "cli" / "commands" / "open_command.py"
    fake_file_location.parent.mkdir(parents=True)
    fake_file_location.touch()

    # Patch __file__ in the function's module scope
    import devflow.cli.commands.open_command as open_cmd_module
    original_file = open_cmd_module.__file__
    monkeypatch.setattr(open_cmd_module, "__file__", str(fake_file_location))

    destination = tmp_path / "test_destination" / "DAF_AGENTS.md"
    destination.parent.mkdir(parents=True, exist_ok=True)

    # Call the function
    success, diagnostics = _install_bundled_cs_agents(destination)

    # Should fail
    assert success is False

    # Should have diagnostic messages from both methods
    assert len(diagnostics) > 0
    # Should have messages from Method 1 (importlib.resources)
    assert any("Method 1" in diag for diag in diagnostics)
    # Should have messages from Method 2 (relative path)
    assert any("Method 2" in diag for diag in diagnostics)


def test_get_bundled_daf_agents_content_success():
    """Test _get_bundled_daf_agents_content successfully reads bundled file."""
    content, diagnostics = _get_bundled_daf_agents_content()

    # Should successfully read content
    assert content is not None
    assert isinstance(content, str)
    assert len(content) > 0
    assert diagnostics == []

    # Verify it looks like DAF_AGENTS.md content
    assert "DevAIFlow Agent Workflow Guide" in content or "daf" in content.lower()


def test_check_and_upgrade_daf_agents_up_to_date(tmp_path, temp_daf_home, monkeypatch):
    """Test that up-to-date DAF_AGENTS.md does not trigger upgrade prompt."""
    # Get the actual bundled content
    bundled_content, _ = _get_bundled_daf_agents_content()
    assert bundled_content is not None

    # Create an installed file with same content
    installed_file = tmp_path / "DAF_AGENTS.md"
    installed_file.write_text(bundled_content)

    # Should return True without prompting
    result = _check_and_upgrade_daf_agents(installed_file, "repository")
    assert result is True


def test_check_and_upgrade_daf_agents_outdated_user_accepts(tmp_path, temp_daf_home, monkeypatch):
    """Test upgrade when DAF_AGENTS.md is outdated and user accepts."""
    from unittest.mock import MagicMock

    # Mock Confirm.ask to return True (user accepts upgrade)
    mock_confirm = MagicMock(return_value=True)
    monkeypatch.setattr("rich.prompt.Confirm.ask", mock_confirm)

    # Create an installed file with outdated content
    installed_file = tmp_path / "DAF_AGENTS.md"
    installed_file.write_text("# Old Version\nThis is outdated content")

    # Get bundled content to verify upgrade
    bundled_content, _ = _get_bundled_daf_agents_content()
    assert bundled_content is not None

    # Should prompt and upgrade
    result = _check_and_upgrade_daf_agents(installed_file, "repository")
    assert result is True

    # Verify file was upgraded
    new_content = installed_file.read_text()
    assert new_content == bundled_content
    assert "Old Version" not in new_content

    # Verify Confirm was called
    assert mock_confirm.called


def test_check_and_upgrade_daf_agents_outdated_user_declines(tmp_path, temp_daf_home, monkeypatch):
    """Test that session continues when user declines upgrade."""
    from unittest.mock import MagicMock

    # Mock Confirm.ask to return False (user declines upgrade)
    mock_confirm = MagicMock(return_value=False)
    monkeypatch.setattr("rich.prompt.Confirm.ask", mock_confirm)

    # Create an installed file with outdated content
    installed_file = tmp_path / "DAF_AGENTS.md"
    old_content = "# Old Version\nThis is outdated content"
    installed_file.write_text(old_content)

    # Should return True (don't block session opening)
    result = _check_and_upgrade_daf_agents(installed_file, "repository")
    assert result is True

    # Verify file was NOT upgraded
    assert installed_file.read_text() == old_content

    # Verify Confirm was called
    assert mock_confirm.called


def test_check_and_upgrade_daf_agents_mock_mode(tmp_path, temp_daf_home, monkeypatch):
    """Test that mock mode auto-upgrades without prompting."""
    # Set mock mode
    monkeypatch.setenv("DAF_MOCK_MODE", "1")

    # Create an installed file with outdated content
    installed_file = tmp_path / "DAF_AGENTS.md"
    installed_file.write_text("# Old Version\nThis is outdated content")

    # Get bundled content to verify upgrade
    bundled_content, _ = _get_bundled_daf_agents_content()
    assert bundled_content is not None

    # Should auto-upgrade without prompting
    result = _check_and_upgrade_daf_agents(installed_file, "repository")
    assert result is True

    # Verify file was upgraded
    new_content = installed_file.read_text()
    assert new_content == bundled_content
    assert "Old Version" not in new_content


def test_check_and_upgrade_daf_agents_cannot_read_bundled(tmp_path, temp_daf_home, monkeypatch):
    """Test that upgrade check continues if bundled file cannot be read."""
    # Mock _get_bundled_daf_agents_content to return None
    def mock_get_bundled():
        return None, ["Error reading bundled file"]

    monkeypatch.setattr("devflow.cli.commands.open_command._get_bundled_daf_agents_content", mock_get_bundled)

    # Create an installed file
    installed_file = tmp_path / "DAF_AGENTS.md"
    installed_file.write_text("# Some content")

    # Should return True (don't block session opening)
    result = _check_and_upgrade_daf_agents(installed_file, "repository")
    assert result is True


def test_check_and_upgrade_daf_agents_cannot_read_installed(tmp_path, temp_daf_home, monkeypatch):
    """Test that upgrade check continues if installed file cannot be read."""
    # Create a file that will fail to read (simulated via monkeypatch)
    installed_file = tmp_path / "DAF_AGENTS.md"
    installed_file.write_text("# Some content")

    # Mock read_text to raise an exception
    original_read_text = Path.read_text
    def mock_read_text(self, *args, **kwargs):
        if self == installed_file:
            raise PermissionError("Cannot read file")
        return original_read_text(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", mock_read_text)

    # Should return True (don't block session opening)
    result = _check_and_upgrade_daf_agents(installed_file, "repository")
    assert result is True


def test_validate_context_files_triggers_upgrade_check_repo(tmp_path, temp_daf_home, monkeypatch):
    """Test that _validate_context_files triggers upgrade check for repo DAF_AGENTS.md."""
    from unittest.mock import MagicMock
    from devflow.config.models import Conversation
    from devflow.config.models import Session

    # Mock Confirm.ask to return True (user accepts upgrade)
    mock_confirm = MagicMock(return_value=True)
    monkeypatch.setattr("rich.prompt.Confirm.ask", mock_confirm)

    # Create a temp repo with outdated DAF_AGENTS.md
    repo_dir = tmp_path / "test-repo"
    repo_dir.mkdir()
    (repo_dir / "DAF_AGENTS.md").write_text("# Old Version")

    config_loader = ConfigLoader()

    # Create a mock session object
    import uuid
    context = ConversationContext(ai_agent_session_id=str(uuid.uuid4()), project_path=str(repo_dir), working_directory=str(repo_dir), temp_directory=None)
    conversation = Conversation(active_session=context)
    session = Session(name="test-session", session_type="standard", conversations={str(repo_dir): conversation}, working_directory=str(repo_dir))

    # Should find, check, and upgrade DAF_AGENTS.md
    result = _validate_context_files(session, config_loader)
    assert result is True

    # Verify upgrade was performed
    bundled_content, _ = _get_bundled_daf_agents_content()
    new_content = (repo_dir / "DAF_AGENTS.md").read_text()
    assert new_content == bundled_content


def test_validate_context_files_triggers_upgrade_check_workspace(tmp_path, temp_daf_home, monkeypatch):
    """Test that _validate_context_files triggers upgrade check for workspace DAF_AGENTS.md."""
    from unittest.mock import MagicMock
    from devflow.config.models import Conversation
    from devflow.config.models import Session

    # Mock Confirm.ask to return True (user accepts upgrade)
    mock_confirm = MagicMock(return_value=True)
    monkeypatch.setattr("rich.prompt.Confirm.ask", mock_confirm)

    # Create workspace with outdated DAF_AGENTS.md
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "DAF_AGENTS.md").write_text("# Old Workspace Version")

    # Create repo WITHOUT DAF_AGENTS.md
    repo_dir = workspace / "test-repo"
    repo_dir.mkdir()

    # Create config with workspace path
    config_loader = ConfigLoader()
    config = config_loader.create_default_config()
    from devflow.config.models import WorkspaceDefinition
    config.repos.workspaces = [
        WorkspaceDefinition(name="default", path=str(workspace))
    ]
    config.repos.last_used_workspace = "default"
    config_loader.save_config(config)

    # Create a mock session object
    import uuid
    context = ConversationContext(ai_agent_session_id=str(uuid.uuid4()), project_path=str(repo_dir), working_directory=str(repo_dir), temp_directory=None)
    conversation = Conversation(active_session=context)
    session = Session(name="test-session", session_type="standard", conversations={str(repo_dir): conversation}, working_directory=str(repo_dir))

    # Should find in workspace and upgrade
    result = _validate_context_files(session, config_loader)
    assert result is True

    # Verify upgrade was performed on workspace file
    bundled_content, _ = _get_bundled_daf_agents_content()
    new_content = (workspace / "DAF_AGENTS.md").read_text()
    assert new_content == bundled_content
