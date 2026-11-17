"""Tests that unexpected GitLab issue states are not interpreted as closed."""

from devflow.gitlab.field_mapper import GitLabFieldMapper
from devflow.issue_tracker.status import issue_is_closed


def _ticket_with_state(state):
    return GitLabFieldMapper().map_gitlab_to_interface(
        {"iid": 42, "title": "Generic issue", "state": state},
        repository="group/project-a",
    )


def test_gitlab_closed_and_open_states_are_standardized():
    assert _ticket_with_state("closed")["status"] == "closed"
    assert _ticket_with_state("opened")["status"] == "open"


def test_gitlab_unknown_or_missing_state_is_not_closed():
    for state in ("unexpected", None):
        ticket = _ticket_with_state(state)
        assert ticket["status"] == "unknown"
        assert not issue_is_closed(ticket, "gitlab")
