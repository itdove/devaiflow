"""JIRA integration for DevAIFlow."""

from devflow.issue_tracker.factory import create_issue_tracker_client
from devflow.jira.client import JiraClient
from devflow.jira.transitions import transition_on_complete, transition_on_start

# Backward compatibility: Export factory as well
__all__ = ["JiraClient", "transition_on_start", "transition_on_complete", "create_issue_tracker_client"]
