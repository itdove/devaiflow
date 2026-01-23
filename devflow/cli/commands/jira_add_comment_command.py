"""Implementation of 'daf jira add-comment' command."""

import sys
import click
from rich.console import Console
from rich.prompt import Confirm

from devflow.cli.utils import output_json as json_output, console_print
from devflow.jira import JiraClient
from devflow.jira.exceptions import (
    JiraError,
    JiraAuthError,
    JiraApiError,
    JiraNotFoundError,
    JiraValidationError,
    JiraConnectionError
)

console = Console()


def add_comment(
    issue_key: str,
    comment: str = None,
    file_path: str = None,
    stdin: bool = False,
    public: bool = False,
    output_json: bool = False
) -> None:
    """Add a comment to a JIRA issue.

    By default, comments are restricted to Example Group visibility.

    Args:
        issue_key: JIRA issue key (e.g., PROJ-12345)
        comment: Comment text (plain argument)
        file_path: Path to file containing comment
        stdin: Read comment from stdin
        public: Make comment public (requires confirmation)
        output_json: Output in JSON format
    """
    # Get comment text from argument, file, or stdin
    comment_text = None

    if file_path:
        try:
            with open(file_path, 'r') as f:
                comment_text = f.read()
        except FileNotFoundError:
            if output_json:
                json_output(success=False, error={
                    "code": "FILE_NOT_FOUND",
                    "message": f"File not found: {file_path}"
                })
            else:
                console.print(f"[red]✗[/red] File not found: {file_path}")
            sys.exit(1)
        except Exception as e:
            if output_json:
                json_output(success=False, error={
                    "code": "FILE_READ_ERROR",
                    "message": f"Error reading file: {e}"
                })
            else:
                console.print(f"[red]✗[/red] Error reading file: {e}")
            sys.exit(1)
    elif stdin:
        comment_text = sys.stdin.read()
    elif comment:
        comment_text = comment
    else:
        if output_json:
            json_output(success=False, error={
                "code": "MISSING_COMMENT",
                "message": "Comment text required. Provide via argument, --file, or --stdin"
            })
        else:
            console.print("[red]✗[/red] Comment text required")
            console.print("Provide comment via:")
            console.print("  - Argument: [cyan]daf jira add-comment PROJ-12345 \"Your comment\"[/cyan]")
            console.print("  - File: [cyan]daf jira add-comment PROJ-12345 --file comment.txt[/cyan]")
            console.print("  - Stdin: [cyan]echo \"Comment\" | daf jira add-comment PROJ-12345 --stdin[/cyan]")
        sys.exit(1)

    # Trim whitespace
    comment_text = comment_text.strip()
    if not comment_text:
        if output_json:
            json_output(success=False, error={
                "code": "EMPTY_COMMENT",
                "message": "Comment cannot be empty"
            })
        else:
            console.print("[red]✗[/red] Comment cannot be empty")
        sys.exit(1)

    # Confirm if making comment public
    if public and not output_json:
        # Confirm making comment public
        if not Confirm.ask("Make comment PUBLIC (visible to all)?", default=False):
            console.print("Cancelled. Comment not added.")
            return

    # Add comment via JIRA client
    try:
        from devflow.utils import is_mock_mode
        from devflow.config.loader import ConfigLoader

        if is_mock_mode():
            from devflow.mocks.jira_mock import MockJiraClient
            config_loader = ConfigLoader()
            config = config_loader.load_config()
            jira_client = MockJiraClient(config=config)
        else:
            jira_client = JiraClient()
        jira_client.add_comment(issue_key, comment_text, public=public)

        # Success
        visibility_label = "Public" if public else "Example Group"
        if output_json:
            json_output(success=True, data={
                "issue_key": issue_key,
                "visibility": visibility_label,
                "comment_length": len(comment_text)
            })
        else:
            console_print(f"[green]✓[/green] Comment added to {issue_key} ({visibility_label})")

    except JiraNotFoundError as e:
        if output_json:
            json_output(success=False, error={
                "code": "NOT_FOUND",
                "message": str(e),
                "resource_type": e.resource_type if hasattr(e, 'resource_type') else None,
                "resource_id": e.resource_id if hasattr(e, 'resource_id') else None
            })
        else:
            console.print(f"[red]✗[/red] {e}")
        sys.exit(1)

    except JiraAuthError as e:
        if output_json:
            json_output(success=False, error={
                "code": "AUTH_ERROR",
                "message": str(e),
                "status_code": e.status_code if hasattr(e, 'status_code') else None
            })
        else:
            console.print(f"[red]✗[/red] {e}")
            console.print("[yellow]Check your JIRA_API_TOKEN environment variable[/yellow]")
        sys.exit(1)

    except JiraApiError as e:
        if output_json:
            json_output(success=False, error={
                "code": "API_ERROR",
                "message": str(e),
                "status_code": e.status_code if hasattr(e, 'status_code') else None
            })
        else:
            console.print(f"[red]✗[/red] {e}")
        sys.exit(1)

    except JiraConnectionError as e:
        if output_json:
            json_output(success=False, error={
                "code": "CONNECTION_ERROR",
                "message": str(e)
            })
        else:
            console.print(f"[red]✗[/red] {e}")
        sys.exit(1)

    except Exception as e:
        if output_json:
            json_output(success=False, error={
                "code": "UNKNOWN_ERROR",
                "message": str(e)
            })
        else:
            console.print(f"[red]✗[/red] Unexpected error: {e}")
        sys.exit(1)
