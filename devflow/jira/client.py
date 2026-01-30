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

        # If URL not in env, try backends/jira.json first (primary source)
        if not self._jira_url:
            try:
                from pathlib import Path
                from devflow.utils.paths import get_cs_home
                import json

                backends_dir = get_cs_home() / "backends"
                jira_backend_config = backends_dir / "jira.json"

                if jira_backend_config.exists():
                    with open(jira_backend_config, 'r') as f:
                        backend_config = json.load(f)
                        self._jira_url = backend_config.get('url')
            except:
                pass

        # If URL still not found, try jira CLI config as fallback
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

    def _add_custom_fields_to_payload(
        self,
        payload: Dict,
        custom_fields: Dict[str, any],
        field_mapper
    ) -> None:
        """Add custom fields to JIRA API payload with proper formatting.

        Args:
            payload: JIRA API payload dict with "fields" key (modified in-place)
            custom_fields: Dictionary of custom field names to values
            field_mapper: JiraFieldMapper instance for field ID lookup

        Note:
            Modifies the payload dict in-place by adding formatted custom fields.
        """
        from devflow.cli.commands.jira_update_command import build_field_value

        for field_name, field_value in custom_fields.items():
            if field_value is None:
                continue
            field_id = field_mapper.get_field_id(field_name)
            if field_id:
                field_info = field_mapper.get_field_info(field_name) or {}
                formatted_value = build_field_value(field_info, str(field_value), field_mapper)
                payload["fields"][field_id] = formatted_value

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

        # Debug: Log API request details (only if DEVAIFLOW_DEBUG=1 and not in JSON output mode)
        import os
        from devflow.cli.utils import is_json_mode

        debug_enabled = os.getenv("DEVAIFLOW_DEBUG") == "1" and not is_json_mode()

        if debug_enabled:
            import json
            import logging
            from rich.console import Console

            logger = logging.getLogger(__name__)
            console = Console()

            # Log request
            logger.debug(f"JIRA API Request - {method} {endpoint}")
            console.print(f"\n[dim]JIRA API Request:[/dim]")
            console.print(f"[dim]{method} {url}[/dim]")

            # Log payload if present
            if 'json' in kwargs:
                logger.debug(f"Payload: {json.dumps(kwargs['json'], indent=2)}")
                console.print("[dim]Payload:[/dim]")
                console.print(f"[dim]{json.dumps(kwargs['json'], indent=2)}[/dim]")

            # Log query params if present
            if 'params' in kwargs:
                logger.debug(f"Params: {kwargs['params']}")
                console.print(f"[dim]Params: {kwargs['params']}[/dim]")

            console.print()

        try:
            response = requests.request(
                method=method,
                url=url,
                headers=headers,
                timeout=timeout,
                **kwargs
            )

            # Debug: Log response (only if DEVAIFLOW_DEBUG=1 and not in JSON output mode)
            if debug_enabled:
                logger.debug(f"Response status: {response.status_code}")
                console.print(f"[dim]Response status: {response.status_code}[/dim]")

                # Log response body for non-2xx responses or if it's small enough
                if response.status_code >= 300 or len(response.text) < 5000:
                    try:
                        response_json = response.json()
                        logger.debug(f"Response: {json.dumps(response_json, indent=2)}")
                        console.print(f"[dim]Response:[/dim]")
                        console.print(f"[dim]{json.dumps(response_json, indent=2)}[/dim]\n")
                    except Exception:
                        # Not JSON or too large
                        logger.debug(f"Response text: {response.text[:500]}")
                        console.print(f"[dim]Response (first 500 chars): {response.text[:500]}[/dim]\n")

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

            # Extract ALL custom fields generically from field_mappings
            if field_mappings:
                for field_name, field_info in field_mappings.items():
                    field_id = field_info.get("id")
                    if not field_id or field_id not in fields:
                        continue

                    field_value = fields[field_id]
                    if field_value is None:
                        continue

                    # Apply type-based transformations
                    field_type = field_info.get("type", "string")
                    field_schema = field_info.get("schema", "")

                    # Number fields - convert to int
                    if field_type == "number":
                        try:
                            field_value = int(field_value)
                        except (ValueError, TypeError):
                            pass

                    # Sprint fields - parse Greenhopper format
                    # Detect by schema containing "sprint" keyword
                    elif "sprint" in str(field_schema).lower() and isinstance(field_value, list) and len(field_value) > 0:
                        sprint_str = field_value[0]
                        if isinstance(sprint_str, str) and "name=" in sprint_str:
                            # Extract name from Greenhopper sprint string format
                            name_start = sprint_str.find("name=") + 5
                            name_end = sprint_str.find(",", name_start)
                            if name_end == -1:
                                name_end = sprint_str.find("]", name_start)
                            field_value = sprint_str[name_start:name_end]

                    # Store field value under its normalized name
                    ticket_data[field_name] = field_value

                    # Backward compatibility aliases (TEMPORARY - should be removed eventually)
                    # TODO: Remove these once all consuming code uses normalized field names
                    if "epic" in field_name and "link" in field_name:
                        ticket_data["epic"] = field_value
                    elif "story" in field_name and "point" in field_name:
                        ticket_data["points"] = field_value

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

            # Extract ALL custom fields generically from field_mappings
            if field_mappings:
                for field_name, field_info in field_mappings.items():
                    field_id = field_info.get("id")
                    if not field_id or field_id not in fields:
                        continue

                    field_value = fields[field_id]
                    if field_value is None:
                        continue

                    # Apply type-based transformations
                    field_type = field_info.get("type", "string")
                    field_schema = field_info.get("schema", "")

                    # Number fields - convert to int
                    if field_type == "number":
                        try:
                            field_value = int(field_value)
                        except (ValueError, TypeError):
                            pass

                    # Sprint fields - parse Greenhopper format
                    # Detect by schema containing "sprint" keyword
                    elif "sprint" in str(field_schema).lower() and isinstance(field_value, list) and len(field_value) > 0:
                        sprint_str = field_value[0]
                        if isinstance(sprint_str, str) and "name=" in sprint_str:
                            # Extract name from Greenhopper sprint string format
                            name_start = sprint_str.find("name=") + 5
                            name_end = sprint_str.find(",", name_start)
                            if name_end == -1:
                                name_end = sprint_str.find("]", name_start)
                            field_value = sprint_str[name_start:name_end]

                    # Store field value under its normalized name
                    ticket_data[field_name] = field_value

                    # Backward compatibility aliases (TEMPORARY - should be removed eventually)
                    # TODO: Remove these once all consuming code uses normalized field names
                    if "epic" in field_name and "link" in field_name:
                        ticket_data["epic"] = field_value
                    elif "story" in field_name and "point" in field_name:
                        ticket_data["points"] = field_value

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
        sprint: Optional[str] = None,  # Deprecated: use field_filters instead
        ticket_type: Optional[str] = None,
        status_list: Optional[List[str]] = None,
        field_mappings: Optional[Dict] = None,
        field_filters: Optional[Dict[str, str]] = None,
    ) -> List[Dict]:
        """List issue tracker tickets with filters using REST API.

        Args:
            assignee: Filter by assignee (use "currentUser()" for current user, will be auto-resolved)
            status: Filter by status (single value, deprecated in favor of status_list)
            sprint: Filter by sprint name (deprecated - use field_filters instead)
            ticket_type: Filter by ticket type (Story, Bug, etc.)
            status_list: Filter by multiple status values (takes precedence over status)
            field_mappings: Optional field mappings dict from config to resolve custom field IDs
            field_filters: Filter by custom fields (e.g., {"sprint": "Sprint 1", "severity": "Critical"})

        Returns:
            List of ticket dictionaries with keys: key, type, status, summary, and any custom fields from field_mappings

        Raises:
            JiraApiError: If API request fails
            JiraAuthError: If authentication fails
            JiraConnectionError: If connection fails
        """
        try:
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

            # Generic custom field filtering
            if field_filters:
                for field_name, field_value in field_filters.items():
                    # Get the field ID from field_mappings if available
                    field_id = field_name
                    if field_mappings and field_name in field_mappings:
                        field_info = field_mappings[field_name]
                        # Use the display name if available, otherwise use field name
                        field_id = field_info.get("name", field_name)

                    # Handle special values
                    if field_value == "IS NOT EMPTY":
                        jql_parts.append(f'"{field_id}" is not EMPTY')
                    else:
                        jql_parts.append(f'"{field_id}" = "{field_value}"')
            elif sprint:
                # Backward compatibility: support legacy sprint parameter
                if sprint == "IS NOT EMPTY":
                    jql_parts.append("sprint is not EMPTY")
                else:
                    jql_parts.append(f'sprint = "{sprint}"')

            if ticket_type:
                jql_parts.append(f'type = "{ticket_type}"')

            jql = " AND ".join(jql_parts) if jql_parts else "assignee = currentUser()"

            # Add ordering
            jql += " ORDER BY updated DESC"

            # Build fields list dynamically - include ALL custom fields from field_mappings
            # Note: 'created' and 'updated' are returned at the root level of the issue object
            # (alongside 'key' and 'fields'), not inside the 'fields' object
            fields_list_parts = ["created", "updated", "issuetype", "status", "summary", "assignee"]

            # Add all custom field IDs from field_mappings
            if field_mappings:
                for field_info in field_mappings.values():
                    field_id = field_info.get("id")
                    if field_id:
                        fields_list_parts.append(field_id)

            fields_list = ",".join(fields_list_parts)

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

                # Extract ALL custom fields generically from field_mappings
                if field_mappings:
                    for field_name, field_info in field_mappings.items():
                        field_id = field_info.get("id")
                        if not field_id or field_id not in fields:
                            continue

                        field_value = fields[field_id]
                        if field_value is None:
                            continue

                        # Apply type-based transformations
                        field_type = field_info.get("type", "string")
                        field_schema = field_info.get("schema", "")

                        # Number fields - convert to int
                        if field_type == "number":
                            try:
                                field_value = int(field_value)
                            except (ValueError, TypeError):
                                pass

                        # Sprint fields - parse Greenhopper format
                        # Detect by schema containing "sprint" keyword
                        elif "sprint" in str(field_schema).lower() and isinstance(field_value, list) and len(field_value) > 0:
                            sprint_str = field_value[0]
                            if isinstance(sprint_str, str) and "name=" in sprint_str:
                                # Extract name from Greenhopper sprint string format
                                name_start = sprint_str.find("name=") + 5
                                name_end = sprint_str.find(",", name_start)
                                if name_end == -1:
                                    name_end = sprint_str.find("]", name_start)
                                field_value = sprint_str[name_start:name_end]

                        # Store field value under its normalized name
                        ticket_data[field_name] = field_value

                        # Backward compatibility aliases (TEMPORARY - should be removed eventually)
                        # TODO: Remove these once all consuming code uses normalized field names
                        if "epic" in field_name and "link" in field_name:
                            ticket_data["epic"] = field_value
                        elif "story" in field_name and "point" in field_name:
                            ticket_data["points"] = field_value

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
        """Get all child issues for a parent issue.

        Uses JQL to find child issues based on parent_field_mapping configuration.
        Searches for:
        - Direct subtasks (where parent field = parent_key)
        - Issues linked via configured parent fields from parent_field_mapping

        Args:
            parent_key: issue key of the parent issue (e.g., PROJ-12345)
            field_mappings: Optional field mappings dict from config to resolve field display names

        Returns:
            List of child issue dictionaries with keys: key, type, status, summary, assignee
            Sorted by key in ascending order

        Raises:
            JiraApiError: If API request fails
            JiraAuthError: If authentication fails
            JiraConnectionError: If connection fails
        """
        try:
            # Build JQL query to find child issues
            # JIRA JQL uses display field names, not field IDs or normalized names
            jql_parts = [f'parent = {parent_key}']

            # Add JQL clauses for all parent fields configured in parent_field_mapping
            try:
                from devflow.config.loader import ConfigLoader
                config_loader = ConfigLoader()
                config = config_loader.load_config()

                if config and config.jira and config.jira.parent_field_mapping:
                    # Collect all unique parent field names from parent_field_mapping
                    parent_field_names = set(config.jira.parent_field_mapping.values())

                    # For each parent field, add JQL clause using its display name
                    if field_mappings:
                        for field_name in parent_field_names:
                            # Skip the standard "parent" field (already handled above)
                            if field_name == "parent":
                                continue

                            # Get field metadata to find display name
                            field_info = field_mappings.get(field_name)
                            if field_info:
                                # Use display name from metadata for JQL
                                display_name = field_info.get("name", field_name)
                                jql_parts.append(f'"{display_name}" = {parent_key}')
            except Exception:
                # If config loading fails, just use parent field
                pass

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
            Field ID string (e.g., "customfield_12311140", or "parent" for sub-task)
            Returns None if parent_field_mapping not configured or field not found
        """
        try:
            from devflow.config.loader import ConfigLoader
            config_loader = ConfigLoader()
            config = config_loader.load_config()

            if not config or not config.jira or not config.jira.parent_field_mapping:
                return None

            # Get logical field name from parent_field_mapping (e.g., "epic_link" or "parent")
            issue_type_lower = issue_type.lower()
            logical_field_name = config.jira.parent_field_mapping.get(issue_type_lower)

            if not logical_field_name:
                return None

            # If logical field is "parent" (standard field for sub-tasks), return it directly
            if logical_field_name == "parent":
                return "parent"

            # Otherwise, look up the custom field ID from field_mappings
            return field_mapper.get_field_id(logical_field_name)

        except Exception:
            return None

    def create_issue(
        self,
        issue_type: str,
        summary: str,
        description: str,
        priority: str,
        project_key: str,
        field_mapper,
        parent: Optional[str] = None,
        components: Optional[List[str]] = None,
        required_custom_fields: Optional[dict] = None,
        **custom_fields
    ) -> str:
        """Generic method to create a JIRA issue of any type.

        This method replaces the duplicated logic in create_bug(), create_story(),
        create_task(), create_epic(), and create_spike(). It handles all issue types
        generically using the field_mappings configuration.

        Args:
            issue_type: Issue type name (e.g., "Bug", "Story", "Task", "Epic", "Spike")
            summary: Issue summary/title
            description: Issue description (using template from AGENTS.md)
            priority: Issue priority (Critical, Major, Normal, Minor)
            project_key: JIRA project key (e.g., "PROJ")
            field_mapper: JiraFieldMapper instance for field ID lookup
            parent: Optional parent issue key (uses parent_field_mapping from config)
            components: List of component names (default: [])
            required_custom_fields: Dictionary of required custom fields {field_name: value}
            **custom_fields: Additional custom fields (field_id: value pairs)

        Returns:
            Created issue key (e.g., "PROJ-12345")

        Raises:
            JiraValidationError: If creation fails due to validation errors (400)
            JiraApiError: If API request fails
            JiraAuthError: If authentication fails
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
        if components is None:
            components = []
        if required_custom_fields is None:
            required_custom_fields = {}

        # Get parent field ID based on parent_field_mapping from config
        parent_field_id = self._get_parent_field_id(issue_type.lower(), field_mapper)

        # Build base payload
        payload = {
            "fields": {
                "project": {"key": project_key},
                "issuetype": {"name": issue_type},
                "summary": summary,
                "description": description,
                "priority": {"name": priority},
                "components": [{"name": comp} for comp in components],
            }
        }

        # Add required custom fields generically
        self._add_custom_fields_to_payload(payload, required_custom_fields, field_mapper)

        # Set required fields based on field_mappings metadata
        self._set_required_fields(payload, issue_type, field_mapper)

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
                    f"Authentication failed when creating {issue_type.lower()}",
                    status_code=response.status_code
                )
            elif response.status_code == 400:
                # Parse validation errors
                try:
                    error_data = response.json()
                    error_messages = error_data.get("errorMessages", [])
                    field_errors = error_data.get("errors", {})

                    raise JiraValidationError(
                        f"Failed to create {issue_type.lower()}",
                        field_errors=field_errors,
                        error_messages=error_messages
                    )
                except JiraValidationError:
                    raise
                except Exception:
                    raise JiraApiError(
                        f"Failed to create {issue_type.lower()}",
                        status_code=response.status_code,
                        response_text=response.text
                    )
            else:
                raise JiraApiError(
                    f"Failed to create {issue_type.lower()}",
                    status_code=response.status_code,
                    response_text=response.text
                )

        except (JiraAuthError, JiraApiError, JiraValidationError, JiraConnectionError):
            # Re-raise JIRA-specific exceptions
            raise
        except Exception as e:
            # Wrap unexpected errors
            raise JiraApiError(f"Failed to create {issue_type.lower()}: {e}")


    def _set_required_fields(
        self,
        payload: Dict,
        issue_type: str,
        field_mapper
    ) -> None:
        """Set required fields for the issue type if not already provided.

        Iterates through all fields in field_mappings and sets default placeholder
        values for fields that are marked as required for the given issue type
        but not already present in the payload.

        Args:
            payload: The JIRA API payload dict with "fields" key (modified in-place)
            issue_type: The JIRA issue type (e.g., "Bug", "Story", "Task")
            field_mapper: JiraFieldMapper instance for field metadata lookup

        Note:
            Modifies the payload dict in-place by adding required fields if needed.
        """
        # Get all field mappings
        if not field_mapper.field_mappings:
            return

        # Normalize issue type to match JIRA's title-case convention
        # JIRA returns issue types as title-case ("Bug", "Story", "Task")
        # CLI accepts lowercase ("bug", "story", "task")
        jira_issue_type = issue_type.capitalize()

        # Iterate through all fields in field_mappings
        for field_name, field_info in field_mapper.field_mappings.items():
            # Check if this field is required for the given issue type
            required_for = field_info.get("required_for", [])
            if jira_issue_type not in required_for:
                continue

            # Get field ID
            field_id = field_info.get("id")
            if not field_id:
                continue

            # Fields that should never be set during CREATE (auto-set by JIRA)
            CREATE_READONLY_FIELDS = {"reporter", "created", "updated", "creator", "assignee"}
            if field_id in CREATE_READONLY_FIELDS:
                continue

            # Skip if field is already set in payload
            if field_id in payload.get("fields", {}):
                continue

            # Set a default placeholder value based on field type
            field_type = field_info.get("type", "string")
            field_schema = field_info.get("schema", "")

            # Generate appropriate placeholder based on field type
            if field_type == "string" or "string" in str(field_schema):
                placeholder = f"TBD: Define {field_name.replace('_', ' ')} for this {issue_type.lower()}"
            elif field_type == "number":
                placeholder = 0
            elif field_type == "array" or "array" in str(field_schema):
                placeholder = []
            else:
                # Default to empty string for unknown types
                placeholder = ""

            payload["fields"][field_id] = placeholder

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
