"""Regression tests for self-identifying agent sessions created by ``daf git new``."""

from unittest.mock import MagicMock, patch

from devflow.agent.factory import PENDING_CAPTURE_PLACEHOLDER
from devflow.cli.commands.git_new_command import (
    _sync_captured_agent_session,
    _create_multi_project_git_session,
    create_git_issue_session,
)
from devflow.config.models import Session
from devflow.config.loader import ConfigLoader
from devflow.session.manager import SessionManager


def _create_ticket_creation_session(
    session_manager: SessionManager,
    project_path: str,
    name: str = "create-issue",
    agent_backend: str = "codex",
) -> Session:
    """Create the persisted session state that precedes an agent launch."""
    session = session_manager.create_session(
        name=name,
        goal="Create a GitHub issue for session persistence",
        working_directory="project-a",
        project_path=project_path,
        agent_backend=agent_backend,
    )
    session.session_type = "ticket_creation"
    session.add_conversation(
        working_dir="project-a",
        ai_agent_session_id=PENDING_CAPTURE_PLACEHOLDER,
        project_path=project_path,
        branch=None,
    )
    session.working_directory = "project-a"
    session_manager.update_session(session)
    return session


def test_sync_captured_agent_session_persists_id_after_session_rename(
    temp_daf_home, tmp_path
):
    """Persist the captured ID without losing metadata saved by the child process."""
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader=config_loader)
    project_path = str(tmp_path / "project-a")

    session = _create_ticket_creation_session(session_manager, project_path)

    # Simulate the child process linking the issue and renaming the session.
    child_manager = SessionManager(config_loader=config_loader)
    child_manager.rename_session("create-issue", "creation-owner-repo-123")
    renamed_session = child_manager.get_session("creation-owner-repo-123")
    renamed_session.issue_key = "owner/repo#123"
    renamed_session.goal = "owner/repo#123: Create a GitHub issue for session persistence"
    child_manager.update_session(renamed_session)

    # The parent capture lifecycle updates its original in-memory object.
    session.active_conversation.ai_agent_session_id = "codex-thread-123"
    session_manager.index = config_loader.load_sessions()

    synced_session = _sync_captured_agent_session(
        session_manager,
        session,
        "create-issue",
        "codex",
    )

    assert synced_session is not None
    assert synced_session.name == "creation-owner-repo-123"
    assert synced_session.active_conversation.ai_agent_session_id == "codex-thread-123"

    reloaded_session = SessionManager(config_loader=config_loader).get_session(
        "creation-owner-repo-123"
    )
    assert reloaded_session.issue_key == "owner/repo#123"
    assert reloaded_session.active_conversation.ai_agent_session_id == "codex-thread-123"


def test_sync_captured_agent_session_keeps_placeholder_when_capture_fails(
    temp_daf_home, tmp_path
):
    """Leave ``pending-capture`` intact so the next open can retry detection."""
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader=config_loader)
    session = _create_ticket_creation_session(
        session_manager,
        str(tmp_path / "project-a"),
        agent_backend="opencode",
    )
    session_manager.index = config_loader.load_sessions()

    synced_session = _sync_captured_agent_session(
        session_manager,
        session,
        "create-issue",
        "opencode",
    )

    assert synced_session is not None
    assert synced_session.active_conversation.ai_agent_session_id == PENDING_CAPTURE_PLACEHOLDER
    reloaded_session = SessionManager(config_loader=config_loader).get_session("create-issue")
    assert reloaded_session.active_conversation.ai_agent_session_id == PENDING_CAPTURE_PLACEHOLDER


def test_sync_captured_agent_session_returns_none_when_session_is_missing(
    temp_daf_home, tmp_path
):
    """Do not create a new session record when the original was removed."""
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader=config_loader)
    session = _create_ticket_creation_session(
        session_manager,
        str(tmp_path / "project-a"),
    )
    session_manager.delete_session("create-issue")
    session.active_conversation.ai_agent_session_id = "codex-thread-123"
    session_manager.index = config_loader.load_sessions()

    assert _sync_captured_agent_session(
        session_manager,
        session,
        "create-issue",
        "codex",
    ) is None


def test_git_new_codex_launch_persists_id_for_creation_session_reopen(
    temp_daf_home, tmp_path
):
    """Persist Codex's captured ID after the child links and renames the issue."""
    config_loader = ConfigLoader()
    config = config_loader.create_default_config()
    project_path = tmp_path / "project-a"
    project_path.mkdir()
    renamed_name = "creation-owner-repo-123"
    captured_id = "codex-thread-123"

    agent_client = MagicMock()
    agent_client.supports_permission_prompts.return_value = True
    agent_client.get_agent_name.return_value = "Codex"

    def launch_and_link_issue(_agent, _backend, _project_path, active_conversation, **_kwargs):
        """Simulate agent exit after linking the issue in a child process."""
        active_conversation.ai_agent_session_id = captured_id

        child_manager = SessionManager(config_loader=ConfigLoader())
        child_manager.rename_session("create-issue", renamed_name)
        child_session = child_manager.get_session(renamed_name)
        child_session.issue_key = "owner/repo#123"
        child_session.issue_tracker = "github"
        child_session.issue_metadata = {
            "summary": "Create a GitHub issue for session persistence",
            "status": "open",
        }
        child_manager.update_session(child_session)

    with patch(
        "devflow.cli.commands.git_new_command.should_launch_claude_code",
        return_value=True,
    ), patch(
        "devflow.cli.commands.git_new_command.validate_daf_agents_md",
        return_value=True,
    ), patch(
        "devflow.cli.commands.git_new_command.setup_signal_handlers"
    ), patch(
        "devflow.cli.commands.git_new_command.is_cleanup_done",
        return_value=False,
    ), patch(
        "devflow.agent.create_agent_client",
        return_value=agent_client,
    ), patch(
        "devflow.agent.factory.launch_and_capture",
        side_effect=launch_and_link_issue,
    ), patch(
        "devflow.cli.commands.open_command._prompt_for_complete_on_exit"
    ):
        create_git_issue_session(
            goal="Create a GitHub issue for session persistence",
            issue_type="bug",
            name="create-issue",
            path=str(project_path),
            temp_clone=False,
            agent="codex",
        )

    reloaded_session = SessionManager(config_loader=ConfigLoader()).get_session(
        renamed_name
    )
    assert reloaded_session is not None
    assert reloaded_session.issue_key == "owner/repo#123"
    assert reloaded_session.issue_metadata["status"] == "open"
    assert reloaded_session.active_conversation.ai_agent_session_id == captured_id


def test_multi_project_git_new_persists_captured_id_after_session_rename(
    temp_daf_home, tmp_path
):
    """Persist captured IDs for the multi-project ticket-creation path too."""
    config_loader = ConfigLoader()
    config = config_loader.create_default_config()
    workspace_path = tmp_path / "workspace"
    project_paths = [workspace_path / "project-a", workspace_path / "project-b"]
    for project_path in project_paths:
        project_path.mkdir(parents=True)

    original_name = "create-multi-project-issue"
    renamed_name = "creation-owner-repo-456"
    captured_id = "codex-thread-456"

    def create_multi_session(session_manager, **kwargs):
        """Create the persisted multi-project session before launch."""
        session = session_manager.create_session(
            name=kwargs["name"],
            goal=kwargs["goal"],
            agent_backend="codex",
        )
        session.session_type = "ticket_creation"
        projects_info = {
            project_path.name: {
                "project_path": str(project_path),
                "branch": "main",
                "base_branch": "main",
            }
            for project_path in project_paths
        }
        session.add_multi_project_conversation(
            ai_agent_session_id=PENDING_CAPTURE_PLACEHOLDER,
            projects_info=projects_info,
            workspace_path=kwargs["workspace_path"],
        )
        session_manager.update_session(session)
        return session, PENDING_CAPTURE_PLACEHOLDER

    def launch_and_link_issue(
        _agent, _backend, _project_path, active_conversation, **_kwargs
    ):
        """Simulate agent exit after linking and renaming the issue."""
        active_conversation.ai_agent_session_id = captured_id

        child_manager = SessionManager(config_loader=ConfigLoader())
        child_manager.rename_session(original_name, renamed_name)
        child_session = child_manager.get_session(renamed_name)
        child_session.issue_key = "owner/repo#456"
        child_session.issue_metadata = {"status": "open"}
        child_manager.update_session(child_session)

    with patch(
        "devflow.cli.commands.git_new_command.get_workspace_path",
        return_value=str(workspace_path),
    ), patch(
        "devflow.cli.commands.git_new_command.should_launch_claude_code",
        return_value=True,
    ), patch(
        "devflow.cli.commands.ticket_creation_multiproject.create_multi_project_ticket_creation_session",
        side_effect=create_multi_session,
    ), patch(
        "devflow.utils.git_remote.GitRemoteDetector.parse_repository_info",
        return_value=None,
    ), patch(
        "devflow.agent.create_agent_client",
        return_value=MagicMock(),
    ), patch(
        "devflow.agent.factory.launch_and_capture",
        side_effect=launch_and_link_issue,
    ):
        _create_multi_project_git_session(
            config=config,
            config_loader=config_loader,
            name=original_name,
            goal="Create a cross-project issue",
            issue_type="bug",
            parent=None,
            project_paths=[str(path) for path in project_paths],
            target_repo_path=str(project_paths[0]),
            workspace=None,
            selected_workspace_name="default",
            agent="codex",
        )

    reloaded_session = SessionManager(config_loader=ConfigLoader()).get_session(
        renamed_name
    )
    assert reloaded_session is not None
    assert reloaded_session.issue_key == "owner/repo#456"
    assert reloaded_session.active_conversation.ai_agent_session_id == captured_id
