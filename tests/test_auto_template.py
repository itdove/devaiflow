"""Tests for auto-template creation and usage functionality."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from devflow.config.loader import ConfigLoader
from devflow.config.models import Config, JiraConfig, RepoConfig, TemplateConfig
from devflow.templates.manager import TemplateManager
from devflow.templates.models import SessionTemplate


def test_template_config_defaults():
    """Test that TemplateConfig has correct default values."""
    config = TemplateConfig()

    assert config.auto_create is True
    assert config.auto_use is True


def test_template_config_in_main_config(temp_daf_home):
    """Test that TemplateConfig is properly integrated into main Config."""
    config_loader = ConfigLoader()

    # Create a config with template settings
    config = Config(
        jira=JiraConfig(
            url="https://jira.example.com",
            user="test-user",
            transitions={},
        ),
        repos=RepoConfig(
            workspace="/test/workspace",
        ),
        templates=TemplateConfig(
            auto_create=True,
            auto_use=True,
        ),
    )

    # Save and reload
    config_loader.save_config(config)
    loaded_config = config_loader.load_config()

    assert loaded_config is not None
    assert loaded_config.templates.auto_create is True
    assert loaded_config.templates.auto_use is True


def test_auto_create_template_when_enabled(temp_daf_home):
    """Test that templates are auto-created when auto_create is enabled."""
    from devflow.cli.commands.new_command import create_new_session

    config_loader = ConfigLoader()

    # Create config with auto_create enabled
    from devflow.config.models import WorkspaceDefinition
    config = Config(
        jira=JiraConfig(
            url="https://jira.example.com",
            user="test-user",
            transitions={},
        ),
        repos=RepoConfig(
            workspaces=[
                WorkspaceDefinition(
                    name="default",
                    path=str(temp_daf_home / "workspace")
                )
            ],
        ),
        templates=TemplateConfig(
            auto_create=True,
            auto_use=False,
        ),
    )
    config_loader.save_config(config)

    # Create a test project directory
    project_path = temp_daf_home / "workspace" / "test-project"
    project_path.mkdir(parents=True)

    # Mock subprocess calls to prevent actual Claude Code launch
    with patch("subprocess.run") as mock_run:
        with patch("devflow.cli.commands.new_command.Confirm.ask", return_value=False):
            # Mock JIRA client to avoid actual JIRA calls
            with patch("devflow.cli.commands.new_command.JiraClient"):
                create_new_session(
                    name="test-session",
                    goal="Test goal",
                    path=str(project_path),
                )

    # Verify template was auto-created
    template_manager = TemplateManager()
    template = template_manager.get_template("test-project")

    assert template is not None
    assert template.name == "test-project"
    assert template.working_directory == "test-project"
    assert "Auto-created" in template.description


def test_auto_use_template_when_enabled(temp_daf_home):
    """Test that template manager can find matching templates."""
    config_loader = ConfigLoader()

    # Create config with auto_use enabled
    config = Config(
        jira=JiraConfig(
            url="https://jira.example.com",
            user="test-user",
            transitions={},
        ),
        repos=RepoConfig(
            workspace=str(temp_daf_home / "workspace"),
        ),
        templates=TemplateConfig(
            auto_create=False,
            auto_use=True,
        ),
    )
    config_loader.save_config(config)

    # Create a template
    template_manager = TemplateManager()
    template = SessionTemplate(
        name="test-template",
        description="Test template",
        working_directory="test-project",
        issue_key="PROJ",
    )
    template_manager.save_template(template)

    # Create a test project directory with matching name
    project_path = temp_daf_home / "workspace" / "test-project"
    project_path.mkdir(parents=True)

    # Test that the template manager can find a matching template
    found_template = template_manager.find_matching_template(project_path)

    assert found_template is not None
    assert found_template.name == "test-template"
    assert found_template.working_directory == "test-project"


def test_no_auto_create_when_disabled(temp_daf_home):
    """Test that templates are NOT auto-created when auto_create is disabled."""
    from devflow.cli.commands.new_command import create_new_session

    config_loader = ConfigLoader()

    # Create config with auto_create disabled
    config = Config(
        jira=JiraConfig(
            url="https://jira.example.com",
            user="test-user",
            transitions={},
        ),
        repos=RepoConfig(
            workspace=str(temp_daf_home / "workspace"),
        ),
        templates=TemplateConfig(
            auto_create=False,
            auto_use=False,
        ),
    )
    config_loader.save_config(config)

    # Create a test project directory
    project_path = temp_daf_home / "workspace" / "test-project-2"
    project_path.mkdir(parents=True)

    # Mock subprocess calls to prevent actual Claude Code launch
    with patch("subprocess.run") as mock_run:
        with patch("devflow.cli.commands.new_command.Confirm.ask", return_value=False):
            # Mock JIRA client
            with patch("devflow.cli.commands.new_command.JiraClient"):
                create_new_session(
                    name="test-session-2",
                    goal="Test goal",
                    path=str(project_path),
                )

    # Verify template was NOT auto-created
    template_manager = TemplateManager()
    template = template_manager.get_template("test-project-2")

    assert template is None


def test_auto_create_template_in_open_command(temp_daf_home):
    """Test that templates are auto-created in daf open when selecting directory."""
    from devflow.cli.commands.open_command import _prompt_for_working_directory
    from devflow.config.models import Session
    from devflow.session.manager import SessionManager

    config_loader = ConfigLoader()

    # Create config with auto_create enabled
    from devflow.config.models import WorkspaceDefinition
    config = Config(
        jira=JiraConfig(
            url="https://jira.example.com",
            user="test-user",
            transitions={},
        ),
        repos=RepoConfig(
            workspaces=[
                WorkspaceDefinition(
                    name="default",
                    path=str(temp_daf_home / "workspace")
                )
            ],
        ),
        templates=TemplateConfig(
            auto_create=True,
            auto_use=False,
        ),
    )
    config_loader.save_config(config)

    # Create workspace directory
    workspace = temp_daf_home / "workspace"
    workspace.mkdir(parents=True)

    # Create a test project directory
    project_path = workspace / "open-test-project"
    project_path.mkdir(parents=True)

    # Create a session without project_path
    session_manager = SessionManager(config_loader)
    session = Session(
        name="test-session",
        goal="Test goal",
        issue_key="PROJ-12345",
    )
    session_manager.index.add_session(session)
    # Use the session manager's own save method
    config_loader.save_sessions(session_manager.index)

    # Mock Prompt.ask to return the project directory
    with patch("rich.prompt.Prompt.ask", return_value="1"):
        result = _prompt_for_working_directory(session, config_loader, session_manager)

    assert result is True
    # Check conversation-based API (active_conversation returns the conversation)
    active_conv = session.active_conversation
    assert active_conv is not None
    assert active_conv.project_path == str(project_path)

    # Verify template was auto-created
    template_manager = TemplateManager()
    template = template_manager.get_template("open-test-project")

    assert template is not None
    assert template.name == "open-test-project"
    assert template.working_directory == "open-test-project"


def test_no_duplicate_template_creation(temp_daf_home):
    """Test that duplicate templates are not created."""
    from devflow.cli.commands.new_command import create_new_session

    config_loader = ConfigLoader()

    # Create config with auto_create enabled
    from devflow.config.models import WorkspaceDefinition
    config = Config(
        jira=JiraConfig(
            url="https://jira.example.com",
            user="test-user",
            transitions={},
        ),
        repos=RepoConfig(
            workspaces=[
                WorkspaceDefinition(
                    name="default",
                    path=str(temp_daf_home / "workspace")
                )
            ],
        ),
        templates=TemplateConfig(
            auto_create=True,
            auto_use=False,
        ),
    )
    config_loader.save_config(config)

    # Create a test project directory
    project_path = temp_daf_home / "workspace" / "duplicate-test"
    project_path.mkdir(parents=True)

    # Create first session (should create template)
    with patch("subprocess.run") as mock_run:
        with patch("devflow.cli.commands.new_command.Confirm.ask", return_value=False):
            with patch("devflow.cli.commands.new_command.JiraClient"):
                create_new_session(
                    name="test-session-1",
                    goal="Test goal 1",
                    path=str(project_path),
                )

    # Verify template was created
    template_manager = TemplateManager()
    template1 = template_manager.get_template("duplicate-test")
    assert template1 is not None

    # Create second session in same directory (should NOT create duplicate)
    with patch("subprocess.run") as mock_run:
        with patch("devflow.cli.commands.new_command.Confirm.ask", return_value=False):
            with patch("devflow.cli.commands.new_command.JiraClient"):
                create_new_session(
                    name="test-session-2",
                    goal="Test goal 2",
                    path=str(project_path),
                )

    # Verify only one template exists
    templates = template_manager.list_templates()
    duplicate_templates = [t for t in templates if t.name == "duplicate-test"]
    assert len(duplicate_templates) == 1


def test_template_usage_tracking(temp_daf_home):
    """Test that template usage statistics can be updated."""
    template_manager = TemplateManager()

    # Create a template
    template = SessionTemplate(
        name="usage-test",
        description="Usage tracking test",
        working_directory="usage-project",
    )
    template_manager.save_template(template)

    # Update usage multiple times
    for i in range(3):
        template_manager.update_usage("usage-test")

    # Verify usage count was updated
    retrieved_template = template_manager.get_template("usage-test")
    assert retrieved_template.usage_count == 3
    assert retrieved_template.last_used is not None
