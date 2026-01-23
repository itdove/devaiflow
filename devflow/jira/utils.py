"""Utility functions for JIRA operations."""

import re
from typing import Union, List, Optional, Dict
from rich.console import Console

console = Console()


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
