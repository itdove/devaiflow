"""Implementation of 'daf jira view' command."""

import sys
from datetime import datetime
from typing import Dict, List, Optional, Any
from rich.console import Console

from devflow.cli.utils import output_json as json_output
from devflow.jira import JiraClient
from devflow.jira.exceptions import JiraError, JiraAuthError, JiraApiError, JiraNotFoundError, JiraValidationError, JiraConnectionError

console = Console()


def format_ticket_for_claude(ticket_data: dict) -> str:
    """Format issue tracker ticket data in a Claude-friendly text format.

    Args:
        ticket_data: Dictionary with ticket data from JiraClient.get_ticket_detailed()

    Returns:
        Formatted string suitable for Claude to read
    """
    lines = []

    # Define standard fields that have specific display order and formatting
    standard_fields = {
        'key', 'summary', 'type', 'status', 'priority', 'assignee', 'reporter',
        'description', 'changelog'
    }

    # Header - required fields
    lines.append(f"Key: {ticket_data['key']}")
    lines.append(f"Summary: {ticket_data['summary']}")
    lines.append(f"Type: {ticket_data['type']}")
    lines.append(f"Status: {ticket_data['status']}")

    # Optional standard metadata
    if ticket_data.get('priority'):
        lines.append(f"Priority: {ticket_data['priority']}")

    if ticket_data.get('assignee'):
        lines.append(f"Assignee: {ticket_data['assignee']}")

    if ticket_data.get('reporter'):
        lines.append(f"Reporter: {ticket_data['reporter']}")

    # Display all custom fields generically
    for field_name, field_value in sorted(ticket_data.items()):
        # Skip standard fields (already displayed above or displayed later)
        if field_name in standard_fields:
            continue

        # Skip None/empty values
        if field_value is None or field_value == '':
            continue

        # Get display name by title-casing the field name
        display_name = field_name.replace('_', ' ').title()

        # Special handling for URL fields (git_pull_request and fields ending with _url)
        if field_name == 'git_pull_request' or field_name.endswith('_url'):
            lines.append("")
            # Handle both string (comma-separated) and list formats
            if isinstance(field_value, list):
                urls = [url.strip() for url in field_value if url and url.strip()]
            else:
                urls = [url.strip() for url in str(field_value).split(',') if url.strip()]

            if len(urls) == 1:
                lines.append(f"{display_name}: {urls[0]}")
            elif len(urls) > 1:
                lines.append(f"{display_name}s:")
                for url in urls:
                    lines.append(f"  - {url}")
        # Special handling for long text fields (description-like fields)
        elif isinstance(field_value, str) and len(field_value) > 100:
            lines.append("")
            lines.append(f"{display_name}:")
            lines.append(field_value)
        # Regular inline fields
        else:
            lines.append(f"{display_name}: {field_value}")

    # Description (always at the end for readability)
    if ticket_data.get('description'):
        lines.append("")
        lines.append("Description:")
        lines.append(ticket_data['description'])

    return "\n".join(lines)


def format_changelog_for_claude(changelog: Dict) -> str:
    """Format JIRA changelog data in a Claude-friendly text format.

    Args:
        changelog: Changelog dict from JIRA API with 'histories' key

    Returns:
        Formatted string with changelog history, or empty string if no history
    """
    histories = changelog.get("histories", [])
    if not histories:
        return ""

    lines = []
    lines.append("")
    lines.append("Changelog/History:")
    lines.append("-" * 80)

    # Limit to last 15 entries as per acceptance criteria
    recent_histories = histories[-15:]

    for history in recent_histories:
        # Parse timestamp
        created = history.get("created", "")
        if created:
            try:
                # JIRA format: 2025-12-05T20:13:45.380+0000
                dt = datetime.fromisoformat(created.replace("+0000", "+00:00"))
                timestamp = dt.strftime("%Y-%m-%d %H:%M:%S")
            except:
                timestamp = created[:19]  # Fallback to just date/time part
        else:
            timestamp = "Unknown time"

        # Get author
        author = history.get("author", {})
        author_name = author.get("displayName", "Unknown")

        # Process each change item
        items = history.get("items", [])
        for item in items:
            field = item.get("field", "Unknown field")
            from_str = item.get("fromString") or "(empty)"
            to_str = item.get("toString") or "(empty)"

            # Format as: timestamp | author | field: from -> to
            lines.append(f"{timestamp} | {author_name:20} | {field}: {from_str} → {to_str}")

    return "\n".join(lines)


def format_child_issues_for_claude(children: List[Dict]) -> str:
    """Format child issues in a Claude-friendly text format.

    Args:
        children: List of child issue dicts from JiraClient.get_child_issues()

    Returns:
        Formatted string with child issues list, or message if no children
    """
    if not children:
        return "\nNo child issues found"

    lines = []
    lines.append("")
    lines.append("Child Issues:")
    lines.append("-" * 80)

    for child in children:
        # Format: KEY | Type | Status | Summary [| Assignee]
        parts = [
            child.get("key", "???"),
            child.get("type", "Unknown"),
            child.get("status", "Unknown"),
            child.get("summary", "No summary"),
        ]

        if child.get("assignee"):
            parts.append(f"Assignee: {child['assignee']}")

        lines.append(" | ".join(parts))

    return "\n".join(lines)


def format_comments_for_claude(comments: List[Dict]) -> str:
    """Format JIRA comments in a Claude-friendly text format.

    Args:
        comments: List of comment dicts from JiraClient.get_comments()
                 Each dict contains: id, author, created, body, visibility (optional)

    Returns:
        Formatted string with comments, or empty string if no comments
    """
    if not comments:
        return ""

    lines = []
    lines.append("")
    lines.append("Comments:")
    lines.append("-" * 80)

    for comment in comments:
        # Parse timestamp
        created = comment.get("created", "")
        if created:
            try:
                # JIRA format: 2025-12-05T20:13:45.380+0000
                dt = datetime.fromisoformat(created.replace("+0000", "+00:00"))
                timestamp = dt.strftime("%Y-%m-%d %H:%M:%S")
            except:
                timestamp = created[:19]  # Fallback to just date/time part
        else:
            timestamp = "Unknown time"

        # Get author
        author = comment.get("author", "Unknown")

        # Get comment body
        body = comment.get("body", "")

        # Format as: timestamp | author
        # Body (on separate lines for readability)
        lines.append(f"{timestamp} | {author}")

        # Add visibility info if present and restricted
        if "visibility" in comment:
            visibility = comment["visibility"]
            vis_type = visibility.get("type", "")
            vis_value = visibility.get("value", "")
            if vis_type and vis_value:
                lines.append(f"  [Visibility: {vis_type}={vis_value}]")

        # Add comment body with indentation for clarity
        for line in body.split('\n'):
            lines.append(f"  {line}")

        # Add separator between comments
        lines.append("")

    return "\n".join(lines)


def view_jira_ticket(issue_key: str, show_history: bool = False, show_children: bool = False, show_comments: bool = False, output_json: bool = False) -> None:
    """View a issue tracker ticket in Claude-friendly format.

    Args:
        issue_key: issue tracker key (e.g., PROJ-12345)
        show_history: If True, include changelog/history display
        show_children: If True, include child issues display
        show_comments: If True, include comments display
        output_json: If True, output in JSON format
    """
    try:
        # Load config to get field mappings
        from devflow.config.loader import ConfigLoader
        config_loader = ConfigLoader()
        config = config_loader.load_config()
        field_mappings = config.jira.field_mappings if config else None

        from devflow.utils import is_mock_mode
        if is_mock_mode():
            from devflow.mocks.jira_mock import MockJiraClient
            jira_client = MockJiraClient(config=config)
        else:
            jira_client = JiraClient()

        # Fetch ticket with full details and changelog/comments if requested
        try:
            ticket_data = jira_client.get_ticket_detailed(
                issue_key,
                field_mappings=field_mappings,
                include_changelog=show_history,
                include_comments=show_comments
            )
        except JiraNotFoundError as e:
            if output_json:
                json_output(
                    success=False,
                    error={"message": str(e), "code": "NOT_FOUND"}
                )
            else:
                console.print(f"[red]✗[/red] {e}")
            sys.exit(1)
        except JiraAuthError as e:
            if output_json:
                json_output(success=False, error={"code": "AUTH_ERROR", "message": str(e)})
            else:
                console.print(f"[red]✗[/red] {e}")
            sys.exit(1)
        except JiraApiError as e:
            if output_json:
                json_output(success=False, error={
                    "code": "API_ERROR",
                    "message": str(e),
                    "status_code": e.status_code
                })
            else:
                console.print(f"[red]✗[/red] {e}")
            sys.exit(1)
        except JiraConnectionError as e:
            if output_json:
                json_output(success=False, error={"code": "CONNECTION_ERROR", "message": str(e)})
            else:
                console.print(f"[red]✗[/red] {e}")
            sys.exit(1)

        # Fetch child issues if requested
        children_data = None
        if show_children:
            try:
                children_data = jira_client.get_child_issues(
                    issue_key,
                    field_mappings=field_mappings
                )
            except JiraAuthError as e:
                if output_json:
                    json_output(success=False, error={"code": "AUTH_ERROR", "message": str(e)})
                else:
                    console.print(f"[red]✗[/red] {e}")
                sys.exit(1)
            except JiraApiError as e:
                if output_json:
                    json_output(success=False, error={
                        "code": "API_ERROR",
                        "message": str(e),
                        "status_code": e.status_code
                    })
                else:
                    console.print(f"[red]✗[/red] {e}")
                sys.exit(1)
            except JiraConnectionError as e:
                if output_json:
                    json_output(success=False, error={"code": "CONNECTION_ERROR", "message": str(e)})
                else:
                    console.print(f"[red]✗[/red] {e}")
                sys.exit(1)

        # JSON output mode
        if output_json:
            # Prepare changelog data for JSON
            changelog_data = None
            if show_history and ticket_data.get("changelog"):
                histories = ticket_data["changelog"].get("histories", [])
                # Limit to last 15 entries as per acceptance criteria
                recent_histories = histories[-15:]

                changelog_data = []
                for history in recent_histories:
                    # Parse timestamp
                    created = history.get("created", "")
                    if created:
                        try:
                            # JIRA format: 2025-12-05T20:13:45.380+0000
                            dt = datetime.fromisoformat(created.replace("+0000", "+00:00"))
                            timestamp = dt.isoformat()
                        except:
                            timestamp = created
                    else:
                        timestamp = None

                    # Get author
                    author = history.get("author", {})
                    author_name = author.get("displayName", "Unknown")

                    # Process each change item
                    items = history.get("items", [])
                    for item in items:
                        changelog_data.append({
                            "timestamp": timestamp,
                            "author": author_name,
                            "field": item.get("field", "Unknown field"),
                            "from_value": item.get("fromString"),
                            "to_value": item.get("toString"),
                        })

            # Build JSON output
            output_data = {
                "ticket": ticket_data,
            }

            if changelog_data is not None:
                output_data["changelog"] = changelog_data

            if children_data is not None:
                output_data["children"] = children_data

            # Comments already included in ticket_data if requested
            # Extract for separate output section (similar to changelog)
            if show_comments and ticket_data.get("comments"):
                output_data["comments"] = ticket_data["comments"]

            json_output(
                success=True,
                data=output_data
            )
            return

        # Format and print in Claude-friendly format
        formatted_output = format_ticket_for_claude(ticket_data)
        console.print(formatted_output)

        # Format and print child issues if requested
        if show_children and children_data is not None:
            formatted_children = format_child_issues_for_claude(children_data)
            console.print(formatted_children)

        # Format and print comments if requested
        if show_comments and ticket_data.get("comments"):
            formatted_comments = format_comments_for_claude(ticket_data["comments"])
            if formatted_comments:
                console.print(formatted_comments)

        # Format and print changelog if requested
        if show_history and ticket_data.get("changelog"):
            formatted_history = format_changelog_for_claude(ticket_data["changelog"])
            if formatted_history:
                console.print(formatted_history)

    except RuntimeError as e:
        if output_json:
            json_output(
                success=False,
                error={"message": str(e), "code": "RUNTIME_ERROR"}
            )
        else:
            console.print(f"[red]✗[/red] {e}")
        sys.exit(1)
    except Exception as e:
        if output_json:
            json_output(
                success=False,
                error={"message": f"Unexpected error: {e}", "code": "UNEXPECTED_ERROR"}
            )
        else:
            console.print(f"[red]✗[/red] Unexpected error: {e}")
        sys.exit(1)
