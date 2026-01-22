"""JIRA REST API client for DevAIFlow.

This module provides a Python interface to the JIRA REST API.
All JIRA operations are performed via the REST API.
"""

import os
from typing import Dict, List, Optional

import requests
import yaml
from rich.console import Console

from devflow.issue_tracker.interface import IssueTrackerClient
from devflow.jira.exceptions import (
    JiraApiError,
    JiraAuthError,
    JiraConnectionError,
    JiraNotFoundError,
    JiraValidationError,
)

console = Console()


class JiraClient(IssueTrackerClient):
    """JIRA implementation of IssueTrackerClient.

    Client for interacting with JIRA via REST API.
    Implements the IssueTrackerClient interface for JIRA-specific operations.
    """

    def __init__(self, timeout: int = 30):
        """Initialize JIRA client.

        Args:
            timeout: Default timeout for API requests in seconds
        """
        self.timeout = timeout
        self._jira_url = None
        self._jira_token = None
        self._jira_auth_type = None
        self._field_cache = None  # Cache for field ID to name mapping
        self._comment_visibility_type = None  # Default visibility type (from config)
        self._comment_visibility_value = None  # Default visibility value (from config)
        self._load_jira_config()

    def _load_jira_config(self) -> None:
        """Load JIRA configuration from environment and config files."""
        # Try environment variables first
        self._jira_url = os.getenv("JIRA_URL")
        self._jira_token = os.getenv("JIRA_API_TOKEN")
        self._jira_auth_type = os.getenv("JIRA_AUTH_TYPE", "bearer").lower()

        # If URL not in env, try jira CLI config
        if not self._jira_url:
            try:
                config_path = os.path.expanduser("~/.config/.jira/.config.yml")
                with open(config_path, 'r') as f:
                    jira_config = yaml.safe_load(f)
                    self._jira_url = jira_config.get('server')
            except:
                pass

        # No default JIRA URL - must be configured by user or via patches
        # if not self._jira_url:
        #     (No default - user must configure)

        # Load comment visibility settings from daf config
        try:
            from devflow.config.loader import ConfigLoader
            config_loader = ConfigLoader()
            if config_loader.config_file.exists():
                config = config_loader.load_config()
                if config and config.jira:
                    if config.jira.comment_visibility_type:
                        self._comment_visibility_type = config.jira.comment_visibility_type
                    if config.jira.comment_visibility_value:
                        self._comment_visibility_value = config.jira.comment_visibility_value
        except Exception:
            # If config loading fails, use defaults
            pass

    def _get_auth_header(self) -> str:
        """Get the authorization header value based on auth type.

        Returns:
            Authorization header value (e.g., "Bearer <token>" or "Basic <token>")

        Raises:
            JiraAuthError: If JIRA_API_TOKEN not set
        """
        if not self._jira_token:
            raise JiraAuthError(
                "JIRA_API_TOKEN not set in environment. "
                "Set it with: export JIRA_API_TOKEN=your_token"
            )

        if self._jira_auth_type == "bearer":
            return f"Bearer {self._jira_token}"
        elif self._jira_auth_type == "basic":
            return f"Basic {self._jira_token}"
        else:
            # Default to bearer for unknown auth types
            return f"Bearer {self._jira_token}"

    def _get_field_name(self, field_id: str) -> str:
        """Get human-readable field name from field ID.

        Args:
            field_id: JIRA field ID (e.g., "customfield_12319275")

        Returns:
            Human-readable field name, or the field_id if lookup fails
        """
        # Return cached result if available
        if self._field_cache and field_id in self._field_cache:
            return self._field_cache[field_id]

        # Try to fetch field metadata
        try:
            response = self._api_request("GET", "/rest/api/2/field")
            if response.status_code == 200:
                fields = response.json()
                # Build cache
                self._field_cache = {}
                for field in fields:
                    field_key = field.get("id", "")
                    field_name = field.get("name", field_key)
                    self._field_cache[field_key] = field_name

                # Return the requested field name
                return self._field_cache.get(field_id, field_id)
        except Exception:
            # If field lookup fails, return the field_id as-is
            pass

        return field_id

    def _api_request(self, method: str, endpoint: str, **kwargs) -> requests.Response:
        """Make a JIRA REST API request.

        Args:
            method: HTTP method (GET, POST, PUT, etc.)
            endpoint: API endpoint (e.g., "/rest/api/2/issue/PROJ-12345")
            **kwargs: Additional arguments passed to requests.request()

        Returns:
            Response object

        Raises:
            JiraAuthError: If JIRA_API_TOKEN not set or JIRA_URL not configured
            JiraConnectionError: If request fails due to network/connection issues
        """
        if not self._jira_url:
            raise JiraAuthError(
                "JIRA URL not configured. Please run 'daf init' or set the JIRA_URL environment variable.",
                status_code=401
            )
        url = f"{self._jira_url}{endpoint}"
        headers = kwargs.pop('headers', {})
        headers.update({
            "Authorization": self._get_auth_header(),
            "Content-Type": "application/json",
            "Accept": "application/json"
        })

        timeout = kwargs.pop('timeout', self.timeout)

        try:
            response = requests.request(
                method=method,
                url=url,
                headers=headers,
                timeout=timeout,
                **kwargs
            )
            return response
        except requests.exceptions.RequestException as e:
            raise JiraConnectionError(f"JIRA API request failed: {e}")

    def get_ticket(self, issue_key: str, field_mappings: Optional[Dict] = None) -> Dict:
        """Fetch a issue tracker ticket by key using REST API.

        Args:
            issue_key: issue tracker key (e.g., PROJ-52470)
            field_mappings: Optional field mappings dict from config to resolve custom field IDs
                          (e.g., {"story_points": {"id": "customfield_12310243"}})

        Returns:
            Dictionary with ticket data

        Raises:
            JiraNotFoundError: If ticket not found (404)
            JiraApiError: If API request fails with other error
            JiraAuthError: If authentication fails
            JiraConnectionError: If connection fails
        """
        try:
            response = self._api_request(
                "GET",
                f"/rest/api/2/issue/{issue_key}"
            )

            if response.status_code == 404:
                raise JiraNotFoundError(
                    f"issue tracker ticket {issue_key} not found",
                    resource_type="issue",
                    resource_id=issue_key
                )
            elif response.status_code == 401 or response.status_code == 403:
                raise JiraAuthError(
                    f"Authentication failed for issue tracker ticket {issue_key}",
                    status_code=response.status_code
                )
            elif response.status_code != 200:
                raise JiraApiError(
                    f"Failed to fetch issue tracker ticket {issue_key}",
                    status_code=response.status_code,
                    response_text=response.text
                )

            data = response.json()
            fields = data.get("fields", {})

            ticket_data = {
                "key": issue_key,
                "type": fields.get("issuetype", {}).get("name"),
                "status": fields.get("status", {}).get("name"),
                "summary": fields.get("summary"),
                "assignee": fields.get("assignee", {}).get("displayName") if fields.get("assignee") else None,
            }

            # Resolve field IDs from field_mappings
            story_points_field = None
            sprint_field = None
            epic_link_field = None

            if field_mappings:
                story_points_field = field_mappings.get("story_points", {}).get("id")
                sprint_field = field_mappings.get("sprint", {}).get("id")
                epic_link_field = field_mappings.get("epic_link", {}).get("id")

            # Story points
            if fields.get(story_points_field):
                try:
                    ticket_data["points"] = int(fields[story_points_field])
                except (ValueError, TypeError):
                    pass

            # Sprint (get first sprint if multiple)
            sprints = fields.get(sprint_field, [])
            if sprints and len(sprints) > 0:
                # Sprint is in format: "com.atlassian.greenhopper.service.sprint.Sprint@xxxxx[id=1234,name=Sprint Name,...]"
                sprint_str = sprints[0] if isinstance(sprints, list) else sprints
                if isinstance(sprint_str, str) and "name=" in sprint_str:
                    # Extract name from sprint string
                    name_start = sprint_str.find("name=") + 5
                    name_end = sprint_str.find(",", name_start)
                    if name_end == -1:
                        name_end = sprint_str.find("]", name_start)
                    ticket_data["sprint"] = sprint_str[name_start:name_end]

            # Epic link
            if fields.get(epic_link_field):
                ticket_data["epic"] = fields[epic_link_field]

            return ticket_data

        except (JiraNotFoundError, JiraAuthError, JiraApiError, JiraConnectionError):
            # Re-raise JIRA-specific exceptions
            raise
        except Exception as e:
            # Wrap unexpected errors in JiraApiError
            raise JiraApiError(f"Failed to fetch issue tracker ticket {issue_key}: {e}")

    def add_comment(self, issue_key: str, comment: str, public: bool = False) -> None:
        """Add a comment to a issue tracker ticket with configurable visibility.

        Uses JIRA REST API to properly set comment visibility based on
        configuration settings (comment_visibility_type and comment_visibility_value).

        Args:
            issue_key: issue tracker key
            comment: Comment text
            public: If True, make comment public (no visibility restriction)

        Raises:
            JiraNotFoundError: If ticket not found
            JiraApiError: If API request fails
            JiraAuthError: If authentication fails
            JiraConnectionError: If connection fails
        """
        # Comment body with optional visibility restriction
        payload = {"body": comment}

        # Add visibility restriction unless public flag is set
        if not public:
            payload["visibility"] = {
                "type": self._comment_visibility_type,
                "value": self._comment_visibility_value
            }

        response = self._api_request(
            "POST",
            f"/rest/api/2/issue/{issue_key}/comment",
            json=payload,
            timeout=30
        )

        if response.status_code == 404:
            raise JiraNotFoundError(
                f"Cannot add comment: issue tracker ticket {issue_key} not found",
                resource_type="issue",
                resource_id=issue_key
            )
        elif response.status_code == 401 or response.status_code == 403:
            raise JiraAuthError(
                f"Authentication failed when adding comment to {issue_key}",
                status_code=response.status_code
            )
        elif response.status_code != 201:
            raise JiraApiError(
                f"Failed to add comment to {issue_key}",
                status_code=response.status_code,
                response_text=response.text
            )

    def transition_ticket(self, issue_key: str, status: str) -> None:
        """Transition a issue tracker ticket to a new status using REST API.

        Args:
            issue_key: issue tracker key
            status: Target status name (e.g., "In Progress", "Review", "Closed")

        Raises:
            JiraNotFoundError: If ticket not found or status not available
            JiraValidationError: If transition requires missing fields (400)
            JiraApiError: If API request fails
            JiraAuthError: If authentication fails
            JiraConnectionError: If connection fails
        """
        try:
            # First, get available transitions for this ticket
            response = self._api_request(
                "GET",
                f"/rest/api/2/issue/{issue_key}/transitions"
            )

            if response.status_code == 404:
                raise JiraNotFoundError(
                    f"Cannot transition: issue tracker ticket {issue_key} not found",
                    resource_type="issue",
                    resource_id=issue_key
                )
            elif response.status_code == 401 or response.status_code == 403:
                raise JiraAuthError(
                    f"Authentication failed when getting transitions for {issue_key}",
                    status_code=response.status_code
                )
            elif response.status_code != 200:
                raise JiraApiError(
                    f"Failed to get transitions for {issue_key}",
                    status_code=response.status_code,
                    response_text=response.text
                )

            transitions = response.json().get("transitions", [])

            # Find the transition ID that matches the target status
            transition_id = None
            for transition in transitions:
                # Match by status name (case-insensitive)
                to_status = transition.get("to", {}).get("name", "")
                if to_status.lower() == status.lower():
                    transition_id = transition.get("id")
                    break

            if not transition_id:
                # List available transitions for error message
                available = [t.get("to", {}).get("name") for t in transitions]
                raise JiraNotFoundError(
                    f"Status '{status}' not available for {issue_key}. "
                    f"Available transitions: {', '.join(available)}",
                    resource_type="transition",
                    resource_id=status
                )

            # Perform the transition
            payload = {
                "transition": {
                    "id": transition_id
                }
            }

            response = self._api_request(
                "POST",
                f"/rest/api/2/issue/{issue_key}/transitions",
                json=payload
            )

            if response.status_code == 204:
                return  # Success
            elif response.status_code == 404:
                raise JiraNotFoundError(
                    f"Cannot transition: issue tracker ticket {issue_key} not found",
                    resource_type="issue",
                    resource_id=issue_key
                )
            elif response.status_code == 401 or response.status_code == 403:
                raise JiraAuthError(
                    f"Authentication failed when transitioning {issue_key}",
                    status_code=response.status_code
                )
            elif response.status_code == 400:
                # Parse the error response to extract field information
                try:
                    error_data = response.json()
                    error_messages = error_data.get("errorMessages", [])
                    field_errors = error_data.get("errors", {})

                    # Build field errors dict with human-readable field names
                    readable_field_errors = {}
                    for field_id, error_msg in field_errors.items():
                        field_name = self._get_field_name(field_id)
                        readable_field_errors[field_name] = error_msg

                    raise JiraValidationError(
                        f"Transition to '{status}' failed for {issue_key}: missing required fields",
                        field_errors=readable_field_errors,
                        error_messages=error_messages
                    )

                except JiraValidationError:
                    # Re-raise JiraValidationError
                    raise
                except Exception:
                    # If JSON parsing fails, raise generic API error
                    raise JiraApiError(
                        f"Transition to '{status}' failed for {issue_key}",
                        status_code=response.status_code,
                        response_text=response.text
                    )
            else:
                raise JiraApiError(
                    f"Transition to '{status}' failed for {issue_key}",
                    status_code=response.status_code,
                    response_text=response.text
                )

        except (JiraNotFoundError, JiraAuthError, JiraApiError, JiraValidationError, JiraConnectionError):
            # Re-raise JIRA-specific exceptions
            raise
        except Exception as e:
            # Wrap unexpected errors
            raise JiraApiError(f"Failed to transition {issue_key} to '{status}': {e}")

    def attach_file(self, issue_key: str, file_path: str) -> None:
        """Attach a file to a issue tracker ticket using REST API.

        Args:
            issue_key: issue tracker key
            file_path: Path to file to attach

        Raises:
            JiraNotFoundError: If ticket not found or file not found
            JiraApiError: If API request fails
            JiraAuthError: If authentication fails
            JiraConnectionError: If connection fails
        """
        try:
            url = f"{self._jira_url}/rest/api/2/issue/{issue_key}/attachments"

            # For file uploads, we need different headers (no Content-Type, let requests set it)
            headers = {
                "Authorization": self._get_auth_header(),
                "X-Atlassian-Token": "no-check"  # Required for attachments
            }

            with open(file_path, 'rb') as f:
                files = {'file': f}
                try:
                    response = requests.post(
                        url,
                        headers=headers,
                        files=files,
                        timeout=60  # Longer timeout for file uploads
                    )
                except requests.exceptions.RequestException as e:
                    raise JiraConnectionError(f"JIRA API request failed: {e}")

            if response.status_code == 200:
                return  # Success
            elif response.status_code == 404:
                raise JiraNotFoundError(
                    f"Cannot attach file: issue tracker ticket {issue_key} not found",
                    resource_type="issue",
                    resource_id=issue_key
                )
            elif response.status_code == 401 or response.status_code == 403:
                raise JiraAuthError(
                    f"Authentication failed when attaching file to {issue_key}",
                    status_code=response.status_code
                )
            else:
                raise JiraApiError(
                    f"Failed to attach file to {issue_key}",
                    status_code=response.status_code,
                    response_text=response.text
                )

        except FileNotFoundError:
            raise JiraNotFoundError(
                f"File not found: {file_path}",
                resource_type="file",
                resource_id=file_path
            )
        except (JiraNotFoundError, JiraAuthError, JiraApiError, JiraConnectionError):
            # Re-raise JIRA-specific exceptions
            raise
        except Exception as e:
            # Wrap unexpected errors
            raise JiraApiError(f"Failed to attach file {file_path} to {issue_key}: {e}")

    def get_ticket_detailed(self, issue_key: str, field_mappings: Optional[Dict] = None, include_changelog: bool = False) -> Dict:
        """Fetch a issue tracker ticket with full details including description.

        Args:
            issue_key: issue tracker key (e.g., PROJ-52470)
            field_mappings: Optional field mappings dict from config to resolve custom field IDs
                          (e.g., {"acceptance_criteria": {"id": "customfield_12315940"}})
            include_changelog: If True, include changelog/history data

        Returns:
            Dictionary with full ticket data.
            If include_changelog is True, includes a "changelog" key with history data.

        Raises:
            JiraNotFoundError: If ticket not found (404)
            JiraApiError: If API request fails
            JiraAuthError: If authentication fails
            JiraConnectionError: If connection fails
        """
        try:
            # Build endpoint with optional changelog expansion
            endpoint = f"/rest/api/2/issue/{issue_key}"
            if include_changelog:
                endpoint += "?expand=changelog"

            response = self._api_request(
                "GET",
                endpoint
            )

            if response.status_code == 404:
                raise JiraNotFoundError(
                    f"issue tracker ticket {issue_key} not found",
                    resource_type="issue",
                    resource_id=issue_key
                )
            elif response.status_code == 401 or response.status_code == 403:
                raise JiraAuthError(
                    f"Authentication failed for issue tracker ticket {issue_key}",
                    status_code=response.status_code
                )
            elif response.status_code != 200:
                raise JiraApiError(
                    f"Failed to fetch issue tracker ticket {issue_key}",
                    status_code=response.status_code,
                    response_text=response.text
                )

            data = response.json()
            fields = data.get("fields", {})

            ticket_data = {
                "key": issue_key,
                "type": fields.get("issuetype", {}).get("name"),
                "status": fields.get("status", {}).get("name"),
                "summary": fields.get("summary"),
                "description": fields.get("description"),
                "priority": fields.get("priority", {}).get("name") if fields.get("priority") else None,
                "assignee": fields.get("assignee", {}).get("displayName") if fields.get("assignee") else None,
                "reporter": fields.get("reporter", {}).get("displayName") if fields.get("reporter") else None,
            }

            # Resolve field IDs from field_mappings
            story_points_field = None
            sprint_field = None
            epic_link_field = None
            git_pr_field = None

            if field_mappings:
                story_points_field = field_mappings.get("story_points", {}).get("id")
                sprint_field = field_mappings.get("sprint", {}).get("id")
                epic_link_field = field_mappings.get("epic_link", {}).get("id")
                git_pr_field = field_mappings.get("git_pull_request", {}).get("id")

            # Story points
            if fields.get(story_points_field):
                try:
                    ticket_data["points"] = int(fields[story_points_field])
                except (ValueError, TypeError):
                    pass

            # Sprint (get first sprint if multiple)
            sprints = fields.get(sprint_field, [])
            if sprints and len(sprints) > 0:
                # Sprint is in format: "com.atlassian.greenhopper.service.sprint.Sprint@xxxxx[id=1234,name=Sprint Name,...]"
                sprint_str = sprints[0] if isinstance(sprints, list) else sprints
                if isinstance(sprint_str, str) and "name=" in sprint_str:
                    # Extract name from sprint string
                    name_start = sprint_str.find("name=") + 5
                    name_end = sprint_str.find(",", name_start)
                    if name_end == -1:
                        name_end = sprint_str.find("]", name_start)
                    ticket_data["sprint"] = sprint_str[name_start:name_end]

            # Epic link
            if fields.get(epic_link_field):
                ticket_data["epic"] = fields[epic_link_field]

            # Acceptance Criteria - only if field mapping is available
            if field_mappings and "acceptance_criteria" in field_mappings:
                ac_field_id = field_mappings["acceptance_criteria"].get("id")
                if ac_field_id and fields.get(ac_field_id):
                    ticket_data["acceptance_criteria"] = fields[ac_field_id]

            # Git Pull Request
            if fields.get(git_pr_field):
                ticket_data["git_pull_request"] = fields[git_pr_field]

            # Changelog (if requested)
            if include_changelog:
                changelog = data.get("changelog", {})
                ticket_data["changelog"] = changelog

            return ticket_data

        except (JiraNotFoundError, JiraAuthError, JiraApiError, JiraConnectionError):
            # Re-raise JIRA-specific exceptions
            raise
        except Exception as e:
            # Wrap unexpected errors
            raise JiraApiError(f"Failed to fetch issue tracker ticket {issue_key}: {e}")

    def list_tickets(
        self,
        assignee: Optional[str] = None,
        status: Optional[str] = None,
        sprint: Optional[str] = None,
        ticket_type: Optional[str] = None,
        status_list: Optional[List[str]] = None,
        field_mappings: Optional[Dict] = None,
    ) -> List[Dict]:
        """List issue tracker tickets with filters using REST API.

        Args:
            assignee: Filter by assignee (use "currentUser()" for current user, will be auto-resolved)
            status: Filter by status (single value, deprecated in favor of status_list)
            sprint: Filter by sprint name
            ticket_type: Filter by ticket type (Story, Bug, etc.)
            status_list: Filter by multiple status values (takes precedence over status)
            field_mappings: Optional field mappings dict from config to resolve custom field IDs

        Returns:
            List of ticket dictionaries with keys: key, type, status, summary, sprint, points, assignee

        Raises:
            JiraApiError: If API request fails
            JiraAuthError: If authentication fails
            JiraConnectionError: If connection fails
        """
        try:
            # Resolve field IDs from field_mappings
            story_points_field = None
            sprint_field = None
            epic_link_field = None

            if field_mappings:
                story_points_field = field_mappings.get("story_points", {}).get("id")
                sprint_field = field_mappings.get("sprint", {}).get("id")
                epic_link_field = field_mappings.get("epic_link", {}).get("id")

            # Build JQL query
            jql_parts = []

            # Resolve currentUser() or $(jira me) to actual username
            if assignee:
                if assignee in ("currentUser()", "$(jira me)"):
                    jql_parts.append("assignee = currentUser()")
                else:
                    jql_parts.append(f'assignee = "{assignee}"')

            # Support both single status and list of statuses
            if status_list:
                # Multiple statuses - use IN clause
                statuses_str = ", ".join([f'"{s}"' for s in status_list])
                jql_parts.append(f'status IN ({statuses_str})')
            elif status:
                # Single status - legacy support
                jql_parts.append(f'status = "{status}"')

            if sprint:
                if sprint == "IS NOT EMPTY":
                    jql_parts.append("sprint is not EMPTY")
                else:
                    jql_parts.append(f'sprint = "{sprint}"')

            if ticket_type:
                jql_parts.append(f'type = "{ticket_type}"')

            jql = " AND ".join(jql_parts) if jql_parts else "assignee = currentUser()"

            # Add ordering
            jql += " ORDER BY updated DESC"

            # Build fields list dynamically
            # Note: 'created' and 'updated' are returned at the root level of the issue object
            # (alongside 'key' and 'fields'), not inside the 'fields' object
            fields_list = f"created,updated,issuetype,status,summary,assignee,{story_points_field},{sprint_field},{epic_link_field}"

            # Make API request
            response = self._api_request(
                "GET",
                "/rest/api/2/search",
                params={
                    "jql": jql,
                    "maxResults": 100,
                    "fields": fields_list
                }
            )

            if response.status_code == 401 or response.status_code == 403:
                raise JiraAuthError(
                    "Authentication failed when listing tickets",
                    status_code=response.status_code
                )
            elif response.status_code != 200:
                raise JiraApiError(
                    "Failed to list tickets",
                    status_code=response.status_code,
                    response_text=response.text
                )

            data = response.json()
            issues = data.get("issues", [])

            tickets = []
            for issue in issues:
                issue_key= issue.get("key")
                fields = issue.get("fields", {})

                ticket_data = {
                    "key": issue_key,
                    "type": fields.get("issuetype", {}).get("name"),
                    "status": fields.get("status", {}).get("name"),
                    "summary": fields.get("summary"),
                    "assignee": fields.get("assignee", {}).get("displayName") if fields.get("assignee") else None,
                    "updated": issue.get("updated"),  # Timestamp from issue root (ISO format)
                }

                # Story points
                if fields.get(story_points_field):
                    try:
                        ticket_data["points"] = int(fields[story_points_field])
                    except (ValueError, TypeError):
                        pass

                # Sprint (get first sprint if multiple)
                sprints = fields.get(sprint_field, [])
                if sprints and len(sprints) > 0:
                    sprint_str = sprints[0] if isinstance(sprints, list) else sprints
                    if isinstance(sprint_str, str) and "name=" in sprint_str:
                        name_start = sprint_str.find("name=") + 5
                        name_end = sprint_str.find(",", name_start)
                        if name_end == -1:
                            name_end = sprint_str.find("]", name_start)
                        ticket_data["sprint"] = sprint_str[name_start:name_end]

                # Epic link
                if fields.get(epic_link_field):
                    ticket_data["epic"] = fields[epic_link_field]

                tickets.append(ticket_data)

            return tickets

        except (JiraAuthError, JiraApiError, JiraConnectionError):
            # Re-raise JIRA-specific exceptions
            raise
        except Exception as e:
            # Wrap unexpected errors
            raise JiraApiError(f"Failed to list tickets: {e}")

    def get_child_issues(
        self,
        parent_key: str,
        field_mappings: Optional[Dict] = None,
    ) -> List[Dict]:
        """Get all child issues for a parent issue (subtasks and epic children).

        Uses JQL to find:
        - Direct subtasks (where parent field = parent_key)
        - Stories/tasks linked via Epic Link (where Epic Link = parent_key)

        Args:
            parent_key: issue key of the parent issue (e.g., PROJ-12345)
            field_mappings: Optional field mappings dict from config to resolve custom field IDs

        Returns:
            List of child issue dictionaries with keys: key, type, status, summary, assignee
            Sorted by key in ascending order

        Raises:
            JiraApiError: If API request fails
            JiraAuthError: If authentication fails
            JiraConnectionError: If connection fails
        """
        try:
            # Build JQL query to find both subtasks and epic children
            # JIRA JQL uses field names, not field IDs
            # For Epic Link, we use "Epic Link" in JQL even though the field ID is customfield_XXXXX
            jql_parts = [f'parent = {parent_key}']

            # Add epic children search if epic_link field is configured
            if field_mappings and field_mappings.get("epic_link"):
                # Use the standard "Epic Link" field name in JQL
                jql_parts.append(f'"Epic Link" = {parent_key}')

            # Combine with OR
            jql = " OR ".join(jql_parts)

            # Add ordering by key
            jql += " ORDER BY key ASC"

            # Build fields list - we need just the basic info
            fields_list = "issuetype,status,summary,assignee"

            # Make API request
            response = self._api_request(
                "GET",
                "/rest/api/2/search",
                params={
                    "jql": jql,
                    "maxResults": 100,
                    "fields": fields_list
                }
            )

            if response.status_code == 401 or response.status_code == 403:
                raise JiraAuthError(
                    "Authentication failed when fetching child issues",
                    status_code=response.status_code
                )
            elif response.status_code != 200:
                raise JiraApiError(
                    f"Failed to fetch child issues for {parent_key}",
                    status_code=response.status_code,
                    response_text=response.text
                )

            data = response.json()
            issues = data.get("issues", [])

            children = []
            for issue in issues:
                issue_key= issue.get("key")
                fields = issue.get("fields", {})

                child_data = {
                    "key": issue_key,
                    "type": fields.get("issuetype", {}).get("name"),
                    "status": fields.get("status", {}).get("name"),
                    "summary": fields.get("summary"),
                    "assignee": fields.get("assignee", {}).get("displayName") if fields.get("assignee") else None,
                }

                children.append(child_data)

            return children

        except (JiraAuthError, JiraApiError, JiraConnectionError):
            # Re-raise JIRA-specific exceptions
            raise
        except Exception as e:
            # Wrap unexpected errors
            raise JiraApiError(f"Failed to fetch child issues for {parent_key}: {e}")

    def update_ticket_field(self, issue_key: str, field_name: str, value: str) -> None:
        """Update a specific field in a issue tracker ticket.

        Args:
            issue_key: issue tracker key
            field_name: Field name or custom field ID (e.g., "customfield_12310220" for PR link)
            value: New value for the field

        Raises:
            JiraNotFoundError: If ticket not found (404)
            JiraValidationError: If field validation fails (400)
            JiraApiError: If API request fails
            JiraAuthError: If authentication fails
            JiraConnectionError: If connection fails
        """
        try:
            payload = {
                "fields": {
                    field_name: value
                }
            }

            response = self._api_request(
                "PUT",
                f"/rest/api/2/issue/{issue_key}",
                json=payload
            )

            if response.status_code == 204:
                return  # Success
            elif response.status_code == 404:
                raise JiraNotFoundError(
                    f"Cannot update field: issue tracker ticket {issue_key} not found",
                    resource_type="issue",
                    resource_id=issue_key
                )
            elif response.status_code == 401 or response.status_code == 403:
                raise JiraAuthError(
                    f"Authentication failed when updating field in {issue_key}",
                    status_code=response.status_code
                )
            elif response.status_code == 400:
                # Parse validation errors
                try:
                    error_data = response.json()
                    error_messages = error_data.get("errorMessages", [])
                    field_errors = error_data.get("errors", {})

                    raise JiraValidationError(
                        f"Field update failed for {issue_key}",
                        field_errors=field_errors,
                        error_messages=error_messages
                    )
                except JiraValidationError:
                    raise
                except Exception:
                    raise JiraApiError(
                        f"Field update failed for {issue_key}",
                        status_code=response.status_code,
                        response_text=response.text
                    )
            else:
                raise JiraApiError(
                    f"Field update failed for {issue_key}",
                    status_code=response.status_code,
                    response_text=response.text
                )

        except (JiraNotFoundError, JiraAuthError, JiraApiError, JiraValidationError, JiraConnectionError):
            # Re-raise JIRA-specific exceptions
            raise
        except Exception as e:
            # Wrap unexpected errors
            raise JiraApiError(f"Failed to update field {field_name} in {issue_key}: {e}")

    def update_issue(self, issue_key: str, payload: Dict) -> None:
        """Update a JIRA issue with multiple fields.

        Args:
            issue_key: issue tracker key
            payload: Update payload with fields to update (must have "fields" key)
                    Example: {"fields": {"description": "New desc", "priority": {"name": "Major"}}}

        Raises:
            JiraNotFoundError: If ticket not found (404)
            JiraValidationError: If field validation fails (400)
            JiraApiError: If API request fails
            JiraAuthError: If authentication fails
            JiraConnectionError: If connection fails
        """
        try:
            response = self._api_request(
                "PUT",
                f"/rest/api/2/issue/{issue_key}",
                json=payload
            )

            if response.status_code == 204:
                return  # Success
            elif response.status_code == 404:
                raise JiraNotFoundError(
                    f"Cannot update issue: issue tracker ticket {issue_key} not found",
                    resource_type="issue",
                    resource_id=issue_key
                )
            elif response.status_code == 401 or response.status_code == 403:
                raise JiraAuthError(
                    f"Authentication failed when updating {issue_key}",
                    status_code=response.status_code
                )
            elif response.status_code == 400:
                # Parse error response for detailed error messages
                try:
                    error_data = response.json()
                    error_messages = error_data.get("errorMessages", [])
                    field_errors = error_data.get("errors", {})

                    # Build field errors dict with human-readable field names
                    readable_field_errors = {}
                    for field_id, error_msg in field_errors.items():
                        field_name = self._get_field_name(field_id)
                        readable_field_errors[field_name] = error_msg

                    raise JiraValidationError(
                        f"Update failed for {issue_key}",
                        field_errors=readable_field_errors,
                        error_messages=error_messages
                    )

                except JiraValidationError:
                    raise
                except Exception:
                    raise JiraApiError(
                        f"Update failed for {issue_key}",
                        status_code=response.status_code,
                        response_text=response.text
                    )
            else:
                raise JiraApiError(
                    f"Update failed for {issue_key}",
                    status_code=response.status_code,
                    response_text=response.text
                )

        except (JiraNotFoundError, JiraAuthError, JiraApiError, JiraValidationError, JiraConnectionError):
            # Re-raise JIRA-specific exceptions
            raise
        except Exception as e:
            # Wrap unexpected errors
            raise JiraApiError(f"Failed to update issue {issue_key}: {e}")

    def get_ticket_pr_links(self, issue_key: str, field_mappings: Optional[Dict] = None) -> str:
        """Get current PR/MR links from issue tracker ticket.

        Args:
            issue_key: issue tracker key
            field_mappings: Optional field mappings dict from config to resolve custom field IDs
                          (e.g., {"git_pull_request": {"id": "customfield_12310220"}})

        Returns:
            Current PR links (comma-separated), empty string if field not set

        Raises:
            JiraNotFoundError: If ticket not found or git_pull_request field not available
            JiraApiError: If API request fails
            JiraAuthError: If authentication fails
            JiraConnectionError: If connection fails
        """
        try:
            # Resolve field ID from field_mappings
            git_pr_field = None
            if field_mappings:
                git_pr_field = field_mappings.get("git_pull_request", {}).get("id")

            # If not found in cache, discover it dynamically
            if not git_pr_field:
                from devflow.jira.field_mapper import JiraFieldMapper

                field_mapper = JiraFieldMapper(self, field_mappings)
                editable_mappings = field_mapper.discover_editable_fields(issue_key)

                if "git_pull_request" in editable_mappings:
                    git_pr_field = editable_mappings["git_pull_request"]["id"]
                else:
                    # Field truly doesn't exist for this ticket
                    raise JiraNotFoundError(
                        f"git_pull_request field not available for {issue_key}",
                        resource_type="field",
                        resource_id="git_pull_request"
                    )

            response = self._api_request(
                "GET",
                f"/rest/api/2/issue/{issue_key}",
                params={"fields": git_pr_field}
            )

            if response.status_code == 404:
                raise JiraNotFoundError(
                    f"issue tracker ticket {issue_key} not found",
                    resource_type="issue",
                    resource_id=issue_key
                )
            elif response.status_code == 401 or response.status_code == 403:
                raise JiraAuthError(
                    f"Authentication failed when getting PR links for {issue_key}",
                    status_code=response.status_code
                )
            elif response.status_code == 200:
                data = response.json()
                field_value = data.get("fields", {}).get(git_pr_field, "")

                # Handle multiurl fields that return lists
                if isinstance(field_value, list):
                    # Convert list of URLs to comma-separated string
                    return ','.join(field_value) if field_value else ""

                return field_value if field_value else ""
            else:
                raise JiraApiError(
                    f"Failed to get PR links for {issue_key}",
                    status_code=response.status_code,
                    response_text=response.text
                )

        except (JiraNotFoundError, JiraAuthError, JiraApiError, JiraConnectionError):
            # Re-raise JIRA-specific exceptions
            raise
        except Exception as e:
            # Wrap unexpected errors
            raise JiraApiError(f"Failed to get PR links for {issue_key}: {e}")

    def _get_parent_field_id(self, issue_type: str, field_mapper) -> Optional[str]:
        """Get the parent field ID for a given issue type using parent_field_mapping.

        Args:
            issue_type: JIRA issue type (e.g., "bug", "story", "task", "sub-task")
            field_mapper: JiraFieldMapper instance for field ID lookup

        Returns:
            Field ID string (e.g., "customfield_12311140" for epic_link, or "parent" for sub-task)
            Returns None if parent_field_mapping not configured or field not found
        """
        try:
            from devflow.config.loader import ConfigLoader
            config_loader = ConfigLoader()
            config = config_loader.load_config()

            if not config or not config.jira or not config.jira.parent_field_mapping:
                # Fallback to epic_link for backward compatibility
                return field_mapper.get_field_id("epic_link")

            # Get logical field name from parent_field_mapping (e.g., "epic_link" or "parent")
            issue_type_lower = issue_type.lower()
            logical_field_name = config.jira.parent_field_mapping.get(issue_type_lower)

            if not logical_field_name:
                # Fallback to epic_link for backward compatibility
                return field_mapper.get_field_id("epic_link")

            # If logical field is "parent" (standard field for sub-tasks), return it directly
            if logical_field_name == "parent":
                return "parent"

            # Otherwise, look up the custom field ID from field_mappings
            return field_mapper.get_field_id(logical_field_name)

        except Exception:
            # Fallback to epic_link for backward compatibility
            return field_mapper.get_field_id("epic_link")

    def create_bug(
        self,
        summary: str,
        description: str,
        priority: str,
        project_key: str,
        workstream: str,
        field_mapper,
        parent: Optional[str] = None,
        affected_version: Optional[str] = None,
        components: Optional[List[str]] = None,
        **custom_fields
    ) -> str:
        """Create a JIRA bug issue.

        Args:
            summary: Bug summary
            description: Bug description (using template from AGENTS.md)
            priority: Bug priority (Critical, Major, Normal, Minor)
            project_key: JIRA project key (e.g., "PROJ")
            workstream: Workstream value (e.g., "Platform", "Hosted Services")
            field_mapper: JiraFieldMapper instance for field ID lookup
            parent: Optional parent issue key (epic for bugs, uses parent_field_mapping from config)
            affected_version: Affected version (optional, will prompt if not provided)
            components: List of component names (default: [])
            **custom_fields: Additional custom fields (field_id: value pairs)

        Returns:
            Created issue key (e.g., "PROJ-12345")

        Raises:
            JiraValidationError: If creation fails due to validation errors (400)
            JiraApiError: If API request fails
            JiraAuthError: If authentication fails
            JiraConnectionError: If connection fails
        """
        if components is None:
            components = []

        # Get field IDs from mapper
        workstream_field = field_mapper.get_field_id("workstream")

        # Get parent field ID based on parent_field_mapping from config
        parent_field_id = self._get_parent_field_id("bug", field_mapper)

        # Build payload
        payload = {
            "fields": {
                "project": {"key": project_key},
                "issuetype": {"name": "Bug"},
                "summary": summary,
                "description": description,
                "priority": {"name": priority},
                "components": [{"name": comp} for comp in components],
                "versions": [{"name": affected_version}],
            }
        }

        # Add workstream if field is configured
        if workstream_field:
            payload["fields"][workstream_field] = [{"value": workstream}]

        # Set acceptance criteria if required based on field_mappings
        self._set_required_acceptance_criteria(payload, "Bug", field_mapper, description)

        # Add parent link if provided and field is configured
        if parent and parent_field_id:
            payload["fields"][parent_field_id] = parent

        # Add custom fields
        for field_id, field_value in custom_fields.items():
            if field_value is not None:
                payload["fields"][field_id] = field_value

        try:
            response = self._api_request(
                "POST",
                "/rest/api/2/issue",
                json=payload
            )

            if response.status_code == 201:
                data = response.json()
                return data["key"]
            elif response.status_code == 401 or response.status_code == 403:
                raise JiraAuthError(
                    "Authentication failed when creating bug",
                    status_code=response.status_code
                )
            elif response.status_code == 400:
                # Parse validation errors
                try:
                    error_data = response.json()
                    error_messages = error_data.get("errorMessages", [])
                    field_errors = error_data.get("errors", {})

                    raise JiraValidationError(
                        "Failed to create bug",
                        field_errors=field_errors,
                        error_messages=error_messages
                    )
                except JiraValidationError:
                    raise
                except Exception:
                    raise JiraApiError(
                        "Failed to create bug",
                        status_code=response.status_code,
                        response_text=response.text
                    )
            else:
                raise JiraApiError(
                    "Failed to create bug",
                    status_code=response.status_code,
                    response_text=response.text
                )

        except (JiraAuthError, JiraApiError, JiraValidationError, JiraConnectionError):
            # Re-raise JIRA-specific exceptions
            raise
        except Exception as e:
            # Wrap unexpected errors
            raise JiraApiError(f"Failed to create bug: {e}")

    def create_story(
        self,
        summary: str,
        description: str,
        priority: str,
        project_key: str,
        workstream: str,
        field_mapper,
        parent: Optional[str] = None,
        components: Optional[List[str]] = None,
        **custom_fields
    ) -> str:
        """Create a JIRA story issue.

        Args:
            summary: Story summary
            description: Story description (using template from AGENTS.md)
            priority: Story priority (Critical, Major, Normal, Minor)
            project_key: JIRA project key (e.g., "PROJ")
            workstream: Workstream value (e.g., "Platform", "Hosted Services")
            field_mapper: JiraFieldMapper instance for field ID lookup
            parent: Optional parent issue key (epic for stories, uses parent_field_mapping from config)
            components: List of component names (default: [])
            **custom_fields: Additional custom fields (field_id: value pairs)

        Returns:
            Created issue key (e.g., "PROJ-12345")

        Raises:
            JiraValidationError: If creation fails due to validation errors (400)
            JiraApiError: If API request fails
            JiraAuthError: If authentication fails
            JiraConnectionError: If connection fails
        """
        if components is None:
            components = []

        # Get field IDs from mapper
        workstream_field = field_mapper.get_field_id("workstream")

        # Get parent field ID based on parent_field_mapping from config
        parent_field_id = self._get_parent_field_id("story", field_mapper)

        # Build payload
        payload = {
            "fields": {
                "project": {"key": project_key},
                "issuetype": {"name": "Story"},
                "summary": summary,
                "description": description,
                "priority": {"name": priority},
                "components": [{"name": comp} for comp in components],
            }
        }

        # Add workstream if field is configured
        if workstream_field:
            payload["fields"][workstream_field] = [{"value": workstream}]

        # Set acceptance criteria if required based on field_mappings
        self._set_required_acceptance_criteria(payload, "Story", field_mapper, description)

        # Add parent link if provided and field is configured
        if parent and parent_field_id:
            payload["fields"][parent_field_id] = parent

        # Add custom fields
        for field_id, field_value in custom_fields.items():
            if field_value is not None:
                payload["fields"][field_id] = field_value

        try:
            response = self._api_request(
                "POST",
                "/rest/api/2/issue",
                json=payload
            )

            if response.status_code == 201:
                data = response.json()
                return data["key"]
            elif response.status_code == 401 or response.status_code == 403:
                raise JiraAuthError(
                    "Authentication failed when creating story",
                    status_code=response.status_code
                )
            elif response.status_code == 400:
                # Parse validation errors
                try:
                    error_data = response.json()
                    error_messages = error_data.get("errorMessages", [])
                    field_errors = error_data.get("errors", {})

                    raise JiraValidationError(
                        "Failed to create story",
                        field_errors=field_errors,
                        error_messages=error_messages
                    )
                except JiraValidationError:
                    raise
                except Exception:
                    raise JiraApiError(
                        "Failed to create story",
                        status_code=response.status_code,
                        response_text=response.text
                    )
            else:
                raise JiraApiError(
                    "Failed to create story",
                    status_code=response.status_code,
                    response_text=response.text
                )

        except (JiraAuthError, JiraApiError, JiraValidationError, JiraConnectionError):
            # Re-raise JIRA-specific exceptions
            raise
        except Exception as e:
            # Wrap unexpected errors
            raise JiraApiError(f"Failed to create story: {e}")

    def create_task(
        self,
        summary: str,
        description: str,
        priority: str,
        project_key: str,
        workstream: str,
        field_mapper,
        parent: Optional[str] = None,
        components: Optional[List[str]] = None,
        **custom_fields
    ) -> str:
        """Create a JIRA task issue.

        Args:
            summary: Task summary
            description: Task description (using template from AGENTS.md)
            priority: Task priority (Critical, Major, Normal, Minor)
            project_key: JIRA project key (e.g., "PROJ")
            workstream: Workstream value (e.g., "Platform", "Hosted Services")
            field_mapper: JiraFieldMapper instance for field ID lookup
            parent: Optional parent issue key (epic for tasks, uses parent_field_mapping from config)
            components: List of component names (default: [])
            **custom_fields: Additional custom fields (field_id: value pairs)

        Returns:
            Created issue key (e.g., "PROJ-12345")

        Raises:
            JiraValidationError: If creation fails due to validation errors (400)
            JiraApiError: If API request fails
            JiraAuthError: If authentication fails
            JiraConnectionError: If connection fails
        """
        if components is None:
            components = []

        # Get field IDs from mapper
        workstream_field = field_mapper.get_field_id("workstream")

        # Get parent field ID based on parent_field_mapping from config
        parent_field_id = self._get_parent_field_id("task", field_mapper)

        # Build payload
        payload = {
            "fields": {
                "project": {"key": project_key},
                "issuetype": {"name": "Task"},
                "summary": summary,
                "description": description,
                "priority": {"name": priority},
                "components": [{"name": comp} for comp in components],
            }
        }

        # Add workstream if field is configured
        if workstream_field:
            payload["fields"][workstream_field] = [{"value": workstream}]

        # Set acceptance criteria if required based on field_mappings
        self._set_required_acceptance_criteria(payload, "Task", field_mapper, description)

        # Add parent link if provided and field is configured
        if parent and parent_field_id:
            payload["fields"][parent_field_id] = parent

        # Add custom fields
        for field_id, field_value in custom_fields.items():
            if field_value is not None:
                payload["fields"][field_id] = field_value

        try:
            response = self._api_request(
                "POST",
                "/rest/api/2/issue",
                json=payload
            )

            if response.status_code == 201:
                data = response.json()
                return data["key"]
            elif response.status_code == 401 or response.status_code == 403:
                raise JiraAuthError(
                    "Authentication failed when creating task",
                    status_code=response.status_code
                )
            elif response.status_code == 400:
                # Parse validation errors
                try:
                    error_data = response.json()
                    error_messages = error_data.get("errorMessages", [])
                    field_errors = error_data.get("errors", {})

                    raise JiraValidationError(
                        "Failed to create task",
                        field_errors=field_errors,
                        error_messages=error_messages
                    )
                except JiraValidationError:
                    raise
                except Exception:
                    raise JiraApiError(
                        "Failed to create task",
                        status_code=response.status_code,
                        response_text=response.text
                    )
            else:
                raise JiraApiError(
                    "Failed to create task",
                    status_code=response.status_code,
                    response_text=response.text
                )

        except (JiraAuthError, JiraApiError, JiraValidationError, JiraConnectionError):
            # Re-raise JIRA-specific exceptions
            raise
        except Exception as e:
            # Wrap unexpected errors
            raise JiraApiError(f"Failed to create task: {e}")

    def create_epic(
        self,
        summary: str,
        description: str,
        priority: str,
        project_key: str,
        workstream: str,
        field_mapper,
        parent: Optional[str] = None,
        components: Optional[List[str]] = None,
        **custom_fields
    ) -> str:
        """Create a JIRA epic issue.

        Args:
            summary: Epic summary
            description: Epic description (using template from AGENTS.md)
            priority: Epic priority (Critical, Major, Normal, Minor)
            project_key: JIRA project key (e.g., "PROJ")
            workstream: Workstream value (e.g., "Platform", "Hosted Services")
            field_mapper: JiraFieldMapper instance for field ID lookup
            parent: Optional parent issue key (not typically used for epics as they are top-level)
            components: List of component names (default: [])
            **custom_fields: Additional custom fields (field_id: value pairs)

        Returns:
            Created issue key (e.g., "PROJ-12345")

        Raises:
            JiraValidationError: If creation fails due to validation errors (400)
            JiraApiError: If API request fails
            JiraAuthError: If authentication fails
            JiraConnectionError: If connection fails

        Note:
            Epic Name custom field is optional in modern JIRA. If discovered via field_mapper,
            it will be populated with the summary. Epics are typically top-level containers
            and do not have parent links.
        """
        if components is None:
            components = []

        # Get field IDs from mapper
        workstream_field = field_mapper.get_field_id("workstream")

        # Build payload
        payload = {
            "fields": {
                "project": {"key": project_key},
                "issuetype": {"name": "Epic"},
                "summary": summary,
                "description": description,
                "priority": {"name": priority},
                "components": [{"name": comp} for comp in components],
            }
        }

        # Add workstream if field is configured
        if workstream_field:
            payload["fields"][workstream_field] = [{"value": workstream}]

        # Set acceptance criteria if required based on field_mappings
        self._set_required_acceptance_criteria(payload, "Epic", field_mapper, description)

        # Optional: Add Epic Name field if discovered (optional in modern JIRA)
        epic_name_field = field_mapper.get_field_id("epic_name")
        if epic_name_field:
            payload["fields"][epic_name_field] = summary

        # Note: Epics typically don't have parent links as they are top-level containers
        # However, if parent is provided and a parent field exists, add it
        if parent:
            parent_field_id = self._get_parent_field_id("epic", field_mapper)
            if parent_field_id:
                payload["fields"][parent_field_id] = parent

        # Add custom fields
        for field_id, field_value in custom_fields.items():
            if field_value is not None:
                payload["fields"][field_id] = field_value

        try:
            response = self._api_request(
                "POST",
                "/rest/api/2/issue",
                json=payload
            )

            if response.status_code == 201:
                data = response.json()
                return data["key"]
            elif response.status_code == 401 or response.status_code == 403:
                raise JiraAuthError(
                    "Authentication failed when creating epic",
                    status_code=response.status_code
                )
            elif response.status_code == 400:
                # Parse validation errors
                try:
                    error_data = response.json()
                    error_messages = error_data.get("errorMessages", [])
                    field_errors = error_data.get("errors", {})

                    raise JiraValidationError(
                        "Failed to create epic",
                        field_errors=field_errors,
                        error_messages=error_messages
                    )
                except JiraValidationError:
                    raise
                except Exception:
                    raise JiraApiError(
                        "Failed to create epic",
                        status_code=response.status_code,
                        response_text=response.text
                    )
            else:
                raise JiraApiError(
                    "Failed to create epic",
                    status_code=response.status_code,
                    response_text=response.text
                )

        except (JiraAuthError, JiraApiError, JiraValidationError, JiraConnectionError):
            # Re-raise JIRA-specific exceptions
            raise
        except Exception as e:
            # Wrap unexpected errors
            raise JiraApiError(f"Failed to create epic: {e}")

    def create_spike(
        self,
        summary: str,
        description: str,
        priority: str,
        project_key: str,
        workstream: str,
        field_mapper,
        parent: Optional[str] = None,
        components: Optional[List[str]] = None,
        **custom_fields
    ) -> str:
        """Create a JIRA spike issue.

        Args:
            summary: Spike summary
            description: Spike description (using template from AGENTS.md)
            priority: Spike priority (Critical, Major, Normal, Minor)
            project_key: JIRA project key (e.g., "PROJ")
            workstream: Workstream value (e.g., "Platform", "Hosted Services")
            field_mapper: JiraFieldMapper instance for field ID lookup
            parent: Optional parent issue key (epic for spikes, uses parent_field_mapping from config)
            components: List of component names (default: [])
            **custom_fields: Additional custom fields (field_id: value pairs)

        Returns:
            Created issue key (e.g., "PROJ-12345")

        Raises:
            JiraValidationError: If creation fails due to validation errors (400)
            JiraApiError: If API request fails
            JiraAuthError: If authentication fails
            JiraConnectionError: If connection fails

        Note:
            Spikes should typically be linked to an Epic via the parent parameter.
        """
        if components is None:
            components = []

        # Get field IDs from mapper
        workstream_field = field_mapper.get_field_id("workstream")

        # Get parent field ID based on parent_field_mapping from config
        parent_field_id = self._get_parent_field_id("spike", field_mapper)

        # Build payload
        payload = {
            "fields": {
                "project": {"key": project_key},
                "issuetype": {"name": "Spike"},
                "summary": summary,
                "description": description,
                "priority": {"name": priority},
                "components": [{"name": comp} for comp in components],
            }
        }

        # Add workstream if field is configured
        if workstream_field:
            payload["fields"][workstream_field] = [{"value": workstream}]

        # Set acceptance criteria if required based on field_mappings
        self._set_required_acceptance_criteria(payload, "Spike", field_mapper, description)

        # Add parent link if provided and field is configured
        if parent and parent_field_id:
            payload["fields"][parent_field_id] = parent

        # Add custom fields
        for field_id, field_value in custom_fields.items():
            if field_value is not None:
                payload["fields"][field_id] = field_value

        try:
            response = self._api_request(
                "POST",
                "/rest/api/2/issue",
                json=payload
            )

            if response.status_code == 201:
                data = response.json()
                return data["key"]
            elif response.status_code == 401 or response.status_code == 403:
                raise JiraAuthError(
                    "Authentication failed when creating spike",
                    status_code=response.status_code
                )
            elif response.status_code == 400:
                # Parse validation errors
                try:
                    error_data = response.json()
                    error_messages = error_data.get("errorMessages", [])
                    field_errors = error_data.get("errors", {})

                    raise JiraValidationError(
                        "Failed to create spike",
                        field_errors=field_errors,
                        error_messages=error_messages
                    )
                except JiraValidationError:
                    raise
                except Exception:
                    raise JiraApiError(
                        "Failed to create spike",
                        status_code=response.status_code,
                        response_text=response.text
                    )
            else:
                raise JiraApiError(
                    "Failed to create spike",
                    status_code=response.status_code,
                    response_text=response.text
                )

        except (JiraAuthError, JiraApiError, JiraValidationError, JiraConnectionError):
            # Re-raise JIRA-specific exceptions
            raise
        except Exception as e:
            # Wrap unexpected errors
            raise JiraApiError(f"Failed to create spike: {e}")

    def _set_required_acceptance_criteria(
        self,
        payload: Dict,
        issue_type: str,
        field_mapper,
        description: str
    ) -> None:
        """Set acceptance criteria field if required for the issue type.

        Checks field_mappings metadata to determine if acceptance_criteria is marked
        as required for the given issue type. If required but not extracted from the
        description, sets a default placeholder value.

        Args:
            payload: The JIRA API payload dict with "fields" key (modified in-place)
            issue_type: The JIRA issue type (e.g., "Bug", "Story", "Task")
            field_mapper: JiraFieldMapper instance for field metadata lookup
            description: Issue description to attempt extraction from

        Note:
            Modifies the payload dict in-place by adding acceptance_criteria field if needed.
        """
        # Get the acceptance criteria field ID
        acceptance_criteria_field = field_mapper.get_field_id("acceptance_criteria")

        # If field not configured, skip setting acceptance criteria
        if not acceptance_criteria_field:
            return

        # Extract acceptance criteria from description if present
        acceptance_criteria = self._extract_acceptance_criteria(description)

        # Check if acceptance_criteria is required for this issue type
        ac_field_info = field_mapper.get_field_info("acceptance_criteria")
        is_required = ac_field_info and issue_type in ac_field_info.get("required_for", [])

        # Set acceptance criteria if provided or if required
        if acceptance_criteria or is_required:
            if not acceptance_criteria:
                # Use default placeholder if required but not provided
                acceptance_criteria = f"TBD: Define acceptance criteria for this {issue_type.lower()}"
            payload["fields"][acceptance_criteria_field] = acceptance_criteria

    def _extract_acceptance_criteria(self, description: str) -> str:
        """Extract acceptance criteria from issue description.

        This method attempts to extract the acceptance criteria section
        from a JIRA description that follows the templates in AGENTS.md.

        Args:
            description: Issue description text

        Returns:
            Extracted acceptance criteria or empty string if not found
        """
        # Look for common patterns in bug/story templates
        # For now, return empty string - caller can set acceptance criteria explicitly
        # This can be enhanced later to parse from description
        return ""

    def get_issue_link_types(self) -> List[Dict]:
        """Fetch available issue link types from JIRA.

        Returns:
            List of dicts with keys: id, name, inward, outward
            Inward/outward are the relationship descriptions shown in UI

        Example return:
            [
                {"id": "10000", "name": "Blocks",
                 "inward": "is blocked by", "outward": "blocks"},
                {"id": "10001", "name": "Relates",
                 "inward": "relates to", "outward": "relates to"}
            ]

        Raises:
            JiraApiError: If API request fails
            JiraAuthError: If authentication fails
            JiraConnectionError: If connection fails
        """
        response = self._api_request("GET", "/rest/api/2/issueLinkType")

        if response.status_code == 401 or response.status_code == 403:
            raise JiraAuthError(
                "Authentication failed when fetching issue link types",
                status_code=response.status_code
            )
        elif response.status_code != 200:
            raise JiraApiError(
                "Failed to fetch issue link types",
                status_code=response.status_code,
                response_text=response.text
            )

        data = response.json()
        return data.get("issueLinkTypes", [])

    def link_issues(
        self,
        issue_key: str,
        link_to_issue_key: str,
        link_type_description: str,
        comment: Optional[str] = None
    ) -> None:
        """Link two JIRA issues together.

        Args:
            issue_key: The issue being created/updated
            link_to_issue_key: The issue key to link to
            link_type_description: Relationship description from UI
                                   (e.g., "blocks", "is blocked by", "relates to")
            comment: Optional comment for the link

        The method determines direction based on link_type_description:
        - If matches "outward" description: issue_key is outwardIssue
        - If matches "inward" description: issue_key is inwardIssue

        Raises:
            JiraValidationError: If link description not found
            JiraNotFoundError: If either issue not found
            JiraApiError: If API request fails
            JiraAuthError: If authentication fails
            JiraConnectionError: If connection fails
        """
        # 1. Fetch link types to find matching description
        link_types = self.get_issue_link_types()

        # 2. Find link type and determine direction
        link_type_name = None
        is_outward = False

        for lt in link_types:
            if lt["outward"].lower() == link_type_description.lower():
                link_type_name = lt["name"]
                is_outward = True
                break
            elif lt["inward"].lower() == link_type_description.lower():
                link_type_name = lt["name"]
                is_outward = False
                break

        if not link_type_name:
            # Build list of available options
            available = []
            for lt in link_types:
                available.append(lt["inward"])
                available.append(lt["outward"])

            raise JiraValidationError(
                f"Invalid linked issue type: '{link_type_description}'",
                error_messages=[
                    f"Available types: {', '.join(sorted(set(available)))}"
                ]
            )

        # 3. Build payload with correct inward/outward placement
        payload = {
            "type": {"name": link_type_name}
        }

        if is_outward:
            payload["outwardIssue"] = {"key": issue_key}
            payload["inwardIssue"] = {"key": link_to_issue_key}
        else:
            payload["inwardIssue"] = {"key": issue_key}
            payload["outwardIssue"] = {"key": link_to_issue_key}

        if comment:
            payload["comment"] = {"body": comment}

        # 4. POST to /rest/api/2/issueLink
        response = self._api_request("POST", "/rest/api/2/issueLink", json=payload)

        if response.status_code == 404:
            raise JiraNotFoundError(
                f"Issue not found when creating link",
                resource_type="issue",
                resource_id=f"{issue_key} or {link_to_issue_key}"
            )
        elif response.status_code == 400:
            # Parse field errors from response
            try:
                error_data = response.json()
                error_messages = error_data.get("errorMessages", [])
                field_errors = error_data.get("errors", {})
                raise JiraValidationError(
                    "Validation failed when creating issue link",
                    field_errors=field_errors,
                    error_messages=error_messages
                )
            except (ValueError, KeyError):
                raise JiraApiError(
                    "Failed to create issue link",
                    status_code=response.status_code,
                    response_text=response.text
                )
        elif response.status_code == 401 or response.status_code == 403:
            raise JiraAuthError(
                "Authentication failed when creating issue link",
                status_code=response.status_code
            )
        elif response.status_code != 201:
            raise JiraApiError(
                "Failed to create issue link",
                status_code=response.status_code,
                response_text=response.text
            )
