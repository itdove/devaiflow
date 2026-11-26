"""Tests for GitLab issue closure decisions during completion."""

from unittest.mock import Mock

import pytest

from devflow.config.models import Config, GitLabConfig, Session
from devflow.gitlab.transitions import transition_on_complete


@pytest.fixture
def session():
    return Session(
        name="session-a",
        goal="Test completion",
        issue_key="group/project-a#42",
    )


@pytest.fixture
def config():
    result = Mock(spec=Config)
    result.gitlab = Mock(spec=GitLabConfig)
    result.gitlab.auto_close_on_complete = False
    return result


@pytest.fixture
def client():
    result = Mock()
    result.get_ticket.return_value = {"status": "open"}
    return result


@pytest.mark.parametrize("approved", [False, True])
def test_completion_callback_tracks_user_approval(
    monkeypatch, session, config, client, approved
):
    callback = Mock()
    monkeypatch.setattr(
        "devflow.gitlab.transitions.Confirm.ask", lambda *_args, **_kwargs: approved
    )

    transition_on_complete(
        session,
        config,
        client=client,
        on_close_approved=callback,
    )

    if approved:
        callback.assert_called_once_with()
        client.transition_ticket.assert_called_once_with(session.issue_key, "closed")
    else:
        callback.assert_not_called()
        client.transition_ticket.assert_not_called()


def test_auto_close_configuration_is_explicit_approval(session, config, client):
    config.gitlab.auto_close_on_complete = True
    callback = Mock()

    transition_on_complete(
        session,
        config,
        client=client,
        on_close_approved=callback,
    )

    callback.assert_called_once_with()
    client.transition_ticket.assert_called_once_with(session.issue_key, "closed")


@pytest.mark.parametrize("status", ["closed", "unknown", None])
def test_existing_closed_or_unknown_issue_never_counts_as_new_approval(
    monkeypatch, session, config, client, status
):
    client.get_ticket.return_value = {"status": status}
    confirm = Mock(side_effect=AssertionError("must not prompt for non-open state"))
    monkeypatch.setattr("devflow.gitlab.transitions.Confirm.ask", confirm)
    callback = Mock()

    transition_on_complete(
        session,
        config,
        client=client,
        on_close_approved=callback,
    )

    callback.assert_not_called()
    client.transition_ticket.assert_not_called()
    confirm.assert_not_called()


def test_no_issue_update_skips_lookup_and_approval(session, config, client):
    callback = Mock()

    transition_on_complete(
        session,
        config,
        client=client,
        no_issue_update=True,
        on_close_approved=callback,
    )

    client.get_ticket.assert_not_called()
    callback.assert_not_called()


def test_status_selection_updates_only_status_label(
    monkeypatch, session, config, client
):
    client.get_ticket.return_value = {
        "status": "open",
        "labels": ["team-a", "status: in-progress"],
    }
    config.gitlab.add_status_labels = True
    config.gitlab.completion_label = "status: in-review"
    monkeypatch.setattr(
        "devflow.gitlab.transitions.Prompt.ask", lambda *_args, **_kwargs: "4"
    )

    transition_on_complete(session, config, client=client)

    client.update_issue.assert_called_once_with(
        session.issue_key,
        {"labels": ["team-a", "status: in-review"]},
    )
    client.transition_ticket.assert_not_called()


def test_status_selection_skip_preserves_labels(monkeypatch, session, config, client):
    client.get_ticket.return_value = {
        "status": "open",
        "labels": ["team-a", "status: in-progress"],
    }
    config.gitlab.add_status_labels = True
    monkeypatch.setattr(
        "devflow.gitlab.transitions.Prompt.ask", lambda *_args, **_kwargs: "1"
    )

    transition_on_complete(session, config, client=client)

    client.update_issue.assert_not_called()
    client.transition_ticket.assert_not_called()


def test_configured_non_prompt_transition_skips_picker(session, config, client):
    config.jira = Mock()
    config.jira.transitions = {"on_complete": Mock(prompt=False, to="Done")}

    transition_on_complete(session, config, client=client)

    client.transition_ticket.assert_called_once_with(session.issue_key, "closed")
