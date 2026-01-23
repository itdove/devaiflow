"""Mock implementation of IssueTrackerClient for testing.

This module provides a simple mock implementation that can be used
for testing without requiring actual JIRA/GitHub/GitLab connections.
"""

from typing import Dict, List, Optional

from devflow.issue_tracker.interface import IssueTrackerClient
from devflow.jira.exceptions import JiraNotFoundError


class MockIssueTrackerClient(IssueTrackerClient):
    """Mock implementation of IssueTrackerClient for testing.

    Provides in-memory storage of tickets without requiring external services.
    Useful for unit tests and development.
    """

    def __init__(self, timeout: int = 30):
        """Initialize mock client.

        Args:
            timeout: Ignored for mock implementation
        """
        self.timeout = timeout
        self._tickets: Dict[str, Dict] = {}
        self._next_id = 1

    def get_ticket(self, issue_key: str, field_mappings: Optional[Dict] = None) -> Dict:
        """Fetch a ticket by its key."""
        if issue_key not in self._tickets:
            raise JiraNotFoundError(
                f"Ticket {issue_key} not found",
                resource_type="issue",
                resource_id=issue_key
            )
        return self._tickets[issue_key].copy()

    def get_ticket_detailed(
        self, issue_key: str, field_mappings: Optional[Dict] = None, include_changelog: bool = False
    ) -> Dict:
        """Fetch detailed ticket information."""
        ticket = self.get_ticket(issue_key, field_mappings)
        if include_changelog:
            ticket["changelog"] = {"histories": []}
        return ticket

    def list_tickets(
        self,
        jql: Optional[str] = None,
        project: Optional[str] = None,
        assignee: Optional[str] = None,
        status: Optional[List[str]] = None,
        issue_type: Optional[List[str]] = None,
        sprint: Optional[str] = None,
        max_results: int = 50,
        start_at: int = 0,
        field_mappings: Optional[Dict] = None,
    ) -> List[Dict]:
        """List tickets matching criteria."""
        results = []
        for ticket in self._tickets.values():
            # Simple filtering
            if project and ticket.get("project") != project:
                continue
            if assignee and ticket.get("assignee") != assignee:
                continue
            if status and ticket.get("status") not in status:
                continue
            if issue_type and ticket.get("type") not in issue_type:
                continue
            results.append(ticket.copy())
        return results[start_at:start_at + max_results]

    def create_bug(
        self,
        summary: str,
        description: str,
        project: str,
        priority: Optional[str] = None,
        affected_version: Optional[str] = None,
        parent: Optional[str] = None,
        workstream: Optional[str] = None,
        acceptance_criteria: Optional[str] = None,
        field_mapper=None,
        **custom_fields,
    ) -> str:
        """Create a bug ticket."""
        return self._create_ticket("Bug", summary, description, project, parent, workstream, acceptance_criteria, priority=priority)

    def create_story(
        self,
        summary: str,
        description: str,
        project: str,
        parent: Optional[str] = None,
        workstream: Optional[str] = None,
        acceptance_criteria: Optional[str] = None,
        field_mapper=None,
        **custom_fields,
    ) -> str:
        """Create a story ticket."""
        return self._create_ticket("Story", summary, description, project, parent, workstream, acceptance_criteria)

    def create_task(
        self,
        summary: str,
        description: str,
        project: str,
        parent: Optional[str] = None,
        workstream: Optional[str] = None,
        acceptance_criteria: Optional[str] = None,
        field_mapper=None,
        **custom_fields,
    ) -> str:
        """Create a task ticket."""
        return self._create_ticket("Task", summary, description, project, parent, workstream, acceptance_criteria)

    def create_epic(
        self,
        summary: str,
        description: str,
        project: str,
        workstream: Optional[str] = None,
        field_mapper=None,
        **custom_fields,
    ) -> str:
        """Create an epic ticket."""
        return self._create_ticket("Epic", summary, description, project, None, workstream, None)

    def create_spike(
        self,
        summary: str,
        description: str,
        project: str,
        parent: Optional[str] = None,
        workstream: Optional[str] = None,
        acceptance_criteria: Optional[str] = None,
        field_mapper=None,
        **custom_fields,
    ) -> str:
        """Create a spike ticket."""
        return self._create_ticket("Spike", summary, description, project, parent, workstream, acceptance_criteria)

    def _create_ticket(
        self,
        issue_type: str,
        summary: str,
        description: str,
        project: str,
        parent: Optional[str] = None,
        workstream: Optional[str] = None,
        acceptance_criteria: Optional[str] = None,
        **extra_fields,
    ) -> str:
        """Internal helper to create a ticket."""
        key = f"{project}-{self._next_id}"
        self._next_id += 1

        ticket = {
            "key": key,
            "summary": summary,
            "description": description,
            "type": issue_type,
            "status": "New",
            "project": project,
            "assignee": None,
            "reporter": "mock-user",
            "priority": extra_fields.get("priority"),
            "labels": [],
            "epic": parent if issue_type != "Epic" else None,
            "sprint": None,
            "points": None,
            "acceptance_criteria": acceptance_criteria,
            "workstream": workstream,
        }
        self._tickets[key] = ticket
        return key

    def update_issue(self, issue_key: str, payload: Dict) -> None:
        """Update an issue."""
        if issue_key not in self._tickets:
            raise JiraNotFoundError(
                f"Ticket {issue_key} not found",
                resource_type="issue",
                resource_id=issue_key
            )
        # Simple update - merge payload into ticket
        self._tickets[issue_key].update(payload)

    def update_ticket_field(self, issue_key: str, field_name: str, value: str) -> None:
        """Update a single field."""
        if issue_key not in self._tickets:
            raise JiraNotFoundError(
                f"Ticket {issue_key} not found",
                resource_type="issue",
                resource_id=issue_key
            )
        self._tickets[issue_key][field_name] = value

    def add_comment(self, issue_key: str, comment: str, public: bool = False) -> None:
        """Add a comment to a ticket."""
        if issue_key not in self._tickets:
            raise JiraNotFoundError(
                f"Ticket {issue_key} not found",
                resource_type="issue",
                resource_id=issue_key
            )
        # Mock implementation - comments not stored
        pass

    def transition_ticket(self, issue_key: str, status: str) -> None:
        """Transition a ticket to a new status."""
        if issue_key not in self._tickets:
            raise JiraNotFoundError(
                f"Ticket {issue_key} not found",
                resource_type="issue",
                resource_id=issue_key
            )
        self._tickets[issue_key]["status"] = status

    def attach_file(self, issue_key: str, file_path: str) -> None:
        """Attach a file to a ticket."""
        if issue_key not in self._tickets:
            raise JiraNotFoundError(
                f"Ticket {issue_key} not found",
                resource_type="issue",
                resource_id=issue_key
            )
        # Mock implementation - attachments not stored
        pass

    def get_ticket_pr_links(self, issue_key: str, field_mappings: Optional[Dict] = None) -> str:
        """Get PR/MR links."""
        ticket = self.get_ticket(issue_key, field_mappings)
        return ticket.get("git_pull_request", "")

    def get_child_issues(
        self,
        parent_key: str,
        issue_types: Optional[List[str]] = None,
        field_mappings: Optional[Dict] = None,
    ) -> List[Dict]:
        """Get child issues."""
        if parent_key not in self._tickets:
            raise JiraNotFoundError(
                f"Ticket {parent_key} not found",
                resource_type="issue",
                resource_id=parent_key
            )
        results = []
        for ticket in self._tickets.values():
            if ticket.get("epic") == parent_key:
                if issue_types is None or ticket.get("type") in issue_types:
                    results.append(ticket.copy())
        return results

    def get_issue_link_types(self) -> List[Dict]:
        """Get available issue link types."""
        return [
            {"id": "1", "name": "Blocks", "inward": "is blocked by", "outward": "blocks"},
            {"id": "2", "name": "Relates", "inward": "relates to", "outward": "relates to"},
            {"id": "3", "name": "Duplicates", "inward": "is duplicated by", "outward": "duplicates"},
        ]

    def link_issues(
        self, issue_key: str, link_type: str, linked_issue_key: str, comment: Optional[str] = None
    ) -> None:
        """Create a link between two issues."""
        if issue_key not in self._tickets:
            raise JiraNotFoundError(
                f"Ticket {issue_key} not found",
                resource_type="issue",
                resource_id=issue_key
            )
        if linked_issue_key not in self._tickets:
            raise JiraNotFoundError(
                f"Ticket {linked_issue_key} not found",
                resource_type="issue",
                resource_id=linked_issue_key
            )
        # Mock implementation - links not stored
        pass
