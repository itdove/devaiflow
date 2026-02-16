"""JIRA custom field mapper for discovering and caching field metadata.

This module provides functionality to discover JIRA custom field IDs and map them
to human-readable names, eliminating the need to hardcode field IDs.
"""

from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any

from rich.console import Console

console = Console()


class JiraFieldMapper:
    """Discovers and caches JIRA custom field mappings.

    This class handles the discovery of JIRA custom fields for a project,
    caching the mappings between human-readable names and field IDs.
    """

    def __init__(self, jira_client, field_mappings: Optional[Dict] = None):
        """Initialize the field mapper.

        Args:
            jira_client: JiraClient instance for making API calls
            field_mappings: Optional pre-cached field mappings
        """
        self.client = jira_client
        self._cache = field_mappings or {}

    @property
    def field_mappings(self) -> Dict[str, Dict[str, Any]]:
        """Get the cached field mappings.

        Returns:
            Dictionary of field mappings
        """
        return self._cache

    def discover_fields(self, project_key: str) -> Dict[str, Dict[str, Any]]:
        """Discover custom fields for a project.

        Fetches field metadata from JIRA and returns normalized mappings.

        Args:
            project_key: JIRA project key (e.g., "PROJ")

        Returns:
            Dictionary mapping normalized field names to field metadata:
            {
                "workstream": {
                    "id": "customfield_12319275",
                    "name": "Workstream",
                    "type": "array",
                    "schema": "option",
                    "allowed_values": ["Platform", "Hosted Services"],
                    "required_for": ["Bug", "Story"],
                    "available_for": ["Bug", "Story", "Task", "Epic"]
                },
                ...
            }

            Note: "available_for" lists ALL issue types where this field can be set.
                  "required_for" lists only issue types where this field is mandatory.

        Raises:
            RuntimeError: If API request fails
        """
        # Fetch all fields in the JIRA instance
        all_fields = self._fetch_all_fields()

        # Try to fetch createmeta for common issue types
        # If createmeta fails (e.g., 404), fall back to using just all_fields
        try:
            createmeta = self._fetch_createmeta(project_key, ["Bug", "Story", "Task", "Epic"])
            field_mappings = self._parse_field_metadata(all_fields, createmeta)
        except RuntimeError as e:
            # If createmeta fails, use fallback method
            # Don't print note in JSON mode (corrupts JSON output)
            import sys
            should_print = True

            # Check for --json flag in sys.argv first (most reliable)
            if "--json" in sys.argv:
                should_print = False
            else:
                # Also try is_json_mode() as a backup
                try:
                    from devflow.cli.utils import is_json_mode
                    if is_json_mode():
                        should_print = False
                except ImportError:
                    pass

            if should_print:
                console.print(f"[dim]Note: Using fallback field discovery (createmeta unavailable)[/dim]")

            field_mappings = self._parse_field_metadata_fallback(all_fields)

        # Note: Required field fallbacks are now handled via config patches
        # See patches/001-aap-59806-field-fallbacks.json for PROJ project workarounds
        # This eliminates the need for hardcoded workarounds in the code

        return field_mappings

    def discover_editable_fields(self, issue_key: str) -> Dict[str, Dict[str, Any]]:
        """Discover editable fields for an existing issue.

        Fetches field metadata from JIRA's editmeta API and returns normalized mappings.
        This includes fields that can be edited but may not be available during creation.

        Args:
            issue_key: JIRA issue key (e.g., "PROJ-12345")

        Returns:
            Dictionary mapping normalized field names to field metadata:
            {
                "git_pull_request": {
                    "id": "customfield_12310220",
                    "name": "Git Pull Request",
                    "type": "any",
                    "schema": "multiurl",
                    "required": false
                },
                ...
            }

        Raises:
            RuntimeError: If API request fails
        """
        # Fetch all fields in the JIRA instance
        all_fields = self._fetch_all_fields()

        # Fetch editmeta for the specific issue
        editmeta = self._fetch_editmeta(issue_key)

        # Parse the editmeta response
        field_mappings = self._parse_editmeta(all_fields, editmeta)

        return field_mappings

    def _fetch_all_fields(self) -> List[Dict]:
        """Fetch all fields in JIRA instance.

        Returns:
            List of field dictionaries with id, name, schema info

        Raises:
            RuntimeError: If API request fails or returns empty field list
        """
        response = self.client._api_request("GET", "/rest/api/2/field")

        if response.status_code != 200:
            raise RuntimeError(
                f"Failed to fetch JIRA fields: HTTP {response.status_code} - {response.text}"
            )

        fields = response.json()

        # Check if the response is empty or invalid
        if not isinstance(fields, list):
            raise RuntimeError(
                f"JIRA API returned invalid response format. Expected a list of fields, got: {type(fields).__name__}"
            )

        if len(fields) == 0:
            raise RuntimeError(
                "JIRA API returned 0 fields. This may indicate:\n"
                "  - Insufficient permissions to access field metadata\n"
                "  - JIRA instance configuration restricts field discovery\n"
                "  - API endpoint is not available on this JIRA version\n"
                "Please check your JIRA permissions and instance configuration."
            )

        return fields

    def _fetch_editmeta(self, issue_key: str) -> Dict:
        """Fetch editable field metadata for a specific issue.

        Uses the JIRA API endpoint:
        - /rest/api/2/issue/{issueKey}/editmeta

        Args:
            issue_key: JIRA issue key (e.g., "PROJ-12345")

        Returns:
            Dictionary with editable field metadata:
            {
                "fields": {
                    "customfield_12310220": {
                        "name": "Git Pull Request",
                        "schema": {
                            "type": "any",
                            "custom": "com.atlassian.jira.plugin.system.customfieldtypes:multiurl"
                        },
                        "required": false
                    },
                    ...
                }
            }

        Raises:
            RuntimeError: If API request fails
        """
        response = self.client._api_request(
            "GET",
            f"/rest/api/2/issue/{issue_key}/editmeta"
        )

        if response.status_code != 200:
            raise RuntimeError(
                f"Failed to fetch editmeta: HTTP {response.status_code} - {response.text}"
            )

        return response.json()

    def _fetch_createmeta(self, project_key: str, issue_types: List[str]) -> Dict:
        """Fetch field metadata for specific issue types using new JIRA API.

        Uses the new JIRA 9.0+ API endpoints:
        - /rest/api/2/issue/createmeta/{projectKey}/issuetypes
        - /rest/api/2/issue/createmeta/{projectKey}/issuetypes/{issueTypeId}

        Args:
            project_key: JIRA project key
            issue_types: List of issue type names (e.g., ["Bug", "Story"])

        Returns:
            Dictionary with project and issue type metadata in legacy format:
            {
                "projects": [{
                    "key": "PROJ",
                    "issuetypes": [
                        {
                            "name": "Bug",
                            "id": "1",
                            "fields": {...}
                        }
                    ]
                }]
            }

        Raises:
            RuntimeError: If API request fails
        """
        # Step 1: Get all issue types for the project
        response = self.client._api_request(
            "GET",
            f"/rest/api/2/issue/createmeta/{project_key}/issuetypes"
        )

        if response.status_code != 200:
            raise RuntimeError(
                f"Failed to fetch issue types: HTTP {response.status_code} - {response.text}"
            )

        issue_types_data = response.json()
        # Support both JIRA API versions:
        # - Newer JIRA (Cloud/9.0+): returns "issueTypes"
        # - Older JIRA: returns "values"
        all_issue_types = issue_types_data.get("issueTypes", issue_types_data.get("values", []))

        # Step 2: Filter to requested issue types and fetch fields for each
        filtered_issue_types = []
        for issue_type in all_issue_types:
            issue_type_name = issue_type.get("name", "")
            issue_type_id = issue_type.get("id", "")

            # Skip if not in requested list
            if issue_type_name not in issue_types:
                continue

            # Fetch field metadata for this issue type
            fields_response = self.client._api_request(
                "GET",
                f"/rest/api/2/issue/createmeta/{project_key}/issuetypes/{issue_type_id}"
            )

            if fields_response.status_code != 200:
                console.print(
                    f"[yellow]Warning: Could not fetch fields for {issue_type_name}: "
                    f"HTTP {fields_response.status_code}[/yellow]"
                )
                continue

            fields_data = fields_response.json()

            # Support both JIRA API versions:
            # - Newer JIRA (Cloud/9.0+): returns "fields"
            # - Older JIRA: returns "values"
            field_values = fields_data.get("fields", fields_data.get("values", []))
            fields_dict = {}
            for field in field_values:
                field_id = field.get("fieldId")
                if field_id:
                    fields_dict[field_id] = field

            # Add fields to the issue type data
            issue_type["fields"] = fields_dict
            filtered_issue_types.append(issue_type)

        # Step 3: Return in legacy format for compatibility with _parse_field_metadata
        return {
            "projects": [{
                "key": project_key,
                "issuetypes": filtered_issue_types
            }]
        }

    def _parse_editmeta(
        self,
        all_fields: List[Dict],
        editmeta: Dict
    ) -> Dict[str, Dict[str, Any]]:
        """Parse editmeta response into normalized structure.

        Args:
            all_fields: List of all fields from /rest/api/2/field
            editmeta: Edit metadata from /rest/api/2/issue/{key}/editmeta

        Returns:
            Dictionary mapping normalized field names to metadata
        """
        mappings = {}

        # Build field ID -> field info map from all_fields
        field_info = {f["id"]: f for f in all_fields}

        # Extract fields from editmeta
        fields_data = editmeta.get("fields", {})

        for field_key, field_data in fields_data.items():
            # CRITICAL: Skip fields that cannot be edited
            # Fields with operations: [] have no edit operations and will fail if updated
            # This prevents errors like "Field does not support update 'attachment'"
            operations = field_data.get("operations", [])
            if not operations:
                # Skip non-editable fields (e.g., attachment, issuelinks, component/s)
                continue

            # Get field name from all_fields or use the one from editmeta
            field_name = field_data.get("name", "")
            if not field_name:
                continue

            # Normalize field name (lowercase, replace spaces with underscores)
            normalized_name = field_name.lower().replace(" ", "_")

            # Get schema info
            schema_info = field_data.get("schema", {})
            field_type = schema_info.get("type", "string")

            # Extract custom schema type (e.g., "com.atlassian...multiurl" -> "multiurl")
            schema_custom = schema_info.get("custom", "")
            if schema_custom and ":" in schema_custom:
                schema_custom = schema_custom.split(":")[-1]
            elif not schema_custom:
                schema_custom = field_type

            mappings[normalized_name] = {
                "id": field_key,
                "name": field_name,
                "type": field_type,
                "schema": schema_custom,
                "required": field_data.get("required", False),
                "allowed_values": []
            }

            # Extract allowed values for select/multi-select fields
            if "allowedValues" in field_data:
                allowed_vals = []
                for v in field_data["allowedValues"]:
                    if isinstance(v, dict):
                        # Handle option objects (e.g., {"value": "Platform"})
                        # or version objects (e.g., {"name": "2.0.1", "id": "12345"})
                        if "value" in v:
                            allowed_vals.append(v["value"])
                        elif "name" in v:
                            allowed_vals.append(v["name"])
                        else:
                            # Skip complex objects that don't have simple display values
                            continue
                    else:
                        allowed_vals.append(str(v))
                mappings[normalized_name]["allowed_values"] = allowed_vals

        return mappings

    def _parse_field_metadata(
        self,
        all_fields: List[Dict],
        createmeta: Dict
    ) -> Dict[str, Dict[str, Any]]:
        """Parse field metadata into normalized structure.

        Args:
            all_fields: List of all fields from /rest/api/2/field
            createmeta: Create metadata from /rest/api/2/issue/createmeta

        Returns:
            Dictionary mapping normalized field names to metadata
        """
        mappings = {}

        # Build field ID -> field info map from all_fields
        field_info = {f["id"]: f for f in all_fields}

        # Extract fields from createmeta
        for project in createmeta.get("projects", []):
            for issuetype in project.get("issuetypes", []):
                issue_type_name = issuetype["name"]

                for field_key, field_data in issuetype.get("fields", {}).items():
                    # Normalize field name (lowercase, replace spaces with underscores)
                    field_name = field_data.get("name", "")
                    if not field_name:
                        continue

                    normalized_name = field_name.lower().replace(" ", "_")

                    # Skip if already processed (from another issue type)
                    if normalized_name not in mappings:
                        schema_info = field_data.get("schema", {})

                        mappings[normalized_name] = {
                            "id": field_key,
                            "name": field_name,
                            "type": schema_info.get("type", "string"),
                            "schema": schema_info.get("custom", schema_info.get("type", "string")),
                            "required_for": [],
                            "available_for": [],
                            "allowed_values": []
                        }

                    # Track which issue types this field is available for (ALL issue types where it appears)
                    if issue_type_name not in mappings[normalized_name]["available_for"]:
                        mappings[normalized_name]["available_for"].append(issue_type_name)

                    # Track which issue types require this field
                    if field_data.get("required", False):
                        if issue_type_name not in mappings[normalized_name]["required_for"]:
                            mappings[normalized_name]["required_for"].append(issue_type_name)

                    # Extract allowed values for select/multi-select fields
                    if "allowedValues" in field_data:
                        # Only set if not already set (avoid duplicates)
                        if not mappings[normalized_name]["allowed_values"]:
                            allowed_vals = []
                            for v in field_data["allowedValues"]:
                                if isinstance(v, dict):
                                    # Handle option objects - try value, name, or id
                                    if "value" in v:
                                        allowed_vals.append(v["value"])
                                    elif "name" in v:
                                        allowed_vals.append(v["name"])
                                    elif "id" in v:
                                        allowed_vals.append(v["id"])
                                    # Skip complex objects that don't have simple display values
                                else:
                                    allowed_vals.append(str(v))
                            mappings[normalized_name]["allowed_values"] = allowed_vals

        return mappings

    def _parse_field_metadata_fallback(self, all_fields: List[Dict]) -> Dict[str, Dict[str, Any]]:
        """Parse field metadata using only the field list (fallback when createmeta unavailable).

        This method is used when the createmeta endpoint is not available or returns errors.
        It provides basic field mappings without required_for or allowed_values information.

        Args:
            all_fields: List of all fields from /rest/api/2/field

        Returns:
            Dictionary mapping normalized field names to field metadata
        """
        mappings = {}

        for field in all_fields:
            field_id = field.get("id", "")
            field_name = field.get("name", "")

            if not field_name or not field_id:
                continue

            # Normalize field name (lowercase, replace spaces with underscores)
            normalized_name = field_name.lower().replace(" ", "_")

            # Get schema information if available
            schema_info = field.get("schema", {})
            field_type = schema_info.get("type", "string")
            schema_custom = schema_info.get("custom", field_type)

            mappings[normalized_name] = {
                "id": field_id,
                "name": field_name,
                "type": field_type,
                "schema": schema_custom,
                "required_for": [],
                "available_for": [],
                "allowed_values": []
            }

        return mappings

    def get_field_id(self, field_name: str) -> Optional[str]:
        """Get field ID from human-readable name.

        Args:
            field_name: Human-readable field name (e.g., "workstream", "epic_link")
                       Can use spaces or underscores, case-insensitive.

        Returns:
            Field ID (e.g., "customfield_12319275") or None if not found
        """
        # Normalize the input
        normalized_name = field_name.lower().replace(" ", "_")

        mapping = self._cache.get(normalized_name)
        return mapping["id"] if mapping else None

    def get_field_info(self, field_name: str) -> Optional[Dict[str, Any]]:
        """Get full field metadata from human-readable name.

        Args:
            field_name: Human-readable field name (e.g., "workstream", "epic_link")

        Returns:
            Field metadata dictionary or None if not found
        """
        normalized_name = field_name.lower().replace(" ", "_")
        return self._cache.get(normalized_name)

    def is_cache_stale(
        self,
        cache_timestamp: Optional[str],
        max_age_days: int = 7,
        max_age_hours: Optional[int] = None
    ) -> bool:
        """Check if cached field mappings are stale.

        Args:
            cache_timestamp: ISO format timestamp string (e.g., "2025-11-23T02:00:00Z")
            max_age_days: Maximum age in days before cache is considered stale (default: 7)
            max_age_hours: Maximum age in hours (takes precedence over max_age_days if provided)

        Returns:
            True if cache is stale or missing, False otherwise
        """
        if not cache_timestamp:
            return True

        try:
            # Parse the timestamp (handle both with and without 'Z' suffix)
            timestamp_str = cache_timestamp.replace('Z', '+00:00')
            cache_time = datetime.fromisoformat(timestamp_str)

            # Calculate age
            age = datetime.now(cache_time.tzinfo) - cache_time

            # Use hours if provided, otherwise fall back to days
            if max_age_hours is not None:
                return age > timedelta(hours=max_age_hours)
            else:
                return age > timedelta(days=max_age_days)
        except (ValueError, AttributeError):
            # If we can't parse the timestamp, consider it stale
            return True

    def update_cache(self, field_mappings: Dict[str, Dict[str, Any]]) -> None:
        """Update the internal cache with new field mappings.

        Args:
            field_mappings: Dictionary of field mappings from discover_fields()
        """
        self._cache = field_mappings

