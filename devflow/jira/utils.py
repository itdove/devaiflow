"""Utility functions for JIRA operations."""

import re
from typing import Union, List, Optional, Dict, TYPE_CHECKING
from rich.console import Console
from rich.prompt import Prompt

if TYPE_CHECKING:
    from devflow.jira.field_mapper import JiraFieldMapper

console = Console()

# Field name aliases for backward compatibility
# Maps old JIRA server field names to new JIRA cloud field names
FIELD_NAME_ALIASES = {
    "component/s": "components",
    "affects_version/s": "affects_versions",
}


def get_field_with_alias(field_mappings: Dict, field_name: str) -> Optional[Dict]:
    """Get field info from field_mappings, checking both the field name and its alias.

    This function provides backward compatibility for JIRA field names that changed
    between server and cloud versions:
    - component/s → components
    - affects_version/s → affects_versions

    Args:
        field_mappings: Dictionary of field mappings
        field_name: Field name to look up (can be old or new variant)

    Returns:
        Field info dictionary if found (checking both name and alias), None otherwise

    Examples:
        >>> field_mappings = {"component/s": {...}, "other": {...}}
        >>> get_field_with_alias(field_mappings, "components")  # Returns field_mappings["component/s"]
        >>> get_field_with_alias(field_mappings, "component/s")  # Returns field_mappings["component/s"]
    """
    # Try the field name directly first
    if field_name in field_mappings:
        return field_mappings[field_name]

    # Try reverse lookup: check if field_name is an alias (new name) for an old name
    for old_name, new_name in FIELD_NAME_ALIASES.items():
        if field_name == new_name and old_name in field_mappings:
            return field_mappings[old_name]

    # Try forward lookup: check if field_name is an old name with a new alias
    alias = FIELD_NAME_ALIASES.get(field_name)
    if alias and alias in field_mappings:
        return field_mappings[alias]

    return None


def merge_pr_urls(existing_urls: Union[str, List[str], None], new_urls: Union[str, List[str]]) -> str:
    """Merge new PR URLs with existing ones, avoiding duplicates.

    This function handles merging pull request/merge request URLs for JIRA's
    git-pull-request custom field. It normalizes input from various formats
    (comma-separated strings, lists) and ensures no duplicate URLs are added.

    Args:
        existing_urls: Existing PR URLs. Can be:
                      - Comma-separated string: "url1,url2,url3"
                      - List of URLs: ["url1", "url2", "url3"]
                      - Empty string or None
        new_urls: New PR URLs to add. Can be:
                 - Comma-separated string: "url4,url5"
                 - List of URLs: ["url4", "url5"]
                 - Single URL string: "url4"

    Returns:
        Merged PR URLs as comma-separated string with duplicates removed.
        Order is preserved: existing URLs first, then new URLs.
        Empty string if no URLs to merge.

    Examples:
        >>> merge_pr_urls("url1,url2", "url3")
        'url1,url2,url3'

        >>> merge_pr_urls("url1,url2", "url2,url3")
        'url1,url2,url3'

        >>> merge_pr_urls(["url1", "url2"], "url3")
        'url1,url2,url3'

        >>> merge_pr_urls("", "url1")
        'url1'

        >>> merge_pr_urls(None, "url1,url2")
        'url1,url2'
    """
    # Parse existing URLs
    existing_list: List[str] = []
    if existing_urls:
        if isinstance(existing_urls, list):
            # JIRA API sometimes returns lists for multiurl fields
            existing_list = [url.strip() for url in existing_urls if url and url.strip()]
        elif isinstance(existing_urls, str):
            # JIRA API usually returns comma-separated strings
            existing_list = [url.strip() for url in existing_urls.split(',') if url.strip()]

    # Parse new URLs
    new_list: List[str] = []
    if new_urls:
        if isinstance(new_urls, list):
            new_list = [url.strip() for url in new_urls if url and url.strip()]
        elif isinstance(new_urls, str):
            new_list = [url.strip() for url in new_urls.split(',') if url.strip()]

    # Merge, avoiding duplicates while preserving order
    for url in new_list:
        if url not in existing_list:
            existing_list.append(url)

    # Return comma-separated string
    return ','.join(existing_list)


def is_issue_key_pattern(identifier: str) -> bool:
    """Check if a string matches issue key pattern.

    Args:
        identifier: String to check (e.g., "PROJ-12345")

    Returns:
        True if matches issue key pattern, False otherwise

    Examples:
        >>> is_issue_key_pattern("PROJ-12345")
        True
        >>> is_issue_key_pattern("MYPROJ-999")
        True
        >>> is_issue_key_pattern("invalid")
        False
        >>> is_issue_key_pattern("aap-123")  # lowercase project key
        False
    """
    # issue key pattern: Starts with uppercase letter, followed by 0+ alphanumeric chars,
    # then hyphen, then 1+ digits
    # Example: PROJ-12345, MYPROJECT-999, A-1, A1B2-1
    # Note: Single letter project keys are allowed (e.g., A-1)
    pattern = r'^[A-Z][A-Z0-9]*-[0-9]+$'
    return bool(re.match(pattern, identifier))


def validate_jira_ticket(issue_key: str, client: Optional['JiraClient'] = None) -> Optional[Dict]:
    """Validate that a issue tracker ticket exists.

    This function checks if a issue tracker ticket exists by making an API call.
    It displays user-friendly error messages for common failure cases.

    Args:
        issue_key: issue tracker key (e.g., "PROJ-12345")
        client: Optional JiraClient instance (creates new if None)

    Returns:
        Ticket data dict if valid (with keys: key, type, status, summary, assignee)
        None if invalid or error occurred

    Displays:
        Error messages for: ticket not found, auth failures, API errors

    Examples:
        >>> from devflow.jira import JiraClient
        >>> client = JiraClient()
        >>> ticket = validate_jira_ticket("PROJ-12345", client)
        >>> if ticket:
        ...     print(f"Valid ticket: {ticket['summary']}")
    """
    # Import here to avoid circular dependency
    from devflow.jira import JiraClient
    from devflow.jira.exceptions import (
        JiraNotFoundError,
        JiraAuthError,
        JiraApiError,
        JiraConnectionError
    )

    # Create client if not provided
    if not client:
        try:
            client = JiraClient()
        except Exception as e:
            console.print(f"[red]✗[/red] Failed to initialize JIRA client: {e}")
            return None

    # Validate ticket exists via API
    try:
        ticket = client.get_ticket(issue_key)
        return ticket
    except JiraNotFoundError:
        console.print(f"[red]✗[/red] issue tracker ticket [bold]{issue_key}[/bold] not found")
        console.print(f"[dim]Please verify the ticket key and try again[/dim]")
        return None
    except JiraAuthError as e:
        console.print(f"[red]✗[/red] Authentication failed: {e}")
        console.print(f"[dim]Set JIRA_API_TOKEN environment variable and ensure it's valid[/dim]")
        return None
    except JiraApiError as e:
        console.print(f"[yellow]⚠[/yellow] JIRA API error: {e}")
        return None
    except JiraConnectionError as e:
        console.print(f"[yellow]⚠[/yellow] Connection error: {e}")
        console.print(f"[dim]Check network connectivity and JIRA_URL configuration[/dim]")
        return None
    except Exception as e:
        console.print(f"[yellow]⚠[/yellow] Unexpected error validating ticket: {e}")
        return None


def validate_affected_version(version: str, field_mapper: Optional['JiraFieldMapper'] = None) -> bool:
    """Validate that a version is in the allowed_values list if one exists.

    Args:
        version: Version string to validate
        field_mapper: Optional JiraFieldMapper instance with field_mappings loaded

    Returns:
        True if version is valid (either in allowed_values or no restrictions exist)
        False if version is invalid (not in allowed_values when restrictions exist)
    """
    if not field_mapper or not field_mapper.field_mappings:
        # No field mapper or mappings - accept any version
        return True

    # Try to find allowed_values for version fields
    allowed_versions = []

    # Strategy 1: Check specific field names
    for field_name in ["affects_version/s", "affected_version", "versions", "affects_versions"]:
        field_info = field_mapper.field_mappings.get(field_name, {})
        allowed_vals = field_info.get("allowed_values", [])
        if allowed_vals:
            allowed_versions = allowed_vals
            break

    # Strategy 2: Search for any version-related field
    if not allowed_versions:
        for field_name, field_info in field_mapper.field_mappings.items():
            if ("version" in field_name or "affect" in field_name):
                allowed_vals = field_info.get("allowed_values", [])
                if allowed_vals:
                    allowed_versions = allowed_vals
                    break

    # If no allowed_values found, accept any version
    if not allowed_versions:
        return True

    # Check if version is in allowed list
    return version in allowed_versions


def is_version_field_required(
    field_mapper: Optional['JiraFieldMapper'] = None,
    issue_type: str = None
) -> bool:
    """Check if the version field is marked as required for the given issue type.

    Checks field_mappings['affects_version/s']['required_for'] to determine if the
    version field is required for the specified issue type.

    Args:
        field_mapper: Optional JiraFieldMapper instance with field_mappings loaded
        issue_type: JIRA issue type (e.g., "Bug", "Story", "Task"). Required parameter.

    Returns:
        True if version field is required for this issue type, False otherwise
    """
    if not issue_type:
        return False
    if not field_mapper or not field_mapper.field_mappings:
        return False

    # Strategy 1: Check specific field names
    for field_name in ["affects_version/s", "affected_version", "versions", "affects_versions"]:
        field_info = field_mapper.field_mappings.get(field_name, {})
        if field_info:
            required_for = field_info.get("required_for", [])
            if issue_type in required_for:
                return True

    # Strategy 2: Search for any version-related field
    for field_name, field_info in field_mapper.field_mappings.items():
        if ("version" in field_name or "affect" in field_name):
            required_for = field_info.get("required_for", [])
            if issue_type in required_for:
                return True

    return False


def prompt_for_affected_version(field_mapper: Optional['JiraFieldMapper'] = None) -> str:
    """Prompt user for affected version with list of available versions if possible.

    This function:
    1. Attempts to discover version fields with allowed_values from field_mappings
    2. If found, displays a numbered list and allows selection by number or name
    3. Validates that the entered version is in the allowed_values list
    4. If not found, falls back to simple text prompt

    Args:
        field_mapper: Optional JiraFieldMapper instance with field_mappings loaded

    Returns:
        Selected version string

    Examples:
        >>> from devflow.jira.field_mapper import JiraFieldMapper
        >>> field_mapper = JiraFieldMapper(jira_client)
        >>> version = prompt_for_affected_version(field_mapper)
    """
    # Try to get allowed_values from field_mappings
    allowed_versions = []
    if field_mapper and field_mapper.field_mappings:
        # Strategy 1: Check for specific field names that might represent affected version
        # JIRA uses different field names: affects_version/s, affected_version, versions
        for field_name in ["affects_version/s", "affected_version", "versions", "affects_versions"]:
            field_info = field_mapper.field_mappings.get(field_name, {})
            allowed_vals = field_info.get("allowed_values", [])
            if allowed_vals:
                allowed_versions = allowed_vals
                break

        # Strategy 2: If not found, search for any field containing "version" or "affect" with allowed_values
        if not allowed_versions:
            for field_name, field_info in field_mapper.field_mappings.items():
                if ("version" in field_name or "affect" in field_name):
                    allowed_vals = field_info.get("allowed_values", [])
                    if allowed_vals:
                        allowed_versions = allowed_vals
                        break

    if allowed_versions:
        # Display numbered list of versions
        console.print("\n[bold]Available versions:[/bold]")
        for i, version in enumerate(allowed_versions, 1):
            console.print(f"  {i}. {version}")
        console.print()

        # Prompt for selection (by number or name)
        console.print("[bold]Select version:[/bold]")
        console.print("  • Enter a number to select from the list")
        console.print("  • Enter a version name from the list above")
        console.print()

        while True:
            selection = Prompt.ask("Selection", default="1" if allowed_versions else "v1.0.0")

            # Parse selection: check if it's a number
            if selection.isdigit():
                version_index = int(selection) - 1
                if 0 <= version_index < len(allowed_versions):
                    return allowed_versions[version_index]
                else:
                    console.print(f"[red]✗[/red] Invalid selection. Please enter a number between 1 and {len(allowed_versions)}.")
                    continue
            else:
                # Validate that the entered version is in the allowed list
                if selection in allowed_versions:
                    return selection
                else:
                    console.print(f"[red]✗[/red] Version '{selection}' is not in the allowed versions list.")
                    console.print(f"[dim]Please select from the list above or enter a valid number.[/dim]")
                    continue
    else:
        # No allowed_values available, fall back to simple text prompt
        console.print("\n[yellow]⚠[/yellow] No version list available.")
        console.print("[dim]Example: v1.0.0[/dim]")
        return Prompt.ask("[bold]Enter affected version[/bold]", default="v1.0.0")
