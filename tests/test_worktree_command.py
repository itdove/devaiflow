"""Tests for cleanup-only worktree management."""

import json
from pathlib import Path
from unittest.mock import Mock

from click.testing import CliRunner

from devflow.cli.commands.worktree_command import worktree
from devflow.config.models import Conversation, ConversationContext, Session
from devflow.utils.session_worktree import (
    SessionWorktreeCleanupError,
    SessionWorktreeError,
    WorktreeChanges,
)

ISSUE_KEY = "owner/project-a#42"


def _session(
    worktree_path: Path, source_path: Path, *, status: str = "complete"
) -> Session:
    context = ConversationContext(
        ai_agent_session_id="pending-capture",
        project_path=str(worktree_path),
        branch="feature-a",
        original_project_path=str(source_path),
        worktree_path=str(worktree_path),
        worktree_source_fingerprint="saved-source-fingerprint",
    )
    return Session(
        name="session-a",
        goal="Test worktree cleanup",
        status=status,
        working_directory="project-a",
        issue_key=ISSUE_KEY,
        issue_tracker="github",
        conversations={
            "project-a": Conversation(active_session=context),
        },
    )


def _setup_command(monkeypatch, session, ticket=None, tracker_error=None):
    from devflow.cli.commands import worktree_command

    config = Mock()
    loader = Mock()
    loader.load_config.return_value = config
    manager = Mock()
    manager.index.sessions = {session.name: session}
    tracker = Mock()
    if tracker_error:
        tracker.get_ticket.side_effect = tracker_error
    else:
        tracker.get_ticket.return_value = ticket or {"status": "closed"}
    factory = Mock(return_value=tracker)
    monkeypatch.setattr(worktree_command, "ConfigLoader", lambda: loader)
    monkeypatch.setattr(worktree_command, "SessionManager", lambda _loader: manager)
    monkeypatch.setattr(worktree_command, "create_issue_tracker_client", factory)
    return config, manager, tracker, factory


def test_clean_worktree_requires_closed_issue_and_uses_recorded_identity(
    monkeypatch, tmp_path
):
    from devflow.cli.commands import worktree_command

    path = tmp_path / "worktree"
    source = tmp_path / "source"
    session = _session(path, source)
    _, _, tracker, factory = _setup_command(monkeypatch, session)
    cleanup = Mock()
    monkeypatch.setattr(worktree_command, "cleanup_session_worktree", cleanup)

    result = CliRunner().invoke(worktree, ["clean", ISSUE_KEY])

    assert result.exit_code == 0, result.output
    factory.assert_called_once_with(backend="github")
    tracker.get_ticket.assert_called_once_with(ISSUE_KEY)
    cleanup.assert_called_once_with(
        path,
        source,
        expected_source_fingerprint="saved-source-fingerprint",
        expected_branch="feature-a",
        config=worktree_command.ConfigLoader().load_config.return_value,
    )


def test_clean_worktree_coalesces_archived_and_active_conversations_for_one_owner(
    monkeypatch, tmp_path
):
    from devflow.cli.commands import worktree_command

    path = tmp_path / "worktree"
    source = tmp_path / "source"
    session = _session(path, source)
    session.conversations["project-a"].archived_sessions.append(
        session.active_conversation.model_copy(deep=True)
    )
    _setup_command(monkeypatch, session)
    cleanup = Mock()
    monkeypatch.setattr(worktree_command, "cleanup_session_worktree", cleanup)

    result = CliRunner().invoke(worktree, ["clean", ISSUE_KEY])

    assert result.exit_code == 0, result.output
    cleanup.assert_called_once()


def test_clean_worktree_refuses_a_worktree_claimed_by_different_sessions(
    monkeypatch, tmp_path
):
    from devflow.cli.commands import worktree_command

    path = tmp_path / "worktree"
    source = tmp_path / "source"
    session = _session(path, source)
    _, manager, tracker, _ = _setup_command(monkeypatch, session)
    other_session = _session(path, source)
    other_session.name = "session-b"
    manager.index.sessions[other_session.name] = other_session
    cleanup = Mock()
    monkeypatch.setattr(worktree_command, "cleanup_session_worktree", cleanup)

    result = CliRunner().invoke(worktree, ["clean", ISSUE_KEY])

    assert result.exit_code == 1
    assert "Multiple session conversations claim the same worktree" in result.output
    tracker.get_ticket.assert_not_called()
    cleanup.assert_not_called()


def test_clean_worktree_refuses_open_or_unverifiable_issues(monkeypatch, tmp_path):
    from devflow.cli.commands import worktree_command

    path = tmp_path / "worktree"
    source = tmp_path / "source"
    session = _session(path, source)
    _setup_command(monkeypatch, session, ticket={"status": "open"})
    cleanup = Mock()
    monkeypatch.setattr(worktree_command, "cleanup_session_worktree", cleanup)

    result = CliRunner().invoke(worktree, ["clean", ISSUE_KEY])

    assert result.exit_code == 1
    assert "not confirmed closed" in result.output
    cleanup.assert_not_called()


def test_clean_worktree_refuses_tracker_lookup_errors(monkeypatch, tmp_path):
    from devflow.cli.commands import worktree_command

    session = _session(tmp_path / "worktree", tmp_path / "source")
    _setup_command(
        monkeypatch, session, tracker_error=RuntimeError("tracker unavailable")
    )
    cleanup = Mock()
    monkeypatch.setattr(worktree_command, "cleanup_session_worktree", cleanup)

    result = CliRunner().invoke(worktree, ["clean", ISSUE_KEY])

    assert result.exit_code == 1
    assert "tracker unavailable" in result.output
    cleanup.assert_not_called()


def test_dirty_worktree_requires_separate_confirmation(monkeypatch, tmp_path):
    from devflow.cli.commands import worktree_command

    path = tmp_path / "worktree"
    source = tmp_path / "source"
    session = _session(path, source)
    _setup_command(monkeypatch, session)
    changes = WorktreeChanges(
        path=path,
        tracked=1,
        untracked=2,
        ignored=1,
        status_output=" M tracked.txt\n?? untracked.txt\n!! generated/\n",
    )
    cleanup = Mock(
        side_effect=[
            SessionWorktreeCleanupError("dirty", changes=changes),
            None,
        ]
    )
    confirm = Mock(return_value=True)
    monkeypatch.setattr(worktree_command, "cleanup_session_worktree", cleanup)
    monkeypatch.setattr(worktree_command.Confirm, "ask", confirm)
    monkeypatch.setattr(worktree_command, "is_non_interactive", lambda: False)

    result = CliRunner().invoke(worktree, ["clean", ISSUE_KEY, "--delete-local-files"])

    assert result.exit_code == 0, result.output
    assert "tracked changes: 1, untracked files: 2, ignored paths: 1" in result.output
    confirm.assert_called_once()
    assert cleanup.call_count == 2
    assert cleanup.call_args.kwargs["delete_local_files"] is True
    assert cleanup.call_args.kwargs["expected_changes"] is changes


def test_noninteractive_dirty_cleanup_never_deletes_files(monkeypatch, tmp_path):
    from devflow.cli.commands import worktree_command

    path = tmp_path / "worktree"
    session = _session(path, tmp_path / "source")
    _setup_command(monkeypatch, session)
    changes = WorktreeChanges(
        path=path,
        tracked=0,
        untracked=1,
        ignored=0,
        status_output="?? local.txt\n",
    )
    cleanup = Mock(side_effect=SessionWorktreeCleanupError("dirty", changes=changes))
    confirm = Mock()
    monkeypatch.setattr(worktree_command, "cleanup_session_worktree", cleanup)
    monkeypatch.setattr(worktree_command.Confirm, "ask", confirm)
    monkeypatch.setattr(worktree_command, "is_non_interactive", lambda: True)

    result = CliRunner().invoke(worktree, ["clean", ISSUE_KEY, "--delete-local-files"])

    assert result.exit_code == 1
    assert "interactive confirmation" in result.output
    assert cleanup.call_count == 1
    confirm.assert_not_called()


def test_clean_worktree_rejects_invalid_session_worktree_association(
    monkeypatch, tmp_path
):
    from devflow.cli.commands import worktree_command

    session = _session(tmp_path / "worktree", tmp_path / "source")
    session.active_conversation.project_path = str(tmp_path / "different-project")
    _, _, tracker, _ = _setup_command(monkeypatch, session)
    cleanup = Mock()
    monkeypatch.setattr(worktree_command, "cleanup_session_worktree", cleanup)

    result = CliRunner().invoke(worktree, ["clean", ISSUE_KEY])

    assert result.exit_code == 1
    assert "does not record the worktree as its project path" in result.output
    tracker.get_ticket.assert_not_called()
    cleanup.assert_not_called()


def test_clean_worktree_reports_cleanup_identity_refusal_without_traceback(
    monkeypatch, tmp_path
):
    from devflow.cli.commands import worktree_command

    session = _session(tmp_path / "worktree", tmp_path / "source")
    _setup_command(monkeypatch, session)
    monkeypatch.setattr(
        worktree_command,
        "cleanup_session_worktree",
        Mock(side_effect=SessionWorktreeError("managed worktree path is invalid")),
    )

    result = CliRunner().invoke(worktree, ["clean", ISSUE_KEY])

    assert result.exit_code == 1
    assert "managed worktree path is invalid" in " ".join(result.output.split())
    assert "Traceback" not in result.output


def test_json_dirty_cleanup_has_no_mixed_console_output(monkeypatch, tmp_path):
    from devflow.cli.commands import worktree_command

    path = tmp_path / "worktree"
    session = _session(path, tmp_path / "source")
    _setup_command(monkeypatch, session)
    changes = WorktreeChanges(
        path=path,
        tracked=1,
        untracked=2,
        ignored=1,
        status_output=" M tracked.txt\n?? untracked.txt\n!! generated/\n",
    )
    cleanup = Mock(side_effect=SessionWorktreeCleanupError("dirty", changes=changes))
    confirm = Mock()
    monkeypatch.setattr(worktree_command, "cleanup_session_worktree", cleanup)
    monkeypatch.setattr(worktree_command.Confirm, "ask", confirm)

    result = CliRunner().invoke(
        worktree, ["clean", ISSUE_KEY, "--delete-local-files", "--json"]
    )

    payload = json.loads(result.output)
    assert result.exit_code == 1
    assert payload["success"] is False
    reason = payload["error"]["worktrees"][0]["reason"]
    assert "tracked changes: 1, untracked files: 2, ignored paths: 1" in reason
    assert confirm.call_count == 0
    assert cleanup.call_count == 1
