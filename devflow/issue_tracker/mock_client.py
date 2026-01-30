"""Mock implementation of IssueTrackerClient for testing.

This module provides a simple mock implementation that can be used
for testing without requiring actual JIRA/GitHub/GitLab connections.

Uses persistent storage via MockDataStore to maintain tickets across
command invocations during integration testing.
"""

from typing import Dict, List, Optional

from devflow.issue_tracker.interface import IssueTrackerClient
from devflow.jira.exceptions import JiraNotFoundError
from devflow.mocks.persistence import MockDataStore


class MockIssueTrackerClient(IssueTrackerClient):
    """Mock implementation of IssueTrackerClient for testing.

    Uses persistent storage to maintain tickets across command invocations.
    Useful for integration tests and development without external services.
    """

    def __init__(self, timeout: int = 30):
        """Initialize mock client.

        Args:
            timeout: Ignored for mock implementation
        """
        self.timeout = timeout
        self.store = MockDataStore()

    def get_ticket(self, issue_key: str, field_mappings: Optional[Dict] = None) -> Dict:
        """Fetch a ticket by its key."""
        ticket = self.store.get_jira_ticket(issue_key)
        if not ticket:
            raise JiraNotFoundError(
                f"Ticket {issue_key} not found",
                resource_type="issue",
                resource_id=issue_key
            )
        return ticket.copy()

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
        all_tickets = self.store.list_jira_tickets()
        results = []
        for ticket in all_tickets:
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

    def create_issue(
        self,
        issue_type: str,
        summary: str,
        description: str,
        priority: str,
        project_key: str,
        field_mapper,
        parent: Optional[str] = None,
        components: Optional[list] = None,
        required_custom_fields: Optional[dict] = None,
        **custom_fields
    ) -> str:
        """Generic method to create a ticket of any type."""
        if required_custom_fields is None:
            required_custom_fields = {}

        # Merge required_custom_fields into custom_fields
        all_custom_fields = {**required_custom_fields, **custom_fields}

        # Add priority to custom fields
        all_custom_fields["priority"] = priority

        # Extract acceptance_criteria if present
        acceptance_criteria = all_custom_fields.pop("acceptance_criteria", None)

        return self._create_ticket(
            issue_type,
            summary,
            description,
            project_key,
            parent,
            acceptance_criteria,
            **all_custom_fields
        )


    def _create_ticket(
        self,
        issue_type: str,
        summary: str,
        description: str,
        project: str,
        parent: Optional[str] = None,
        acceptance_criteria: Optional[str] = None,
        **custom_fields,
    ) -> str:
        """Internal helper to create a ticket."""
        # Get next ticket number (global counter across all projects)
        all_tickets = self.store.list_jira_tickets()
        ticket_num = len(all_tickets) + 1
        key = f"{project}-{ticket_num}"

        ticket = {
            "key": key,
            "summary": summary,
            "description": description,
            "type": issue_type,
            "status": "New",
            "project": project,
            "assignee": None,
            "reporter": "mock-user",
            "priority": custom_fields.get("priority"),
            "labels": [],
            "epic": parent if issue_type != "Epic" else None,
            "sprint": None,
            "points": None,
            "acceptance_criteria": acceptance_criteria,
        }

        # Add all custom fields generically
        for field_name, field_value in custom_fields.items():
            if field_name not in ticket and field_value is not None:
                ticket[field_name] = field_value

        self.store.set_jira_ticket(key, ticket)
        return key

    def update_issue(self, issue_key: str, payload: Dict) -> None:
        """Update an issue."""
        ticket = self.store.get_jira_ticket(issue_key)
        if not ticket:
            raise JiraNotFoundError(
                f"Ticket {issue_key} not found",
                resource_type="issue",
                resource_id=issue_key
            )
        # Simple update - merge payload into ticket
        ticket.update(payload)
        self.store.set_jira_ticket(issue_key, ticket)

    def update_ticket_field(self, issue_key: str, field_name: str, value: str) -> None:
        """Update a single field."""
        ticket = self.store.get_jira_ticket(issue_key)
        if not ticket:
            raise JiraNotFoundError(
                f"Ticket {issue_key} not found",
                resource_type="issue",
                resource_id=issue_key
            )
        ticket[field_name] = value
        self.store.set_jira_ticket(issue_key, ticket)

    def add_comment(self, issue_key: str, comment: str, public: bool = False) -> None:
        """Add a comment to a ticket."""
        ticket = self.store.get_jira_ticket(issue_key)
        if not ticket:
            raise JiraNotFoundError(
                f"Ticket {issue_key} not found",
                resource_type="issue",
                resource_id=issue_key
            )
        # Mock implementation - comments not stored
        pass

    def transition_ticket(self, issue_key: str, status: str) -> None:
        """Transition a ticket to a new status."""
        ticket = self.store.get_jira_ticket(issue_key)
        if not ticket:
            raise JiraNotFoundError(
                f"Ticket {issue_key} not found",
                resource_type="issue",
                resource_id=issue_key
            )
        ticket["status"] = status
        self.store.set_jira_ticket(issue_key, ticket)

    def attach_file(self, issue_key: str, file_path: str) -> None:
        """Attach a file to a ticket."""
        ticket = self.store.get_jira_ticket(issue_key)
        if not ticket:
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
        parent_ticket = self.store.get_jira_ticket(parent_key)
        if not parent_ticket:
            raise JiraNotFoundError(
                f"Ticket {parent_key} not found",
                resource_type="issue",
                resource_id=parent_key
            )
        results = []
        all_tickets = self.store.list_jira_tickets()
        for ticket in all_tickets:
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
        ticket = self.store.get_jira_ticket(issue_key)
        if not ticket:
            raise JiraNotFoundError(
                f"Ticket {issue_key} not found",
                resource_type="issue",
                resource_id=issue_key
            )
        linked_ticket = self.store.get_jira_ticket(linked_issue_key)
        if not linked_ticket:
            raise JiraNotFoundError(
                f"Ticket {linked_issue_key} not found",
                resource_type="issue",
                resource_id=linked_issue_key
            )
        # Mock implementation - links not stored
        pass
