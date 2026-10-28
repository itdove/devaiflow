"""Persisted first-open cancellation, retry, and explicit recovery (issue #650)."""

import json
import subprocess
from contextlib import nullcontext
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from click.testing import CliRunner

from devflow.agent.factory import PENDING_CAPTURE_PLACEHOLDER, launch_and_capture
from devflow.agent.opencode_agent import OpenCodeAgent, OpenCodeCompatibilityError
from devflow.cli.commands import open_command
from devflow.cli.commands.new_command import _handle_branch_creation
from devflow.cli.main import cli
from devflow.config.loader import ConfigLoader
from devflow.config.models import (
    Config,
    ConversationContext,
    JiraConfig,
    RepoConfig,
    WorkspaceDefinition,
)
from devflow.git.utils import GitUtils
from devflow.session.manager import SessionManager


@pytest.fixture
def first_open(temp_daf_home, tmp_path, monkeypatch):
    """Use real CLI/persistence; never run native agents or external Git operations."""
    monkeypatch.chdir(tmp_path)
    workspace = tmp_path / "workspace-1"
    project = workspace / "project-a"
    project.mkdir(parents=True)
    loader = ConfigLoader()
    loader.save_config(
        Config(
            jira=JiraConfig(url="https://jira.example.com", user="test-user", transitions={}),
            repos=RepoConfig(
                workspaces=[WorkspaceDefinition(name="workspace-1", path=str(workspace))],
                last_used_workspace="workspace-1",
            ),
            agent_backend="opencode",
        )
    )
    manager = SessionManager(loader)
    session = manager.create_session(
        name="session-a", goal="Test first open", agent_backend="opencode"
    )
    session.workspace_name = "workspace-1"
    manager.update_session(session)
    agent = OpenCodeAgent()
    agent._opencode_major_version = 2
    monkeypatch.setattr("devflow.agent.opencode_agent.require_tool", lambda *args: None)
    monkeypatch.setattr(agent, "_get_db_path", lambda: tmp_path / "native.db")
    monkeypatch.setattr(agent, "get_session_model_id", lambda *args: None)
    query = Mock(return_value=set())

    def create_native(*args, **kwargs):
        saved = SessionManager(loader).get_session(session.name).active_conversation
        assert saved.agent_launch_started is True
        assert saved.ai_agent_session_id == PENDING_CAPTURE_PLACEHOLDER
        return "ses_created"

    create = Mock(side_effect=create_native)
    monkeypatch.setattr(agent, "get_existing_sessions", query)
    monkeypatch.setattr(agent, "_create_session_with_title", create)
    monkeypatch.setattr(agent, "wait_for_exit", Mock())
    monkeypatch.setattr("devflow.agent.create_agent_client", lambda *args: agent)

    spawn = Mock(return_value=Mock(returncode=0))
    original_popen = subprocess.Popen

    def popen(command, **kwargs):
        if command[0] != "opencode":
            return original_popen(command, **kwargs)
        saved = SessionManager(loader).get_session(session.name).active_conversation
        assert saved.agent_launch_started is True
        assert saved.ai_agent_session_id == "ses_created"
        return spawn(command, **kwargs)

    monkeypatch.setattr("devflow.agent.opencode_agent.subprocess.Popen", popen)
    for name in (
        "_handle_branch_checkout",
        "_check_and_sync_with_base_branch",
        "_validate_context_files",
        "should_launch_claude_code",
        "_check_and_warn_feature_orchestration",
    ):
        monkeypatch.setattr(open_command, name, Mock(return_value=True))
    for name in (
        "_detect_working_directory_from_cwd",
        "_detect_workspace_from_cwd",
        "get_active_profile",
        "setup_signal_handlers",
        "_sync_branch_for_import",
        "_display_feature_context",
        "_display_session_summary",
        "_prompt_for_complete_on_exit",
        "_set_terminal_title",
    ):
        monkeypatch.setattr(open_command, name, Mock(return_value=None))
    monkeypatch.setattr(open_command, "is_cleanup_done", lambda: False)
    monkeypatch.setattr(
        "devflow.utils.workspace_utils.ensure_workspace_skills_and_commands",
        lambda *args, **kwargs: (True, None),
    )
    monkeypatch.setattr(
        "devflow.orchestration.feature.FeatureManager.get_session_context", lambda *args: None
    )
    monkeypatch.setattr(
        open_command,
        "check_concurrent_session",
        Mock(return_value=SimpleNamespace(safe_to_proceed=True, clone_path=None)),
    )
    monkeypatch.setattr(open_command, "scan_workspace_repositories", lambda *args: ["project-a"])
    selection = Mock(return_value=([str(project)], False))
    monkeypatch.setattr(open_command, "unified_project_selection", selection)
    branch = Mock(return_value=("feature-a", "main"))
    monkeypatch.setattr("devflow.cli.commands.new_command._handle_branch_creation", branch)
    monkeypatch.setattr(GitUtils, "is_git_repository", lambda *args: True)
    monkeypatch.setattr(GitUtils, "get_current_branch", lambda *args: "main")
    monkeypatch.setattr(GitUtils, "has_merge_conflicts", lambda *args: False)
    monkeypatch.setattr(GitUtils, "has_uncommitted_changes", lambda *args: True)
    monkeypatch.setattr(GitUtils, "get_status_summary", lambda *args: " M file.txt")
    return SimpleNamespace(
        loader=loader,
        session=session,
        project=project,
        workspace=workspace,
        agent=agent,
        query=query,
        create=create,
        spawn=spawn,
        branch=branch,
        selection=selection,
    )


def test_dirty_first_open_cancel_reload_retry_then_launch(first_open, monkeypatch):
    case = first_open
    work = case.project / "file.txt"
    work.write_text("uncommitted user work")
    checkout = Mock()
    create_branch = Mock()
    monkeypatch.setattr(GitUtils, "checkout_branch", checkout)
    monkeypatch.setattr(GitUtils, "create_branch", create_branch)
    monkeypatch.setattr(
        "devflow.cli.commands.new_command._handle_branch_creation", _handle_branch_creation
    )
    runner = CliRunner()

    for _ in range(2):
        result = runner.invoke(cli, ["open", case.session.name], input="\n")
        assert result.exit_code == 0, result.output
        assert "Continue anyway?" in result.output
        assert "Session open cancelled" in result.output
        assert "AGENT_SESSION_UNVERIFIED" not in result.output
        saved = SessionManager(case.loader).get_session(case.session.name)
        assert saved.workspace_name == "workspace-1"
        assert saved.working_directory == "project-a"
        assert saved.active_conversation.project_path == str(case.project)
        assert saved.active_conversation.branch == ""
        assert saved.active_conversation.agent_launch_started is False
        assert saved.active_conversation.ai_agent_session_id == PENDING_CAPTURE_PLACEHOLDER
        assert not saved.conversations["project-a"].archived_sessions
        assert work.read_text() == "uncommitted user work"
        assert GitUtils.get_current_branch(case.project) == "main"
        checkout.assert_not_called()
        create_branch.assert_not_called()
        case.query.assert_not_called()
        case.create.assert_not_called()
        case.spawn.assert_not_called()

    # Simulate the user preserving/clearing the dirty worktree before trying again.
    work.rename(case.project / "saved-work.txt")
    monkeypatch.setattr(GitUtils, "has_uncommitted_changes", lambda *args: False)
    monkeypatch.setattr("devflow.cli.commands.new_command._handle_branch_creation", case.branch)
    result = runner.invoke(cli, ["open", case.session.name])
    assert result.exit_code == 0, result.output
    case.branch.assert_called_once()
    case.create.assert_called_once()
    case.spawn.assert_called_once()
    case.selection.assert_called_once()
    saved = SessionManager(case.loader).get_session(case.session.name)
    assert saved.active_conversation.branch == "feature-a"
    assert saved.active_conversation.ai_agent_session_id == "ses_created"
    assert saved.active_conversation.agent_launch_started is True
    assert (case.project / "saved-work.txt").read_text() == "uncommitted user work"


@pytest.mark.parametrize(
    "refusal", ["selection", "concurrency", "checkout", "sync", "conflicts", "launch", "context"]
)
def test_prelaunch_refusal_is_retryable(first_open, monkeypatch, refusal):
    case = first_open
    with monkeypatch.context() as blocked:
        if refusal == "selection":
            blocked.setattr(case.selection, "return_value", ([], False))
        elif refusal == "concurrency":
            blocked.setattr(
                open_command.check_concurrent_session,
                "return_value",
                SimpleNamespace(safe_to_proceed=False, clone_path=None),
            )
        elif refusal == "conflicts":
            blocked.setattr(GitUtils, "has_merge_conflicts", lambda *args: True)
            blocked.setattr(open_command, "_display_conflict_resolution_help", Mock())
        else:
            hook = {
                "checkout": "_handle_branch_checkout",
                "sync": "_check_and_sync_with_base_branch",
                "launch": "should_launch_claude_code",
                "context": "_validate_context_files",
            }[refusal]
            blocked.setattr(open_command, hook, Mock(return_value=False))
        result = CliRunner().invoke(cli, ["open", case.session.name])
    assert result.exit_code == 0, result.output
    case.create.assert_not_called()
    case.spawn.assert_not_called()
    case.query.assert_not_called()
    saved = SessionManager(case.loader).get_session(case.session.name)
    if refusal == "selection":
        assert saved.active_conversation is None
    else:
        assert saved.active_conversation.agent_launch_started is False
    retry = CliRunner().invoke(cli, ["open", case.session.name])
    assert retry.exit_code == 0, retry.output
    case.create.assert_called_once()
    case.spawn.assert_called_once()


@pytest.mark.parametrize("launch_started", [None, True])
@pytest.mark.parametrize("json_mode", [False, True])
@pytest.mark.parametrize("saved_id", [PENDING_CAPTURE_PLACEHOLDER, ""])
def test_legacy_or_attempted_pending_without_branch_still_refuses(
    first_open, launch_started, json_mode, saved_id
):
    case = first_open
    manager = SessionManager(case.loader)
    session = manager.get_session(case.session.name)
    conv = session.add_conversation("project-a", saved_id, str(case.project), branch="")
    conv.agent_launch_started = launch_started
    session.working_directory = "project-a"
    manager.update_session(session)
    original = SessionManager(case.loader).get_session(session.name).model_dump()
    result = CliRunner().invoke(cli, ["open", session.name, *(["--json"] if json_mode else [])])
    assert result.exit_code == 1, result.output
    output = json.loads(result.output)["error"]["message"] if json_mode else result.output
    assert "--new-conversation" in output
    assert "even without a saved branch" in " ".join(output.split())
    assert SessionManager(case.loader).get_session(session.name).model_dump() == original
    case.branch.assert_not_called()
    case.create.assert_not_called()
    case.spawn.assert_not_called()
    case.query.assert_not_called()


@pytest.mark.parametrize("old_id", [PENDING_CAPTURE_PLACEHOLDER, "ses_existing"])
@pytest.mark.parametrize("branch", [None, ""])
def test_explicit_start_over_without_branch_can_cancel_then_retry(first_open, old_id, branch):
    case = first_open
    manager = SessionManager(case.loader)
    session = manager.get_session(case.session.name)
    old = session.add_conversation("project-a", old_id, str(case.project), branch=branch)
    old.message_count = 7
    old.summary = "Previous conversation"
    session.working_directory = "project-a"
    manager.update_session(session)
    original = old.model_dump(exclude={"archived"})
    case.branch.return_value = False
    result = CliRunner().invoke(cli, ["open", session.name, "--new-conversation"])
    assert result.exit_code == 0, result.output
    assert "Session open cancelled" in result.output
    saved = SessionManager(case.loader).get_session(session.name)
    assert saved.active_conversation.agent_launch_started is False
    archived = saved.conversations["project-a"].archived_sessions
    assert len(archived) == 1
    assert archived[0].archived is True
    assert archived[0].model_dump(exclude={"archived"}) == original
    case.create.assert_not_called()
    case.spawn.assert_not_called()
    case.branch.return_value = ("feature-a", "main")
    retry = CliRunner().invoke(cli, ["open", session.name])
    assert retry.exit_code == 0, retry.output
    saved = SessionManager(case.loader).get_session(session.name)
    assert saved.active_conversation.ai_agent_session_id == "ses_created"
    assert len(saved.conversations["project-a"].archived_sessions) == 1


@pytest.mark.parametrize("change", ["tags", "identity", "path", "branch"])
def test_launch_transition_merges_latest_metadata_and_rejects_replacement(first_open, change):
    case = first_open

    def concurrent_update(*args, **kwargs):
        manager = SessionManager(case.loader)
        session = manager.get_session(case.session.name)
        session.tags = ["user-update"]
        if change == "identity":
            session.active_conversation.ai_agent_session_id = "ses_other"
        elif change == "path":
            session.active_conversation.project_path = str(case.workspace / "project-b")
        elif change == "branch":
            session.active_conversation.branch = "other-branch"
        manager.update_session(session)
        return set()

    case.query.side_effect = concurrent_update
    result = CliRunner().invoke(cli, ["open", case.session.name])
    assert result.exit_code == 0, result.output
    saved = SessionManager(case.loader).get_session(case.session.name)
    assert saved.tags == ["user-update"]
    if change != "tags":
        case.create.assert_not_called()
        case.spawn.assert_not_called()
        if change == "identity":
            assert saved.active_conversation.ai_agent_session_id == "ses_other"
        elif change == "path":
            assert saved.active_conversation.project_path == str(case.workspace / "project-b")
        else:
            assert saved.active_conversation.branch == "other-branch"
        assert "Conversation changed during setup" in result.output
    else:
        case.create.assert_called_once()
        case.spawn.assert_called_once()
        assert saved.active_conversation.agent_launch_started is True


def test_unresolved_launch_attempt_cannot_reuse_never_launched_proof(first_open, monkeypatch):
    case = first_open

    def interrupted_launch(**kwargs):
        kwargs["on_launch"]()
        raise RuntimeError("interrupted")

    monkeypatch.setattr(case.agent, "launch_with_prompt", Mock(side_effect=interrupted_launch))
    monkeypatch.setattr("devflow.agent.factory.capture_agent_session_id", Mock(return_value=False))
    CliRunner().invoke(cli, ["open", case.session.name])
    saved = SessionManager(case.loader).get_session(case.session.name)
    assert saved.active_conversation.agent_launch_started is True
    assert saved.active_conversation.ai_agent_session_id == PENDING_CAPTURE_PLACEHOLDER
    retry = CliRunner().invoke(cli, ["open", case.session.name, "--json"])
    assert retry.exit_code == 1, retry.output
    assert json.loads(retry.output)["error"]["code"] == "AGENT_SESSION_UNVERIFIED"
    case.agent.launch_with_prompt.assert_called_once()
    case.create.assert_not_called()
    case.spawn.assert_not_called()


@pytest.mark.parametrize("failure", ["tool", "version", "model"])
def test_adapter_preflight_failure_remains_retryable(first_open, monkeypatch, failure):
    case = first_open
    with monkeypatch.context() as failed:
        if failure == "tool":
            failed.setattr(
                "devflow.agent.opencode_agent.require_tool",
                Mock(side_effect=RuntimeError("missing tool")),
            )
        elif failure == "version":
            failed.setattr(
                case.agent,
                "get_opencode_version",
                Mock(side_effect=RuntimeError("unknown version")),
            )
        else:
            failed.setattr(
                "devflow.agent.model_config.get_agent_model_config",
                Mock(side_effect=ValueError("invalid model")),
            )
        CliRunner().invoke(cli, ["open", case.session.name])
    saved = SessionManager(case.loader).get_session(case.session.name)
    assert saved.active_conversation.agent_launch_started is False
    case.create.assert_not_called()
    case.spawn.assert_not_called()
    retry = CliRunner().invoke(cli, ["open", case.session.name])
    assert retry.exit_code == 0, retry.output
    case.create.assert_called_once()
    case.spawn.assert_called_once()


@pytest.mark.parametrize("launch_started", [None, False, True])
def test_launch_provenance_round_trips_without_inference(launch_started):
    legacy = {"ai_agent_session_id": PENDING_CAPTURE_PLACEHOLDER, "branch": "", "message_count": 0}
    assert ConversationContext.model_validate(legacy).agent_launch_started is None
    conv = ConversationContext(**legacy, agent_launch_started=launch_started)
    assert (
        ConversationContext.model_validate_json(conv.model_dump_json()).agent_launch_started
        is launch_started
    )


@pytest.mark.parametrize("callback_fails", [False, True])
def test_launch_hook_runs_before_adapter_and_failure_stops_it(callback_fails):
    agent = Mock()
    conv = SimpleNamespace(ai_agent_session_id="initial-id", temp_directory=None)
    events = []

    def before_launch():
        events.append("persist")
        if callback_fails:
            raise OSError("cannot persist launch state")

    agent.launch_with_prompt.side_effect = lambda **kwargs: events.append("launch") or Mock(
        returncode=0
    )
    if callback_fails:
        with pytest.raises(OSError, match="cannot persist"):
            launch_and_capture(
                agent,
                "claude",
                "/project",
                conv,
                initial_prompt="Read",
                session_id=conv.ai_agent_session_id,
                on_launch=before_launch,
            )
        agent.launch_with_prompt.assert_not_called()
        agent.wait_for_exit.assert_not_called()
        assert events == ["persist"]
    else:
        launch_and_capture(
            agent,
            "claude",
            "/project",
            conv,
            initial_prompt="Read",
            session_id=conv.ai_agent_session_id,
            on_launch=before_launch,
        )
        assert events == ["persist", "launch"]


@pytest.mark.parametrize("source", ["path", "cwd", "workspace"])
def test_new_repository_setup_preserves_existing_native_history(first_open, monkeypatch, source):
    case = first_open
    manager = SessionManager(case.loader)
    session = manager.get_session(case.session.name)
    other_project = case.workspace / "project-b"
    other_project.mkdir()
    old = session.add_conversation("project-b", "ses_existing", str(other_project), branch="other")
    old.message_count = 12
    session.working_directory = "project-b"
    manager.update_session(session)
    original = old.model_dump()
    if source == "path":
        success = open_command._create_conversation_for_path(
            session, "project-a", case.project, manager, case.loader
        )
    elif source == "cwd":
        success = open_command._create_conversation_for_current_directory(
            session, "project-a", case.project, manager, case.loader
        )
    else:
        monkeypatch.setattr("rich.prompt.IntPrompt.ask", lambda *args, **kwargs: 1)
        success = open_command._create_conversation_from_workspace_selection(
            session, manager, case.loader
        )
    assert success
    saved = SessionManager(case.loader).get_session(session.name)
    assert saved.get_conversation("project-b").model_dump() == original
    assert saved.active_conversation.ai_agent_session_id == PENDING_CAPTURE_PLACEHOLDER
    assert saved.active_conversation.agent_launch_started is False
    case.branch.return_value = False
    cancelled = CliRunner().invoke(cli, ["open", session.name, "--path", str(case.project)])
    assert cancelled.exit_code == 0, cancelled.output
    assert "Session open cancelled" in cancelled.output
    saved = SessionManager(case.loader).get_session(session.name)
    assert saved.get_conversation("project-b").model_dump() == original
    case.create.assert_not_called()
    case.spawn.assert_not_called()


def test_multi_project_setup_launch_decline_then_retry(first_open, monkeypatch):
    case = first_open
    other_project = case.workspace / "project-b"
    other_project.mkdir()
    case.selection.return_value = ([str(case.project), str(other_project)], True)
    with monkeypatch.context() as declined:
        declined.setattr(open_command, "should_launch_claude_code", Mock(return_value=False))
        first = CliRunner().invoke(
            cli, ["open", case.session.name, "--create-branch", "--source-branch", "main"]
        )
    assert first.exit_code == 0, first.output
    saved = SessionManager(case.loader).get_session(case.session.name)
    assert saved.active_conversation.is_multi_project
    assert saved.active_conversation.agent_launch_started is False
    assert case.branch.call_count == 2
    case.create.assert_not_called()
    case.spawn.assert_not_called()
    retry = CliRunner().invoke(cli, ["open", case.session.name])
    assert retry.exit_code == 0, retry.output
    case.create.assert_called_once()
    case.spawn.assert_called_once()


def test_clone_preflight_failure_does_not_consume_launch_proof(tmp_path, monkeypatch):
    agent = Mock()
    clone = tmp_path / "missing-clone"
    conv = SimpleNamespace(ai_agent_session_id="initial-id", temp_directory=str(clone))
    callback = Mock()
    monkeypatch.setattr("devflow.utils.clone_cache.CloneCache.use", Mock())
    monkeypatch.setattr(
        "devflow.agent.factory.temporary_directory_lock", lambda *args: nullcontext()
    )
    with pytest.raises(FileNotFoundError, match="Cached clone disappeared"):
        launch_and_capture(
            agent,
            "claude",
            str(clone),
            conv,
            initial_prompt="Read",
            session_id=conv.ai_agent_session_id,
            on_launch=callback,
        )
    callback.assert_not_called()
    agent.launch_with_prompt.assert_not_called()


def test_never_launched_marker_cannot_replace_known_native_id(first_open):
    case = first_open
    manager = SessionManager(case.loader)
    session = manager.get_session(case.session.name)
    conv = session.add_conversation("project-a", "ses_existing", str(case.project), branch="main")
    conv.agent_launch_started = False
    session.working_directory = "project-a"
    manager.update_session(session)
    result = CliRunner().invoke(cli, ["open", session.name, "--json"])
    assert result.exit_code == 1, result.output
    assert json.loads(result.output)["error"]["code"] == "AGENT_SESSION_UNVERIFIED"
    saved = SessionManager(case.loader).get_session(session.name)
    assert saved.active_conversation.ai_agent_session_id == "ses_existing"
    case.query.assert_called_once()
    case.create.assert_not_called()
    case.spawn.assert_not_called()


@pytest.mark.parametrize("mode", ["titled", "untitled", "headless"])
@pytest.mark.parametrize("persist_fails", [False, True])
def test_adapter_launch_hook_precedes_all_native_creation(
    first_open, monkeypatch, mode, persist_fails
):
    case = first_open
    events = []

    def persist():
        events.append("persist")
        if persist_fails:
            raise OSError("cannot persist")

    def create(*args):
        assert events == ["persist"]
        events.append("create")
        return "ses_created"

    monkeypatch.setattr(case.agent, "_create_session_with_title", create)
    monkeypatch.setattr(
        "devflow.agent.opencode_agent.subprocess.Popen",
        lambda *args, **kwargs: events.append("spawn") or Mock(returncode=0),
    )
    kwargs = {
        "project_path": str(case.project),
        "initial_prompt": "Read",
        "session_id": PENDING_CAPTURE_PLACEHOLDER,
        "display_name": "session-a" if mode == "titled" else None,
        "headless": mode == "headless",
        "on_launch": persist,
        "on_session_id": lambda sid: events.append("identity"),
    }
    if persist_fails:
        with pytest.raises(OSError, match="cannot persist"):
            case.agent.launch_with_prompt(**kwargs)
        assert events == ["persist"]
    else:
        case.agent.launch_with_prompt(**kwargs)
        assert events == (
            ["persist", "create", "identity", "spawn"] if mode == "titled" else ["persist", "spawn"]
        )


def test_created_native_identity_is_saved_even_if_later_validation_refuses(first_open, monkeypatch):
    case = first_open
    events = []
    monkeypatch.setattr(case.agent, "_create_session_with_title", Mock(return_value="ses_created"))
    with pytest.raises(OpenCodeCompatibilityError):
        case.agent.launch_with_prompt(
            project_path=str(case.project),
            initial_prompt="Read",
            session_id=PENDING_CAPTURE_PLACEHOLDER,
            display_name="session-a",
            model_override="provider/model-a",
            auto_approve=True,
            on_launch=lambda: events.append("persist"),
            on_session_id=lambda sid: events.append(sid),
        )
    assert events == ["persist", "ses_created"]
    case.spawn.assert_not_called()
