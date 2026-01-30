"""Abstract interface for issue tracking systems.

This module defines the abstract base class that all issue tracker backends
must implement. It provides a common interface for operations like:
- Fetching tickets/issues
- Creating tickets/issues
- Updating tickets/issues
- Managing comments, attachments, and links
- Transitioning issue status

Following the StorageBackend pattern from devflow/storage/base.py.
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional


class IssueTrackerClient(ABC):
    """Abstract base class for issue tracking system clients.

    Defines the interface that all issue tracker backends must implement.
    Allows swapping between JIRA, GitHub Issues, GitLab Issues, or other systems.

    All methods should raise appropriate exceptions from devflow.jira.exceptions
    for error conditions (authentication failures, API errors, validation errors, etc.).
    """

    @abstractmethod
    def get_ticket(self, issue_key: str, field_mappings: Optional[Dict] = None) -> Dict:
        """Fetch a ticket by its key/ID.

        Args:
            issue_key: Unique identifier for the ticket (e.g., "PROJ-12345")
            field_mappings: Optional field name mappings for custom fields

        Returns:
            Dictionary containing ticket data with standardized keys:
                - key: Ticket identifier
                - summary: Brief title/summary
                - description: Full description
                - type: Issue type (bug, story, task, etc.)
                - status: Current status
                - assignee: Assigned user (optional)
                - reporter: Reporter user (optional)
                - priority: Priority level (optional)
                - labels: List of labels (optional)
                - epic: Parent epic key (optional)

            Custom fields (sprint, points, acceptance_criteria, etc.) are returned
            as additional keys in the dictionary based on the field_mappings provided

        Raises:
            JiraAuthError: If authentication fails
            JiraNotFoundError: If ticket not found (404)
            JiraApiError: If API request fails
            JiraConnectionError: If connection fails
        """
        pass

    @abstractmethod
    def get_ticket_detailed(
        self, issue_key: str, field_mappings: Optional[Dict] = None, include_changelog: bool = False
    ) -> Dict:
        """Fetch detailed ticket information including changelog.

        Args:
            issue_key: Unique identifier for the ticket
            field_mappings: Optional field name mappings for custom fields
            include_changelog: Whether to include changelog/history

        Returns:
            Dictionary with detailed ticket data (same format as get_ticket, plus changelog if requested)

        Raises:
            JiraAuthError: If authentication fails
            JiraNotFoundError: If ticket not found (404)
            JiraApiError: If API request fails
            JiraConnectionError: If connection fails
        """
        pass

    @abstractmethod
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
        """List tickets matching given criteria.

        Args:
            jql: Raw query language string (backend-specific)
            project: Project key/ID to filter by
            assignee: Assignee username to filter by
            status: List of statuses to filter by
            issue_type: List of issue types to filter by
            sprint: Sprint name/ID to filter by
            max_results: Maximum number of results to return
            start_at: Pagination offset
            field_mappings: Optional field name mappings for custom fields

        Returns:
            List of ticket dictionaries (same format as get_ticket)

        Raises:
            JiraAuthError: If authentication fails
            JiraApiError: If API request fails
            JiraConnectionError: If connection fails
        """
        pass

    @abstractmethod
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
        """Generic method to create a ticket of any type.

        This method provides a unified interface for creating issues across all types
        (Bug, Story, Task, Epic, Spike). Issue-type-specific methods (create_bug,
        create_story, etc.) are thin wrappers around this method for backward compatibility.

        Args:
            issue_type: Type of issue to create (e.g., "Bug", "Story", "Task", "Epic", "Spike")
            summary: Brief title of the issue
            description: Detailed description
            priority: Priority level (e.g., "Critical", "Major", "Normal", "Minor")
            project_key: Project key/ID
            field_mapper: Field mapping helper (backend-specific)
            parent: Parent epic/issue key (optional, uses parent_field_mapping from config)
            components: List of component names (optional)
            required_custom_fields: Dictionary of required custom fields {field_name: value}
            **custom_fields: Additional custom fields (field_id: value pairs)

        Returns:
            Created ticket key/ID

        Raises:
            JiraAuthError: If authentication fails
            JiraValidationError: If validation fails (400 with field errors)
            JiraApiError: If API request fails
            JiraConnectionError: If connection fails

        Example:
            # Create a bug
            key = client.create_issue(
                issue_type="Bug",
                summary="Production API timeout",
                description="...",
                priority="Critical",
                project_key="PROJ",
                field_mapper=field_mapper,
                parent="PROJ-1234",
                required_custom_fields={"affected_version": "2.5.0"}
            )

            # Create a story
            key = client.create_issue(
                issue_type="Story",
                summary="Add caching layer",
                description="...",
                priority="Major",
                project_key="PROJ",
                field_mapper=field_mapper,
                parent="PROJ-1234"
            )
        """
        pass

    @abstractmethod
    def update_issue(self, issue_key: str, payload: Dict) -> None:
        """Update an issue with the given payload.

        Args:
            issue_key: Unique identifier for the ticket
            payload: Update payload (backend-specific format)

        Raises:
            JiraAuthError: If authentication fails
            JiraNotFoundError: If ticket not found (404)
            JiraValidationError: If validation fails (400 with field errors)
            JiraApiError: If API request fails
            JiraConnectionError: If connection fails
        """
        pass

    @abstractmethod
    def update_ticket_field(self, issue_key: str, field_name: str, value: str) -> None:
        """Update a single field on a ticket.

        Args:
            issue_key: Unique identifier for the ticket
            field_name: Name of the field to update
            value: New value for the field

        Raises:
            JiraAuthError: If authentication fails
            JiraNotFoundError: If ticket not found (404)
            JiraValidationError: If validation fails (400 with field errors)
            JiraApiError: If API request fails
            JiraConnectionError: If connection fails
        """
        pass

    @abstractmethod
    def add_comment(self, issue_key: str, comment: str, public: bool = False) -> None:
        """Add a comment to a ticket.

        Args:
            issue_key: Unique identifier for the ticket
            comment: Comment text
            public: Whether comment is public (True) or restricted (False)

        Raises:
            JiraAuthError: If authentication fails
            JiraNotFoundError: If ticket not found (404)
            JiraApiError: If API request fails
            JiraConnectionError: If connection fails
        """
        pass

    @abstractmethod
    def transition_ticket(self, issue_key: str, status: str) -> None:
        """Transition a ticket to a new status.

        Args:
            issue_key: Unique identifier for the ticket
            status: Target status name

        Raises:
            JiraAuthError: If authentication fails
            JiraNotFoundError: If ticket not found (404)
            JiraApiError: If transition fails or status not available
            JiraConnectionError: If connection fails
        """
        pass

    @abstractmethod
    def attach_file(self, issue_key: str, file_path: str) -> None:
        """Attach a file to a ticket.

        Args:
            issue_key: Unique identifier for the ticket
            file_path: Path to the file to attach

        Raises:
            JiraAuthError: If authentication fails
            JiraNotFoundError: If ticket not found (404)
            JiraApiError: If file upload fails
            JiraConnectionError: If connection fails
        """
        pass

    @abstractmethod
    def get_ticket_pr_links(self, issue_key: str, field_mappings: Optional[Dict] = None) -> str:
        """Get PR/MR links associated with a ticket.

        Args:
            issue_key: Unique identifier for the ticket
            field_mappings: Optional field name mappings for custom fields

        Returns:
            Comma-separated string of PR/MR URLs

        Raises:
            JiraAuthError: If authentication fails
            JiraNotFoundError: If ticket not found (404)
            JiraApiError: If API request fails
            JiraConnectionError: If connection fails
        """
        pass

    @abstractmethod
    def get_child_issues(
        self,
        parent_key: str,
        issue_types: Optional[List[str]] = None,
        field_mappings: Optional[Dict] = None,
    ) -> List[Dict]:
        """Get child issues of a parent issue.

        Args:
            parent_key: Parent issue key/ID
            issue_types: Filter by specific issue types (optional)
            field_mappings: Optional field name mappings for custom fields

        Returns:
            List of child ticket dictionaries (same format as get_ticket)

        Raises:
            JiraAuthError: If authentication fails
            JiraNotFoundError: If parent ticket not found (404)
            JiraApiError: If API request fails
            JiraConnectionError: If connection fails
        """
        pass

    @abstractmethod
    def get_issue_link_types(self) -> List[Dict]:
        """Get available issue link types (e.g., blocks, relates to, duplicates).

        Returns:
            List of link type dictionaries with keys:
                - id: Link type ID
                - name: Link type name
                - inward: Inward link description (e.g., "is blocked by")
                - outward: Outward link description (e.g., "blocks")

        Raises:
            JiraAuthError: If authentication fails
            JiraApiError: If API request fails
            JiraConnectionError: If connection fails
        """
        pass

    @abstractmethod
    def link_issues(
        self, issue_key: str, link_type: str, linked_issue_key: str, comment: Optional[str] = None
    ) -> None:
        """Create a link between two issues.

        Args:
            issue_key: Source issue key
            link_type: Type of link (e.g., "blocks", "relates to", "duplicates")
            linked_issue_key: Target issue key to link to
            comment: Optional comment for the link

        Raises:
            JiraAuthError: If authentication fails
            JiraNotFoundError: If either ticket not found (404)
            JiraValidationError: If link type invalid
            JiraApiError: If API request fails
            JiraConnectionError: If connection fails
        """
        pass
