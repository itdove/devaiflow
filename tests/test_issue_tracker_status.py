"""Tests for fail-safe issue closure checks."""

import pytest

from devflow.issue_tracker.status import (
    issue_is_closed,
    ticket_matches_closed_transition,
)


@pytest.mark.parametrize("backend", ["github", "gitlab"])
def test_hosted_issue_backends_require_closed_state(backend):
    assert issue_is_closed({"status": "closed"}, backend)
    assert not issue_is_closed({"status": "open"}, backend)
    assert not issue_is_closed({"status": None}, backend)


def test_jira_prefers_done_status_category_over_name_fallback():
    assert issue_is_closed(
        {"status": "In Progress", "status_category": {"key": "done"}}, "jira"
    )
    assert not issue_is_closed(
        {"status": "Closed", "status_category": {"key": "indeterminate"}}, "jira"
    )


@pytest.mark.parametrize("status", ["Done", "Resolved", "Closed", "Completed"])
def test_jira_common_terminal_status_names_are_supported_without_category(status):
    assert issue_is_closed({"status": status}, "jira")


def test_unknown_jira_status_and_unknown_backends_fail_closed():
    assert not issue_is_closed({"status": "In Review"}, "jira")
    assert not issue_is_closed({"status": "closed"}, "custom")
    assert not issue_is_closed({}, "jira")


def test_jira_closed_transition_must_match_selected_target():
    ticket = {"status": "Done", "status_category": "done"}
    assert ticket_matches_closed_transition(ticket, "jira", "done")
    assert not ticket_matches_closed_transition(ticket, "jira", "Closed")


def test_hosted_closed_status_does_not_require_a_transition_target():
    assert ticket_matches_closed_transition({"status": "closed"}, "github")
