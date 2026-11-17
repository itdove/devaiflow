"""Focused tests for worktree selection during daf open."""

from types import SimpleNamespace
from unittest.mock import Mock

from devflow.cli.commands import open_command


def _session_and_conversation(*, launch_started=False, session_id="new-id"):
    conversation = SimpleNamespace(
        worktree_path=None,
        project_path="/workspace/project-a",
        original_project_path=None,
        ai_agent_session_id=session_id,
        agent_launch_started=launch_started,
        branch=None,
        base_branch="main",
        remote_url=None,
        is_multi_project=False,
        temp_directory=None,
    )
    session = SimpleNamespace(
        name="TEST-42",
        issue_key="TEST-42",
        goal="Implement a sample change",
        session_type="development",
    )
    return session, conversation


def test_open_worktree_prompt_defaults_to_existing_checkout_without_conflict(
    monkeypatch,
):
    session, conversation = _session_and_conversation(launch_started=False)
    manager = Mock()
    create = Mock()
    ask = Mock(return_value=False)
    monkeypatch.setattr(open_command, "Confirm", SimpleNamespace(ask=ask))
    monkeypatch.setattr(open_command, "is_non_interactive", lambda: False)
    monkeypatch.setattr(
        "devflow.utils.session_worktree.create_session_worktree", create
    )

    assert open_command._prepare_session_worktree(
        session,
        conversation,
        manager,
        None,
        requested=None,
        first_launch=True,
        identity_preexisting=True,
        output_json=False,
    )

    ask.assert_called_once_with(
        "Use a managed Git worktree instead of the existing checkout? "
        "Uncommitted files in the source checkout are not copied",
        default=False,
    )
    create.assert_not_called()
    manager.update_session.assert_not_called()


def test_open_worktree_prompt_persists_source_and_worktree_paths(monkeypatch):
    session, conversation = _session_and_conversation(launch_started=False)
    manager = Mock()
    monkeypatch.setattr(open_command, "is_non_interactive", lambda: False)
    monkeypatch.setattr(open_command.Confirm, "ask", lambda *args, **kwargs: True)
    monkeypatch.setattr(
        open_command, "get_issue_tracker_backend", lambda *_args: "github"
    )
    monkeypatch.setattr(
        "devflow.utils.session_worktree.worktree_source_fingerprint",
        lambda _source: "fingerprint",
    )
    monkeypatch.setattr(
        "devflow.utils.session_worktree.create_session_worktree",
        lambda *_args, **_kwargs: (
            "/cache/daf-session-a/project-a",
            "feature-a",
            "main",
        ),
    )

    assert open_command._prepare_session_worktree(
        session,
        conversation,
        manager,
        None,
        requested=None,
        first_launch=True,
        identity_preexisting=True,
        output_json=False,
    )

    assert conversation.project_path == "/cache/daf-session-a/project-a"
    assert conversation.worktree_path == conversation.project_path
    assert conversation.original_project_path == "/workspace/project-a"
    assert conversation.branch == "feature-a"
    assert conversation.base_branch == "main"
    manager.update_session.assert_called_once_with(session)


def test_open_worktree_refuses_to_move_a_launched_conversation(monkeypatch):
    session, conversation = _session_and_conversation(launch_started=True)
    manager = Mock()
    create = Mock()
    monkeypatch.setattr(open_command, "console", Mock())
    monkeypatch.setattr(
        "devflow.utils.session_worktree.create_session_worktree", create
    )

    assert not open_command._prepare_session_worktree(
        session,
        conversation,
        manager,
        None,
        requested=True,
        first_launch=True,
        identity_preexisting=True,
        output_json=False,
    )

    create.assert_not_called()
    manager.update_session.assert_not_called()


def test_open_worktree_refusal_has_structured_json_error(monkeypatch):
    session, conversation = _session_and_conversation(launch_started=True)
    manager = Mock()
    emit_json = Mock()
    monkeypatch.setattr(open_command, "emit_json", emit_json)

    assert not open_command._prepare_session_worktree(
        session,
        conversation,
        manager,
        None,
        requested=True,
        first_launch=True,
        identity_preexisting=True,
        output_json=True,
    )

    emit_json.assert_called_once()
    assert emit_json.call_args.kwargs["error"]["code"] == "WORKTREE_UNAVAILABLE"


def test_no_worktree_choice_keeps_the_existing_checkout_unchanged(monkeypatch):
    session, conversation = _session_and_conversation(launch_started=False)
    manager = Mock()
    create = Mock()
    monkeypatch.setattr(
        "devflow.utils.session_worktree.create_session_worktree", create
    )

    assert open_command._prepare_session_worktree(
        session,
        conversation,
        manager,
        None,
        requested=False,
        first_launch=True,
        identity_preexisting=True,
        output_json=False,
    )

    assert conversation.project_path == "/workspace/project-a"
    assert conversation.worktree_path is None
    create.assert_not_called()
    manager.update_session.assert_not_called()


def test_no_worktree_cannot_rehome_a_saved_worktree_conversation(monkeypatch):
    session, conversation = _session_and_conversation(launch_started=True)
    conversation.worktree_path = "/cache/daf-session-a/project-a"
    manager = Mock()
    console = Mock()
    monkeypatch.setattr(open_command, "console", console)

    assert not open_command._prepare_session_worktree(
        session,
        conversation,
        manager,
        None,
        requested=False,
        first_launch=False,
        identity_preexisting=True,
        output_json=False,
    )

    console.print.assert_called_once()
    manager.update_session.assert_not_called()


def test_open_worktree_prompt_is_skipped_for_json_output(monkeypatch):
    session, conversation = _session_and_conversation(launch_started=False)
    ask = Mock()
    monkeypatch.setattr(open_command, "Confirm", SimpleNamespace(ask=ask))

    assert open_command._prepare_session_worktree(
        session,
        conversation,
        Mock(),
        None,
        requested=None,
        first_launch=True,
        identity_preexisting=True,
        output_json=True,
    )

    ask.assert_not_called()


def test_open_worktree_prompt_is_skipped_when_non_interactive(monkeypatch):
    session, conversation = _session_and_conversation(launch_started=False)
    ask = Mock()
    monkeypatch.setattr(open_command, "Confirm", SimpleNamespace(ask=ask))
    monkeypatch.setattr(open_command, "is_non_interactive", lambda: True)

    assert open_command._prepare_session_worktree(
        session,
        conversation,
        Mock(),
        None,
        requested=None,
        first_launch=True,
        identity_preexisting=True,
        output_json=False,
    )

    ask.assert_not_called()


def test_explicit_worktree_override_skips_prompt(monkeypatch):
    session, conversation = _session_and_conversation(launch_started=False)
    ask = Mock()
    monkeypatch.setattr(open_command, "Confirm", SimpleNamespace(ask=ask))
    monkeypatch.setattr(
        "devflow.utils.session_worktree.worktree_source_fingerprint",
        lambda _source: "fingerprint",
    )
    monkeypatch.setattr(
        "devflow.utils.session_worktree.create_session_worktree",
        lambda *_args, **_kwargs: (
            "/cache/daf-session-a/project-a",
            "feature-a",
            "main",
        ),
    )
    monkeypatch.setattr(
        open_command, "get_issue_tracker_backend", lambda *_args: "github"
    )

    assert open_command._prepare_session_worktree(
        session,
        conversation,
        Mock(),
        None,
        requested=True,
        first_launch=True,
        identity_preexisting=True,
        output_json=False,
    )

    ask.assert_not_called()


def test_open_worktree_prompt_is_skipped_for_ineligible_sessions(monkeypatch):
    ask = Mock()
    monkeypatch.setattr(open_command, "Confirm", SimpleNamespace(ask=ask))
    monkeypatch.setattr(open_command, "is_non_interactive", lambda: False)

    for session_type, multi_project, temp_directory, first_launch in (
        ("development", False, None, False),
        ("ticket_creation", False, None, True),
        ("investigation", False, None, True),
        ("development", True, None, True),
        ("development", False, "/tmp/session-clone", True),
    ):
        session, conversation = _session_and_conversation(launch_started=False)
        session.session_type = session_type
        conversation.is_multi_project = multi_project
        conversation.temp_directory = temp_directory

        assert open_command._prepare_session_worktree(
            session,
            conversation,
            Mock(),
            None,
            requested=None,
            first_launch=first_launch,
            identity_preexisting=True,
            output_json=False,
        )

    ask.assert_not_called()
