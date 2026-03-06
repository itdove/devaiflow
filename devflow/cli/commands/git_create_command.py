"""Implementation of 'daf git create' command."""

import sys
from typing import Optional, List
from rich.console import Console
from rich.prompt import Prompt, Confirm

from devflow.cli.utils import output_json as json_output, console_print, require_outside_claude
from devflow.cli.commands.sync_command import issue_key_to_session_name
from devflow.config.loader import ConfigLoader
from devflow.github.issues_client import GitHubClient
from devflow.github.field_mapper import GitHubFieldMapper
from devflow.issue_tracker.exceptions import (
    IssueTrackerError,
    IssueTrackerAuthError,
    IssueTrackerApiError,
    IssueTrackerValidationError,
)

console = Console()


def _get_issue_template(config, issue_type: str) -> str:
    """Get GitHub issue template from config.

    Args:
        config: Config object
        issue_type: Issue type (e.g., "bug", "enhancement", "task")

    Returns:
        Template string for the given issue type
    """
    # Normalize issue type
    issue_type_lower = issue_type.lower()

    # Try to get template from config
    if config and config.github and config.github.issue_templates:
        template = config.github.issue_templates.get(issue_type_lower)
        if template:
            return template

    # Default templates for common types
    default_templates = {
        "bug": """## Bug Description
[Describe the bug]

## Steps to Reproduce
1.
2.
3.

## Expected Behavior
[What should happen]

## Actual Behavior
[What actually happens]

## Environment
- OS:
- Browser/Version:
""",
        "enhancement": """## Feature Description
[Describe the feature]

## Use Case
[Why is this needed?]

## Proposed Solution
[How should it work?]

## Alternatives Considered
[Other approaches considered]
""",
        "task": """## Task Description
[Describe what needs to be done]

## Requirements
-
-
-

## Context
[Additional context or background]
""",
    }

    return default_templates.get(issue_type_lower, "")


def git_create(
    summary: str,
    issue_type: Optional[str] = None,
    description: Optional[str] = None,
    priority: Optional[str] = None,
    points: Optional[int] = None,
    labels: Optional[str] = None,
    assignee: Optional[str] = None,
    milestone: Optional[str] = None,
    repository: Optional[str] = None,
    acceptance_criteria: tuple = (),
    output_json: bool = False,
) -> None:
    """Create a new GitHub/GitLab issue.

    Args:
        summary: Issue title
        issue_type: Optional issue type (bug, enhancement, task, spike, epic). If not provided, no type label is added
        description: Issue description (optional, will use template if not provided)
        priority: Priority level (critical, high, medium, low)
        points: Story points (1, 2, 3, 5, 8, etc.)
        labels: Additional labels (comma-separated)
        assignee: GitHub username to assign
        milestone: Milestone name
        repository: Repository in owner/repo format (optional, will auto-detect)
        acceptance_criteria: List of acceptance criteria
        output_json: Output in JSON format
    """
    config_loader = ConfigLoader()
    config = config_loader.load_config()

    if not config:
        console.print("[yellow]⚠[/yellow] No configuration found")
        console.print("[dim]Run 'daf init' to create default configuration[/dim]")
        sys.exit(1)

    # Normalize and validate issue type if provided
    issue_type_lower = None
    if issue_type:
        issue_type_lower = issue_type.lower()

        # Validate issue type
        valid_types = {"bug", "enhancement", "task", "spike", "epic"}
        if issue_type_lower not in valid_types:
            console.print(f"[red]✗[/red] Invalid issue type: {issue_type}")
            console.print(f"[dim]Valid types: {', '.join(sorted(valid_types))}[/dim]")
            sys.exit(1)

    # Get description from template if not provided
    if not description:
        if issue_type_lower:
            template = _get_issue_template(config, issue_type_lower)
            if template:
                console.print(f"\n[cyan]Using template for {issue_type}...[/cyan]")
                console.print("[dim]Edit the template below:[/dim]\n")
                console.print(template)

                if Confirm.ask("\nUse this template?", default=True):
                    description = template
                else:
                    description = Prompt.ask("Enter description")
            else:
                description = Prompt.ask("Enter description")
        else:
            description = Prompt.ask("Enter description")

    try:
        # Create GitHub client (automatically returns mock in mock mode)
        import os
        is_mock_mode = os.getenv("DAF_MOCK_MODE") == "1"
        # For mock mode, use a dummy repository if not provided
        effective_repository = repository or ("test-owner/test-repo" if is_mock_mode else "")

        client = GitHubClient(repository=repository)
        field_mapper = GitHubFieldMapper()

        # Build required custom fields
        required_custom_fields = {}

        # Add acceptance criteria if provided (convert tuple to list)
        if acceptance_criteria:
            required_custom_fields['acceptance_criteria'] = list(acceptance_criteria)

        # Add additional labels if provided
        if labels:
            additional_labels = [label.strip() for label in labels.split(',')]
            required_custom_fields['labels'] = additional_labels

        # Create the issue
        console_print(f"\n[cyan]Creating GitHub issue...[/cyan]")

        issue_key = client.create_issue(
            issue_type=issue_type_lower,
            summary=summary,
            description=description,
            priority=priority or "",
            project_key=effective_repository,  # Will auto-detect if not provided
            field_mapper=field_mapper,
            required_custom_fields=required_custom_fields,
            points=points,
        )

        # Update assignee if provided
        if assignee:
            try:
                client.update_issue(issue_key, {'assignees': [assignee]})
                console_print(f"[dim]Assigned to @{assignee}[/dim]")
            except Exception as e:
                console_print(f"[yellow]⚠[/yellow] Could not assign to {assignee}: {e}")

        # Update milestone if provided
        if milestone:
            try:
                client.update_issue(issue_key, {'milestone': milestone})
                console_print(f"[dim]Added to milestone: {milestone}[/dim]")
            except Exception as e:
                console_print(f"[yellow]⚠[/yellow] Could not set milestone: {e}")

        console_print(f"\n[green]✓[/green] Created GitHub issue: {issue_key}")

        # If we're in a ticket_creation session, rename it to match the issue
        renamed_session_name = None
        try:
            from devflow.session.manager import SessionManager
            from devflow.session.capture import SessionCapture

            config_loader = ConfigLoader()
            session_manager = SessionManager(config_loader)
            capture = SessionCapture()

            # Check if we're in a session
            current_session_id = capture.get_current_session_id()
            if current_session_id:
                # Find session by Claude session ID
                all_sessions = session_manager.list_sessions()
                current_session = next(
                    (s for s in all_sessions
                     if s.active_conversation and s.active_conversation.ai_agent_session_id == current_session_id),
                    None
                )

                if current_session and current_session.session_type == "ticket_creation":
                    # Convert issue key to session name format (e.g., "owner/repo#123" -> "owner-repo-123")
                    base_name = issue_key_to_session_name(issue_key)
                    new_name = f"creation-{base_name}"

                    # Rename session
                    old_name = current_session.name
                    session_manager.rename_session(old_name, new_name)

                    # Update session metadata
                    renamed_session = session_manager.get_session(new_name)
                    if renamed_session:
                        renamed_session.issue_key = issue_key
                        if not renamed_session.issue_metadata:
                            renamed_session.issue_metadata = {}
                        renamed_session.issue_metadata["summary"] = summary
                        renamed_session.issue_metadata["type"] = issue_type_lower if issue_type_lower else "task"
                        renamed_session.issue_metadata["status"] = "open"
                        session_manager.update_session(renamed_session)

                        renamed_session_name = new_name
                        console_print(f"[green]✓[/green] Renamed session to: [bold]{new_name}[/bold]")
        except Exception as e:
            # Don't fail the whole command if session rename fails
            console_print(f"[yellow]⚠[/yellow] Could not rename session: {e}")

        # JSON output mode
        if output_json:
            session_data = {"issue_key": issue_key}
            if renamed_session_name:
                session_data["session_name"] = renamed_session_name
            json_output(success=True, data=session_data)
            return

        # Show next steps
        console.print("\n[cyan]Next steps:[/cyan]")
        console.print(f"  View: daf github view {issue_key}")
        console.print(f"  Open session: daf github open {issue_key}")

    except IssueTrackerValidationError as e:
        console.print(f"[red]✗[/red] Validation error: {e}")
        if output_json:
            json_output(success=False, error=str(e))
        sys.exit(1)
    except IssueTrackerAuthError as e:
        console.print(f"[red]✗[/red] GitHub authentication failed")
        console.print(f"[dim]Run 'gh auth login' to authenticate[/dim]")
        if output_json:
            json_output(success=False, error=str(e))
        sys.exit(1)
    except IssueTrackerApiError as e:
        console.print(f"[red]✗[/red] GitHub API error: {e}")
        if output_json:
            json_output(success=False, error=str(e))
        sys.exit(1)
    except Exception as e:
        console.print(f"[red]✗[/red] Unexpected error: {e}")
        if output_json:
            json_output(success=False, error=str(e))
        sys.exit(1)
