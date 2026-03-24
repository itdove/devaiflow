"""Tests for DAF_AGENTS.md validation logic."""

import pytest
from pathlib import Path
from devflow.utils.daf_agents_validation import (
    validate_daf_agents_md,
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
        project_path=repo_dir,  # Set project_path for validate_daf_agents_md
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


def test_validate_daf_agents_in_repo(tmp_path, temp_daf_home, monkeypatch):
    """Test DAF_AGENTS.md found in repository directory triggers deletion prompt."""
    from unittest.mock import MagicMock

    # Mock Confirm.ask to return True (user accepts deletion)
    mock_confirm = MagicMock(return_value=True)
    monkeypatch.setattr("rich.prompt.Confirm.ask", mock_confirm)

    # Create a temp repo with old DAF_AGENTS.md
    repo_dir = tmp_path / "test-repo"
    repo_dir.mkdir()
    (repo_dir / "DAF_AGENTS.md").write_text("# Old DAF_AGENTS.md")

    config_loader = ConfigLoader()
    session = _create_mock_session(str(repo_dir))

    # Should find DAF_AGENTS.md in repo and offer to delete
    result = validate_daf_agents_md(session, config_loader)
    assert result is True

    # Verify file was deleted
    assert not (repo_dir / "DAF_AGENTS.md").exists()


def test_validate_daf_agents_in_workspace_fallback(tmp_path, temp_daf_home, monkeypatch):
    """Test DAF_AGENTS.md found in workspace directory triggers deletion prompt."""
    from devflow.config.loader import ConfigLoader
    from unittest.mock import MagicMock

    # Mock Confirm.ask to return True (user accepts deletion)
    mock_confirm = MagicMock(return_value=True)
    monkeypatch.setattr("rich.prompt.Confirm.ask", mock_confirm)

    # Create workspace with old DAF_AGENTS.md
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "DAF_AGENTS.md").write_text("# Old workspace DAF_AGENTS.md")

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

    # Should find DAF_AGENTS.md in workspace and offer to delete
    session = _create_mock_session(str(repo_dir))

    result = validate_daf_agents_md(session, config_loader)
    assert result is True

    # Verify file was deleted
    assert not (workspace / "DAF_AGENTS.md").exists()


def test_validate_daf_agents_not_found_returns_true(tmp_path, temp_daf_home):
    """Test DAF_AGENTS.md not found - returns True (workflow is in daf-workflow skill)."""
    from devflow.config.loader import ConfigLoader

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

    # DAF_AGENTS.md not required - workflow is in daf-workflow skill
    session = _create_mock_session(str(repo_dir))

    result = validate_daf_agents_md(session, config_loader)
    assert result is True  # Should succeed without DAF_AGENTS.md


def test_validate_daf_agents_not_found_succeeds(tmp_path, temp_daf_home):
    """Test DAF_AGENTS.md not found succeeds (workflow in daf-workflow skill)."""
    from devflow.config.loader import ConfigLoader

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

    # Should succeed without DAF_AGENTS.md (workflow is in skill)
    session = _create_mock_session(str(repo_dir))

    result = validate_daf_agents_md(session, config_loader)
    assert result is True


@pytest.mark.skip(reason="DAF_AGENTS.md removed - replaced by daf-workflow skill")
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

    

    result = validate_daf_agents_md(session, config_loader)
    assert result is True


@pytest.mark.skip(reason="DAF_AGENTS.md removed - replaced by daf-workflow skill")
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
    def mock_install(destination):
        # Return failure with diagnostic messages
        diagnostics = [
            "  Method 1 (importlib.resources): FileNotFoundError - DAF_AGENTS.md not found",
            "    Searched path: /path/to/package/DAF_AGENTS.md",
            "  Method 2 (relative path): Searched: /path/to/devflow/utils/../../DAF_AGENTS.md",
            "  Method 2 (relative path): File does not exist"
        ]
        return False, diagnostics
    monkeypatch.setattr("devflow.utils.daf_agents_validation._install_bundled_cs_agents", mock_install)

    # Should fail to install and return False
    session = _create_mock_session(str(repo_dir))

    

    result = validate_daf_agents_md(session, config_loader)
    assert result is False

    # Verify DAF_AGENTS.md was NOT created
    assert not (repo_dir / "DAF_AGENTS.md").exists()


def test_install_bundled_cs_agents_returns_false(tmp_path):
    """Test _install_bundled_cs_agents returns False (bundled file removed)."""
    from devflow.utils.daf_agents_validation import _install_bundled_cs_agents

    destination = tmp_path / "DAF_AGENTS.md"

    # Call the function
    success, diagnostics = _install_bundled_cs_agents(destination)

    # Should fail since bundled file no longer exists
    assert success is False
    # Should have diagnostics explaining why
    assert len(diagnostics) > 0
    # Destination should not exist
    assert not destination.exists()


def test_install_bundled_cs_agents_returns_diagnostics_on_failure(tmp_path, monkeypatch):
    """Test _install_bundled_cs_agents returns detailed diagnostics on failure."""
    from devflow.utils.daf_agents_validation import _install_bundled_cs_agents
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
    fake_file_location = tmp_path / "fake_package" / "devflow" / "utils" / "daf_agents_validation.py"
    fake_file_location.parent.mkdir(parents=True)
    fake_file_location.touch()

    # Patch __file__ in the function's module scope
    import devflow.utils.daf_agents_validation as validation_module
    original_file = validation_module.__file__
    monkeypatch.setattr(validation_module, "__file__", str(fake_file_location))

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


def test_get_bundled_daf_agents_content_returns_none():
    """Test _get_bundled_daf_agents_content returns None (DAF_AGENTS.md removed)."""
    content, diagnostics = _get_bundled_daf_agents_content()

    # Should return None since bundled file no longer exists
    assert content is None
    # Should have diagnostics explaining file not found
    assert len(diagnostics) > 0


def test_check_and_upgrade_daf_agents_offers_deletion(tmp_path, temp_daf_home, monkeypatch):
    """Test that existing DAF_AGENTS.md triggers deletion prompt (bundled file removed)."""
    from unittest.mock import MagicMock

    # Mock Confirm.ask to return True (user accepts deletion)
    mock_confirm = MagicMock(return_value=True)
    monkeypatch.setattr("rich.prompt.Confirm.ask", mock_confirm)

    # Create an installed file (old DAF_AGENTS.md)
    installed_file = tmp_path / "DAF_AGENTS.md"
    installed_file.write_text("# Old DAF_AGENTS.md")

    # Should offer deletion since bundled file no longer exists
    result = _check_and_upgrade_daf_agents(installed_file, "repository")
    assert result is True

    # Verify file was deleted
    assert not installed_file.exists()

    # Verify Confirm was called
    assert mock_confirm.called


@pytest.mark.skip(reason="DAF_AGENTS.md removed - replaced by daf-workflow skill")
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


@pytest.mark.skip(reason="DAF_AGENTS.md removed - replaced by daf-workflow skill")
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


@pytest.mark.skip(reason="DAF_AGENTS.md removed - replaced by daf-workflow skill")
def test_check_and_upgrade_daf_agents_cannot_read_bundled(tmp_path, temp_daf_home, monkeypatch):
    """Test that upgrade check continues if bundled file cannot be read."""
    # Mock _get_bundled_daf_agents_content to return None
    def mock_get_bundled():
        return None, ["Error reading bundled file"]

    monkeypatch.setattr("devflow.utils.daf_agents_validation._get_bundled_daf_agents_content", mock_get_bundled)

    # Create an installed file
    installed_file = tmp_path / "DAF_AGENTS.md"
    installed_file.write_text("# Some content")

    # Should return True (don't block session opening)
    result = _check_and_upgrade_daf_agents(installed_file, "repository")
    assert result is True


@pytest.mark.skip(reason="DAF_AGENTS.md removed - replaced by daf-workflow skill")
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


@pytest.mark.skip(reason="DAF_AGENTS.md removed - replaced by daf-workflow skill")
def testvalidate_daf_agents_md_triggers_upgrade_check_repo(tmp_path, temp_daf_home, monkeypatch):
    """Test that validate_daf_agents_md triggers upgrade check for repo DAF_AGENTS.md."""
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
    result = validate_daf_agents_md(session, config_loader)
    assert result is True

    # Verify upgrade was performed
    bundled_content, _ = _get_bundled_daf_agents_content()
    new_content = (repo_dir / "DAF_AGENTS.md").read_text()
    assert new_content == bundled_content


@pytest.mark.skip(reason="DAF_AGENTS.md removed - replaced by daf-workflow skill")
def testvalidate_daf_agents_md_triggers_upgrade_check_workspace(tmp_path, temp_daf_home, monkeypatch):
    """Test that validate_daf_agents_md triggers upgrade check for workspace DAF_AGENTS.md."""
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
    result = validate_daf_agents_md(session, config_loader)
    assert result is True

    # Verify upgrade was performed on workspace file
    bundled_content, _ = _get_bundled_daf_agents_content()
    new_content = (workspace / "DAF_AGENTS.md").read_text()
    assert new_content == bundled_content


@pytest.mark.skip(reason="DAF_AGENTS.md removed - replaced by daf-workflow skill")
def test_validate_daf_agents_multi_project_session(tmp_path, temp_daf_home):
    """Test DAF_AGENTS.md validation for multi-project sessions."""
    from devflow.config.models import Conversation, ProjectInfo
    from devflow.config.models import Session
    import uuid

    # Create workspace with up-to-date DAF_AGENTS.md
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    # Use actual bundled content to avoid triggering upgrade
    bundled_content, _ = _get_bundled_daf_agents_content()
    (workspace / "DAF_AGENTS.md").write_text(bundled_content)

    # Create multiple project directories (no DAF_AGENTS.md in individual projects)
    project1 = workspace / "backend-api"
    project2 = workspace / "frontend-app"
    project1.mkdir()
    project2.mkdir()

    # Create a multi-project conversation context
    session_id = str(uuid.uuid4())
    projects_dict = {
        "backend-api": ProjectInfo(
            project_path=str(project1),
            relative_path="backend-api",
            branch="feature-branch",
            base_branch="main",
            repo_name="backend-api"
        ),
        "frontend-app": ProjectInfo(
            project_path=str(project2),
            relative_path="frontend-app",
            branch="feature-branch",
            base_branch="main",
            repo_name="frontend-app"
        )
    }
    context = ConversationContext(
        ai_agent_session_id=session_id,
        is_multi_project=True,
        projects=projects_dict,
        workspace_path=str(workspace)
    )

    # Create session with multi-project conversation
    conversation = Conversation(active_session=context)
    working_dir_key = f"multiproject-{session_id[:8]}"
    session = Session(
        name="test-multi-project-session",
        session_type="development",
        conversations={working_dir_key: conversation},
        working_directory=working_dir_key
    )

    config_loader = ConfigLoader()

    # Should find DAF_AGENTS.md in workspace
    result = validate_daf_agents_md(session, config_loader)
    assert result is True


@pytest.mark.skip(reason="DAF_AGENTS.md removed - replaced by daf-workflow skill")
@pytest.mark.skip(reason="DAF_AGENTS.md removed - replaced by daf-workflow skill")
def test_validate_daf_agents_multi_project_session_not_found(tmp_path, temp_daf_home, monkeypatch):
    """Test DAF_AGENTS.md validation for multi-project sessions when not found."""
    from devflow.config.models import Conversation, ProjectInfo
    from devflow.config.models import Session
    from unittest.mock import MagicMock
    from devflow.utils.paths import get_cs_home
    import uuid

    # Mock Confirm.ask to return True (user accepts installation)
    mock_confirm = MagicMock(return_value=True)
    monkeypatch.setattr("rich.prompt.Confirm.ask", mock_confirm)

    # Create workspace WITHOUT DAF_AGENTS.md
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    # Create multiple project directories
    project1 = workspace / "backend-api"
    project2 = workspace / "frontend-app"
    project1.mkdir()
    project2.mkdir()

    # Create a multi-project conversation context
    session_id = str(uuid.uuid4())
    projects_dict = {
        "backend-api": ProjectInfo(
            project_path=str(project1),
            relative_path="backend-api",
            branch="feature-branch",
            base_branch="main",
            repo_name="backend-api"
        ),
        "frontend-app": ProjectInfo(
            project_path=str(project2),
            relative_path="frontend-app",
            branch="feature-branch",
            base_branch="main",
            repo_name="frontend-app"
        )
    }
    context = ConversationContext(
        ai_agent_session_id=session_id,
        is_multi_project=True,
        projects=projects_dict,
        workspace_path=str(workspace)
    )

    # Create session with multi-project conversation
    conversation = Conversation(active_session=context)
    working_dir_key = f"multiproject-{session_id[:8]}"
    session = Session(
        name="test-multi-project-session",
        session_type="development",
        conversations={working_dir_key: conversation},
        working_directory=working_dir_key
    )

    config_loader = ConfigLoader()

    # Should offer to install DAF_AGENTS.md to DEVAIFLOW_HOME (new behavior)
    result = validate_daf_agents_md(session, config_loader)
    assert result is True

    # Verify DAF_AGENTS.md was created in DEVAIFLOW_HOME (new behavior)
    cs_home = get_cs_home()
    assert (cs_home / "DAF_AGENTS.md").exists()

    # Verify Confirm was called
    assert mock_confirm.called


@pytest.mark.skip(reason="DAF_AGENTS.md removed - replaced by daf-workflow skill")
@pytest.mark.skip(reason="DAF_AGENTS.md removed - replaced by daf-workflow skill")
def test_validate_daf_agents_multi_project_session_user_declines(tmp_path, temp_daf_home, monkeypatch):
    """Test multi-project session validation when user declines installation."""
    from devflow.config.models import Conversation, ProjectInfo
    from devflow.config.models import Session
    from unittest.mock import MagicMock
    import uuid

    # Mock Confirm.ask to return False (user declines installation)
    mock_confirm = MagicMock(return_value=False)
    monkeypatch.setattr("rich.prompt.Confirm.ask", mock_confirm)

    # Create workspace WITHOUT DAF_AGENTS.md
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    # Create multiple project directories
    project1 = workspace / "backend-api"
    project2 = workspace / "frontend-app"
    project1.mkdir()
    project2.mkdir()

    # Create a multi-project conversation context
    session_id = str(uuid.uuid4())
    projects_dict = {
        "backend-api": ProjectInfo(
            project_path=str(project1),
            relative_path="backend-api",
            branch="feature-branch",
            base_branch="main",
            repo_name="backend-api"
        ),
        "frontend-app": ProjectInfo(
            project_path=str(project2),
            relative_path="frontend-app",
            branch="feature-branch",
            base_branch="main",
            repo_name="frontend-app"
        )
    }
    context = ConversationContext(
        ai_agent_session_id=session_id,
        is_multi_project=True,
        projects=projects_dict,
        workspace_path=str(workspace)
    )

    # Create session with multi-project conversation
    conversation = Conversation(active_session=context)
    working_dir_key = f"multiproject-{session_id[:8]}"
    session = Session(
        name="test-multi-project-session",
        session_type="development",
        conversations={working_dir_key: conversation},
        working_directory=working_dir_key
    )

    config_loader = ConfigLoader()

    # Should return False when user declines
    result = validate_daf_agents_md(session, config_loader)
    assert result is False

    # Verify DAF_AGENTS.md was NOT created
    assert not (workspace / "DAF_AGENTS.md").exists()

    # Verify Confirm was called
    assert mock_confirm.called


@pytest.mark.skip(reason="DAF_AGENTS.md removed - replaced by daf-workflow skill")
def test_validate_daf_agents_devaiflow_home_priority_over_repo(tmp_path, temp_daf_home):
    """Test that DEVAIFLOW_HOME is checked before repository."""
    from devflow.config.loader import ConfigLoader
    from devflow.utils.paths import get_cs_home

    # Create DEVAIFLOW_HOME with up-to-date DAF_AGENTS.md
    cs_home = get_cs_home()
    bundled_content, _ = _get_bundled_daf_agents_content()
    (cs_home / "DAF_AGENTS.md").write_text(bundled_content)

    # Create repo with DIFFERENT (older) DAF_AGENTS.md
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    repo_dir = workspace / "test-repo"
    repo_dir.mkdir()
    (repo_dir / "DAF_AGENTS.md").write_text("# Old Repository Version")

    # Create config
    config_loader = ConfigLoader()
    config = config_loader.create_default_config()
    from devflow.config.models import WorkspaceDefinition
    config.repos.workspaces = [
        WorkspaceDefinition(name="default", path=str(workspace))
    ]
    config.repos.last_used_workspace = "default"
    config_loader.save_config(config)

    session = _create_mock_session(str(repo_dir))

    # Should find DEVAIFLOW_HOME version (not repository version)
    result = validate_daf_agents_md(session, config_loader)
    assert result is True

    # Repository file should still have old content (wasn't used)
    assert (repo_dir / "DAF_AGENTS.md").read_text() == "# Old Repository Version"


@pytest.mark.skip(reason="DAF_AGENTS.md removed - replaced by daf-workflow skill")
def test_validate_daf_agents_devaiflow_home_priority_over_workspace(tmp_path, temp_daf_home):
    """Test that DEVAIFLOW_HOME is checked before workspace."""
    from devflow.config.loader import ConfigLoader
    from devflow.utils.paths import get_cs_home

    # Create DEVAIFLOW_HOME with up-to-date DAF_AGENTS.md
    cs_home = get_cs_home()
    bundled_content, _ = _get_bundled_daf_agents_content()
    (cs_home / "DAF_AGENTS.md").write_text(bundled_content)

    # Create workspace with DIFFERENT (older) DAF_AGENTS.md
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "DAF_AGENTS.md").write_text("# Old Workspace Version")

    # Create repo WITHOUT DAF_AGENTS.md
    repo_dir = workspace / "test-repo"
    repo_dir.mkdir()

    # Create config
    config_loader = ConfigLoader()
    config = config_loader.create_default_config()
    from devflow.config.models import WorkspaceDefinition
    config.repos.workspaces = [
        WorkspaceDefinition(name="default", path=str(workspace))
    ]
    config.repos.last_used_workspace = "default"
    config_loader.save_config(config)

    session = _create_mock_session(str(repo_dir))

    # Should find DEVAIFLOW_HOME version (not workspace version)
    result = validate_daf_agents_md(session, config_loader)
    assert result is True

    # Workspace file should still have old content (wasn't used)
    assert (workspace / "DAF_AGENTS.md").read_text() == "# Old Workspace Version"


@pytest.mark.skip(reason="DAF_AGENTS.md removed - replaced by daf-workflow skill")
def test_validate_daf_agents_upgrade_devaiflow_home(tmp_path, temp_daf_home, monkeypatch):
    """Test that upgrade detection works for DEVAIFLOW_HOME location."""
    from devflow.config.loader import ConfigLoader
    from devflow.utils.paths import get_cs_home
    from unittest.mock import MagicMock

    # Mock Confirm.ask to return True (user accepts upgrade)
    mock_confirm = MagicMock(return_value=True)
    monkeypatch.setattr("rich.prompt.Confirm.ask", mock_confirm)

    # Create DEVAIFLOW_HOME with outdated DAF_AGENTS.md
    cs_home = get_cs_home()
    (cs_home / "DAF_AGENTS.md").write_text("# Old DEVAIFLOW_HOME Version")

    # Create workspace and repo
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    repo_dir = workspace / "test-repo"
    repo_dir.mkdir()

    # Create config
    config_loader = ConfigLoader()
    config = config_loader.create_default_config()
    from devflow.config.models import WorkspaceDefinition
    config.repos.workspaces = [
        WorkspaceDefinition(name="default", path=str(workspace))
    ]
    config.repos.last_used_workspace = "default"
    config_loader.save_config(config)

    session = _create_mock_session(str(repo_dir))

    # Should find, check, and upgrade DEVAIFLOW_HOME version
    result = validate_daf_agents_md(session, config_loader)
    assert result is True

    # Verify upgrade was performed on DEVAIFLOW_HOME file
    bundled_content, _ = _get_bundled_daf_agents_content()
    new_content = (cs_home / "DAF_AGENTS.md").read_text()
    assert new_content == bundled_content
    assert "Old DEVAIFLOW_HOME Version" not in new_content

    # Verify Confirm was called for upgrade
    assert mock_confirm.called
