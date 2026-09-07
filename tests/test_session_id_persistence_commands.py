"""Regression tests for self-identifying agent session persistence."""

from pathlib import Path
from unittest.mock import MagicMock, patch

from devflow.cli.commands.investigate_command import (
    _create_multi_project_investigation_session,
    create_investigation_session,
)
from devflow.cli.commands.jira_new_command import (
    _create_multi_project_jira_session,
    create_jira_ticket_session,
)
from devflow.config.loader import ConfigLoader
from devflow.config.models import WorkspaceDefinition
from devflow.session.manager import SessionManager


def _configure_workspace(config_loader: ConfigLoader, workspace_path: Path):
    """Save a minimal generic configuration with one test workspace."""
    config = config_loader.create_default_config()
    config.repos.workspaces = [
        WorkspaceDefinition(name="default", path=str(workspace_path))
    ]
    config.repos.last_used_workspace = "default"
    config_loader.save_config(config)
    return config


def _agent_client():
    """Return an agent client double suitable for launch-path tests."""
    client = MagicMock()
    client.supports_permission_prompts.return_value = True
    client.get_agent_name.return_value = "Codex"
    return client


def _rename_and_update_session(
    session_name: str,
    renamed_name: str,
    issue_key: str,
    issue_metadata: dict,
) -> None:
    """Simulate child-process metadata changes made during agent execution."""
    child_manager = SessionManager(config_loader=ConfigLoader())
    child_manager.rename_session(session_name, renamed_name)
    child_session = child_manager.get_session(renamed_name)
    child_session.issue_key = issue_key
    child_session.issue_metadata = issue_metadata
    child_manager.update_session(child_session)


def test_jira_new_persists_codex_id_after_signal_cleanup(
    temp_daf_home, tmp_path
):
    """Keep JIRA metadata and the captured ID when ticket creation renames a session."""
    config_loader = ConfigLoader()
    project_path = tmp_path / "project-a"
    project_path.mkdir()
    _configure_workspace(config_loader, tmp_path / "workspace")
    captured_id = "codex-jira-thread-123"
    renamed_name = "creation-PROJ-123"

    def launch_and_link_issue(_agent, _backend, _path, active_conversation, **_kwargs):
        active_conversation.ai_agent_session_id = captured_id
        _rename_and_update_session(
            "create-jira-issue",
            renamed_name,
            "PROJ-123",
            {"status": "new"},
        )

    with patch(
        "devflow.cli.commands.jira_new_command.should_launch_claude_code",
        return_value=True,
    ), patch(
        "devflow.cli.commands.jira_new_command.validate_daf_agents_md",
        return_value=True,
    ), patch(
        "devflow.cli.commands.jira_new_command.setup_signal_handlers"
    ), patch(
        "devflow.cli.commands.jira_new_command.is_cleanup_done",
        return_value=True,
    ), patch(
        "devflow.agent.create_agent_client",
        return_value=_agent_client(),
    ), patch(
        "devflow.agent.factory.launch_and_capture",
        side_effect=launch_and_link_issue,
    ), patch(
        "devflow.cli.commands.open_command._prompt_for_complete_on_exit"
    ):
        create_jira_ticket_session(
            issue_type="task",
            parent=None,
            goal="Create a generic issue",
            name="create-jira-issue",
            path=str(project_path),
            temp_clone=False,
            agent="codex",
        )

    session = SessionManager(config_loader=ConfigLoader()).get_session(renamed_name)
    assert session is not None
    assert session.issue_key == "PROJ-123"
    assert session.issue_metadata["status"] == "new"
    assert session.active_conversation.ai_agent_session_id == captured_id


def test_investigate_persists_codex_id_after_agent_exit(temp_daf_home, tmp_path):
    """Persist a captured ID for a single-project investigation session."""
    config_loader = ConfigLoader()
    project_path = tmp_path / "project-a"
    project_path.mkdir()
    _configure_workspace(config_loader, tmp_path / "workspace")
    captured_id = "codex-investigation-thread-123"

    def launch_and_record(_agent, _backend, _path, active_conversation, **_kwargs):
        active_conversation.ai_agent_session_id = captured_id
        child_manager = SessionManager(config_loader=ConfigLoader())
        child_session = child_manager.get_session("investigate-session")
        child_session.issue_metadata = {"status": "reviewed"}
        child_manager.update_session(child_session)

    with patch(
        "devflow.cli.commands.investigate_command.should_launch_claude_code",
        return_value=True,
    ), patch(
        "devflow.cli.commands.investigate_command.validate_daf_agents_md",
        return_value=True,
    ), patch(
        "devflow.cli.commands.investigate_command.setup_signal_handlers"
    ), patch(
        "devflow.cli.commands.investigate_command.is_cleanup_done",
        return_value=False,
    ), patch(
        "devflow.agent.create_agent_client",
        return_value=_agent_client(),
    ), patch(
        "devflow.agent.factory.launch_and_capture",
        side_effect=launch_and_record,
    ), patch(
        "devflow.cli.commands.open_command._prompt_for_complete_on_exit"
    ):
        create_investigation_session(
            goal="Review a generic investigation",
            name="investigate-session",
            path=str(project_path),
            temp_clone=False,
            agent="codex",
        )

    session = SessionManager(config_loader=ConfigLoader()).get_session(
        "investigate-session"
    )
    assert session is not None
    assert session.issue_metadata["status"] == "reviewed"
    assert session.active_conversation.ai_agent_session_id == captured_id


def test_multi_project_jira_new_persists_codex_id_after_rename(
    temp_daf_home, tmp_path
):
    """Persist captured IDs for the multi-project JIRA creation path."""
    config_loader = ConfigLoader()
    workspace_path = tmp_path / "workspace"
    project_paths = [workspace_path / "project-a", workspace_path / "project-b"]
    for project_path in project_paths:
        project_path.mkdir(parents=True)
    config = _configure_workspace(config_loader, workspace_path)
    captured_id = "codex-jira-multi-thread-123"
    original_name = "create-jira-multi"
    renamed_name = "creation-PROJ-456"

    def launch_and_link_issue(_agent, _backend, _path, active_conversation, **_kwargs):
        active_conversation.ai_agent_session_id = captured_id
        _rename_and_update_session(
            original_name,
            renamed_name,
            "PROJ-456",
            {"status": "new"},
        )

    with patch(
        "devflow.cli.commands.jira_new_command.get_workspace_path",
        return_value=str(workspace_path),
    ), patch(
        "devflow.cli.commands.jira_new_command.should_launch_claude_code",
        return_value=True,
    ), patch(
        "devflow.agent.create_agent_client",
        return_value=_agent_client(),
    ), patch(
        "devflow.agent.factory.launch_and_capture",
        side_effect=launch_and_link_issue,
    ):
        _create_multi_project_jira_session(
            config=config,
            config_loader=config_loader,
            name=original_name,
            goal="Create a cross-project issue",
            issue_type="task",
            parent=None,
            project_paths=[str(path) for path in project_paths],
            workspace="default",
            selected_workspace_name="default",
            agent="codex",
        )

    session = SessionManager(config_loader=ConfigLoader()).get_session(renamed_name)
    assert session is not None
    assert session.issue_key == "PROJ-456"
    assert session.active_conversation.ai_agent_session_id == captured_id


def test_multi_project_investigate_persists_codex_id_after_rename(
    temp_daf_home, tmp_path
):
    """Persist captured IDs for the multi-project investigation path."""
    config_loader = ConfigLoader()
    workspace_path = tmp_path / "workspace"
    project_paths = [workspace_path / "project-a", workspace_path / "project-b"]
    for project_path in project_paths:
        project_path.mkdir(parents=True)
    config = _configure_workspace(config_loader, workspace_path)
    captured_id = "codex-investigation-multi-thread-123"
    original_name = "investigate-multi"
    renamed_name = "investigation-PROJ-789"

    def launch_and_record(_agent, _backend, _path, active_conversation, **_kwargs):
        active_conversation.ai_agent_session_id = captured_id
        _rename_and_update_session(
            original_name,
            renamed_name,
            "PROJ-789",
            {"status": "reviewed"},
        )

    with patch(
        "devflow.cli.commands.investigate_command.get_workspace_path",
        return_value=str(workspace_path),
    ), patch(
        "devflow.cli.commands.investigate_command.resolve_workspace_path",
        return_value=str(workspace_path),
    ), patch(
        "devflow.cli.commands.investigate_command.should_launch_claude_code",
        return_value=True,
    ), patch(
        "devflow.cli.commands.investigate_command.validate_daf_agents_md",
        return_value=True,
    ), patch(
        "devflow.cli.commands.investigate_command.setup_signal_handlers"
    ), patch(
        "devflow.cli.commands.investigate_command.is_cleanup_done",
        return_value=False,
    ), patch(
        "devflow.agent.create_agent_client",
        return_value=_agent_client(),
    ), patch(
        "devflow.agent.factory.launch_and_capture",
        side_effect=launch_and_record,
    ), patch(
        "devflow.cli.commands.open_command._prompt_for_complete_on_exit"
    ):
        _create_multi_project_investigation_session(
            config=config,
            config_loader=config_loader,
            name=original_name,
            goal="Inspect a cross-project behavior",
            parent=None,
            project_paths=[str(path) for path in project_paths],
            workspace="default",
            selected_workspace_name="default",
            agent="codex",
        )

    session = SessionManager(config_loader=ConfigLoader()).get_session(renamed_name)
    assert session is not None
    assert session.issue_key == "PROJ-789"
    assert session.active_conversation.ai_agent_session_id == captured_id
