"""Regression tests for persisted model provider and model selections."""

from unittest.mock import MagicMock, patch

from click.testing import CliRunner

from devflow.cli.commands.jira_new_command import create_jira_ticket_session
from devflow.cli.commands.new_command import create_new_session
from devflow.cli.commands.new_command_multiproject import create_multi_project_session
from devflow.cli.commands.ticket_creation_multiproject import (
    create_multi_project_ticket_creation_session,
)
from devflow.cli.main import cli
from devflow.config.loader import ConfigLoader
from devflow.config.models import ModelProviderConfig, ModelProviderProfile
from devflow.session.manager import SessionManager


def _configure_profiles(config_loader: ConfigLoader):
    """Configure generic profiles used by persistence tests."""
    config = config_loader.create_default_config()
    config.model_provider = ModelProviderConfig(
        default_profile="configured-profile",
        profiles={
            "configured-profile": ModelProviderProfile(
                name="configured-profile",
                provider="anthropic",
                agent_backend="claude",
                model_name="configured-model",
            ),
            "changed-profile": ModelProviderProfile(
                name="changed-profile",
                provider="codex",
                agent_backend="codex",
                model_name="changed-model",
            ),
        },
    )
    config_loader.save_config(config)
    return config


def test_new_persists_configured_profile_and_model(temp_daf_home, tmp_path):
    """A normal session stores the profile selected by configuration."""
    config_loader = ConfigLoader()
    _configure_profiles(config_loader)
    project_path = tmp_path / "project-a"
    project_path.mkdir()

    create_new_session(
        name="model-persistence",
        goal="Persist the configured model selection",
        path=str(project_path),
        branch="main",
        create_branch=False,
        output_json=True,
    )

    session = SessionManager(config_loader=ConfigLoader()).get_session("model-persistence")
    assert session is not None
    assert session.model_profile == "configured-profile"
    assert session.model_id == "configured-model"
    assert session.agent_backend == "claude"


def test_new_multi_project_persists_configured_profile_and_model(temp_daf_home, tmp_path):
    """The multi-project development path stores effective provider metadata."""
    config_loader = ConfigLoader()
    config = _configure_profiles(config_loader)
    workspace_path = tmp_path / "workspace"
    workspace_path.mkdir()
    for project_name in ("project-a", "project-b"):
        project_path = workspace_path / project_name
        project_path.mkdir()
        (project_path / ".git").mkdir()

    session_manager = SessionManager(config_loader=config_loader)
    with patch(
        "devflow.cli.commands.new_command._handle_branch_creation",
        return_value=("shared-branch", "main"),
    ):
        create_multi_project_session(
            session_manager=session_manager,
            config_loader=config_loader,
            config=config,
            name="multi-model-persistence",
            goal="Persist a multi-project model selection",
            issue_key=None,
            issue_metadata_dict=None,
            issue_title=None,
            project_names=["project-a", "project-b"],
            workspace_path=str(workspace_path),
            selected_workspace_name="workspace-a",
            force_new_session=False,
            model_profile=None,
            output_json=True,
            create_branch=False,
            source_branch="main",
            non_interactive=True,
        )

    session = session_manager.get_session("multi-model-persistence")
    assert session is not None
    assert session.model_profile == "configured-profile"
    assert session.model_id == "configured-model"


def test_ticket_creation_multi_project_persists_configured_profile_and_model(tmp_path):
    """Shared ticket-creation sessions retain effective profile metadata."""
    config = ConfigLoader().create_default_config()
    config.model_provider = ModelProviderConfig(
        default_profile="configured-profile",
        profiles={
            "configured-profile": ModelProviderProfile(
                name="configured-profile",
                provider="anthropic",
                agent_backend="claude",
                model_name="configured-model",
            )
        },
    )
    workspace_path = tmp_path / "workspace"
    workspace_path.mkdir()
    project_paths = []
    for project_name in ("project-a", "project-b"):
        project_path = workspace_path / project_name
        project_path.mkdir()
        project_paths.append(str(project_path))

    session_manager = MagicMock()
    session_manager.create_session.return_value = MagicMock()

    create_multi_project_ticket_creation_session(
        session_manager=session_manager,
        config=config,
        name="ticket-model-persistence",
        goal="Persist ticket creation model selection",
        project_paths=project_paths,
        workspace_path=str(workspace_path),
        selected_workspace_name="workspace-a",
    )

    create_kwargs = session_manager.create_session.call_args.kwargs
    assert create_kwargs["model_profile"] == "configured-profile"
    assert create_kwargs["model_id"] == "configured-model"
    assert create_kwargs["agent_backend"] == "claude"


def test_git_new_persists_configured_profile_and_model(
    temp_daf_home, tmp_path
):
    """Single-project Git issue sessions store effective profile metadata."""
    config_loader = ConfigLoader()
    _configure_profiles(config_loader)
    project_path = tmp_path / "project-a"
    project_path.mkdir()

    with patch(
        "devflow.cli.commands.git_new_command.should_launch_claude_code",
        return_value=False,
    ):
        from devflow.cli.commands.git_new_command import create_git_issue_session

        create_git_issue_session(
            goal="Persist the Git issue model selection",
            name="git-model-persistence",
            path=str(project_path),
            temp_clone=False,
        )

    session = SessionManager(config_loader=ConfigLoader()).get_session("git-model-persistence")
    assert session is not None
    assert session.model_profile == "configured-profile"
    assert session.model_id == "configured-model"


def test_jira_new_persists_configured_profile_and_model(temp_daf_home, tmp_path):
    """Single-project JIRA ticket sessions store effective profile metadata."""
    config_loader = ConfigLoader()
    _configure_profiles(config_loader)
    project_path = tmp_path / "project-a"
    project_path.mkdir()

    with patch(
        "devflow.cli.commands.jira_new_command.Confirm.ask",
        return_value=False,
    ):
        create_jira_ticket_session(
            issue_type="story",
            parent=None,
            goal="Persist the JIRA model selection",
            name="jira-model-persistence",
            path=str(project_path),
        )

    session = SessionManager(config_loader=ConfigLoader()).get_session(
        "jira-model-persistence"
    )
    assert session is not None
    assert session.model_profile == "configured-profile"
    assert session.model_id == "configured-model"


def test_open_reuses_persisted_profile_and_model_after_configuration_changes(
    temp_daf_home, tmp_path, monkeypatch
):
    """Reopen uses session metadata instead of the current default or environment."""
    config_loader = ConfigLoader()
    config = _configure_profiles(config_loader)
    config.model_provider.default_profile = "changed-profile"
    config_loader.save_config(config)

    project_path = tmp_path / "project-a"
    project_path.mkdir()
    session_manager = SessionManager(config_loader=config_loader)
    session_manager.create_session(
        name="reopen-model-persistence",
        goal="Reuse the original model selection",
        working_directory="project-a",
        project_path=str(project_path),
        ai_agent_session_id="codex-thread-123",
        model_profile="configured-profile",
        agent_backend="claude",
        model_id="configured-model",
    )
    monkeypatch.setenv("MODEL_PROVIDER_PROFILE", "changed-profile")

    mock_agent = MagicMock()
    mock_agent.get_agent_name.return_value = "Claude"
    mock_agent.session_exists.return_value = True
    runner = CliRunner()
    with patch(
        "devflow.cli.commands.open_command._detect_working_directory_from_cwd",
        return_value=None,
    ), patch(
        "devflow.cli.commands.open_command._handle_branch_checkout",
        return_value=True,
    ), patch(
        "devflow.cli.commands.open_command._check_and_sync_with_base_branch",
        return_value=True,
    ), patch(
        "devflow.cli.commands.open_command.should_launch_claude_code",
        return_value=False,
    ), patch("devflow.agent.create_agent_client", return_value=mock_agent):
        result = runner.invoke(cli, ["open", "reopen-model-persistence"])

    assert result.exit_code == 0
    mock_agent.session_exists.assert_called_once()
    loaded = SessionManager(config_loader=ConfigLoader()).get_session(
        "reopen-model-persistence"
    )
    assert loaded.model_profile == "configured-profile"
    assert loaded.agent_backend == "claude"
    assert loaded.model_id == "configured-model"
    assert loaded.active_conversation.ai_agent_session_id == "codex-thread-123"


def test_open_explicit_model_updates_persisted_model(temp_daf_home, tmp_path):
    """An explicit --model override becomes the model used by later reopens."""
    config_loader = ConfigLoader()
    _configure_profiles(config_loader)
    project_path = tmp_path / "project-a"
    project_path.mkdir()
    session_manager = SessionManager(config_loader=config_loader)
    session_manager.create_session(
        name="explicit-model-persistence",
        goal="Persist an explicit model override",
        working_directory="project-a",
        project_path=str(project_path),
        ai_agent_session_id="claude-session-123",
        model_profile="configured-profile",
        agent_backend="claude",
        model_id="configured-model",
    )

    mock_agent = MagicMock()
    mock_agent.get_agent_name.return_value = "Claude"
    mock_agent.session_exists.return_value = True
    runner = CliRunner()
    with patch(
        "devflow.cli.commands.open_command._detect_working_directory_from_cwd",
        return_value=None,
    ), patch(
        "devflow.cli.commands.open_command._handle_branch_checkout",
        return_value=True,
    ), patch(
        "devflow.cli.commands.open_command._check_and_sync_with_base_branch",
        return_value=True,
    ), patch(
        "devflow.cli.commands.open_command.should_launch_claude_code",
        return_value=False,
    ), patch("devflow.agent.create_agent_client", return_value=mock_agent):
        result = runner.invoke(
            cli,
            [
                "open",
                "explicit-model-persistence",
                "--model-profile",
                "changed-profile",
                "--model",
                "explicit-model",
            ],
        )

    assert result.exit_code == 0
    loaded = SessionManager(config_loader=ConfigLoader()).get_session(
        "explicit-model-persistence"
    )
    assert loaded.model_profile == "changed-profile"
    assert loaded.agent_backend == "codex"
    assert loaded.model_id == "explicit-model", (
        result.exit_code,
        result.output,
        loaded.model_profile,
        loaded.agent_backend,
    )
