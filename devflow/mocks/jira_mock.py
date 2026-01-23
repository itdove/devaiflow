"""Mock JIRA service for integration testing.

This module provides a mock implementation of the JIRA client that uses
persistent storage. It's designed to be used for integration testing without
requiring a real JIRA instance.
"""

from typing import Any, Dict, List, Optional
from datetime import datetime

from devflow.mocks.persistence import MockDataStore


class MockJiraClient:
    """Mock JIRA client that mimics the real JiraClient interface.

    This client uses persistent storage to maintain issue tracker ticket data across
    command invocations. It implements the same interface as the real JiraClient
    to allow drop-in replacement when DAF_MOCK_MODE=1 is set.
    """

    def __init__(self, url: str = None, user: str = None, config: Any = None):
        """Initialize the mock JIRA client.

        Args:
            url: JIRA URL (ignored in mock)
            user: JIRA user (ignored in mock)
            config: Config object (used for field mappings)
        """
        self.store = MockDataStore()
        self.url = url or "http://localhost:8080/mock-jira"
        self.user = user or "mock-user"
        self.config = config

    def get_ticket(self, key: str) -> Optional[Dict[str, Any]]:
        """Get a issue tracker ticket by key.

        Args:
            key: issue tracker key (e.g., "PROJ-12345")

        Returns:
            Ticket data dict or None if not found
        """
        return self.store.get_jira_ticket(key)

    def get_ticket_detailed(self, key: str, field_mappings: Optional[Dict] = None, include_changelog: bool = False) -> Optional[Dict[str, Any]]:
        """Get detailed issue tracker ticket including changelog.

        Args:
            key: issue tracker key
            field_mappings: Optional field mappings dict (ignored in mock)
            include_changelog: If True, include changelog/history data

        Returns:
            Ticket data dict with changelog or None if not found
        """
        ticket = self.store.get_jira_ticket(key)
        if ticket:
            # Add mock changelog if requested and not present
            if include_changelog and "changelog" not in ticket:
                ticket["changelog"] = {
                    "histories": []
                }
        return ticket

    def create_ticket(
        self,
        issue_type: str,
        summary: str,
        description: str = "",
        project: str = "PROJ",
        **kwargs
    ) -> Dict[str, Any]:
        """Create a new issue tracker ticket.

        Args:
            issue_type: Issue type (Bug, Story, Task, Epic)
            summary: Ticket summary
            description: Ticket description
            project: Project key (default: PROJ)
            **kwargs: Additional fields

        Returns:
            Created ticket data dict
        """
        # Generate mock ticket key
        tickets = self.store.list_jira_tickets()
        ticket_num = len([t for t in tickets if t.get("key", "").startswith(f"{project}-")]) + 1
        key = f"{project}-{ticket_num}"

        # Create ticket data
        ticket_data = {
            "key": key,
            "fields": {
                "issuetype": {"name": issue_type},
                "summary": summary,
                "description": description,
                "project": {"key": project},
                "status": {"name": "New"},
                "created": datetime.now().isoformat(),
                "updated": datetime.now().isoformat(),
            }
        }

        # Add additional fields
        for field_name, field_value in kwargs.items():
            ticket_data["fields"][field_name] = field_value

        # Store ticket
        self.store.set_jira_ticket(key, ticket_data)

        return ticket_data

    def update_ticket(self, key: str, **fields) -> bool:
        """Update issue tracker ticket fields.

        Args:
            key: issue tracker key
            **fields: Fields to update

        Returns:
            True if successful, False if ticket not found
        """
        ticket = self.store.get_jira_ticket(key)
        if not ticket:
            return False

        # Update fields
        for field_name, field_value in fields.items():
            ticket["fields"][field_name] = field_value

        # Update timestamp
        ticket["fields"]["updated"] = datetime.now().isoformat()

        # Store updated ticket
        self.store.set_jira_ticket(key, ticket)
        return True

    def update_issue(self, issue_key: str, payload: Dict) -> None:
        """Update a JIRA issue with multiple fields.

        Compatible with JiraClient.update_issue() signature.

        Args:
            issue_key: issue tracker key
            payload: Update payload with fields to update (must have "fields" key)
                    Example: {"fields": {"description": "New desc", "priority": {"name": "Major"}}}

        Raises:
            JiraNotFoundError: If ticket not found
        """
        from devflow.jira.exceptions import JiraNotFoundError

        ticket = self.store.get_jira_ticket(issue_key)
        if not ticket:
            raise JiraNotFoundError(f"Ticket {issue_key} not found")

        # Extract fields from payload
        fields = payload.get("fields", {})

        # Update each field in the ticket
        for field_name, field_value in fields.items():
            ticket["fields"][field_name] = field_value

        # Update timestamp
        ticket["fields"]["updated"] = datetime.now().isoformat()

        # Store updated ticket
        self.store.set_jira_ticket(issue_key, ticket)

    def add_comment(self, key: str, comment: str) -> bool:
        """Add a comment to a issue tracker ticket.

        Args:
            key: issue tracker key
            comment: Comment text

        Returns:
            True if successful, False if ticket not found
        """
        ticket = self.store.get_jira_ticket(key)
        if not ticket:
            return False

        self.store.add_jira_comment(key, comment)
        return True

    def add_attachment(self, key: str, filepath: str) -> bool:
        """Add an attachment to a issue tracker ticket.

        Args:
            key: issue tracker key
            filepath: Path to file to attach

        Returns:
            True if successful, False if ticket not found
        """
        ticket = self.store.get_jira_ticket(key)
        if not ticket:
            return False

        # Extract filename from path
        from pathlib import Path
        filename = Path(filepath).name

        self.store.add_jira_attachment(key, filename)
        return True

    def transition_ticket(self, key: str, status: str) -> bool:
        """Transition a issue tracker ticket to a new status.

        Args:
            key: issue tracker key
            status: New status name

        Returns:
            True if successful, False if ticket not found
        """
        ticket = self.store.get_jira_ticket(key)
        if not ticket:
            return False

        self.store.set_jira_transition(key, status)
        return True

    def get_available_transitions(self, key: str) -> List[Dict[str, Any]]:
        """Get available transitions for a ticket.

        Args:
            key: issue tracker key

        Returns:
            List of available transitions
        """
        ticket = self.store.get_jira_ticket(key)
        if not ticket:
            return []

        # Return mock transitions
        current_status = ticket.get("fields", {}).get("status", {}).get("name", "New")

        transitions = []
        if current_status == "New":
            transitions = [
                {"id": "1", "name": "In Progress", "to": {"name": "In Progress"}},
                {"id": "2", "name": "Done", "to": {"name": "Done"}},
            ]
        elif current_status == "In Progress":
            transitions = [
                {"id": "3", "name": "Review", "to": {"name": "Review"}},
                {"id": "4", "name": "Done", "to": {"name": "Done"}},
            ]
        elif current_status == "Review":
            transitions = [
                {"id": "5", "name": "In Progress", "to": {"name": "In Progress"}},
                {"id": "6", "name": "Done", "to": {"name": "Done"}},
            ]

        return transitions

    def list_tickets(
        self,
        jql: str = None,
        max_results: int = 50,
        fields: List[str] = None
    ) -> List[Dict[str, Any]]:
        """List issue tracker tickets.

        Args:
            jql: JQL query (partially supported in mock)
            max_results: Maximum number of results
            fields: Fields to include in results

        Returns:
            List of ticket data dicts
        """
        tickets = self.store.list_jira_tickets()

        # Apply max_results limit
        if max_results:
            tickets = tickets[:max_results]

        # Simple JQL filtering (very limited mock implementation)
        if jql:
            # Support simple status filters
            if "status" in jql.lower():
                # Extract status values from JQL
                # This is a very simplified parser
                if "in progress" in jql.lower():
                    tickets = [t for t in tickets
                              if t.get("fields", {}).get("status", {}).get("name") == "In Progress"]
                elif "new" in jql.lower():
                    tickets = [t for t in tickets
                              if t.get("fields", {}).get("status", {}).get("name") == "New"]

        return tickets

    def get_field_metadata(self) -> List[Dict[str, Any]]:
        """Get JIRA field metadata.

        Returns:
            List of field metadata dicts
        """
        # Return mock field metadata
        return [
            {"id": "customfield_12310243", "name": "Story Points", "schema": {"type": "number"}},
            {"id": "customfield_12310940", "name": "Sprint", "schema": {"type": "string"}},
            {"id": "customfield_12311140", "name": "Epic Link", "schema": {"type": "string"}},
            {"id": "customfield_12315940", "name": "Acceptance Criteria", "schema": {"type": "string"}},
            {"id": "customfield_12319275", "name": "Workstream", "schema": {"type": "array", "items": "option"}},
        ]

    def search_issues(self, jql: str, max_results: int = 50) -> Dict[str, Any]:
        """Search for issues using JQL.

        Args:
            jql: JQL query string
            max_results: Maximum number of results

        Returns:
            Search results dict with 'issues' and 'total' keys
        """
        tickets = self.list_tickets(jql=jql, max_results=max_results)
        return {
            "issues": tickets,
            "total": len(tickets),
            "maxResults": max_results,
        }
